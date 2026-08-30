"""Persistent, privacy-bounded diagnostic event journal."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import is_launch_identity


MAX_DETAIL_STRING_LENGTH = 4096
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
            "store",
            "wineprefix",
            "protonpath",
        }
    ),
    "umu_resolved": frozenset({"source", "umu_path"}),
    "umu_rejected": frozenset({"reason"}),
    "trainer_spawned": frozenset({"trainer_path", "process_group_id"}),
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
            if len(value) > MAX_DETAIL_STRING_LENGTH:
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
        self._malformed_line_count = 0
        self.storage_diagnostic: str | None = None
        self.last_export_path: str | None = None
        if self.enabled:
            self._load_existing()

    def _paths_oldest_first(self) -> list[Path]:
        return [self.root / f"diagnostics.{index}.ndjson" for index in range(self.max_files - 1, -1, -1)]

    def _load_existing(self) -> None:
        self._sequence = 0
        self._malformed_line_count = 0
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
                self._sequence = max(self._sequence, sequence)

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
            oldest.unlink()
        for index in range(self.max_files - 2, -1, -1):
            source = self.root / f"diagnostics.{index}.ndjson"
            if source.exists():
                source.replace(self.root / f"diagnostics.{index + 1}.ndjson")

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
        if self._repeat_count <= 0 or self._repeat_context is None:
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
        self._append_event(summary)
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
        fingerprint = self._event_fingerprint(category, event, outcome, identity, session, safe_details)
        now = self._clock()
        if fingerprint == self._fingerprint:
            self._repeat_count += 1
            if now - self._repeat_started >= 30.0:
                self._flush_repeat()
            return
        self._flush_repeat()
        value = self._new_event(category, event, outcome, safe_details, identity, session)
        self._append_event(value)
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

    def stats(self) -> dict[str, Any]:
        event_count = 0
        malformed = 0
        bytes_used = 0
        for path in self._paths_oldest_first():
            if not path.is_file():
                continue
            try:
                bytes_used += path.stat().st_size
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                malformed += 1
                continue
            for line in lines:
                try:
                    value = json.loads(line)
                    if type(value.get("sequence")) is not int:
                        raise ValueError
                except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
                    malformed += 1
                    continue
                event_count += 1
        return {
            "enabled": self.enabled,
            "bytesUsed": bytes_used,
            "byteLimit": self.max_file_bytes * self.max_files,
            "eventCount": event_count,
            "malformedLineCount": malformed,
            "storageDiagnostic": self.storage_diagnostic,
            "lastExportPath": self.last_export_path,
        }


class NullDiagnosticRecorder:
    enabled = False

    def record(self, *_args: Any, **_kwargs: Any) -> None:
        return

    def flush(self) -> None:
        return
