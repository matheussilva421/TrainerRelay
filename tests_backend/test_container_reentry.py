import asyncio
import hashlib
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from trainer_relay.container_reentry import ContainerReentryError, ContainerReentryProbe


_HOST_BUS = "unix:path=/run/user/1000/bus"


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

    @staticmethod
    def _bus_for(prefix: Path) -> str:
        return "com.steampowered.App" + hashlib.md5(
            str(prefix.resolve()).encode(), usedforsecurity=False
        ).hexdigest()

    def test_probes_the_host_session_bus_not_the_game_runtime_bus(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, launch_client = self._layout(root)
            prefix = root / "prefix"
            prefix.mkdir()
            bus = self._bus_for(prefix)
            calls = []

            def run(argv, **kwargs):
                calls.append((argv, kwargs))
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=run,
                    sleep=lambda _: None,
                    host_environ={"DBUS_SESSION_BUS_ADDRESS": _HOST_BUS},
                    getuid=lambda: 1000,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                        # The game-runtime address must never be used for the probe.
                        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/game/private/bus",
                        "DBUS_STARTER_ADDRESS": "unix:path=/game/private/bus",
                    }
                )
            )

            self.assertEqual(result.bus_name, bus)
            self.assertEqual(result.runtime_variant, "steamrt3")
            self.assertEqual(result.attempts, 1)
            self.assertEqual(result.dbus_address, _HOST_BUS)
            self.assertEqual(result.dbus_source, "host_env")
            self.assertEqual(calls[0][0], [str(launch_client.resolve()), "--list"])
            self.assertFalse(calls[0][1]["shell"])
            self.assertEqual(calls[0][1]["env"]["DBUS_SESSION_BUS_ADDRESS"], _HOST_BUS)
            self.assertNotIn("DBUS_STARTER_ADDRESS", calls[0][1]["env"])

    def test_selects_the_first_host_candidate_that_lists_the_prefix_bus(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            prefix = root / "prefix"
            bus = self._bus_for(prefix)
            addresses = []

            def run(argv, **kwargs):
                address = kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"]
                addresses.append(address)
                if address == "unix:path=/run/user/1000/bus":
                    return SimpleNamespace(returncode=0, stdout=f"--bus-name={bus}\n", stderr="")
                # The host_env candidate is unreachable in this scenario.
                return SimpleNamespace(returncode=1, stdout="", stderr="Failed to connect")

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=run,
                    sleep=lambda _: None,
                    host_environ={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/stale/bus"},
                    getuid=lambda: 1000,
                ).verify({"WINEPREFIX": str(prefix), "PROTONPATH": str(proton)})
            )

            self.assertEqual(result.dbus_address, "unix:path=/run/user/1000/bus")
            self.assertEqual(result.dbus_source, "uid_default")
            self.assertEqual(addresses, ["unix:path=/stale/bus", "unix:path=/run/user/1000/bus"])

    def test_fails_closed_with_bounded_evidence_when_no_host_bus_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)

            def run(argv, **kwargs):
                return SimpleNamespace(returncode=125, stdout="", stderr="Failed to connect to bus")

            with self.assertRaises(ContainerReentryError) as caught:
                asyncio.run(
                    ContainerReentryProbe(
                        root,
                        run=run,
                        sleep=lambda _: None,
                        host_environ={"DBUS_SESSION_BUS_ADDRESS": _HOST_BUS},
                        getuid=lambda: 1000,
                    ).verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)})
                )

            self.assertEqual(str(caught.exception), "container_reentry_probe_failed")
            evidence = caught.exception.evidence
            self.assertEqual(evidence["returncode"], 125)
            self.assertIn("Failed to connect to bus", evidence["detail"])

    def test_fails_closed_when_no_host_session_bus_can_be_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            ran = []

            with self.assertRaises(ContainerReentryError) as caught:
                asyncio.run(
                    ContainerReentryProbe(
                        root,
                        run=lambda *a, **k: ran.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""),
                        host_environ={},
                        getuid=None,
                    ).verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)})
                )

            self.assertEqual(str(caught.exception), "container_reentry_probe_failed")
            self.assertEqual(caught.exception.evidence["detail"], "no_host_session_bus")
            self.assertEqual(ran, [])

    def test_redacts_secrets_from_bounded_probe_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)

            def run(argv, **kwargs):
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="denied token=supersecret password=hunter2 reason=bad",
                )

            with self.assertRaises(ContainerReentryError) as caught:
                asyncio.run(
                    ContainerReentryProbe(
                        root,
                        run=run,
                        sleep=lambda _: None,
                        host_environ={"DBUS_SESSION_BUS_ADDRESS": _HOST_BUS},
                        getuid=lambda: 1000,
                    ).verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)})
                )

            detail = caught.exception.evidence["detail"]
            self.assertNotIn("supersecret", detail)
            self.assertNotIn("hunter2", detail)
            self.assertIn("[redacted]", detail)
            self.assertLessEqual(len(detail), 200)

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
                host_environ={"DBUS_SESSION_BUS_ADDRESS": _HOST_BUS},
                getuid=None,
            )
            with self.assertRaises(ContainerReentryError) as caught:
                asyncio.run(probe.verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)}))
            self.assertEqual(str(caught.exception), "container_reentry_bus_missing")
            self.assertEqual(len(attempts), 3)

    def test_uses_the_game_session_xdg_data_home_for_the_umu_runtime(self):
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
            bus = self._bus_for(prefix)
            calls = []

            def run(argv, **kwargs):
                calls.append(argv)
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=run,
                    host_environ={"DBUS_SESSION_BUS_ADDRESS": _HOST_BUS},
                    getuid=lambda: 1000,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                        "XDG_DATA_HOME": str(data_home),
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
            bus = self._bus_for(prefix)

            result = asyncio.run(
                ContainerReentryProbe(
                    root,
                    run=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=0,
                        stdout=f"--bus-name={bus}\n",
                        stderr="",
                    ),
                    host_environ={"DBUS_SESSION_BUS_ADDRESS": _HOST_BUS},
                    getuid=lambda: 1000,
                ).verify(
                    {
                        "WINEPREFIX": str(prefix),
                        "PROTONPATH": str(proton),
                        "UMU_FOLDERS_PATH": str(folders_root),
                        "XDG_DATA_HOME": str(root / "wrong-data-home"),
                    }
                )
            )

            self.assertEqual(result.launch_client, custom_client.resolve())

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
                    ContainerReentryProbe(
                        root,
                        run=lambda *_args, **_kwargs: None,
                        host_environ={"DBUS_SESSION_BUS_ADDRESS": _HOST_BUS},
                    ).verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)})
                )

    def test_rejects_relative_or_empty_runtime_roots_instead_of_using_the_plugin_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)

            for environment in (
                {"UMU_FOLDERS_PATH": ""},
                {"UMU_FOLDERS_PATH": "relative"},
                {"XDG_DATA_HOME": "relative"},
            ):
                with self.subTest(environment=environment):
                    with self.assertRaisesRegex(ContainerReentryError, "container_reentry_unsupported"):
                        asyncio.run(
                            ContainerReentryProbe(
                                root,
                                host_environ={"DBUS_SESSION_BUS_ADDRESS": _HOST_BUS},
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
