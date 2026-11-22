import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClaudeAutoUpdateTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.home() / ".cache/agent-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.home = Path(tempfile.mkdtemp(prefix="claude-update-test-", dir=scratch))
        self.addCleanup(shutil.rmtree, self.home)
        self.binary = self.home / ".local/share/claude/versions/9.9.9"
        self.binary.parent.mkdir(parents=True)
        # The script strips the environment, so the stub writes its probe under HOME.
        self.binary.write_text(
            "#!/bin/bash\n"
            '[[ -z "${CLAUDE_CONFIG_DIR-}" ]] || mkdir -p "$CLAUDE_CONFIG_DIR"\n'
            'if [[ "$1" = --version ]]; then\n'
            '  [[ ! -e "$HOME/version-exit" ]] || exit "$(cat "$HOME/version-exit")"\n'
            '  cat "$HOME/version" 2>/dev/null || echo "9.9.9 (Claude Code)"; exit 0\n'
            'fi\n'
            'echo "10.0.0 (Claude Code)" > "$HOME/version"\n'
            'printf "%s\\n" "$*" "$PWD" "${CLAUDE_CONFIG_DIR-unset}" '
            '"${DISABLE_UPDATES-unset}" "${CLAUDECODE-unset}" '
            '> "$HOME/probe"\n'
            'exit "$(cat "$HOME/exit-code" 2>/dev/null || echo 0)"\n'
        )
        self.binary.chmod(0o755)
        self.cli = self.home / ".local/bin/claude"
        self.cli.parent.mkdir(parents=True)
        self.cli.symlink_to(self.binary)

    def run_update(self):
        env = os.environ.copy()
        env.update({"HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(self.home / ".claude-gmail"),
                    "DISABLE_UPDATES": "1", "CLAUDECODE": "1"})
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

    def test_logs_when_already_up_to_date(self):
        (self.home / "version").write_text("10.0.0 (Claude Code)\n")
        result, log = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr + log)
        self.assertIn("Already up to date", log)

    def test_version_check_failure_is_logged_and_propagated(self):
        (self.home / "version-exit").write_text("7")
        result, log = self.run_update()
        self.assertEqual(result.returncode, 7)
        self.assertIn("--version failed before updating (exit 7)", log)
        self.assertFalse((self.home / "probe").exists())

    def test_updater_failure_is_logged_and_propagated(self):
        (self.home / "exit-code").write_text("23")
        result, log = self.run_update()
        self.assertEqual(result.returncode, 23)
        self.assertIn("failed (exit 23)", log)
        self.assertNotIn("After:", log)

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
