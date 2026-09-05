"""One-second game-session poller and owned trainer lifecycle."""

from __future__ import annotations

import asyncio
import inspect
import ntpath
import os
import posixpath
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import default_prefix_for, is_launch_identity, validate_game_config
from .container_reentry import ContainerReentryError, ContainerReentryProbe
from .diagnostics import (
    DiagnosticRecorder,
    DiagnosticSession,
    DiagnosticValidationError,
    NullDiagnosticRecorder,
)
from .environment import build_sanitized_environment
from .games_map import load_games_map
from .window_probe import collect_window_snapshot
from .helper_manifest import read_pe_architecture, sha256_file
from .process import CandidateDecision, DiscoveryResult, ProcessDiscoverer, SessionIdentity, normalize_wine_path
from .types import CommandContext, CommandContextError, DiscoveryState, RelayStatus


_DIAGNOSTIC_RUNTIME_FLAGS = frozenset(
    {
        "STEAM_COMPAT_LAUNCHER_SERVICE",
        "STEAM_RUNTIME_LIBRARY_PATH",
        "UMU_CONTAINER_NSENTER",
    }
)

_HOST_RUNTIME_ENVIRONMENT_KEYS = frozenset(
    {
        "HOME",
        "PATH",
        "XDG_DATA_HOME",
        "UMU_FOLDERS_PATH",
        "DBUS_SESSION_BUS_ADDRESS",
        "XDG_RUNTIME_DIR",
    }
)


@dataclass
class _RelayState:
    state: RelayStatus = RelayStatus.DISABLED
    diagnostic: str | None = None
    session: SessionIdentity | None = None
    handle: object | None = None
    launched_at: float | None = None
    retry_at: float | None = None
    automatic_retries: int = 0
    rejected_preflight_session: SessionIdentity | None = None
    expected_reentry_bus: str | None = None
    reentry_confirmed: bool = False
    service_marker_present: bool = False
    effective_environment: dict[str, str] | None = None
    prefix: str | None = None
    umu_run: str | None = None
    trainer_path: str | None = None
    trainer_sha256: str | None = None
    session_prefix: str | None = None
    window_snapshot_at: float | None = None


