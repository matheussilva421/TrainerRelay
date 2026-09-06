import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from trainer_relay.cheat_catalog import CheatCatalog, load_packaged_catalog, packaged_catalog_path


ROOT = Path(__file__).resolve().parents[1]
BS2_SHA256 = "313ce3e30029bc88a27113ed2224ab8f66a8d62c82670c3508bd60af07157401"
INFINITE_SHA256 = "4aed63db45d25cc61acc94369f60c841c9f4252b86f88b4760b259f1ab552474"
MORTAL_SHELL_SHA256 = "872935c570a105d81db056264e540ffc254b2ee3cf63407afa9be65eaca41fb8"


def hotkey(key, modifiers=None):
    return {"modifiers": modifiers or [], "key": key}


def adapter(adapter_id, sha256, cheats, **extra):
    return {
        "id": adapter_id,
        "sha256": sha256,
        "peArchitecture": "x86",
        "trainerLabel": "Test trainer",
        "cheats": cheats,
        **extra,
    }


def cheat(cheat_id="health", label="Health", key="F1"):
    return {"id": cheat_id, "label": label, "hotkey": hotkey(key)}


class CheatCatalogTests(unittest.TestCase):
    def test_packaged_catalog_is_available_and_resolves_exact_hashes(self):
        self.assertTrue(packaged_catalog_path().is_file())
        catalog = load_packaged_catalog()
        bs2 = catalog.resolve(BS2_SHA256, "gog:1482265668")
        infinite = catalog.resolve(INFINITE_SHA256, "epic:8870")
        self.assertIsNotNone(bs2)
        self.assertIsNotNone(infinite)
        self.assertEqual(bs2.trainer_label, "BioShock 2 Remastered v1.0-Update 2 Plus 15 Trainer")
        self.assertEqual(infinite.trainer_label, "Bioshock Infinite v1.1.25.5165 Plus 15 Trainer")
        self.assertEqual(len(bs2.cheats), 15)
        self.assertEqual(len(infinite.cheats), 15)
        self.assertEqual(bs2.cheats[0].hotkey, hotkey("NUMPAD1"))
        self.assertEqual(bs2.cheats[10].hotkey, hotkey("DECIMAL"))
        self.assertEqual(bs2.cheats[11].hotkeys, (hotkey("NUMPAD1", ["alt"]), hotkey("NUMPAD2", ["alt"]), hotkey("NUMPAD3", ["alt"]), hotkey("NUMPAD4", ["alt"])))
        self.assertEqual(infinite.cheats[10].hotkey, hotkey("NUMPAD1", ["ctrl"]))
        self.assertEqual(infinite.cheats[14].hotkeys, (hotkey("F1"), hotkey("F2"), hotkey("F3"), hotkey("F4")))
        self.assertEqual(bs2.disable_all_hotkey, hotkey("HOME"))
        self.assertEqual(infinite.disable_all_hotkey, hotkey("HOME"))

    def test_packaged_catalog_resolves_exact_mortal_shell_epic_trainer(self):
        catalog = load_packaged_catalog()

        mortal_shell = catalog.resolve(
            MORTAL_SHELL_SHA256,
            "epic:0055e45ce7654c55aade646467349e83",
        )

        self.assertIsNotNone(mortal_shell)
        self.assertEqual(mortal_shell.trainer_label, "Mortal Shell v1.0-Build.08.25.21 Plus 16 Trainer")
        self.assertEqual(mortal_shell.pe_architecture, "x64")
        self.assertEqual(len(mortal_shell.cheats), 16)
        self.assertEqual(mortal_shell.cheats[0].hotkey, hotkey("NUMPAD1"))
        self.assertEqual(mortal_shell.cheats[10].hotkey, hotkey("DECIMAL"))
        self.assertEqual(mortal_shell.cheats[11].hotkey, hotkey("ADD"))
        self.assertEqual(mortal_shell.cheats[12].hotkey, hotkey("SUBTRACT"))
        self.assertEqual(mortal_shell.cheats[13].hotkey, hotkey("NUMPAD1", ["ctrl"]))
        self.assertEqual(mortal_shell.disable_all_hotkey, hotkey("HOME", ["ctrl", "shift"]))
        self.assertIsNone(catalog.resolve(MORTAL_SHELL_SHA256, "gog:0055e45ce7654c55aade646467349e83"))

    def test_unknown_hash_fails_closed_and_identity_restrictions_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "adapters": [adapter("test", "b" * 64, [cheat()], supportedIdentities=["gog:known"])],
                    }
                ),
                encoding="utf-8",
            )
            catalog = CheatCatalog.load(path)
        self.assertIsNotNone(catalog.resolve("b" * 64, "gog:known"))
        self.assertIsNone(catalog.resolve("b" * 64, "epic:known"))
        self.assertIsNone(catalog.resolve("c" * 64, "gog:known"))
        self.assertIsNone(catalog.resolve("b" * 64, "steam:known"))

    def test_duplicate_adapter_hash_ids_or_cheat_ids_reject_the_whole_catalog(self):
        cases = [
            [adapter("same", "a" * 64, [cheat("one")]), adapter("same", "b" * 64, [cheat("two")])],
            [adapter("one", "a" * 64, [cheat("one")]), adapter("two", "a" * 64, [cheat("two")])],
            [adapter("one", "a" * 64, [cheat("same"), cheat("same", "Other", "F2")])],
        ]
        for adapters in cases:
            with self.subTest(adapters=adapters):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "catalog.json"
                    path.write_text(json.dumps({"schemaVersion": 1, "adapters": adapters}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        CheatCatalog.load(path)

    def test_catalog_rejects_unsafe_descriptors_and_is_all_or_nothing(self):
        invalid_adapters = [
            adapter("test", "A" * 64, [cheat()]),
            adapter("test", "a" * 64, [{"id": "health", "label": "Health", "hotkey": hotkey("ESCAPE")}]),
            adapter("test", "a" * 64, [cheat(), cheat("health")]),
            adapter("test", "a" * 64, [cheat()], peArchitecture="arm64"),
            adapter("test", "a" * 64, [cheat()], supportedIdentities=["steam:one"]),
        ]
        for invalid in invalid_adapters:
            with self.subTest(invalid=invalid):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "catalog.json"
                    path.write_text(json.dumps({"schemaVersion": 1, "adapters": [invalid]}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        CheatCatalog.load(path)

    def test_non_text_pe_architecture_is_a_bounded_catalog_error(self):
        for invalid_architecture in ([], {}):
            with self.subTest(invalid_architecture=invalid_architecture):
                invalid = adapter("test", "a" * 64, [cheat()], peArchitecture=invalid_architecture)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "catalog.json"
                    path.write_text(json.dumps({"schemaVersion": 1, "adapters": [invalid]}), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "^invalid_cheat_catalog$"):
                        CheatCatalog.load(path)

    def test_descriptors_are_immutable_dataclasses(self):
        catalog = load_packaged_catalog()
        adapter_record = catalog.resolve(BS2_SHA256, "gog:1482265668")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            adapter_record.trainer_label = "changed"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            adapter_record.cheats[0].label = "changed"


if __name__ == "__main__":
    unittest.main()
