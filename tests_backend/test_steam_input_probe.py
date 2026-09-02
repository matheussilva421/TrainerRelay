import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trainer_relay.steam_input_probe import MAX_PROBE_BYTES, export_steam_input_probe, validate_steam_input_probe


def probe_report() -> dict:
    return {
        "schemaVersion": 1,
        "appId": 123456789,
        "identity": "gog:1482265668",
        "controller": "steam_deck_builtin",
        "controllerIndex": 0,
        "runtimeFingerprint": "c" * 64,
        "sourceLayoutIdHash": "d" * 64,
        "sourceLayoutNameLength": 17,
        "methodShape": {
            "getConfig": True,
            "exportConfig": True,
            "startEditing": True,
            "saveEditing": True,
            "setSelected": True,
            "showConfigurator": True,
        },
        "responsePrimitiveKeys": ["controller_type", "url"],
    }


class SteamInputProbeTests(unittest.TestCase):
    def test_validates_the_exact_sanitized_probe_schema(self):
        value = validate_steam_input_probe(probe_report())

        self.assertEqual(value, probe_report())
        self.assertEqual(
            set(value),
            {
                "schemaVersion",
                "appId",
                "identity",
                "controller",
                "controllerIndex",
                "runtimeFingerprint",
                "sourceLayoutIdHash",
                "sourceLayoutNameLength",
                "methodShape",
                "responsePrimitiveKeys",
            },
        )

    def test_rejects_private_payloads_extra_fields_nested_objects_and_too_many_keys(self):
        invalid = [
            {**probe_report(), "rawPayload": {"accountId": "76561198000000000"}},
            {**probe_report(), "accountId": "76561198000000000"},
            {**probe_report(), "sourceLayoutName": "private source"},
            {**probe_report(), "sourceLayoutUrl": "private://layout"},
            {**probe_report(), "methodShape": {"getConfig": {"private": True}}},
            {**probe_report(), "responsePrimitiveKeys": [f"key_{index}" for index in range(65)]},
        ]

        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "invalid_steam_input_probe"):
                    validate_steam_input_probe(candidate)

    def test_rejects_encoded_probe_above_sixteen_kib(self):
        candidate = probe_report()
        candidate["responsePrimitiveKeys"] = [f"k_{index}_{'x' * 250}" for index in range(64)]

        with self.assertRaisesRegex(ValueError, "steam_input_probe_too_large"):
            export_steam_input_probe(
                candidate,
                tempfile.mkdtemp(),
                wall_clock=lambda: datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc),
            )

    def test_atomically_exports_lf_json_with_bounded_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            downloads = Path(directory) / "Downloads"
            result = export_steam_input_probe(
                probe_report(),
                downloads,
                wall_clock=lambda: datetime(2026, 9, 2, 12, 0, 3, tzinfo=timezone.utc),
            )

            destination = Path(result["path"])
            self.assertEqual(destination.name, "TrainerRelay-steam-input-probe-20260902-120003.json")
            self.assertEqual(result["bytesWritten"], destination.stat().st_size)
            payload = destination.read_bytes()
            self.assertLessEqual(len(payload), MAX_PROBE_BYTES)
            self.assertNotIn(b"\r\n", payload)
            self.assertTrue(payload.endswith(b"\n"))
            self.assertEqual(json.loads(payload), probe_report())
            self.assertEqual(list(downloads.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
