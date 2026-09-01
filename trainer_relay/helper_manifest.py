"""Fail-closed validation for the packaged Windows input helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


MANIFEST_SCHEMA_VERSION = 1
MAX_PE_OFFSET = 1024 * 1024
SHA256_LENGTH = 64
_ARCHITECTURES = {"x86", "x64"}


class HelperManifestError(ValueError):
    """A bounded reason why a helper cannot be trusted for execution."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class HelperManifestEntry:
    architecture: str
    sha256: str
    path: str | None = None


@dataclass(frozen=True)
class HelperVerification:
    path: Path
    architecture: str
    sha256: str


@dataclass(frozen=True)
class HelperManifest:
    schema_version: int
    helpers: Mapping[str, HelperManifestEntry]

    def __post_init__(self) -> None:
        object.__setattr__(self, "helpers", MappingProxyType(dict(self.helpers)))

    @classmethod
    def load(cls, path: str | Path) -> "HelperManifest":
        manifest_path = Path(path)
        try:
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, UnicodeError, ValueError) as error:
            raise HelperManifestError("invalid_helper_manifest") from error
        return cls.decode(document)

    @classmethod
    def decode(cls, document: Any) -> "HelperManifest":
        if not isinstance(document, Mapping) or set(document) != {"schemaVersion", "helpers"}:
            raise HelperManifestError("invalid_helper_manifest")
        if type(document["schemaVersion"]) is not int or document["schemaVersion"] != MANIFEST_SCHEMA_VERSION:
            raise HelperManifestError("invalid_helper_manifest")
        raw_helpers = document["helpers"]
        if not isinstance(raw_helpers, Mapping) or not raw_helpers:
            raise HelperManifestError("invalid_helper_manifest")

        helpers: dict[str, HelperManifestEntry] = {}
        for architecture, raw_entry in raw_helpers.items():
            if architecture not in _ARCHITECTURES or not isinstance(raw_entry, Mapping):
                raise HelperManifestError("invalid_helper_manifest")
            allowed = {"sha256", "path", "architecture"}
            if set(raw_entry) - allowed != set() or "sha256" not in raw_entry:
                raise HelperManifestError("invalid_helper_manifest")
            sha256 = raw_entry["sha256"]
            if (
                not isinstance(sha256, str)
                or len(sha256) != SHA256_LENGTH
                or any(character not in "0123456789abcdef" for character in sha256)
            ):
                raise HelperManifestError("invalid_helper_manifest")
            declared_architecture = raw_entry.get("architecture", architecture)
            if declared_architecture != architecture:
                raise HelperManifestError("invalid_helper_manifest")
            helper_path = raw_entry.get("path")
            if helper_path is not None and (
                not isinstance(helper_path, str) or not helper_path or Path(helper_path).is_absolute()
            ):
                raise HelperManifestError("invalid_helper_manifest")
            helpers[architecture] = HelperManifestEntry(architecture, sha256, helper_path)
        return cls(MANIFEST_SCHEMA_VERSION, helpers)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, TypeError, ValueError) as error:
        raise HelperManifestError("helper_missing") from error
    return digest.hexdigest()


def read_pe_architecture(path: str | Path) -> str:
    helper_path = Path(path)
    try:
        with helper_path.open("rb") as source:
            dos_header = source.read(0x40)
            if len(dos_header) < 0x40 or dos_header[:2] != b"MZ":
                raise HelperManifestError("helper_architecture_unknown")
            pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
            if pe_offset > MAX_PE_OFFSET:
                raise HelperManifestError("helper_architecture_unknown")
            source.seek(pe_offset)
            signature_and_machine = source.read(6)
    except HelperManifestError:
        raise
    except (OSError, TypeError, ValueError, struct.error) as error:
        raise HelperManifestError("helper_architecture_unknown") from error
    if len(signature_and_machine) != 6 or signature_and_machine[:4] != b"PE\0\0":
        raise HelperManifestError("helper_architecture_unknown")
    machine = struct.unpack_from("<H", signature_and_machine, 4)[0]
    if machine == 0x14C:
        return "x86"
    if machine == 0x8664:
        return "x64"
    raise HelperManifestError("helper_architecture_unknown")


def load_helper_manifest(path: str | Path) -> HelperManifest:
    return HelperManifest.load(path)


def verify_helper(
    helper: str | Path,
    architecture: str,
    manifest: HelperManifest | str | Path,
) -> HelperVerification:
    if architecture not in _ARCHITECTURES:
        raise HelperManifestError("helper_architecture_unknown")
    manifest_path: Path | None = None
    if isinstance(manifest, HelperManifest):
        loaded = manifest
    else:
        manifest_path = Path(manifest)
        loaded = HelperManifest.load(manifest_path)
    entry = loaded.helpers.get(architecture)
    if entry is None:
        raise HelperManifestError("helper_manifest_entry_missing")

    helper_path = Path(helper)
    if not helper_path.is_file():
        raise HelperManifestError("helper_missing")
    if entry.path is not None and manifest_path is not None:
        expected_path = (manifest_path.parent / entry.path).resolve()
        try:
            actual_path = helper_path.resolve()
        except OSError as error:
            raise HelperManifestError("helper_missing") from error
        if actual_path != expected_path:
            raise HelperManifestError("helper_manifest_path_mismatch")

    actual_architecture = read_pe_architecture(helper_path)
    if actual_architecture != architecture or actual_architecture != entry.architecture:
        raise HelperManifestError("helper_architecture_mismatch")
    actual_sha256 = sha256_file(helper_path)
    if not hmac.compare_digest(actual_sha256, entry.sha256):
        raise HelperManifestError("helper_hash_mismatch")
    return HelperVerification(helper_path, actual_architecture, actual_sha256)


__all__ = [
    "HelperManifest",
    "HelperManifestEntry",
    "HelperManifestError",
    "HelperVerification",
    "load_helper_manifest",
    "read_pe_architecture",
    "sha256_file",
    "verify_helper",
]
