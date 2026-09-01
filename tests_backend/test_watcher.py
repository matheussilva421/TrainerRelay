import asyncio
import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from trainer_relay.container_reentry import ContainerReentryError
from trainer_relay.games_map import GamesMapDiagnostic, GamesMapEntry, GamesMapResult
from trainer_relay.process import CandidateDecision, DiscoveryResult, ProcessDiscoverer, SessionIdentity
from trainer_relay.runner import StopResult
from trainer_relay.types import CommandContext, RelayStatus
from trainer_relay.umu import UmuResolution
from trainer_relay.watcher import RelayWatcher


class FakeRunner:
    def __init__(self):
        self.handles = []
        self.spawn_calls = []
        self.stop_calls = []
        self.expected_reentry_buses = []

    @property
    def owned(self):
        return tuple(self.handles)

    def spawn(self, session, trainer_executable, environment, *, expected_reentry_bus=None):
        handle = {
            "session": session,
            "exit_code": None,
            "process_group_id": 999,
            "reentry_status": "confirmed",
            "reentry_observed_at": 0.0,
        }
        self.handles.append(handle)
        self.spawn_calls.append((session, trainer_executable, environment))
        self.expected_reentry_buses.append(expected_reentry_bus)
        return handle

    def poll(self, handle):
        return handle["exit_code"]

    def reentry_status(self, handle, *, wait_seconds=0.0):
        return handle["reentry_status"]

    def reentry_observed_at(self, handle, status):
        return handle["reentry_observed_at"]

    def stop(self, handle):
        self.stop_calls.append(handle)
        return StopResult(forced=False)

    def exit_diagnostics(self, handle):
        return handle.get("exit_diagnostics")

    def forget(self, handle):
        return None


class FakeRecorder:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.calls = []

    def record(self, category, event, outcome, **kwargs):
        self.calls.append({"category": category, "event": event, "outcome": outcome, **kwargs})

    def flush(self):
        return None


class FakeDiscoverer:
    def __init__(self, result):
        self.result = result
        self.expected_sessions = []

    def discover(self, identity, executable, prefix, *, expected_session=None):
        self.expected_sessions.append(expected_session)
        return self.result


class FakeContainerProbe:
    def __init__(self, error=None, session_environment=None, launch_environment=None):
        self.error = error
        self.calls = []
        self.session_environment = session_environment or {
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "XDG_RUNTIME_DIR": "/run/user/1000",
        }
        self.launch_environment = launch_environment or {
            "HOME": "/home/deck",
            "PATH": "/usr/bin:/bin",
            **self.session_environment,
        }

    async def verify(self, environment):
        self.calls.append(environment)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            bus_name="com.steampowered.Appabc",
            runtime_variant="steamrt3",
            attempts=1,
            bus_source="home_owner_runtime",
            app_id_source="computed",
            session_environment=self.session_environment,
            launch_environment=self.launch_environment,
        )


class WatcherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.trainer = root / "trainer.exe"
        trainer_bytes = bytearray(0x100)
        trainer_bytes[:2] = b"MZ"
        trainer_bytes[0x3C:0x40] = (0x80).to_bytes(4, "little")
        trainer_bytes[0x80:0x84] = b"PE\0\0"
        trainer_bytes[0x84:0x86] = (0x14C).to_bytes(2, "little")
        self.trainer.write_bytes(trainer_bytes)
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
        self.container_probe = FakeContainerProbe()
        self.watcher = RelayWatcher(
            {"schemaVersion": 1, "games": {self.identity: {"enabled": True, "trainerPath": str(self.trainer)}}},
            games_map_path="/games.map",
            map_loader=lambda _: self.map_result,
            process_discoverer=self.discoverer,
            umu_resolver=lambda: UmuResolution(Path("/umu-run"), "bundled"),
            container_probe=self.container_probe,
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
        self.assertEqual(self.runner.expected_reentry_buses, ["com.steampowered.Appabc"])
        self.assertEqual(
            [call["event"] for call in self.recorder.calls],
            [
                "games_map_loaded",
                "prefix_selected",
                "process_scan_summary",
                "candidate_accepted",
                "umu_resolved",
                "container_reentry_verified",
                "trainer_spawned",
                "games_map_loaded",
                "prefix_selected",
                "process_scan_summary",
                "candidate_accepted",
                "container_reentry_confirmed",
                "trainer_running",
            ],
        )
        self.assertEqual(self.recorder.calls[3]["session"].to_wire(), {"pid": 10, "startTime": 20})
        self.assertEqual(self.discoverer.expected_sessions, [None, self.session])

    async def test_spawn_replaces_private_game_runtime_roots_with_the_verified_host_context(self):
        self.discovery.environment.update(
            {
                "HOME": "/run/pressure-vessel/private-home",
                "PATH": "/run/pressure-vessel/bin",
                "XDG_DATA_HOME": "/run/pressure-vessel/private-data",
                "UMU_FOLDERS_PATH": "/run/pressure-vessel/private-folders",
            }
        )
        self.container_probe.launch_environment = {
            "HOME": "/home/deck",
            "PATH": "/usr/bin:/bin",
            "XDG_DATA_HOME": "/home/deck/.local/share",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "XDG_RUNTIME_DIR": "/run/user/1000",
        }

        await self.watcher.poll_once()

        launch_environment = self.runner.spawn_calls[0][2]
        self.assertEqual(launch_environment["HOME"], "/home/deck")
        self.assertEqual(launch_environment["PATH"], "/usr/bin:/bin")
        self.assertEqual(launch_environment["XDG_DATA_HOME"], "/home/deck/.local/share")
        self.assertNotIn("UMU_FOLDERS_PATH", launch_environment)

    async def test_real_proc_session_survives_main_thread_rename_until_running(self):
        root = Path(self.directory.name)
        proc_root = root / "proc"
        process = proc_root / "57719"
        process.mkdir(parents=True)
        stat = "57719 (Bioshock2HD.exe) S " + " ".join(["0"] * 18) + " 2457048 0 0"
        (process / "stat").write_text(stat, encoding="utf-8")
        (process / "comm").write_text("Bioshock2HD.exe\n", encoding="utf-8")
        expected_executable = "/games/Bioshock2HD.exe"
        (process / "cmdline").write_bytes(b"wine\0" + expected_executable.encode() + b"\0")
        (process / "environ").write_bytes(
            b"\0".join(
                (
                    f"WINEPREFIX={self.prefix}".encode(),
                    b"PROTONPATH=/proton",
                    b"GAMEID=umu-0",
                    b"STORE=gog",
                    b"UMU_CONTAINER_NSENTER=1",
                )
            )
            + b"\0"
        )
        entry = GamesMapEntry(self.identity, expected_executable)
        watcher = RelayWatcher(
            {
                "schemaVersion": 1,
                "games": {
                    self.identity: {
                        "enabled": True,
                        "trainerPath": str(self.trainer),
                        "prefixOverride": str(self.prefix),
                    }
                },
            },
            games_map_path="/games.map",
            map_loader=lambda _: GamesMapResult({self.identity: entry}),
            process_discoverer=ProcessDiscoverer(proc_root),
            umu_resolver=lambda: UmuResolution(Path("/umu-run"), "bundled"),
            container_probe=self.container_probe,
            runner=self.runner,
            home="/home/deck",
            clock=lambda: self.clock_value,
            diagnostics=self.recorder,
        )

        await watcher.poll_once()
        self.assertEqual(watcher.status(self.identity)["state"], "launching")

        (process / "comm").write_text("Main Game Threa\n", encoding="utf-8")
        (process / "stat").write_text(
            "57719 (Main Game Threa) S " + " ".join(["0"] * 18) + " 2457048 0 0",
            encoding="utf-8",
        )
        self.clock_value = 3.0
        await watcher.poll_once()

        self.assertEqual(watcher.status(self.identity)["state"], "running")
        self.assertEqual(len(self.runner.spawn_calls), 1)
        self.assertEqual(self.runner.stop_calls, [])
        events = [call["event"] for call in self.recorder.calls]
        self.assertIn("candidate_revalidated", events)
        self.assertNotIn("session_ended", events)

    async def test_spawn_rebuilds_umu_root_from_proton_child_wineprefix(self):
        child_prefix = self.prefix / "pfx"
        self.discoverer.result = DiscoveryResult(
            "session",
            session=self.session,
            environment={
                "WINEPREFIX": str(child_prefix),
                "STEAM_COMPAT_DATA_PATH": str(self.prefix),
                "PROTONPATH": "/proton",
                "GAMEID": "umu-0",
                "STORE": "gog",
            },
        )

        await self.watcher.poll_once()

        launch_environment = self.runner.spawn_calls[0][2]
        self.assertEqual(launch_environment["WINEPREFIX"], "/home/deck/.local/share/unifideck/prefixes/game")
        self.assertEqual(
            launch_environment["STEAM_COMPAT_DATA_PATH"], "/home/deck/.local/share/unifideck/prefixes/game"
        )
        self.assertEqual(launch_environment["PROTON_VERB"], "runinprefix")

    async def test_spawn_normalizes_prefix_override_that_points_at_pfx(self):
        child_prefix = self.prefix / "pfx"
        child_prefix.mkdir()
        discovery = DiscoveryResult(
            "session",
            session=self.session,
            environment={
                "WINEPREFIX": str(child_prefix),
                "STEAM_COMPAT_DATA_PATH": str(self.prefix),
                "PROTONPATH": "/proton",
                "GAMEID": "umu-0",
                "STORE": "gog",
            },
        )
        watcher = RelayWatcher(
            {
                "schemaVersion": 1,
                "games": {
                    self.identity: {
                        "enabled": True,
                        "trainerPath": str(self.trainer),
                        "prefixOverride": str(child_prefix),
                    }
                },
            },
            games_map_path="/games.map",
            map_loader=lambda _: self.map_result,
            process_discoverer=FakeDiscoverer(discovery),
            umu_resolver=lambda: UmuResolution(Path("/umu-run"), "bundled"),
            container_probe=self.container_probe,
            runner=self.runner,
            home="/home/deck",
            clock=lambda: self.clock_value,
            diagnostics=self.recorder,
        )

        await watcher.poll_once()

        launch_environment = self.runner.spawn_calls[0][2]
        self.assertEqual(launch_environment["WINEPREFIX"], str(self.prefix))
        self.assertEqual(launch_environment["STEAM_COMPAT_DATA_PATH"], str(self.prefix))

    async def test_default_game_id_named_pfx_remains_the_umu_root(self):
        identity = "gog:pfx"
        entry = GamesMapEntry(identity, "/games/game.exe")
        session = SessionIdentity(12, 22)
        discovery = DiscoveryResult(
            "session",
            session=session,
            environment={
                "WINEPREFIX": "/home/deck/.local/share/unifideck/prefixes/pfx/pfx",
                "STEAM_COMPAT_DATA_PATH": "/home/deck/.local/share/unifideck/prefixes/pfx",
                "PROTONPATH": "/proton",
                "GAMEID": "umu-0",
                "STORE": "gog",
            },
        )
        watcher = RelayWatcher(
            {"schemaVersion": 1, "games": {identity: {"enabled": True, "trainerPath": str(self.trainer)}}},
            games_map_path="/games.map",
            map_loader=lambda _: GamesMapResult({identity: entry}),
            process_discoverer=FakeDiscoverer(discovery),
            umu_resolver=lambda: UmuResolution(Path("/umu-run"), "bundled"),
            container_probe=self.container_probe,
            runner=self.runner,
            home="/home/deck",
            clock=lambda: self.clock_value,
            diagnostics=self.recorder,
        )

        await watcher.poll_once()

        launch_environment = self.runner.spawn_calls[0][2]
        self.assertEqual(launch_environment["WINEPREFIX"], "/home/deck/.local/share/unifideck/prefixes/pfx")
        self.assertEqual(
            launch_environment["STEAM_COMPAT_DATA_PATH"], "/home/deck/.local/share/unifideck/prefixes/pfx"
        )

    async def test_prefix_override_preserves_posix_root(self):
        watcher = RelayWatcher(
            {
                "schemaVersion": 1,
                "games": {
                    self.identity: {
                        "enabled": True,
                        "trainerPath": str(self.trainer),
                        "prefixOverride": "/",
                    }
                },
            },
            games_map_path="/games.map",
            map_loader=lambda _: self.map_result,
            process_discoverer=FakeDiscoverer(self.discovery),
            umu_resolver=lambda: UmuResolution(Path("/umu-run"), "bundled"),
            container_probe=self.container_probe,
            runner=self.runner,
            home="/home/deck",
            clock=lambda: self.clock_value,
            diagnostics=self.recorder,
        )

        await watcher.poll_once()

        launch_environment = self.runner.spawn_calls[0][2]
        self.assertEqual(launch_environment["WINEPREFIX"], "/")
        self.assertEqual(launch_environment["STEAM_COMPAT_DATA_PATH"], "/")

    async def test_spawn_diagnostic_records_effective_umu_environment_shape(self):
        await self.watcher.poll_once()

        spawned = next(call for call in self.recorder.calls if call["event"] == "trainer_spawned")
        self.assertEqual(
            {
                "wineprefix": spawned["details"]["wineprefix"],
                "steam_compat_data_path": spawned["details"]["steam_compat_data_path"],
                "proton_verb": spawned["details"]["proton_verb"],
                "container_reentry": spawned["details"]["container_reentry"],
            },
            {
                "wineprefix": "/home/deck/.local/share/unifideck/prefixes/game",
                "steam_compat_data_path": "/home/deck/.local/share/unifideck/prefixes/game",
                "proton_verb": "runinprefix",
                "container_reentry": "enabled",
            },
        )

    async def test_fails_closed_before_spawn_when_container_bus_is_missing(self):
        self.watcher._container_probe = FakeContainerProbe(
            ContainerReentryError(
                "container_reentry_bus_missing",
                failure_class="bus_missing",
                exit_code=0,
                bus_source="home_owner_runtime",
                attempts=5,
            )
        )

        await self.watcher.poll_once()

        self.assertEqual(self.runner.spawn_calls, [])
        self.assertEqual(self.watcher.status(self.identity)["state"], "invalid_config")
        self.assertEqual(
            self.watcher.status(self.identity)["diagnostic"],
            {"code": "container_reentry_bus_missing"},
        )
        rejected = next(call for call in self.recorder.calls if call["event"] == "container_reentry_rejected")
        self.assertEqual(
            rejected["details"],
            {
                "reason": "container_reentry_bus_missing",
                "failure_class": "bus_missing",
                "probe_exit_code": 0,
                "bus_source": "home_owner_runtime",
                "attempt_count": 5,
                "service_marker_present": False,
            },
        )

    async def test_validated_host_session_bus_replaces_the_game_container_bus_for_umu(self):
        self.discovery.environment.update(
            {
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/inside-pressure-vessel/bus",
                "XDG_RUNTIME_DIR": "/inside-pressure-vessel",
            }
        )

        await self.watcher.poll_once()

        launch_environment = self.runner.spawn_calls[0][2]
        self.assertEqual(
            launch_environment["DBUS_SESSION_BUS_ADDRESS"],
            "unix:path=/run/user/1000/bus",
        )
        self.assertEqual(launch_environment["XDG_RUNTIME_DIR"], "/run/user/1000")

    async def test_validated_bus_without_xdg_fails_closed_instead_of_reusing_the_game_runtime_dir(self):
        self.discovery.environment.update(
            {
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/inside-pressure-vessel/bus",
                "XDG_RUNTIME_DIR": "/inside-pressure-vessel",
            }
        )
        self.watcher._container_probe = FakeContainerProbe(
            session_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"}
        )

        await self.watcher.poll_once()

        self.assertEqual(self.runner.spawn_calls, [])
        self.assertEqual(self.watcher.status(self.identity)["state"], "invalid_config")
        self.assertEqual(
            self.watcher.status(self.identity)["diagnostic"],
            {"code": "container_reentry_probe_failed"},
        )

    async def test_failed_preflight_is_latched_for_the_same_session_until_manual_retry(self):
        probe = FakeContainerProbe(ContainerReentryError("container_reentry_probe_failed"))
        self.watcher._container_probe = probe

        await self.watcher.poll_once()
        await self.watcher.poll_once()

        self.assertEqual(len(probe.calls), 1)
        self.assertEqual(self.runner.spawn_calls, [])
        self.assertEqual(self.watcher.status(self.identity)["state"], "invalid_config")

        await self.watcher.retry(self.identity)

        self.assertEqual(len(probe.calls), 2)

    async def test_diagnostic_mode_uses_info_logging_and_records_only_known_runtime_flag_names(self):
        self.discovery.environment.update(
            {
                "STEAM_COMPAT_LAUNCHER_SERVICE": "private-value",
                "UMU_CONTAINER_NSENTER": "1",
                "STEAM_RUNTIME_LIBRARY_PATH": "/private/runtime",
            }
        )

        await self.watcher.poll_once()

        launch_environment = self.runner.spawn_calls[0][2]
        self.assertEqual(launch_environment["UMU_LOG"], "info")
        self.assertNotIn("STEAM_COMPAT_LAUNCHER_SERVICE", launch_environment)
        spawned = next(call for call in self.recorder.calls if call["event"] == "trainer_spawned")
        self.assertEqual(spawned["details"]["environment_key_count"], len(launch_environment))
        self.assertEqual(
            spawned["details"]["runtime_flags"],
            "STEAM_COMPAT_LAUNCHER_SERVICE,STEAM_RUNTIME_LIBRARY_PATH,UMU_CONTAINER_NSENTER",
        )
        self.assertNotIn("private-value", repr(spawned))

    async def test_umu_info_logging_remains_enabled_when_diagnostic_recording_is_disabled(self):
        self.watcher._diagnostics = FakeRecorder(enabled=False)

        await self.watcher.poll_once()

        self.assertEqual(self.runner.spawn_calls[0][2]["UMU_LOG"], "info")

    async def test_does_not_mark_running_until_exact_container_reentry_is_confirmed(self):
        await self.watcher.poll_once()
        self.runner.handles[0]["reentry_status"] = "pending"
        self.clock_value = 2.9

        await self.watcher.poll_once()

        self.assertEqual(self.watcher.status(self.identity)["state"], "launching")
        self.assertNotIn("container_reentry_confirmed", [call["event"] for call in self.recorder.calls])
        self.runner.handles[0]["reentry_status"] = "confirmed"
        self.runner.handles[0]["reentry_observed_at"] = 2.9
        await self.watcher.poll_once()
        self.assertIn("container_reentry_confirmed", [call["event"] for call in self.recorder.calls])
        self.assertEqual(self.watcher.status(self.identity)["state"], "launching")
        self.clock_value = 3.0
        await self.watcher.poll_once()
        self.assertEqual(self.watcher.status(self.identity)["state"], "running")

    async def test_reentry_confirmation_timeout_stops_only_the_owned_group_and_requires_manual_retry(self):
        await self.watcher.poll_once()
        first_handle = self.runner.handles[0]
        first_handle["reentry_status"] = "retrying"
        self.clock_value = 3.0

        await self.watcher.poll_once()

        self.assertEqual(self.runner.stop_calls, [first_handle])
        self.assertEqual(self.watcher.status(self.identity)["state"], "failed")
        self.assertEqual(
            self.watcher.status(self.identity)["diagnostic"],
            {"code": "container_reentry_confirmation_failed"},
        )
        await self.watcher.poll_once()
        self.assertEqual(len(self.runner.spawn_calls), 1)

        await self.watcher.retry(self.identity)

        self.assertEqual(len(self.runner.spawn_calls), 2)

    async def test_reentry_first_observed_after_the_three_second_deadline_is_rejected(self):
        await self.watcher.poll_once()
        handle = self.runner.handles[0]
        handle["reentry_status"] = "confirmed"
        handle["reentry_observed_at"] = 3.001
        self.clock_value = 3.001

        await self.watcher.poll_once()

        self.assertEqual(self.runner.stop_calls, [handle])
        self.assertEqual(self.watcher.status(self.identity)["state"], "failed")
        self.assertEqual(
            self.watcher.status(self.identity)["diagnostic"],
            {"code": "container_reentry_confirmation_failed"},
        )

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

    async def test_premature_exit_records_bounded_umu_diagnostics_before_retry(self):
        await self.watcher.poll_once()
        self.runner.handles[0]["exit_code"] = 1
        self.runner.handles[0]["exit_diagnostics"] = {
            "stdout_bytes": 25,
            "stderr_bytes": 50,
            "stdout_truncated": False,
            "stderr_truncated": True,
            "stdout_tail": "umu stdout",
            "stderr_tail": "wine error",
            "failure_class": "wine",
            "group_member_count": 1,
            "group_member_names": "trainer.exe",
            "observed_descendant_count": 2,
            "observed_descendant_names": "pressure-vessel,wine64",
        }
        self.clock_value = 1.0

        await self.watcher.poll_once()

        diagnostic = next(call for call in self.recorder.calls if call["event"] == "umu_exit_diagnostics")
        self.assertEqual(
            diagnostic["details"],
            {
                "stdout_bytes": 25,
                "stderr_bytes": 50,
                "stdout_truncated": False,
                "stderr_truncated": True,
                "stdout_tail": "umu stdout",
                "stderr_tail": "wine error",
                "failure_class": "wine",
                "group_member_count": 1,
                "group_member_names": "trainer.exe",
                "observed_descendant_count": 2,
                "observed_descendant_names": "pressure-vessel,wine64",
            },
        )
        events = [call["event"] for call in self.recorder.calls]
        self.assertLess(events.index("umu_exit_diagnostics"), events.index("trainer_exited"))

    async def test_exit_after_three_seconds_retries_when_never_observed_running(self):
        await self.watcher.poll_once()
        self.runner.handles[0]["exit_code"] = 1
        self.clock_value = 3.248

        await self.watcher.poll_once()

        self.assertEqual(self.watcher.status(self.identity)["state"], "retrying")
        exited = next(call for call in self.recorder.calls if call["event"] == "trainer_exited")
        self.assertEqual(exited["outcome"], "warning")
        self.assertIn("trainer_retry_scheduled", [call["event"] for call in self.recorder.calls])

    async def test_exit_after_observed_running_does_not_retry_automatically(self):
        await self.watcher.poll_once()
        self.clock_value = 3.0
        await self.watcher.poll_once()
        self.runner.handles[0]["exit_code"] = 1
        self.clock_value = 4.0

        await self.watcher.poll_once()

        self.assertEqual(self.watcher.status(self.identity)["state"], "failed")
        self.assertNotIn("trainer_retry_scheduled", [call["event"] for call in self.recorder.calls])

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
            container_probe=self.container_probe,
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
            container_probe=self.container_probe,
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

    async def _start_running_session(self):
        await self.watcher.poll_once()
        self.clock_value = 3.0
        await self.watcher.poll_once()

    async def test_command_context_returns_an_immutable_revalidated_running_snapshot(self):
        await self._start_running_session()

        context = self.watcher.command_context(self.identity)

        self.assertIsInstance(context, CommandContext)
        self.assertEqual(context.identity, self.identity)
        self.assertEqual(context.session, self.session)
        self.assertEqual(context.trainer_sha256, hashlib.sha256(self.trainer.read_bytes()).hexdigest())
        self.assertEqual(context.trainer_arch, "x86")
        self.assertEqual(context.umu_run, str(Path("/umu-run")))
        self.assertEqual(context.expected_reentry_bus, "com.steampowered.Appabc")
        self.assertEqual(context.environment["PROTON_VERB"], "runinprefix")
        with self.assertRaises(TypeError):
            context.environment["WINEPREFIX"] = "/different"  # type: ignore[index]
        self.assertEqual(self.discoverer.expected_sessions[-1], self.session)

    async def test_command_context_rejects_disabled_and_launching_without_spawning(self):
        with self.assertRaisesRegex(ValueError, "relay_not_running"):
            self.watcher.command_context(self.identity)
        await self.watcher.poll_once()
        with self.assertRaisesRegex(ValueError, "relay_not_running"):
            self.watcher.command_context(self.identity)
        self.assertEqual(len(self.runner.spawn_calls), 1)

    async def test_command_context_rejects_ended_and_recycled_sessions_without_spawning(self):
        await self._start_running_session()
        self.discoverer.result = DiscoveryResult("waiting_for_game")
        with self.assertRaisesRegex(ValueError, "session_ended"):
            self.watcher.command_context(self.identity)
        self.discoverer.result = DiscoveryResult("session", session=SessionIdentity(10, 21), environment=self.discovery.environment)
        with self.assertRaisesRegex(ValueError, "session_recycled"):
            self.watcher.command_context(self.identity)
        self.assertEqual(len(self.runner.spawn_calls), 1)

    async def test_command_context_rejects_trainer_that_is_no_longer_owned(self):
        await self._start_running_session()
        self.runner.handles.clear()
        with self.assertRaisesRegex(ValueError, "trainer_not_owned"):
            self.watcher.command_context(self.identity)
        self.assertEqual(len(self.runner.spawn_calls), 1)

    async def test_retry_same_session_preserves_session_prefix_for_command_context(self):
        await self.watcher.poll_once()
        self.runner.handles[0]["exit_code"] = 1
        self.clock_value = 1.0
        await self.watcher.poll_once()
        self.clock_value = 3.0
        await self.watcher.poll_once()
        self.clock_value = 6.0
        await self.watcher.poll_once()

        context = self.watcher.command_context(self.identity)

        self.assertEqual(context.session, self.session)
        self.assertEqual(context.environment["WINEPREFIX"], self.runner.spawn_calls[1][2]["WINEPREFIX"])

    async def test_watcher_context_lease_blocks_mutation_until_popen_returns(self):
        await self._start_running_session()
        state = self.watcher._states[self.identity]
        lease_ready = threading.Event()
        release_lease = threading.Event()

        def hold_lease():
            with self.watcher.command_context_lease(self.identity) as context:
                self.assertEqual(context.session, self.session)
                lease_ready.set()
                release_lease.wait(1.0)

        lease_thread = threading.Thread(target=hold_lease)
        lease_thread.start()
        self.assertTrue(lease_ready.wait(1.0))

        mutation_started = threading.Event()
        mutation_finished = threading.Event()

        def mutate_state():
            mutation_started.set()
            self.watcher._set_state(state, RelayStatus.FAILED, "during_popen")
            mutation_finished.set()

        mutation_thread = threading.Thread(target=mutate_state)
        mutation_thread.start()
        self.assertTrue(mutation_started.wait(1.0))
        await asyncio.sleep(0.02)
        self.assertFalse(mutation_finished.is_set())

        release_lease.set()
        await asyncio.to_thread(lease_thread.join, 1.0)
        await asyncio.to_thread(mutation_thread.join, 1.0)
        self.assertTrue(mutation_finished.is_set())
        self.assertEqual(state.state, RelayStatus.FAILED)

    async def test_watcher_mutation_started_during_popen_waits_for_context_lease(self):
        await self._start_running_session()
        state = self.watcher._states[self.identity]
        popen_started = threading.Event()
        popen_release = threading.Event()
        mutation_finished = threading.Event()

        def popen():
            with self.watcher.command_context_lease(self.identity):
                popen_started.set()

                def mutate_state():
                    self.watcher._set_state(state, RelayStatus.FAILED, "during_popen")
                    mutation_finished.set()

                mutation_thread = threading.Thread(target=mutate_state)
                mutation_thread.start()
                self.assertFalse(mutation_finished.wait(0.02))
                popen_release.wait(1.0)
            mutation_thread.join(1.0)

        popen_thread = threading.Thread(target=popen)
        popen_thread.start()
        self.assertTrue(popen_started.wait(1.0))
        popen_release.set()
        await asyncio.to_thread(popen_thread.join, 1.0)
        self.assertTrue(mutation_finished.is_set())
        self.assertEqual(state.state, RelayStatus.FAILED)

    async def test_poll_once_waits_for_context_lease_without_blocking_event_loop(self):
        await self._start_running_session()
        lease_ready = threading.Event()
        release_lease = threading.Event()

        def hold_lease():
            with self.watcher.command_context_lease(self.identity):
                lease_ready.set()
                release_lease.wait(1.0)

        lease_thread = threading.Thread(target=hold_lease)
        lease_thread.start()
        self.assertTrue(lease_ready.wait(1.0))

        poll_task = asyncio.create_task(self.watcher.poll_once())
        await asyncio.sleep(0.02)
        self.assertFalse(poll_task.done())

        release_lease.set()
        await asyncio.to_thread(lease_thread.join, 1.0)
        await asyncio.wait_for(poll_task, 1.0)

    async def test_command_context_rejects_ambiguous_discovery_changed_hash_prefix_and_bus(self):
        await self._start_running_session()

        self.discoverer.result = DiscoveryResult("ambiguous", candidates=(self.session, SessionIdentity(11, 21)))
        with self.assertRaisesRegex(ValueError, "multiple_game_sessions"):
            self.watcher.command_context(self.identity)

        self.discoverer.result = self.discovery
        original_trainer = self.trainer.read_bytes()
        changed = bytearray(self.trainer.read_bytes())
        changed[-1] ^= 1
        self.trainer.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "trainer_hash_changed"):
            self.watcher.command_context(self.identity)

        self.trainer.write_bytes(original_trainer)
        self.discovery.environment["WINEPREFIX"] = "/other-prefix"
        with self.assertRaisesRegex(ValueError, "prefix_mismatch"):
            self.watcher.command_context(self.identity)

        self.discovery.environment["WINEPREFIX"] = str(self.prefix)
        self.watcher._states[self.identity].expected_reentry_bus = None
        with self.assertRaisesRegex(ValueError, "container_reentry_bus_missing"):
            self.watcher.command_context(self.identity)
        self.assertEqual(len(self.runner.spawn_calls), 1)


if __name__ == "__main__":
    unittest.main()
