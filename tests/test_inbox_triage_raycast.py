import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "raycast" / "inbox-triage"
SCRIPTS = {
    "auto": SCRIPTS_DIR / "inbox-triage.sh",
    "bod": SCRIPTS_DIR / "inbox-triage-bod.sh",
    "eod": SCRIPTS_DIR / "inbox-triage-eod.sh",
}


class RaycastScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="inbox triage home ")
        self.home = Path(self.temp_dir.name)
        self.backend = self.home / ".local" / "bin" / "inbox-triage-launch"
        self.backend.parent.mkdir(parents=True)
        self.backend.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$#\" > \"$HOME/call-count\"\n"
            "printf '%s\\n' \"$@\" > \"$HOME/arguments\"\n"
            "printf '%s\\n' \"${BACKEND_STDOUT:-backend ok}\"\n"
            "printf '%s\\n' \"${BACKEND_STDERR:-}\" >&2\n"
            "exit \"${BACKEND_EXIT:-0}\"\n"
        )
        self.backend.chmod(0o755)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, script, **extra_env):
        env = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin",
            **extra_env,
        }
        return subprocess.run(
            [str(script)],
            cwd=self.home / "working directory",
            env=env,
            capture_output=True,
            text=True,
        )

    def test_each_script_makes_one_backend_call_with_expected_mode(self):
        (self.home / "working directory").mkdir()

        for mode, script in SCRIPTS.items():
            with self.subTest(mode=mode):
                result = self.run_script(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.home / "call-count").read_text(), "2\n")
                self.assertEqual(
                    (self.home / "arguments").read_text().splitlines(),
                    ["--mode", mode],
                )
                self.assertEqual(result.stdout, "backend ok\n")

    def test_backend_failure_is_forwarded_without_retry(self):
        (self.home / "working directory").mkdir()
        result = self.run_script(
            SCRIPTS["auto"], BACKEND_EXIT="37", BACKEND_STDERR="backend failed"
        )

        self.assertEqual(result.returncode, 37)
        self.assertEqual((self.home / "call-count").read_text(), "2\n")
        self.assertIn("backend failed", result.stderr)

    def test_missing_backend_is_actionable_and_nonzero(self):
        self.backend.unlink()
        (self.home / "working directory").mkdir()
        result = self.run_script(SCRIPTS["auto"])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("make install-inbox-triage", result.stderr)
        self.assertIn("missing or not executable", result.stderr)


class InstallerTests(unittest.TestCase):
    def test_focused_install_is_idempotent_and_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory(prefix="inbox triage install home ") as temp:
            home = Path(temp)
            destination = home / ".local" / "share" / "raycast" / "scripts" / "inbox-triage"
            destination.mkdir(parents=True)
            unrelated = destination / "unrelated-script.sh"
            unrelated.write_text("keep me\n")
            env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}

            first = subprocess.run(
                ["make", "install-inbox-triage-raycast"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            installed = {
                path.name: path.read_bytes()
                for path in destination.iterdir()
                if path.name != unrelated.name
            }
            self.assertEqual(set(installed), {path.name for path in SCRIPTS.values()})
            self.assertEqual(unrelated.read_text(), "keep me\n")

            second = subprocess.run(
                ["make", "install-inbox-triage-raycast"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                {
                    path.name: path.read_bytes()
                    for path in destination.iterdir()
                    if path.name != unrelated.name
                },
                installed,
            )
            self.assertEqual(unrelated.read_text(), "keep me\n")


class MetadataTests(unittest.TestCase):
    def test_scripts_have_valid_focused_metadata_and_no_arguments_or_hotkeys(self):
        expected_titles = {
            "inbox-triage.sh": "Inbox Triage",
            "inbox-triage-bod.sh": "Inbox Triage — BOD",
            "inbox-triage-eod.sh": "Inbox Triage — EOD",
        }
        for script in SCRIPTS_DIR.iterdir():
            if script.suffix != ".sh":
                continue
            text = script.read_text()
            self.assertIn("# @raycast.schemaVersion 1", text)
            self.assertIn(f"# @raycast.title {expected_titles[script.name]}", text)
            self.assertIn("# @raycast.mode compact", text)
            self.assertIn("# @raycast.packageName Inbox Triage", text)
            self.assertNotRegex(text, r"^# @raycast\.argument\d+", re.MULTILINE)
            self.assertNotIn("@raycast.hotkey", text)


if __name__ == "__main__":
    unittest.main()
