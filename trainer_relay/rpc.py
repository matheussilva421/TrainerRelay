"""Typed, sanitised RPC adapter for the Decky backend."""

from __future__ import annotations

import asyncio
import inspect
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .cheat_config import validate_label, validate_trainer_sha256
from .cheat_service import PUBLIC_CHEAT_DIAGNOSTIC_CODES
from .config import DEFAULT_CONFIG_KEY, decode_relay_config, empty_relay_config, validate_game_config, validate_launch_identity
from .diagnostic_settings import DIAGNOSTIC_SETTINGS_KEY, decode_diagnostic_settings
from .hotkeys import normalize_hotkey
from .radial_registry import (
    RADIAL_LAYOUT_FIELDS,
    RADIAL_LAYOUT_REGISTRY_KEY,
    append_generated_radial_layout,
    decode_radial_layout_registry,
    empty_radial_layout_registry,
    next_radial_layout_revision,
    validate_generated_radial_layout,
    validate_radial_layout_registry,
)
from .steam_input_probe import export_steam_input_probe, validate_steam_input_probe


class RelayRpcError(ValueError):
    pass


_SAFE_CODE = re.compile(r"^[a-z0-9_]{1,64}$")
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
_CHEAT_STATUSES = {"unavailable", "waiting", "ready"}
_CHEAT_SOURCES = {"adapter", "manual", "cooperative"}
_CHEAT_STATES = {"unknown", "enabled", "disabled"}
_CHEAT_OPERATIONS = {"enable", "disable", "toggle"}
_CHEAT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_DIAGNOSTIC_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_HASH_PREFIX = re.compile(r"^[0-9a-f]{8,16}$")
_STEAM_INPUT_PROBE_EVENT_FIELDS = {
    "preview_created": frozenset(
        {
            "event",
            "appId",
            "identity",
            "commandCount",
            "pageCount",
            "skippedCount",
            "trainerHashPrefix",
            "catalogFingerprintPrefix",
            "runtimeFingerprintPrefix",
            "sourceLayoutIdHashPrefix",
            "resultCode",
            "correlationId",
        }
    ),
    "authority_changed": frozenset(
        {
            "event",
            "appId",
            "identity",
            "changedFieldCount",
            "trainerHashPrefix",
            "catalogFingerprintPrefix",
            "runtimeFingerprintPrefix",
            "sourceLayoutIdHashPrefix",
            "resultCode",
            "correlationId",
        }
    ),
    "configurator_opened": frozenset(
        {"event", "appId", "identity", "resultCode", "correlationId"}
    ),
}
_STEAM_INPUT_PROBE_EVENT_OUTCOMES = {
    "preview_created": "accepted",
    "authority_changed": "rejected",
    "configurator_opened": "accepted",
}
_STEAM_INPUT_PROBE_RESULT_CODES = {
    "preview_created": "readonly",
    "authority_changed": "authority_changed",
    "configurator_opened": "opened",
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
        cheat_service: Any | None = None,
    ) -> None:
        self._settings = settings
        self._watcher = watcher
        self._diagnostics = diagnostics
        self._downloads_dir = Path(downloads_dir)
        self._plugin_version = plugin_version
        self._cheat_service = cheat_service
        self._radial_registry_lock = asyncio.Lock()

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

    def _record_diagnostic(
        self,
        event: str,
        outcome: str,
        details: Mapping[str, Any],
        *,
        category: str = "config",
        identity: str | None = None,
    ) -> None:
        if self._diagnostics is None:
            return
        try:
            self._diagnostics.record(category, event, outcome, identity=identity, details=details)
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

    def _load_radial_layout_registry(self) -> dict[str, Any]:
        try:
            value = self._settings.getSetting(RADIAL_LAYOUT_REGISTRY_KEY, empty_radial_layout_registry())
        except (OSError, RuntimeError) as error:
            raise RelayRpcError("radial_registry_read_failed") from error
        return decode_radial_layout_registry(value)

    def _persist_radial_layout_registry(self, registry: dict[str, Any]) -> None:
        safe_registry = validate_radial_layout_registry(registry)
        try:
            self._settings.setSetting(RADIAL_LAYOUT_REGISTRY_KEY, safe_registry)
            self._settings.commit()
        except (OSError, RuntimeError) as error:
            raise RelayRpcError("radial_registry_persistence_failed") from error

    async def get_radial_layout_registry(self) -> dict[str, Any]:
        return self._load_radial_layout_registry()

    async def export_steam_input_probe(self, data: Mapping[str, Any]) -> dict[str, Any]:
        try:
            report = validate_steam_input_probe(data)
            result = export_steam_input_probe(report, self._downloads_dir)
        except ValueError as error:
            code = str(error)
            if code not in {"invalid_steam_input_probe", "steam_input_probe_too_large"}:
                code = "invalid_steam_input_probe"
            raise RelayRpcError(code) from None
        except OSError as error:
            raise RelayRpcError("steam_input_probe_export_failed") from error

        self._record_diagnostic(
            "probe_completed",
            "accepted",
            {
                "app_id": report["appId"],
                "primitive_key_count": len(report["responsePrimitiveKeys"]),
                "runtime_fingerprint_prefix": report["runtimeFingerprint"][:12],
                "result_code": "readonly",
                "correlation_id": str(uuid.uuid4()),
            },
            category="steam_input",
            identity=report["identity"],
        )
        return result

    async def record_steam_input_probe_event(self, data: Mapping[str, Any]) -> dict[str, bool]:
        if not isinstance(data, Mapping):
            raise RelayRpcError("invalid_steam_input_probe_event")
        event = data.get("event")
        fields = _STEAM_INPUT_PROBE_EVENT_FIELDS.get(event) if isinstance(event, str) else None
        if fields is None or set(data) != fields:
            raise RelayRpcError("invalid_steam_input_probe_event")
        app_id = data["appId"]
        if type(app_id) is not int or not 1 <= app_id <= 2**53 - 1:
            raise RelayRpcError("invalid_steam_input_probe_event")
        try:
            identity = validate_launch_identity(data["identity"])
        except (TypeError, ValueError):
            raise RelayRpcError("invalid_steam_input_probe_event") from None
        correlation_id = data["correlationId"]
        if not isinstance(correlation_id, str) or _DIAGNOSTIC_UUID.fullmatch(correlation_id) is None:
            raise RelayRpcError("invalid_steam_input_probe_event")
        if data["resultCode"] != _STEAM_INPUT_PROBE_RESULT_CODES[event]:
            raise RelayRpcError("invalid_steam_input_probe_event")

        details: dict[str, str | int] = {
            "app_id": app_id,
            "result_code": data["resultCode"],
            "correlation_id": correlation_id,
        }
        count_fields = {
            "commandCount": "command_count",
            "pageCount": "page_count",
            "skippedCount": "skipped_count",
            "changedFieldCount": "changed_field_count",
        }
        for wire_key, detail_key in count_fields.items():
            if wire_key not in data:
                continue
            value = data[wire_key]
            if type(value) is not int or not 0 <= value <= 64:
                raise RelayRpcError("invalid_steam_input_probe_event")
            details[detail_key] = value
        hash_fields = {
            "trainerHashPrefix": "trainer_hash_prefix",
            "catalogFingerprintPrefix": "catalog_fingerprint_prefix",
            "runtimeFingerprintPrefix": "runtime_fingerprint_prefix",
            "sourceLayoutIdHashPrefix": "source_layout_id_hash_prefix",
        }
        for wire_key, detail_key in hash_fields.items():
            if wire_key not in data:
                continue
            value = data[wire_key]
            if not isinstance(value, str) or _HASH_PREFIX.fullmatch(value) is None:
                raise RelayRpcError("invalid_steam_input_probe_event")
            details[detail_key] = value

        self._record_diagnostic(
            event,
            _STEAM_INPUT_PROBE_EVENT_OUTCOMES[event],
            details,
            category="steam_input",
            identity=identity,
        )
        return {"accepted": True}

    async def record_generated_radial_layout(self, data: Mapping[str, Any]) -> dict[str, Any]:
        request = self._strict_request(data, set(RADIAL_LAYOUT_FIELDS))
        try:
            layout = validate_generated_radial_layout(request)
        except ValueError:
            raise RelayRpcError("invalid_radial_layout") from None

        async with self._radial_registry_lock:
            registry = self._load_radial_layout_registry()
            try:
                expected_revision = next_radial_layout_revision(
                    registry,
                    layout["appId"],
                    layout["identity"],
                    layout["trainerSha256"],
                    layout["catalogFingerprint"],
                )
            except ValueError as error:
                code = str(error)
                if code == "radial_revision_exhausted":
                    raise RelayRpcError("radial_layout_revision_exhausted") from None
                raise RelayRpcError("invalid_radial_layout") from None
            if layout["revision"] != expected_revision:
                raise RelayRpcError("radial_layout_revision_conflict")

            try:
                updated = append_generated_radial_layout(registry, layout)
            except ValueError as error:
                code = str(error)
                if code == "radial_registry_capacity_exhausted":
                    raise RelayRpcError(code) from None
                raise RelayRpcError("invalid_radial_layout") from None
            self._persist_radial_layout_registry(updated)
            try:
                persisted = self._load_radial_layout_registry()
            except RelayRpcError as error:
                if str(error) == "radial_registry_read_failed":
                    raise RelayRpcError("radial_registry_persistence_failed") from None
                raise
            if layout not in persisted["layouts"]:
                raise RelayRpcError("radial_registry_persistence_failed")
            return persisted

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
    def _strict_request(data: Any, fields: set[str]) -> Mapping[str, Any]:
        if not isinstance(data, Mapping) or set(data) != fields:
            raise RelayRpcError("invalid_request")
        return data

    def _require_cheat_service(self) -> Any:
        if self._cheat_service is None:
            raise RelayRpcError("cheat_service_unavailable")
        return self._cheat_service

    @staticmethod
    def _safe_cheat_id(value: Any) -> str:
        if not isinstance(value, str) or _CHEAT_ID.fullmatch(value) is None:
            raise RelayRpcError("invalid_cheat_id")
        return value

    @staticmethod
    def _safe_cheat_diagnostic(value: Any) -> dict[str, str] | None:
        if value is None:
            return None
        if not isinstance(value, Mapping) or set(value) != {"code"}:
            raise RelayRpcError("invalid_cheat_response")
        code = value.get("code")
        if not isinstance(code, str) or code not in PUBLIC_CHEAT_DIAGNOSTIC_CODES:
            raise RelayRpcError("invalid_cheat_response")
        return {"code": code}

    @classmethod
    def _safe_cheat_descriptor(cls, value: Any, *, source: str | None = None) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise RelayRpcError("invalid_cheat_response")
        allowed = {"id", "label", "hotkey", "state", "hotkeys", "operations", "authoritative"}
        if set(value) - allowed or not {"id", "label"}.issubset(value) or source != "cooperative" and "hotkey" not in value:
            raise RelayRpcError("invalid_cheat_response")
        cheat_id = cls._safe_cheat_id(value.get("id"))
        try:
            label = validate_label(value.get("label"))
        except ValueError:
            raise RelayRpcError("invalid_cheat_response") from None
        hotkey = None
        if "hotkey" in value:
            try:
                hotkey = normalize_hotkey(value.get("hotkey"))
            except ValueError:
                raise RelayRpcError("invalid_cheat_response") from None
        state = value.get("state", "unknown")
        if state not in _CHEAT_STATES:
            raise RelayRpcError("invalid_cheat_response")
        authoritative = value.get("authoritative", False)
        if (
            type(authoritative) is not bool
            or source != "cooperative"
            and authoritative
            or state in {"enabled", "disabled"}
            and (source != "cooperative" or value.get("authoritative") is not True)
        ):
            raise RelayRpcError("invalid_cheat_response")
        result: dict[str, Any] = {
            "id": cheat_id,
            "label": label,
            "state": state,
        }
        if hotkey is not None:
            result["hotkey"] = hotkey
        if "hotkeys" in value:
            raw_hotkeys = value["hotkeys"]
            if type(raw_hotkeys) is not list or not 1 <= len(raw_hotkeys) <= 8:
                raise RelayRpcError("invalid_cheat_response")
            try:
                result["hotkeys"] = [normalize_hotkey(raw) for raw in raw_hotkeys]
            except ValueError:
                raise RelayRpcError("invalid_cheat_response") from None
        if "operations" in value:
            operations = value["operations"]
            if type(operations) is not list or not operations or any(
                not isinstance(operation, str) or operation not in _CHEAT_OPERATIONS for operation in operations
            ) or len(set(operations)) != len(operations):
                raise RelayRpcError("invalid_cheat_response")
            result["operations"] = list(operations)
        if "authoritative" in value:
            result["authoritative"] = authoritative
        return result

    @classmethod
    def _safe_cheat_controls(cls, identity: str, value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise RelayRpcError("invalid_cheat_response")
        status = value.get("status")
        if status not in _CHEAT_STATUSES or value.get("identity") != identity:
            raise RelayRpcError("invalid_cheat_response")
        if status != "ready":
            if set(value) != {"identity", "status", "diagnostic"}:
                raise RelayRpcError("invalid_cheat_response")
            return {
                "identity": identity,
                "status": status,
                "diagnostic": cls._safe_cheat_diagnostic(value.get("diagnostic")),
            }
        expected = {
            "identity",
            "status",
            "trainerSha256",
            "source",
            "trainerLabel",
            "cheats",
            "capabilities",
            "diagnostic",
        }
        if set(value) != expected or value.get("source") not in _CHEAT_SOURCES:
            raise RelayRpcError("invalid_cheat_response")
        try:
            trainer_sha256 = validate_trainer_sha256(value.get("trainerSha256"))
            trainer_label = validate_label(value.get("trainerLabel"))
        except ValueError:
            raise RelayRpcError("invalid_cheat_response") from None
        cheats = value.get("cheats")
        if type(cheats) is not list or len(cheats) > 64 or not cheats and value["source"] != "manual":
            raise RelayRpcError("invalid_cheat_response")
        safe_cheats = [cls._safe_cheat_descriptor(cheat, source=value["source"]) for cheat in cheats]
        if len({cheat["id"] for cheat in safe_cheats}) != len(safe_cheats):
            raise RelayRpcError("invalid_cheat_response")
        capabilities = value.get("capabilities")
        if not isinstance(capabilities, Mapping) or set(capabilities) != {"commands", "authoritativeState", "toggles"} or any(
            type(capabilities[key]) is not bool for key in capabilities
        ):
            raise RelayRpcError("invalid_cheat_response")
        if value["source"] != "cooperative" and (capabilities["authoritativeState"] or capabilities["toggles"]):
            raise RelayRpcError("invalid_cheat_response")
        if capabilities["toggles"] and not capabilities["authoritativeState"]:
            raise RelayRpcError("invalid_cheat_response")
        if not safe_cheats and capabilities["commands"]:
            raise RelayRpcError("invalid_cheat_response")
        if value["source"] != "cooperative" and any(cheat.get("authoritative") is True for cheat in safe_cheats):
            raise RelayRpcError("invalid_cheat_response")
        if value["source"] == "cooperative" and not capabilities["authoritativeState"]:
            if any(cheat["state"] in {"enabled", "disabled"} for cheat in safe_cheats):
                raise RelayRpcError("invalid_cheat_response")
        return {
            "identity": identity,
            "status": "ready",
            "trainerSha256": trainer_sha256,
            "source": value["source"],
            "trainerLabel": trainer_label,
            "cheats": safe_cheats,
            "capabilities": dict(capabilities),
            "diagnostic": cls._safe_cheat_diagnostic(value.get("diagnostic")),
        }

    @classmethod
    def _safe_manual_mutation(cls, identity: str, value: Any, *, add: bool) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise RelayRpcError("invalid_cheat_response")
        if add:
            if set(value) != {"identity", "trainerSha256", "cheat"} or value.get("identity") != identity:
                raise RelayRpcError("invalid_cheat_response")
            try:
                trainer_sha256 = validate_trainer_sha256(value.get("trainerSha256"))
            except ValueError:
                raise RelayRpcError("invalid_cheat_response") from None
            cheat = cls._safe_cheat_descriptor(value.get("cheat"), source="manual")
            if cheat["state"] != "unknown":
                raise RelayRpcError("invalid_cheat_response")
            return {"identity": identity, "trainerSha256": trainer_sha256, "cheat": cheat}
        if set(value) != {"identity", "cheatId", "removed"} or value.get("identity") != identity or type(value.get("removed")) is not bool:
            raise RelayRpcError("invalid_cheat_response")
        return {"identity": identity, "cheatId": cls._safe_cheat_id(value.get("cheatId")), "removed": value["removed"]}

    @classmethod
    def _safe_command_result(cls, identity: str, cheat_id: str, value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping) or set(value) != {"commandId", "identity", "cheatId", "outcome", "state", "diagnostic"}:
            raise RelayRpcError("invalid_cheat_response")
        command_id = value.get("commandId")
        if not isinstance(command_id, str) or _UUID.fullmatch(command_id) is None:
            raise RelayRpcError("invalid_cheat_response")
        try:
            uuid.UUID(command_id)
        except (AttributeError, ValueError):
            raise RelayRpcError("invalid_cheat_response") from None
        if value.get("identity") != identity or value.get("cheatId") != cheat_id:
            raise RelayRpcError("invalid_cheat_response")
        outcome = value.get("outcome")
        state = value.get("state")
        if outcome not in {"requested", "failed", "rejected"} or state not in _CHEAT_STATES:
            raise RelayRpcError("invalid_cheat_response")
        if outcome != "requested" and state != "unknown":
            raise RelayRpcError("invalid_cheat_response")
        diagnostic = cls._safe_cheat_diagnostic(value.get("diagnostic"))
        if outcome != "requested" and diagnostic is None:
            raise RelayRpcError("invalid_cheat_response")
        return {
            "commandId": command_id,
            "identity": identity,
            "cheatId": cheat_id,
            "outcome": outcome,
            "state": state,
            "diagnostic": diagnostic,
        }

    async def _cheat_call(self, method: str, *args: Any) -> Any:
        service = self._require_cheat_service()
        function = getattr(service, method, None)
        if function is None:
            raise RelayRpcError("cheat_service_unavailable")
        try:
            value = function(*args)
            if inspect.isawaitable(value):
                value = await value
            return value
        except RelayRpcError:
            raise
        except Exception as error:
            code = getattr(error, "code", None)
            if not isinstance(code, str) or code not in PUBLIC_CHEAT_DIAGNOSTIC_CODES:
                code = "cheat_service_failed"
            raise RelayRpcError(code) from None

    async def get_cheat_controls(self, data: Mapping[str, Any]) -> dict[str, Any]:
        request = self._strict_request(data, {"identity"})
        identity = self._identity_from_request(request)
        return self._safe_cheat_controls(identity, await self._cheat_call("get_cheat_controls", identity))

    async def add_manual_cheat_control(self, data: Mapping[str, Any]) -> dict[str, Any]:
        request = self._strict_request(data, {"identity", "trainerSha256", "label", "hotkey"})
        identity = self._identity_from_request({"identity": request["identity"]})
        try:
            normalized = {
                "identity": identity,
                "trainerSha256": validate_trainer_sha256(request["trainerSha256"]),
                "label": validate_label(request["label"]),
                "hotkey": normalize_hotkey(request["hotkey"]),
            }
        except ValueError as error:
            code = str(error)
            raise RelayRpcError(code if code in PUBLIC_CHEAT_DIAGNOSTIC_CODES else "invalid_manual_cheat") from None
        return self._safe_manual_mutation(
            identity,
            await self._cheat_call("add_manual_cheat_control", normalized),
            add=True,
        )

    async def remove_manual_cheat_control(self, data: Mapping[str, Any]) -> dict[str, Any]:
        request = self._strict_request(data, {"identity", "cheatId"})
        identity = self._identity_from_request({"identity": request["identity"]})
        normalized = {"identity": identity, "cheatId": self._safe_cheat_id(request["cheatId"])}
        return self._safe_manual_mutation(
            identity,
            await self._cheat_call("remove_manual_cheat_control", normalized),
            add=False,
        )

    async def send_cheat_command(self, data: Mapping[str, Any]) -> dict[str, Any]:
        request = self._strict_request(data, {"identity", "cheatId"})
        identity = self._identity_from_request({"identity": request["identity"]})
        cheat_id = self._safe_cheat_id(request["cheatId"])
        return self._safe_command_result(
            identity,
            cheat_id,
            await self._cheat_call("send_cheat_command", {"identity": identity, "cheatId": cheat_id}),
        )

    @staticmethod
    def _identity_from_request(data: Mapping[str, Any]) -> str:
        if not isinstance(data, Mapping):
            raise RelayRpcError("invalid_request")
        try:
            return validate_launch_identity(data.get("identity"))
        except ValueError as error:
            raise RelayRpcError("invalid_identity") from error
