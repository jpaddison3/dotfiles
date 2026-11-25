import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A stand-in for the native binary. The script strips the environment, so the
# stub takes its instructions from files under HOME and writes its probe there.
STUB = """#!/bin/bash
[[ -z "${CLAUDE_CONFIG_DIR-}" ]] || mkdir -p "$CLAUDE_CONFIG_DIR"
if [[ "$1" = --version ]]; then
  # A child that keeps stdout open, as a stray helper process might.
  [[ ! -e "$HOME/hang-version" ]] || { sleep 5 & exec sleep 30; }
  if [[ -e "$HOME/version" ]]; then fail="$HOME/after-version-exit"; else fail="$HOME/before-version-exit"; fi
  if [[ -e "$fail" ]]; then echo "version diagnostic"; exit "$(cat "$fail")"; fi
  cat "$HOME/version" 2>/dev/null || echo "9.9.9 (Claude Code)"
  exit 0
fi
printf "%s\\n" "$*" "$PWD" "${CLAUDE_CONFIG_DIR-unset}" "${DISABLE_UPDATES-unset}" \\
  "${CLAUDECODE-unset}" > "$HOME/probe"
[[ ! -e "$HOME/hang" ]] || exec sleep 30
echo "10.0.0 (Claude Code)" > "$HOME/version"
# exec keeps the pending alarm, and alarm(0) returns the seconds it had left.
[[ ! -e "$HOME/report-alarm" ]] || exec /usr/bin/perl -e \
  'open my $f, ">", "$ENV{HOME}/alarm" or die; print $f alarm(0)'
exit "$(cat "$HOME/exit-code" 2>/dev/null || echo 0)"
"""


class ClaudeAutoUpdateTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.home() / ".cache/agent-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.home = Path(tempfile.mkdtemp(prefix="claude-update-test-", dir=scratch))
        self.addCleanup(shutil.rmtree, self.home)
        self.binary = self.home / ".local/share/claude/versions/9.9.9"
        self.binary.parent.mkdir(parents=True)
        self.binary.write_text(STUB)
        self.binary.chmod(0o755)
        self.cli = self.home / ".local/bin/claude"
        self.cli.parent.mkdir(parents=True)
        self.cli.symlink_to(self.binary)

    def run_update(self, **extra):
        env = os.environ.copy()
        env.update({"HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(self.home / ".claude-gmail"),
                    "DISABLE_UPDATES": "1", "CLAUDECODE": "1"})
        env.update(extra)
        result = subprocess.run(["/bin/bash", str(ROOT / "claude-auto-update.sh")],
                                env=env, cwd=ROOT, capture_output=True, text=True, timeout=20)
        log = self.home / ".local/share/claude-auto-update/claude-auto-update.log"
        return result, log.read_text() if log.exists() else ""

    def test_updates_native_cli_despite_inherited_session_environment(self):
        result, log = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr + log)
        self.assertEqual((self.home / "probe").read_text().splitlines(), [
            "update", str((self.home / ".local/share/claude").resolve()),
            "unset", "unset", "unset"])
        self.assertFalse((self.home / ".claude-gmail").exists())
        self.assertIn("Before: 9.9.9 (Claude Code)", log)
        self.assertIn("After: 10.0.0 (Claude Code)", log)
        self.assertIn("Updated.", log)
        self.assertEqual(list((self.home / ".local/share/claude-auto-update").glob("version.*")), [])

    def test_logs_when_version_is_unchanged(self):
        (self.home / "version").write_text("10.0.0 (Claude Code)\n")
        result, log = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr + log)
        self.assertIn("Version unchanged", log)

    def test_accepts_a_relative_native_symlink(self):
        self.cli.unlink()
        self.cli.symlink_to("../share/claude/versions/9.9.9")
        result, log = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr + log)
        self.assertIn("Updated.", log)

    def test_updater_failure_is_logged_and_propagated(self):
        (self.home / "exit-code").write_text("23")
        result, log = self.run_update()
        self.assertEqual(result.returncode, 23)
        self.assertIn("update failed (exit 23); see output above", log)
        self.assertNotIn("After:", log)

    def test_hung_update_is_stopped_at_the_time_limit(self):
        (self.home / "hang").write_text("")
        result, log = self.run_update(CLAUDE_AUTO_UPDATE_TIME_LIMIT="1")
        self.assertEqual(result.returncode, 142, log)
        self.assertIn("(exit 142, stopped at the 1s time limit)", log)

    def test_hung_version_check_is_stopped_at_the_time_limit(self):
        (self.home / "hang-version").write_text("")
        result, log = self.run_update(CLAUDE_AUTO_UPDATE_TIME_LIMIT="1")
        self.assertEqual(result.returncode, 142, log)
        self.assertIn("--version failed before updating (exit 142, stopped at the 1s", log)

    def test_invalid_time_limit_falls_back_to_the_default(self):
        (self.home / "report-alarm").write_text("")
        for value in ["0", "30m", ""]:
            result, log = self.run_update(CLAUDE_AUTO_UPDATE_TIME_LIMIT=value)
            self.assertEqual(result.returncode, 0, log)
            self.assertGreater(int((self.home / "alarm").read_text()), 1790, value)

    def test_version_failure_before_update_is_logged_with_its_output(self):
        (self.home / "before-version-exit").write_text("7")
        result, log = self.run_update()
        self.assertEqual(result.returncode, 7)
        self.assertIn("version diagnostic\nERROR: claude --version failed before updating (exit 7)", log)
        self.assertFalse((self.home / "probe").exists())

    def test_version_failure_after_update_is_logged_and_propagated(self):
        (self.home / "after-version-exit").write_text("9")
        result, log = self.run_update()
        self.assertEqual(result.returncode, 9)
        self.assertIn("version diagnostic\nERROR: claude --version failed after updating (exit 9)", log)
        self.assertNotIn("Updated.", log)

    def assert_refuses(self):
        result, log = self.run_update()
        self.assertEqual(result.returncode, 1, log)
        self.assertIn("not the native Claude Code installation", log)
        self.assertFalse((self.home / "probe").exists())

    def test_refuses_when_cli_is_missing(self):
        self.cli.unlink()
        self.assert_refuses()

    def test_refuses_a_launcher_file_in_place_of_the_symlink(self):
        self.cli.unlink()
        shutil.copy(self.binary, self.cli)
        self.assert_refuses()

    def test_refuses_a_symlink_outside_the_native_versions_dir(self):
        shim = self.home / ".local/codex-shim/claude"
        shim.parent.mkdir(parents=True)
        shutil.copy(self.binary, shim)
        self.cli.unlink()
        self.cli.symlink_to(shim)
        self.assert_refuses()

    def test_refuses_a_versions_entry_that_links_elsewhere(self):
        launcher = self.home / "launcher"
        shutil.copy(self.binary, launcher)
        self.binary.unlink()
        self.binary.symlink_to(launcher)
        self.assert_refuses()

    def test_refuses_a_dangling_native_symlink(self):
        self.binary.unlink()
        self.assert_refuses()


if __name__ == "__main__":
    unittest.main()
