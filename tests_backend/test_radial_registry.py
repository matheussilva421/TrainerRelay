import json
import unittest

from trainer_relay.radial_registry import (
    RADIAL_LAYOUT_REGISTRY_KEY,
    empty_radial_layout_registry,
    decode_radial_layout_registry,
    next_radial_layout_revision,
    validate_generated_radial_layout,
    validate_radial_layout_registry,
)


VALID = {
    "appId": 123456789,
    "identity": "gog:1482265668",
    "trainerSha256": "a" * 64,
    "catalogFingerprint": "b" * 64,
    "steamRuntimeFingerprint": "c" * 64,
    "sourceLayoutId": "autosave://123/source",
    "generatedLayoutId": "personal://123/generated",
    "generatedLayoutName": "Trainer Relay — BioShock 2 — aaaaaaaa — r1",
    "revision": 1,
    "createdAt": "2026-09-02T12:00:00Z",
}


def valid_record(**overrides):
    return {**VALID, **overrides}


class RadialLayoutRegistryTests(unittest.TestCase):
    def test_uses_separate_v1_key_and_empty_registry_shape(self):
        self.assertEqual(RADIAL_LAYOUT_REGISTRY_KEY, "RadialLayoutRegistryV1")
        self.assertEqual(empty_radial_layout_registry(), {"schemaVersion": 1, "layouts": []})

    def test_valid_generated_layout_requires_exact_safe_metadata_shape(self):
        value = valid_record()

        validated = validate_generated_radial_layout(value)

        self.assertEqual(validated, VALID)
        self.assertIsNot(validated, value)
        self.assertEqual(set(validated), set(VALID))

    def test_generated_layout_validator_parses_json_and_does_not_normalize_opaque_ids(self):
        value = valid_record(
            sourceLayoutId=" source://opaque ",
            generatedLayoutId=" generated://opaque ",
        )

        validated = validate_generated_radial_layout(json.dumps(value))

        self.assertEqual(validated["sourceLayoutId"], " source://opaque ")
        self.assertEqual(validated["generatedLayoutId"], " generated://opaque ")

    def test_rejects_unsafe_generated_layout_values(self):
        invalid_values = [
            {**VALID, "extra": "not metadata"},
            {key: value for key, value in VALID.items() if key != "revision"},
            {**VALID, "appId": True},
            {**VALID, "appId": 0},
            {**VALID, "appId": 2**53},
            {**VALID, "identity": "steam:123456789"},
            {**VALID, "trainerSha256": "A" * 64},
            {**VALID, "catalogFingerprint": "b" * 63},
            {**VALID, "steamRuntimeFingerprint": "g" * 64},
            {**VALID, "sourceLayoutId": VALID["generatedLayoutId"]},
            {**VALID, "sourceLayoutId": ""},
            {**VALID, "sourceLayoutId": "x" * 257},
            {**VALID, "sourceLayoutId": "source\nlayout"},
            {**VALID, "generatedLayoutName": ""},
            {**VALID, "generatedLayoutName": "x" * 121},
            {**VALID, "generatedLayoutName": "generated\u0000layout"},
            {**VALID, "revision": True},
            {**VALID, "revision": 0},
            {**VALID, "revision": 2**31},
            {**VALID, "createdAt": "2026-09-02T12:00:00"},
            {**VALID, "createdAt": "2026-09-02T12:00:00-03:00"},
            {**VALID, "createdAt": "not-a-timestamp"},
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_generated_radial_layout(value)

    def test_decoder_parses_json_drops_invalid_entries_and_keeps_newest_128(self):
        records = [
            valid_record(
                sourceLayoutId=f"source://{revision}",
                generatedLayoutId=f"generated://{revision}",
                generatedLayoutName=f"Layout {revision}",
                revision=revision,
            )
            for revision in range(129, 0, -1)
        ]
        records.insert(17, {**VALID, "generatedLayoutId": "bad\nlayout"})
        encoded = json.dumps({"schemaVersion": 1, "layouts": records})

        decoded = decode_radial_layout_registry(encoded)

        self.assertEqual(len(decoded["layouts"]), 128)
        self.assertEqual([record["revision"] for record in decoded["layouts"]], list(range(2, 130)))
        self.assertEqual(decoded["layouts"][0]["sourceLayoutId"], "source://2")
        self.assertEqual(decoded["layouts"][-1]["sourceLayoutId"], "source://129")

    def test_decoder_fails_closed_for_invalid_documents(self):
        for value in (None, {}, {"schemaVersion": 2, "layouts": []}, {"schemaVersion": 1}, "not-json"):
            with self.subTest(value=value):
                self.assertEqual(decode_radial_layout_registry(value), {"schemaVersion": 1, "layouts": []})

    def test_strict_document_validation_is_all_or_nothing_and_bounded(self):
        valid = {"schemaVersion": 1, "layouts": [VALID]}
        expected = {"schemaVersion": 1, "layouts": [VALID]}
        self.assertEqual(validate_radial_layout_registry(valid), expected)

        invalid = {"schemaVersion": 1, "layouts": [VALID, {**VALID, "revision": 0}]}
        with self.assertRaises(ValueError):
            validate_radial_layout_registry(invalid)

        too_many = {
            "schemaVersion": 1,
            "layouts": [
                valid_record(
                    sourceLayoutId=f"source://{revision}",
                    generatedLayoutId=f"generated://{revision}",
                    generatedLayoutName=f"Layout {revision}",
                    revision=revision,
                )
                for revision in range(1, 130)
            ],
        }
        with self.assertRaises(ValueError):
            validate_radial_layout_registry(too_many)

    def test_revision_allocation_is_monotonic_and_scoped_to_four_authority_fields(self):
        same_scope = valid_record(revision=4, generatedLayoutId="personal://123/old")
        other_catalog = valid_record(
            revision=99,
            catalogFingerprint="d" * 64,
            generatedLayoutId="personal://123/other-catalog",
        )
        other_app = valid_record(
            revision=77,
            appId=987654321,
            generatedLayoutId="personal://987/other-app",
        )
        registry = {"schemaVersion": 1, "layouts": [same_scope, other_catalog, other_app]}

        self.assertEqual(next_radial_layout_revision(registry, 123456789, "gog:1482265668", "a" * 64, "b" * 64), 5)
        self.assertEqual(next_radial_layout_revision(registry, 123456789, "gog:1482265668", "a" * 64, "d" * 64), 100)
        self.assertEqual(next_radial_layout_revision(registry, 987654321, "gog:1482265668", "a" * 64, "b" * 64), 78)
        self.assertEqual(next_radial_layout_revision(registry, 123456789, "gog:1482265668", "a" * 64, "e" * 64), 1)


if __name__ == "__main__":
    unittest.main()
