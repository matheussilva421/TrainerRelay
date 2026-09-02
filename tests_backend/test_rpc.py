import tempfile
import unittest
from pathlib import Path

from trainer_relay.rpc import RelayRpc, RelayRpcError


class FakeSettings:
    def __init__(self, value):
        self.values = {"RelayConfigV1": value}
        self.set_calls = []
        self.commit_calls = 0

    def getSetting(self, key, default):
        return self.values.get(key, default)

    def setSetting(self, key, value):
        self.set_calls.append((key, value))
        self.values[key] = value
        return value

    def commit(self):
        self.commit_calls += 1
        return True


class FakeWatcher:
    def __init__(self):
        self.configs = []
        self.retries = []

    async def update_config(self, config):
        self.configs.append(config)

    async def status(self, identity):
        return {"identity": identity, "state": "invalid_config", "diagnostic": {"code": "safe_code"}}

    async def retry(self, identity):
        self.retries.append(identity)
        return await self.status(identity)


class FakeCheatService:
    def __init__(self):
        self.calls = []

    async def get_cheat_controls(self, identity):
        self.calls.append(("get", identity))
        return {
            "identity": identity,
            "status": "ready",
            "trainerSha256": "a" * 64,
            "source": "manual",
            "trainerLabel": "Manual controls",
            "cheats": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "label": "Health",
                    "hotkey": {"modifiers": ["ctrl"], "key": "F1"},
                    "state": "unknown",
                }
            ],
            "capabilities": {"commands": True, "authoritativeState": False, "toggles": False},
            "diagnostic": None,
        }

    async def add_manual_cheat_control(self, request):
        self.calls.append(("add", request))
        return {
            "identity": request["identity"],
            "trainerSha256": request["trainerSha256"],
            "cheat": {
                "id": "11111111-1111-4111-8111-111111111111",
                "label": request["label"].strip(),
                "hotkey": {"modifiers": ["ctrl", "shift"], "key": "F1"},
            },
        }

    async def remove_manual_cheat_control(self, request):
        self.calls.append(("remove", request))
        return {"identity": request["identity"], "cheatId": request["cheatId"], "removed": True}

    async def send_cheat_command(self, request):
        self.calls.append(("send", request))
        return {
            "commandId": "22222222-2222-4222-8222-222222222222",
            "identity": request["identity"],
            "cheatId": request["cheatId"],
            "outcome": "requested",
            "state": "unknown",
            "diagnostic": None,
        }


class FakeDiagnostics:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.set_calls = []
        self.record_calls = []
        self.event_calls = []

    def stats(self):
        return {
            "enabled": self.enabled,
            "bytesUsed": 12,
            "byteLimit": 52_428_800,
            "eventCount": 3,
            "malformedLineCount": 0,
            "storageDiagnostic": None,
            "lastExportPath": "/home/deck/Downloads/previous.txt",
        }

    def set_enabled(self, enabled):
        self.set_calls.append(enabled)
        self.enabled = enabled

    def record(self, *args, **kwargs):
        self.record_calls.append((args, kwargs))

    def events_after(self, cursor, limit):
        self.event_calls.append((cursor, limit))
        return {"generation": 4, "nextCursor": "v1:4:3", "cursorReset": False, "events": []}

    def export_text(self, downloads_dir, plugin_version):
        return {"path": str(downloads_dir / "export.txt"), "bytesWritten": 42}

    def clear(self):
        return self.stats()


