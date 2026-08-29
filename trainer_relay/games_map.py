"""Fail-closed parser for UniFiDeck's games.map file."""

from __future__ import annotations

import os
import ntpath
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import is_launch_identity


@dataclass(frozen=True)
class GamesMapEntry:
    identity: str
    executable: str
    work_dir: str | None = None
    signed_app_id: int | None = None


@dataclass(frozen=True)
class GamesMapDiagnostic:
    code: str
    line: int | None = None


@dataclass(frozen=True)
class GamesMapResult:
    entries: dict[str, GamesMapEntry]
    diagnostic: GamesMapDiagnostic | None = None

    def entry_for(self, identity: str) -> GamesMapEntry | None:
        if self.diagnostic is not None:
            return None
        return self.entries.get(identity)


_INTEGER_APP_ID = re.compile(r"^-?[0-9]+$")


def default_games_map_path(home: str | os.PathLike[str] | None = None) -> Path:
    home_path = Path(home) if home is not None else Path.home()
    return home_path / ".local" / "share" / "unifideck" / "games.map"


def _diagnostic(code: str, line: int | None = None) -> GamesMapResult:
    return GamesMapResult({}, GamesMapDiagnostic(code, line))


def _is_xcloud_sentinel(value: str) -> bool:
    folded = value.strip().casefold()
    return folded == "xcloud" or folded.startswith("xcloud:") or folded.startswith("xcloud://")


def parse_games_map(document: str) -> GamesMapResult:
    if not isinstance(document, str):
        return _diagnostic("games_map_malformed")

    entries: dict[str, GamesMapEntry] = {}
    for line_number, raw_line in enumerate(document.splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in raw_line:
            return _diagnostic("games_map_malformed", line_number)

        key, payload = raw_line.split("=", 1)
        key = key.strip()
        if not key or _is_xcloud_sentinel(key) or not is_launch_identity(key):
            return _diagnostic("games_map_invalid_identity", line_number)
        if key in entries:
            return _diagnostic("games_map_duplicate_identity", line_number)

        fields = payload.split("\t")
        if len(fields) > 3:
            return _diagnostic("games_map_too_many_fields", line_number)
        executable = fields[0]
        if not executable or _is_xcloud_sentinel(executable):
            return _diagnostic("games_map_empty_executable", line_number)
        if not (posixpath.isabs(executable) or ntpath.isabs(executable)):
            return _diagnostic("games_map_relative_executable", line_number)

        work_dir: str | None = None
        signed_app_id: int | None = None
        if len(fields) >= 2:
            work_dir = fields[1]
            if not work_dir:
                return _diagnostic("games_map_empty_work_dir", line_number)
        if len(fields) == 3:
            app_id = fields[2]
            if not _INTEGER_APP_ID.fullmatch(app_id):
                return _diagnostic("games_map_invalid_app_id", line_number)
            signed_app_id = int(app_id)

        entries[key] = GamesMapEntry(key, executable, work_dir, signed_app_id)
    return GamesMapResult(entries)


def load_games_map(path: str | os.PathLike[str]) -> GamesMapResult:
    try:
        document = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return _diagnostic("games_map_unreadable")
    return parse_games_map(document)
