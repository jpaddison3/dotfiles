import os
import json
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
            "printf 'call\\n' >> \"$HOME/calls\"\n"
            "printf '%s\\n' \"$@\" > \"$HOME/arguments\"\n"
            "cat \"$HOME/stdout\"\n"
            "printf '%s\\n' \"${BACKEND_STDERR:-}\" >&2\n"
            "exit \"${BACKEND_EXIT:-0}\"\n"
        )
        self.backend.chmod(0o755)
        (self.home / "working directory").mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_script(self, script, **extra_env):
        (self.home / "calls").write_text("")
        (self.home / "stdout").write_text(extra_env.pop("BACKEND_STDOUT", "backend ok\n"))
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
        for mode, script in SCRIPTS.items():
            with self.subTest(mode=mode):
                result = self.run_script(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.home / "calls").read_text().splitlines(), ["call"])
                self.assertEqual(
                    (self.home / "arguments").read_text().splitlines(),
                    ["--mode", mode],
                )
                self.assertEqual(result.stdout, "backend ok\n")

    def test_backend_failure_is_forwarded_without_retry(self):
        for mode, script in SCRIPTS.items():
            with self.subTest(mode=mode):
                result = self.run_script(
                    script, BACKEND_EXIT="37", BACKEND_STDERR="backend failed"
                )
                self.assertEqual(result.returncode, 37)
                self.assertEqual((self.home / "calls").read_text().splitlines(), ["call"])
                self.assertEqual(result.stderr, "backend failed\n")

    def test_structured_backend_output_is_condensed_for_compact_mode(self):
        cases = {
            "fresh launch": (
                json.dumps(
                    {
                        "action": "launched",
                        "mode": "bod",
                        "terminal_handle": "pane-123",
                        "run_id": "run-123",
                    }
                )
                + "\nspawn verified: run-123 is running\n",
                "launched: mode=bod pane=pane-123\n",
                0,
            ),
            "already preparing": (
                json.dumps(
                    {
                        "action": "already-preparing",
                        "opened_at": "2026-09-17T12:34:56+00:00",
                        "run_id": "run-123",
                    },
                    indent=2,
                )
                + "\n",
                "already-preparing: since=2026-09-17T12:34:56+00:00\n",
                0,
            ),
            "reopen failure": (
                json.dumps(
                    {
                        "action": "reopened",
                        "opened": False,
                        "open_error": "obsidian could not open the proposal",
                    },
                    indent=2,
                )
                + "\n",
                "reopen failed: obsidian could not open the proposal\n",
                1,
            ),
            "multiline reopen failure": (
                json.dumps({
                    "action": "reopened",
                    "opened": False,
                    "open_error": "cannot open proposal\napplication unavailable\r\ntry again",
                }),
                "reopen failed: cannot open proposal application unavailable try again\n",
                1,
            ),
            "launch with run identity only": (
                json.dumps({"action": "launched", "mode": "eod", "run_id": "run-456"}),
                "launched: mode=eod run=run-456\n",
                0,
            ),
        }

        for mode, script in SCRIPTS.items():
            for case, (backend_stdout, expected_stdout, expected_status) in cases.items():
                with self.subTest(mode=mode, case=case):
                    result = self.run_script(
                        script,
                        BACKEND_STDOUT=backend_stdout,
                        BACKEND_EXIT=str(expected_status),
                    )
                    self.assertEqual(result.returncode, expected_status, result.stderr)
                    self.assertEqual(result.stdout, expected_stdout)
                    self.assertEqual((self.home / "calls").read_text().splitlines(), ["call"])

    def test_unrecognized_output_is_preserved_verbatim(self):
        outputs = ["", "no newline", "two lines\n\n", "{invalid json\n\n", "[]\n", '{"action": "future"}\n\n']
        for mode, script in SCRIPTS.items():
            for output in outputs:
                with self.subTest(mode=mode, output=output):
                    result = self.run_script(
                        script, BACKEND_STDOUT=output, BACKEND_EXIT="37",
                        BACKEND_STDERR="backend diagnostic",
                    )
                    self.assertEqual(result.stdout, output)
                    self.assertEqual(result.stderr, "backend diagnostic\n")
                    self.assertEqual(result.returncode, 37)
                    self.assertEqual((self.home / "calls").read_text().splitlines(), ["call"])

    def test_failed_spawn_verification_is_not_reported_as_a_successful_launch(self):
        for mode, script in SCRIPTS.items():
            with self.subTest(mode=mode):
                diagnostic = "spawn verification failed: session file missing; inspect the pane"
                result = self.run_script(
                    script,
                    BACKEND_STDOUT=json.dumps({
                        "action": "launched", "mode": "bod", "terminal_handle": "pane-123",
                    }),
                    BACKEND_STDERR=diagnostic,
                    BACKEND_EXIT="1",
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, diagnostic + "\n")
                self.assertEqual(result.stdout, "launch failed: mode=bod pane=pane-123\n")
                self.assertEqual((self.home / "calls").read_text().splitlines(), ["call"])

    def test_missing_backend_is_actionable_and_nonzero(self):
        self.backend.unlink()
        self.assert_backend_unavailable()

    def test_nonexecutable_backend_is_actionable_and_nonzero(self):
        self.backend.chmod(0o644)
        self.assert_backend_unavailable()

    def assert_backend_unavailable(self):
        for mode, script in SCRIPTS.items():
            with self.subTest(mode=mode):
                result = self.run_script(script)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("make install-inbox-triage", result.stderr)
                self.assertIn(str(self.backend), result.stderr)
                self.assertEqual((self.home / "calls").read_text(), "")


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
            for source in SCRIPTS.values():
                self.assertEqual(installed[source.name], source.read_bytes())
                self.assertTrue(os.access(destination / source.name, os.X_OK))
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
            self.assertNotRegex(text, re.compile(r"^# @raycast\.needsConfirmation\s+true", re.MULTILINE))
            self.assertNotRegex(text, re.compile(r"^# @raycast\.argument\d+", re.MULTILINE))
            self.assertNotIn("@raycast.hotkey", text)


if __name__ == "__main__":
    unittest.main()
