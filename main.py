#!/usr/bin/env python

"""Decky entry point for Trainer Relay's Python runtime."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Mapping

import decky  # type: ignore
from settings import SettingsManager  # type: ignore

from trainer_relay.config import DEFAULT_CONFIG_KEY, decode_relay_config
from trainer_relay.diagnostic_settings import DIAGNOSTIC_SETTINGS_KEY, decode_diagnostic_settings
from trainer_relay.diagnostics import DiagnosticRecorder
from trainer_relay.process import ProcessDiscoverer
from trainer_relay.rpc import RelayRpc
from trainer_relay.runner import OwnedTrainerRunner
from trainer_relay.umu import resolve_umu_run, resolve_umu_run_details
from trainer_relay.watcher import RelayWatcher


settings_dir = decky.DECKY_PLUGIN_SETTINGS_DIR
logger = decky.logger
logger.setLevel(logging.DEBUG)
settings = SettingsManager(name="settings", settings_directory=settings_dir)
settings.read()

_watcher: RelayWatcher | None = None
_watcher_task: asyncio.Task[Any] | None = None
_rpc: RelayRpc | None = None
_diagnostics: DiagnosticRecorder | None = None

PLUGIN_VERSION = "0.1.0-experimental.19"


def _host_user_home() -> str:
    return getattr(
        decky,
        "DECKY_USER_HOME",
        getattr(decky, "HOME", os.environ.get("HOME", "/home/deck")),
    )


def _current_config() -> dict[str, Any]:
    value = settings.getSetting(DEFAULT_CONFIG_KEY, {"schemaVersion": 1, "games": {}})
    return decode_relay_config(value)


def _current_diagnostic_settings() -> dict[str, Any]:
    value = settings.getSetting(DIAGNOSTIC_SETTINGS_KEY, {"schemaVersion": 1, "enabled": False})
    return decode_diagnostic_settings(value)


def _ensure_diagnostics() -> DiagnosticRecorder:
    global _diagnostics
    if _diagnostics is None:
        diagnostic_settings = _current_diagnostic_settings()
        _diagnostics = DiagnosticRecorder(Path(settings_dir) / "diagnostics", enabled=diagnostic_settings["enabled"])
    return _diagnostics


def _build_watcher() -> RelayWatcher:
    home = _host_user_home()
    umu_path = lambda: resolve_umu_run(home)
    runner = OwnedTrainerRunner(umu_path)
    return RelayWatcher(
        _current_config(),
        games_map_path=os.path.join(home, ".local", "share", "unifideck", "games.map"),
        process_discoverer=ProcessDiscoverer(),
        umu_resolver=lambda: resolve_umu_run_details(home),
        runner=runner,
        home=home,
        diagnostics=_ensure_diagnostics(),
    )


def _service() -> RelayRpc:
    global _rpc, _watcher
    if _watcher is None:
        _watcher = _build_watcher()
    if _rpc is None:
        home = _host_user_home()
        _rpc = RelayRpc(
            settings,
            _watcher,
            _ensure_diagnostics(),
            downloads_dir=Path(home) / "Downloads",
            plugin_version=PLUGIN_VERSION,
        )
    return _rpc


class Plugin:
    @classmethod
    async def _main(cls) -> None:
        global _watcher, _watcher_task
        if _watcher is None:
            _watcher = _build_watcher()
        if _watcher_task is None or _watcher_task.done():
            _ensure_diagnostics().record(
                "lifecycle",
                "plugin_loaded",
                "info",
                details={"version": PLUGIN_VERSION},
            )
            _watcher_task = asyncio.create_task(_watcher.run())

    @classmethod
    async def _unload(cls) -> None:
        global _watcher, _watcher_task, _rpc, _diagnostics
        watcher = _watcher
        task = _watcher_task
        diagnostics = _diagnostics
        _watcher_task = None
        _rpc = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if watcher is not None:
            try:
                await watcher.stop()
            except (OSError, RuntimeError, ValueError):
                pass
        if diagnostics is not None:
            try:
                diagnostics.record(
                    "lifecycle",
                    "plugin_unloaded",
                    "info",
                    details={"version": PLUGIN_VERSION},
                )
            except (OSError, ValueError):
                pass
            diagnostics.flush()
        _watcher = None
        _diagnostics = None

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
    async def get_diagnostic_settings(cls) -> dict[str, Any]:
        return await _service().get_diagnostic_settings()

    @classmethod
    async def set_diagnostics_enabled(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        return await _service().set_diagnostics_enabled(data)

    @classmethod
    async def get_diagnostic_events(cls, data: Mapping[str, Any]) -> dict[str, Any]:
        return await _service().get_diagnostic_events(data)

    @classmethod
    async def export_diagnostics(cls) -> dict[str, Any]:
        return await _service().export_diagnostics()

    @classmethod
    async def clear_diagnostics(cls) -> dict[str, Any]:
        return await _service().clear_diagnostics()

    @classmethod
    async def get_env(cls, env: str) -> Any:
        return getattr(decky, env)
