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
                names = set(bundle.namelist())
                text_entries = [
                    name
                    for name in names
                    if Path(name).suffix.lower() in {".js", ".md", ".py", ".json", ""}
                ]
                for name in text_entries:
                    self.assertNotIn(b"\r\n", bundle.read(name), name)

        self.assertTrue(names)
        self.assertTrue(all(name.startswith("TrainerRelay/") for name in names))
        self.assertIn("TrainerRelay/dist/index.js", names)
        self.assertIn("TrainerRelay/main.py", names)
        self.assertIn("TrainerRelay/plugin.json", names)
        self.assertIn("TrainerRelay/package.json", names)
        self.assertIn("TrainerRelay/trainer_relay/watcher.py", names)
        self.assertIn("TrainerRelay/docs/adr/0001-session-watcher.md", names)
        self.assertIn("TrainerRelay/docs/STEAM-DECK-VALIDATION.md", names)
        self.assertNotIn("TrainerRelay/dist/index.js.map", names)
        self.assertFalse(any("tests" in name.lower() for name in names))
        self.assertFalse(any("__pycache__" in name.lower() for name in names))
        self.assertFalse(any(name.endswith((".env", ".log", ".pyc", ".map")) for name in names))
        self.assertFalse(any("node_modules" in name or "pnpm-lock" in name for name in names))


if __name__ == "__main__":
    unittest.main()
