import signal
import subprocess
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
        self.assertEqual(calls[0][1]["stdout"], subprocess.DEVNULL)
        self.assertEqual(calls[0][1]["stderr"], subprocess.DEVNULL)
        self.assertEqual(handle.process_group_id, process.pid)
        self.assertIn(handle, runner.owned)

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
