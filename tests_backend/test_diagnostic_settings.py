import json
import unittest

from trainer_relay.diagnostic_settings import (
    DIAGNOSTIC_SETTINGS_KEY,
    decode_diagnostic_settings,
    empty_diagnostic_settings,
    validate_diagnostic_settings,
)


class DiagnosticSettingsTests(unittest.TestCase):
    def test_defaults_disabled_under_the_versioned_settings_key(self):
        self.assertEqual(DIAGNOSTIC_SETTINGS_KEY, "diagnostic_settings_v1")
        self.assertEqual(empty_diagnostic_settings(), {"schemaVersion": 1, "enabled": False})

    def test_decodes_exact_mapping_or_json_document(self):
        enabled = {"schemaVersion": 1, "enabled": True}
        self.assertEqual(decode_diagnostic_settings(enabled), enabled)
        self.assertEqual(decode_diagnostic_settings(json.dumps(enabled)), enabled)

    def test_malformed_or_future_documents_fail_closed(self):
        for value in (
            None,
            {},
            "not-json",
            {"schemaVersion": 2, "enabled": True},
            {"schemaVersion": 1, "enabled": "yes"},
            {"schemaVersion": True, "enabled": True},
        ):
            with self.subTest(value=value):
                self.assertEqual(decode_diagnostic_settings(value), {"schemaVersion": 1, "enabled": False})

    def test_strict_validation_rejects_malformed_rpc_writes(self):
        self.assertEqual(
            validate_diagnostic_settings({"schemaVersion": 1, "enabled": False}),
            {"schemaVersion": 1, "enabled": False},
        )
        for value in ({}, {"schemaVersion": 1, "enabled": 1}, {"schemaVersion": 3, "enabled": True}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "invalid_diagnostic_settings"):
                    validate_diagnostic_settings(value)


if __name__ == "__main__":
    unittest.main()
