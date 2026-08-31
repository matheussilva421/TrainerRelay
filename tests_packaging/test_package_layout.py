import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = ROOT / "scripts" / "package_trainer_relay.py"


class TrainerRelayPackageLayoutTests(unittest.TestCase):
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
        self.assertNotIn("TrainerRelay/trainer_relay/watcher.py", names)
        self.assertIn("TrainerRelay/docs/adr/0001-session-watcher.md", names)
        self.assertIn("TrainerRelay/docs/STEAM-DECK-VALIDATION.md", names)
        self.assertNotIn("TrainerRelay/dist/index.js.map", names)
        self.assertFalse(any("tests" in name.lower() for name in names))
        self.assertFalse(any("__pycache__" in name.lower() for name in names))
        self.assertFalse(any(name.endswith((".env", ".log", ".pyc", ".map")) for name in names))
        self.assertFalse(any("node_modules" in name or "pnpm-lock" in name for name in names))

        self.assertIn(b'"version": "0.1.0-experimental.18"', package_document)
        self.assertIn(b'PLUGIN_VERSION = "0.1.0-experimental.18"', main_document)

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