class RelayWatcher:
    def __init__(
        self,
        config: Mapping[str, Any] | Any,
        *,
        games_map_path: str | os.PathLike[str],
        map_loader: Callable[[str | os.PathLike[str]], Any] = load_games_map,
        process_discoverer: ProcessDiscoverer | Any | None = None,
        umu_resolver: Callable[[], Any] | None = None,
        container_probe: Any | None = None,
        runner: Any,
        home: str | os.PathLike[str] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Any] = asyncio.sleep,
        diagnostics: DiagnosticRecorder | NullDiagnosticRecorder | Any | None = None,
    ) -> None:
        self._config = config
        self._games_map_path = games_map_path
        self._map_loader = map_loader
        self._process_discoverer = process_discoverer or ProcessDiscoverer()
        self._umu_resolver = umu_resolver or (lambda: None)
        self._runner = runner
        self._home = os.fspath(home) if home is not None else str(Path.home())
        self._container_probe = container_probe or ContainerReentryProbe(self._home)
        self._clock = clock
        self._sleep = sleep
        self._diagnostics = diagnostics or NullDiagnosticRecorder()
        self._states: dict[str, _RelayState] = {}
        self._state_lock = threading.RLock()
        self._stopped = False

    @property
    def config(self) -> Any:
        with self._state_lock:
            return self._config

    def _games(self) -> Mapping[str, Any]:
        with self._state_lock:
            if isinstance(self._config, Mapping) and isinstance(self._config.get("games"), Mapping):
                return self._config["games"]
            return {}

    def _state_for(self, identity: str) -> _RelayState:
        with self._state_lock:
            return self._states.setdefault(identity, _RelayState())

    @staticmethod
    def _diagnostic(code: str | None) -> dict[str, str] | None:
        return {"code": code} if code else None

    @staticmethod
    def _prefix_anchor(prefix: str, *, override: bool) -> str:
        normalized = prefix.rstrip("/\\") or prefix
        if not override:
            return normalized
        path_module = ntpath if "\\" in normalized else posixpath
        parent, basename = path_module.split(normalized)
        return parent if basename.casefold() == "pfx" and parent else normalized

    def status(self, identity: str) -> dict[str, Any]:
        with self._state_lock:
            state = self._states.get(identity, _RelayState())
            return {
                "identity": identity,
                "state": state.state,
                "diagnostic": self._diagnostic(state.diagnostic),
            }

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _record(
        self,
        category: str,
        event: str,
        outcome: str,
        *,
        identity: str | None = None,
        session: SessionIdentity | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        diagnostic_session = DiagnosticSession(session.pid, session.start_time) if session is not None else None
        try:
            self._diagnostics.record(
                category,
                event,
                outcome,
                identity=identity,
                session=diagnostic_session,
                details=details,
            )
        except (DiagnosticValidationError, OSError, ValueError):
            return

    @staticmethod
    def _process_group_id(handle: object) -> int | None:
        if isinstance(handle, Mapping):
            value = handle.get("process_group_id")
        else:
            value = getattr(handle, "process_group_id", None)
        return value if type(value) is int and value > 0 else None

    @staticmethod
    def _reset_launch_state(state: _RelayState) -> None:
        state.handle = None
        state.launched_at = None
        state.expected_reentry_bus = None
        state.reentry_confirmed = False
        state.service_marker_present = False
        state.effective_environment = None
        state.prefix = None
        state.umu_run = None
        state.trainer_path = None
        state.trainer_sha256 = None

    async def _stop_owned(self, state: _RelayState, identity: str | None = None) -> None:
        await self._acquire_state_lock()
        try:
            if state.handle is None:
                self._reset_launch_state(state)
                return
            handle = state.handle
            session = state.session
            process_group_id = self._process_group_id(handle)
            self._reset_launch_state(state)
        finally:
            self._state_lock.release()
        stop_result = None
        try:
            stop_result = await self._maybe_await(self._runner.stop(handle))
        except (OSError, ValueError):
            pass
        if stop_result is not None and process_group_id is not None:
            self._record(
                "trainer",
                "owned_group_signal",
                "info",
                identity=identity,
                session=session,
                details={"process_group_id": process_group_id, "signal": "SIGTERM", "forced": False},
            )
            if getattr(stop_result, "forced", False):
                self._record(
                    "trainer",
                    "owned_group_signal",
                    "warning",
                    identity=identity,
                    session=session,
                    details={"process_group_id": process_group_id, "signal": "SIGKILL", "forced": True},
                )
        forget = getattr(self._runner, "forget", None)
        if forget is not None:
            await self._maybe_await(forget(handle))

    async def _discard_exited(self, handle: object) -> None:
        forget = getattr(self._runner, "forget", None)
        if forget is not None:
            await self._maybe_await(forget(handle))

    async def _exit_diagnostics(self, handle: object) -> Mapping[str, Any] | None:
        getter = getattr(self._runner, "exit_diagnostics", None)
        if getter is None:
            return None
        try:
            result = await self._maybe_await(getter(handle))
        except (OSError, ValueError):
            return None
        if result is None:
            return None
        if isinstance(result, Mapping):
            return result
        to_wire = getattr(result, "to_wire", None)
        if to_wire is None:
            return None
        value = to_wire()
        return value if isinstance(value, Mapping) else None

    def _set_state(self, state: _RelayState, value: RelayStatus, diagnostic: str | None = None) -> None:
        with self._state_lock:
            state.state = value
            state.diagnostic = diagnostic

    def _record_discovery(self, identity: str, discovery: DiscoveryResult) -> None:
        counts = discovery.rejection_counts
        details = {
            "process_count": len(discovery.decisions),
            "readable_count": sum(decision.reason != "proc_entry_unreadable" for decision in discovery.decisions),
            "relevant_count": sum(decision.relevant for decision in discovery.decisions),
            "accepted_count": sum(decision.accepted for decision in discovery.decisions),
            "proc_entry_unreadable_count": counts.get("proc_entry_unreadable", 0),
            "pid_reused_during_scan_count": counts.get("pid_reused_during_scan", 0),
            "missing_required_environment_count": counts.get("missing_required_environment", 0),
            "process_name_mismatch_count": counts.get("process_name_mismatch", 0),
            "store_mismatch_count": counts.get("store_mismatch", 0),
            "prefix_mismatch_count": counts.get("prefix_mismatch", 0),
            "executable_mismatch_count": counts.get("executable_mismatch", 0),
            "legacy_settings_present_count": counts.get("legacy_settings_present", 0),
        }
        self._record("process", "process_scan_summary", "info", identity=identity, details=details)
        for decision in discovery.decisions:
            if not decision.relevant:
                continue
            self._record_candidate(identity, decision)

    def _record_candidate(self, identity: str, decision: CandidateDecision) -> None:
        details: dict[str, Any] = dict(decision.details)
        event = decision.reason if decision.accepted else "candidate_rejected"
        if not decision.accepted:
            details["reason"] = decision.reason
        session = decision.session
        if session is None and decision.start_time > 0:
            session = SessionIdentity(decision.pid, decision.start_time)
        self._record(
            "process",
            event,
            "accepted" if decision.accepted else "rejected",
            identity=identity,
            session=session,
            details=details,
        )

    async def _spawn(
        self,
        state: _RelayState,
        identity: str,
        game: Mapping[str, Any],
        session: SessionIdentity,
        environment: Mapping[str, str],
        prefix: str,
    ) -> None:
        service_marker_present = bool(environment.get("STEAM_COMPAT_LAUNCHER_SERVICE"))
        try:
            resolution = self._umu_resolver()
            if not resolution:
                raise RuntimeError("umu_not_found")
            umu_path = getattr(resolution, "path", resolution)
            umu_source = getattr(resolution, "source", "resolver")
            self._record(
                "umu",
                "umu_resolved",
                "accepted",
                identity=identity,
                session=session,
                details={"source": str(umu_source), "umu_path": str(umu_path)},
            )
            trainer_path = str(game["trainerPath"])
            trainer_sha256 = sha256_file(trainer_path)
            source_environment = dict(environment)
            # The exact INFO re-entry line is part of the fail-closed launch
            # contract. DEBUG would expose UMU's complete derived environment.
            source_environment["UMU_LOG"] = "info"
            safe_environment = build_sanitized_environment(source_environment, prefix)
            reentry = await self._maybe_await(self._container_probe.verify(safe_environment))
            launch_environment = reentry.launch_environment
            required_launch_values = {
                key: launch_environment.get(key)
                for key in ("HOME", "PATH", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR")
            }
            if any(not isinstance(value, str) or not value for value in required_launch_values.values()):
                raise ContainerReentryError(
                    "container_reentry_probe_failed",
                    failure_class="host_session_bus_unavailable",
                    bus_source=str(reentry.bus_source),
                    attempts=int(reentry.attempts),
                )
            for key in _HOST_RUNTIME_ENVIRONMENT_KEYS:
                safe_environment.pop(key, None)
            safe_environment.update(
                {
                    key: value
                    for key, value in launch_environment.items()
                    if key in _HOST_RUNTIME_ENVIRONMENT_KEYS and isinstance(value, str) and value
                }
            )
            proton_verb = safe_environment.pop("PROTON_VERB")
            safe_environment["PROTON_VERB"] = proton_verb
            self._record(
                "umu",
                "container_reentry_verified",
                "accepted",
                identity=identity,
                session=session,
                details={
                    "bus_name": str(reentry.bus_name),
                    "runtime_variant": str(reentry.runtime_variant),
                    "attempt_count": int(reentry.attempts),
                    "bus_source": str(reentry.bus_source),
                    "app_id_source": str(reentry.app_id_source),
                    "service_marker_present": service_marker_present,
                },
            )
            launch_started_at = self._clock()
            state.handle = await self._maybe_await(
                self._runner.spawn(
                    session,
                    trainer_path,
                    safe_environment,
                    expected_reentry_bus=str(reentry.bus_name),
                )
            )
            state.expected_reentry_bus = str(reentry.bus_name)
            state.reentry_confirmed = False
            state.service_marker_present = service_marker_present
            state.effective_environment = dict(safe_environment)
            state.prefix = prefix
            state.umu_run = str(umu_path)
            state.trainer_path = trainer_path
            state.trainer_sha256 = trainer_sha256
        except Exception as error:
            candidate_code = str(error)
            bounded_codes = {
                "umu_not_found",
                "umu_ambiguous",
                "container_reentry_unsupported",
                "container_reentry_probe_failed",
                "container_reentry_bus_missing",
                "container_reentry_identity_mismatch",
            }
            code = candidate_code if candidate_code in bounded_codes else "trainer_spawn_failed"
            event = (
                "container_reentry_rejected"
                if code.startswith("container_reentry_")
                else "umu_rejected"
                if code.startswith("umu_")
                else "trainer_spawn_failed"
            )
            rejection_details: dict[str, Any] = {"reason": code}
            if event == "container_reentry_rejected":
                rejection_details["service_marker_present"] = service_marker_present
            for attribute, detail_key in (
                ("failure_class", "failure_class"),
                ("exit_code", "probe_exit_code"),
                ("bus_source", "bus_source"),
                ("attempts", "attempt_count"),
            ):
                value = getattr(error, attribute, None)
                if value is not None:
                    rejection_details[detail_key] = value
            self._record(
                "umu" if event in {"umu_rejected", "container_reentry_rejected"} else "trainer",
                event,
                "rejected" if event in {"umu_rejected", "container_reentry_rejected"} else "error",
                identity=identity,
                session=session,
                details=rejection_details
                if event in {"umu_rejected", "container_reentry_rejected"}
                else {"trainer_path": str(game["trainerPath"]), "reason": code},
            )
            self._reset_launch_state(state)
            state.rejected_preflight_session = session if code.startswith("container_reentry_") else None
            self._set_state(state, RelayStatus.INVALID_CONFIG, code)
            return
        spawn_details: dict[str, Any] = {
            "trainer_path": str(game["trainerPath"]),
            "wineprefix": safe_environment["WINEPREFIX"],
            "steam_compat_data_path": safe_environment["STEAM_COMPAT_DATA_PATH"],
            "proton_verb": safe_environment["PROTON_VERB"],
            "container_reentry": "enabled" if safe_environment.get("UMU_CONTAINER_NSENTER") == "1" else "missing",
            "environment_key_count": len(safe_environment),
            "runtime_flags": ",".join(sorted(_DIAGNOSTIC_RUNTIME_FLAGS.intersection(environment))),
        }
        process_group_id = self._process_group_id(state.handle)
        if process_group_id is not None:
            spawn_details["process_group_id"] = process_group_id
        self._record(
            "trainer",
            "trainer_spawned",
            "accepted",
            identity=identity,
            session=session,
            details=spawn_details,
        )
        state.launched_at = launch_started_at
        state.retry_at = None
        state.rejected_preflight_session = None
        self._set_state(state, RelayStatus.LAUNCHING)

    @staticmethod
    def _raise_context(code: str) -> None:
        raise CommandContextError(code)

    @staticmethod
    def _prefix_matches(expected: str, observed: str) -> bool:
        expected_normalized = normalize_wine_path(expected).rstrip("/")
        observed_normalized = normalize_wine_path(observed).rstrip("/")
        return observed_normalized in {expected_normalized, expected_normalized + "/pfx"}

    def _command_context_unlocked(self, identity: str) -> CommandContext:
        """Return a fresh, immutable command snapshot only for a live relay session."""

        if not is_launch_identity(identity):
            self._raise_context("invalid_config_identity")
        state = self._states.get(identity)
        if state is None or state.state != RelayStatus.RUNNING:
            self._raise_context("relay_not_running")
        if state.session is None or state.handle is None:
            self._raise_context("session_ended")
        if (
            state.effective_environment is None
            or not state.umu_run
            or not state.trainer_path
            or not state.trainer_sha256
        ):
            self._raise_context("command_context_unavailable")
        if not state.expected_reentry_bus or not state.reentry_confirmed:
            self._raise_context("container_reentry_bus_missing")

        owned_handles = getattr(self._runner, "owned", None)
        if owned_handles is None or not any(candidate is state.handle for candidate in owned_handles):
            self._raise_context("trainer_not_owned")
        poll = getattr(self._runner, "poll", None)
        if poll is not None:
            try:
                if poll(state.handle) is not None:
                    self._raise_context("trainer_not_owned")
            except CommandContextError:
                raise
            except (OSError, ProcessLookupError, TypeError, ValueError):
                self._raise_context("trainer_not_owned")

        game = self._games().get(identity)
        validated_game = validate_game_config(game) if game is not None else None
        if validated_game is None:
            self._raise_context("relay_not_running")
        if str(validated_game["trainerPath"]) != state.trainer_path:
            self._raise_context("trainer_not_owned")

        try:
            map_result = self._map_loader(self._games_map_path)
        except Exception:
            map_result = None
        if map_result is None or getattr(map_result, "diagnostic", None) is not None:
            self._raise_context("games_map_unreadable")
        entry = map_result.entry_for(identity)
        if entry is None:
            self._raise_context("games_map_identity_missing")

        expected_prefix = state.prefix or ""
        try:
            discovery = self._process_discoverer.discover(
                identity,
                entry.executable,
                expected_prefix,
                expected_session=state.session,
            )
        except Exception:
            self._raise_context("session_ended")
        if discovery.state == DiscoveryState.AMBIGUOUS:
            self._raise_context("multiple_game_sessions")
        if discovery.state != DiscoveryState.SESSION or discovery.session is None:
            self._raise_context("session_ended")
        if discovery.session != state.session:
            self._raise_context("session_recycled")
        observed_environment = discovery.environment or {}
        observed_prefix = observed_environment.get("WINEPREFIX", "")
        original_prefix = state.session_prefix or ""
        if not observed_prefix or not original_prefix or not self._prefix_matches(original_prefix, observed_prefix):
            self._raise_context("prefix_mismatch")

        try:
            trainer_sha256 = sha256_file(state.trainer_path)
        except (OSError, TypeError, ValueError):
            self._raise_context("trainer_hash_unavailable")
        if trainer_sha256 != state.trainer_sha256:
            self._raise_context("trainer_hash_changed")
        try:
            trainer_arch = read_pe_architecture(state.trainer_path)
        except (OSError, TypeError, ValueError):
            self._raise_context("trainer_architecture_unknown")

        return CommandContext(
            identity=identity,
            session=state.session,
            trainer_sha256=trainer_sha256,
            trainer_arch=trainer_arch,
            environment=state.effective_environment,
            umu_run=state.umu_run,
            expected_reentry_bus=state.expected_reentry_bus,
        )

    def command_context(self, identity: str) -> CommandContext:
        with self._state_lock:
            return self._command_context_unlocked(identity)

    @contextmanager
    def command_context_lease(self, identity: str):
        with self._state_lock:
            yield self.command_context(identity)

    async def _acquire_state_lock(self) -> None:
        while not self._state_lock.acquire(blocking=False):
            await asyncio.sleep(0)

    async def _poll_identity_unlocked(self, identity: str, *, force_retry: bool = False) -> None:
        state = self._state_for(identity)
        game = self._games().get(identity)
        if not is_launch_identity(identity):
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.INVALID_CONFIG, "invalid_config_identity")
            state.session = None
            state.session_prefix = None
            return
        if game is None:
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.DISABLED)
            state.session = None
            state.session_prefix = None
            state.retry_at = None
            state.rejected_preflight_session = None
            return
        if not isinstance(game, Mapping) or game.get("enabled") is not True:
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.DISABLED)
            state.session = None
            state.session_prefix = None
            state.retry_at = None
            state.rejected_preflight_session = None
            return
        validated_game = validate_game_config(game)
        if validated_game is None:
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.INVALID_CONFIG, "invalid_config_entry")
            state.session = None
            state.session_prefix = None
            return

        try:
            map_result = self._map_loader(self._games_map_path)
        except Exception:
            map_result = None
        diagnostic = getattr(map_result, "diagnostic", None)
        if diagnostic is not None:
            code = getattr(diagnostic, "code", "games_map_unreadable")
            self._record(
                "games_map",
                "games_map_rejected",
                "rejected",
                identity=identity,
                details={"reason": code, "map_path": os.fspath(self._games_map_path)},
            )
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.INVALID_CONFIG, code)
            return
        entry = map_result.entry_for(identity) if map_result is not None else None
        if entry is None:
            code = "games_map_unreadable" if map_result is None else "games_map_identity_missing"
            self._record(
                "games_map",
                "games_map_rejected",
                "rejected",
                identity=identity,
                details={"reason": code, "map_path": os.fspath(self._games_map_path)},
            )
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.WAITING_FOR_GAME, "games_map_identity_missing")
            return

        entries = getattr(map_result, "entries", {})
        self._record(
            "games_map",
            "games_map_loaded",
            "accepted",
            identity=identity,
            details={
                "entry_count": len(entries) if isinstance(entries, Mapping) else 0,
                "map_path": os.fspath(self._games_map_path),
                "expected_executable": entry.executable,
            },
        )

        prefix_override = validated_game.get("prefixOverride")
        prefix = self._prefix_anchor(
            prefix_override or default_prefix_for(identity, self._home),
            override=bool(prefix_override),
        )
        self._record(
            "config",
            "prefix_selected",
            "info",
            identity=identity,
            details={
                "source": "override" if prefix_override else "unifideck_default",
                "expected_prefix": prefix,
            },
        )
        try:
            discovery: DiscoveryResult = self._process_discoverer.discover(
                identity,
                entry.executable,
                prefix,
                expected_session=state.session,
            )
        except Exception:
            discovery = DiscoveryResult(DiscoveryState.WAITING_FOR_GAME, diagnostic="proc_unreadable")
        self._record_discovery(identity, discovery)
        if discovery.state == DiscoveryState.AMBIGUOUS:
            await self._stop_owned(state, identity)
            state.session = None
            state.session_prefix = None
            self._set_state(state, RelayStatus.AMBIGUOUS, discovery.diagnostic or "multiple_game_sessions")
            return
        if discovery.state == DiscoveryState.INVALID_CONFIG:
            await self._stop_owned(state, identity)
            state.session = None
            state.session_prefix = None
            state.rejected_preflight_session = None
            self._set_state(state, RelayStatus.INVALID_CONFIG, discovery.diagnostic or "invalid_process_environment")
            return
        if discovery.state != DiscoveryState.SESSION or discovery.session is None:
            if state.session is not None:
                self._record(
                    "lifecycle",
                    "session_ended",
                    "info",
                    identity=identity,
                    session=state.session,
                    details={},
                )
            await self._stop_owned(state, identity)
            state.session = None
            state.session_prefix = None
            state.rejected_preflight_session = None
            self._set_state(state, RelayStatus.WAITING_FOR_GAME, discovery.diagnostic)
            return

        if state.session != discovery.session:
            previous_state = state.state
            previous_session = state.session
            await self._stop_owned(state, identity)
            state.session = discovery.session
            state.session_prefix = (discovery.environment or {}).get("WINEPREFIX")
            state.retry_at = None
            state.automatic_retries = 0
            state.rejected_preflight_session = None
            state.diagnostic = None
            if previous_session is not None:
                self._record(
                    "lifecycle",
                    "session_changed",
                    "info",
                    identity=identity,
                    session=discovery.session,
                    details={
                        "previous_pid": previous_session.pid,
                        "previous_start_time": previous_session.start_time,
                    },
                )
            if previous_state in {
                RelayStatus.FAILED,
                RelayStatus.RETRYING,
                RelayStatus.LAUNCHING,
                RelayStatus.RUNNING,
            }:
                state.state = RelayStatus.WAITING_FOR_GAME
        if state.handle is None and state.state == RelayStatus.FAILED and not force_retry:
            return
        if state.rejected_preflight_session == discovery.session and not force_retry:
            return
        now = self._clock()
        if state.handle is not None:
            try:
                exit_code = await self._maybe_await(self._runner.poll(state.handle))
            except Exception:
                exit_code = 1
            if exit_code is None:
                elapsed = now - state.launched_at if state.launched_at is not None else 0.0
                reentry_status = "pending"
                reentry_observed_at: float | None = None
                reentry_status_getter = getattr(self._runner, "reentry_status", None)
                if reentry_status_getter is not None:
                    try:
                        try:
                            observed = await self._maybe_await(
                                reentry_status_getter(
                                    state.handle,
                                    wait_seconds=0.05 if elapsed >= 3.0 else 0.0,
                                )
                            )
                        except TypeError:
                            observed = await self._maybe_await(reentry_status_getter(state.handle))
                        if observed in {"pending", "retrying", "confirmed"}:
                            reentry_status = observed
                    except (OSError, ValueError):
                        pass
                observation_getter = getattr(self._runner, "reentry_observed_at", None)
                if reentry_status in {"confirmed", "retrying"} and observation_getter is not None:
                    try:
                        candidate_observed_at = await self._maybe_await(
                            observation_getter(state.handle, reentry_status)
                        )
                        if isinstance(candidate_observed_at, (int, float)):
                            reentry_observed_at = float(candidate_observed_at)
                    except (OSError, TypeError, ValueError):
                        pass
                confirmed_within_deadline = (
                    reentry_status == "confirmed"
                    and reentry_observed_at is not None
                    and state.launched_at is not None
                    and reentry_observed_at - state.launched_at <= 3.0
                )
                if confirmed_within_deadline and not state.reentry_confirmed:
                    state.reentry_confirmed = True
                    confirmation_elapsed = max(0.0, reentry_observed_at - state.launched_at)
                    self._record(
                        "umu",
                        "container_reentry_confirmed",
                        "accepted",
                        identity=identity,
                        session=state.session,
                        details={
                            "bus_name": state.expected_reentry_bus or "unknown",
                            "elapsed_ms": int(confirmation_elapsed * 1000),
                        },
                    )
                if elapsed >= 3.0 and not state.reentry_confirmed:
                    expected_reentry_bus = state.expected_reentry_bus or "unknown"
                    service_marker_present = state.service_marker_present
                    self._record(
                        "umu",
                        "container_reentry_confirmation_failed",
                        "rejected",
                        identity=identity,
                        session=state.session,
                        details={
                            "bus_name": expected_reentry_bus,
                            "elapsed_ms": int(elapsed * 1000),
                            "failure_observed": reentry_status == "retrying",
                            "service_marker_present": service_marker_present,
                        },
                    )
                    await self._stop_owned(state, identity)
                    self._set_state(state, RelayStatus.FAILED, "container_reentry_confirmation_failed")
                    return
                if state.reentry_confirmed and elapsed >= 3.0:
                    if (elapsed >= 10.0 and state.window_snapshot_at != state.launched_at
                            and getattr(self._diagnostics, 'enabled', False) is True):
                        state.window_snapshot_at = state.launched_at
                        try:
                            snapshot = await asyncio.to_thread(
                                collect_window_snapshot, dict(discovery.environment or {}),
                            )
                        except Exception:
                            snapshot = {'probe_status': 'probe_failed'}
                        self._record('trainer', 'window_snapshot', 'info', identity=identity,
                                     session=state.session, details=snapshot)
                    if state.state != RelayStatus.RUNNING:
                        self._record(
                            "trainer",
                            "trainer_running",
                            "accepted",
                            identity=identity,
                            session=state.session,
                            details={
                                "trainer_path": str(validated_game["trainerPath"]),
                                "elapsed_ms": int(elapsed * 1000),
                            },
                        )
                    self._set_state(state, RelayStatus.RUNNING)
                else:
                    self._set_state(state, RelayStatus.LAUNCHING)
                return
            was_running = state.state == RelayStatus.RUNNING
            handle = state.handle
            launched_at = state.launched_at
            self._reset_launch_state(state)
            exit_diagnostics = await self._exit_diagnostics(handle)
            if exit_diagnostics is not None:
                self._record(
                    "umu",
                    "umu_exit_diagnostics",
                    "warning" if not was_running else "info",
                    identity=identity,
                    session=state.session,
                    details=exit_diagnostics,
                )
            await self._discard_exited(handle)
            elapsed = now - (launched_at if launched_at is not None else now)
            self._record(
                "trainer",
                "trainer_exited",
                "warning" if not was_running else "info",
                identity=identity,
                session=state.session,
                details={
                    "trainer_path": str(validated_game["trainerPath"]),
                    "exit_code": int(exit_code),
                    "elapsed_ms": int(elapsed * 1000),
                },
            )
            if not was_running and state.automatic_retries < 1:
                state.automatic_retries += 1
                state.retry_at = now + 2.0
                self._record(
                    "trainer",
                    "trainer_retry_scheduled",
                    "info",
                    identity=identity,
                    session=state.session,
                    details={"retry_count": state.automatic_retries, "delay_ms": 2000},
                )
                self._set_state(state, RelayStatus.RETRYING, "trainer_exited")
                return
            self._set_state(state, RelayStatus.FAILED, "trainer_exited")
            return
        if state.state == RelayStatus.RETRYING and not force_retry:
            if state.retry_at is None or now < state.retry_at:
                return
        if force_retry:
            self._record(
                "trainer",
                "trainer_manual_retry",
                "info",
                identity=identity,
                session=discovery.session,
                details={"retry_count": state.automatic_retries + 1},
            )
            state.automatic_retries = 0
            state.rejected_preflight_session = None
        await self._spawn(state, identity, validated_game, discovery.session, discovery.environment or {}, prefix)

    async def _poll_identity(self, identity: str, *, force_retry: bool = False) -> None:
        await self._acquire_state_lock()
        try:
            await self._poll_identity_unlocked(identity, force_retry=force_retry)
        finally:
            self._state_lock.release()

    async def poll_once(self) -> None:
        await self._acquire_state_lock()
        try:
            identities = set(self._states) | set(self._games())
        finally:
            self._state_lock.release()
        for identity in sorted(identities):
            await self._poll_identity(identity)

    async def update_config(self, config: Mapping[str, Any] | Any) -> None:
        await self._acquire_state_lock()
        try:
            self._config = config
        finally:
            self._state_lock.release()
        await self.poll_once()

    async def retry(self, identity: str) -> dict[str, Any]:
        if not is_launch_identity(identity):
            return self.status(identity)
        await self._poll_identity(identity, force_retry=True)
        return self.status(identity)

    async def run(self) -> None:
        await self._acquire_state_lock()
        try:
            self._stopped = False
        finally:
            self._state_lock.release()
        while True:
            await self._acquire_state_lock()
            try:
                if self._stopped:
                    return
            finally:
                self._state_lock.release()
            await self.poll_once()
            await self._sleep(1.0)

    async def stop(self) -> None:
        await self._acquire_state_lock()
        try:
            self._stopped = True
            states = tuple(self._states.items())
        finally:
            self._state_lock.release()
        for identity, state in states:
            await self._stop_owned(state, identity)
