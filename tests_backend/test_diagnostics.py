import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trainer_relay.diagnostics import (
    DiagnosticRecorder,
    DiagnosticSession,
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


if __name__ == "__main__":
    unittest.main()
