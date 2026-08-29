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
from .environment import build_sanitized_environment
from .games_map import load_games_map
from .process import DiscoveryResult, ProcessDiscoverer, SessionIdentity


@dataclass
class _RelayState:
    state: str = "disabled"
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

    async def _stop_owned(self, state: _RelayState) -> None:
        if state.handle is None:
            return
        handle = state.handle
        state.handle = None
        state.launched_at = None
        try:
            await self._maybe_await(self._runner.stop(handle))
        except (OSError, ValueError):
            pass
        forget = getattr(self._runner, "forget", None)
        if forget is not None:
            await self._maybe_await(forget(handle))

    async def _discard_exited(self, handle: object) -> None:
        forget = getattr(self._runner, "forget", None)
        if forget is not None:
            await self._maybe_await(forget(handle))

    def _set_state(self, state: _RelayState, value: str, diagnostic: str | None = None) -> None:
        state.state = value
        state.diagnostic = diagnostic

    async def _spawn(self, state: _RelayState, identity: str, game: Mapping[str, Any], session: SessionIdentity, environment: Mapping[str, str]) -> None:
        try:
            umu_run = self._umu_resolver()
            if not umu_run:
                raise RuntimeError("umu_not_found")
            trainer_path = str(game["trainerPath"])
            safe_environment = build_sanitized_environment(environment)
            state.handle = await self._maybe_await(self._runner.spawn(session, trainer_path, safe_environment))
        except Exception as error:
            code = str(error) if str(error).replace("_", "").isalnum() else "trainer_spawn_failed"
            if not code.startswith(("umu_", "trainer_")):
                code = "trainer_spawn_failed"
            state.handle = None
            state.launched_at = None
            self._set_state(state, "invalid_config", code)
            return
        state.launched_at = self._clock()
        state.retry_at = None
        self._set_state(state, "launching")

    async def _poll_identity(self, identity: str, *, force_retry: bool = False) -> None:
        state = self._state_for(identity)
        game = self._games().get(identity)
        if not is_launch_identity(identity):
            await self._stop_owned(state)
            self._set_state(state, "invalid_config", "invalid_config_identity")
            return
        if game is None:
            await self._stop_owned(state)
            self._set_state(state, "disabled")
            state.session = None
            state.retry_at = None
            return
        if not isinstance(game, Mapping) or game.get("enabled") is not True:
            await self._stop_owned(state)
            self._set_state(state, "disabled")
            state.session = None
            state.retry_at = None
            return
        validated_game = validate_game_config(game)
        if validated_game is None:
            await self._stop_owned(state)
            self._set_state(state, "invalid_config", "invalid_config_entry")
            return

        try:
            map_result = self._map_loader(self._games_map_path)
        except Exception:
            map_result = None
        diagnostic = getattr(map_result, "diagnostic", None)
        if diagnostic is not None:
            await self._stop_owned(state)
            self._set_state(state, "invalid_config", getattr(diagnostic, "code", "games_map_unreadable"))
            return
        entry = map_result.entry_for(identity) if map_result is not None else None
        if entry is None:
            await self._stop_owned(state)
            self._set_state(state, "waiting_for_game", "games_map_identity_missing")
            return

        prefix = validated_game.get("prefixOverride") or default_prefix_for(identity, self._home)
        try:
            discovery: DiscoveryResult = self._process_discoverer.discover(identity, entry.executable, prefix)
        except Exception:
            discovery = DiscoveryResult("waiting_for_game", diagnostic="proc_unreadable")
        if discovery.state == "ambiguous":
            await self._stop_owned(state)
            self._set_state(state, "ambiguous", discovery.diagnostic or "multiple_game_sessions")
            return
        if discovery.state == "invalid_config":
            await self._stop_owned(state)
            self._set_state(state, "invalid_config", discovery.diagnostic or "invalid_process_environment")
            return
        if discovery.state != "session" or discovery.session is None:
            await self._stop_owned(state)
            self._set_state(state, "waiting_for_game", discovery.diagnostic)
            return

        if state.session != discovery.session:
            previous_state = state.state
            await self._stop_owned(state)
            state.session = discovery.session
            state.retry_at = None
            state.automatic_retries = 0
            state.diagnostic = None
            if previous_state in {"failed", "retrying", "launching", "running"}:
                state.state = "waiting_for_game"
        if state.handle is None and state.state == "failed" and not force_retry:
            return
        now = self._clock()
        if state.handle is not None:
            try:
                exit_code = await self._maybe_await(self._runner.poll(state.handle))
            except Exception:
                exit_code = 1
            if exit_code is None:
                if state.launched_at is not None and now - state.launched_at >= 3.0:
                    self._set_state(state, "running")
                else:
                    self._set_state(state, "launching")
                return
            handle = state.handle
            launched_at = state.launched_at
            state.handle = None
            state.launched_at = None
            await self._discard_exited(handle)
            elapsed = now - (launched_at if launched_at is not None else now)
            if elapsed < 3.0 and state.automatic_retries < 1:
                state.automatic_retries += 1
                state.retry_at = now + 2.0
                self._set_state(state, "retrying", "trainer_exited")
                return
            self._set_state(state, "failed", "trainer_exited")
            return
        if state.state == "retrying" and not force_retry:
            if state.retry_at is None or now < state.retry_at:
                return
        if force_retry:
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
        for state in self._states.values():
            await self._stop_owned(state)
