import json
import re
import unittest

from trainer_relay.cheat_config import (
    DEFAULT_CONFIG_KEY,
    decode_cheat_controls_config,
    empty_cheat_controls_config,
    new_manual_cheat_control,
    validate_cheat_controls_config,
)


SHA256 = "a" * 64
HOTKEY = {"modifiers": ["shift", "ctrl"], "key": "F1"}


def valid_control(control_id="11111111-1111-4111-8111-111111111111", label=" Infinite health "):
    return {"id": control_id, "label": label, "hotkey": HOTKEY}


class CheatControlsConfigTests(unittest.TestCase):
    def test_uses_a_separate_v1_persistence_key(self):
        self.assertEqual(DEFAULT_CONFIG_KEY, "CheatControlsConfigV1")
        self.assertEqual(empty_cheat_controls_config(), {"schemaVersion": 1, "games": {}})

    def test_decoder_trims_valid_controls_and_drops_invalid_entries(self):
        decoded = decode_cheat_controls_config(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "games": {
                        "gog:1482265668": {
                            "trainerSha256": SHA256,
                            "cheats": [
                                valid_control(),
                                {"id": "not-a-uuid", "label": "bad", "hotkey": HOTKEY},
                                {"id": "22222222-2222-4222-8222-222222222222", "label": "\n", "hotkey": HOTKEY},
                                {"id": "33333333-3333-4333-8333-333333333333", "label": "bad", "hotkey": {"modifiers": [], "key": "ESCAPE"}},
                                {"id": "44444444-4444-4444-8444-444444444444", "label": "bad", "hotkey": HOTKEY, "path": "x.exe"},
                            ],
                        },
                        "steam:unsupported": {"trainerSha256": SHA256, "cheats": [valid_control()]},
                        "epic:bad-hash": {"trainerSha256": "A" * 64, "cheats": [valid_control()]},
                    },
                }
            )
        )
        self.assertEqual(
            decoded,
            {
                "schemaVersion": 1,
                "games": {
                    "gog:1482265668": {
                        "trainerSha256": SHA256,
                        "cheats": [
                            {
                                "id": "11111111-1111-4111-8111-111111111111",
                                "label": "Infinite health",
                                "hotkey": {"modifiers": ["ctrl", "shift"], "key": "F1"},
                            }
                        ],
                    }
                },
            },
        )

    def test_decoder_keeps_at_most_64_controls_in_input_order(self):
        cheats = [
            valid_control(f"{index:08d}-1111-4111-8111-111111111111", f"Cheat {index}")
            for index in range(1, 66)
        ]
        decoded = decode_cheat_controls_config(
            {"schemaVersion": 1, "games": {"gog:one": {"trainerSha256": SHA256, "cheats": cheats}}}
        )
        self.assertEqual(len(decoded["games"]["gog:one"]["cheats"]), 64)
        self.assertEqual(decoded["games"]["gog:one"]["cheats"][0]["label"], "Cheat 1")
        self.assertEqual(decoded["games"]["gog:one"]["cheats"][-1]["label"], "Cheat 64")

    def test_strict_validation_requires_the_complete_safe_shape(self):
        valid = {
            "schemaVersion": 1,
            "games": {"epic:game": {"trainerSha256": SHA256, "cheats": [valid_control(label="Infinite health")] }},
        }
        expected_valid = {
            "schemaVersion": 1,
            "games": {
                "epic:game": {
                    "trainerSha256": SHA256,
                    "cheats": [{**valid_control(label="Infinite health"), "hotkey": {"modifiers": ["ctrl", "shift"], "key": "F1"}}],
                }
            },
        }
        self.assertEqual(validate_cheat_controls_config(valid), expected_valid)

        invalid_documents = [
            None,
            {"schemaVersion": 2, "games": {}},
            {"schemaVersion": 1},
            {"schemaVersion": 1, "games": {"steam:game": {"trainerSha256": SHA256, "cheats": []}}},
            {"schemaVersion": 1, "games": {"gog:game": {"trainerSha256": "A" * 64, "cheats": []}}},
            {"schemaVersion": 1, "games": {"gog:game": {"trainerSha256": SHA256, "cheats": [valid_control(), valid_control()]}}},
            {"schemaVersion": 1, "games": {"gog:game": {"trainerSha256": SHA256, "cheats": [valid_control("55555555-5555-4555-8555-555555555555", "x" * 81)]}}},
        ]
        for value in invalid_documents:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_cheat_controls_config(value)

    def test_new_control_gets_a_lowercase_uuid_and_normalized_hotkey(self):
        control = new_manual_cheat_control("  Infinite health  ", HOTKEY)
        self.assertEqual(control["label"], "Infinite health")
        self.assertEqual(control["hotkey"], {"modifiers": ["ctrl", "shift"], "key": "F1"})
        self.assertRegex(control["id"], re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"))

    def test_labels_reject_controls_and_trim_to_the_character_limit(self):
        valid = valid_control()
        valid["label"] = "x" * 80
        self.assertEqual(validate_cheat_controls_config({"schemaVersion": 1, "games": {"gog:x": {"trainerSha256": SHA256, "cheats": [valid]}}})["games"]["gog:x"]["cheats"][0]["label"], "x" * 80)
        for label in ("", "   ", "x" * 81, "line\nfeed", "x\n", "null\x00byte"):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    validate_cheat_controls_config({"schemaVersion": 1, "games": {"gog:x": {"trainerSha256": SHA256, "cheats": [valid_control(label=label)]}}})


if __name__ == "__main__":
    unittest.main()
