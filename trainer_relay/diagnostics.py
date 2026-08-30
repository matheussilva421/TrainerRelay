"""Persistent, privacy-bounded diagnostic event journal."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import is_launch_identity


MAX_DETAIL_STRING_LENGTH = 4096
MAX_UMU_OUTPUT_TAIL_LENGTH = 1024
DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_FILES = 5
_CATEGORIES = {"config", "games_map", "process", "umu", "trainer", "lifecycle"}
_OUTCOMES = {"info", "accepted", "rejected", "warning", "error"}
_FORBIDDEN_KEY_PARTS = ("token", "secret", "password", "cookie", "authorization", "credential")

EVENT_DETAIL_KEYS: dict[str, frozenset[str]] = {
    "diagnostic_mode_changed": frozenset({"enabled"}),
    "plugin_loaded": frozenset({"version"}),
    "plugin_unloaded": frozenset({"version"}),
    "config_loaded": frozenset({"game_count"}),
    "config_persisted": frozenset({"game_count", "enabled", "trainer_path", "prefix_override"}),
    "games_map_loaded": frozenset({"entry_count", "map_path", "expected_executable"}),
    "games_map_rejected": frozenset({"reason", "map_path"}),
    "prefix_selected": frozenset({"source", "expected_prefix"}),
    "process_scan_summary": frozenset(
        {
            "process_count",
            "readable_count",
            "relevant_count",
            "accepted_count",
            "proc_entry_unreadable_count",
            "pid_reused_during_scan_count",
            "missing_required_environment_count",
            "game_id_mismatch_count",
            "process_name_mismatch_count",
            "store_mismatch_count",
            "prefix_mismatch_count",
            "executable_mismatch_count",
            "legacy_settings_present_count",
        }
    ),
    "candidate_rejected": frozenset(
        {
            "reason",
            "expected_executable",
            "observed_executable",
            "expected_prefix",
            "observed_prefix",
            "game_id",
            "process_name",
            "store",
            "wineprefix",
            "protonpath",
        }
    ),
    "candidate_accepted": frozenset(
        {
            "expected_executable",
            "observed_executable",
            "expected_prefix",
            "observed_prefix",
            "game_id",
            "process_name",
            "store",
            "wineprefix",
            "protonpath",
        }
    ),
    "candidate_revalidated": frozenset(
        {
            "expected_executable",
            "observed_executable",
            "expected_prefix",
            "observed_prefix",
            "game_id",
            "process_name",
            "store",
            "wineprefix",
            "protonpath",
        }
    ),
    "umu_resolved": frozenset({"source", "umu_path"}),
    "umu_rejected": frozenset({"reason"}),
    "container_reentry_verified": frozenset({"bus_name", "runtime_variant", "attempt_count"}),
    "container_reentry_rejected": frozenset({"reason"}),
    "umu_exit_diagnostics": frozenset(
        {
            "stdout_bytes",
            "stderr_bytes",
            "stdout_truncated",
            "stderr_truncated",
            "stdout_tail",
            "stderr_tail",
            "failure_class",
            "group_member_count",
            "group_member_names",
            "observed_descendant_count",
            "observed_descendant_names",
        }
    ),
    "trainer_spawned": frozenset(
        {
            "trainer_path",
            "process_group_id",
            "wineprefix",
            "steam_compat_data_path",
            "proton_verb",
            "container_reentry",
            "environment_key_count",
            "runtime_flags",
        }
    ),
    "trainer_spawn_failed": frozenset({"trainer_path", "reason"}),
    "trainer_running": frozenset({"trainer_path", "elapsed_ms"}),
    "trainer_exited": frozenset({"trainer_path", "exit_code", "elapsed_ms"}),
    "trainer_retry_scheduled": frozenset({"retry_count", "delay_ms"}),
    "trainer_manual_retry": frozenset({"retry_count"}),
    "session_changed": frozenset({"previous_pid", "previous_start_time"}),
    "session_ended": frozenset(),
    "owned_group_signal": frozenset({"process_group_id", "signal", "forced"}),
    "event_repeated": frozenset({"repeated_event", "count", "elapsed_ms"}),
}


class DiagnosticValidationError(ValueError):
    pass


class DiagnosticStorageError(OSError):
    """A bounded storage error safe to surface through an RPC adapter."""


@dataclass(frozen=True)
class DiagnosticSession:
    pid: int
    start_time: int

    def to_wire(self) -> dict[str, int]:
        return {"pid": self.pid, "startTime": self.start_time}


@dataclass(frozen=True)
class DiagnosticEvent:
    sequence: int
    timestamp: str
    category: str
    event: str
    outcome: str
    details: Mapping[str, str | int | bool | None]
    identity: str | None = None
    session: DiagnosticSession | None = None

    def to_wire(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "category": self.category,
            "event": self.event,
            "outcome": self.outcome,
            "details": dict(self.details),
        }
        if self.identity is not None:
            value["identity"] = self.identity
        if self.session is not None:
            value["session"] = self.session.to_wire()
        return value


def _utc_timestamp(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_details(event: str, details: Mapping[str, Any] | None) -> dict[str, str | int | bool | None]:
    allowed = EVENT_DETAIL_KEYS.get(event)
    if allowed is None or details is None and allowed:
        raise DiagnosticValidationError("diagnostic_event_rejected")
    source = {} if details is None else details
    if not isinstance(source, Mapping) or any(not isinstance(key, str) for key in source):
        raise DiagnosticValidationError("diagnostic_event_rejected")
    if any(part in key.casefold().replace("-", "_") for key in source for part in _FORBIDDEN_KEY_PARTS):
        raise DiagnosticValidationError("diagnostic_event_rejected")
    if not set(source).issubset(allowed):
        raise DiagnosticValidationError("diagnostic_event_rejected")
    safe: dict[str, str | int | bool | None] = {}
    for key, value in source.items():
        if isinstance(value, str):
            maximum_length = (
                MAX_UMU_OUTPUT_TAIL_LENGTH
                if event == "umu_exit_diagnostics" and key in {"stdout_tail", "stderr_tail"}
                else MAX_DETAIL_STRING_LENGTH
            )
            if len(value) > maximum_length:
                raise DiagnosticValidationError("diagnostic_event_rejected")
        elif value is None or type(value) in {int, bool}:
            pass
        else:
            raise DiagnosticValidationError("diagnostic_event_rejected")
        safe[key] = value
    return safe


class DiagnosticRecorder:
    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        enabled: bool,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        max_files: int = DEFAULT_MAX_FILES,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        if type(enabled) is not bool or max_file_bytes <= 0 or max_files <= 0:
            raise ValueError("invalid_diagnostic_recorder")
        self.root = Path(root)
        self.enabled = enabled
        self.max_file_bytes = int(max_file_bytes)
        self.max_files = int(max_files)
        self._clock = clock
        self._wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self._sequence = 0
        self._fingerprint: str | None = None
        self._repeat_count = 0
        self._repeat_started = 0.0
        self._repeat_context: tuple[str, str | None, DiagnosticSession | None] | None = None
        self._event_count = 0
        self._malformed_line_count = 0
        self._generation = 1
        self._writes_blocked = False
        self.storage_diagnostic: str | None = None
        self.last_export_path: str | None = None
        if self.enabled:
            self._load_existing()
        elif self.root.exists():
            self._load_existing(persist_metadata=False)

    @property
    def _metadata_path(self) -> Path:
        return self.root / "diagnostics.metadata.json"

    @property
    def _metadata_temporary_path(self) -> Path:
        return self.root / ".diagnostics.metadata.tmp"

    def _paths_oldest_first(self) -> list[Path]:
        return [self.root / f"diagnostics.{index}.ndjson" for index in range(self.max_files - 1, -1, -1)]

    def _load_existing(self, *, persist_metadata: bool = True) -> None:
        self._sequence = 0
        self._event_count = 0
        self._malformed_line_count = 0
        self._generation = self._read_generation()
        for path in self._paths_oldest_first():
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                self._malformed_line_count += 1
                continue
            for line in lines:
                try:
                    value = json.loads(line)
                    sequence = value["sequence"]
                    if type(sequence) is not int or sequence < 1:
                        raise ValueError
                except (TypeError, ValueError, KeyError, json.JSONDecodeError):
                    self._malformed_line_count += 1
                    continue
                self._event_count += 1
                self._sequence = max(self._sequence, sequence)
        self._reset_repeat_state()
        if persist_metadata:
            self._retry_storage()
            try:
                self._persist_metadata()
            except OSError:
                self._mark_storage_failure()

    def _read_generation(self) -> int:
        if not self._metadata_path.is_file():
            return 1
        try:
            value = json.loads(self._metadata_path.read_text(encoding="utf-8"))
            generation = value["generation"]
            if type(generation) is not int or generation < 1:
                raise ValueError
            return generation
        except (OSError, UnicodeError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            self._malformed_line_count += 1
            return 1

    def _persist_metadata(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            {"generation": self._generation, "lastSequence": self._sequence},
            sort_keys=True,
            separators=(",", ":"),
        )
        self._metadata_temporary_path.write_text(content + "\n", encoding="utf-8")
        os.replace(self._metadata_temporary_path, self._metadata_path)

    def _retry_storage(self) -> None:
        self._writes_blocked = False
        self.storage_diagnostic = None

    def _mark_storage_failure(self) -> None:
        self._writes_blocked = True
        self.storage_diagnostic = "diagnostic_storage_unavailable"

    def _reset_repeat_state(self) -> None:
        self._fingerprint = None
        self._repeat_count = 0
        self._repeat_started = self._clock()
        self._repeat_context = None

    def _validate(
        self,
        category: str,
        event: str,
        outcome: str,
        identity: str | None,
        session: DiagnosticSession | None,
        details: Mapping[str, Any] | None,
    ) -> dict[str, str | int | bool | None]:
        if category not in _CATEGORIES or outcome not in _OUTCOMES:
            raise DiagnosticValidationError("diagnostic_event_rejected")
        if identity is not None and not is_launch_identity(identity):
            raise DiagnosticValidationError("diagnostic_event_rejected")
        if session is not None and (
            not isinstance(session, DiagnosticSession)
            or type(session.pid) is not int
            or type(session.start_time) is not int
            or session.pid <= 0
            or session.start_time < 0
        ):
            raise DiagnosticValidationError("diagnostic_event_rejected")
        return _safe_details(event, details)

    def _new_event(
        self,
        category: str,
        event: str,
        outcome: str,
        details: Mapping[str, str | int | bool | None],
        identity: str | None,
        session: DiagnosticSession | None,
    ) -> DiagnosticEvent:
        self._sequence += 1
        return DiagnosticEvent(
            self._sequence,
            _utc_timestamp(self._wall_clock()),
            category,
            event,
            outcome,
            details,
            identity,
            session,
        )

    def _rotate(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        oldest = self.root / f"diagnostics.{self.max_files - 1}.ndjson"
        if oldest.exists():
            removed_events, removed_malformed = self._count_file(oldest)
            oldest.unlink()
            self._event_count = max(0, self._event_count - removed_events)
            self._malformed_line_count = max(0, self._malformed_line_count - removed_malformed)
        for index in range(self.max_files - 2, -1, -1):
            source = self.root / f"diagnostics.{index}.ndjson"
            if source.exists():
                source.replace(self.root / f"diagnostics.{index + 1}.ndjson")

    @staticmethod
    def _count_file(path: Path) -> tuple[int, int]:
        valid = 0
        malformed = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return 0, 1
        for line in lines:
            try:
                value = json.loads(line)
                if not isinstance(value, dict) or type(value.get("sequence")) is not int:
                    raise ValueError
            except (TypeError, ValueError, json.JSONDecodeError):
                malformed += 1
            else:
                valid += 1
        return valid, malformed

    def _append_event(self, event: DiagnosticEvent) -> None:
        content = (json.dumps(event.to_wire(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        if len(content) > self.max_file_bytes:
            raise DiagnosticValidationError("diagnostic_event_rejected")
        self.root.mkdir(parents=True, exist_ok=True)
        active = self.root / "diagnostics.0.ndjson"
        active_size = active.stat().st_size if active.exists() else 0
        if active_size + len(content) > self.max_file_bytes:
            self._rotate()
        with active.open("ab") as stream:
            stream.write(content)
        self._event_count += 1
        self._persist_metadata()

    @staticmethod
    def _event_fingerprint(
        category: str,
        event: str,
        outcome: str,
        identity: str | None,
        session: DiagnosticSession | None,
        details: Mapping[str, Any],
    ) -> str:
        value = {
            "category": category,
            "event": event,
            "outcome": outcome,
            "identity": identity,
            "session": session.to_wire() if session else None,
            "details": details,
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def _flush_repeat(self) -> None:
        if self._repeat_count <= 0 or self._repeat_context is None or self._writes_blocked:
            return
        repeated_event, identity, session = self._repeat_context
        elapsed_ms = max(0, int((self._clock() - self._repeat_started) * 1000))
        summary = self._new_event(
            "lifecycle",
            "event_repeated",
            "info",
            {"repeated_event": repeated_event, "count": self._repeat_count, "elapsed_ms": elapsed_ms},
            identity,
            session,
        )
        try:
            self._append_event(summary)
        except OSError:
            self._mark_storage_failure()
            return
        self._repeat_count = 0
        self._repeat_started = self._clock()

    def record(
        self,
        category: str,
        event: str,
        outcome: str,
        *,
        identity: str | None = None,
        session: DiagnosticSession | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        safe_details = self._validate(category, event, outcome, identity, session, details)
        if self._writes_blocked:
            return
        fingerprint = self._event_fingerprint(category, event, outcome, identity, session, safe_details)
        now = self._clock()
        if fingerprint == self._fingerprint:
            self._repeat_count += 1
            if now - self._repeat_started >= 30.0:
                self._flush_repeat()
            return
        self._flush_repeat()
        if self._writes_blocked:
            return
        value = self._new_event(category, event, outcome, safe_details, identity, session)
        try:
            self._append_event(value)
        except OSError:
            self._mark_storage_failure()
            self._reset_repeat_state()
            return
        self._fingerprint = fingerprint
        self._repeat_count = 0
        self._repeat_started = now
        self._repeat_context = (event, identity, session)

    def flush(self) -> None:
        if self.enabled:
            self._flush_repeat()

    def set_enabled(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise ValueError("invalid_diagnostic_settings")
        if self.enabled and not enabled:
            self._flush_repeat()
        self.enabled = enabled
        if enabled:
            self._load_existing()
        else:
            self._reset_repeat_state()

    def _read_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for path in self._paths_oldest_first():
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            for line in lines:
                try:
                    value = json.loads(line)
                    sequence = value["sequence"]
                    if not isinstance(value, dict) or type(sequence) is not int or sequence < 1:
                        raise ValueError
                except (TypeError, ValueError, KeyError, json.JSONDecodeError):
                    continue
                events.append(value)
        events.sort(key=lambda value: value["sequence"])
        return events

    def _cursor(self, sequence: int) -> str:
        return f"v1:{self._generation}:{sequence}"

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[int, int] | None:
        if cursor is None:
            return None
        if not isinstance(cursor, str):
            return None
        match = re.fullmatch(r"v1:([1-9][0-9]*):(0|[1-9][0-9]*)", cursor)
        if match is None:
            return None
        return int(match.group(1)), int(match.group(2))

    def events_after(self, cursor: str | None, limit: int) -> dict[str, Any]:
        if not self.enabled and self.root.exists():
            self._generation = self._read_generation()
        requested = 20 if type(limit) is not int else limit
        bounded_limit = max(1, min(200, requested))
        decoded = self._decode_cursor(cursor)
        cursor_reset = cursor is not None and (decoded is None or decoded[0] != self._generation)
        after_sequence = 0 if decoded is None or cursor_reset else decoded[1]
        available = [event for event in self._read_events() if event["sequence"] > after_sequence]
        selected = available[:bounded_limit]
        next_sequence = selected[-1]["sequence"] if selected else after_sequence
        return {
            "generation": self._generation,
            "nextCursor": self._cursor(next_sequence),
            "cursorReset": cursor_reset,
            "events": selected,
        }

    @staticmethod
    def _text_value(value: Any) -> str:
        if isinstance(value, str) and re.fullmatch(r"[^\s=]+", value):
            return value
        if value is True:
            return "true"
        if value is False:
            return "false"
        if value is None:
            return "null"
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def _event_text(self, event: Mapping[str, Any]) -> str:
        fields = [
            str(event["timestamp"]),
            f"#{event['sequence']}",
            str(event["category"]),
            str(event["outcome"]),
            str(event["event"]),
        ]
        identity = event.get("identity")
        if identity is not None:
            fields.append(f"identity={self._text_value(identity)}")
        session = event.get("session")
        if isinstance(session, Mapping):
            fields.append(f"pid={self._text_value(session.get('pid'))}")
            fields.append(f"startTime={self._text_value(session.get('startTime'))}")
        details = event.get("details")
        if isinstance(details, Mapping):
            fields.extend(f"{key}={self._text_value(details[key])}" for key in sorted(details))
        return " ".join(fields)

    def _next_export_path(self, downloads_dir: Path) -> Path:
        timestamp = self._wall_clock().astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
        stem = f"TrainerRelay-diagnostics-{timestamp}"
        candidate = downloads_dir / f"{stem}.txt"
        suffix = 1
        while candidate.exists():
            candidate = downloads_dir / f"{stem}-{suffix}.txt"
            suffix += 1
        return candidate

    def export_text(self, downloads_dir: Path, plugin_version: str) -> dict[str, Any]:
        self._retry_storage()
        self.flush()
        downloads_dir = Path(downloads_dir)
        temporary_path: Path | None = None
        try:
            downloads_dir.mkdir(parents=True, exist_ok=True)
            destination = self._next_export_path(downloads_dir)
            current_stats = self.stats()
            header = (
                "Trainer Relay diagnostic export\n"
                f"Plugin version: {plugin_version}\n"
                f"Exported UTC: {_utc_timestamp(self._wall_clock())}\n"
                f"Diagnostic mode: {'enabled' if self.enabled else 'disabled'}\n"
                f"Journal bytes: {current_stats['bytesUsed']} / {current_stats['byteLimit']}\n"
                "Privacy: sanitized allowlisted events only; no complete environment, command line, credentials, "
                "or legacy debug-command content; includes bounded sanitized UMU process output tails.\n"
                "\n"
            )
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=".trainer-relay-diagnostics-",
                suffix=".tmp",
                dir=downloads_dir,
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                stream.write(header)
                for event in self._read_events():
                    stream.write(self._event_text(event) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, destination)
            temporary_path = None
            self.last_export_path = str(destination.resolve())
            return {"path": self.last_export_path, "bytesWritten": destination.stat().st_size}
        except (OSError, UnicodeError):
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise DiagnosticStorageError("diagnostic_export_failed") from None

    def clear(self) -> dict[str, Any]:
        self._retry_storage()
        self._reset_repeat_state()
        owned_paths = self._paths_oldest_first() + [self._metadata_path, self._metadata_temporary_path]
        try:
            for path in owned_paths:
                path.unlink(missing_ok=True)
        except OSError:
            self._mark_storage_failure()
            raise DiagnosticStorageError("diagnostic_clear_failed") from None
        self._generation += 1
        self._sequence = 0
        self._event_count = 0
        self._malformed_line_count = 0
        try:
            self._persist_metadata()
        except OSError:
            self._mark_storage_failure()
            raise DiagnosticStorageError("diagnostic_clear_failed") from None
        return self.stats()

    def stats(self) -> dict[str, Any]:
        bytes_used = 0
        unreadable_files = 0
        for path in self._paths_oldest_first():
            if not path.is_file():
                continue
            try:
                bytes_used += path.stat().st_size
            except OSError:
                unreadable_files += 1
        return {
            "enabled": self.enabled,
            "bytesUsed": bytes_used,
            "byteLimit": self.max_file_bytes * self.max_files,
            "eventCount": self._event_count,
            "malformedLineCount": self._malformed_line_count + unreadable_files,
            "storageDiagnostic": self.storage_diagnostic,
            "lastExportPath": self.last_export_path,
        }


class NullDiagnosticRecorder:
    enabled = False

    def record(self, *_args: Any, **_kwargs: Any) -> None:
        return

    def flush(self) -> None:
        return
