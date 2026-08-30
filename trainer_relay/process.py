"""Stable `/proc` discovery for supported game sessions."""

from __future__ import annotations

import os
import posixpath
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from .types import DiscoveryState


@dataclass(frozen=True)
class SessionIdentity:
    pid: int
    start_time: int


@dataclass(frozen=True)
class CandidateDecision:
    pid: int
    start_time: int
    relevant: bool
    accepted: bool
    reason: str
    details: Mapping[str, str]
    session: SessionIdentity | None = None
    environment: Mapping[str, str] | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    state: DiscoveryState
    session: SessionIdentity | None = None
    environment: Mapping[str, str] | None = None
    candidates: tuple[SessionIdentity, ...] = ()
    diagnostic: str | None = None
    decisions: tuple[CandidateDecision, ...] = ()
    rejection_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", DiscoveryState(self.state))


def normalize_wine_path(value: str) -> str:
    """Convert a proc/Wine path to a stable slash-separated comparison form."""

    normalized = value.replace("\\", "/")
    if len(normalized) >= 2 and normalized[1] == ":":
        if normalized[0].casefold() == "z":
            normalized = normalized[2:] or "/"
        else:
            normalized = normalized[0].casefold() + normalized[1:]
    if normalized.startswith("//"):
        normalized = "/" + normalized.lstrip("/")
    return posixpath.normpath(normalized)


def _stat_body(stat: str) -> str:
    closing = stat.rfind(")")
    if closing < 0:
        raise ValueError("invalid_proc_stat")
    return stat[closing + 1 :].lstrip()


def parse_proc_stat_start_time(stat: str) -> int:
    fields = _stat_body(stat).split()
    # The body begins with field 3, so field 22 is offset 19.
    if len(fields) <= 19:
        raise ValueError("invalid_proc_stat")
    try:
        return int(fields[19])
    except ValueError as error:
        raise ValueError("invalid_proc_stat") from error


def _parse_nul_mapping(raw: bytes) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            values[key.decode("utf-8")] = value.decode("utf-8")
        except UnicodeDecodeError:
            continue
    return values