class RpcTests(unittest.IsolatedAsyncioTestCase):
    def diagnostic_rpc(self, settings=None, diagnostics=None):
        return RelayRpc(
            settings or FakeSettings(None),
            FakeWatcher(),
            diagnostics or FakeDiagnostics(),
            downloads_dir=Path("/home/deck/Downloads"),
            plugin_version="0.1.0-experimental.13",
        )

    async def test_get_and_set_persist_one_versioned_config_and_notify_watcher(self):
        with tempfile.TemporaryDirectory() as directory:
            trainer = Path(directory) / "trainer.exe"
            trainer.write_text("trainer", encoding="utf-8")
            settings = FakeSettings(None)
            watcher = FakeWatcher()
            rpc = RelayRpc(settings, watcher)
            config = await rpc.set_relay_game_config(
                {"identity": "epic:game", "config": {"enabled": True, "trainerPath": str(trainer)}}
            )
            self.assertEqual(config["schemaVersion"], 1)
            self.assertIn("epic:game", config["games"])
            self.assertEqual(settings.set_calls[0][0], "RelayConfigV1")
            self.assertEqual(settings.commit_calls, 1)
            self.assertEqual(watcher.configs, [config])
            self.assertEqual(await rpc.get_relay_config(), config)

    async def test_null_game_config_removes_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            trainer = Path(directory) / "trainer.exe"
            trainer.write_text("trainer", encoding="utf-8")
            initial = {"schemaVersion": 1, "games": {"gog:game": {"enabled": True, "trainerPath": str(trainer)}}}
            settings = FakeSettings(initial)
            watcher = FakeWatcher()
            rpc = RelayRpc(settings, watcher)
            config = await rpc.set_relay_game_config({"identity": "gog:game", "config": None})
            self.assertEqual(config, {"schemaVersion": 1, "games": {}})

    async def test_rejects_invalid_rpc_data_with_sanitised_code(self):
        rpc = RelayRpc(FakeSettings(None), FakeWatcher())
        for data in ({}, {"identity": "steam:1", "config": None}, {"identity": "epic:1", "config": {"enabled": True}}):
            with self.subTest(data=data):
                with self.assertRaisesRegex(RelayRpcError, "invalid_"):
                    await rpc.set_relay_game_config(data)

    async def test_status_and_retry_preserve_wire_shape_without_environment_values(self):
        watcher = FakeWatcher()
        rpc = RelayRpc(FakeSettings(None), watcher)
        status = await rpc.get_relay_status({"identity": "gog:game"})
        self.assertEqual(status, {"identity": "gog:game", "state": "invalid_config", "diagnostic": {"code": "safe_code"}})
        self.assertNotIn("environment", status)
        retried = await rpc.retry_relay({"identity": "gog:game"})
        self.assertEqual(retried, status)
        self.assertEqual(watcher.retries, ["gog:game"])

    async def test_diagnostic_settings_response_and_persist_before_recorder_change(self):
        settings = FakeSettings(None)
        diagnostics = FakeDiagnostics()
        rpc = self.diagnostic_rpc(settings, diagnostics)

        initial = await rpc.get_diagnostic_settings()
        self.assertEqual(
            initial,
            {
                "settings": {"schemaVersion": 1, "enabled": False},
                "bytesUsed": 12,
                "byteLimit": 52_428_800,
                "eventCount": 3,
                "storageDiagnostic": None,
                "lastExportPath": "/home/deck/Downloads/previous.txt",
            },
        )

        original_set_enabled = diagnostics.set_enabled

        def assert_committed(enabled):
            self.assertEqual(settings.commit_calls, 1)
            self.assertEqual(settings.set_calls[-1][0], "diagnostic_settings_v1")
            original_set_enabled(enabled)

        diagnostics.set_enabled = assert_committed
        enabled = await rpc.set_diagnostics_enabled({"enabled": True})
        self.assertTrue(enabled["settings"]["enabled"])
        self.assertTrue(diagnostics.enabled)

    async def test_diagnostic_inputs_are_strict_and_cursor_limit_are_forwarded(self):
        diagnostics = FakeDiagnostics()
        rpc = self.diagnostic_rpc(diagnostics=diagnostics)
        for data in ({}, {"enabled": 1}, {"enabled": "true"}, None):
            with self.subTest(data=data):
                with self.assertRaisesRegex(RelayRpcError, "invalid_request"):
                    await rpc.set_diagnostics_enabled(data)
        for data in ({"cursor": 1}, {"limit": True}, {"extra": 1}, None):
            with self.subTest(data=data):
                with self.assertRaisesRegex(RelayRpcError, "invalid_request"):
                    await rpc.get_diagnostic_events(data)

        response = await rpc.get_diagnostic_events({"cursor": "v1:4:2", "limit": 20})
        self.assertEqual(response["generation"], 4)
        self.assertEqual(diagnostics.event_calls, [("v1:4:2", 20)])

    async def test_diagnostic_export_clear_and_failures_use_bounded_codes(self):
        diagnostics = FakeDiagnostics()
        rpc = self.diagnostic_rpc(diagnostics=diagnostics)
        self.assertEqual(
            await rpc.export_diagnostics(),
            {"path": str(Path("/home/deck/Downloads/export.txt")), "bytesWritten": 42},
        )
        cleared = await rpc.clear_diagnostics()
        self.assertEqual(cleared["generation"], 4)
        self.assertEqual(cleared["settings"]["enabled"], False)

        diagnostics.export_text = lambda *_: (_ for _ in ()).throw(OSError("private disk path"))
        with self.assertRaisesRegex(RelayRpcError, "diagnostic_export_failed") as raised:
            await rpc.export_diagnostics()
        self.assertNotIn("private disk path", str(raised.exception))

    async def test_cheat_rpcs_require_exact_requests_and_decode_safe_responses(self):
        service = FakeCheatService()
        rpc = RelayRpc(FakeSettings(None), FakeWatcher(), cheat_service=service)

        controls = await rpc.get_cheat_controls({"identity": "gog:game"})
        self.assertEqual(controls["status"], "ready")
        added = await rpc.add_manual_cheat_control(
            {
                "identity": "gog:game",
                "trainerSha256": "a" * 64,
                "label": " Health ",
                "hotkey": {"modifiers": ["shift", "ctrl"], "key": "F1"},
            }
        )
        self.assertEqual(added["cheat"]["label"], "Health")
        self.assertEqual(
            await rpc.remove_manual_cheat_control(
                {"identity": "gog:game", "cheatId": "11111111-1111-4111-8111-111111111111"}
            ),
            {"identity": "gog:game", "cheatId": "11111111-1111-4111-8111-111111111111", "removed": True},
        )
        self.assertEqual(
            (await rpc.send_cheat_command({"identity": "gog:game", "cheatId": "health"}))["state"],
            "unknown",
        )
        for method, data in (
            (rpc.get_cheat_controls, {"identity": "gog:game", "extra": 1}),
            (
                rpc.add_manual_cheat_control,
                {
                    "identity": "gog:game",
                    "trainerSha256": "a" * 64,
                    "label": "x",
                    "hotkey": {"modifiers": [], "key": "F1"},
                    "extra": 1,
                },
            ),
            (rpc.remove_manual_cheat_control, {"identity": "gog:game", "cheatId": "health", "extra": 1}),
            (rpc.send_cheat_command, {"identity": "gog:game", "cheatId": "health", "extra": 1}),
        ):
            with self.subTest(data=data):
                with self.assertRaisesRegex(RelayRpcError, "invalid_request"):
                    await method(data)

    async def test_cheat_rpc_sanitizes_malformed_service_response_and_exception(self):
        class Unsafe:
            async def get_cheat_controls(self, _identity):
                raise RuntimeError("/private/trainer.exe secret-token")

            async def send_cheat_command(self, _request):
                return {
                    "commandId": "not-a-command",
                    "identity": "gog:game",
                    "cheatId": "health",
                    "outcome": "requested",
                    "state": "enabled",
                    "diagnostic": None,
                }

        rpc = RelayRpc(FakeSettings(None), FakeWatcher(), cheat_service=Unsafe())
        with self.assertRaisesRegex(RelayRpcError, "cheat_service_failed") as raised:
            await rpc.get_cheat_controls({"identity": "gog:game"})
        self.assertNotIn("trainer.exe", str(raised.exception))
        with self.assertRaisesRegex(RelayRpcError, "invalid_cheat_response") as raised:
            await rpc.send_cheat_command({"identity": "gog:game", "cheatId": "health"})
        self.assertNotIn("not-a-command", str(raised.exception))

    async def test_cooperative_control_response_may_omit_a_hotkey(self):
        class CooperativeService:
            async def get_cheat_controls(self, identity):
                return {
                    "identity": identity,
                    "status": "ready",
                    "trainerSha256": "a" * 64,
                    "source": "cooperative",
                    "trainerLabel": "Owned trainer",
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "disabled", "authoritative": True}],
                    "capabilities": {"commands": True, "authoritativeState": True, "toggles": True},
                    "diagnostic": None,
                }

        rpc = RelayRpc(FakeSettings(None), FakeWatcher(), cheat_service=CooperativeService())
        response = await rpc.get_cheat_controls({"identity": "gog:game"})
        self.assertEqual(response["cheats"][0]["state"], "disabled")

    async def test_cheat_rpc_rejects_overlong_diagnostic_codes(self):
        class Unsafe:
            async def get_cheat_controls(self, identity):
                return {
                    "identity": identity,
                    "status": "unavailable",
                    "diagnostic": {"code": "a" * 65},
                }

        rpc = RelayRpc(FakeSettings(None), FakeWatcher(), cheat_service=Unsafe())
        with self.assertRaisesRegex(RelayRpcError, "invalid_cheat_response"):
            await rpc.get_cheat_controls({"identity": "gog:game"})

    async def test_cheat_rpc_rejects_authority_claims_outside_cooperative_state(self):
        class Unsafe:
            async def get_cheat_controls(self, identity):
                return {
                    "identity": identity,
                    "status": "ready",
                    "trainerSha256": "a" * 64,
                    "source": "manual",
                    "trainerLabel": "Manual controls",
                    "cheats": [
                        {
                            "id": "manual",
                            "label": "Manual",
                            "hotkey": {"modifiers": [], "key": "F1"},
                            "state": "unknown",
                            "authoritative": True,
                        }
                    ],
                    "capabilities": {"commands": True, "authoritativeState": False, "toggles": False},
                    "diagnostic": None,
                }

            async def send_cheat_command(self, _request):
                return {
                    "commandId": "11111111-1111-4111-8111-111111111111",
                    "identity": "gog:game",
                    "cheatId": "health",
                    "outcome": "failed",
                    "state": "enabled",
                    "diagnostic": {"code": "helper_exit_nonzero"},
                }

        rpc = RelayRpc(FakeSettings(None), FakeWatcher(), cheat_service=Unsafe())
        with self.assertRaisesRegex(RelayRpcError, "invalid_cheat_response"):
            await rpc.get_cheat_controls({"identity": "gog:game"})
        with self.assertRaisesRegex(RelayRpcError, "invalid_cheat_response"):
            await rpc.send_cheat_command({"identity": "gog:game", "cheatId": "health"})

    async def test_cooperative_enabled_state_requires_explicit_authority(self):
        class Unsafe:
            async def get_cheat_controls(self, identity):
                return {
                    "identity": identity,
                    "status": "ready",
                    "trainerSha256": "a" * 64,
                    "source": "cooperative",
                    "trainerLabel": "Owned trainer",
                    "cheats": [{"id": "health", "label": "Health", "state": "enabled"}],
                    "capabilities": {"commands": True, "authoritativeState": True, "toggles": True},
                    "diagnostic": None,
                }

        rpc = RelayRpc(FakeSettings(None), FakeWatcher(), cheat_service=Unsafe())
        with self.assertRaisesRegex(RelayRpcError, "invalid_cheat_response"):
            await rpc.get_cheat_controls({"identity": "gog:game"})

    async def test_cooperative_toggles_require_authoritative_state_capability(self):
        class Unsafe:
            async def get_cheat_controls(self, identity):
                return {
                    "identity": identity,
                    "status": "ready",
                    "trainerSha256": "a" * 64,
                    "source": "cooperative",
                    "trainerLabel": "Owned trainer",
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                    "capabilities": {"commands": True, "authoritativeState": False, "toggles": True},
                    "diagnostic": None,
                }

        rpc = RelayRpc(FakeSettings(None), FakeWatcher(), cheat_service=Unsafe())
        with self.assertRaisesRegex(RelayRpcError, "invalid_cheat_response"):
            await rpc.get_cheat_controls({"identity": "gog:game"})

    async def test_cheat_rpc_maps_unknown_service_exception_codes_to_generic_code(self):
        class Unsafe:
            async def get_cheat_controls(self, _identity):
                from trainer_relay.cheat_service import CheatServiceError

                raise CheatServiceError("private_internal_code")

        rpc = RelayRpc(FakeSettings(None), FakeWatcher(), cheat_service=Unsafe())
        with self.assertRaisesRegex(RelayRpcError, "cheat_service_failed"):
            await rpc.get_cheat_controls({"identity": "gog:game"})


if __name__ == "__main__":
    unittest.main()
