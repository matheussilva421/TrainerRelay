"""Fail-closed cheat-control resolution and one-shot command dispatch."""

from __future__ import annotations

import asyncio
import inspect
import re
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .cheat_catalog import AdapterDescriptor, CheatCatalog, load_packaged_catalog
from .cheat_config import (
    DEFAULT_CONFIG_KEY,
    decode_cheat_controls_config,
    empty_cheat_controls_config,
    new_manual_cheat_control,
    validate_cheat_controls_config,
    validate_trainer_sha256,
)
from .cooperative import CooperativeAck, CooperativeDescriptor, decode_cooperative_ack, decode_cooperative_descriptor
from .config import validate_launch_identity
from .hotkeys import hotkey_to_vk
from .types import CommandContext


CHEAT_STATUS_UNAVAILABLE = "unavailable"
CHEAT_STATUS_WAITING = "waiting"
CHEAT_STATUS_READY = "ready"
CHEAT_CONFIG_SCHEMA_VERSION = 1
_SAFE_CODE = re.compile(r"^[a-z0-9_]{1,64}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_RUNNER_CODES = {
    "command_busy",
    "invalid_command_context",
    "invalid_virtual_key",
    "invalid_modifier_mask",
    "invalid_hold_ms",
    "helper_missing",
    "helper_manifest_invalid",
    "helper_manifest_entry_missing",
    "helper_path_mismatch",
    "helper_manifest_path_mismatch",
    "helper_architecture_unknown",
    "helper_hash_mismatch",
    "helper_architecture_mismatch",
    "helper_spawn_failed",
    "helper_exit_nonzero",
    "helper_output_oversized",
    "helper_output_malformed",
    "helper_input_count_mismatch",
    "helper_result_nonzero",
    "container_reentry_marker_missing",
    "command_timeout",
    "command_timeout_cleanup_failed",
    "helper_output_cleanup_failed",
    "command_context_changed",
    "command_context_revalidation_failed",
    "command_cancelled",
    "command_cancel_cleanup_failed",
}
_CONTEXT_CODES = {
    "invalid_config_identity",
    "relay_not_running",
    "session_ended",
    "trainer_not_owned",
    "games_map_unreadable",
    "games_map_identity_missing",
    "multiple_game_sessions",
    "session_recycled",
    "prefix_mismatch",
    "trainer_hash_unavailable",
    "trainer_hash_changed",
    "trainer_architecture_unknown",
    "command_context_unavailable",
    "container_reentry_bus_missing",
}
_PUBLIC_CODES = frozenset(
    {
        "invalid_identity",
        "invalid_cheat_id",
        "invalid_request",
        "relay_not_running",
        "unknown_trainer_hash",
        "cheat_unavailable",
        "cheat_not_found",
        "too_many_manual_cheats",
        "invalid_manual_cheat",
        "trainer_hash_changed",
        "cheat_config_read_failed",
        "cheat_config_invalid",
        "cheat_config_persist_failed",
        "helper_unavailable",
        "invalid_hotkey",
        "cooperative_unavailable",
        "cooperative_ack_stale",
        "cooperative_command_rejected",
        "command_runner_failed",
        "command_busy",
        "command_context_changed",
        "command_context_revalidation_failed",
        "command_cancelled",
        "command_cancel_cleanup_failed",
        "service_closing",
        "cheat_service_failed",
        "trainer_architecture_mismatch",
        "status_unavailable",
        *_RUNNER_CODES,
        *_CONTEXT_CODES,
    }
)
PUBLIC_CHEAT_DIAGNOSTIC_CODES = _PUBLIC_CODES


class CheatServiceError(ValueError):
    """A bounded error safe to return through the Decky RPC boundary."""

    def __init__(self, code: str) -> None:
        self.code = code if isinstance(code, str) and code in _PUBLIC_CODES else "cheat_service_failed"
        super().__init__(self.code)


