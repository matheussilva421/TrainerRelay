import asyncio
import tempfile
import unittest
from pathlib import Path

from trainer_relay.games_map import GamesMapDiagnostic, GamesMapEntry, GamesMapResult
from trainer_relay.process import CandidateDecision, DiscoveryResult, SessionIdentity
from trainer_relay.runner import StopResult
from trainer_relay.umu import UmuResolution
from trainer_relay.watcher import RelayWatcher


class FakeRunner:
    def __init__(self):
        self.handles = []
        self.spawn_calls = []
        self.stop_calls = []

    def spawn(self, session, trainer_executable, environment):
        handle = {"session": session, "exit_code": None, "process_group_id": 999}
        self.handles.append(handle)
        self.spawn_calls.append((session, trainer_executable, environment))
        return handle

    def poll(self, handle):
        return handle["exit_code"]

    def stop(self, handle):
        self.stop_calls.append(handle)
        return StopResult(forced=False)


class FakeRecorder:
    def __init__(self):
        self.calls = []

    def record(self, category, event, outcome, **kwargs):
        self.calls.append({"category": category, "event": event, "outcome": outcome, **kwargs})

    def flush(self):
        return None


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
            decisions=(
                CandidateDecision(
                    10,
                    20,
                    True,
                    True,
                    "candidate_accepted",
                    {
                        "expected_executable": "/games/game.exe",
                        "observed_executable": "/games/game.exe",
                        "expected_prefix": str(self.prefix),
                        "observed_prefix": str(self.prefix),
                        "game_id": "game",
                        "store": "gog",
                        "wineprefix": str(self.prefix),
                        "protonpath": "/proton",
                    },
                    self.session,
                ),
            ),
        )
        self.clock_value = 0.0
        self.runner = FakeRunner()
        self.recorder = FakeRecorder()
        self.discoverer = FakeDiscoverer(self.discovery)
        self.watcher = RelayWatcher(
            {"schemaVersion": 1, "games": {self.identity: {"enabled": True, "trainerPath": str(self.trainer)}}},
            games_map_path="/games.map",
            map_loader=lambda _: self.map_result,
            process_discoverer=self.discoverer,
            umu_resolver=lambda: UmuResolution(Path("/umu-run"), "bundled"),
            runner=self.runner,
            diagnostics=self.recorder,
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
        self.assertEqual(
            [call["event"] for call in self.recorder.calls],
            [
                "games_map_loaded",
                "prefix_selected",
                "process_scan_summary",
                "candidate_accepted",
                "umu_resolved",
                "trainer_spawned",
                "games_map_loaded",
                "prefix_selected",
                "process_scan_summary",
                "candidate_accepted",
                "trainer_running",
            ],
        )
        self.assertEqual(self.recorder.calls[3]["session"].to_wire(), {"pid": 10, "startTime": 20})

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
        events = [call["event"] for call in self.recorder.calls]
        self.assertIn("trainer_exited", events)
        self.assertIn("trainer_retry_scheduled", events)

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
        self.assertIn("trainer_manual_retry", [call["event"] for call in self.recorder.calls])

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
        self.assertIn("session_changed", [call["event"] for call in self.recorder.calls])

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
        signals = [call for call in self.recorder.calls if call["event"] == "owned_group_signal"]
        self.assertEqual(signals[0]["details"], {"process_group_id": 999, "signal": "SIGTERM", "forced": False})

    async def test_game_end_records_session_end_and_stops_owned_sidecar(self):
        await self.watcher.poll_once()
        self.discoverer.result = DiscoveryResult("waiting_for_game")

        await self.watcher.poll_once()

        self.assertIn("session_ended", [call["event"] for call in self.recorder.calls])
        self.assertEqual(self.runner.stop_calls, [self.runner.handles[0]])

    async def test_spawn_failure_records_bounded_reason(self):
        def fail_spawn(*_args):
            raise OSError("private filesystem message")

        self.runner.spawn = fail_spawn
        await self.watcher.poll_once()
        failures = [call for call in self.recorder.calls if call["event"] == "trainer_spawn_failed"]
        self.assertEqual(failures[0]["details"]["reason"], "trainer_spawn_failed")
        self.assertNotIn("private filesystem message", str(failures))

    async def test_spawn_failure_never_treats_trainer_prefixed_exception_text_as_a_code(self):
        private_marker = "trainer_privatecredentialvalue"
        self.runner.spawn = lambda *_: (_ for _ in ()).throw(RuntimeError(private_marker))

        await self.watcher.poll_once()

        failures = [call for call in self.recorder.calls if call["event"] == "trainer_spawn_failed"]
        self.assertEqual(failures[0]["details"]["reason"], "trainer_spawn_failed")
        self.assertEqual(self.watcher.status(self.identity)["diagnostic"], {"code": "trainer_spawn_failed"})
        self.assertNotIn(private_marker, str(failures))

    async def test_malformed_map_and_ambiguous_umu_record_safe_reasons(self):
        self.watcher._map_loader = lambda _: GamesMapResult({}, GamesMapDiagnostic("games_map_malformed", 7))
        await self.watcher.poll_once()
        rejected = [call for call in self.recorder.calls if call["event"] == "games_map_rejected"]
        self.assertEqual(rejected[-1]["details"]["reason"], "games_map_malformed")

        self.watcher._map_loader = lambda _: self.map_result
        self.watcher._umu_resolver = lambda: (_ for _ in ()).throw(RuntimeError("umu_ambiguous"))
        await self.watcher.poll_once()
        umu = [call for call in self.recorder.calls if call["event"] == "umu_rejected"]
        self.assertEqual(umu[-1]["details"], {"reason": "umu_ambiguous"})

    async def test_forced_shutdown_records_sigterm_and_sigkill(self):
        self.runner.stop = lambda handle: (self.runner.stop_calls.append(handle) or StopResult(forced=True))
        await self.watcher.poll_once()
        await self.watcher.stop()
        signals = [call["details"] for call in self.recorder.calls if call["event"] == "owned_group_signal"]
        self.assertEqual(
            signals,
            [
                {"process_group_id": 999, "signal": "SIGTERM", "forced": False},
                {"process_group_id": 999, "signal": "SIGKILL", "forced": True},
            ],
        )


if __name__ == "__main__":
    unittest.main()
