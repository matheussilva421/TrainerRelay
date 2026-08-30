import os
import stat
import tempfile
import unittest
from pathlib import Path

from trainer_relay.environment import build_sanitized_environment
from trainer_relay.umu import UmuResolution, UmuResolutionError, resolve_umu_run, resolve_umu_run_details


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class EnvironmentTests(unittest.TestCase):
    def test_copies_allowlisted_values_without_mutating_source_or_leaking_secrets(self):
        source = {
            "HOME": "/home/deck",
            "PATH": "/usr/bin",
            "LANG": "pt_BR.UTF-8",
            "DISPLAY": ":0",
            "LC_ALL": "pt_BR.UTF-8",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "WINEPREFIX": "/prefix",
            "PROTONPATH": "/proton",
            "GAMEID": "game",
            "STORE": "gog",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": "/home/deck/.steam/root",
            "STEAM_COMPAT_DATA_PATH": "/compatdata",
            "SteamGameId": "123",
            "UMU_LOG": "1",
            "DXVK_HUD": "full",
            "WINEDEBUG": "-all",
            "API_TOKEN": "must-not-cross",
            "STEAM_PASSWORD": "must-not-cross",
            "WINE_AUTH_COOKIE": "must-not-cross",
            "UNRELATED": "must-not-cross",
            "PROTON_REMOTE_DEBUG_CMD": "must-always-go",
            "PROTON_VERB": "waitforexitandrun",
        }
        original = dict(source)
        result = build_sanitized_environment(source)
        self.assertEqual(source, original)
        self.assertEqual(result["HOME"], "/home/deck")
        self.assertEqual(result["STEAM_COMPAT_DATA_PATH"], "/compatdata")
        self.assertEqual(result["SteamGameId"], "123")
        self.assertEqual(result["PROTON_VERB"], "runinprefix")
        for key in (
            "API_TOKEN",
            "STEAM_PASSWORD",
            "WINE_AUTH_COOKIE",
            "UNRELATED",
            "PROTON_REMOTE_DEBUG_CMD",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH",
        ):
            self.assertNotIn(key, result)

    def test_preserves_posix_root_prefix_anchor(self):
        result = build_sanitized_environment({}, "/")

        self.assertEqual(result["WINEPREFIX"], "/")
        self.assertEqual(result["STEAM_COMPAT_DATA_PATH"], "/")


class UmuResolutionTests(unittest.TestCase):
    def test_resolves_one_bundled_candidate_and_does_not_use_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            candidate = home / "homebrew" / "plugins" / "Unifideck" / "bin" / "umu" / "umu" / "umu-run"
            candidate.parent.mkdir(parents=True)
            write_executable(candidate, "runner")
            result = resolve_umu_run(home, path_value=str(home / "must-not-be-used"))
            self.assertEqual(result, candidate.resolve())
            self.assertEqual(
                resolve_umu_run_details(home, path_value=str(home / "must-not-be-used")),
                UmuResolution(candidate.resolve(), "bundled"),
            )

    def test_falls_back_to_path_when_no_bundled_candidate_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            path_candidate = Path(directory) / "umu-run"
            write_executable(path_candidate, "runner")
            result = resolve_umu_run(Path(directory), path_value=directory, bundled_candidates=[])
            self.assertEqual(result, path_candidate.resolve())
            self.assertEqual(
                resolve_umu_run_details(Path(directory), path_value=directory, bundled_candidates=[]),
                UmuResolution(path_candidate.resolve(), "path"),
            )

    def test_rejects_multiple_distinct_path_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_dir = root / "one"
            second_dir = root / "two"
            first_dir.mkdir()
            second_dir.mkdir()
            write_executable(first_dir / "umu-run", "one")
            write_executable(second_dir / "umu-run", "two")

            with self.assertRaisesRegex(UmuResolutionError, "umu_ambiguous"):
                resolve_umu_run(root, path_value=os.pathsep.join((str(first_dir), str(second_dir))), bundled_candidates=[])

    def test_deduplicates_repeated_path_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "umu-run"
            write_executable(candidate, "runner")
            result = resolve_umu_run(
                Path(directory),
                path_value=os.pathsep.join((directory, directory)),
                bundled_candidates=[],
            )
            self.assertEqual(result, candidate.resolve())

    def test_rejects_zero_and_multiple_distinct_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            first = home / "one" / "umu-run"
            second = home / "two" / "umu-run"
            first.parent.mkdir()
            second.parent.mkdir()
            write_executable(first, "one")
            write_executable(second, "two")
            with self.assertRaisesRegex(UmuResolutionError, "umu_not_found"):
                resolve_umu_run(home, path_value="", bundled_candidates=[])
            with self.assertRaisesRegex(UmuResolutionError, "umu_ambiguous"):
                resolve_umu_run(home, path_value="", bundled_candidates=[first, second])

    def test_deduplicates_identical_bundled_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "umu-run"
            write_executable(candidate, "runner")
            result = resolve_umu_run(Path(directory), path_value="", bundled_candidates=[candidate, candidate])
            self.assertEqual(result, candidate.resolve())
