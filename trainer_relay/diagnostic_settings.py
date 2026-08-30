"""Validation for persistent Trainer Relay diagnostic settings."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


DIAGNOSTIC_SETTINGS_KEY = "diagnostic_settings_v1"
DIAGNOSTIC_SETTINGS_SCHEMA_VERSION = 1


def empty_diagnostic_settings() -> dict[str, Any]:
    return {"schemaVersion": DIAGNOSTIC_SETTINGS_SCHEMA_VERSION, "enabled": False}


def _parse_document(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _validated(value: Any) -> dict[str, Any] | None:
    document = _parse_document(value)
    if not isinstance(document, Mapping):
        return None
    if type(document.get("schemaVersion")) is not int or document["schemaVersion"] != DIAGNOSTIC_SETTINGS_SCHEMA_VERSION:
        return None
    if type(document.get("enabled")) is not bool:
        return None
    return {"schemaVersion": DIAGNOSTIC_SETTINGS_SCHEMA_VERSION, "enabled": document["enabled"]}


def decode_diagnostic_settings(value: Any) -> dict[str, Any]:
    return _validated(value) or empty_diagnostic_settings()


def validate_diagnostic_settings(value: Any) -> dict[str, Any]:
    validated = _validated(value)
    if validated is None:
        raise ValueError("invalid_diagnostic_settings")
    return validated
