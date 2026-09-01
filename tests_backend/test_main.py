import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
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
        self.kwargs = kwargs

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


class FakeDiagnostics:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.flush_calls = 0
        self.record_calls = []

    def flush(self):
        self.flush_calls += 1

    def record(self, *args, **kwargs):
        self.record_calls.append((args, kwargs))


class FakeDiagnosticRpc:
    def __init__(self):
        self.get_diagnostic_settings = AsyncMock(return_value={"settings": {"schemaVersion": 1, "enabled": True}})
        self.set_diagnostics_enabled = AsyncMock(return_value={"settings": {"schemaVersion": 1, "enabled": True}})
        self.get_diagnostic_events = AsyncMock(return_value={"generation": 1, "events": []})
        self.export_diagnostics = AsyncMock(return_value={"path": "/downloads/export.txt", "bytesWritten": 1})
        self.clear_diagnostics = AsyncMock(return_value={"generation": 2})


class FakeCheatRpc(FakeDiagnosticRpc):
    def __init__(self):
        super().__init__()
        self.get_cheat_controls = AsyncMock(return_value={"status": "unavailable"})
        self.add_manual_cheat_control = AsyncMock(return_value={"saved": True})
        self.remove_manual_cheat_control = AsyncMock(return_value={"removed": True})
        self.send_cheat_command = AsyncMock(return_value={"outcome": "requested", "state": "unknown"})


class MainWiringTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.settings = FakeSettings()
        decky = types.ModuleType("decky")
        decky.DECKY_PLUGIN_SETTINGS_DIR = "/settings"
        decky.DECKY_PLUGIN_LOG_DIR = "/logs"
        decky.DECKY_PLUGIN_DIR = "/plugin"
        decky.HOME = "/root"
        decky.DECKY_USER_HOME = "/home/deck"
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

    async def test_watcher_uses_the_decky_host_user_home_not_the_backend_home(self):
        with (
            patch.object(self.main, "RelayWatcher") as watcher_factory,
            patch.object(self.main, "OwnedTrainerRunner", return_value=object()),
        ):
            self.main._build_watcher()

        self.assertEqual(watcher_factory.call_args.kwargs["home"], "/home/deck")
        self.assertEqual(
            watcher_factory.call_args.kwargs["games_map_path"],
            self.main.os.path.join("/home/deck", ".local", "share", "unifideck", "games.map"),
        )

    async def test_unload_cancels_task_and_stops_owned_watcher(self):
        watcher = FakeWatcher({})
        with patch.object(self.main, "RelayWatcher", return_value=watcher), patch.object(self.main, "OwnedTrainerRunner", return_value=object()), patch.object(
            self.main, "resolve_umu_run", return_value="/umu-run"
        ):
            await self.main.Plugin._main()
            await self.main.Plugin._unload()
            self.assertEqual(watcher.stop_calls, 1)
            self.assertIsNone(self.main._watcher_task)

    async def test_main_owns_one_persisted_recorder_shared_by_watcher_and_rpc(self):
        self.settings.values["diagnostic_settings_v1"] = {"schemaVersion": 1, "enabled": True}
        diagnostics = FakeDiagnostics(enabled=True)
        watcher = FakeWatcher({})
        rpc = FakeDiagnosticRpc()
        with (
            patch.object(self.main, "DiagnosticRecorder", return_value=diagnostics) as recorder_factory,
            patch.object(self.main, "RelayWatcher", return_value=watcher) as watcher_factory,
            patch.object(self.main, "RelayRpc", return_value=rpc) as rpc_factory,
            patch.object(self.main, "OwnedTrainerRunner", return_value=object()),
        ):
            await self.main.Plugin._main()
            self.main._service()

        recorder_factory.assert_called_once_with(Path("/settings") / "diagnostics", enabled=True)
        self.assertIs(watcher_factory.call_args.kwargs["diagnostics"], diagnostics)
        self.assertIs(rpc_factory.call_args.args[2], diagnostics)
        self.assertEqual(rpc_factory.call_args.kwargs["downloads_dir"], Path("/home/deck") / "Downloads")
        self.assertEqual(len(diagnostics.record_calls), 1)

    async def test_service_wires_a_dedicated_manifest_checked_one_shot_runner(self):
        watcher = FakeWatcher({})
        diagnostics = FakeDiagnostics(enabled=True)
        with (
            patch.object(self.main, "DiagnosticRecorder", return_value=diagnostics),
            patch.object(self.main, "RelayWatcher", return_value=watcher),
            patch.object(self.main, "OwnedTrainerRunner", return_value=object()),
            patch.object(self.main, "OneShotCommandRunner", return_value=object()) as runner_factory,
            patch.object(self.main, "CheatControlService", return_value=object()) as service_factory,
            patch.object(self.main, "RelayRpc", return_value=FakeDiagnosticRpc()),
        ):
            self.main._service()

        runner_factory.assert_called_once_with(manifest=Path("/plugin") / "bin" / "input-helper-manifest.json")
        self.assertEqual(service_factory.call_args.args[:2], (self.main.settings, watcher))
        self.assertEqual(service_factory.call_args.kwargs["helper_paths"]["x86"], Path("/plugin") / "bin" / "TrainerRelay.InputHelper.x86.exe")
        self.assertEqual(service_factory.call_args.kwargs["helper_paths"]["x64"], Path("/plugin") / "bin" / "TrainerRelay.InputHelper.x64.exe")

    async def test_unload_flushes_once_even_when_watcher_stop_fails(self):
        diagnostics = FakeDiagnostics(enabled=True)
        watcher = FakeWatcher({})
        watcher.stop = AsyncMock(side_effect=OSError("private stop failure"))
        self.main._diagnostics = diagnostics
        self.main._watcher = watcher

        await self.main.Plugin._unload()

        self.assertEqual(diagnostics.flush_calls, 1)
        self.assertIsNone(self.main._diagnostics)

    async def test_plugin_delegates_all_five_diagnostic_rpcs(self):
        rpc = FakeDiagnosticRpc()
        self.main._rpc = rpc

        await self.main.Plugin.get_diagnostic_settings()
        await self.main.Plugin.set_diagnostics_enabled({"enabled": True})
        await self.main.Plugin.get_diagnostic_events({"limit": 20})
        await self.main.Plugin.export_diagnostics()
        await self.main.Plugin.clear_diagnostics()

        rpc.get_diagnostic_settings.assert_awaited_once_with()
        rpc.set_diagnostics_enabled.assert_awaited_once_with({"enabled": True})
        rpc.get_diagnostic_events.assert_awaited_once_with({"limit": 20})
        rpc.export_diagnostics.assert_awaited_once_with()
        rpc.clear_diagnostics.assert_awaited_once_with()

    async def test_plugin_delegates_all_four_cheat_rpcs(self):
        rpc = FakeCheatRpc()
        self.main._rpc = rpc

        await self.main.Plugin.get_cheat_controls({"identity": "gog:game"})
        await self.main.Plugin.add_manual_cheat_control({"identity": "gog:game"})
        await self.main.Plugin.remove_manual_cheat_control({"identity": "gog:game"})
        await self.main.Plugin.send_cheat_command({"identity": "gog:game"})

        rpc.get_cheat_controls.assert_awaited_once_with({"identity": "gog:game"})
        rpc.add_manual_cheat_control.assert_awaited_once_with({"identity": "gog:game"})
        rpc.remove_manual_cheat_control.assert_awaited_once_with({"identity": "gog:game"})
        rpc.send_cheat_command.assert_awaited_once_with({"identity": "gog:game"})


if __name__ == "__main__":
    unittest.main()
