"""Stable `/proc` discovery for supported game sessions."""

from __future__ import annotations

import ntpath
import os
import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True)
class SessionIdentity:
    pid: int
    start_time: int


@dataclass(frozen=True)
class DiscoveryResult:
    state: str
    session: SessionIdentity | None = None
    environment: Mapping[str, str] | None = None
    candidates: tuple[SessionIdentity, ...] = ()
    diagnostic: str | None = None


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


def _basename(value: str) -> str:
    normalized = normalize_wine_path(value)
    return posixpath.basename(normalized) or ntpath.basename(normalized)


class ProcessDiscoverer:
    REQUIRED_ENVIRONMENT = ("WINEPREFIX", "PROTONPATH", "GAMEID", "STORE")

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

    def _candidate(self, process_dir: Path, identity: str, expected_executable: str, expected_prefix: str) -> tuple[SessionIdentity, dict[str, str]] | None:
        try:
            first_stat = parse_proc_stat_start_time(self._read(process_dir / "stat").decode("utf-8"))
            comm = self._read(process_dir / "comm").decode("utf-8").strip()
            command_line = self._read(process_dir / "cmdline")
            environment = _parse_nul_mapping(self._read(process_dir / "environ"))
            second_stat = parse_proc_stat_start_time(self._read(process_dir / "stat").decode("utf-8"))
        except (OSError, UnicodeError, ValueError):
            return None
        if first_stat != second_stat:
            return None
        if any(not environment.get(key) for key in self.REQUIRED_ENVIRONMENT):
            return None

        game_id = identity.split(":", 1)[1]
        if environment["GAMEID"] != game_id:
            return None
        store = environment["STORE"].casefold()
        scheme = identity.split(":", 1)[0]
        if scheme == "gog" and store != "gog":
            return None
        if scheme == "epic" and store not in {"epic", "egs", "none"}:
            return None

        actual_prefix = normalize_wine_path(environment["WINEPREFIX"])
        expected = normalize_wine_path(expected_prefix).rstrip("/")
        if actual_prefix not in {expected, expected + "/pfx"}:
            return None

        expected_normalized = normalize_wine_path(expected_executable).casefold()
        command_matches = any(
            normalize_wine_path(argument.decode("utf-8", errors="ignore")).casefold() == expected_normalized
            for argument in command_line.split(b"\0")
            if argument
        )
        comm_matches = _basename(comm).casefold() == _basename(expected_executable).casefold()
        if not command_matches and not comm_matches:
            return None
        return SessionIdentity(int(process_dir.name), first_stat), environment

    def discover(self, identity: str, expected_executable: str, expected_prefix: str) -> DiscoveryResult:
        candidates: list[tuple[SessionIdentity, dict[str, str]]] = []
        try:
            process_dirs = sorted(
                (entry for entry in self.proc_root.iterdir() if entry.is_dir() and entry.name.isdigit()),
                key=lambda entry: int(entry.name),
            )
        except OSError:
            return DiscoveryResult("waiting_for_game", diagnostic="proc_unreadable")
        for process_dir in process_dirs:
            candidate = self._candidate(process_dir, identity, expected_executable, expected_prefix)
            if candidate is not None:
                candidates.append(candidate)
        sessions = tuple(candidate[0] for candidate in candidates)
        if len(candidates) == 0:
            return DiscoveryResult("waiting_for_game")
        if len(candidates) > 1:
            return DiscoveryResult("ambiguous", candidates=sessions, diagnostic="multiple_game_sessions")
        return DiscoveryResult("session", session=sessions[0], environment=candidates[0][1], candidates=sessions)
