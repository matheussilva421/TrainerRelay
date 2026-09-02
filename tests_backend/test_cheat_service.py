import asyncio
import copy
import threading
import time
import unittest
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import patch

from trainer_relay.cheat_catalog import AdapterDescriptor, CheatDescriptor
from trainer_relay.cheat_config import DEFAULT_CONFIG_KEY
from trainer_relay.process import SessionIdentity
from trainer_relay.types import CommandContext, CommandContextError


HASH = "a" * 64
OTHER_HASH = "b" * 64
IDENTITY = "gog:game"
HOTKEY = {"modifiers": ["shift", "ctrl"], "key": "F1"}


class _BoundedCooperativeProvider:
    cooperative_command_contract = {"deadline_seconds": 1.0, "cancel_deadline_seconds": 1.0}

    def cancel_command(self, _descriptor, _command_id):
        return None


def _cheat(cheat_id="health", label="Infinite health", key="F1"):
    hotkey = {"modifiers": [], "key": key}
    return CheatDescriptor(cheat_id, label, hotkey, (hotkey,))


def _adapter(sha256=HASH):
    return AdapterDescriptor(
        adapter_id="test-adapter",
        sha256=sha256,
        pe_architecture="x86",
        trainer_label="Test trainer",
        supported_identities=(IDENTITY,),
        cheats=(_cheat(),),
        disable_all_hotkey={"modifiers": [], "key": "HOME"},
    )


class Settings:
    def __init__(self, controls=None):
        self.values = {DEFAULT_CONFIG_KEY: controls or {"schemaVersion": 1, "games": {}}}
        self.set_calls = []
        self.commit_calls = 0

    def getSetting(self, key, default):
        return self.values.get(key, default)

    def setSetting(self, key, value):
        self.values[key] = value
        self.set_calls.append((key, value))

    def commit(self):
        self.commit_calls += 1


class Watcher:
    def __init__(self, context=None, state="running", diagnostic=None):
        self.context = context
        self.state = state
        self.diagnostic = diagnostic
        self.context_threads = []

    def status(self, identity):
        return {"identity": identity, "state": self.state, "diagnostic": self.diagnostic}

    def command_context(self, identity):
        self.context_threads.append(threading.get_ident())
        if isinstance(self.context, Exception):
            raise self.context
        if self.context is None:
            raise CommandContextError("relay_not_running")
        return self.context

    @contextmanager
    def command_context_lease(self, identity):
        yield self.command_context(identity)


@dataclass
class Execution:
    outcome: str = "requested"
    diagnostic: str | None = None
    duration_ms: int = 4


class Runner:
    def __init__(self, result=None, block=False):
        self.result = result or Execution()
        self.block = block
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self.threads = []

    def run(self, context, helper, vk, modifiers, *, lease_factory):
        self.threads.append(threading.get_ident())
        self.calls.append((context, helper, vk, modifiers, lease_factory))
        self.started.set()
        if self.block:
            self.release.wait(1)
        return self.result


class Catalog:
    def __init__(self, adapter=None):
        self.adapter = adapter

    def resolve(self, sha256, identity):
        return self.adapter if self.adapter and self.adapter.sha256 == sha256 else None


def _context(sha256=HASH):
    return CommandContext(
        identity=IDENTITY,
        session=(10, 20),
        trainer_sha256=sha256,
        trainer_arch="x86",
        environment={"WINEPREFIX": "/prefix"},
        umu_run="/umu-run",
        expected_reentry_bus="com.example.bus",
    )


def _cooperative_context(sha256=HASH, session=SessionIdentity(10, 20)):
    return CommandContext(
        identity=IDENTITY,
        session=session,
        trainer_sha256=sha256,
        trainer_arch="x86",
        environment={"WINEPREFIX": "/prefix"},
        umu_run="/umu-run",
        expected_reentry_bus="com.example.bus",
    )


class CheatServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_precedes_matching_manual_controls(self):
        settings = Settings(
            {
                "schemaVersion": 1,
                "games": {
                    IDENTITY: {
                        "trainerSha256": HASH,
                        "cheats": [
                            {
                                "id": "11111111-1111-4111-8111-111111111111",
                                "label": "Manual duplicate",
                                "hotkey": HOTKEY,
                            }
                        ],
                    }
                },
            }
        )
        from trainer_relay.cheat_service import CheatControlService

        service = CheatControlService(
            settings,
            Watcher(_context()),
            Runner(),
            catalog=Catalog(_adapter()),
            helper_paths={"x86": "/helper.x86.exe"},
        )

        response = await service.get_cheat_controls(IDENTITY)

        self.assertEqual(response["status"], "ready")
        self.assertEqual(response["source"], "adapter")
        self.assertEqual([cheat["id"] for cheat in response["cheats"]], ["health"])
        self.assertFalse(response["capabilities"]["authoritativeState"])
        self.assertEqual(response["cheats"][0]["state"], "unknown")

    async def test_unknown_hash_uses_exact_manual_binding_and_changed_hash_is_hidden(self):
        manual = {
            "schemaVersion": 1,
            "games": {
                IDENTITY: {
                    "trainerSha256": HASH,
                    "cheats": [
                        {
                            "id": "11111111-1111-4111-8111-111111111111",
                            "label": "Manual health",
                            "hotkey": HOTKEY,
                        }
                    ],
                }
            },
        }
        from trainer_relay.cheat_service import CheatControlService

        watcher = Watcher(_context(HASH))
        service = CheatControlService(
            Settings(manual), watcher, Runner(), catalog=Catalog(), helper_paths={"x86": "/helper.exe"}
        )
        ready = await service.get_cheat_controls(IDENTITY)
        self.assertEqual(ready["source"], "manual")
        self.assertEqual(ready["trainerSha256"], HASH)

        watcher.context = _context(OTHER_HASH)
        unavailable = await service.get_cheat_controls(IDENTITY)
        self.assertNotEqual(unavailable["status"], "ready")
        self.assertNotIn("Manual health", str(unavailable))

    async def test_zero_multiple_and_non_running_sessions_never_become_ready(self):
        from trainer_relay.cheat_service import CheatControlService

        for state, diagnostic in (
            ("disabled", None),
            ("waiting_for_game", None),
            ("ambiguous", {"code": "multiple_game_sessions"}),
        ):
            with self.subTest(state=state):
                service = CheatControlService(
                    Settings(), Watcher(state=state, diagnostic=diagnostic), Runner(), catalog=Catalog(_adapter())
                )
                response = await service.get_cheat_controls(IDENTITY)
                self.assertIn(response["status"], {"unavailable", "waiting"})
                self.assertNotEqual(response["status"], "ready")

    async def test_adapter_command_is_requested_unknown_and_uses_background_context_and_runner(self):
        from trainer_relay.cheat_service import CheatControlService

        watcher = Watcher(_context())
        runner = Runner()
        service = CheatControlService(
            Settings(), watcher, runner, catalog=Catalog(_adapter()), helper_paths={"x86": "/helper.exe"}
        )
        caller_thread = threading.get_ident()

        result = await service.send_cheat_command(IDENTITY, "health")

        self.assertEqual(result["outcome"], "requested")
        self.assertEqual(result["state"], "unknown")
        self.assertIsNone(result["diagnostic"])
        self.assertNotEqual(watcher.context_threads, [caller_thread])
        self.assertNotEqual(runner.threads, [caller_thread])
        self.assertEqual(runner.calls[0][2:4], (0x70, 0))
        self.assertRegex(result["commandId"], r"^[0-9a-f-]{36}$")
        uuid.UUID(result["commandId"])

    async def test_second_command_for_identity_is_bounded_busy(self):
        from trainer_relay.cheat_service import CheatControlService

        runner = Runner(block=True)
        service = CheatControlService(
            Settings(), Watcher(_context()), runner, catalog=Catalog(_adapter()), helper_paths={"x86": "/helper.exe"}
        )
        first = asyncio.create_task(service.send_cheat_command(IDENTITY, "health"))
        await asyncio.to_thread(runner.started.wait, 1)
        second = await service.send_cheat_command(IDENTITY, "health")
        runner.release.set()
        first_result = await first

        self.assertEqual(second["outcome"], "rejected")
        self.assertEqual(second["diagnostic"]["code"], "command_busy")
        self.assertEqual(first_result["outcome"], "requested")

    async def test_runner_failure_is_bounded_and_raw_exception_is_not_returned(self):
        from trainer_relay.cheat_service import CheatControlService

        runner = Runner(Execution(outcome="failed", diagnostic="helper_exit_nonzero"))
        service = CheatControlService(
            Settings(), Watcher(_context()), runner, catalog=Catalog(_adapter()), helper_paths={"x86": "/helper.exe"}
        )
        result = await service.send_cheat_command(IDENTITY, "health")
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["diagnostic"], {"code": "helper_exit_nonzero"})

    async def test_runner_busy_diagnostic_remains_command_busy(self):
        from trainer_relay.cheat_service import CheatControlService

        runner = Runner(Execution(outcome="rejected", diagnostic="command_busy"))
        service = CheatControlService(
            Settings(), Watcher(_context()), runner, catalog=Catalog(_adapter()), helper_paths={"x86": "/helper.exe"}
        )
        result = await service.send_cheat_command(IDENTITY, "health")
        self.assertEqual(result["outcome"], "rejected")
        self.assertEqual(result["diagnostic"], {"code": "command_busy"})

    async def test_runner_revalidation_diagnostic_is_preserved_as_bounded_code(self):
        from trainer_relay.cheat_service import CheatControlService

        runner = Runner(Execution(outcome="rejected", diagnostic="command_context_changed"))
        service = CheatControlService(
            Settings(), Watcher(_context()), runner, catalog=Catalog(_adapter()), helper_paths={"x86": "/helper.exe"}
        )
        result = await service.send_cheat_command(IDENTITY, "health")
        self.assertEqual(result["diagnostic"], {"code": "command_context_changed"})

    async def test_runner_manifest_path_diagnostic_is_preserved_as_bounded_code(self):
        from trainer_relay.cheat_service import CheatControlService

        runner = Runner(Execution(outcome="rejected", diagnostic="helper_manifest_path_mismatch"))
        service = CheatControlService(
            Settings(), Watcher(_context()), runner, catalog=Catalog(_adapter()), helper_paths={"x86": "/helper.exe"}
        )
        result = await service.send_cheat_command(IDENTITY, "health")
        self.assertEqual(result["diagnostic"], {"code": "helper_manifest_path_mismatch"})

    async def test_invalid_cheat_and_context_failure_are_rejected_without_runner(self):
        from trainer_relay.cheat_service import CheatControlService

        runner = Runner()
        watcher = Watcher(_context())
        service = CheatControlService(
            Settings(), watcher, runner, catalog=Catalog(_adapter()), helper_paths={"x86": "/helper.exe"}
        )
        invalid = await service.send_cheat_command(IDENTITY, "missing")
        watcher.context = CommandContextError("session_recycled")
        rejected = await service.send_cheat_command(IDENTITY, "health")
        self.assertEqual(invalid["diagnostic"]["code"], "cheat_unavailable")
        self.assertEqual(rejected["diagnostic"]["code"], "session_recycled")
        self.assertEqual(runner.calls, [])

    async def test_cooperative_descriptor_snapshot_never_claims_authoritative_state(self):
        from trainer_relay.cheat_service import CheatControlService

        context = _context()
        context = CommandContext(
            identity=context.identity,
            session=SessionIdentity(10, 20),
            trainer_sha256=context.trainer_sha256,
            trainer_arch=context.trainer_arch,
            environment=context.environment,
            umu_run=context.umu_run,
            expected_reentry_bus=context.expected_reentry_bus,
        )

        class CooperativeProvider(_BoundedCooperativeProvider):
            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "enabled"}],
                }

        service = CheatControlService(
            Settings(), Watcher(context), Runner(), catalog=Catalog(), helper_paths={"x86": "/helper.exe"}, cooperative=CooperativeProvider()
        )
        response = await service.get_cheat_controls(IDENTITY)
        self.assertEqual(response["source"], "cooperative")
        self.assertEqual(response["cheats"][0]["state"], "unknown")
        self.assertFalse(response["capabilities"]["authoritativeState"])

    async def test_manual_control_must_bind_to_the_current_running_trainer_hash(self):
        from trainer_relay.cheat_service import CheatControlService

        service = CheatControlService(
            Settings(), Watcher(_context(HASH)), Runner(), catalog=Catalog(), helper_paths={"x86": "/helper.exe"}
        )
        saved = await service.add_manual_cheat_control(
            {
                "identity": IDENTITY,
                "trainerSha256": HASH,
                "label": "Manual health",
                "hotkey": HOTKEY,
            }
        )
        self.assertEqual(saved["trainerSha256"], HASH)

        with self.assertRaisesRegex(Exception, "trainer_hash_changed"):
            await service.add_manual_cheat_control(
                {
                    "identity": IDENTITY,
                    "trainerSha256": OTHER_HASH,
                    "label": "Stale health",
                    "hotkey": HOTKEY,
                }
            )

    async def test_fresh_cooperative_ack_is_the_only_source_of_authoritative_state(self):
        from trainer_relay.cheat_service import CheatControlService

        class CooperativeProvider(_BoundedCooperativeProvider):
            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, command_id, cheat_id, operation):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "capabilityToken": "token",
                    "commandId": command_id,
                    "cheatId": cheat_id,
                    "operation": operation,
                    "accepted": True,
                    "state": "enabled",
                    "revision": 2,
                    "freshUntil": 100.0,
                }

        context = CommandContext(
            identity=IDENTITY,
            session=SessionIdentity(10, 20),
            trainer_sha256=HASH,
            trainer_arch="x86",
            environment={"WINEPREFIX": "/prefix"},
            umu_run="/umu-run",
            expected_reentry_bus="com.example.bus",
        )
        runner = Runner()
        service = CheatControlService(
            Settings(), Watcher(context), runner, catalog=Catalog(), helper_paths={"x86": "/helper.exe"}, cooperative=CooperativeProvider(), clock=lambda: 10.0
        )
        result = await service.send_cheat_command(IDENTITY, "health")
        self.assertEqual(result["outcome"], "requested")
        self.assertEqual(result["state"], "enabled")
        self.assertEqual(runner.calls, [])

    async def test_adapter_architecture_must_match_the_revalidated_trainer_architecture(self):
        from trainer_relay.cheat_service import CheatControlService

        mismatch = AdapterDescriptor(
            adapter_id="x64-adapter",
            sha256=HASH,
            pe_architecture="x64",
            trainer_label="Wrong architecture",
            supported_identities=(IDENTITY,),
            cheats=(_cheat(),),
            disable_all_hotkey={"modifiers": [], "key": "HOME"},
        )
        runner = Runner()
        service = CheatControlService(
            Settings(), Watcher(_context()), runner, catalog=Catalog(mismatch), helper_paths={"x86": "/helper.exe", "x64": "/helper64.exe"}
        )
        result = await service.send_cheat_command(IDENTITY, "health")
        self.assertEqual(result["outcome"], "rejected")
        self.assertEqual(result["diagnostic"]["code"], "trainer_architecture_mismatch")
        self.assertEqual(runner.calls, [])

    async def test_cooperative_dataclass_descriptor_is_revalidated_before_controls_are_ready(self):
        from trainer_relay.cheat_service import CheatControlService
        from trainer_relay.cooperative import CooperativeCheatDescriptor, CooperativeDescriptor

        context = CommandContext(
            identity=IDENTITY,
            session=SessionIdentity(10, 20),
            trainer_sha256=HASH,
            trainer_arch="x86",
            environment={"WINEPREFIX": "/prefix"},
            umu_run="/umu-run",
            expected_reentry_bus="com.example.bus",
        )
        forged = CooperativeDescriptor(
            IDENTITY,
            HASH,
            {"pid": 10, "startTime": 20},
            {"transport": "tcp", "address": "127.0.0.1"},
            "token",
            1,
            ("toggle",),
            (CooperativeCheatDescriptor("health", "Health", ("toggle",), "enabled"),),
        )

        class CooperativeProvider(_BoundedCooperativeProvider):
            def descriptor_for(self, _context):
                return forged

        service = CheatControlService(
            Settings(), Watcher(context), Runner(), catalog=Catalog(), cooperative=CooperativeProvider()
        )
        response = await service.get_cheat_controls(IDENTITY)
        self.assertNotEqual(response["status"], "ready")

    async def test_cooperative_dataclass_ack_cannot_authorize_unvalidated_state(self):
        from trainer_relay.cheat_service import CheatControlService
        from trainer_relay.cooperative import CooperativeAck

        class CooperativeProvider(_BoundedCooperativeProvider):
            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, command_id, cheat_id, operation):
                return CooperativeAck(
                    IDENTITY,
                    HASH,
                    {"pid": 10, "startTime": 20},
                    command_id,
                    cheat_id,
                    operation,
                    True,
                    "enabled",
                    2,
                    100.0,
                    True,
                )

        context = CommandContext(
            identity=IDENTITY,
            session=SessionIdentity(10, 20),
            trainer_sha256=HASH,
            trainer_arch="x86",
            environment={"WINEPREFIX": "/prefix"},
            umu_run="/umu-run",
            expected_reentry_bus="com.example.bus",
        )
        service = CheatControlService(
            Settings(), Watcher(context), Runner(), catalog=Catalog(), cooperative=CooperativeProvider(), helper_paths={"x86": "/helper.exe"}, clock=lambda: 10.0
        )
        result = await service.send_cheat_command(IDENTITY, "health")
        self.assertNotEqual(result["state"], "enabled")

    async def test_fresh_negative_cooperative_ack_has_bounded_rejection_diagnostic(self):
        from trainer_relay.cheat_service import CheatControlService

        class CooperativeProvider(_BoundedCooperativeProvider):
            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, command_id, cheat_id, operation):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "capabilityToken": "token",
                    "commandId": command_id,
                    "cheatId": cheat_id,
                    "operation": operation,
                    "accepted": False,
                    "state": "unknown",
                    "revision": 2,
                    "freshUntil": 100.0,
                }

        context = CommandContext(
            identity=IDENTITY,
            session=SessionIdentity(10, 20),
            trainer_sha256=HASH,
            trainer_arch="x86",
            environment={"WINEPREFIX": "/prefix"},
            umu_run="/umu-run",
            expected_reentry_bus="com.example.bus",
        )
        service = CheatControlService(
            Settings(), Watcher(context), Runner(), catalog=Catalog(), cooperative=CooperativeProvider(), clock=lambda: 10.0
        )
        result = await service.send_cheat_command(IDENTITY, "health")
        self.assertEqual(result["outcome"], "rejected")
        self.assertEqual(result["diagnostic"], {"code": "cooperative_command_rejected"})

    async def test_cooperative_dispatch_holds_authority_lease_through_send_and_ack(self):
        from trainer_relay.cheat_service import CheatControlService

        context = _cooperative_context()
        events = []

        class LeaseWatcher(Watcher):
            def __init__(self):
                super().__init__(context)
                self.lease_active = False

            @contextmanager
            def command_context_lease(self, identity):
                events.append("enter")
                self.lease_active = True
                try:
                    yield self.context
                finally:
                    self.lease_active = False
                    events.append("exit")

        watcher = LeaseWatcher()

        class CooperativeProvider(_BoundedCooperativeProvider):
            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, command_id, cheat_id, operation):
                events.append("send")
                if not watcher.lease_active:
                    raise AssertionError("cooperative send escaped authority lease")
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "capabilityToken": "token",
                    "commandId": command_id,
                    "cheatId": cheat_id,
                    "operation": operation,
                    "accepted": True,
                    "state": "enabled",
                    "revision": 2,
                    "freshUntil": 100.0,
                }

        service = CheatControlService(
            Settings(), watcher, Runner(), catalog=Catalog(), cooperative=CooperativeProvider(), clock=lambda: 10.0
        )

        result = await service.send_cheat_command(IDENTITY, "health")

        self.assertEqual(result["state"], "enabled")
        self.assertEqual(events, ["enter", "send", "exit"])

    async def test_stale_cooperative_ack_falls_back_to_independent_adapter_command(self):
        from trainer_relay.cheat_service import CheatControlService

        class CooperativeProvider(_BoundedCooperativeProvider):
            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, command_id, cheat_id, operation):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "capabilityToken": "token",
                    "commandId": command_id,
                    "cheatId": cheat_id,
                    "operation": operation,
                    "accepted": True,
                    "state": "enabled",
                    "revision": 2,
                    "freshUntil": 10.0,
                }

        runner = Runner()
        service = CheatControlService(
            Settings(),
            Watcher(_cooperative_context()),
            runner,
            catalog=Catalog(_adapter()),
            cooperative=CooperativeProvider(),
            helper_paths={"x86": "/helper.exe"},
            clock=lambda: 10.1,
        )

        result = await service.send_cheat_command(IDENTITY, "health")

        self.assertEqual(result["outcome"], "requested")
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["diagnostic"], {"code": "cooperative_ack_stale"})
        self.assertEqual(len(runner.calls), 0)

    async def test_malformed_cooperative_ack_after_send_never_falls_back_to_helper(self):
        from trainer_relay.cheat_service import CheatControlService

        class CooperativeProvider(_BoundedCooperativeProvider):
            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, _command_id, _cheat_id, _operation):
                return {"malformed": True}

        runner = Runner()
        service = CheatControlService(
            Settings(),
            Watcher(_cooperative_context()),
            runner,
            catalog=Catalog(_adapter()),
            cooperative=CooperativeProvider(),
            helper_paths={"x86": "/helper.exe"},
        )

        result = await service.send_cheat_command(IDENTITY, "health")

        self.assertEqual(result["outcome"], "requested")
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["diagnostic"], {"code": "cooperative_ack_non_authoritative"})
        self.assertEqual(runner.calls, [])

    async def test_cooperative_provider_without_bounded_contract_is_rejected_before_send(self):
        from trainer_relay.cheat_service import CheatControlService

        class CooperativeProvider:
            def __init__(self):
                self.send_calls = 0

            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, _command_id, _cheat_id, _operation):
                self.send_calls += 1
                raise AssertionError("ineligible cooperative provider was invoked")

        provider = CooperativeProvider()
        runner = Runner()
        service = CheatControlService(
            Settings(),
            Watcher(_cooperative_context()),
            runner,
            catalog=Catalog(_adapter()),
            cooperative=provider,
            helper_paths={"x86": "/helper.exe"},
        )

        result = await service.send_cheat_command(IDENTITY, "health")

        self.assertEqual(result["outcome"], "rejected")
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["diagnostic"], {"code": "cooperative_provider_ineligible"})
        self.assertEqual(provider.send_calls, 0)
        self.assertEqual(runner.calls, [])

    async def test_overflowing_cooperative_deadlines_are_rejected_before_send(self):
        from trainer_relay.cheat_service import CheatControlService

        for overflowing_field in ("deadline_seconds", "cancel_deadline_seconds"):
            with self.subTest(field=overflowing_field):
                class CooperativeProvider:
                    cooperative_command_contract = {
                        "deadline_seconds": 0.1,
                        "cancel_deadline_seconds": 0.1,
                        overflowing_field: 10**1000,
                    }

                    def __init__(self):
                        self.send_calls = 0

                    def descriptor_for(self, _context):
                        return {
                            "protocol": "TrainerRelay Cooperative Control v1",
                            "schemaVersion": 1,
                            "identity": IDENTITY,
                            "trainerSha256": HASH,
                            "session": {"pid": 10, "startTime": 20},
                            "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                            "capabilityToken": "token",
                            "revision": 1,
                            "operations": ["toggle"],
                            "cheats": [
                                {"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}
                            ],
                        }

                    def send_command(self, _descriptor, _command_id, _cheat_id, _operation):
                        self.send_calls += 1
                        raise AssertionError("overflowing cooperative provider was invoked")

                    def cancel_command(self, _descriptor, _command_id):
                        raise AssertionError("overflowing cooperative provider was cancelled")

                provider = CooperativeProvider()
                runner = Runner()
                service = CheatControlService(
                    Settings(),
                    Watcher(_cooperative_context()),
                    runner,
                    catalog=Catalog(_adapter()),
                    cooperative=provider,
                    helper_paths={"x86": "/helper.exe"},
                )

                result = await service.send_cheat_command(IDENTITY, "health")

                self.assertEqual(result["outcome"], "rejected")
                self.assertEqual(result["state"], "unknown")
                self.assertEqual(result["diagnostic"], {"code": "cooperative_provider_ineligible"})
                self.assertEqual(provider.send_calls, 0)
                self.assertEqual(runner.calls, [])

    async def test_unload_fails_closed_when_cooperative_worker_ignores_cancel(self):
        from trainer_relay.cheat_service import CheatControlService, CheatServiceError

        class IgnoringProvider:
            cooperative_command_contract = {"deadline_seconds": 0.02, "cancel_deadline_seconds": 0.02}

            def __init__(self):
                self.started = threading.Event()
                self.released = threading.Event()
                self.finished = threading.Event()
                self.cancel_calls = 0

            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, _command_id, _cheat_id, _operation):
                self.started.set()
                self.released.wait(4)
                self.finished.set()
                return {"malformed": True}

            def cancel_command(self, _descriptor, _command_id):
                self.cancel_calls += 1

        provider = IgnoringProvider()
        service = CheatControlService(Settings(), Watcher(_cooperative_context()), Runner(), cooperative=provider)
        dispatch = asyncio.create_task(service.send_cheat_command(IDENTITY, "health"))
        self.assertTrue(await asyncio.to_thread(provider.started.wait, 1))

        with self.assertRaises(CheatServiceError) as error:
            await service.close()

        self.assertEqual(error.exception.code, "cooperative_worker_drain_failed")
        self.assertGreaterEqual(provider.cancel_calls, 1)
        self.assertFalse(provider.finished.is_set())
        self.assertTrue(any(not worker.done() for worker in service._cooperative_workers))

        provider.released.set()
        await asyncio.wait_for(dispatch, 1)
        await asyncio.wait_for(service.close(), 1)

    async def test_cancelled_cooperative_coroutine_keeps_worker_owned_until_close_drains_it(self):
        from trainer_relay.cheat_service import CheatControlService

        class CooperativeProvider(_BoundedCooperativeProvider):
            def __init__(self):
                self.started = threading.Event()
                self.released = threading.Event()
                self.finished = threading.Event()
                self.cancel_calls = 0

            def descriptor_for(self, _context):
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": {"pid": 10, "startTime": 20},
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": 1,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

            def send_command(self, _descriptor, _command_id, _cheat_id, _operation):
                self.started.set()
                self.released.wait(2)
                self.finished.set()
                return {"malformed": True}

            def cancel_command(self, _descriptor, _command_id):
                self.cancel_calls += 1
                self.released.set()

        provider = CooperativeProvider()
        service = CheatControlService(
            Settings(), Watcher(_cooperative_context()), Runner(), cooperative=provider
        )
        dispatch = asyncio.create_task(service.send_cheat_command(IDENTITY, "health"))
        await asyncio.to_thread(provider.started.wait, 1)

        dispatch.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await dispatch

        self.assertFalse(provider.finished.is_set())
        await service.close()

        self.assertEqual(provider.cancel_calls, 1)
        self.assertTrue(provider.finished.is_set())

    async def test_cooperative_revision_regression_is_rejected_per_session_binding(self):
        from trainer_relay.cheat_service import CheatControlService

        class CooperativeProvider:
            def __init__(self):
                self.revisions = iter((2, 1))

            def descriptor_for(self, context):
                revision = next(self.revisions)
                session = {"pid": context.session.pid, "startTime": context.session.start_time}
                return {
                    "protocol": "TrainerRelay Cooperative Control v1",
                    "schemaVersion": 1,
                    "identity": IDENTITY,
                    "trainerSha256": HASH,
                    "session": session,
                    "endpoint": {"transport": "unix", "address": "@trainer-relay-test"},
                    "capabilityToken": "token",
                    "revision": revision,
                    "operations": ["toggle"],
                    "cheats": [{"id": "health", "label": "Health", "operations": ["toggle"], "state": "unknown"}],
                }

        watcher = Watcher(_cooperative_context())
        service = CheatControlService(
            Settings(), watcher, Runner(), catalog=Catalog(), cooperative=CooperativeProvider()
        )

        first = await service.get_cheat_controls(IDENTITY)
        second = await service.get_cheat_controls(IDENTITY)

        self.assertEqual(first["source"], "cooperative")
        self.assertNotEqual(second["status"], "ready")

    async def test_catalog_and_diagnostic_recording_leave_the_event_loop(self):
        from trainer_relay import cheat_service as module
        from trainer_relay.cheat_service import CheatControlService

        caller_thread = threading.get_ident()
        catalog_threads = []
        diagnostic_threads = []

        class Diagnostics:
            def record(self, *_args, **_kwargs):
                diagnostic_threads.append(threading.get_ident())

        def load_catalog():
            catalog_threads.append(threading.get_ident())
            return Catalog(_adapter())

        with patch.object(module, "load_packaged_catalog", side_effect=load_catalog):
            service = CheatControlService(
                Settings(), Watcher(_context()), Runner(), diagnostics=Diagnostics()
            )
            response = await service.get_cheat_controls(IDENTITY)

        self.assertEqual(response["status"], "ready")
        self.assertTrue(catalog_threads)
        self.assertTrue(diagnostic_threads)
        self.assertNotEqual(catalog_threads[0], caller_thread)
        self.assertNotEqual(diagnostic_threads[0], caller_thread)

    async def test_concurrent_manual_mutations_are_serialized_per_identity(self):
        from trainer_relay.cheat_service import CheatControlService

        class SlowSettings(Settings):
            def getSetting(self, key, default):
                time.sleep(0.03)
                return copy.deepcopy(super().getSetting(key, default))

        service = CheatControlService(
            SlowSettings(), Watcher(_context()), Runner(), catalog=Catalog(), helper_paths={"x86": "/helper.exe"}
        )
        first = asyncio.create_task(
            service.add_manual_cheat_control(IDENTITY, HASH, "First", {"modifiers": [], "key": "F1"})
        )
        second = asyncio.create_task(
            service.add_manual_cheat_control(IDENTITY, HASH, "Second", {"modifiers": [], "key": "F2"})
        )

        await asyncio.gather(first, second)

        self.assertEqual(len(service._load_sync()["games"][IDENTITY]["cheats"]), 2)

    async def test_close_cancels_and_drains_a_running_dispatch(self):
        from trainer_relay.cheat_service import CheatControlService

        class CancellableRunner(Runner):
            def __init__(self):
                super().__init__(block=True)
                self.cancel_calls = 0

            def cancel_all(self):
                self.cancel_calls += 1
                self.release.set()

        runner = CancellableRunner()
        service = CheatControlService(
            Settings(), Watcher(_context()), runner, catalog=Catalog(_adapter()), helper_paths={"x86": "/helper.exe"}
        )
        dispatch = asyncio.create_task(service.send_cheat_command(IDENTITY, "health"))
        await asyncio.to_thread(runner.started.wait, 1)

        await service.close()
        result = await dispatch

        self.assertEqual(runner.cancel_calls, 1)
        self.assertIn(result["outcome"], {"requested", "failed", "rejected"})


if __name__ == "__main__":
    unittest.main()
