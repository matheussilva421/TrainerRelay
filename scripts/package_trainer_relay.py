#!/usr/bin/env python3
"""Create the relocatable Trainer Relay Decky plugin archive."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "dist/index.js",
    "main.py",
    "plugin.json",
    "package.json",
    "README.md",
    "CONTEXT.md",
    "LICENSE",
    "docs/adr/0001-session-watcher.md",
    "docs/STEAM-DECK-VALIDATION.md",
)
TEXT_SUFFIXES = {".js", ".md", ".py", ".json", ""}


def iter_package_files() -> list[Path]:
    files = [ROOT / relative_path for relative_path in REQUIRED_FILES]
    runtime_dir = ROOT / "trainer_relay"
    files.extend(sorted(runtime_dir.rglob("*.py")))
    return files


def validate_sources(files: list[Path]) -> None:
    missing = [path.relative_to(ROOT).as_posix() for path in files if not path.is_file()]
    if missing:
        missing_text = ", ".join(missing)
        raise FileNotFoundError(f"required package files are missing: {missing_text}")

    invalid_runtime = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "trainer_relay").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".py"
    ]
    if invalid_runtime:
        invalid_text = ", ".join(invalid_runtime)
        raise ValueError(f"trainer_relay contains non-Python runtime files: {invalid_text}")


def write_archive(output: Path, files: list[Path]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for source in sorted(files, key=lambda path: path.relative_to(ROOT).as_posix()):
            source_relative = source.relative_to(ROOT)
            if source_relative.parts[0] == "trainer_relay":
                relative_path = Path("TrainerRelay") / "py_modules" / source_relative
            else:
                relative_path = Path("TrainerRelay") / source_relative
            archive_name = relative_path.as_posix()
            info = ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            info.compress_type = ZIP_STORED
            content = source.read_bytes()
            if source.suffix.lower() in TEXT_SUFFIXES:
                content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            archive.writestr(info, content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=ROOT / "TrainerRelay.zip",
        help="destination archive path (default: TrainerRelay.zip in the repository root)",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    files = iter_package_files()
    validate_sources(files)
    if output in {path.resolve() for path in files}:
        raise ValueError("archive output cannot replace a package source file")
    if output.suffix.lower() != ".zip":
        raise ValueError("archive output must use the .zip extension")
    write_archive(output, files)
    print(os.fspath(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