class ProcessDiscoverer:
    REQUIRED_ENVIRONMENT = ("WINEPREFIX", "PROTONPATH", "GAMEID", "STORE")
    LEGACY_ENVIRONMENT = ("PROTON_REMOTE_DEBUG_CMD", "PRESSURE_VESSEL_FILESYSTEMS_RW")

    def __init__(
        self,
        proc_root: str | os.PathLike[str] = "/proc",
        *,
        read_bytes: Callable[[Path], bytes] | None = None,
    ) -> None:
        self.proc_root = Path(proc_root)
        self._read_bytes = read_bytes or (lambda path: path.read_bytes())

    def _read(self, path: Path) -> bytes:
        return self._read_bytes(path)

    @staticmethod
    def _store_matches(scheme: str, store: str) -> bool:
        normalized = store.casefold()
        if scheme == "gog":
            return normalized == "gog"
        return scheme == "epic" and normalized in {"epic", "egs", "none"}

    @staticmethod
    def _observed_executable(arguments: list[str], expected_normalized: str) -> str:
        for argument in arguments:
            if normalize_wine_path(argument).casefold() == expected_normalized:
                return normalize_wine_path(argument)
        for argument in arguments:
            normalized = normalize_wine_path(argument)
            if normalized.casefold().endswith(".exe"):
                return normalized
        return ""

    @staticmethod
    def _details(
        environment: Mapping[str, str],
        expected_executable: str,
        observed_executable: str,
        expected_prefix: str,
    ) -> dict[str, str]:
        wineprefix = environment.get("WINEPREFIX", "")
        values = {
            "expected_executable": normalize_wine_path(expected_executable),
            "observed_executable": observed_executable,
            "expected_prefix": normalize_wine_path(expected_prefix).rstrip("/"),
            "observed_prefix": normalize_wine_path(wineprefix) if wineprefix else "",
            "game_id": environment.get("GAMEID", ""),
            "store": environment.get("STORE", ""),
            "wineprefix": wineprefix,
            "protonpath": environment.get("PROTONPATH", ""),
        }
        return {key: value for key, value in values.items() if value}

    def _evaluate(
        self, process_dir: Path, identity: str, expected_executable: str, expected_prefix: str
    ) -> CandidateDecision:
        pid = int(process_dir.name)
        try:
            first_stat = parse_proc_stat_start_time(self._read(process_dir / "stat").decode("utf-8"))
            command_line = self._read(process_dir / "cmdline")
            environment = _parse_nul_mapping(self._read(process_dir / "environ"))
        except (OSError, UnicodeError, ValueError):
            return CandidateDecision(pid, 0, False, False, "proc_entry_unreadable", {})

        arguments = [argument.decode("utf-8", errors="ignore") for argument in command_line.split(b"\0") if argument]
        expected_normalized = normalize_wine_path(expected_executable).casefold()
        observed_executable = self._observed_executable(arguments, expected_normalized)
        expected_basename = posixpath.basename(expected_normalized)
        executable_basename_matches = any(
            posixpath.basename(normalize_wine_path(argument).casefold()) == expected_basename for argument in arguments
        )
        game_id = identity.split(":", 1)[1]
        scheme = identity.split(":", 1)[0]
        expected = normalize_wine_path(expected_prefix).rstrip("/")
        wineprefix = environment.get("WINEPREFIX", "")
        actual_prefix = normalize_wine_path(wineprefix) if wineprefix else ""
        prefix_matches = actual_prefix in {expected, expected + "/pfx"}
        store_matches = self._store_matches(scheme, environment.get("STORE", ""))
        relevant = (
            executable_basename_matches
            or environment.get("GAMEID") == game_id
            or (store_matches and prefix_matches)
            or identity in arguments
        )
        details = self._details(environment, expected_executable, observed_executable, expected_prefix)

        try:
            second_stat = parse_proc_stat_start_time(self._read(process_dir / "stat").decode("utf-8"))
        except (OSError, UnicodeError, ValueError):
            return CandidateDecision(pid, first_stat, relevant, False, "proc_entry_unreadable", details)
        if first_stat != second_stat:
            return CandidateDecision(pid, first_stat, relevant, False, "pid_reused_during_scan", details)
        if any(not environment.get(key) for key in self.REQUIRED_ENVIRONMENT):
            return CandidateDecision(pid, first_stat, relevant, False, "missing_required_environment", details)

        if environment["GAMEID"] != game_id:
            return CandidateDecision(pid, first_stat, relevant, False, "game_id_mismatch", details)
        if not store_matches:
            return CandidateDecision(pid, first_stat, relevant, False, "store_mismatch", details)
        if not prefix_matches:
            return CandidateDecision(pid, first_stat, relevant, False, "prefix_mismatch", details)
        command_matches = any(
            normalize_wine_path(argument.decode("utf-8", errors="ignore")).casefold() == expected_normalized
            for argument in command_line.split(b"\0")
            if argument
        )
        if not command_matches:
            return CandidateDecision(pid, first_stat, relevant, False, "executable_mismatch", details)
        if any(key in environment for key in self.LEGACY_ENVIRONMENT):
            return CandidateDecision(pid, first_stat, True, False, "legacy_settings_present", details)
        session = SessionIdentity(pid, first_stat)
        return CandidateDecision(pid, first_stat, True, True, "candidate_accepted", details, session, environment)

    def discover(self, identity: str, expected_executable: str, expected_prefix: str) -> DiscoveryResult:
        try:
            process_dirs = sorted(
                (entry for entry in self.proc_root.iterdir() if entry.is_dir() and entry.name.isdigit()),
                key=lambda entry: int(entry.name),
            )
        except OSError:
            return DiscoveryResult(DiscoveryState.WAITING_FOR_GAME, diagnostic="proc_unreadable")
        decisions = tuple(
            self._evaluate(process_dir, identity, expected_executable, expected_prefix) for process_dir in process_dirs
        )
        accepted = tuple(decision for decision in decisions if decision.accepted and decision.session is not None)
        sessions = tuple(decision.session for decision in accepted if decision.session is not None)
        rejection_counts = dict(Counter(decision.reason for decision in decisions if not decision.accepted))
        if any(decision.reason == "legacy_settings_present" for decision in decisions):
            return DiscoveryResult(
                DiscoveryState.INVALID_CONFIG,
                candidates=sessions,
                diagnostic="legacy_settings_present",
                decisions=decisions,
                rejection_counts=rejection_counts,
            )
        if len(accepted) == 0:
            precedence = (
                "pid_reused_during_scan",
                "missing_required_environment",
                "game_id_mismatch",
                "store_mismatch",
                "prefix_mismatch",
                "executable_mismatch",
            )
            relevant_reasons = {decision.reason for decision in decisions if decision.relevant}
            diagnostic = next((reason for reason in precedence if reason in relevant_reasons), None)
            return DiscoveryResult(
                DiscoveryState.WAITING_FOR_GAME,
                diagnostic=diagnostic,
                decisions=decisions,
                rejection_counts=rejection_counts,
            )
        if len(accepted) > 1:
            return DiscoveryResult(
                DiscoveryState.AMBIGUOUS,
                candidates=sessions,
                diagnostic="multiple_game_sessions",
                decisions=decisions,
                rejection_counts=rejection_counts,
            )
        return DiscoveryResult(
            DiscoveryState.SESSION,
            session=sessions[0],
            environment=accepted[0].environment,
            candidates=sessions,
            decisions=decisions,
            rejection_counts=rejection_counts,
        )
