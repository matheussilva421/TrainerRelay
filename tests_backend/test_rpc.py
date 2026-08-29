import tempfile
import unittest
from pathlib import Path

from trainer_relay.rpc import RelayRpc, RelayRpcError


class FakeSettings:
    def __init__(self, value):
        self.value = value
        self.set_calls = []
        self.commit_calls = 0

    def getSetting(self, key, default):
        return self.value if key == "RelayConfigV1" else default

    def setSetting(self, key, value):
        self.set_calls.append((key, value))
        self.value = value
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


class RpcTests(unittest.IsolatedAsyncioTestCase):
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


if __name__ == "__main__":
    unittest.main()
