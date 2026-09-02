"""Strict, privacy-bounded Steam Input capability probe export."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import validate_launch_identity


MAX_PROBE_BYTES = 16 * 1024
MAX_RESPONSE_PRIMITIVE_KEYS = 64
MAX_RESPONSE_PRIMITIVE_KEY_LENGTH = 256
MAX_SAFE_APP_ID = 2**53 - 1

_PROBE_FIELDS = frozenset(
    {
        "schemaVersion",
        "appId",
        "identity",
        "controller",
        "controllerIndex",
        "runtimeFingerprint",
        "sourceLayoutIdHash",
        "sourceLayoutNameLength",
        "methodShape",
        "responsePrimitiveKeys",
    }
)
_METHOD_SHAPE_FIELDS = frozenset(
    {"getConfig", "exportConfig", "startEditing", "saveEditing", "setSelected", "showConfigurator"}
)
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RESPONSE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_FORBIDDEN_RESPONSE_KEY_PARTS = (
    "account",
    "token",
    "authorization",
    "secret",
    "password",
    "cookie",
    "credential",
)


class SteamInputProbeStorageError(OSError):
    """Raised when a validated probe cannot be atomically written."""


def _invalid() -> ValueError:
    return ValueError("invalid_steam_input_probe")


def _validate_hash(value: Any) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _invalid()
    return value


def _validate_method_shape(value: Any) -> dict[str, bool]:
    if not isinstance(value, Mapping) or set(value) != _METHOD_SHAPE_FIELDS:
        raise _invalid()
    if any(type(value[key]) is not bool for key in _METHOD_SHAPE_FIELDS):
        raise _invalid()
    return {key: value[key] for key in sorted(_METHOD_SHAPE_FIELDS)}


def _validate_response_keys(value: Any) -> list[str]:
    if type(value) is not list or len(value) > MAX_RESPONSE_PRIMITIVE_KEYS:
        raise _invalid()
    result: list[str] = []
    for key in value:
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= MAX_RESPONSE_PRIMITIVE_KEY_LENGTH
            or _RESPONSE_KEY_PATTERN.fullmatch(key) is None
            or any(part in key.casefold() for part in _FORBIDDEN_RESPONSE_KEY_PARTS)
        ):
            raise _invalid()
        if key in result:
            raise _invalid()
        result.append(key)
    return result


def validate_steam_input_probe(value: Any) -> dict[str, Any]:
    """Return a copy of the only probe shape permitted to cross the RPC boundary."""

    if not isinstance(value, Mapping) or set(value) != _PROBE_FIELDS:
        raise _invalid()
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise _invalid()
    app_id = value["appId"]
    if type(app_id) is not int or not 1 <= app_id <= MAX_SAFE_APP_ID:
        raise _invalid()
    try:
        identity = validate_launch_identity(value["identity"])
    except (TypeError, ValueError):
        raise _invalid() from None
    if (
        value["controller"] != "steam_deck_builtin"
        or type(value["controllerIndex"]) is not int
        or value["controllerIndex"] != 0
    ):
        raise _invalid()
    name_length = value["sourceLayoutNameLength"]
    if type(name_length) is not int or not 0 <= name_length <= 120:
        raise _invalid()
    return {
        "schemaVersion": 1,
        "appId": app_id,
        "identity": identity,
        "controller": "steam_deck_builtin",
        "controllerIndex": 0,
        "runtimeFingerprint": _validate_hash(value["runtimeFingerprint"]),
        "sourceLayoutIdHash": _validate_hash(value["sourceLayoutIdHash"]),
        "sourceLayoutNameLength": name_length,
        "methodShape": _validate_method_shape(value["methodShape"]),
        "responsePrimitiveKeys": _validate_response_keys(value["responsePrimitiveKeys"]),
    }


def _encode_probe(value: Mapping[str, Any]) -> bytes:
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")
    if len(encoded) > MAX_PROBE_BYTES:
        raise ValueError("steam_input_probe_too_large")
    return encoded


def _probe_stem(wall_clock: Callable[[], datetime]) -> str:
    timestamp = wall_clock().astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"TrainerRelay-steam-input-probe-{timestamp}"


def _reserve_probe_path(downloads_dir: Path, stem: str, temporary_path: Path) -> Path:
    suffix = 0
    while True:
        name = f"{stem}.json" if suffix == 0 else f"{stem}-{suffix}.json"
        destination = downloads_dir / name
        try:
            os.link(temporary_path, destination)
            return destination
        except FileExistsError:
            suffix += 1


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            pass
    finally:
        os.close(descriptor)


def export_steam_input_probe(
    value: Any,
    downloads_dir: str | os.PathLike[str],
    *,
    wall_clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Validate and atomically export a newline-terminated UTF-8 JSON report."""

    report = validate_steam_input_probe(value)
    encoded = _encode_probe(report)
    destination: Path | None = None
    temporary_path: Path | None = None
    try:
        directory = Path(downloads_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stem = _probe_stem(wall_clock or (lambda: datetime.now(timezone.utc)))
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".trainer-relay-steam-input-probe-", suffix=".tmp", dir=directory, delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        destination = _reserve_probe_path(directory, stem, temporary_path)
        temporary_path.unlink()
        temporary_path = None
        _fsync_directory(directory)
        return {"path": str(destination.resolve()), "bytesWritten": len(encoded)}
    except (OSError, UnicodeError):
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise SteamInputProbeStorageError("steam_input_probe_export_failed") from None
