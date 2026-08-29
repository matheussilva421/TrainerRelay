import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class FakeSettings:
    def __init__(self):
        self.values = {"RelayConfigV1": {"schemaVersion": 1, "games": {}}}
        self.read_calls = 0
        self.commit_calls = 0

    def read(self):
        self.read_calls += 1
        return self.values

    def commit(self):
        self.commit_calls += 1
        return True

    def getSetting(self, key, default):
        return self.values.get(key, default)

    def setSetting(self, key, value):
        self.values[key] = value
        return value


class FakeWatcher:
    def __init__(self, config, **kwargs):
        self.config = config
        self.stop_calls = 0
        self.run_calls = 0

    async def run(self):
        self.run_calls += 1
        await asyncio.sleep(3600)

    async def stop(self):
        self.stop_calls += 1

    def status(self, identity):
        return {"identity": identity, "state": "invalid_config", "diagnostic": {"code": "status_unavailable"}}

    async def update_config(self, config):
        self.config = config

    async def retry(self, identity):
        return self.status(identity)


class MainWiringTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.settings = FakeSettings()
        decky = types.ModuleType("decky")
        decky.DECKY_PLUGIN_SETTINGS_DIR = "/settings"
        decky.DECKY_PLUGIN_LOG_DIR = "/logs"
        decky.DECKY_PLUGIN_DIR = "/plugin"
        decky.logger = types.SimpleNamespace(setLevel=lambda *_: None, info=lambda *_: None)
        settings_module = types.ModuleType("settings")
        settings_module.SettingsManager = lambda **_: self.settings
        self.original_decky = sys.modules.get("decky")
        self.original_settings = sys.modules.get("settings")
        sys.modules["decky"] = decky
        sys.modules["settings"] = settings_module
        sys.modules.pop("main", None)
        self.main = importlib.import_module("main")

    async def asyncTearDown(self):
        if self.main._watcher_task is not None:
            self.main._watcher_task.cancel()
            try:
                await self.main._watcher_task
            except asyncio.CancelledError:
                pass
        if self.original_decky is None:
            sys.modules.pop("decky", None)
        else:
            sys.modules["decky"] = self.original_decky
        if self.original_settings is None:
            sys.modules.pop("settings", None)
        else:
            sys.modules["settings"] = self.original_settings
        sys.modules.pop("main", None)

    async def test_main_starts_one_watcher_task_and_exposes_typed_rpcs(self):
        watcher = FakeWatcher({})
        with patch.object(self.main, "RelayWatcher", return_value=watcher), patch.object(self.main, "OwnedTrainerRunner", return_value=object()), patch.object(
            self.main, "resolve_umu_run", return_value="/umu-run"
        ):
            await self.main.Plugin._main()
            first_task = self.main._watcher_task
            await self.main.Plugin._main()
            self.assertIs(self.main._watcher_task, first_task)
            self.assertEqual(await self.main.Plugin.get_relay_config(), {"schemaVersion": 1, "games": {}})
            self.assertEqual(await self.main.Plugin.get_relay_status({"identity": "gog:game"}), {
                "identity": "gog:game",
                "state": "invalid_config",
                "diagnostic": {"code": "status_unavailable"},
            })

    async def test_unload_cancels_task_and_stops_owned_watcher(self):
        watcher = FakeWatcher({})
        with patch.object(self.main, "RelayWatcher", return_value=watcher), patch.object(self.main, "OwnedTrainerRunner", return_value=object()), patch.object(
            self.main, "resolve_umu_run", return_value="/umu-run"
        ):
            await self.main.Plugin._main()
            await self.main.Plugin._unload()
            self.assertEqual(watcher.stop_calls, 1)
            self.assertIsNone(self.main._watcher_task)


if __name__ == "__main__":
    unittest.main()
