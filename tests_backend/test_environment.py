import stat
import tempfile
import unittest
from pathlib import Path

from trainer_relay.environment import build_sanitized_environment
from trainer_relay.umu import UmuResolutionError, resolve_umu_run


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
        for key in ("API_TOKEN", "STEAM_PASSWORD", "WINE_AUTH_COOKIE", "UNRELATED", "PROTON_REMOTE_DEBUG_CMD"):
            self.assertNotIn(key, result)


class UmuResolutionTests(unittest.TestCase):
    def test_resolves_one_bundled_candidate_and_does_not_use_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            candidate = home / "homebrew" / "plugins" / "Unifideck" / "bin" / "umu" / "umu" / "umu-run"
            candidate.parent.mkdir(parents=True)
            write_executable(candidate, "runner")
            result = resolve_umu_run(home, which=lambda _: (_ for _ in ()).throw(AssertionError("PATH used")))
            self.assertEqual(result, candidate.resolve())

    def test_falls_back_to_path_when_no_bundled_candidate_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            path_candidate = Path(directory) / "umu-run"
            write_executable(path_candidate, "runner")
            result = resolve_umu_run(Path(directory), which=lambda _: str(path_candidate))
            self.assertEqual(result, path_candidate.resolve())

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
                resolve_umu_run(home, which=lambda _: None, bundled_candidates=[])
            with self.assertRaisesRegex(UmuResolutionError, "umu_ambiguous"):
                resolve_umu_run(home, which=lambda _: None, bundled_candidates=[first, second])

    def test_deduplicates_identical_bundled_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "umu-run"
            write_executable(candidate, "runner")
            result = resolve_umu_run(Path(directory), which=lambda _: None, bundled_candidates=[candidate, candidate])
            self.assertEqual(result, candidate.resolve())