@dataclass(frozen=True)
class _ResolvedControl:
    source: str
    trainer_sha256: str
    trainer_label: str
    trainer_arch: str
    cheats: tuple[Mapping[str, Any], ...]
    by_id: Mapping[str, Mapping[str, Any]]
    cooperative: CooperativeDescriptor | None = None


def _safe_identity(value: Any) -> str:
    try:
        return validate_launch_identity(value)
    except ValueError:
        raise CheatServiceError("invalid_identity") from None


def _safe_cheat_id(value: Any) -> str:
    if not isinstance(value, str) or (_IDENTIFIER.fullmatch(value) is None and _UUID.fullmatch(value) is None):
        raise CheatServiceError("invalid_cheat_id")
    return value


def _safe_runner_code(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value in _RUNNER_CODES else default


def _safe_context_code(error: BaseException) -> str:
    code = getattr(error, "code", None)
    if isinstance(code, str) and code in _CONTEXT_CODES:
        return code
    return "command_context_unavailable"


def _safe_public_code(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value in _PUBLIC_CODES else default


def _mapping_result(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _session_for_diagnostics(context: Any) -> Any | None:
    session = getattr(context, "session", None)
    if session is None or not isinstance(getattr(session, "pid", None), int) or not isinstance(getattr(session, "start_time", None), int):
        return None
    try:
        from .diagnostics import DiagnosticSession

        return DiagnosticSession(session.pid, session.start_time)
    except (ImportError, TypeError, ValueError):
        return None


class CheatControlService:
    def __init__(
        self,
        settings: Any,
        watcher: Any,
        runner: Any,
        *,
        catalog: CheatCatalog | Any | None = None,
        helper_paths: Mapping[str, str | Path] | None = None,
        diagnostics: Any | None = None,
        cooperative: Any | None = None,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._watcher = watcher
        self._runner = runner
        self._catalog = catalog
        self._helper_paths = dict(helper_paths or {})
        self._diagnostics = diagnostics
        self._cooperative = cooperative
        self._uuid_factory = uuid_factory
        self._clock = clock
        self._identity_locks: dict[str, asyncio.Lock] = {}
        self._identity_locks_guard = asyncio.Lock()
        self._catalog_lock = asyncio.Lock()
        self._revision_state: dict[str, tuple[str, tuple[int, int], int]] = {}
        self._dispatch_tasks: set[asyncio.Task[Any]] = set()
        self._dispatch_guard = asyncio.Lock()
        self._close_lock = asyncio.Lock()
        self._closing = False

    async def _thread_call(self, function: Callable[..., Any], *args: Any) -> Any:
        value = await asyncio.to_thread(function, *args)
        if inspect.isawaitable(value):
            return await value
        return value

    async def _record(
        self,
        event: str,
        outcome: str,
        *,
        identity: str | None = None,
        context: CommandContext | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        if self._diagnostics is None:
            return
        try:
            awaitable = await asyncio.to_thread(
                self._diagnostics.record,
                "command",
                event,
                outcome,
                identity=identity,
                session=_session_for_diagnostics(context),
                details=details or {},
            )
            if inspect.isawaitable(awaitable):
                await awaitable
        except (OSError, ValueError, TypeError):
            return

    def _load_sync(self) -> dict[str, Any]:
        try:
            value = self._settings.getSetting(DEFAULT_CONFIG_KEY, empty_cheat_controls_config())
        except Exception:
            raise CheatServiceError("cheat_config_read_failed") from None
        return decode_cheat_controls_config(value)

    async def _load(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._load_sync)

    def _persist_sync(self, config: Mapping[str, Any]) -> None:
        try:
            validated = validate_cheat_controls_config(config)
            self._settings.setSetting(DEFAULT_CONFIG_KEY, validated)
            self._settings.commit()
        except CheatServiceError:
            raise
        except ValueError:
            raise CheatServiceError("cheat_config_invalid") from None
        except Exception:
            raise CheatServiceError("cheat_config_persist_failed") from None

    async def _persist(self, config: Mapping[str, Any]) -> None:
        await asyncio.to_thread(self._persist_sync, config)

    async def _identity_lock(self, identity: str) -> asyncio.Lock:
        async with self._identity_locks_guard:
            return self._identity_locks.setdefault(identity, asyncio.Lock())

    @staticmethod
    def _session_key(value: Any) -> tuple[int, int]:
        if isinstance(value, Mapping):
            pid, start_time = value.get("pid"), value.get("startTime")
        else:
            pid, start_time = getattr(value, "pid", None), getattr(value, "start_time", None)
            if pid is None and isinstance(value, (tuple, list)) and len(value) == 2:
                pid, start_time = value
        if type(pid) is not int or type(start_time) is not int:
            raise ValueError("cooperative_session_invalid")
        return pid, start_time

    def _previous_revision(self, context: CommandContext) -> int | None:
        binding = (context.trainer_sha256, self._session_key(context.session))
        previous = self._revision_state.get(context.identity)
        if previous is None or previous[:2] != binding:
            self._revision_state.pop(context.identity, None)
            return None
        return previous[2]

    def _remember_revision(self, context: CommandContext, revision: int) -> None:
        binding = (context.trainer_sha256, self._session_key(context.session))
        previous = self._revision_state.get(context.identity)
        if previous is not None and previous[:2] == binding and revision < previous[2]:
            raise ValueError("cooperative_revision_invalid")
        self._revision_state[context.identity] = (*binding, revision)

    async def _status(self, identity: str) -> Mapping[str, Any]:
        try:
            value = await self._thread_call(self._watcher.status, identity)
        except Exception:
            return {"identity": identity, "state": "invalid_config", "diagnostic": {"code": "status_unavailable"}}
        result = _mapping_result(value)
        if result is None:
            return {"identity": identity, "state": "invalid_config", "diagnostic": {"code": "status_unavailable"}}
        state = result.get("state")
        diagnostic = result.get("diagnostic")
        code = diagnostic.get("code") if isinstance(diagnostic, Mapping) else None
        safe_diagnostic = {"code": code} if isinstance(code, str) and _SAFE_CODE.fullmatch(code) else None
        return {"identity": identity, "state": state, "diagnostic": safe_diagnostic}

    async def _context(self, identity: str) -> CommandContext:
        try:
            context = await self._thread_call(self._watcher.command_context, identity)
        except Exception as error:
            raise CheatServiceError(_safe_context_code(error)) from None
        if not isinstance(context, CommandContext):
            raise CheatServiceError("command_context_unavailable")
        if context.identity != identity:
            raise CheatServiceError("command_context_unavailable")
        return context

    async def _catalog_or_none(self) -> CheatCatalog | Any | None:
        if self._catalog is not None:
            return self._catalog
        async with self._catalog_lock:
            if self._catalog is not None:
                return self._catalog
            try:
                self._catalog = await asyncio.to_thread(load_packaged_catalog)
                adapter_count = getattr(self._catalog, "adapters", ())
                await self._record(
                    "catalog_loaded",
                    "accepted",
                    details={"adapter_count": len(adapter_count) if hasattr(adapter_count, "__len__") else 0},
                )
            except Exception:
                await self._record("catalog_rejected", "rejected", details={"reason": "invalid_cheat_catalog"})
                self._catalog = False
        return self._catalog if self._catalog is not False else None

    def _manual_controls(self, config: Mapping[str, Any], identity: str, trainer_sha256: str) -> tuple[Mapping[str, Any], ...]:
        game = config.get("games", {}).get(identity) if isinstance(config.get("games"), Mapping) else None
        if not isinstance(game, Mapping) or game.get("trainerSha256") != trainer_sha256:
            return ()
        cheats = game.get("cheats")
        return tuple(cheat for cheat in cheats if isinstance(cheat, Mapping)) if isinstance(cheats, list) else ()

    async def _cooperative_descriptor(self, context: CommandContext) -> CooperativeDescriptor | None:
        provider = self._cooperative
        if provider is None:
            return None
        try:
            getter = getattr(provider, "descriptor_for", None) or getattr(provider, "get_descriptor", None)
            raw = await self._thread_call(getter, context) if getter is not None else await self._thread_call(provider, context)
            if raw is None:
                return None
            if isinstance(raw, CooperativeDescriptor):
                raw = raw.to_wire()
            decoded = decode_cooperative_descriptor(
                raw,
                expected_identity=context.identity,
                expected_trainer_sha256=context.trainer_sha256,
                expected_session=context.session,
                previous_revision=self._previous_revision(context),
            )
            self._remember_revision(context, decoded.revision)
            return decoded
        except Exception:
            await self._record(
                "cooperative_descriptor_rejected",
                "rejected",
                identity=context.identity,
                context=context,
                details={"reason": "cooperative_descriptor_invalid"},
            )
            return None

    @staticmethod
    def _adapter_controls(adapter: AdapterDescriptor) -> tuple[Mapping[str, Any], ...]:
        controls: list[Mapping[str, Any]] = []
        for cheat in adapter.cheats:
            value: dict[str, Any] = {
                "id": cheat.id,
                "label": cheat.label,
                "hotkey": {"modifiers": list(cheat.hotkey["modifiers"]), "key": cheat.hotkey["key"]},
                "state": "unknown",
            }
            if len(cheat.hotkeys) > 1:
                value["hotkeys"] = [
                    {"modifiers": list(hotkey["modifiers"]), "key": hotkey["key"]} for hotkey in cheat.hotkeys
                ]
            controls.append(value)
        return tuple(controls)

    @staticmethod
    def _cooperative_controls(descriptor: CooperativeDescriptor) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            {
                **cheat.to_wire(),
                "state": "unknown",
                "authoritative": False,
            }
            for cheat in descriptor.cheats
        )

    async def _resolve(
        self,
        context: CommandContext,
        *,
        config: Mapping[str, Any] | None = None,
        allow_cooperative: bool = True,
    ) -> _ResolvedControl | None:
        config = await self._load() if config is None else config
        cooperative = await self._cooperative_descriptor(context) if allow_cooperative else None
        if cooperative is not None:
            controls = self._cooperative_controls(cooperative)
            return _ResolvedControl(
                "cooperative",
                context.trainer_sha256,
                cooperative.trainer_label or "Cooperative trainer",
                context.trainer_arch,
                controls,
                {str(value["id"]): value for value in controls},
                cooperative,
            )
        adapter = None
        catalog = await self._catalog_or_none()
        if catalog is not None:
            try:
                adapter = catalog.resolve(context.trainer_sha256, context.identity)
            except Exception:
                adapter = None
        if adapter is not None and adapter.pe_architecture != context.trainer_arch:
            raise CheatServiceError("trainer_architecture_mismatch")
        if adapter is not None:
            controls = self._adapter_controls(adapter)
            return _ResolvedControl(
                "adapter",
                context.trainer_sha256,
                adapter.trainer_label,
                adapter.pe_architecture,
                controls,
                {str(value["id"]): value for value in controls},
            )
        controls = self._manual_controls(config, context.identity, context.trainer_sha256)
        if controls:
            safe_controls = tuple(
                {
                    "id": str(value["id"]),
                    "label": str(value["label"]),
                    "hotkey": {"modifiers": list(value["hotkey"]["modifiers"]), "key": value["hotkey"]["key"]},
                    "state": "unknown",
                }
                for value in controls
            )
            return _ResolvedControl(
                "manual",
                context.trainer_sha256,
                "Manual controls",
                context.trainer_arch,
                safe_controls,
                {str(value["id"]): value for value in safe_controls},
            )
        return None

    @staticmethod
    def _ready_response(identity: str, resolved: _ResolvedControl) -> dict[str, Any]:
        authoritative = any(value.get("authoritative") is True for value in resolved.cheats)
        return {
            "identity": identity,
            "status": CHEAT_STATUS_READY,
            "trainerSha256": resolved.trainer_sha256,
            "source": resolved.source,
            "trainerLabel": resolved.trainer_label,
            "cheats": [dict(value) for value in resolved.cheats],
            "capabilities": {
                "commands": True,
                "authoritativeState": authoritative,
                "toggles": authoritative,
            },
            "diagnostic": None,
        }

    @staticmethod
    def _not_ready(identity: str, status: str, code: str) -> dict[str, Any]:
        return {"identity": identity, "status": status, "diagnostic": {"code": code}}

    async def get_cheat_controls(self, identity: str) -> dict[str, Any]:
        identity = _safe_identity(identity)
        status = await self._status(identity)
        if status.get("state") != "running":
            diagnostic = status.get("diagnostic")
            code = diagnostic.get("code") if isinstance(diagnostic, Mapping) else None
            code = _safe_public_code(code, "relay_not_running")
            transient = status.get("state") in {"waiting_for_game", "launching", "retrying"}
            return self._not_ready(identity, CHEAT_STATUS_WAITING if transient else CHEAT_STATUS_UNAVAILABLE, code)
        lock = await self._identity_lock(identity)
        async with lock:
            try:
                context = await self._context(identity)
                resolved = await self._resolve(context)
            except CheatServiceError as error:
                return self._not_ready(identity, CHEAT_STATUS_UNAVAILABLE, error.code)
            if resolved is None:
                return self._not_ready(identity, CHEAT_STATUS_UNAVAILABLE, "unknown_trainer_hash")
            return self._ready_response(identity, resolved)

    @staticmethod
    def _request_values(identity_or_request: Any, trainer_sha256: Any, label: Any, hotkey: Any) -> tuple[str, Any, Any, Any]:
        if isinstance(identity_or_request, Mapping):
            request = identity_or_request
            if set(request) != {"identity", "trainerSha256", "label", "hotkey"}:
                raise CheatServiceError("invalid_request")
            return request["identity"], request["trainerSha256"], request["label"], request["hotkey"]
        return identity_or_request, trainer_sha256, label, hotkey

    async def add_manual_cheat_control(
        self,
        identity_or_request: Any,
        trainer_sha256: Any = None,
        label: Any = None,
        hotkey: Any = None,
    ) -> dict[str, Any]:
        raw_identity, raw_hash, raw_label, raw_hotkey = self._request_values(identity_or_request, trainer_sha256, label, hotkey)
        identity = _safe_identity(raw_identity)
        try:
            trainer_sha256 = validate_trainer_sha256(raw_hash)
            control = new_manual_cheat_control(raw_label, raw_hotkey)
        except ValueError as error:
            raise CheatServiceError(str(error) if _SAFE_CODE.fullmatch(str(error)) else "invalid_manual_cheat") from None
        lock = await self._identity_lock(identity)
        async with lock:
            current_context = await self._context(identity)
            if current_context.trainer_sha256 != trainer_sha256:
                raise CheatServiceError("trainer_hash_changed")
            config = await self._load()
            games = dict(config["games"])
            game = dict(games.get(identity, {"trainerSha256": trainer_sha256, "cheats": []}))
            if game.get("trainerSha256") != trainer_sha256:
                game = {"trainerSha256": trainer_sha256, "cheats": []}
            cheats = list(game.get("cheats", []))
            if len(cheats) >= 64:
                raise CheatServiceError("too_many_manual_cheats")
            cheats.append(control)
            games[identity] = {"trainerSha256": trainer_sha256, "cheats": cheats}
            await self._persist({"schemaVersion": CHEAT_CONFIG_SCHEMA_VERSION, "games": games})
        await self._record("manual_control_added", "accepted", identity=identity, details={"cheat_id": control["id"], "control_count": len(cheats)})
        return {"identity": identity, "trainerSha256": trainer_sha256, "cheat": control}

    async def remove_manual_cheat_control(self, identity_or_request: Any, cheat_id: Any = None) -> dict[str, Any]:
        if isinstance(identity_or_request, Mapping):
            request = identity_or_request
            if set(request) != {"identity", "cheatId"}:
                raise CheatServiceError("invalid_request")
            raw_identity, cheat_id = request["identity"], request["cheatId"]
        else:
            raw_identity = identity_or_request
        identity = _safe_identity(raw_identity)
        cheat_id = _safe_cheat_id(cheat_id)
        lock = await self._identity_lock(identity)
        async with lock:
            config = await self._load()
            games = dict(config["games"])
            game = games.get(identity)
            if not isinstance(game, Mapping):
                raise CheatServiceError("cheat_not_found")
            cheats = [value for value in game.get("cheats", []) if isinstance(value, Mapping) and value.get("id") != cheat_id]
            if len(cheats) == len(game.get("cheats", [])):
                raise CheatServiceError("cheat_not_found")
            games[identity] = {"trainerSha256": game["trainerSha256"], "cheats": cheats}
            await self._persist({"schemaVersion": CHEAT_CONFIG_SCHEMA_VERSION, "games": games})
        await self._record("manual_control_removed", "accepted", identity=identity, details={"cheat_id": cheat_id, "control_count": len(cheats)})
        return {"identity": identity, "cheatId": cheat_id, "removed": True}

    @staticmethod
    def _same_context(left: CommandContext, right: Any) -> bool:
        if not isinstance(right, CommandContext):
            return False
        try:
            left_session = CheatControlService._session_key(left.session)
            right_session = CheatControlService._session_key(right.session)
        except ValueError:
            return False
        return (
            left.identity == right.identity
            and left_session == right_session
            and left.trainer_sha256 == right.trainer_sha256
            and left.trainer_arch == right.trainer_arch
            and dict(left.environment) == dict(right.environment)
            and left.umu_run == right.umu_run
            and left.expected_reentry_bus == right.expected_reentry_bus
        )

    @staticmethod
    def _command_result(
        command_id: str,
        identity: str,
        cheat_id: str,
        outcome: str,
        diagnostic: str | None = None,
        state: str = "unknown",
    ) -> dict[str, Any]:
        return {
            "commandId": command_id,
            "identity": identity,
            "cheatId": cheat_id,
            "outcome": outcome,
            "state": state,
            "diagnostic": {"code": diagnostic} if diagnostic is not None else None,
        }

    async def _register_dispatch(self) -> asyncio.Task[Any] | None:
        task = asyncio.current_task()
        async with self._dispatch_guard:
            if self._closing:
                return None
            if task is not None:
                self._dispatch_tasks.add(task)
        return task

    async def _unregister_dispatch(self, task: asyncio.Task[Any] | None) -> None:
        if task is None:
            return
        async with self._dispatch_guard:
            self._dispatch_tasks.discard(task)

    async def close(self) -> None:
        async with self._close_lock:
            async with self._dispatch_guard:
                self._closing = True
                current = asyncio.current_task()
                dispatches = tuple(task for task in self._dispatch_tasks if task is not current)
            cancel_all = getattr(self._runner, "cancel_all", None)
            if callable(cancel_all):
                try:
                    await asyncio.to_thread(cancel_all)
                except Exception:
                    pass
            if dispatches:
                await asyncio.gather(*dispatches, return_exceptions=True)

    def _cooperative_send_sync(
        self,
        identity: str,
        context: CommandContext,
        descriptor: CooperativeDescriptor,
        command_id: str,
        cheat: Mapping[str, Any],
        operation: str,
        previous_revision: int | None,
    ) -> CooperativeAck | None:
        provider = self._cooperative
        sender = getattr(provider, "send_command", None) if provider is not None else None
        if sender is None:
            return None
        lease_factory = getattr(self._watcher, "command_context_lease", None)
        if not callable(lease_factory):
            raise CheatServiceError("command_context_unavailable")
        with lease_factory(identity) as refreshed_context:
            if not self._same_context(context, refreshed_context):
                raise CheatServiceError("command_context_changed")
            if (
                descriptor.identity != refreshed_context.identity
                or descriptor.trainer_sha256 != refreshed_context.trainer_sha256
                or self._session_key(descriptor.session) != self._session_key(refreshed_context.session)
            ):
                raise CheatServiceError("command_context_changed")
            raw = sender(descriptor, command_id, cheat["id"], operation)
            if inspect.isawaitable(raw):
                if inspect.iscoroutine(raw):
                    raw.close()
                raise ValueError("cooperative_transport_invalid")
            if isinstance(raw, CooperativeAck):
                raw = raw.to_wire()
            return decode_cooperative_ack(
                raw,
                descriptor=descriptor,
                expected_command_id=command_id,
                now=self._clock(),
                previous_revision=previous_revision,
            )

    async def _cooperative_send(
        self,
        identity: str,
        context: CommandContext,
        descriptor: CooperativeDescriptor,
        command_id: str,
        cheat: Mapping[str, Any],
        operation: str,
        previous_revision: int | None,
    ) -> CooperativeAck | None:
        return await asyncio.to_thread(
            self._cooperative_send_sync,
            identity,
            context,
            descriptor,
            command_id,
            cheat,
            operation,
            previous_revision,
        )

    async def send_cheat_command(self, identity_or_request: Any, cheat_id: Any = None) -> dict[str, Any]:
        if isinstance(identity_or_request, Mapping):
            request = identity_or_request
            if set(request) != {"identity", "cheatId"}:
                raise CheatServiceError("invalid_request")
            raw_identity, cheat_id = request["identity"], request["cheatId"]
        else:
            raw_identity = identity_or_request
        identity = _safe_identity(raw_identity)
        cheat_id = _safe_cheat_id(cheat_id)
        command_id = str(self._uuid_factory()).lower()
        dispatch = await self._register_dispatch()
        if dispatch is None:
            return self._command_result(command_id, identity, cheat_id, "rejected", "service_closing")
        try:
            lock = await self._identity_lock(identity)
            if lock.locked():
                await self._record("command_rejected", "rejected", identity=identity, details={"command_id": command_id, "cheat_id": cheat_id, "reason": "command_busy"})
                return self._command_result(command_id, identity, cheat_id, "rejected", "command_busy")
            async with lock:
                try:
                    context = await self._context(identity)
                    resolved = await self._resolve(context)
                except CheatServiceError as error:
                    await self._record("command_rejected", "rejected", identity=identity, details={"command_id": command_id, "cheat_id": cheat_id, "reason": error.code})
                    return self._command_result(command_id, identity, cheat_id, "rejected", error.code)
                if resolved is None or cheat_id not in resolved.by_id:
                    await self._record("command_rejected", "rejected", identity=identity, context=context, details={"command_id": command_id, "cheat_id": cheat_id, "reason": "cheat_unavailable"})
                    return self._command_result(command_id, identity, cheat_id, "rejected", "cheat_unavailable")
                cheat = resolved.by_id[cheat_id]
                if resolved.source == "cooperative" and resolved.cooperative is not None:
                    operation = "toggle"
                    operations = resolved.by_id[cheat_id].get("operations")
                    if isinstance(operations, list) and "toggle" not in operations:
                        operation = str(operations[0]) if operations else "toggle"
                    try:
                        ack = await self._cooperative_send(
                            identity,
                            context,
                            resolved.cooperative,
                            command_id,
                            cheat,
                            operation,
                            self._previous_revision(context),
                        )
                    except CheatServiceError as error:
                        if error.code in {"command_context_changed", "command_context_unavailable"}:
                            await self._record("command_rejected", "rejected", identity=identity, context=context, details={"command_id": command_id, "cheat_id": cheat_id, "reason": error.code})
                            return self._command_result(command_id, identity, cheat_id, "rejected", error.code)
                        ack = None
                    except Exception:
                        ack = None
                    if ack is not None:
                        self._remember_revision(context, ack.revision)
                        await self._record(
                            "cooperative_acknowledged" if ack.fresh else "cooperative_stale",
                            "accepted" if ack.fresh and ack.accepted else "rejected",
                            identity=identity,
                            context=context,
                            details={"command_id": command_id, "cheat_id": cheat_id, "revision": ack.revision},
                        )
                        if ack.fresh:
                            return self._command_result(
                                command_id,
                                identity,
                                cheat_id,
                                "requested" if ack.accepted else "rejected",
                                None if ack.accepted else "cooperative_command_rejected",
                                ack.state if ack.accepted else "unknown",
                            )
                    try:
                        context = await self._context(identity)
                        resolved = await self._resolve(context, allow_cooperative=False)
                    except CheatServiceError as error:
                        await self._record("command_rejected", "rejected", identity=identity, details={"command_id": command_id, "cheat_id": cheat_id, "reason": error.code})
                        return self._command_result(command_id, identity, cheat_id, "rejected", error.code)
                    if resolved is None:
                        code = "cooperative_unavailable"
                        await self._record("command_rejected", "rejected", identity=identity, context=context, details={"command_id": command_id, "cheat_id": cheat_id, "reason": code})
                        return self._command_result(command_id, identity, cheat_id, "rejected", code)
                    if cheat_id not in resolved.by_id:
                        code = "cheat_unavailable"
                        return self._command_result(command_id, identity, cheat_id, "rejected", code)
                    cheat = resolved.by_id[cheat_id]
                if self._closing:
                    return self._command_result(command_id, identity, cheat_id, "rejected", "service_closing")
                helper = self._helper_paths.get(context.trainer_arch)
                if not isinstance(helper, (str, Path)) or not str(helper):
                    code = "helper_unavailable"
                    await self._record("command_rejected", "rejected", identity=identity, context=context, details={"command_id": command_id, "cheat_id": cheat_id, "reason": code})
                    return self._command_result(command_id, identity, cheat_id, "rejected", code)
                try:
                    vk, modifiers = hotkey_to_vk(cheat["hotkey"])
                except (KeyError, TypeError, ValueError):
                    code = "invalid_hotkey"
                    await self._record("command_rejected", "rejected", identity=identity, context=context, details={"command_id": command_id, "cheat_id": cheat_id, "reason": code})
                    return self._command_result(command_id, identity, cheat_id, "rejected", code)
                await self._record("helper_spawned", "accepted", identity=identity, context=context, details={"command_id": command_id, "cheat_id": cheat_id, "source": resolved.source})
                started_at = self._clock()
                try:
                    result = await asyncio.to_thread(
                        self._runner.run,
                        context,
                        helper,
                        vk,
                        modifiers,
                        lease_factory=lambda: self._watcher.command_context_lease(identity),
                    )
                except Exception:
                    result = None
                duration_ms = max(0, int((self._clock() - started_at) * 1000))
                if result is None:
                    outcome, diagnostic = "failed", "command_runner_failed"
                else:
                    raw_outcome = getattr(result, "outcome", None)
                    outcome = raw_outcome if raw_outcome in {"requested", "failed", "rejected"} else "failed"
                    diagnostic = _safe_runner_code(getattr(result, "diagnostic", None), "command_runner_failed") if outcome != "requested" else None
                if diagnostic == "command_timeout":
                    await self._record("helper_timeout", "rejected", identity=identity, context=context, details={"command_id": command_id, "cheat_id": cheat_id})
                await self._record("helper_completed", "accepted" if outcome == "requested" else "rejected", identity=identity, context=context, details={"command_id": command_id, "cheat_id": cheat_id, "source": resolved.source, "outcome": outcome, "duration_ms": duration_ms})
                return self._command_result(command_id, identity, cheat_id, outcome, None if outcome == "requested" else diagnostic)
        finally:
            await self._unregister_dispatch(dispatch)


CheatService = CheatControlService

__all__ = ["CheatControlService", "CheatService", "CheatServiceError", "PUBLIC_CHEAT_DIAGNOSTIC_CODES"]
