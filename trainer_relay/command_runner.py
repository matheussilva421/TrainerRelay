"""Bounded, one-shot helper execution for revalidated trainer commands."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .helper_manifest import HelperManifest, HelperManifestError, verify_helper
from .types import CommandContext


COMMAND_TIMEOUT_SECONDS = 5.0
COMMAND_CLEANUP_TIMEOUT_SECONDS = 0.2
MAX_CAPTURE_BYTES = 8192
MAX_JSON_COUNTS = 64
_JSON_FIELDS = {"protocol", "accepted_count", "expected_count", "result_code"}
_ALLOWED_MODIFIER_MASK = 0b111
_ALLOWED_VIRTUAL_KEYS = frozenset(
    {
        *range(0x41, 0x5B),
        *range(0x30, 0x3A),
        *range(0x70, 0x88),
        *range(0x60, 0x6A),
        0x6A,
        0x6B,
        0x6D,
        0x6E,
        0x6F,
        0x2D,
        0x2E,
        0x24,
        0x23,
        0x21,
        0x22,
        0x26,
        0x28,
        0x25,
        0x27,
        0x20,
        0x09,
        0x0D,
        0x08,
        0x13,
        0x14,
        0x91,
        0x90,
    }
)


@dataclass(frozen=True)
class CommandExecution:
    outcome: str
    diagnostic: str | None
    exit_code: int | None
    accepted_count: int | None
    expected_count: int | None
    duration_ms: int

    @property
    def successful(self) -> bool:
        return self.outcome == "requested"

    @property
    def diagnostic_code(self) -> str | None:
        return self.diagnostic

    def to_wire(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "diagnostic": {"code": self.diagnostic} if self.diagnostic else None,
            "exitCode": self.exit_code,
            "acceptedCount": self.accepted_count,
            "expectedCount": self.expected_count,
            "durationMs": self.duration_ms,
        }


class _BoundedCapture:
    def __init__(self, stream: Any, overflow_event: threading.Event | None = None):
        self._stream = stream
        self._buffer = bytearray()
        self._size = 0
        self._overflow = False
        self._overflow_event = overflow_event or threading.Event()
        self._close_lock = threading.Lock()
        self._closed = False

    def read(self) -> None:
        if self._stream is None or not hasattr(self._stream, "read"):
            return
        try:
            while True:
                remaining = MAX_CAPTURE_BYTES - self._size
                chunk = self._stream.read(min(4096, remaining + 1))
                if not chunk:
                    return
                if not isinstance(chunk, bytes):
                    self._overflow = True
                    self._overflow_event.set()
                    self.close()
                    return
                self._size += len(chunk)
                if self._size > MAX_CAPTURE_BYTES:
                    self._overflow = True
                    self._overflow_event.set()
                    self.close()
                    return
                self._buffer.extend(chunk)
        except (OSError, ValueError):
            self._overflow = True
            self._overflow_event.set()
            self.close()

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            stream = self._stream
        close = getattr(stream, "close", None)
        if close is not None:
            try:
                close()
            except (OSError, ValueError):
                return

    @property
    def overflow(self) -> bool:
        return self._overflow

    @property
    def overflow_event(self) -> threading.Event:
        return self._overflow_event

    @property
    def data(self) -> bytes:
        return bytes(self._buffer)


def _kill_process_group(group_id: int, signum: int) -> None:
    os.killpg(group_id, signum)


def _empty_process_group(_group_id: int) -> tuple[()]:
    return ()


class OneShotCommandRunner:
    def __init__(
        self,
        manifest_path: str | os.PathLike[str] | HelperManifest | None = None,
        *,
        manifest: HelperManifest | str | os.PathLike[str] | None = None,
        popen_factory: Callable[..., Any] = subprocess.Popen,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        kill_process_group: Callable[[int, int], None] = _kill_process_group,
        process_group_members: Callable[[int], Any] = _empty_process_group,
    ) -> None:
        if manifest_path is not None and manifest is not None:
            raise ValueError("duplicate_helper_manifest")
        self._manifest = manifest if manifest is not None else manifest_path
        self._popen = popen_factory
        self._monotonic = monotonic
        self._sleep = sleep
        self._kill_process_group = kill_process_group
        self._process_group_members = process_group_members
        self._busy: set[str] = set()
        self._busy_lock = threading.Lock()

    @property
    def busy_identities(self) -> frozenset[str]:
        with self._busy_lock:
            return frozenset(self._busy)

    @staticmethod
    def _result(
        outcome: str,
        diagnostic: str | None,
        started_at: float,
        monotonic: Callable[[], float],
        *,
        exit_code: int | None = None,
        accepted_count: int | None = None,
        expected_count: int | None = None,
    ) -> CommandExecution:
        duration_ms = max(0, int((monotonic() - started_at) * 1000))
        return CommandExecution(outcome, diagnostic, exit_code, accepted_count, expected_count, duration_ms)

    @staticmethod
    def _validate_arguments(vk: Any, modifiers: Any, hold_ms: Any) -> str | None:
        if type(vk) is not int or vk not in _ALLOWED_VIRTUAL_KEYS:
            return "invalid_virtual_key"
        if type(modifiers) is not int or modifiers < 0 or modifiers & ~_ALLOWED_MODIFIER_MASK:
            return "invalid_modifier_mask"
        if type(hold_ms) is not int or not 1 <= hold_ms <= 1000:
            return "invalid_hold_ms"
        return None

    @staticmethod
    def _parse_output(capture: _BoundedCapture) -> tuple[int, int, int] | str:
        if capture.overflow:
            return "helper_output_oversized"
        try:
            text = capture.data.decode("utf-8")
            lines = text.splitlines()
        except UnicodeDecodeError:
            return "helper_output_malformed"
        if len(lines) != 1 or not lines[0].strip() or len(lines[0].encode("utf-8")) > 4096:
            return "helper_output_malformed"
        try:
            value = json.loads(lines[0])
        except (TypeError, ValueError):
            return "helper_output_malformed"
        if not isinstance(value, Mapping) or set(value) != _JSON_FIELDS:
            return "helper_output_malformed"
        protocol = value["protocol"]
        accepted = value["accepted_count"]
        expected = value["expected_count"]
        result_code = value["result_code"]
        if (
            type(protocol) is not int
            or protocol != 1
            or type(accepted) is not int
            or type(expected) is not int
            or type(result_code) is not int
            or not 0 <= accepted <= MAX_JSON_COUNTS
            or not 0 <= expected <= MAX_JSON_COUNTS
        ):
            return "helper_output_malformed"
        if accepted != expected:
            return "helper_input_count_mismatch"
        if result_code != 0:
            return "helper_result_nonzero"
        return accepted, expected, result_code

    @staticmethod
    def _has_reentry_marker(capture: _BoundedCapture, bus: str) -> bool:
        marker = f"INFO: Re-entering container through bus '{bus}'".encode("utf-8")
        return any(line == marker for line in capture.data.splitlines())

    @staticmethod
    def _same_authority(left: CommandContext, right: Any) -> bool:
        if not isinstance(right, CommandContext):
            return False
        return (
            left.identity == right.identity
            and left.session == right.session
            and left.trainer_sha256 == right.trainer_sha256
            and left.trainer_arch == right.trainer_arch
            and left.environment.get("WINEPREFIX") == right.environment.get("WINEPREFIX")
            and dict(left.environment) == dict(right.environment)
            and left.umu_run == right.umu_run
            and left.expected_reentry_bus == right.expected_reentry_bus
        )

    @staticmethod
    def _returncode(process: Any) -> int | None:
        candidate = getattr(process, "returncode", None)
        return candidate if type(candidate) is int else None

    def _wait_for_process(
        self,
        process: Any,
        deadline: float,
        overflow_event: threading.Event | None = None,
    ) -> tuple[bool, int | None, bool]:
        while True:
            if overflow_event is not None and overflow_event.is_set():
                return False, self._returncode(process), True
            remaining = max(0.0, deadline - self._monotonic())
            if remaining <= 0.0:
                return True, None, False
            wait_timeout = min(remaining, 0.05) if overflow_event is not None else remaining
            try:
                returncode = process.wait(timeout=wait_timeout)
            except subprocess.TimeoutExpired:
                if overflow_event is not None and overflow_event.is_set():
                    return False, self._returncode(process), True
                if self._monotonic() >= deadline:
                    return True, None, False
                continue
            except (OSError, ValueError):
                return False, None, False
            if type(returncode) is int:
                return False, returncode, bool(overflow_event and overflow_event.is_set())
            return False, self._returncode(process), bool(overflow_event and overflow_event.is_set())

    def _close_captures(self, captures: tuple[_BoundedCapture, ...], readers: list[threading.Thread]) -> bool:
        for capture in captures:
            capture.close()
        for reader in readers:
            reader.join(timeout=COMMAND_CLEANUP_TIMEOUT_SECONDS)
        if any(reader.is_alive() for reader in readers):
            for capture in captures:
                capture.close()
            for reader in readers:
                reader.join(timeout=COMMAND_CLEANUP_TIMEOUT_SECONDS)
        return not any(reader.is_alive() for reader in readers)

    def _wait_for_empty_group(self, group_id: int) -> bool:
        deadline = self._monotonic() + COMMAND_CLEANUP_TIMEOUT_SECONDS
        while True:
            try:
                members = self._process_group_members(group_id)
                if members is not None and not tuple(members):
                    return True
            except Exception:
                return False
            remaining = deadline - self._monotonic()
            if remaining <= 0.0:
                return False
            self._sleep(min(0.01, remaining))

    def _terminate_process_group(
        self,
        process: Any,
        captures: tuple[_BoundedCapture, ...],
        readers: list[threading.Thread],
    ) -> bool:
        pid = getattr(process, "pid", None)
        cleanup_ok = type(pid) is int and pid > 0
        if cleanup_ok:
            try:
                self._kill_process_group(pid, getattr(signal, "SIGKILL", 9))
            except (OSError, ProcessLookupError, ValueError):
                cleanup_ok = False
        try:
            returncode = process.wait(timeout=COMMAND_CLEANUP_TIMEOUT_SECONDS)
            if type(returncode) is not int and self._returncode(process) is None:
                cleanup_ok = False
        except (OSError, subprocess.TimeoutExpired, ValueError):
            cleanup_ok = False
        cleanup_ok = self._close_captures(captures, readers) and cleanup_ok
        if type(pid) is int and pid > 0:
            cleanup_ok = self._wait_for_empty_group(pid) and cleanup_ok
        return cleanup_ok

    def run(
        self,
        context: CommandContext,
        helper: str | os.PathLike[str],
        vk: int,
        modifiers: int,
        hold_ms: int = 40,
        *,
        lease_factory: Callable[[], Any],
    ) -> CommandExecution:
        started_at = self._monotonic()
        identity = getattr(context, "identity", None)
        if not isinstance(identity, str):
            return self._result("rejected", "invalid_command_context", started_at, self._monotonic)
        with self._busy_lock:
            if identity in self._busy:
                return self._result("rejected", "command_busy", started_at, self._monotonic)
            self._busy.add(identity)
        try:
            argument_error = self._validate_arguments(vk, modifiers, hold_ms)
            if argument_error is not None:
                return self._result("rejected", argument_error, started_at, self._monotonic)
            if not isinstance(context, CommandContext) or not context.expected_reentry_bus:
                return self._result("rejected", "invalid_command_context", started_at, self._monotonic)
            if not isinstance(context.environment, Mapping):
                return self._result("rejected", "invalid_command_context", started_at, self._monotonic)
            if (
                context.environment.get("UMU_CONTAINER_NSENTER") != "1"
                or context.environment.get("PROTON_VERB") != "runinprefix"
                or not context.environment.get("WINEPREFIX")
                or not context.environment.get("PROTONPATH")
                or not context.environment.get("DBUS_SESSION_BUS_ADDRESS")
                or not context.environment.get("XDG_RUNTIME_DIR")
            ):
                return self._result("rejected", "invalid_command_context", started_at, self._monotonic)
            try:
                verified = verify_helper(helper, context.trainer_arch, self._manifest)  # type: ignore[arg-type]
            except (HelperManifestError, TypeError, ValueError) as error:
                code = getattr(error, "code", None)
                return self._result("rejected", code if isinstance(code, str) else "invalid_helper_manifest", started_at, self._monotonic)

            try:
                with lease_factory() as refreshed_context:
                    if not self._same_authority(context, refreshed_context):
                        return self._result("rejected", "command_context_changed", started_at, self._monotonic)
                    try:
                        process = self._popen(
                            [
                                str(refreshed_context.umu_run),
                                str(verified.path),
                                "--protocol",
                                "1",
                                "--key",
                                str(vk),
                                "--modifiers",
                                str(modifiers),
                                "--hold-ms",
                                str(hold_ms),
                            ],
                            env=refreshed_context.environment,
                            shell=False,
                            start_new_session=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            bufsize=0,
                        )
                    except (OSError, TypeError, ValueError):
                        return self._result("failed", "helper_spawn_failed", started_at, self._monotonic)
            except Exception:
                return self._result("rejected", "command_context_revalidation_failed", started_at, self._monotonic)

            overflow_event = threading.Event()
            stdout_capture = _BoundedCapture(getattr(process, "stdout", None), overflow_event)
            stderr_capture = _BoundedCapture(getattr(process, "stderr", None), overflow_event)
            captures = (stdout_capture, stderr_capture)
            readers = [
                threading.Thread(target=stdout_capture.read, daemon=True),
                threading.Thread(target=stderr_capture.read, daemon=True),
            ]
            for reader in readers:
                reader.start()
            try:
                timed_out, exit_code, output_overflowed = self._wait_for_process(
                    process,
                    started_at + COMMAND_TIMEOUT_SECONDS,
                    stdout_capture.overflow_event,
                )
                if timed_out:
                    cleanup_ok = self._terminate_process_group(process, captures, readers)
                    diagnostic = "command_timeout" if cleanup_ok else "command_timeout_cleanup_failed"
                    return self._result("failed", diagnostic, started_at, self._monotonic)
                if output_overflowed and exit_code is None:
                    cleanup_ok = self._terminate_process_group(process, captures, readers)
                    diagnostic = "helper_output_oversized" if cleanup_ok else "helper_output_cleanup_failed"
                    return self._result("failed", diagnostic, started_at, self._monotonic)
                capture_ok = self._close_captures(captures, readers)
                if not capture_ok:
                    return self._result("failed", "helper_output_cleanup_failed", started_at, self._monotonic)
                if type(exit_code) is not int:
                    exit_code = self._returncode(process)
                    if exit_code is None:
                        exit_code = 1
                if exit_code != 0:
                    return self._result("failed", "helper_exit_nonzero", started_at, self._monotonic, exit_code=exit_code)
                if stderr_capture.overflow or stdout_capture.overflow:
                    return self._result("failed", "helper_output_oversized", started_at, self._monotonic, exit_code=exit_code)
                if not self._has_reentry_marker(stderr_capture, context.expected_reentry_bus):
                    return self._result("failed", "container_reentry_marker_missing", started_at, self._monotonic, exit_code=exit_code)
                parsed = self._parse_output(stdout_capture)
                if isinstance(parsed, str):
                    return self._result("failed", parsed, started_at, self._monotonic, exit_code=exit_code)
                accepted_count, expected_count, _result_code = parsed
                return self._result(
                    "requested",
                    None,
                    started_at,
                    self._monotonic,
                    exit_code=exit_code,
                    accepted_count=accepted_count,
                    expected_count=expected_count,
                )
            finally:
                self._close_captures(captures, readers)
        finally:
            with self._busy_lock:
                self._busy.discard(identity)


__all__ = ["CommandExecution", "OneShotCommandRunner"]
