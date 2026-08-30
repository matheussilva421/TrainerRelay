import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trainer_relay.process import (
    CandidateDecision,
    DiscoveryResult,
    ProcessDiscoverer,
    SessionIdentity,
    normalize_wine_path,
    parse_proc_stat_start_time,
)


def proc_stat(pid: int, comm: str, start_time: int) -> str:
    return f"{pid} ({comm}) S " + " ".join(["0"] * 18) + f" {start_time} 0 0"


def write_candidate(
    root: Path,
    pid: int,
    *,
    start_time: int,
    executable: str,
    prefix: str,
    game_id: str,
    store: str,
    comm: str = "expected.exe",
    legacy: bool = False,
) -> None:
    process = root / str(pid)
    process.mkdir()
    (process / "stat").write_text(proc_stat(pid, comm, start_time), encoding="utf-8")
    (process / "comm").write_text(comm + "\n", encoding="utf-8")
    (process / "cmdline").write_bytes(b"\0".join([b"wine", executable.encode()]) + b"\0")
    environment = {
        "WINEPREFIX": prefix,
        "PROTONPATH": "/compat/proton",
        "GAMEID": game_id,
        "STORE": store,
    }
    if legacy:
        environment["PROTON_REMOTE_DEBUG_CMD"] = "/home/deck/legacy.exe"
        environment["PRESSURE_VESSEL_FILESYSTEMS_RW"] = "/tmp"
    (process / "environ").write_bytes(b"\0".join(f"{key}={value}".encode() for key, value in environment.items()) + b"\0")


