"""Owned trainer process-group spawning and shutdown."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Mapping, Sequence

from .process import SessionIdentity


_SIGTERM = getattr(signal, "SIGTERM", 15)
_SIGKILL = getattr(signal, "SIGKILL", 9)
_CAPTURE_BYTES = 4096
_DIAGNOSTIC_TAIL_CHARACTERS = 1024


class _BoundedPipeCapture:
    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._tail = bytearray()
        self._total = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._drain, name="trainer-relay-umu-output", daemon=True)
        self._thread.start()

    def _drain(self) -> None:
        try:
            while True:
                chunk = self._stream.read(4096)
                if not chunk:
                    break
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8", errors="replace")
                with self._lock:
                    self._total += len(chunk)
                    self._tail.extend(chunk)
                    if len(self._tail) > _CAPTURE_BYTES:
                        del self._tail[: len(self._tail) - _CAPTURE_BYTES]
        except (OSError, ValueError):
            pass
        finally:
            try:
                self._stream.close()
            except (OSError, ValueError):
                pass

    def snapshot(self) -> tuple[int, bytes]:
        self._thread.join(timeout=0.25)
        with self._lock:
            return self._total, bytes(self._tail)


def _sanitize_output(value: bytes, *, leading_fragment: bool) -> str:
    text = value.decode("utf-8", errors="replace")
    if leading_fragment:
        _, separator, remainder = text.partition("\n")
        text = "[REDACTED] truncated output line\n" + remainder if separator else "[REDACTED] truncated output line"
    text = "".join(character if character in "\n\t" or ord(character) >= 32 else " " for character in text)
    text = re.sub(
        r"(?i)\b([A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET|COOKIE|AUTHORIZATION|CREDENTIAL|(?:API|ACCESS|PRIVATE)[_-]?KEY)[A-Z0-9_]*)\s*=\s*(?:\"[^\"]*\"|'[^']*'|\S+)",
        r"\1=[REDACTED]",
        text,
    )
    text = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?im)\bAuthorization\s*:\s*[^\r\n]+", "Authorization: [REDACTED]", text)
    text = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", text)
    return text[-_DIAGNOSTIC_TAIL_CHARACTERS:]


def _classify_failure(stdout: str, stderr: str) -> str:
    folded = f"{stderr}\n{stdout}".casefold()
    if not folded.strip():
        return "no_output"
    categories = (
        ("pressure_vessel", ("pressure-vessel", "steam linux runtime")),
        ("container", ("container", "launcher service", "nsenter")),
        ("prefix", ("wineprefix", "compat_data", "compatdata", "prefix")),
        ("proton", ("proton", "compatibility tool")),
        ("wine", ("wine:", "wineserver", ".dll", "win32")),
        ("permission", ("permission denied", "access denied")),
        ("python", ("traceback", "python")),
    )
    for name, markers in categories:
        if any(marker in folded for marker in markers):
            return name
    return "unknown"


def _default_process_group_members(group_id: int) -> tuple[str, ...]:
    names: list[str] = []
    proc_root = Path("/proc")
    if not proc_root.is_dir() or not hasattr(os, "getpgid"):
        return ()
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        return ()
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if os.getpgid(int(entry.name)) != group_id:
                continue
            name = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, ProcessLookupError, ValueError):
            continue
        safe_name = re.sub(r"[^A-Za-z0-9_.+ -]", "?", name)[:64]
        if safe_name:
            names.append(safe_name)
    return tuple(names)


def _default_process_descendants(root_pid: int) -> tuple[str, ...]:
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return ()
    try:
        entries = tuple(entry for entry in proc_root.iterdir() if entry.name.isdigit())
    except OSError:
        return ()
    parents: dict[int, int] = {}
    names: dict[int, str] = {}
    for entry in entries:
        try:
            pid = int(entry.name)
            status = (entry / "status").read_text(encoding="utf-8", errors="replace")
            parent_line = next(line for line in status.splitlines() if line.startswith("PPid:"))
            parent = int(parent_line.split(":", 1)[1].strip())
            name = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, StopIteration, ValueError):
            continue
        parents[pid] = parent
        safe_name = re.sub(r"[^A-Za-z0-9_.+ -]", "?", name)[:64]
        if safe_name:
            names[pid] = safe_name
    descendants: set[int] = set()
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        children = [pid for pid, ppid in parents.items() if ppid == parent and pid not in descendants]
        descendants.update(children)
        pending.extend(children)
    return tuple(names[pid] for pid in descendants if pid in names)


@dataclass
class RunnerHandle:
    session: SessionIdentity
    process: object
    process_group_id: int
    environment: Mapping[str, str]
    stdout_capture: _BoundedPipeCapture | None = None
    stderr_capture: _BoundedPipeCapture | None = None
    observed_descendant_names: set[str] | None = None


@dataclass(frozen=True)
class ExitDiagnostics:
    stdout_bytes: int
    stderr_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool
    stdout_tail: str
    stderr_tail: str
    failure_class: str
    group_member_count: int
    group_member_names: str
    observed_descendant_count: int
    observed_descendant_names: str

    def to_wire(self) -> dict[str, str | int | bool]:
        return {
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "failure_class": self.failure_class,
            "group_member_count": self.group_member_count,
            "group_member_names": self.group_member_names,
            "observed_descendant_count": self.observed_descendant_count,
            "observed_descendant_names": self.observed_descendant_names,
        }


@dataclass(frozen=True)
class StopResult:
    forced: bool


def _signal_process_group(group_id: int, signum: int) -> None:
    kill_group = getattr(os, "killpg", None)
    if kill_group is not None:
        kill_group(group_id, signum)
    else:
        os.kill(group_id, signum)


class OwnedTrainerRunner:
    def __init__(
        self,
        umu_run: str | os.PathLike[str] | Callable[[], str | os.PathLike[str]],
        *,
        popen_factory: Callable[..., object] = subprocess.Popen,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        signal_group: Callable[[int, int], None] = _signal_process_group,
        process_group_members: Callable[[int], Sequence[str]] = _default_process_group_members,
        process_descendants: Callable[[int], Sequence[str]] = _default_process_descendants,
    ) -> None:
        self.umu_run = umu_run
        self._popen = popen_factory
        self._monotonic = monotonic
        self._sleep = sleep
        self._signal_group = signal_group
        self._process_group_members = process_group_members
        self._process_descendants = process_descendants
        self._owned: list[RunnerHandle] = []

    @property
    def owned(self) -> tuple[RunnerHandle, ...]:
        return tuple(self._owned)

    def spawn(self, session: SessionIdentity, trainer_executable: str, environment: Mapping[str, str]) -> RunnerHandle:
        spawn_environment = dict(environment)
        umu_run = self.umu_run() if callable(self.umu_run) else self.umu_run
        process = self._popen(
            [str(umu_run), trainer_executable],
            cwd=str(Path(trainer_executable).parent),
            env=spawn_environment,
            shell=False,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        stdout = getattr(process, "stdout", None)
        stderr = getattr(process, "stderr", None)
        handle = RunnerHandle(
            session,
            process,
            int(process.pid),
            spawn_environment,
            _BoundedPipeCapture(stdout) if hasattr(stdout, "read") else None,
            _BoundedPipeCapture(stderr) if hasattr(stderr, "read") else None,
            set(),
        )
        self._owned.append(handle)
        return handle

    def poll(self, handle: RunnerHandle) -> int | None:
        if handle.observed_descendant_names is not None:
            try:
                handle.observed_descendant_names.update(self._process_descendants(handle.process_group_id))
            except (OSError, ProcessLookupError, ValueError):
                pass
        return handle.process.poll()  # type: ignore[attr-defined]

    def exit_diagnostics(self, handle: RunnerHandle) -> ExitDiagnostics:
        stdout_bytes, stdout_tail_bytes = handle.stdout_capture.snapshot() if handle.stdout_capture else (0, b"")
        stderr_bytes, stderr_tail_bytes = handle.stderr_capture.snapshot() if handle.stderr_capture else (0, b"")
        stdout_truncated = stdout_bytes > len(stdout_tail_bytes)
        stderr_truncated = stderr_bytes > len(stderr_tail_bytes)
        stdout_tail = _sanitize_output(stdout_tail_bytes, leading_fragment=stdout_truncated)
        stderr_tail = _sanitize_output(stderr_tail_bytes, leading_fragment=stderr_truncated)
        members = tuple(sorted(set(self._process_group_members(handle.process_group_id))))
        observed_descendants = tuple(sorted(handle.observed_descendant_names or ()))
        return ExitDiagnostics(
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            failure_class=_classify_failure(stdout_tail, stderr_tail),
            group_member_count=len(members),
            group_member_names=",".join(members)[:_DIAGNOSTIC_TAIL_CHARACTERS],
            observed_descendant_count=len(observed_descendants),
            observed_descendant_names=",".join(observed_descendants)[:_DIAGNOSTIC_TAIL_CHARACTERS],
        )

    def forget(self, handle: RunnerHandle) -> None:
        if handle in self._owned:
            self._owned.remove(handle)

    def stop(self, handle: RunnerHandle) -> StopResult:
        if not any(candidate is handle for candidate in self._owned):
            raise ValueError("unowned_process")
        self._signal_group(handle.process_group_id, _SIGTERM)
        deadline = self._monotonic() + 5.0
        while self.poll(handle) is None and self._monotonic() < deadline:
            self._sleep(0.1)
        forced = self.poll(handle) is None
        if forced:
            self._signal_group(handle.process_group_id, _SIGKILL)
        self._owned.remove(handle)
        return StopResult(forced=forced)
