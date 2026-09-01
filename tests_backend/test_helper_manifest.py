import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from trainer_relay.helper_manifest import HelperManifestError, verify_helper


def fake_pe(machine: int) -> bytes:
    value = bytearray(0x100)
    value[:2] = b"MZ"
    value[0x3C:0x40] = (0x80).to_bytes(4, "little")
    value[0x80:0x84] = b"PE\0\0"
    value[0x84:0x86] = machine.to_bytes(2, "little")
    return bytes(value)


class HelperManifestTests(unittest.TestCase):
    def _write_manifest(self, directory: Path, helper: Path, sha256: str) -> Path:
        manifest = directory / "input-helper-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "helpers": {
                        "x86": {"path": helper.name, "sha256": sha256},
                        "x64": {"path": "helper.x64.exe", "sha256": "b" * 64},
                    },
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_verifies_manifest_hash_and_pe_architecture(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            helper = directory / "helper.x86.exe"
            helper.write_bytes(fake_pe(0x14C))
            digest = hashlib.sha256(helper.read_bytes()).hexdigest()
            manifest = self._write_manifest(directory, helper, digest)

            verified = verify_helper(helper, "x86", manifest)

        self.assertEqual(verified.architecture, "x86")
        self.assertEqual(verified.sha256, digest)

    def test_rejects_missing_helper_before_any_launch(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            helper = directory / "missing.exe"
            manifest = self._write_manifest(directory, helper, "a" * 64)

            with self.assertRaisesRegex(HelperManifestError, "helper_missing"):
                verify_helper(helper, "x86", manifest)

    def test_rejects_corrupt_helper_bytes_even_when_manifest_is_present(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            helper = directory / "helper.x86.exe"
            helper.write_bytes(fake_pe(0x14C))
            digest = hashlib.sha256(helper.read_bytes()).hexdigest()
            manifest = self._write_manifest(directory, helper, digest)
            helper.write_bytes(b"not a PE helper")

            with self.assertRaisesRegex(HelperManifestError, "helper_architecture_unknown"):
                verify_helper(helper, "x86", manifest)

    def test_rejects_hash_mismatch_and_wrong_architecture(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            helper = directory / "helper.x86.exe"
            helper.write_bytes(fake_pe(0x14C))
            manifest = self._write_manifest(directory, helper, "c" * 64)

            with self.assertRaisesRegex(HelperManifestError, "helper_hash_mismatch"):
                verify_helper(helper, "x86", manifest)

            helper.write_bytes(fake_pe(0x8664))
            digest = hashlib.sha256(helper.read_bytes()).hexdigest()
            manifest = self._write_manifest(directory, helper, digest)
            with self.assertRaisesRegex(HelperManifestError, "helper_architecture_mismatch"):
                verify_helper(helper, "x86", manifest)

    def test_rejects_malformed_manifest_with_one_bounded_reason(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            helper = directory / "helper.x86.exe"
            helper.write_bytes(fake_pe(0x14C))
            manifest = directory / "input-helper-manifest.json"
            manifest.write_text("{not json", encoding="utf-8")

            with self.assertRaisesRegex(HelperManifestError, "invalid_helper_manifest"):
                verify_helper(helper, "x86", manifest)


if __name__ == "__main__":
    unittest.main()
