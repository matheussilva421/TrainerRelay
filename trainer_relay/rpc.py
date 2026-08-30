"""Typed, sanitised RPC adapter for the Decky backend."""

from __future__ import annotations

import inspect
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import DEFAULT_CONFIG_KEY, decode_relay_config, empty_relay_config, validate_game_config, validate_launch_identity
from .diagnostic_settings import DIAGNOSTIC_SETTINGS_KEY, decode_diagnostic_settings


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
    def __init__(
        self,
        settings: Any,
        watcher: Any,
        diagnostics: Any | None = None,
        *,
        downloads_dir: str | Path = "/home/deck/Downloads",
        plugin_version: str = "unknown",
    ) -> None:
        self._settings = settings
        self._watcher = watcher
        self._diagnostics = diagnostics
        self._downloads_dir = Path(downloads_dir)
        self._plugin_version = plugin_version

    def _load(self) -> dict[str, Any]:
        try:
            value = self._settings.getSetting(DEFAULT_CONFIG_KEY, empty_relay_config())
        except Exception as error:
            raise RelayRpcError("config_read_failed") from error
        config = decode_relay_config(value)
        self._record_diagnostic("config_loaded", "info", {"game_count": len(config["games"])})
        return config

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
        self._record_diagnostic("config_persisted", "info", {"game_count": len(config["games"])})

    def _record_diagnostic(self, event: str, outcome: str, details: Mapping[str, Any]) -> None:
        if self._diagnostics is None:
            return
        try:
            self._diagnostics.record("config", event, outcome, details=details)
        except (OSError, ValueError):
            return

    def _diagnostic_settings(self) -> dict[str, Any]:
        try:
            value = self._settings.getSetting(DIAGNOSTIC_SETTINGS_KEY, {"schemaVersion": 1, "enabled": False})
        except Exception as error:
            raise RelayRpcError("diagnostic_settings_read_failed") from error
        return decode_diagnostic_settings(value)

    def _persist_diagnostic_settings(self, value: dict[str, Any]) -> None:
        try:
            self._settings.setSetting(DIAGNOSTIC_SETTINGS_KEY, value)
            self._settings.commit()
        except Exception as error:
            raise RelayRpcError("diagnostic_settings_persist_failed") from error

    def _require_diagnostics(self) -> Any:
        if self._diagnostics is None:
            raise RelayRpcError("diagnostics_unavailable")
        return self._diagnostics

    def _diagnostic_response(self) -> dict[str, Any]:
        diagnostics = self._require_diagnostics()
        try:
            stats = diagnostics.stats()
        except Exception as error:
            raise RelayRpcError("diagnostics_unavailable") from error
        return {
            "settings": self._diagnostic_settings(),
            "bytesUsed": int(stats.get("bytesUsed", 0)),
            "byteLimit": int(stats.get("byteLimit", 52_428_800)),
            "eventCount": int(stats.get("eventCount", 0)),
            "storageDiagnostic": stats.get("storageDiagnostic")
            if isinstance(stats.get("storageDiagnostic"), str)
            else None,
            "lastExportPath": stats.get("lastExportPath") if isinstance(stats.get("lastExportPath"), str) else None,
        }

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

    async def get_diagnostic_settings(self) -> dict[str, Any]:
        return self._diagnostic_response()

    async def set_diagnostics_enabled(self, data: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(data, Mapping) or set(data) != {"enabled"} or type(data.get("enabled")) is not bool:
            raise RelayRpcError("invalid_request")
        enabled = data["enabled"]
        updated = {"schemaVersion": 1, "enabled": enabled}
        self._persist_diagnostic_settings(updated)
        diagnostics = self._require_diagnostics()
        try:
            if not enabled and getattr(diagnostics, "enabled", False):
                diagnostics.record(
                    "config",
                    "diagnostic_mode_changed",
                    "info",
                    details={"enabled": False},
                )
            diagnostics.set_enabled(enabled)
            if enabled:
                diagnostics.record(
                    "config",
                    "diagnostic_mode_changed",
                    "info",
                    details={"enabled": True},
                )
        except Exception as error:
            raise RelayRpcError("diagnostic_settings_apply_failed") from error
        return self._diagnostic_response()

    async def get_diagnostic_events(self, data: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(data, Mapping) or not set(data).issubset({"cursor", "limit"}):
            raise RelayRpcError("invalid_request")
        cursor = data.get("cursor")
        limit = data.get("limit", 20)
        if cursor is not None and not isinstance(cursor, str):
            raise RelayRpcError("invalid_request")
        if type(limit) is not int:
            raise RelayRpcError("invalid_request")
        try:
            return self._require_diagnostics().events_after(cursor, limit)
        except Exception as error:
            raise RelayRpcError("diagnostic_events_failed") from error

    async def export_diagnostics(self) -> dict[str, Any]:
        try:
            return self._require_diagnostics().export_text(self._downloads_dir, self._plugin_version)
        except Exception as error:
            raise RelayRpcError("diagnostic_export_failed") from error

    async def clear_diagnostics(self) -> dict[str, Any]:
        diagnostics = self._require_diagnostics()
        try:
            diagnostics.clear()
            generation = diagnostics.events_after(None, 1)["generation"]
        except Exception as error:
            raise RelayRpcError("diagnostic_clear_failed") from error
        return {**self._diagnostic_response(), "generation": generation}

    @staticmethod
    def _identity_from_request(data: Mapping[str, Any]) -> str:
        if not isinstance(data, Mapping):
            raise RelayRpcError("invalid_request")
        try:
            return validate_launch_identity(data.get("identity"))
        except ValueError as error:
            raise RelayRpcError("invalid_identity") from error
