import hashlib
import io
import json
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path

from trainer_relay.command_runner import OneShotCommandRunner
from trainer_relay.process import SessionIdentity
from trainer_relay.types import CommandContext

from tests_backend.test_helper_manifest import fake_pe


class TrackingStream(io.BytesIO):
    def __init__(self, value=b""):
        super().__init__(value)
        self.was_closed = False

    def close(self):
        self.was_closed = True
        super().close()


class FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes, *, returncode: int = 0, block: bool = False):
        self.pid = 4321
        self.stdout = TrackingStream(stdout)
        self.stderr = TrackingStream(stderr)
        self.returncode = None if block else returncode
        self._block = block
        self.released = threading.Event()
        self.process_kill_called = False
        self.group_alive = True
        self.descendants = {"fake-descendant"} if block else set()

    def wait(self, timeout=None):
        if self._block and not self.released.wait(timeout):
            raise subprocess.TimeoutExpired("fake", timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class OneShotCommandRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.helper = root / "helper.x86.exe"
        self.helper.write_bytes(fake_pe(0x14C))
        self.manifest = root / "input-helper-manifest.json"
        digest = hashlib.sha256(self.helper.read_bytes()).hexdigest()
        self.manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "helpers": {
                        "x86": {"path": self.helper.name, "sha256": digest},
                    },
                }
            ),
            encoding="utf-8",
        )
        self.environment = {
            "HOME": "/home/deck",
            "PATH": "/usr/bin:/bin",
            "WINEPREFIX": "/prefix",
            "PROTONPATH": "/proton",
            "GAMEID": "game",
            "STORE": "gog",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "XDG_RUNTIME_DIR": "/run/user/1000",
            "UMU_CONTAINER_NSENTER": "1",
            "PROTON_VERB": "runinprefix",
        }
        self.context = CommandContext(
            identity="gog:game",
            session=SessionIdentity(10, 20),
            trainer_sha256="a" * 64,
            trainer_arch="x86",
            environment=self.environment,
            umu_run="/usr/bin/umu-run",
            expected_reentry_bus="com.steampowered.Appabc",
        )
        self.marker = b"INFO: Re-entering container through bus 'com.steampowered.Appabc'\n"

    def tearDown(self):
        self.directory.cleanup()

    def _runner(self, process, *, kill_group=None):
        calls = []

        def popen(argv, **kwargs):
            calls.append((argv, kwargs))
            return process

        runner = OneShotCommandRunner(
            self.manifest,
            popen_factory=popen,
            kill_process_group=kill_group or (lambda *_: None),
        )
        return runner, calls

    @staticmethod
    def _output(*, accepted=3, expected=3, result_code=0):
        return json.dumps(
            {
                "protocol": 1,
                "accepted_count": accepted,
                "expected_count": expected,
                "result_code": result_code,
            }
        ).encode()

    def test_runs_structured_argv_with_exact_context_environment_and_reports_requested(self):
        process = FakeProcess(self._output(), self.marker)
        runner, calls = self._runner(process)

        result = runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)

        self.assertEqual(result.outcome, "requested")
        self.assertIsNone(result.diagnostic)
        self.assertEqual(result.accepted_count, 3)
        self.assertEqual(result.expected_count, 3)
        self.assertEqual(
            calls[0][0],
            [
                "/usr/bin/umu-run",
                str(self.helper),
                "--protocol",
                "1",
                "--key",
                "65",
                "--modifiers",
                "5",
                "--hold-ms",
                "40",
            ],
        )
        self.assertFalse(calls[0][1]["shell"])
        self.assertTrue(calls[0][1]["start_new_session"])
        self.assertEqual(calls[0][1]["env"], self.environment)

    def test_rejects_count_mismatch_nonzero_exit_and_missing_reentry_marker(self):
        cases = (
            (FakeProcess(self._output(accepted=2), self.marker), "helper_input_count_mismatch"),
            (FakeProcess(self._output(), self.marker, returncode=7), "helper_exit_nonzero"),
            (FakeProcess(self._output(), b""), "container_reentry_marker_missing"),
        )
        for process, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                runner, calls = self._runner(process)
                result = runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)
                self.assertEqual(result.outcome, "failed")
                self.assertEqual(result.diagnostic, diagnostic)
                self.assertEqual(len(calls), 1)

    def test_rejects_malformed_and_oversized_helper_output_without_exposing_raw_bytes(self):
        cases = (
            (b"not json", "helper_output_malformed"),
            (b"{}\n{}", "helper_output_malformed"),
            (b"x" * 8193, "helper_output_oversized"),
        )
        for stdout, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                runner, _ = self._runner(FakeProcess(stdout, self.marker))
                result = runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)
                self.assertEqual(result.diagnostic, diagnostic)
                self.assertNotIn("x" * 100, repr(result))

    def test_excessive_output_stops_total_capture_and_terminates_the_group(self):
        class ExcessiveStream:
            def __init__(self):
                self.read_calls = 0
                self.was_closed = False
                self.closed = threading.Event()

            def read(self, _size):
                self.read_calls += 1
                if self.read_calls == 1:
                    return b"x" * (8192 + 1)
                self.closed.wait(1.0)
                return b""

            def close(self):
                self.was_closed = True
                self.closed.set()

        process = FakeProcess(self._output(), self.marker, block=True)
        process.stdout = ExcessiveStream()

        def kill_group(_group, _signum):
            process.group_alive = False
            process.descendants.clear()
            process.released.set()

        runner, _ = self._runner(process, kill_group=kill_group)

        result = runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.diagnostic, "helper_output_oversized")
        self.assertEqual(process.stdout.read_calls, 1)
        self.assertTrue(process.stdout.was_closed)
        self.assertFalse(process.group_alive)
        self.assertEqual(process.descendants, set())

    def test_timeout_kills_only_the_helper_process_group(self):
        process = FakeProcess(self._output(), self.marker, block=True)
        signals = []

        def kill_group(group, signum):
            signals.append((group, signum))
            process.group_alive = False
            process.descendants.clear()
            process.released.set()

        runner, calls = self._runner(process, kill_group=kill_group)

        result = runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.diagnostic, "command_timeout")
        self.assertEqual(signals, [(process.pid, getattr(signal, "SIGKILL", 9))])
        self.assertFalse(process.process_kill_called)
        self.assertFalse(process.group_alive)
        self.assertEqual(process.descendants, set())
        self.assertTrue(process.stdout.was_closed)
        self.assertTrue(process.stderr.was_closed)
        self.assertEqual(len(calls), 1)

    def test_timeout_reports_cleanup_failure_when_group_does_not_die(self):
        process = FakeProcess(self._output(), self.marker, block=True)
        runner, _ = self._runner(process, kill_group=lambda *_: None)

        result = runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.diagnostic, "command_timeout_cleanup_failed")
        self.assertTrue(process.group_alive)
        self.assertEqual(process.descendants, {"fake-descendant"})
        self.assertTrue(process.stdout.was_closed)
        self.assertTrue(process.stderr.was_closed)

    def test_timeout_reports_cleanup_failure_when_kill_group_fails(self):
        process = FakeProcess(self._output(), self.marker, block=True)

        def kill_group(*_):
            raise OSError("private process detail")

        runner, _ = self._runner(process, kill_group=kill_group)

        result = runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.diagnostic, "command_timeout_cleanup_failed")
        self.assertNotIn("private process detail", repr(result))

    def test_second_command_for_the_same_identity_is_rejected_while_first_is_in_flight(self):
        process = FakeProcess(self._output(), self.marker, block=True)
        runner, _ = self._runner(process)
        first_result = []
        first = threading.Thread(
            target=lambda: first_result.append(
                runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)
            )
        )
        first.start()
        deadline = time.monotonic() + 1.0
        while not runner.busy_identities and time.monotonic() < deadline:
            time.sleep(0.001)

        second = runner.run(self.context, self.helper, 65, 5, revalidator=lambda: self.context)
        process.released.set()
        first.join(timeout=2.0)

        self.assertEqual(second.diagnostic, "command_busy")
        self.assertEqual(first_result[0].outcome, "requested")

    def test_manifest_rejection_happens_before_popen(self):
        process = FakeProcess(self._output(), self.marker)
        runner, calls = self._runner(process)
        missing = Path(self.directory.name) / "missing.exe"

        result = runner.run(self.context, missing, 65, 5, revalidator=lambda: self.context)

        self.assertEqual(result.outcome, "rejected")
        self.assertEqual(result.diagnostic, "helper_missing")
        self.assertEqual(calls, [])

    def test_rejects_a_virtual_key_outside_the_symbolic_allowlist_before_popen(self):
        process = FakeProcess(self._output(), self.marker)
        runner, calls = self._runner(process)

        result = runner.run(self.context, self.helper, 1, 0, revalidator=lambda: self.context)

        self.assertEqual(result.outcome, "rejected")
        self.assertEqual(result.diagnostic, "invalid_virtual_key")
        self.assertEqual(calls, [])

    def test_rejects_a_context_without_the_verified_umu_environment_before_popen(self):
        invalid_environment = dict(self.environment)
        invalid_environment["UMU_CONTAINER_NSENTER"] = "0"
        invalid_context = CommandContext(
            identity=self.context.identity,
            session=self.context.session,
            trainer_sha256=self.context.trainer_sha256,
            trainer_arch=self.context.trainer_arch,
            environment=invalid_environment,
            umu_run=self.context.umu_run,
            expected_reentry_bus=self.context.expected_reentry_bus,
        )
        process = FakeProcess(self._output(), self.marker)
        runner, calls = self._runner(process)

        result = runner.run(invalid_context, self.helper, 65, 5, revalidator=lambda: invalid_context)

        self.assertEqual(result.outcome, "rejected")
        self.assertEqual(result.diagnostic, "invalid_command_context")
        self.assertEqual(calls, [])

    def test_revalidator_rejects_changed_session_or_trainer_before_popen(self):
        for changed_context in (
            replace(self.context, session=SessionIdentity(11, 21)),
            replace(self.context, trainer_sha256="b" * 64),
        ):
            with self.subTest(changed_context=changed_context):
                process = FakeProcess(self._output(), self.marker)
                runner, calls = self._runner(process)

                result = runner.run(
                    self.context,
                    self.helper,
                    65,
                    5,
                    revalidator=lambda changed_context=changed_context: changed_context,
                )

                self.assertEqual(result.outcome, "rejected")
                self.assertEqual(result.diagnostic, "command_context_changed")
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