class ProcessDiscoveryTests(unittest.TestCase):
    def discover_one(self, root: Path):
        return ProcessDiscoverer(root).discover(
            "gog:game",
            "/games/expected.exe",
            "/home/deck/.local/share/unifideck/prefixes/game",
        )

    def test_normalizes_posix_and_wine_z_paths(self):
        self.assertEqual(normalize_wine_path("Z:\\home\\deck\\Games\\game.exe"), "/home/deck/Games/game.exe")
        self.assertEqual(normalize_wine_path("/home/deck/Games/./game.exe"), "/home/deck/Games/game.exe")

    def test_parses_start_time_after_process_name_with_spaces_and_parenthesis(self):
        self.assertEqual(parse_proc_stat_start_time(proc_stat(123, "name ) with spaces", 987654)), 987654)

    def test_returns_waiting_when_no_candidate_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/other.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                game_id="game",
                store="gog",
            )
            result = ProcessDiscoverer(root).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
            )
            self.assertEqual(result.state, "waiting_for_game")
            self.assertIsNone(result.session)

    def test_rejects_same_comm_basename_when_cmdline_lacks_the_exact_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/not-present-in-cmdline.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                game_id="game",
                store="none",
                comm="expected.exe",
            )
            process = root / "123" / "cmdline"
            process.write_bytes(b"wine\0other-argument\0")
            result = ProcessDiscoverer(root).discover(
                "epic:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
            )
            self.assertEqual(result.state, "waiting_for_game")
            self.assertIsNone(result.session)

    def test_rejects_unknown_discovery_states(self):
        with self.assertRaises(ValueError):
            DiscoveryResult("guessed")

    def test_requires_matching_game_store_and_prefix_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pid, store, prefix in (
                (1, "gog", "/home/deck/.local/share/unifideck/prefixes/game/pfx/extra"),
                (2, "steam", "/home/deck/.local/share/unifideck/prefixes/game/pfx"),
                (3, "gog", "/home/deck/.local/share/unifideck/prefixes/other/pfx"),
            ):
                write_candidate(
                    root,
                    pid,
                    start_time=pid,
                    executable="/games/expected.exe",
                    prefix=prefix,
                    game_id="game",
                    store=store,
                )
            result = ProcessDiscoverer(root).discover(
                "epic:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
            )
            self.assertEqual(result.state, "waiting_for_game")

    def test_requires_nonempty_values_for_all_required_environment_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game",
                game_id="game",
                store="gog",
            )
            (root / "123" / "environ").write_bytes(
                b"WINEPREFIX=/home/deck/.local/share/unifideck/prefixes/game\0"
                b"PROTONPATH=\0GAMEID=game\0STORE=gog\0"
            )
            result = ProcessDiscoverer(root).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
            )
            self.assertEqual(result.state, "waiting_for_game")

    def test_blocks_a_matching_session_when_legacy_cheatdeck_environment_reappears(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                game_id="game",
                store="gog",
                legacy=True,
            )

            result = ProcessDiscoverer(root).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
            )

            self.assertEqual(result.state, "invalid_config")
            self.assertEqual(result.diagnostic, "legacy_settings_present")
            self.assertIsNone(result.session)

    def test_returns_ambiguous_for_multiple_matching_stable_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pid in (101, 202):
                write_candidate(
                    root,
                    pid,
                    start_time=pid,
                    executable="/games/expected.exe",
                    prefix="/home/deck/.local/share/unifideck/prefixes/game",
                    game_id="game",
                    store="gog",
                )
            result = ProcessDiscoverer(root).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
            )
            self.assertEqual(result.state, "ambiguous")
            self.assertEqual({session.pid for session in result.candidates}, {101, 202})

    def test_rejects_a_pid_recycled_during_candidate_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game",
                game_id="game",
                store="gog",
            )
            stat_path = root / "123" / "stat"
            calls = 0

            def read_bytes(path: Path) -> bytes:
                nonlocal calls
                if path == stat_path:
                    calls += 1
                    if calls == 2:
                        return proc_stat(123, "game.exe", 11).encode()
                return path.read_bytes()

            result = ProcessDiscoverer(root, read_bytes=read_bytes).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
            )
            self.assertEqual(result.state, "waiting_for_game")
            self.assertEqual(result.diagnostic, "pid_reused_during_scan")
            self.assertEqual(result.decisions[0].reason, "pid_reused_during_scan")

    def test_reports_prefix_mismatch_for_relevant_game_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/wrong",
                game_id="game",
                store="gog",
            )

            result = self.discover_one(root)

            self.assertEqual(result.diagnostic, "prefix_mismatch")
            self.assertEqual(result.rejection_counts["prefix_mismatch"], 1)
            self.assertTrue(result.decisions[0].relevant)
            self.assertEqual(result.decisions[0].details["observed_prefix"], "/home/deck/.local/share/unifideck/prefixes/wrong")

    def test_accepts_umu_database_id_distinct_from_gog_launch_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game",
                game_id="umu-0",
                store="gog",
            )
            result = self.discover_one(root)

            self.assertEqual(result.state, "session")
            self.assertEqual(result.session, SessionIdentity(123, 10))
            self.assertEqual(result.environment["GAMEID"], "umu-0")

    def test_selects_real_wine_process_from_umu_wrappers_and_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = "/home/deck/Games/BioShock 2 Remastered/Build/Final/Bioshock2HD.exe"
            prefix = "/home/deck/.local/share/unifideck/prefixes/1482265668"
            write_candidate(
                root,
                55481,
                start_time=100,
                executable=expected,
                prefix=prefix,
                game_id="umu-0",
                store="gog",
                comm="umu-run",
            )
            write_candidate(
                root,
                55639,
                start_time=200,
                executable="C:\\windows\\system32\\explorer.exe",
                prefix=prefix + "/pfx",
                game_id="umu-0",
                store="gog",
                comm="explorer.exe",
            )
            write_candidate(
                root,
                55675,
                start_time=300,
                executable="X:\\Games\\BioShock 2 Remastered\\Build\\Final\\Bioshock2HD.exe",
                prefix=prefix + "/pfx",
                game_id="umu-0",
                store="gog",
                comm="Bioshock2HD.exe",
            )

            with patch("trainer_relay.process.os.readlink", return_value="/home/deck"):
                result = ProcessDiscoverer(root).discover("gog:1482265668", expected, prefix)

            self.assertEqual(result.state, "session")
            self.assertEqual(result.session, SessionIdentity(55675, 300))
            self.assertEqual(result.decisions[0].reason, "process_name_mismatch")
            self.assertEqual(result.decisions[1].reason, "process_name_mismatch")
            self.assertEqual(result.decisions[2].reason, "candidate_accepted")
            self.assertEqual(
                result.decisions[2].details["observed_executable"],
                "/home/deck/Games/BioShock 2 Remastered/Build/Final/Bioshock2HD.exe",
            )

    def test_accepts_linux_truncated_comm_only_with_matching_full_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = "/games/VeryLongGameExecutable.exe"
            write_candidate(
                root,
                123,
                start_time=10,
                executable=expected,
                prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                game_id="umu-0",
                store="gog",
                comm="VeryLongGameExe",
            )

            result = ProcessDiscoverer(root).discover(
                "gog:game",
                expected,
                "/home/deck/.local/share/unifideck/prefixes/game",
            )

            self.assertEqual(result.state, "session")
            self.assertEqual(result.session, SessionIdentity(123, 10))

    def test_revalidates_same_session_after_game_renames_main_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = "/home/deck/Games/BioShock 2 Remastered/Build/Final/Bioshock2HD.exe"
            prefix = "/home/deck/.local/share/unifideck/prefixes/1482265668"
            write_candidate(
                root,
                57719,
                start_time=2457048,
                executable=expected,
                prefix=prefix + "/pfx",
                game_id="umu-0",
                store="gog",
                comm="Bioshock2HD.exe",
            )
            discoverer = ProcessDiscoverer(root)
            initial = discoverer.discover("gog:1482265668", expected, prefix)
            self.assertEqual(initial.session, SessionIdentity(57719, 2457048))

            (root / "57719" / "comm").write_text("Main Game Threa\n", encoding="utf-8")
            (root / "57719" / "stat").write_text(
                proc_stat(57719, "Main Game Threa", 2457048), encoding="utf-8"
            )
            revalidated = discoverer.discover(
                "gog:1482265668",
                expected,
                prefix,
                expected_session=initial.session,
            )

            self.assertEqual(revalidated.state, "session")
            self.assertEqual(revalidated.session, initial.session)
            self.assertEqual(revalidated.decisions[0].reason, "candidate_revalidated")

    def test_does_not_accept_renamed_thread_without_matching_pinned_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                game_id="umu-0",
                store="gog",
                comm="Main Game Threa",
            )

            result = ProcessDiscoverer(root).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
                expected_session=SessionIdentity(999, 10),
            )

            self.assertEqual(result.state, "waiting_for_game")
            self.assertEqual(result.decisions[0].reason, "process_name_mismatch")

    def test_does_not_revalidate_recycled_pid_after_thread_rename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=11,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                game_id="umu-0",
                store="gog",
                comm="Main Game Threa",
            )

            result = ProcessDiscoverer(root).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
                expected_session=SessionIdentity(123, 10),
            )

            self.assertEqual(result.state, "waiting_for_game")
            self.assertEqual(result.decisions[0].reason, "process_name_mismatch")

    def test_revalidated_session_and_new_real_session_remain_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pid, start_time, comm in (
                (123, 10, "Main Game Threa"),
                (456, 20, "expected.exe"),
            ):
                write_candidate(
                    root,
                    pid,
                    start_time=start_time,
                    executable="/games/expected.exe",
                    prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                    game_id="umu-0",
                    store="gog",
                    comm=comm,
                )

            result = ProcessDiscoverer(root).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
                expected_session=SessionIdentity(123, 10),
            )

            self.assertEqual(result.state, "ambiguous")
            self.assertEqual(result.candidates, (SessionIdentity(123, 10), SessionIdentity(456, 20)))

    def test_revalidated_session_still_blocks_reintroduced_legacy_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                game_id="umu-0",
                store="gog",
                comm="Main Game Threa",
                legacy=True,
            )

            result = ProcessDiscoverer(root).discover(
                "gog:game",
                "/games/expected.exe",
                "/home/deck/.local/share/unifideck/prefixes/game",
                expected_session=SessionIdentity(123, 10),
            )

            self.assertEqual(result.state, "invalid_config")
            self.assertEqual(result.diagnostic, "legacy_settings_present")

    def test_reports_store_mismatch_for_relevant_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game",
                game_id="game",
                store="steam",
            )
            self.assertEqual(self.discover_one(root).diagnostic, "store_mismatch")

    def test_reports_executable_mismatch_for_relevant_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/actual.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game",
                game_id="game",
                store="gog",
            )
            result = self.discover_one(root)
            self.assertEqual(result.diagnostic, "executable_mismatch")
            self.assertEqual(result.decisions[0].details["observed_executable"], "/games/actual.exe")

    def test_reports_missing_environment_for_relevant_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game",
                game_id="game",
                store="gog",
            )
            (root / "123" / "environ").write_bytes(b"GAMEID=game\0STORE=gog\0")
            self.assertEqual(self.discover_one(root).diagnostic, "missing_required_environment")

    def test_accepted_decision_contains_only_allowlisted_process_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(
                root,
                123,
                start_time=10,
                executable="/games/expected.exe",
                prefix="/home/deck/.local/share/unifideck/prefixes/game/pfx",
                game_id="game",
                store="gog",
            )
            result = self.discover_one(root)
            decision = result.decisions[0]
            self.assertIsInstance(decision, CandidateDecision)
            self.assertTrue(decision.accepted)
            self.assertEqual(decision.reason, "candidate_accepted")
            self.assertEqual(
                set(decision.details),
                {
                    "expected_executable",
                    "observed_executable",
                    "expected_prefix",
                    "observed_prefix",
                    "game_id",
                    "process_name",
                    "store",
                    "wineprefix",
                    "protonpath",
                },
            )
            self.assertNotIn("cmdline", decision.details)
            self.assertNotIn("environment", decision.details)


if __name__ == "__main__":
    unittest.main()
