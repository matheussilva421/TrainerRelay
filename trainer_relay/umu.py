"""Resolve one executable UMU runner without silently guessing."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal


class UmuResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class UmuResolution:
    path: Path
    source: Literal["bundled", "path"]


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))


def resolve_umu_run(
    home: str | os.PathLike[str] | None = None,
    *,
    path_value: str | None = None,
    bundled_candidates: Iterable[str | os.PathLike[str]] | None = None,
) -> Path:
    return resolve_umu_run_details(
        home,
        path_value=path_value,
        bundled_candidates=bundled_candidates,
    ).path


def resolve_umu_run_details(
    home: str | os.PathLike[str] | None = None,
    *,
    path_value: str | None = None,
    bundled_candidates: Iterable[str | os.PathLike[str]] | None = None,
) -> UmuResolution:
    home_path = Path(home) if home is not None else Path.home()
    candidates = (
        [
            home_path / "homebrew" / "plugins" / "Unifideck" / "bin" / "umu" / "umu" / "umu-run",
            home_path / "homebrew" / "plugins" / "unifideck" / "bin" / "umu" / "umu" / "umu-run",
        ]
        if bundled_candidates is None
        else [Path(candidate) for candidate in bundled_candidates]
    )
    resolved: dict[str, Path] = {}
    for candidate in candidates:
        try:
            absolute = candidate.expanduser().resolve()
        except OSError:
            continue
        if _is_executable_file(absolute):
            resolved[str(absolute)] = absolute
    if len(resolved) == 1:
        return UmuResolution(next(iter(resolved.values())), "bundled")
    if len(resolved) > 1:
        raise UmuResolutionError("umu_ambiguous")

    path_candidates: dict[str, Path] = {}
    search_path = os.environ.get("PATH", "") if path_value is None else path_value
    for directory in search_path.split(os.pathsep):
        if not directory:
            continue
        try:
            candidate = (Path(directory).expanduser() / "umu-run").resolve()
        except OSError:
            continue
        if _is_executable_file(candidate):
            path_candidates[os.path.normcase(str(candidate))] = candidate
    if len(path_candidates) == 0:
        raise UmuResolutionError("umu_not_found")
    if len(path_candidates) > 1:
        raise UmuResolutionError("umu_ambiguous")
    return UmuResolution(next(iter(path_candidates.values())), "path")
