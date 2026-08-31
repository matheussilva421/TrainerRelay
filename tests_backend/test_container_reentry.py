import asyncio
import hashlib
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from trainer_relay.container_reentry import ContainerReentryError, ContainerReentryProbe


class ContainerReentryProbeTests(unittest.TestCase):
    def _layout(self, root: Path) -> tuple[Path, Path]:
        proton = root / "GE-Proton"
        proton.mkdir()
        (proton / "toolmanifest.vdf").write_text(
            '"manifest"\n{\n\t"require_tool_appid" "1628350"\n}\n',
            encoding="utf-8",
        )
        launch_client = root / ".local" / "share" / "umu" / "steamrt3" / "pressure-vessel" / "bin" / "steam-runtime-launch-client"
        launch_client.parent.mkdir(parents=True)
        launch_client.write_text("client", encoding="utf-8")
        launch_client.chmod(launch_client.stat().st_mode | stat.S_IXUSR)
        return proton, launch_client

    def test_verifies_the_exact_same_prefix_bus_with_structured_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, launch_client = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            bus = "com.steampowered.App" + hashlib.md5(str(prefix.resolve()).encode(), usedforsecurity=False).hexdigest()
            calls = []
            host_bus = "unix:path=/run/user/1000/bus"

            def run(argv, **kwargs):
                calls.append((argv, kwargs))
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=run,
                    sleep=lambda _: None,
                    host_environment={
                        "HOME": str(root),
                        "DBUS_SESSION_BUS_ADDRESS": host_bus,
                        "XDG_RUNTIME_DIR": "/run/user/1000",
                    },
                    target_uid=1000,
                    getuid=lambda: 0,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/inside-pressure-vessel/bus",
                        "XDG_RUNTIME_DIR": "/inside-pressure-vessel",
                    }
                )
            )

            self.assertEqual(result.bus_name, bus)
            self.assertEqual(result.runtime_variant, "steamrt3")
            self.assertEqual(result.attempts, 1)
            self.assertEqual(result.bus_source, "host_environment")
            self.assertEqual(result.app_id_source, "computed")
            self.assertEqual(
                result.session_environment,
                {
                    "DBUS_SESSION_BUS_ADDRESS": host_bus,
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                },
            )
            self.assertEqual(calls[0][0], [str(launch_client.resolve()), "--list"])
            self.assertFalse(calls[0][1]["shell"])
            self.assertEqual(calls[0][1]["env"]["DBUS_SESSION_BUS_ADDRESS"], host_bus)
            self.assertNotIn("WINEPREFIX", calls[0][1]["env"])
            with self.assertRaises(TypeError):
                result.session_environment["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/tampered"

    def test_rejects_a_captured_app_id_that_disagrees_with_the_prefix_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            probe = ContainerReentryProbe(
                root,
                run=lambda *_args, **_kwargs: self.fail("launch client must not run for an identity mismatch"),
                host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
                target_uid=1000,
                getuid=lambda: 1000,
            )

            with self.assertRaises(ContainerReentryError) as captured:
                asyncio.run(
                    probe.verify(
                        {
                            "WINEPREFIX": str(prefix),
                            "PROTONPATH": str(proton),
                            "STEAM_COMPAT_APP_ID": "0" * 32,
                        }
                    )
                )

            self.assertEqual(str(captured.exception), "container_reentry_identity_mismatch")
            self.assertEqual(captured.exception.failure_class, "app_id_mismatch")
            self.assertEqual(captured.exception.attempts, 0)

    def test_records_when_the_captured_app_id_confirms_the_prefix_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            digest = hashlib.md5(str(prefix.resolve()).encode(), usedforsecurity=False).hexdigest()
            bus = f"com.steampowered.App{digest}"

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=0,
                        stdout=f"--bus-name={bus}\n",
                        stderr="",
                    ),
                    host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
                    target_uid=1000,
                    getuid=lambda: 1000,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                        "STEAM_COMPAT_APP_ID": digest.upper(),
                    }
                )
            )

            self.assertEqual(result.app_id_source, "computed_and_captured")

    def test_uses_one_host_runtime_environment_for_probe_and_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            host_data = root / "host-data"
            private_data = root / "private-game-data"
            relative_client = Path("umu/steamrt3/pressure-vessel/bin/steam-runtime-launch-client")
            host_client = host_data / relative_client
            private_client = private_data / relative_client
            for client in (host_client, private_client):
                client.parent.mkdir(parents=True)
                client.write_text("client", encoding="utf-8")
                client.chmod(client.stat().st_mode | stat.S_IXUSR)
            bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()
            host_bus = "unix:path=/run/user/1000/bus"

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=0,
                        stdout=f"--bus-name={bus}\n",
                        stderr="",
                    ),
                    host_environment={
                        "HOME": str(root),
                        "PATH": "/host/bin:/usr/bin",
                        "XDG_DATA_HOME": str(host_data),
                        "DBUS_SESSION_BUS_ADDRESS": host_bus,
                        "XDG_RUNTIME_DIR": "/run/user/1000",
                    },
                    target_uid=1000,
                    getuid=lambda: 1000,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                        "HOME": "/run/pressure-vessel/private-home",
                        "PATH": "/run/pressure-vessel/bin",
                        "XDG_DATA_HOME": str(private_data),
                    }
                )
            )

            self.assertEqual(result.launch_client, host_client.resolve())
            self.assertEqual(
                result.launch_environment,
                {
                    "HOME": str(root),
                    "PATH": "/host/bin:/usr/bin",
                    "XDG_DATA_HOME": str(host_data),
                    "DBUS_SESSION_BUS_ADDRESS": host_bus,
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                },
            )
            with self.assertRaises(TypeError):
                result.launch_environment["HOME"] = "/tampered"

    def test_falls_back_from_an_unusable_host_address_to_the_uid_runtime_bus(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            expected_bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()
            calls = []

            def run(_argv, **kwargs):
                address = kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"]
                calls.append(address)
                if address == "unix:path=/stale/plugin/bus":
                    return SimpleNamespace(returncode=1, stdout="", stderr="Connection refused")
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={expected_bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=run,
                    sleep=lambda _: None,
                    host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/stale/plugin/bus"},
                    target_uid=1000,
                    getuid=lambda: 1000,
                ).verify({"WINEPREFIX": str(prefix), "PROTONPATH": str(proton)})
            )

            self.assertEqual(
                calls,
                ["unix:path=/stale/plugin/bus", "unix:path=/run/user/1000/bus"],
            )
            self.assertEqual(result.bus_source, "home_owner_runtime")
            self.assertEqual(
                result.session_environment,
                {
                    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                },
            )

    def test_completes_a_verified_host_bus_with_the_target_runtime_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            expected_bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=0,
                        stdout=f"--bus-name={expected_bus}\n",
                        stderr="",
                    ),
                    target_uid=1000,
                    getuid=lambda: 1000,
                    host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
                ).verify({"WINEPREFIX": str(prefix), "PROTONPATH": str(proton)})
            )

            self.assertEqual(
                result.session_environment,
                {
                    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                },
            )

    def test_uses_the_home_owner_session_bus_before_a_root_plugin_uid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            expected_bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()
            calls = []

            def run(_argv, **kwargs):
                address = kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"]
                calls.append(address)
                if address != "unix:path=/run/user/1000/bus":
                    return SimpleNamespace(returncode=1, stdout="", stderr="Connection refused")
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={expected_bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=run,
                    target_uid=1000,
                    getuid=lambda: 0,
                    host_environment={},
                ).verify({"WINEPREFIX": str(prefix), "PROTONPATH": str(proton)})
            )

            self.assertEqual(calls, ["unix:path=/run/user/1000/bus"])
            self.assertEqual(result.bus_source, "home_owner_runtime")

    def test_root_probe_fails_closed_when_the_target_home_owner_is_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            probe = ContainerReentryProbe(
                root,
                run=lambda *_args, **_kwargs: self.fail("launch client must not run without a host-user session"),
                target_uid=0,
                getuid=lambda: 0,
                host_environment={},
            )

            with self.assertRaises(ContainerReentryError) as captured:
                asyncio.run(probe.verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)}))

            self.assertEqual(str(captured.exception), "container_reentry_probe_failed")
            self.assertEqual(captured.exception.failure_class, "host_session_bus_unavailable")
            self.assertEqual(captured.exception.attempts, 0)

    def test_rejects_a_host_bus_address_owned_by_a_different_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            expected_bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()
            calls = []

            def run(_argv, **kwargs):
                address = kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"]
                calls.append(address)
                if address == "unix:path=/run/user/0/bus":
                    return SimpleNamespace(returncode=0, stdout="--bus-name=com.steampowered.Wrong\n", stderr="")
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={expected_bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=run,
                    target_uid=1000,
                    getuid=lambda: 0,
                    host_environment={
                        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/0/bus",
                        "XDG_RUNTIME_DIR": "/run/user/0",
                    },
                ).verify({"WINEPREFIX": str(prefix), "PROTONPATH": str(proton)})
            )

            self.assertEqual(calls, ["unix:path=/run/user/1000/bus"])
            self.assertEqual(result.bus_source, "home_owner_runtime")

    def test_retries_then_fails_closed_when_the_prefix_bus_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            attempts = []

            def run(argv, **kwargs):
                attempts.append(argv)
                return SimpleNamespace(returncode=0, stdout="--bus-name=com.steampowered.Other\n", stderr="")

            probe = ContainerReentryProbe(
                root,
                run=run,
                sleep=lambda _: None,
                attempts=3,
                host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
                getuid=lambda: 1000,
            )
            with self.assertRaisesRegex(ContainerReentryError, "container_reentry_bus_missing"):
                asyncio.run(probe.verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)}))
            self.assertEqual(len(attempts), 3)

    def test_attempt_limit_counts_launch_client_invocations_across_all_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            calls = []

            def run(_argv, **kwargs):
                calls.append(kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"])
                return SimpleNamespace(returncode=1, stdout="", stderr="Connection refused")

            probe = ContainerReentryProbe(
                root,
                run=run,
                sleep=lambda _: None,
                attempts=5,
                target_uid=1000,
                getuid=lambda: 1000,
                host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/stale/plugin/bus"},
            )

            with self.assertRaises(ContainerReentryError) as captured:
                asyncio.run(probe.verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)}))

            self.assertEqual(len(calls), 5)
            self.assertEqual(captured.exception.attempts, 5)

    def test_uses_the_host_xdg_data_home_for_the_umu_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, default_client = self._layout(root)
            data_home = root / "custom-data"
            custom_client = (
                data_home
                / "umu"
                / "steamrt3"
                / "pressure-vessel"
                / "bin"
                / "steam-runtime-launch-client"
            )
            custom_client.parent.mkdir(parents=True)
            default_client.replace(custom_client)
            prefix = root / "prefix"
            bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()
            calls = []

            def run(argv, **kwargs):
                calls.append(argv)
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=run,
                    host_environment={
                        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                        "XDG_DATA_HOME": str(data_home),
                    },
                    getuid=lambda: 1000,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                    }
                )
            )

            self.assertEqual(result.launch_client, custom_client.resolve())
            self.assertEqual(calls, [[str(custom_client.resolve()), "--list"]])

    def test_uses_umu_folders_path_before_xdg_data_home(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, default_client = self._layout(root)
            folders_root = root / "portable"
            custom_client = (
                folders_root
                / "umu"
                / "steamrt3"
                / "pressure-vessel"
                / "bin"
                / "steam-runtime-launch-client"
            )
            custom_client.parent.mkdir(parents=True)
            default_client.replace(custom_client)
            prefix = root / "prefix"
            bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=0,
                        stdout=f"--bus-name={bus}\n",
                        stderr="",
                    ),
                    host_environment={
                        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                        "UMU_FOLDERS_PATH": str(folders_root),
                    },
                    getuid=lambda: 1000,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                        "XDG_DATA_HOME": str(root / "wrong-data-home"),
                    }
                )
            )

            self.assertEqual(result.launch_client, custom_client.resolve())

    def test_ignores_a_private_game_umu_folders_path_when_resolving_the_host_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, default_client = self._layout(root)
            private_root = root / "pressure-vessel-private"
            private_client = (
                private_root
                / "umu"
                / "steamrt3"
                / "pressure-vessel"
                / "bin"
                / "steam-runtime-launch-client"
            )
            private_client.parent.mkdir(parents=True)
            private_client.write_text("private", encoding="utf-8")
            private_client.chmod(private_client.stat().st_mode | stat.S_IXUSR)
            prefix = root / "prefix"
            bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=0,
                        stdout=f"--bus-name={bus}\n",
                        stderr="",
                    ),
                    host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
                    getuid=lambda: 1000,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                        "UMU_FOLDERS_PATH": str(private_root),
                    }
                )
            )

            self.assertEqual(result.launch_client, default_client.resolve())
            self.assertNotIn("UMU_FOLDERS_PATH", result.launch_environment)

    def test_rejects_unknown_or_ambiguous_proton_runtime_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton = root / "Proton"
            proton.mkdir()
            (proton / "toolmanifest.vdf").write_text(
                '"require_tool_appid" "999"\n"require_tool_appid" "1628350"\n', encoding="utf-8"
            )

            with self.assertRaisesRegex(ContainerReentryError, "container_reentry_unsupported"):
                asyncio.run(
                    ContainerReentryProbe(root, run=lambda *_args, **_kwargs: None).verify(
                        {"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)}
                    )
                )

    def test_reports_a_bounded_probe_failure_for_nonzero_launch_client_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)

            with self.assertRaisesRegex(ContainerReentryError, "container_reentry_probe_failed"):
                asyncio.run(
                    ContainerReentryProbe(
                        root,
                        run=lambda *_args, **_kwargs: SimpleNamespace(returncode=125, stdout="", stderr="private"),
                        host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
                        getuid=lambda: 1000,
                    ).verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)})
                )

    def test_reports_sanitized_probe_metadata_without_exposing_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            probe = ContainerReentryProbe(
                root,
                run=lambda *_args, **_kwargs: SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="Authorization token=private: Connection refused",
                ),
                attempts=1,
                host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"},
                getuid=lambda: 1000,
            )

            with self.assertRaises(ContainerReentryError) as captured:
                asyncio.run(probe.verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)}))

            error = captured.exception
            self.assertEqual(str(error), "container_reentry_probe_failed")
            self.assertEqual(error.failure_class, "dbus_unavailable")
            self.assertEqual(error.exit_code, 1)
            self.assertEqual(error.bus_source, "host_environment")
            self.assertEqual(error.attempts, 1)
            self.assertNotIn("private", repr(error))

    def test_preserves_the_most_actionable_failure_class_across_bus_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)

            def run(_argv, **kwargs):
                address = kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"]
                if address == "unix:path=/stale/plugin/bus":
                    return SimpleNamespace(returncode=1, stdout="", stderr="Permission denied")
                return SimpleNamespace(returncode=125, stdout="", stderr="unclassified failure")

            probe = ContainerReentryProbe(
                root,
                run=run,
                attempts=1,
                target_uid=1000,
                getuid=lambda: 1000,
                host_environment={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/stale/plugin/bus"},
            )

            with self.assertRaises(ContainerReentryError) as captured:
                asyncio.run(probe.verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)}))

            self.assertEqual(captured.exception.failure_class, "dbus_access_denied")
            self.assertEqual(captured.exception.bus_source, "host_environment")

    def test_rejects_relative_or_empty_runtime_roots_instead_of_using_the_plugin_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)

            for environment, host_environment in (
                ({}, {"UMU_FOLDERS_PATH": ""}),
                ({}, {"UMU_FOLDERS_PATH": "relative"}),
                ({}, {"XDG_DATA_HOME": "relative"}),
            ):
                with self.subTest(environment=environment, host_environment=host_environment):
                    with self.assertRaisesRegex(ContainerReentryError, "container_reentry_unsupported"):
                        asyncio.run(
                            ContainerReentryProbe(
                                root,
                                host_environment={
                                    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                                    **host_environment,
                                },
                                getuid=lambda: 1000,
                            ).verify(
                                {
                                    "WINEPREFIX": str(root / "prefix"),
                                    "PROTONPATH": str(proton),
                                    **environment,
                                }
                            )
                        )


if __name__ == "__main__":
    unittest.main()
