import os
import tempfile
import unittest

from trainer_relay.config import (
    DEFAULT_CONFIG_KEY,
    decode_relay_config,
    default_prefix_for,
    validate_launch_identity,
)


class RelayConfigTests(unittest.TestCase):
    def test_identity_requires_supported_scheme_and_single_nonempty_game_id(self):
        self.assertEqual(validate_launch_identity("epic:deadbeef"), "epic:deadbeef")
        self.assertEqual(validate_launch_identity("gog:game-id_2"), "gog:game-id_2")
        for value in ("steam:123", "epic:", "epic:one:two", "epic:has space", "GOG:game"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_launch_identity(value)

    def test_invalid_document_becomes_empty_v1_config(self):
        for value in (None, {}, {"schemaVersion": 2, "games": {}}, {"schemaVersion": 1}, "not-json"):
            with self.subTest(value=value):
                self.assertEqual(decode_relay_config(value), {"schemaVersion": 1, "games": {}})

    def test_decoder_omits_invalid_entries_and_keeps_valid_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            trainer = os.path.join(directory, "trainer.EXE")
            prefix = os.path.join(directory, "prefix")
            open(trainer, "w", encoding="utf-8").close()
            os.mkdir(prefix)
            decoded = decode_relay_config(
                {
                    "schemaVersion": 1,
                    "games": {
                        "epic:good": {"enabled": True, "trainerPath": trainer},
                        "gog:with-prefix": {
                            "enabled": False,
                            "trainerPath": trainer,
                            "prefixOverride": prefix,
                        },
                        "steam:not-supported": {"enabled": True, "trainerPath": trainer},
                        "epic:missing-trainer": {
                            "enabled": True,
                            "trainerPath": os.path.join(directory, "missing.exe"),
                        },
                        "epic:bad-suffix": {"enabled": True, "trainerPath": prefix},
                        "epic:bad-prefix": {
                            "enabled": True,
                            "trainerPath": trainer,
                            "prefixOverride": os.path.join(directory, "missing-prefix"),
                        },
                    },
                }
            )
            self.assertEqual(
                decoded,
                {
                    "schemaVersion": 1,
                    "games": {
                        "epic:good": {"enabled": True, "trainerPath": trainer},
                        "gog:with-prefix": {
                            "enabled": False,
                            "trainerPath": trainer,
                            "prefixOverride": prefix,
                        },
                    },
                },
            )

    def test_default_prefix_is_under_unifideck_prefixes(self):
        self.assertEqual(
            default_prefix_for("epic:deadbeef", home="/home/deck"),
            "/home/deck/.local/share/unifideck/prefixes/deadbeef",
        )

    def test_persisted_key_is_the_single_backend_config_key(self):
        self.assertEqual(DEFAULT_CONFIG_KEY, "RelayConfigV1")


if __name__ == "__main__":
    unittest.main()
