"""Resolve one executable UMU runner without silently guessing."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, Iterable


class UmuResolutionError(RuntimeError):
    pass


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))


def resolve_umu_run(
    home: str | os.PathLike[str] | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
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

    path_value = which("umu-run")
    if path_value is None:
        raise UmuResolutionError("umu_not_found")
    path = Path(path_value).expanduser()
    try:
        path = path.resolve()
    except OSError as error:
        raise UmuResolutionError("umu_not_found") from error
    if not _is_executable_file(path):
        raise UmuResolutionError("umu_not_found")
    return path
