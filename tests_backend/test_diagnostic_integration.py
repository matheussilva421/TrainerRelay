import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trainer_relay.diagnostics import DiagnosticRecorder
from trainer_relay.games_map import GamesMapEntry, GamesMapResult
from trainer_relay.process import CandidateDecision, DiscoveryResult
from trainer_relay.watcher import RelayWatcher


class StaticDiscoverer:
    def __init__(self, result):
        self.result = result

    def discover(self, *_args):
        return self.result


class NeverRunner:
    def spawn(self, *_args):
        raise AssertionError("rejected candidates must never spawn")


class DiagnosticIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_name_rejection_reaches_cursor_and_txt_without_private_process_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trainer = root / "trainer.exe"
            trainer.write_text("trainer", encoding="utf-8")
            identity = "gog:game"
            expected_prefix = "/home/deck/.local/share/unifideck/prefixes/game"
            observed_prefix = expected_prefix
            forbidden_value = "DO-NOT-EXPORT-PRIVATE-TOKEN"
            full_argv = "wine /games/game.exe --private-argument"
            decisions = (
                CandidateDecision(
                    321,
                    654,
                    True,
                    False,
                    "process_name_mismatch",
                    {
                        "expected_executable": "/games/game.exe",
                        "observed_executable": "/games/game.exe",
                        "expected_prefix": expected_prefix,
                        "observed_prefix": observed_prefix,
                        "game_id": "game",
                        "process_name": "umu-run",
                        "store": "gog",
                        "wineprefix": observed_prefix,
                        "protonpath": "/home/deck/proton",
                    },
                ),
                CandidateDecision(
                    999,
                    777,
                    False,
                    False,
                    "executable_mismatch",
                    {"observed_executable": "/unrelated/private-process"},
                ),
            )
            discovery = DiscoveryResult(
                "waiting_for_game",
                environment={
                    "API_TOKEN": forbidden_value,
                    "PROTON_REMOTE_DEBUG_CMD": full_argv,
                },
                diagnostic="process_name_mismatch",
                decisions=decisions,
                rejection_counts={"process_name_mismatch": 1, "executable_mismatch": 1},
            )
            recorder = DiagnosticRecorder(
                root / "diagnostics",
                enabled=True,
                wall_clock=lambda: datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
            )
            entry = GamesMapEntry(identity, "/games/game.exe")
            watcher = RelayWatcher(
                {
                    "schemaVersion": 1,
                    "games": {identity: {"enabled": True, "trainerPath": str(trainer)}},
                },
                games_map_path="/home/deck/.local/share/unifideck/games.map",
                map_loader=lambda _: GamesMapResult({identity: entry}),
                process_discoverer=StaticDiscoverer(discovery),
                runner=NeverRunner(),
                home="/home/deck",
                diagnostics=recorder,
            )

            await watcher.poll_once()
            events = recorder.events_after(None, 200)["events"]
            export = recorder.export_text(root / "Downloads", "test")
            combined = repr(events) + Path(export["path"]).read_text(encoding="utf-8")

            self.assertIn("process_name_mismatch", combined)
            self.assertIn("process_name_mismatch_count=1", combined)
            self.assertIn("process_name=umu-run", combined)
            self.assertIn(identity, combined)
            self.assertIn("321", combined)
            self.assertIn("654", combined)
            self.assertIn(expected_prefix, combined)
            self.assertIn(observed_prefix, combined)
            self.assertNotIn(forbidden_value, combined)
            self.assertNotIn("API_TOKEN", combined)
            self.assertNotIn("PROTON_REMOTE_DEBUG_CMD", combined)
            self.assertNotIn(full_argv, combined)
            self.assertNotIn("/unrelated/private-process", combined)


if __name__ == "__main__":
    unittest.main()
