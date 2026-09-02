"""Validation for bounded metadata about generated Steam Input layouts."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from .cheat_config import validate_trainer_sha256
from .config import validate_launch_identity


RADIAL_LAYOUT_REGISTRY_KEY = "RadialLayoutRegistryV1"
RADIAL_LAYOUT_REGISTRY_SCHEMA_VERSION = 1
MAX_RADIAL_LAYOUTS = 128
MAX_SAFE_APP_ID = 2**53 - 1
MAX_RADIAL_LAYOUT_REVISION = 2**31 - 1

RADIAL_LAYOUT_FIELDS = frozenset(
    {
        "appId",
        "identity",
        "trainerSha256",
        "catalogFingerprint",
        "steamRuntimeFingerprint",
        "sourceLayoutId",
        "generatedLayoutId",
        "generatedLayoutName",
        "revision",
        "createdAt",
    }
)
_RADIAL_LAYOUT_KEYS = set(RADIAL_LAYOUT_FIELDS)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$"
)


def empty_radial_layout_registry() -> dict[str, Any]:
    return {"schemaVersion": RADIAL_LAYOUT_REGISTRY_SCHEMA_VERSION, "layouts": []}


def _parse_document(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _validate_app_id(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_SAFE_APP_ID:
        raise ValueError("invalid_radial_app_id")
    return value


def _validate_fingerprint(value: Any, code: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(code)
    return value


def _validate_printable(value: Any, *, maximum: int, code: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise ValueError(code)
    if not value.isprintable() or any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(code)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(code) from None
    return value


def _parse_utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or _UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid_radial_created_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid_radial_created_at") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("invalid_radial_created_at")
    return parsed


def _validate_revision(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_RADIAL_LAYOUT_REVISION:
        raise ValueError("invalid_radial_revision")
    return value


def _validate_radial_layout(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _RADIAL_LAYOUT_KEYS:
        raise ValueError("invalid_generated_radial_layout")

    app_id = _validate_app_id(value["appId"])
    try:
        identity = validate_launch_identity(value["identity"])
    except ValueError:
        raise ValueError("invalid_radial_identity") from None
    trainer_sha256 = validate_trainer_sha256(value["trainerSha256"])
    catalog_fingerprint = _validate_fingerprint(value["catalogFingerprint"], "invalid_radial_catalog_fingerprint")
    steam_runtime_fingerprint = _validate_fingerprint(
        value["steamRuntimeFingerprint"], "invalid_radial_runtime_fingerprint"
    )
    source_layout_id = _validate_printable(value["sourceLayoutId"], maximum=256, code="invalid_radial_source_layout_id")
    generated_layout_id = _validate_printable(
        value["generatedLayoutId"], maximum=256, code="invalid_radial_generated_layout_id"
    )
    if source_layout_id == generated_layout_id:
        raise ValueError("radial_layout_ids_must_differ")
    generated_layout_name = _validate_printable(
        value["generatedLayoutName"], maximum=120, code="invalid_radial_generated_layout_name"
    )
    revision = _validate_revision(value["revision"])
    _parse_utc_timestamp(value["createdAt"])

    return {
        "appId": app_id,
        "identity": identity,
        "trainerSha256": trainer_sha256,
        "catalogFingerprint": catalog_fingerprint,
        "steamRuntimeFingerprint": steam_runtime_fingerprint,
        "sourceLayoutId": source_layout_id,
        "generatedLayoutId": generated_layout_id,
        "generatedLayoutName": generated_layout_name,
        "revision": revision,
        "createdAt": value["createdAt"],
    }


def validate_generated_radial_layout(value: Any) -> dict[str, Any]:
    """Validate one generated-layout record and return a fresh safe dictionary."""

    return _validate_radial_layout(_parse_document(value))


def _validate_registry_document(value: Any) -> dict[str, Any]:
    document = _parse_document(value)
    if not isinstance(document, Mapping) or set(document) != {"schemaVersion", "layouts"}:
        raise ValueError("invalid_radial_layout_registry")
    if type(document["schemaVersion"]) is not int or document["schemaVersion"] != RADIAL_LAYOUT_REGISTRY_SCHEMA_VERSION:
        raise ValueError("invalid_radial_layout_registry")
    layouts = document["layouts"]
    if type(layouts) is not list:
        raise ValueError("invalid_radial_layout_registry")
    if len(layouts) > MAX_RADIAL_LAYOUTS:
        raise ValueError("too_many_radial_layouts")
    return {
        "schemaVersion": RADIAL_LAYOUT_REGISTRY_SCHEMA_VERSION,
        "layouts": [_validate_radial_layout(layout) for layout in layouts],
    }


def validate_radial_layout_registry(value: Any) -> dict[str, Any]:
    """Validate the complete persisted registry without accepting partial writes."""

    return _validate_registry_document(value)


def decode_radial_layout_registry(value: Any) -> dict[str, Any]:
    """Decode settings, dropping invalid records and retaining the newest 128."""

    document = _parse_document(value)
    if (
        not isinstance(document, Mapping)
        or type(document.get("schemaVersion")) is not int
        or document["schemaVersion"] != RADIAL_LAYOUT_REGISTRY_SCHEMA_VERSION
        or type(document.get("layouts")) is not list
    ):
        return empty_radial_layout_registry()

    valid_layouts: list[dict[str, Any]] = []
    for layout in document["layouts"]:
        try:
            valid_layouts.append(_validate_radial_layout(layout))
        except ValueError:
            continue
    valid_layouts.sort(key=lambda layout: (_parse_utc_timestamp(layout["createdAt"]), layout["revision"]))
    return {
        "schemaVersion": RADIAL_LAYOUT_REGISTRY_SCHEMA_VERSION,
        "layouts": valid_layouts[-MAX_RADIAL_LAYOUTS:],
    }


def next_radial_layout_revision(
    registry: Any,
    app_id: Any,
    identity: Any,
    trainer_sha256: Any,
    catalog_fingerprint: Any,
) -> int:
    """Return the next revision for one AppID/identity/build/catalog scope."""

    expected_app_id = _validate_app_id(app_id)
    try:
        expected_identity = validate_launch_identity(identity)
    except ValueError:
        raise ValueError("invalid_radial_identity") from None
    expected_trainer_sha256 = validate_trainer_sha256(trainer_sha256)
    expected_catalog_fingerprint = _validate_fingerprint(catalog_fingerprint, "invalid_radial_catalog_fingerprint")

    decoded = decode_radial_layout_registry(registry)
    latest = 0
    for layout in decoded["layouts"]:
        if (
            layout["appId"],
            layout["identity"],
            layout["trainerSha256"],
            layout["catalogFingerprint"],
        ) == (
            expected_app_id,
            expected_identity,
            expected_trainer_sha256,
            expected_catalog_fingerprint,
        ):
            latest = max(latest, layout["revision"])
    if latest == MAX_RADIAL_LAYOUT_REVISION:
        raise ValueError("radial_revision_exhausted")
    return latest + 1
