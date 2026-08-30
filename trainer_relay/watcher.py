"""One-second game-session poller and owned trainer lifecycle."""

from __future__ import annotations

import asyncio
import inspect
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import default_prefix_for, is_launch_identity, validate_game_config
from .diagnostics import (
    DiagnosticRecorder,
    DiagnosticSession,
    DiagnosticValidationError,
    NullDiagnosticRecorder,
)
from .environment import build_sanitized_environment
from .games_map import load_games_map
from .process import CandidateDecision, DiscoveryResult, ProcessDiscoverer, SessionIdentity
from .types import DiscoveryState, RelayStatus


@dataclass
class _RelayState:
    state: RelayStatus = RelayStatus.DISABLED
    diagnostic: str | None = None
    session: SessionIdentity | None = None
    handle: object | None = None
    launched_at: float | None = None
    retry_at: float | None = None
    automatic_retries: int = 0


class RelayWatcher:
    def __init__(
        self,
        config: Mapping[str, Any] | Any,
        *,
        games_map_path: str | os.PathLike[str],
        map_loader: Callable[[str | os.PathLike[str]], Any] = load_games_map,
        process_discoverer: ProcessDiscoverer | Any | None = None,
        umu_resolver: Callable[[], Any] | None = None,
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
        self._clock = clock
        self._sleep = sleep
        self._diagnostics = diagnostics or NullDiagnosticRecorder()
        self._states: dict[str, _RelayState] = {}
        self._stopped = False

    @property
    def config(self) -> Any:
        return self._config

    def _games(self) -> Mapping[str, Any]:
        if isinstance(self._config, Mapping) and isinstance(self._config.get("games"), Mapping):
            return self._config["games"]
        return {}

    def _state_for(self, identity: str) -> _RelayState:
        return self._states.setdefault(identity, _RelayState())

    @staticmethod
    def _diagnostic(code: str | None) -> dict[str, str] | None:
        return {"code": code} if code else None

    def status(self, identity: str) -> dict[str, Any]:
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

    async def _stop_owned(self, state: _RelayState, identity: str | None = None) -> None:
        if state.handle is None:
            return
        handle = state.handle
        session = state.session
        process_group_id = self._process_group_id(handle)
        state.handle = None
        state.launched_at = None
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

    def _set_state(self, state: _RelayState, value: RelayStatus, diagnostic: str | None = None) -> None:
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
        event = "candidate_accepted" if decision.accepted else "candidate_rejected"
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

    async def _spawn(self, state: _RelayState, identity: str, game: Mapping[str, Any], session: SessionIdentity, environment: Mapping[str, str]) -> None:
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
            safe_environment = build_sanitized_environment(environment)
            state.handle = await self._maybe_await(self._runner.spawn(session, trainer_path, safe_environment))
        except Exception as error:
            candidate_code = str(error)
            code = candidate_code if candidate_code in {"umu_not_found", "umu_ambiguous"} else "trainer_spawn_failed"
            event = "umu_rejected" if code.startswith("umu_") else "trainer_spawn_failed"
            self._record(
                "umu" if event == "umu_rejected" else "trainer",
                event,
                "rejected" if event == "umu_rejected" else "error",
                identity=identity,
                session=session,
                details={"reason": code}
                if event == "umu_rejected"
                else {"trainer_path": str(game["trainerPath"]), "reason": code},
            )
            state.handle = None
            state.launched_at = None
            self._set_state(state, RelayStatus.INVALID_CONFIG, code)
            return
        spawn_details: dict[str, Any] = {"trainer_path": str(game["trainerPath"])}
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
        state.launched_at = self._clock()
        state.retry_at = None
        self._set_state(state, RelayStatus.LAUNCHING)

    async def _poll_identity(self, identity: str, *, force_retry: bool = False) -> None:
        state = self._state_for(identity)
        game = self._games().get(identity)
        if not is_launch_identity(identity):
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.INVALID_CONFIG, "invalid_config_identity")
            return
        if game is None:
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.DISABLED)
            state.session = None
            state.retry_at = None
            return
        if not isinstance(game, Mapping) or game.get("enabled") is not True:
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.DISABLED)
            state.session = None
            state.retry_at = None
            return
        validated_game = validate_game_config(game)
        if validated_game is None:
            await self._stop_owned(state, identity)
            self._set_state(state, RelayStatus.INVALID_CONFIG, "invalid_config_entry")
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

        prefix = validated_game.get("prefixOverride") or default_prefix_for(identity, self._home)
        self._record(
            "config",
            "prefix_selected",
            "info",
            identity=identity,
            details={
                "source": "override" if validated_game.get("prefixOverride") else "unifideck_default",
                "expected_prefix": prefix,
            },
        )
        try:
            discovery: DiscoveryResult = self._process_discoverer.discover(identity, entry.executable, prefix)
        except Exception:
            discovery = DiscoveryResult(DiscoveryState.WAITING_FOR_GAME, diagnostic="proc_unreadable")
        self._record_discovery(identity, discovery)
        if discovery.state == DiscoveryState.AMBIGUOUS:
            await self._stop_owned(state, identity)
            state.session = None
            self._set_state(state, RelayStatus.AMBIGUOUS, discovery.diagnostic or "multiple_game_sessions")
            return
        if discovery.state == DiscoveryState.INVALID_CONFIG:
            await self._stop_owned(state, identity)
            state.session = None
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
            self._set_state(state, RelayStatus.WAITING_FOR_GAME, discovery.diagnostic)
            return

        if state.session != discovery.session:
            previous_state = state.state
            previous_session = state.session
            await self._stop_owned(state, identity)
            state.session = discovery.session
            state.retry_at = None
            state.automatic_retries = 0
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
        now = self._clock()
        if state.handle is not None:
            try:
                exit_code = await self._maybe_await(self._runner.poll(state.handle))
            except Exception:
                exit_code = 1
            if exit_code is None:
                if state.launched_at is not None and now - state.launched_at >= 3.0:
                    if state.state != RelayStatus.RUNNING:
                        self._record(
                            "trainer",
                            "trainer_running",
                            "accepted",
                            identity=identity,
                            session=state.session,
                            details={
                                "trainer_path": str(validated_game["trainerPath"]),
                                "elapsed_ms": int((now - state.launched_at) * 1000),
                            },
                        )
                    self._set_state(state, RelayStatus.RUNNING)
                else:
                    self._set_state(state, RelayStatus.LAUNCHING)
                return
            handle = state.handle
            launched_at = state.launched_at
            state.handle = None
            state.launched_at = None
            await self._discard_exited(handle)
            elapsed = now - (launched_at if launched_at is not None else now)
            self._record(
                "trainer",
                "trainer_exited",
                "warning" if elapsed < 3.0 else "info",
                identity=identity,
                session=state.session,
                details={
                    "trainer_path": str(validated_game["trainerPath"]),
                    "exit_code": int(exit_code),
                    "elapsed_ms": int(elapsed * 1000),
                },
            )
            if elapsed < 3.0 and state.automatic_retries < 1:
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
        await self._spawn(state, identity, validated_game, discovery.session, discovery.environment or {})

    async def poll_once(self) -> None:
        identities = set(self._states) | set(self._games())
        for identity in sorted(identities):
            await self._poll_identity(identity)

    async def update_config(self, config: Mapping[str, Any] | Any) -> None:
        self._config = config
        await self.poll_once()

    async def retry(self, identity: str) -> dict[str, Any]:
        if not is_launch_identity(identity):
            return self.status(identity)
        await self._poll_identity(identity, force_retry=True)
        return self.status(identity)

    async def run(self) -> None:
        self._stopped = False
        while not self._stopped:
            await self.poll_once()
            await self._sleep(1.0)

    async def stop(self) -> None:
        self._stopped = True
        for identity, state in self._states.items():
            await self._stop_owned(state, identity)
