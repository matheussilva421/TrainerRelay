#!/usr/bin/env python3
"""Generate the deterministic manifest for the packaged Win32 helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


MACHINE_BY_ARCHITECTURE = {"x86": 0x014C, "x64": 0x8664}
MANIFEST_SCHEMA_VERSION = 1
MAX_PE_OFFSET = 1024 * 1024
MANIFEST_TOP_LEVEL_KEYS = {"schemaVersion", "helpers"}
MANIFEST_HELPER_KEYS = {"architecture", "path", "sha256"}


def read_pe_machine(path: Path) -> int:
    with path.open("rb") as source:
        dos_header = source.read(0x40)
        if len(dos_header) != 0x40 or dos_header[:2] != b"MZ":
            raise ValueError(f"{path.name}: invalid DOS header")
        pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
        if pe_offset > MAX_PE_OFFSET:
            raise ValueError(f"{path.name}: PE header offset is out of bounds")
        source.seek(pe_offset)
        signature_and_machine = source.read(6)
    if len(signature_and_machine) != 6 or signature_and_machine[:4] != b"PE\0\0":
        raise ValueError(f"{path.name}: invalid PE signature")
    return struct.unpack_from("<H", signature_and_machine, 4)[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(input_directory: Path) -> dict[str, object]:
    helpers: dict[str, dict[str, str]] = {}
    for architecture, expected_machine in MACHINE_BY_ARCHITECTURE.items():
        helper = input_directory / f"TrainerRelay.InputHelper.{architecture}.exe"
        if not helper.is_file():
            raise FileNotFoundError(f"missing helper: {helper}")
        machine = read_pe_machine(helper)
        if machine != expected_machine:
            raise ValueError(
                f"{helper.name}: expected PE machine 0x{expected_machine:04x}, got 0x{machine:04x}"
            )
        helpers[architecture] = {
            "architecture": architecture,
            "path": helper.name,
            "sha256": sha256_file(helper),
        }
    return {"schemaVersion": MANIFEST_SCHEMA_VERSION, "helpers": helpers}


def validate_helper_manifest(input_directory: Path, manifest_path: Path) -> None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid helper manifest: {error}") from error

    if (
        not isinstance(manifest, dict)
        or set(manifest) != MANIFEST_TOP_LEVEL_KEYS
        or type(manifest.get("schemaVersion")) is not int
        or manifest["schemaVersion"] != MANIFEST_SCHEMA_VERSION
        or not isinstance(manifest.get("helpers"), dict)
        or set(manifest["helpers"]) != set(MACHINE_BY_ARCHITECTURE)
    ):
        raise ValueError("invalid helper manifest schema")

    helpers = manifest["helpers"]
    for architecture, expected_machine in MACHINE_BY_ARCHITECTURE.items():
        entry = helpers[architecture]
        expected_name = f"TrainerRelay.InputHelper.{architecture}.exe"
        if (
            not isinstance(entry, dict)
            or set(entry) != MANIFEST_HELPER_KEYS
            or entry.get("architecture") != architecture
            or entry.get("path") != expected_name
            or not isinstance(entry.get("sha256"), str)
            or len(entry["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in entry["sha256"])
        ):
            raise ValueError(f"invalid helper manifest schema for {architecture}")

        helper = input_directory / expected_name
        if not helper.is_file():
            raise ValueError(f"missing helper: {expected_name}")
        machine = read_pe_machine(helper)
        if machine != expected_machine:
            raise ValueError(
                f"{expected_name}: expected PE machine 0x{expected_machine:04x}, got 0x{machine:04x}"
            )
        actual_hash = sha256_file(helper)
        if entry["sha256"] != actual_hash:
            raise ValueError(f"{expected_name}: helper hash mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = build_manifest(args.input_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
