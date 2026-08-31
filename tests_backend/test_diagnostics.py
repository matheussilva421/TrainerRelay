import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from trainer_relay.diagnostics import (
    DiagnosticRecorder,
    DiagnosticSession,
    DiagnosticStorageError,
    DiagnosticValidationError,
)


class MutableClock:
    def __init__(self) -> None:
        self.monotonic = 0.0
        self.wall = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


class DiagnosticRecorderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "diagnostics"
        self.clock = MutableClock()

    def tearDown(self):
        self.directory.cleanup()

    def recorder(self, **kwargs) -> DiagnosticRecorder:
        return DiagnosticRecorder(
            self.root,
            enabled=True,
            clock=lambda: self.clock.monotonic,
            wall_clock=lambda: self.clock.wall,
            **kwargs,
        )

    def read_events(self) -> list[dict]:
        events = []
        for index in range(4, -1, -1):
            path = self.root / f"diagnostics.{index}.ndjson"
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    def test_writes_sanitized_event_with_sequence_timestamp_identity_and_session(self):
        recorder = self.recorder()
        recorder.record(
            "process",
            "candidate_rejected",
            "rejected",
            identity="gog:game",
            session=DiagnosticSession(123, 456),
            details={
                "reason": "prefix_mismatch",
                "expected_prefix": "/expected/pfx",
                "observed_prefix": "/observed/pfx",
            },
        )

        events = self.read_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["sequence"], 1)
        self.assertEqual(events[0]["timestamp"], "2026-08-30T12:00:00.000Z")
        self.assertEqual(events[0]["identity"], "gog:game")
        self.assertEqual(events[0]["session"], {"pid": 123, "startTime": 456})
        self.assertEqual(events[0]["details"]["reason"], "prefix_mismatch")

    def test_writes_only_effective_umu_shape_for_trainer_spawn(self):
        recorder = self.recorder()
        recorder.record(
            "trainer",
            "trainer_spawned",
            "accepted",
            identity="gog:game",
            session=DiagnosticSession(123, 456),
            details={
                "trainer_path": "/games/trainer.exe",
                "process_group_id": 789,
                "wineprefix": "/prefix",
                "steam_compat_data_path": "/prefix",
                "proton_verb": "runinprefix",
                "container_reentry": "enabled",
                "environment_key_count": 5,
                "runtime_flags": "UMU_CONTAINER_NSENTER",
            },
        )

        self.assertEqual(
            self.read_events()[0]["details"],
            {
                "trainer_path": "/games/trainer.exe",
                "process_group_id": 789,
                "wineprefix": "/prefix",
                "steam_compat_data_path": "/prefix",
                "proton_verb": "runinprefix",
                "container_reentry": "enabled",
                "environment_key_count": 5,
                "runtime_flags": "UMU_CONTAINER_NSENTER",
            },
        )

    def test_accepts_only_bounded_sanitized_umu_exit_diagnostics(self):
        recorder = self.recorder()
        details = {
            "stdout_bytes": 10,
            "stderr_bytes": 20,
            "stdout_truncated": False,
            "stderr_truncated": True,
            "stdout_tail": "safe output",
            "stderr_tail": "wine error",
            "failure_class": "wine",
            "group_member_count": 1,
            "group_member_names": "trainer.exe",
            "observed_descendant_count": 2,
            "observed_descendant_names": "pressure-vessel,wine64",
        }

        recorder.record("umu", "umu_exit_diagnostics", "warning", details=details)

        self.assertEqual(self.read_events()[0]["details"], details)

    def test_accepts_bounded_container_probe_failure_metadata(self):
        recorder = self.recorder()
        details = {
            "reason": "container_reentry_probe_failed",
            "failure_class": "dbus_unavailable",
            "probe_exit_code": 1,
            "bus_source": "home_owner_runtime",
            "attempt_count": 5,
        }

        recorder.record("umu", "container_reentry_rejected", "rejected", details=details)

        self.assertEqual(self.read_events()[0]["details"], details)

    def test_rejects_umu_output_tail_larger_than_the_runner_retention_limit(self):
        recorder = self.recorder()
        details = {
            "stdout_bytes": 1025,
            "stderr_bytes": 0,
            "stdout_truncated": True,
            "stderr_truncated": False,
            "stdout_tail": "x" * 1025,
            "stderr_tail": "",
            "failure_class": "unknown",
            "group_member_count": 0,
            "group_member_names": "",
            "observed_descendant_count": 0,
            "observed_descendant_names": "",
        }

        with self.assertRaisesRegex(DiagnosticValidationError, "diagnostic_event_rejected"):
            recorder.record("umu", "umu_exit_diagnostics", "warning", details=details)

        self.assertEqual(recorder.stats()["eventCount"], 0)

    def test_rejects_unknown_or_forbidden_details_without_writing(self):
        recorder = self.recorder()
        invalid_calls = (
            ("unknown_event", {"version": "1"}),
            ("plugin_loaded", {"unknown": "value"}),
            ("plugin_loaded", {"token": "secret"}),
            ("plugin_loaded", {"version": "x" * 4097}),
            ("plugin_loaded", {"version": ["nested"]}),
        )
        for event, details in invalid_calls:
            with self.subTest(event=event, details=details):
                with self.assertRaisesRegex(DiagnosticValidationError, "diagnostic_event_rejected"):
                    recorder.record("lifecycle", event, "info", details=details)
        self.assertEqual(recorder.stats()["eventCount"], 0)

    def test_disabled_recorder_does_not_create_storage(self):
        recorder = DiagnosticRecorder(self.root, enabled=False)
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "test"})
        self.assertFalse(self.root.exists())
        self.assertEqual(recorder.stats()["eventCount"], 0)

    def test_rotates_at_most_five_bounded_files(self):
        recorder = self.recorder(max_file_bytes=300, max_files=5)
        for sequence in range(100):
            recorder.record(
                "lifecycle",
                "plugin_loaded",
                "info",
                details={"version": f"test-{sequence:03d}"},
            )

        files = sorted(self.root.glob("diagnostics.*.ndjson"))
        self.assertEqual(len(files), 5)
        self.assertTrue(all(path.stat().st_size <= 300 for path in files))
        self.assertLessEqual(sum(path.stat().st_size for path in files), 1500)
        sequences = [event["sequence"] for event in self.read_events()]
        self.assertEqual(sequences, sorted(sequences))
        self.assertEqual(sequences[-1], 100)

    def test_startup_skips_malformed_lines_and_recovers_sequence(self):
        self.root.mkdir(parents=True)
        (self.root / "diagnostics.0.ndjson").write_text(
            '{"sequence":7,"timestamp":"2026-08-30T00:00:00.000Z","category":"lifecycle","event":"plugin_loaded","outcome":"info","details":{"version":"old"}}\nnot-json\n',
            encoding="utf-8",
        )
        recorder = self.recorder()
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "new"})
        self.assertEqual(self.read_events()[-1]["sequence"], 8)
        self.assertEqual(recorder.stats()["malformedLineCount"], 1)

    def test_rotation_recovers_when_middle_files_are_missing(self):
        self.root.mkdir(parents=True)
        (self.root / "diagnostics.0.ndjson").write_text("x" * 290, encoding="utf-8")
        (self.root / "diagnostics.2.ndjson").write_text("older\n", encoding="utf-8")
        recorder = self.recorder(max_file_bytes=300, max_files=5)
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "new"})
        self.assertTrue((self.root / "diagnostics.0.ndjson").exists())
        self.assertTrue((self.root / "diagnostics.1.ndjson").exists())
        self.assertTrue((self.root / "diagnostics.3.ndjson").exists())

    def test_consolidates_identical_repeats_on_change_and_timeout(self):
        recorder = self.recorder()
        details = {"reason": "prefix_mismatch", "expected_prefix": "/a", "observed_prefix": "/b"}
        recorder.record("process", "candidate_rejected", "rejected", identity="gog:game", details=details)
        recorder.record("process", "candidate_rejected", "rejected", identity="gog:game", details=details)
        recorder.record("process", "candidate_rejected", "rejected", identity="gog:game", details=details)
        self.assertEqual([event["event"] for event in self.read_events()], ["candidate_rejected"])

        self.clock.monotonic = 31.0
        recorder.record("process", "candidate_rejected", "rejected", identity="gog:game", details=details)
        events = self.read_events()
        self.assertEqual([event["event"] for event in events], ["candidate_rejected", "event_repeated"])
        self.assertEqual(events[1]["details"]["count"], 3)
        self.assertEqual(events[1]["details"]["repeated_event"], "candidate_rejected")

        recorder.record("lifecycle", "plugin_unloaded", "info", details={"version": "test"})
        self.assertEqual(self.read_events()[-1]["event"], "plugin_unloaded")

    def test_disable_flushes_pending_repeat_summary(self):
        recorder = self.recorder()
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "test"})
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "test"})
        recorder.set_enabled(False)
        self.assertEqual([event["event"] for event in self.read_events()], ["plugin_loaded", "event_repeated"])

    def test_cursor_paginates_and_clear_resets_generation(self):
        recorder = self.recorder()
        for count in range(3):
            recorder.record("lifecycle", "plugin_loaded", "info", details={"version": str(count)})

        first = recorder.events_after(None, 2)
        second = recorder.events_after(first["nextCursor"], 2)
        self.assertEqual(
            [event["details"]["version"] for event in first["events"] + second["events"]],
            ["0", "1", "2"],
        )

        recorder.clear()
        stale = recorder.events_after(second["nextCursor"], 20)
        self.assertTrue(stale["cursorReset"])
        self.assertGreater(stale["generation"], first["generation"])
        self.assertEqual(stale["events"], [])

    def test_cursor_metadata_and_sequence_survive_restart(self):
        recorder = self.recorder()
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "one"})
        first = recorder.events_after(None, 20)

        restarted = self.recorder()
        restarted.record("lifecycle", "plugin_loaded", "info", details={"version": "two"})
        second = restarted.events_after(first["nextCursor"], 20)

        self.assertFalse(second["cursorReset"])
        self.assertEqual(second["generation"], first["generation"])
        self.assertEqual([event["sequence"] for event in second["events"]], [2])

    def test_cursor_limit_is_clamped_to_supported_range(self):
        recorder = self.recorder()
        for count in range(3):
            recorder.record("lifecycle", "plugin_loaded", "info", details={"version": str(count)})
        self.assertEqual(len(recorder.events_after(None, 0)["events"]), 1)
        self.assertEqual(len(recorder.events_after(None, 999)["events"]), 3)

    def test_export_writes_oldest_first_private_deterministic_text_and_uses_collision_suffix(self):
        recorder = self.recorder()
        recorder.record(
            "process",
            "candidate_rejected",
            "rejected",
            identity="gog:game",
            session=DiagnosticSession(123, 456),
            details={"reason": "prefix_mismatch", "expected_prefix": "/a", "observed_prefix": "/b"},
        )
        recorder.record("lifecycle", "plugin_unloaded", "info", details={"version": "0.1.0"})
        downloads = Path(self.directory.name) / "Downloads"

        first = recorder.export_text(downloads, "0.1.0-experimental.13")
        second = recorder.export_text(downloads, "0.1.0-experimental.13")

        self.assertNotEqual(first["path"], second["path"])
        self.assertGreater(first["bytesWritten"], 0)
        text = Path(first["path"]).read_text(encoding="utf-8")
        self.assertIn("Trainer Relay diagnostic export", text)
        self.assertIn("Privacy: sanitized allowlisted events only", text)
        self.assertIn("bounded sanitized UMU process output tails", text)
        self.assertLess(text.index("#1 process rejected candidate_rejected"), text.index("#2 lifecycle info plugin_unloaded"))
        self.assertIn("identity=gog:game pid=123 startTime=456", text)
        self.assertIn("expected_prefix=/a observed_prefix=/b reason=prefix_mismatch", text)

    def test_export_failure_preserves_journal_and_prior_export(self):
        recorder = self.recorder()
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "test"})
        downloads = Path(self.directory.name) / "Downloads"
        prior = recorder.export_text(downloads, "test")
        prior_contents = Path(prior["path"]).read_bytes()

        with mock.patch("trainer_relay.diagnostics.os.replace", side_effect=OSError("denied")):
            with self.assertRaisesRegex(DiagnosticStorageError, "diagnostic_export_failed"):
                recorder.export_text(downloads, "test")

        self.assertEqual(Path(prior["path"]).read_bytes(), prior_contents)
        self.assertEqual(recorder.stats()["eventCount"], 1)
        self.assertEqual(list(downloads.glob("*.tmp")), [])

    def test_append_failure_is_isolated_until_explicit_retry(self):
        recorder = self.recorder()
        original = recorder._append_event
        failing = mock.Mock(side_effect=OSError("read-only filesystem"))
        recorder._append_event = failing

        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "one"})
        recorder.record("lifecycle", "plugin_unloaded", "info", details={"version": "two"})

        self.assertEqual(failing.call_count, 1)
        self.assertEqual(recorder.stats()["storageDiagnostic"], "diagnostic_storage_unavailable")

        recorder._append_event = original
        recorder.set_enabled(True)
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "recovered"})
        self.assertEqual(recorder.stats()["eventCount"], 1)
        self.assertIsNone(recorder.stats()["storageDiagnostic"])

    def test_clear_removes_only_owned_journal_and_metadata(self):
        recorder = self.recorder()
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "test"})
        unrelated = self.root / "keep-me.txt"
        unrelated.write_text("keep", encoding="utf-8")

        result = recorder.clear()

        self.assertEqual(result["eventCount"], 0)
        self.assertTrue(unrelated.is_file())
        self.assertEqual(list(self.root.glob("diagnostics.*.ndjson")), [])

    def test_stats_does_not_reread_journal_contents_during_one_second_polling(self):
        recorder = self.recorder()
        recorder.record("lifecycle", "plugin_loaded", "info", details={"version": "test"})

        with mock.patch.object(Path, "read_text", side_effect=AssertionError("journal reread")):
            first = recorder.stats()
            second = recorder.stats()

        self.assertEqual(first["eventCount"], 1)
        self.assertEqual(second["eventCount"], 1)


if __name__ == "__main__":
    unittest.main()
