import os
import tempfile
import unittest
from pathlib import Path

from trainer_relay.process import (
    ProcessDiscoverer,
    SessionIdentity,
    normalize_wine_path,
    parse_proc_stat_start_time,
)


def proc_stat(pid: int, comm: str, start_time: int) -> str:
    return f"{pid} ({comm}) S " + " ".join(["0"] * 18) + f" {start_time} 0 0"


def write_candidate(root: Path, pid: int, *, start_time: int, executable: str, prefix: str, game_id: str, store: str, comm: str = "game.exe") -> None:
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
    (process / "environ").write_bytes(b"\0".join(f"{key}={value}".encode() for key, value in environment.items()) + b"\0")


class ProcessDiscoveryTests(unittest.TestCase):
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

    def test_returns_one_stable_session_and_accepts_comm_basename_fallback(self):
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
            self.assertEqual(result.state, "session")
            self.assertEqual(result.session, SessionIdentity(123, 10))
            self.assertEqual(result.environment["STORE"], "none")

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


if __name__ == "__main__":
    unittest.main()
