import unittest

from trainer_relay.hotkeys import hotkey_to_vk, normalize_hotkey


class HotkeyTests(unittest.TestCase):
    def test_normalizes_modifiers_to_canonical_order(self):
        self.assertEqual(
            normalize_hotkey({"modifiers": ["shift", "ctrl", "alt"], "key": "F1"}),
            {"modifiers": ["ctrl", "alt", "shift"], "key": "F1"},
        )

    def test_accepts_every_key_family_boundary(self):
        keys = (
            "A",
            "Z",
            "0",
            "9",
            "F1",
            "F24",
            "NUMPAD0",
            "NUMPAD9",
            "MULTIPLY",
            "ADD",
            "SUBTRACT",
            "DECIMAL",
            "DIVIDE",
            "INSERT",
            "DELETE",
            "HOME",
            "END",
            "PAGEUP",
            "PAGEDOWN",
            "UP",
            "DOWN",
            "LEFT",
            "RIGHT",
            "SPACE",
            "TAB",
            "ENTER",
            "BACKSPACE",
            "PAUSE",
            "CAPSLOCK",
            "SCROLLLOCK",
            "NUMLOCK",
        )
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(normalize_hotkey({"modifiers": [], "key": key})["key"], key)

    def test_maps_symbols_and_modifier_bits(self):
        cases = {
            "A": 0x41,
            "Z": 0x5A,
            "0": 0x30,
            "9": 0x39,
            "F1": 0x70,
            "F24": 0x87,
            "NUMPAD0": 0x60,
            "NUMPAD9": 0x69,
            "MULTIPLY": 0x6A,
            "ADD": 0x6B,
            "SUBTRACT": 0x6D,
            "DECIMAL": 0x6E,
            "DIVIDE": 0x6F,
            "INSERT": 0x2D,
            "DELETE": 0x2E,
            "HOME": 0x24,
            "END": 0x23,
            "PAGEUP": 0x21,
            "PAGEDOWN": 0x22,
            "UP": 0x26,
            "DOWN": 0x28,
            "LEFT": 0x25,
            "RIGHT": 0x27,
            "SPACE": 0x20,
            "TAB": 0x09,
            "ENTER": 0x0D,
            "BACKSPACE": 0x08,
            "PAUSE": 0x13,
            "CAPSLOCK": 0x14,
            "SCROLLLOCK": 0x91,
            "NUMLOCK": 0x90,
        }
        for key, virtual_key in cases.items():
            with self.subTest(key=key):
                self.assertEqual(
                    hotkey_to_vk({"modifiers": ["shift", "ctrl"], "key": key}),
                    (virtual_key, 5),
                )

    def test_rejects_duplicate_unknown_and_noncanonical_modifiers(self):
        values = (
            ["ctrl", "ctrl"],
            ["meta"],
            ["CTRL"],
            ["shift", "alt", "shift"],
        )
        for modifiers in values:
            with self.subTest(modifiers=modifiers):
                with self.assertRaises(ValueError):
                    normalize_hotkey({"modifiers": modifiers, "key": "A"})

    def test_rejects_unknown_noncanonical_and_integer_keys(self):
        for key in ("a", "f1", "NUMPAD", "ESCAPE", "CTRL+A", 65, True, "A\n"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    normalize_hotkey({"modifiers": [], "key": key})

    def test_rejects_nonmappings_extra_fields_and_wrong_modifier_shape(self):
        values = (
            None,
            [],
            {"modifiers": [], "key": "A", "extra": "ignored"},
            {"modifiers": "ctrl", "key": "A"},
            {"modifiers": [1], "key": "A"},
            {"modifiers": [], "key": "A", "other": 1},
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_hotkey(value)

    def test_mapping_result_is_canonical_and_does_not_retain_extra_state(self):
        value = {"key": "ENTER", "modifiers": ["alt"]}
        result = normalize_hotkey(value)
        self.assertEqual(result, {"modifiers": ["alt"], "key": "ENTER"})
        self.assertIsNot(result, value)
        result["modifiers"].append("ctrl")
        self.assertEqual(value, {"key": "ENTER", "modifiers": ["alt"]})


if __name__ == "__main__":
    unittest.main()
