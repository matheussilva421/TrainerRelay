import signal
import subprocess
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from trainer_relay.process import SessionIdentity
from trainer_relay.runner import OwnedTrainerRunner, RunnerHandle, StopResult


class FakeProcess:
    def __init__(self, pid=4321, returncode=None):
        self.pid = pid
        self.returncode = returncode

    def poll(self):
        return self.returncode


class RunnerTests(unittest.TestCase):
    def test_confirms_only_the_exact_expected_umu_reentry_line_across_pipe_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake-umu.py"
            script.write_text(
                "import sys, time\n"
                "sys.stderr.write(\"INFO: Re-entering container through bus 'com.steam\")\n"
                "sys.stderr.flush()\n"
                "time.sleep(0.02)\n"
                "sys.stderr.write(\"powered.Appabc123'\\n\")\n"
                "sys.stderr.flush()\n"
                "time.sleep(0.1)\n",
                encoding="utf-8",
            )
            runner = OwnedTrainerRunner(sys.executable)
            handle = runner.spawn(
                SessionIdentity(7, 99),
                str(script),
                dict(os.environ),
                expected_reentry_bus="com.steampowered.Appabc123",
            )

            deadline = time.monotonic() + 2.0

            self.assertEqual(runner.reentry_status(handle, wait_seconds=0.2), "confirmed")
            while runner.poll(handle) is None and time.monotonic() < deadline:
                time.sleep(0.01)
            runner.forget(handle)

    def test_reports_the_exact_expected_umu_reentry_failure_without_accepting_another_bus(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake-umu.py"
            script.write_text(
                "import sys, time\n"
                "print(\"INFO: Re-entering container through bus 'com.steampowered.Appwrong'\", file=sys.stderr, flush=True)\n"
                "print('INFO: Failed to find bus name com.steampowered.Appexpected (retry 1)', file=sys.stderr, flush=True)\n"
                "time.sleep(0.1)\n",
                encoding="utf-8",
            )
            runner = OwnedTrainerRunner(sys.executable)
            handle = runner.spawn(
                SessionIdentity(7, 99),
                str(script),
                dict(os.environ),
                expected_reentry_bus="com.steampowered.Appexpected",
            )

            deadline = time.monotonic() + 2.0
            while runner.reentry_status(handle) == "pending" and time.monotonic() < deadline:
                time.sleep(0.01)

            self.assertEqual(runner.reentry_status(handle), "retrying")
            while runner.poll(handle) is None and time.monotonic() < deadline:
                time.sleep(0.01)
            runner.forget(handle)

    def test_does_not_confirm_the_expected_text_when_it_is_not_the_exact_umu_info_line(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake-umu.py"
            script.write_text(
                "import sys\n"
                "print(\"noise INFO: Re-entering container through bus 'com.steampowered.Appabc123' suffix\", file=sys.stderr)\n",
                encoding="utf-8",
            )
            runner = OwnedTrainerRunner(sys.executable)
            handle = runner.spawn(
                SessionIdentity(7, 99),
                str(script),
                dict(os.environ),
                expected_reentry_bus="com.steampowered.Appabc123",
            )

            deadline = time.monotonic() + 2.0
            while runner.poll(handle) is None and time.monotonic() < deadline:
                time.sleep(0.01)

            self.assertEqual(runner.reentry_status(handle), "pending")
            runner.forget(handle)

    def test_spawns_exact_umu_argv_in_trainer_parent_and_new_session(self):
        calls = []
        process = FakeProcess()

        def popen(argv, **kwargs):
            calls.append((argv, kwargs))
            return process

        runner = OwnedTrainerRunner("/home/deck/umu-run", popen_factory=popen)
        handle = runner.spawn(SessionIdentity(7, 99), "/games/My Trainer.EXE", {"SAFE": "yes"})
        self.assertEqual(calls[0][0], ["/home/deck/umu-run", "/games/My Trainer.EXE"])
        self.assertEqual(calls[0][1]["cwd"], str(Path("/games/My Trainer.EXE").parent))
        self.assertFalse(calls[0][1]["shell"])
        self.assertTrue(calls[0][1]["start_new_session"])
        self.assertIs(calls[0][1]["env"], handle.environment)
        self.assertEqual(calls[0][1]["stdout"], subprocess.PIPE)
        self.assertEqual(calls[0][1]["stderr"], subprocess.PIPE)
        self.assertEqual(handle.process_group_id, process.pid)
        self.assertIn(handle, runner.owned)

    def test_spawns_epic_trainer_inside_named_wine_virtual_desktop(self):
        calls = []
        process = FakeProcess()

        def popen(argv, **kwargs):
            calls.append((argv, kwargs))
            return process

        runner = OwnedTrainerRunner("/home/deck/umu-run", popen_factory=popen)
        trainer = "/games/My Trainer.EXE"
        runner.spawn(
            SessionIdentity(7, 99),
            trainer,
            {"SAFE": "yes"},
            virtual_desktop=True,
        )

        self.assertEqual(
            calls[0][0],
            [
                "/home/deck/umu-run",
                "explorer.exe",
                "/desktop=TrainerRelay,800x680",
                trainer,
            ],
        )

    def test_exit_diagnostics_drains_bounds_and_sanitizes_umu_output(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake-umu.py"
            script.write_text(
                "import sys\n"
                "print('x' * 5000)\n"
                "print('API_TOKEN=super-private')\n"
                "print('https://user:password@example.invalid/path', file=sys.stderr)\n"
                "print('wine: failed to load kernel32.dll', file=sys.stderr)\n",
                encoding="utf-8",
            )
            runner = OwnedTrainerRunner(
                sys.executable,
                process_group_members=lambda _: ("umu-run", "trainer.exe"),
            )

            handle = runner.spawn(SessionIdentity(7, 99), str(script), dict(os.environ))
            deadline = time.monotonic() + 5.0
            while runner.poll(handle) is None and time.monotonic() < deadline:
                time.sleep(0.01)
            diagnostic = runner.exit_diagnostics(handle)

            self.assertGreater(diagnostic.stdout_bytes, 4096)
            self.assertTrue(diagnostic.stdout_truncated)
            self.assertLessEqual(len(diagnostic.stdout_tail), 1024)
            self.assertNotIn("super-private", diagnostic.stdout_tail)
            self.assertIn("API_TOKEN=[REDACTED]", diagnostic.stdout_tail)
            self.assertNotIn("user:password", diagnostic.stderr_tail)
            self.assertIn("[REDACTED]@example.invalid", diagnostic.stderr_tail)
            self.assertIn("kernel32.dll", diagnostic.stderr_tail)
            self.assertEqual(diagnostic.group_member_count, 2)
            self.assertEqual(diagnostic.group_member_names, "trainer.exe,umu-run")
            runner.forget(handle)

    def test_exit_diagnostics_classifies_empty_output_without_exposing_environment(self):
        process = FakeProcess(pid=91, returncode=1)
        runner = OwnedTrainerRunner(
            "/umu-run",
            popen_factory=lambda *args, **kwargs: process,
            process_group_members=lambda _: (),
        )
        handle = runner.spawn(SessionIdentity(1, 2), "/game.exe", {"API_TOKEN": "private"})

        diagnostic = runner.exit_diagnostics(handle)

        self.assertEqual(diagnostic.failure_class, "no_output")
        self.assertNotIn("private", repr(diagnostic))

    def test_poll_retains_descendant_names_observed_before_the_umu_parent_exits(self):
        process = FakeProcess(pid=91)
        snapshots = iter((("pressure-vessel", "wine64"), ()))
        runner = OwnedTrainerRunner(
            "/umu-run",
            popen_factory=lambda *args, **kwargs: process,
            process_group_members=lambda _: (),
            process_descendants=lambda _: next(snapshots),
        )
        handle = runner.spawn(SessionIdentity(1, 2), "/game.exe", {})

        self.assertIsNone(runner.poll(handle))
        process.returncode = 1
        self.assertEqual(runner.poll(handle), 1)
        diagnostic = runner.exit_diagnostics(handle)

        self.assertEqual(diagnostic.observed_descendant_count, 2)
        self.assertEqual(diagnostic.observed_descendant_names, "pressure-vessel,wine64")

    def test_sanitization_redacts_a_secret_whose_key_starts_before_the_retained_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake-umu.py"
            script.write_text(
                "print('API_TOKEN=' + 's' * 6000)\n",
                encoding="utf-8",
            )
            runner = OwnedTrainerRunner(sys.executable, process_group_members=lambda _: ())
            handle = runner.spawn(SessionIdentity(7, 99), str(script), dict(os.environ))
            deadline = time.monotonic() + 5.0
            while runner.poll(handle) is None and time.monotonic() < deadline:
                time.sleep(0.01)

            diagnostic = runner.exit_diagnostics(handle)

            self.assertNotIn("s" * 128, diagnostic.stdout_tail)
            self.assertIn("[REDACTED]", diagnostic.stdout_tail)
            runner.forget(handle)

    def test_sanitization_redacts_secret_url_parameters_and_authorization_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake-umu.py"
            script.write_text(
                "print('GET https://example.invalid/run?token=private&safe=yes')\n"
                "print('Authorization: Basic cHJpdmF0ZQ==')\n",
                encoding="utf-8",
            )
            runner = OwnedTrainerRunner(sys.executable, process_group_members=lambda _: ())
            handle = runner.spawn(SessionIdentity(7, 99), str(script), dict(os.environ))
            deadline = time.monotonic() + 5.0
            while runner.poll(handle) is None and time.monotonic() < deadline:
                time.sleep(0.01)

            diagnostic = runner.exit_diagnostics(handle)

            self.assertNotIn("private", diagnostic.stdout_tail)
            self.assertNotIn("cHJpdmF0ZQ", diagnostic.stdout_tail)
            self.assertIn("token=[REDACTED]", diagnostic.stdout_tail)
            self.assertIn("Authorization: [REDACTED]", diagnostic.stdout_tail)
            runner.forget(handle)

    def test_sanitization_redacts_api_access_and_private_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake-umu.py"
            script.write_text(
                "print('OPENAI_API_KEY=sk-private')\n"
                "print('AWS_ACCESS_KEY=access-private')\n"
                "print('PRIVATE_KEY=private-material')\n",
                encoding="utf-8",
            )
            runner = OwnedTrainerRunner(sys.executable, process_group_members=lambda _: ())
            handle = runner.spawn(SessionIdentity(7, 99), str(script), dict(os.environ))
            deadline = time.monotonic() + 5.0
            while runner.poll(handle) is None and time.monotonic() < deadline:
                time.sleep(0.01)

            diagnostic = runner.exit_diagnostics(handle)

            self.assertNotIn("sk-private", diagnostic.stdout_tail)
            self.assertNotIn("access-private", diagnostic.stdout_tail)
            self.assertNotIn("private-material", diagnostic.stdout_tail)
            self.assertEqual(diagnostic.stdout_tail.count("[REDACTED]"), 3)
            runner.forget(handle)

    def test_exit_diagnostics_does_not_wait_for_a_child_that_inherits_the_pipes(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fake-umu.py"
            script.write_text(
                "import subprocess, sys, tempfile\n"
                "subprocess.Popen([sys.executable, '-c', \"import time; print('child alive', flush=True); time.sleep(2)\"], cwd=tempfile.gettempdir())\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            runner = OwnedTrainerRunner(sys.executable, process_group_members=lambda _: ("trainer.exe",))
            handle = runner.spawn(SessionIdentity(7, 99), str(script), dict(os.environ))
            deadline = time.monotonic() + 5.0
            while runner.poll(handle) is None and time.monotonic() < deadline:
                time.sleep(0.01)

            started = time.monotonic()
            diagnostic = runner.exit_diagnostics(handle)
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.75)
            self.assertEqual(diagnostic.group_member_count, 1)
            runner.forget(handle)

    def test_rejects_a_log_path_that_could_capture_arbitrary_trainer_output(self):
        with self.assertRaisesRegex(TypeError, "log_path"):
            OwnedTrainerRunner("/home/deck/umu-run", log_path="/tmp/trainer-relay.log")

    def test_stop_signals_only_recorded_owned_group_then_kills_after_five_seconds(self):
        process = FakeProcess(pid=99)
        signals = []
        times = iter([0.0, 0.0, 4.9, 5.1])
        runner = OwnedTrainerRunner(
            "/umu-run",
            popen_factory=lambda *args, **kwargs: process,
            monotonic=lambda: next(times),
            sleep=lambda _: None,
            signal_group=lambda group, signum: signals.append((group, signum)),
        )
        handle = runner.spawn(SessionIdentity(1, 2), "/game.exe", {})
        result = runner.stop(handle)
        self.assertEqual(signals, [(99, getattr(signal, "SIGTERM", 15)), (99, getattr(signal, "SIGKILL", 9))])
        self.assertNotIn(handle, runner.owned)
        self.assertEqual(result, StopResult(forced=True))

    def test_stop_reports_graceful_exit_without_sigkill(self):
        process = FakeProcess(pid=99)
        signals = []

        def signal_group(group, signum):
            signals.append((group, signum))
            process.returncode = 0

        runner = OwnedTrainerRunner(
            "/umu-run",
            popen_factory=lambda *args, **kwargs: process,
            signal_group=signal_group,
        )
        handle = runner.spawn(SessionIdentity(1, 2), "/game.exe", {})
        result = runner.stop(handle)
        self.assertEqual(result, StopResult(forced=False))
        self.assertEqual(signals, [(99, getattr(signal, "SIGTERM", 15))])

    def test_refuses_to_signal_a_handle_not_created_by_this_runner(self):
        signals = []
        runner = OwnedTrainerRunner("/umu-run", signal_group=lambda group, signum: signals.append((group, signum)))
        foreign = RunnerHandle(SessionIdentity(1, 2), FakeProcess(pid=55), 55, {})
        with self.assertRaisesRegex(ValueError, "unowned_process"):
            runner.stop(foreign)
        self.assertEqual(signals, [])

    def test_refuses_a_structurally_equal_but_foreign_handle(self):
        process = FakeProcess(pid=55)
        signals = []
        runner = OwnedTrainerRunner(
            "/umu-run",
            popen_factory=lambda *args, **kwargs: process,
            signal_group=lambda group, signum: signals.append((group, signum)),
        )
        handle = runner.spawn(SessionIdentity(1, 2), "/game.exe", {})
        foreign = RunnerHandle(handle.session, handle.process, handle.process_group_id, handle.environment)
        with self.assertRaisesRegex(ValueError, "unowned_process"):
            runner.stop(foreign)
        self.assertEqual(signals, [])


if __name__ == "__main__":
    unittest.main()
