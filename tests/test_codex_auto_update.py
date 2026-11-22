import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodexAutoUpdateTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.home() / ".cache/agent-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.home = Path(tempfile.mkdtemp(prefix="codex-update-test-", dir=scratch))
        self.addCleanup(shutil.rmtree, self.home)
        binary = self.home / ".codex/packages/standalone/current/bin/codex"
        binary.parent.mkdir(parents=True)
        binary.write_text(
            "#!/bin/bash\n"
            'if [[ "$1" = --version ]]; then echo "codex-cli test"; exit 0; fi\n'
            'printf "%s\\n" "$*" "$CODEX_HOME" "$CODEX_RELEASE" '
            '"$CODEX_NON_INTERACTIVE" "$CODEX_INSTALL_DIR" "$PWD" '
            '> "$UPDATE_PROBE"\n'
            'exit "${UPDATE_TEST_EXIT:-0}"\n'
        )
        binary.chmod(0o755)
        self.cli = self.home / ".local/bin/codex"
        self.cli.parent.mkdir(parents=True)
        self.cli.symlink_to(binary)

    def run_update(self, **extra):
        env = os.environ.copy()
        env.update({"HOME": str(self.home), "CODEX_HOME": str(self.home / ".codex-gmail"),
                    "CODEX_RELEASE": "0.100.0", "CODEX_NON_INTERACTIVE": "0",
                    "CODEX_INSTALL_DIR": str(self.home / "wrong-bin"),
                    "UPDATE_PROBE": str(self.home / "probe")})
        env.update(extra)
        result = subprocess.run(["/bin/bash", str(ROOT / "codex-auto-update.sh")],
                                env=env, capture_output=True, text=True, timeout=20)
        log = self.home / ".local/share/codex-auto-update/codex-auto-update.log"
        return result, log.read_text() if log.exists() else ""

    def test_updates_shared_cli_despite_personal_home_and_pinned_environment(self):
        result, log = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr + log)
        self.assertEqual((self.home / "probe").read_text().splitlines(), [
            "update", str(self.home / ".codex"), "latest", "1",
            str(self.home / ".local/bin"), str(self.home / ".codex")])
        self.assertFalse((self.home / ".codex-gmail").exists())
        self.assertIn("Update completed", log)

    def test_installer_failure_is_logged_and_propagated(self):
        result, log = self.run_update(UPDATE_TEST_EXIT="23")
        self.assertEqual(result.returncode, 23)
        self.assertIn("failed (exit 23)", log)
        self.assertNotIn("Update completed", log)

    def test_refuses_to_update_a_different_cli_installation(self):
        self.cli.unlink()
        self.cli.write_text("#!/bin/bash\nexit 88\n")
        self.cli.chmod(0o755)
        result, log = self.run_update()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not the shared standalone", log)
        self.assertFalse((self.home / "probe").exists())


if __name__ == "__main__":
    unittest.main()
