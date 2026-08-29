import asyncio
import tempfile
import unittest
from pathlib import Path

from trainer_relay.games_map import GamesMapEntry, GamesMapResult
from trainer_relay.process import DiscoveryResult, SessionIdentity
from trainer_relay.watcher import RelayWatcher


class FakeRunner:
    def __init__(self):
        self.handles = []
        self.spawn_calls = []
        self.stop_calls = []

    def spawn(self, session, trainer_executable, environment):
        handle = {"session": session, "exit_code": None}
        self.handles.append(handle)
        self.spawn_calls.append((session, trainer_executable, environment))
        return handle

    def poll(self, handle):
        return handle["exit_code"]

    def stop(self, handle):
        self.stop_calls.append(handle)


class FakeDiscoverer:
    def __init__(self, result):
        self.result = result

    def discover(self, identity, executable, prefix):
        return self.result


class WatcherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.trainer = root / "trainer.exe"
        self.trainer.write_text("trainer", encoding="utf-8")
        self.prefix = root / "prefix"
        self.prefix.mkdir()
        self.identity = "gog:game"
        self.entry = GamesMapEntry(self.identity, "/games/game.exe")
        self.map_result = GamesMapResult({self.identity: self.entry})
        self.session = SessionIdentity(10, 20)
        self.discovery = DiscoveryResult(
            "session",
            session=self.session,
            environment={
                "WINEPREFIX": str(self.prefix),
                "PROTONPATH": "/proton",
                "GAMEID": "game",
                "STORE": "gog",
            },
        )
        self.clock_value = 0.0
        self.runner = FakeRunner()
        self.discoverer = FakeDiscoverer(self.discovery)
        self.watcher = RelayWatcher(
            {"schemaVersion": 1, "games": {self.identity: {"enabled": True, "trainerPath": str(self.trainer)}}},
            games_map_path="/games.map",
            map_loader=lambda _: self.map_result,
            process_discoverer=self.discoverer,
            umu_resolver=lambda: "/umu-run",
            runner=self.runner,
            home="/home/deck",
            clock=lambda: self.clock_value,
        )

    async def asyncTearDown(self):
        self.directory.cleanup()

    async def test_launch_becomes_running_after_three_seconds(self):
        await self.watcher.poll_once()
        self.assertEqual(self.watcher.status(self.identity)["state"], "launching")
        self.clock_value = 3.0
        await self.watcher.poll_once()
        self.assertEqual(self.watcher.status(self.identity)["state"], "running")
        self.assertEqual(len(self.runner.spawn_calls), 1)

    async def test_first_premature_exit_retries_once_after_two_seconds(self):
        await self.watcher.poll_once()
        self.runner.handles[0]["exit_code"] = 1
        self.clock_value = 1.0
        await self.watcher.poll_once()
        self.assertEqual(self.watcher.status(self.identity)["state"], "retrying")
        self.clock_value = 2.9
        await self.watcher.poll_once()
        self.assertEqual(len(self.runner.spawn_calls), 1)
        self.clock_value = 3.0
        await self.watcher.poll_once()
        self.assertEqual(len(self.runner.spawn_calls), 2)

    async def test_second_premature_exit_fails_until_manual_retry(self):
        await self.watcher.poll_once()
        self.runner.handles[0]["exit_code"] = 1
        self.clock_value = 1.0
        await self.watcher.poll_once()
        self.clock_value = 3.0
        await self.watcher.poll_once()
        self.runner.handles[1]["exit_code"] = 2
        self.clock_value = 4.0
        await self.watcher.poll_once()
        self.assertEqual(self.watcher.status(self.identity)["state"], "failed")
        await self.watcher.retry(self.identity)
        self.assertEqual(len(self.runner.spawn_calls), 3)
        self.assertEqual(self.watcher.status(self.identity)["state"], "launching")

    async def test_new_game_session_resets_previous_retry_state_and_launches(self):
        await self.watcher.poll_once()
        self.runner.handles[0]["exit_code"] = 1
        self.clock_value = 1.0
        await self.watcher.poll_once()
        self.discoverer.result = DiscoveryResult(
            "session",
            session=SessionIdentity(11, 21),
            environment=self.discovery.environment,
        )
        self.clock_value = 1.5
        await self.watcher.poll_once()
        self.assertEqual(len(self.runner.spawn_calls), 2)
        self.assertEqual(self.runner.spawn_calls[1][0], SessionIdentity(11, 21))
        self.assertEqual(self.watcher.status(self.identity)["state"], "launching")

    async def test_ambiguity_after_launch_stops_owned_sidecar(self):
        await self.watcher.poll_once()
        self.discoverer.result = DiscoveryResult("ambiguous", candidates=(self.session, SessionIdentity(11, 21)))
        self.clock_value = 1.0
        await self.watcher.poll_once()
        self.assertEqual(self.watcher.status(self.identity)["state"], "ambiguous")
        self.assertEqual(self.runner.stop_calls, [self.runner.handles[0]])

    async def test_disabled_or_invalid_configuration_never_spawns(self):
        disabled = RelayWatcher(
            {"schemaVersion": 1, "games": {self.identity: {"enabled": False, "trainerPath": str(self.trainer)}}},
            games_map_path="/games.map",
            map_loader=lambda _: self.map_result,
            process_discoverer=self.discoverer,
            umu_resolver=lambda: "/umu-run",
            runner=self.runner,
            home="/home/deck",
        )
        await disabled.poll_once()
        self.assertEqual(disabled.status(self.identity)["state"], "disabled")
        invalid = RelayWatcher(
            {"schemaVersion": 1, "games": {self.identity: {"enabled": True, "trainerPath": "/missing.exe"}}},
            games_map_path="/games.map",
            map_loader=lambda _: self.map_result,
            process_discoverer=self.discoverer,
            umu_resolver=lambda: "/umu-run",
            runner=self.runner,
            home="/home/deck",
        )
        await invalid.poll_once()
        self.assertEqual(invalid.status(self.identity)["state"], "invalid_config")
        self.assertEqual(len(self.runner.spawn_calls), 0)

    async def test_missing_umu_resolution_is_diagnostic_and_never_spawns(self):
        self.watcher._umu_resolver = lambda: None
        await self.watcher.poll_once()
        self.assertEqual(self.watcher.status(self.identity)["state"], "invalid_config")
        self.assertEqual(self.watcher.status(self.identity)["diagnostic"], {"code": "umu_not_found"})
        self.assertEqual(len(self.runner.spawn_calls), 0)

    async def test_unload_stops_every_active_owned_sidecar(self):
        await self.watcher.poll_once()
        await self.watcher.stop()
        self.assertEqual(self.runner.stop_calls, [self.runner.handles[0]])


if __name__ == "__main__":
    unittest.main()
