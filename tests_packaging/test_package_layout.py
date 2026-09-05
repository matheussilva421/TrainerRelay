import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from scripts import package_trainer_relay


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = ROOT / "scripts" / "package_trainer_relay.py"
BUILD_SCRIPT = ROOT / "scripts" / "build_input_helper.ps1"


class TrainerRelayPackageLayoutTests(unittest.TestCase):
    def _write_package_with_helper_bundle(
        self, helper_directory: Path, staging_root: Path, archive: Path
    ) -> None:
        for source in package_trainer_relay.iter_package_files():
            relative = source.relative_to(ROOT)
            staged_source = staging_root / relative
            staged_source.parent.mkdir(parents=True, exist_ok=True)
            if relative.parts[0] == "bin":
                source = helper_directory / source.name
            shutil.copy2(source, staged_source)

        with mock.patch.object(package_trainer_relay, "ROOT", staging_root):
            files = package_trainer_relay.iter_package_files()
            package_trainer_relay.validate_sources(files)
            package_trainer_relay.write_archive(archive, files)

    def test_package_validation_rejects_invalid_helper_contracts(self):
        mutations = ("schema", "machine", "hash")

        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                fixture_root = Path(directory)
                fixture_bin = fixture_root / "bin"
                fixture_runtime = fixture_root / "trainer_relay"
                fixture_bin.mkdir()
                fixture_runtime.mkdir()
                for name in (
                    "TrainerRelay.InputHelper.x86.exe",
                    "TrainerRelay.InputHelper.x64.exe",
                    "input-helper-manifest.json",
                ):
                    shutil.copy2(ROOT / "bin" / name, fixture_bin / name)

                manifest_path = fixture_bin / "input-helper-manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if mutation == "schema":
                    manifest["schemaVersion"] = 2
                elif mutation == "machine":
                    helper = fixture_bin / "TrainerRelay.InputHelper.x86.exe"
                    helper_bytes = bytearray(helper.read_bytes())
                    pe_offset = struct.unpack_from("<I", helper_bytes, 0x3C)[0]
                    struct.pack_into("<H", helper_bytes, pe_offset + 4, 0x8664)
                    helper.write_bytes(helper_bytes)
                    manifest["helpers"]["x86"]["sha256"] = hashlib.sha256(helper_bytes).hexdigest()
                else:
                    manifest["helpers"]["x64"]["sha256"] = "0" * 64
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                files = [
                    fixture_bin / "TrainerRelay.InputHelper.x86.exe",
                    fixture_bin / "TrainerRelay.InputHelper.x64.exe",
                    manifest_path,
                ]
                with mock.patch.object(package_trainer_relay, "ROOT", fixture_root):
                    with self.assertRaises(ValueError):
                        package_trainer_relay.validate_sources(files)

    def test_package_contains_only_the_relocatable_runtime_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "TrainerRelay.zip"
            completed = subprocess.run(
                [sys.executable, str(PACKAGE_SCRIPT), str(archive)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

            with zipfile.ZipFile(archive) as bundle:
                self.assertTrue(
                    all(entry.compress_type == zipfile.ZIP_STORED for entry in bundle.infolist()),
                    "stored entries keep package bytes independent of zlib versions",
                )
                names = set(bundle.namelist())
                text_entries = [
                    name
                    for name in names
                    if Path(name).suffix.lower() in {".js", ".md", ".py", ".json", ""}
                ]
                for name in text_entries:
                    self.assertNotIn(b"\r\n", bundle.read(name), name)
                package_document = bundle.read("TrainerRelay/package.json")
                main_document = bundle.read("TrainerRelay/main.py")
                self.assertTrue(
                    all((entry.external_attr >> 16) & 0o111 == 0 for entry in bundle.infolist()),
                    "ZIP entries must not require executable permissions",
                )

        self.assertTrue(names)
        self.assertTrue(all(name.startswith("TrainerRelay/") for name in names))
        self.assertIn("TrainerRelay/dist/index.js", names)
        self.assertIn("TrainerRelay/main.py", names)
        self.assertIn("TrainerRelay/plugin.json", names)
        self.assertIn("TrainerRelay/package.json", names)
        self.assertIn("TrainerRelay/py_modules/trainer_relay/watcher.py", names)
        self.assertIn("TrainerRelay/py_modules/trainer_relay/container_reentry.py", names)
        self.assertIn("TrainerRelay/py_modules/trainer_relay/diagnostics.py", names)
        self.assertIn("TrainerRelay/py_modules/trainer_relay/diagnostic_settings.py", names)
        self.assertIn("TrainerRelay/data/fling_adapters_v1.json", names)
        self.assertIn("TrainerRelay/bin/TrainerRelay.InputHelper.x86.exe", names)
        self.assertIn("TrainerRelay/bin/TrainerRelay.InputHelper.x64.exe", names)
        self.assertIn("TrainerRelay/bin/input-helper-manifest.json", names)
        self.assertNotIn("TrainerRelay/trainer_relay/watcher.py", names)
        self.assertIn("TrainerRelay/docs/adr/0001-session-watcher.md", names)
        self.assertIn("TrainerRelay/docs/STEAM-DECK-VALIDATION.md", names)
        self.assertNotIn("TrainerRelay/dist/index.js.map", names)
        self.assertFalse(any("tests" in name.lower() for name in names))
        self.assertFalse(any("__pycache__" in name.lower() for name in names))
        self.assertFalse(any(name.endswith((".env", ".log", ".pyc", ".map")) for name in names))
        self.assertFalse(any("node_modules" in name or "pnpm-lock" in name for name in names))
        self.assertIn(b'"version": "0.1.0-experimental.23"', package_document)
        self.assertIn(b'PLUGIN_VERSION = "0.1.0-experimental.23"', main_document)

    def test_manifest_hashes_match_packaged_helper_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "TrainerRelay.zip"
            completed = subprocess.run(
                [sys.executable, str(PACKAGE_SCRIPT), str(archive)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

            with zipfile.ZipFile(archive) as bundle:
                manifest = json.loads(bundle.read("TrainerRelay/bin/input-helper-manifest.json"))
                for architecture in ("x86", "x64"):
                    helper_name = f"TrainerRelay/bin/TrainerRelay.InputHelper.{architecture}.exe"
                    helper_bytes = bundle.read(helper_name)
                    entry = manifest["helpers"][architecture]
                    self.assertEqual(entry["architecture"], architecture)
                    self.assertEqual(entry["path"], f"TrainerRelay.InputHelper.{architecture}.exe")
                    self.assertEqual(entry["sha256"], hashlib.sha256(helper_bytes).hexdigest())

    def test_package_bytes_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            for archive in (first, second):
                completed = subprocess.run(
                    [sys.executable, str(PACKAGE_SCRIPT), str(archive)],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

            self.assertEqual(first.read_bytes(), second.read_bytes())

    @unittest.skipUnless(os.name == "nt" and shutil.which("pwsh"), "requires Windows PowerShell")
    def test_two_builds_manifests_and_packages_are_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            build_directories = [temporary_root / "build-a", temporary_root / "build-b"]
            archives = [temporary_root / "first.zip", temporary_root / "second.zip"]

            for build_directory in build_directories:
                completed = subprocess.run(
                    [
                        "pwsh",
                        "-NoProfile",
                        "-File",
                        str(BUILD_SCRIPT),
                        "-OutputDirectory",
                        str(build_directory),
                    ],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

            artifact_names = (
                "TrainerRelay.InputHelper.x86.exe",
                "TrainerRelay.InputHelper.x64.exe",
                "input-helper-manifest.json",
            )
            for name in artifact_names:
                self.assertEqual(
                    (build_directories[0] / name).read_bytes(),
                    (build_directories[1] / name).read_bytes(),
                    name,
                )

            for index, build_directory in enumerate(build_directories):
                self._write_package_with_helper_bundle(
                    build_directory,
                    temporary_root / f"stage-{index}",
                    archives[index],
                )
            self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())

    @unittest.skipUnless(os.name == "nt" and shutil.which("pwsh"), "requires Windows PowerShell")
    def test_build_test_only_removes_temporary_host_test_executables(self):
        temporary_root = Path(tempfile.gettempdir())
        pattern = "TrainerRelay.InputHelper.test.*.exe"
        before = {path.name for path in temporary_root.glob(pattern)}

        completed = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(BUILD_SCRIPT), "-TestOnly"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        after = {path.name for path in temporary_root.glob(pattern)}
        self.assertEqual(after - before, set(), "build left temporary host-test executables")

    def test_packaged_runtime_imports_from_decky_py_modules_path(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            archive = temporary_root / "TrainerRelay.zip"
            completed = subprocess.run(
                [sys.executable, str(PACKAGE_SCRIPT), str(archive)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

            extract_root = temporary_root / "installed"
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(extract_root)

            plugin_root = extract_root / "TrainerRelay"
            import_check = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import sys; "
                        f"sys.path.append({str(plugin_root / 'py_modules')!r}); "
                        "import trainer_relay.config; "
                        "print(trainer_relay.config.DEFAULT_CONFIG_KEY)"
                    ),
                ],
                cwd=temporary_root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(import_check.returncode, 0, import_check.stderr or import_check.stdout)


if __name__ == "__main__":
    unittest.main()
