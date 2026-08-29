import unittest

from trainer_relay.games_map import parse_games_map


class GamesMapTests(unittest.TestCase):
    def test_parses_v1_v2_v3_and_preserves_equals_in_executable_path(self):
        result = parse_games_map(
            "\n".join(
                [
                    "# comments and blanks are ignored",
                    "epic:one=/games/one.exe",
                    "gog:two=/games/two.exe\t/home/deck/games/two",
                    "epic:three=/games/name=with-equals.exe\t/home/deck/games/three\t-759876716",
                ]
            )
        )
        self.assertIsNone(result.diagnostic)
        self.assertEqual(result.entries["epic:one"].executable, "/games/one.exe")
        self.assertEqual(result.entries["gog:two"].work_dir, "/home/deck/games/two")
        self.assertEqual(result.entries["epic:three"].signed_app_id, -759876716)
        self.assertEqual(result.entries["epic:three"].executable, "/games/name=with-equals.exe")

    def test_malformed_file_is_diagnostic_and_has_no_partially_trusted_entries(self):
        result = parse_games_map("epic:good=/games/good.exe\nmalformed-without-equals\n")
        self.assertIsNotNone(result.diagnostic)
        self.assertEqual(result.entries, {})
        self.assertEqual(result.diagnostic.code, "games_map_malformed")

    def test_rejects_every_ambiguous_row_shape(self):
        invalid_documents = {
            "empty-key": "=/games/game.exe",
            "empty-executable": "epic:game=",
            "too-many-tabs": "epic:game=/games/game.exe\t/work\t1\textra",
            "bad-app-id": "epic:game=/games/game.exe\t/work\tnot-an-int",
            "duplicate-key": "epic:game=/games/one.exe\nepic:game=/games/two.exe",
            "unsupported-identity": "steam:game=/games/game.exe",
            "xcloud-key": "xcloud:game=/games/game.exe",
            "xcloud-sentinel": "epic:game=xcloud",
            "relative-executable": "epic:game=games/game.exe",
        }
        for name, document in invalid_documents.items():
            with self.subTest(name=name):
                result = parse_games_map(document)
                self.assertIsNotNone(result.diagnostic)
                self.assertEqual(result.entries, {})

    def test_lookup_is_exact_identity_only(self):
        result = parse_games_map("epic:game=/games/epic.exe\ngog:game=/games/gog.exe")
        self.assertEqual(result.entry_for("epic:game").executable, "/games/epic.exe")
        self.assertIsNone(result.entry_for("epic:game:extra"))


if __name__ == "__main__":
    unittest.main()
