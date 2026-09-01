"""Validation for the separate, safe manual-cheat-controls configuration."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from collections.abc import Mapping
from typing import Any

from .config import is_launch_identity, validate_launch_identity
from .hotkeys import normalize_hotkey


DEFAULT_CONFIG_KEY = "CheatControlsConfigV1"
SCHEMA_VERSION = 1
MAX_MANUAL_CONTROLS = 64
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def empty_cheat_controls_config() -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "games": {}}


def _parse_document(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def validate_trainer_sha256(value: Any) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid_trainer_sha256")
    return value


def _validate_uuid(value: Any) -> str:
    if not isinstance(value, str) or UUID_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid_cheat_id")
    try:
        uuid.UUID(value)
    except (AttributeError, ValueError):
        raise ValueError("invalid_cheat_id") from None
    return value


def validate_label(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid_cheat_label")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("invalid_cheat_label")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("invalid_cheat_label") from None
    label = value.strip()
    if not 1 <= len(label) <= 80:
        raise ValueError("invalid_cheat_label")
    return label


def _validate_manual_control(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"id", "label", "hotkey"}:
        raise ValueError("invalid_manual_cheat_control")
    return {
        "id": _validate_uuid(value["id"]),
        "label": validate_label(value["label"]),
        "hotkey": normalize_hotkey(value["hotkey"]),
    }


def _validate_game(value: Any, *, limit: bool) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"trainerSha256", "cheats"}:
        raise ValueError("invalid_manual_trainer_controls")
    trainer_sha256 = validate_trainer_sha256(value["trainerSha256"])
    cheats = value["cheats"]
    if type(cheats) is not list:
        raise ValueError("invalid_manual_cheats")
    if len(cheats) > MAX_MANUAL_CONTROLS:
        if not limit:
            raise ValueError("too_many_manual_cheats")
        cheats = cheats[:MAX_MANUAL_CONTROLS]

    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for cheat in cheats:
        try:
            normalized = _validate_manual_control(cheat)
        except ValueError:
            if limit:
                continue
            raise
        if normalized["id"] in seen_ids:
            if limit:
                continue
            raise ValueError("duplicate_manual_cheat_id")
        seen_ids.add(normalized["id"])
        validated.append(normalized)

    return {"trainerSha256": trainer_sha256, "cheats": validated}


def decode_cheat_controls_config(value: Any) -> dict[str, Any]:
    """Decode persisted settings, dropping invalid games and controls."""

    document = _parse_document(value)
    if (
        not isinstance(document, Mapping)
        or type(document.get("schemaVersion")) is not int
        or document["schemaVersion"] != SCHEMA_VERSION
        or not isinstance(document.get("games"), Mapping)
    ):
        return empty_cheat_controls_config()

    games: dict[str, Any] = {}
    for identity, game in document["games"].items():
        if not is_launch_identity(identity):
            continue
        try:
            games[identity] = _validate_game(game, limit=True)
        except ValueError:
            continue
    return {"schemaVersion": SCHEMA_VERSION, "games": games}


def validate_cheat_controls_config(value: Any) -> dict[str, Any]:
    """Validate the complete document before writing it to settings."""

    document = _parse_document(value)
    if not isinstance(document, Mapping) or set(document) != {"schemaVersion", "games"}:
        raise ValueError("invalid_cheat_controls_config")
    if type(document["schemaVersion"]) is not int or document["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("invalid_cheat_controls_config")
    if not isinstance(document["games"], Mapping):
        raise ValueError("invalid_cheat_controls_config")

    games: dict[str, Any] = {}
    for identity, game in document["games"].items():
        try:
            validated_identity = validate_launch_identity(identity)
            games[validated_identity] = _validate_game(game, limit=False)
        except ValueError as error:
            if error.args and str(error) in {"invalid_launch_identity", "invalid_manual_trainer_controls", "invalid_manual_cheats"}:
                raise ValueError("invalid_cheat_controls_config") from error
            raise
    return {"schemaVersion": SCHEMA_VERSION, "games": games}


def new_manual_cheat_control(label: str, hotkey: Mapping[str, Any]) -> dict[str, Any]:
    """Create a safe manual control with a backend-generated UUID."""

    return {
        "id": str(uuid.uuid4()),
        "label": validate_label(label),
        "hotkey": normalize_hotkey(hotkey),
    }
