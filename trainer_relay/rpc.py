"""Typed, sanitised RPC adapter for the Decky backend."""

from __future__ import annotations

import inspect
import re
from collections.abc import Mapping
from typing import Any

from .config import DEFAULT_CONFIG_KEY, decode_relay_config, empty_relay_config, validate_game_config, validate_launch_identity


class RelayRpcError(ValueError):
    pass


_SAFE_CODE = re.compile(r"^[a-z0-9_]+$")
_STATES = {
    "disabled",
    "waiting_for_game",
    "launching",
    "running",
    "retrying",
    "failed",
    "ambiguous",
    "invalid_config",
}


class RelayRpc:
    def __init__(self, settings: Any, watcher: Any) -> None:
        self._settings = settings
        self._watcher = watcher

    def _load(self) -> dict[str, Any]:
        try:
            value = self._settings.getSetting(DEFAULT_CONFIG_KEY, empty_relay_config())
        except Exception as error:
            raise RelayRpcError("config_read_failed") from error
        return decode_relay_config(value)

    async def _notify(self, config: dict[str, Any]) -> None:
        result = self._watcher.update_config(config)
        if inspect.isawaitable(result):
            await result

    def _persist(self, config: dict[str, Any]) -> None:
        try:
            self._settings.setSetting(DEFAULT_CONFIG_KEY, config)
            self._settings.commit()
        except Exception as error:
            raise RelayRpcError("config_persist_failed") from error

    async def get_relay_config(self) -> dict[str, Any]:
        return self._load()

    async def set_relay_game_config(self, data: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(data, Mapping):
            raise RelayRpcError("invalid_request")
        try:
            identity = validate_launch_identity(data.get("identity"))
        except ValueError as error:
            raise RelayRpcError("invalid_identity") from error
        if "config" not in data:
            raise RelayRpcError("invalid_request")
        config = self._load()
        games = dict(config["games"])
        game = data["config"]
        if game is None:
            games.pop(identity, None)
        else:
            validated = validate_game_config(game)
            if validated is None:
                raise RelayRpcError("invalid_config_entry")
            games[identity] = validated
        updated = {"schemaVersion": 1, "games": games}
        self._persist(updated)
        await self._notify(updated)
        return updated

    @staticmethod
    def _safe_status(identity: str, value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            return {"identity": identity, "state": "invalid_config", "diagnostic": {"code": "status_unavailable"}}
        state = value.get("state")
        if state not in _STATES:
            state = "invalid_config"
        diagnostic = value.get("diagnostic")
        if isinstance(diagnostic, Mapping):
            code = diagnostic.get("code")
            diagnostic = {"code": code} if isinstance(code, str) and _SAFE_CODE.fullmatch(code) else {"code": "status_unavailable"}
        else:
            diagnostic = None
        return {"identity": identity, "state": state, "diagnostic": diagnostic}

    async def _watcher_status(self, identity: str) -> dict[str, Any]:
        value = self._watcher.status(identity)
        if inspect.isawaitable(value):
            value = await value
        return self._safe_status(identity, value)

    async def get_relay_status(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identity = self._identity_from_request(data)
        return await self._watcher_status(identity)

    async def retry_relay(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identity = self._identity_from_request(data)
        value = self._watcher.retry(identity)
        if inspect.isawaitable(value):
            value = await value
        return self._safe_status(identity, value)

    @staticmethod
    def _identity_from_request(data: Mapping[str, Any]) -> str:
        if not isinstance(data, Mapping):
            raise RelayRpcError("invalid_request")
        try:
            return validate_launch_identity(data.get("identity"))
        except ValueError as error:
            raise RelayRpcError("invalid_identity") from error
