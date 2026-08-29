"""Resolve one executable UMU runner without silently guessing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


class UmuResolutionError(RuntimeError):
    pass


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))


def resolve_umu_run(
    home: str | os.PathLike[str] | None = None,
    *,
    path_value: str | None = None,
    bundled_candidates: Iterable[str | os.PathLike[str]] | None = None,
) -> Path:
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
        return next(iter(resolved.values()))
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
    return next(iter(path_candidates.values()))
