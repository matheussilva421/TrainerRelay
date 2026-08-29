"""Validation and serialisation for the persisted relay configuration."""

from __future__ import annotations

import json
import ntpath
import os
import posixpath
import re
from pathlib import Path
from typing import Any, Callable, Mapping


DEFAULT_CONFIG_KEY = "RelayConfigV1"
SCHEMA_VERSION = 1
IDENTITY_PATTERN = re.compile(r"^(epic|gog):([^\s:]+)$")

FilePredicate = Callable[[str], bool]


def empty_relay_config() -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "games": {}}


def validate_launch_identity(value: Any) -> str:
    if not isinstance(value, str) or IDENTITY_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid_launch_identity")
    return value


def is_launch_identity(value: Any) -> bool:
    try:
        validate_launch_identity(value)
    except ValueError:
        return False
    return True


def game_id_for(identity: str) -> str:
    return validate_launch_identity(identity).split(":", 1)[1]


def default_prefix_for(identity: str, home: str | os.PathLike[str] | None = None) -> str:
    game_id = game_id_for(identity)
    home_value = os.fspath(home) if home is not None else os.environ.get("HOME", str(Path.home()))
    return posixpath.join(home_value.rstrip("/"), ".local", "share", "unifideck", "prefixes", game_id)


def _is_absolute(value: str) -> bool:
    return posixpath.isabs(value) or ntpath.isabs(value)


def _is_regular_file(path: str) -> bool:
    return Path(path).is_file()


def _is_directory(path: str) -> bool:
    return Path(path).is_dir()


def validate_game_config(
    value: Any,
    *,
    file_exists: FilePredicate = _is_regular_file,
    directory_exists: FilePredicate = _is_directory,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    enabled = value.get("enabled")
    trainer_path = value.get("trainerPath")
    if type(enabled) is not bool or not isinstance(trainer_path, str):
        return None
    if not _is_absolute(trainer_path) or not trainer_path.casefold().endswith(".exe"):
        return None
    if not file_exists(trainer_path):
        return None

    result: dict[str, Any] = {"enabled": enabled, "trainerPath": trainer_path}
    if "prefixOverride" in value:
        prefix_override = value["prefixOverride"]
        if (
            not isinstance(prefix_override, str)
            or not _is_absolute(prefix_override)
            or not directory_exists(prefix_override)
        ):
            return None
        result["prefixOverride"] = prefix_override
    return result


def _parse_document(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def decode_relay_config(value: Any) -> dict[str, Any]:
    """Decode stored settings, dropping invalid entries and failing closed."""

    document = _parse_document(value)
    if not isinstance(document, Mapping):
        return empty_relay_config()
    if type(document.get("schemaVersion")) is not int or document["schemaVersion"] != SCHEMA_VERSION:
        return empty_relay_config()
    source_games = document.get("games")
    if not isinstance(source_games, Mapping):
        return empty_relay_config()

    games: dict[str, Any] = {}
    for identity, game in source_games.items():
        if not is_launch_identity(identity):
            continue
        validated = validate_game_config(game)
        if validated is not None:
            games[identity] = validated
    return {"schemaVersion": SCHEMA_VERSION, "games": games}


def validate_relay_config(value: Any) -> dict[str, Any]:
    """Validate an RPC document strictly enough to persist it safely."""

    document = _parse_document(value)
    if not isinstance(document, Mapping):
        raise ValueError("invalid_config")
    if type(document.get("schemaVersion")) is not int or document["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("invalid_config")
    source_games = document.get("games")
    if not isinstance(source_games, Mapping):
        raise ValueError("invalid_config")

    games: dict[str, Any] = {}
    for identity, game in source_games.items():
        if not is_launch_identity(identity):
            raise ValueError("invalid_config_identity")
        validated = validate_game_config(game)
        if validated is None:
            raise ValueError("invalid_config_entry")
        games[identity] = validated
    return {"schemaVersion": SCHEMA_VERSION, "games": games}
