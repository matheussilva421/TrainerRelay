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

            def run(argv, **kwargs):
                calls.append((argv, kwargs))
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(root, run=run, sleep=lambda _: None).verify(
                    {"WINEPREFIX": str(prefix), "PROTONPATH": str(proton), "DBUS_SESSION_BUS_ADDRESS": "private"}
                )
            )

            self.assertEqual(result.bus_name, bus)
            self.assertEqual(result.runtime_variant, "steamrt3")
            self.assertEqual(result.attempts, 1)
            self.assertEqual(calls[0][0], [str(launch_client.resolve()), "--list"])
            self.assertFalse(calls[0][1]["shell"])
            self.assertEqual(calls[0][1]["env"]["DBUS_SESSION_BUS_ADDRESS"], "private")

    def test_retries_then_fails_closed_when_the_prefix_bus_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proton, _ = self._layout(root)
            attempts = []

            def run(argv, **kwargs):
                attempts.append(argv)
                return SimpleNamespace(returncode=0, stdout="--bus-name=com.steampowered.Other\n", stderr="")

            probe = ContainerReentryProbe(root, run=run, sleep=lambda _: None, attempts=3)
            with self.assertRaisesRegex(ContainerReentryError, "container_reentry_bus_missing"):
                asyncio.run(probe.verify({"WINEPREFIX": str(root / "prefix"), "PROTONPATH": str(proton)}))
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
            bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()
            calls = []

            def run(argv, **kwargs):
                calls.append(argv)
                return SimpleNamespace(returncode=0, stdout=f"--bus-name={bus}\n", stderr="")

            result = asyncio.run(
                ContainerReentryProbe(root, run=run).verify(
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
            bus = "com.steampowered.App" + hashlib.md5(
                str(prefix.resolve()).encode(), usedforsecurity=False
            ).hexdigest()

            result = asyncio.run(
                ContainerReentryProbe(root, run=lambda *_args, **_kwargs: SimpleNamespace(
                    returncode=0,
                    stdout=f"--bus-name={bus}\n",
                    stderr="",
                )).verify(
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
                            ContainerReentryProbe(root).verify(
                                {
                                    "WINEPREFIX": str(root / "prefix"),
                                    "PROTONPATH": str(proton),
                                    **environment,
                                }
                            )
                        )


if __name__ == "__main__":
    unittest.main()
