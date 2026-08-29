#!/usr/bin/env python

"""Decky entry point for Trainer Relay's Python runtime."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Mapping

import decky  # type: ignore
from settings import SettingsManager  # type: ignore

from trainer_relay.config import DEFAULT_CONFIG_KEY, decode_relay_config
from trainer_relay.process import ProcessDiscoverer
from trainer_relay.rpc import RelayRpc
from trainer_relay.runner import OwnedTrainerRunner
from trainer_relay.umu import resolve_umu_run
from trainer_relay.watcher import RelayWatcher


settings_dir = decky.DECKY_PLUGIN_SETTINGS_DIR
logging_dir = decky.DECKY_PLUGIN_LOG_DIR
logger = decky.logger
logger.setLevel(logging.DEBUG)
settings = SettingsManager(name="settings", settings_directory=settings_dir)
settings.read()

_watcher: RelayWatcher | None = None
_watcher_task: asyncio.Task[Any] | None = None
_rpc: RelayRpc | None = None


def _current_config() -> dict[str, Any]:
    value = settings.getSetting(DEFAULT_CONFIG_KEY, {"schemaVersion": 1, "games": {}})
    return decode_relay_config(value)


def _build_watcher() -> RelayWatcher:
    home = getattr(decky, "HOME", os.environ.get("HOME", "/home/deck"))
    plugin_log = getattr(decky, "DECKY_PLUGIN_LOG", os.path.join(logging_dir, "trainer-relay.log"))
    umu_run = lambda: resolve_umu_run(home)
    runner = OwnedTrainerRunner(umu_run, log_path=plugin_log)
    return RelayWatcher(
        _current_config(),
        games_map_path=os.path.join(home, ".local", "share", "unifideck", "games.map"),
        process_discoverer=ProcessDiscoverer(),
        umu_resolver=umu_run,
        runner=runner,
        home=home,
    )


def _service() -> RelayRpc:
    global _rpc, _watcher
    if _watcher is None:
        _watcher = _build_watcher()
    if _rpc is None:
        _rpc = RelayRpc(settings, _watcher)
    return _rpc


class Plugin:
    @classmethod
    async def _main(cls) -> None:
        global _watcher, _watcher_task
        if _watcher is None:
            _watcher = _build_watcher()
        if _watcher_task is None or _watcher_task.done():
            _watcher_task = asyncio.create_task(_watcher.run())

    @classmethod
    async def _unload(cls) -> None:
        global _watcher, _watcher_task, _rpc
        watcher = _watcher
        task = _watcher_task
        _watcher_task = None
        _rpc = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if watcher is not None:
            await watcher.stop()
        _watcher = None

    @classmethod
    async def _uninstall(cls) -> None:
        await cls._unload()

    @classmethod
    async def get_relay_config(cls) -> dict[str, Any]:
        return await _service().get_relay_config()

    @classmethod
    async def set_relay_game_config(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        return await _service().set_relay_game_config(data)

    @classmethod
    async def get_relay_status(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        return await _service().get_relay_status(data)

    @classmethod
    async def retry_relay(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        return await _service().retry_relay(data)

    @classmethod
    async def get_env(cls, env: str) -> Any:
        return getattr(decky, env)
