import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "agent-tmp-cleanup.sh"
DAY = 24 * 60 * 60


class AgentTmpCleanupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.root = self.home / ".cache" / "agent-tmp"
        self.root.mkdir(parents=True)

    def run_cleanup(self, **extra_env):
        env = os.environ.copy()
        env.update({"HOME": str(self.home), "AGENT_TMP_TTY": "1"})
        env.update(extra_env)
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)], env=env, capture_output=True,
            text=True, timeout=30,
        )

    @staticmethod
    def age(path, days=40, atime_days=None):
        now = int(time.time())
        atime_days = days if atime_days is None else atime_days
        os.utime(path, (now - atime_days * DAY, now - days * DAY))

    def test_deletes_old_file_and_reports_count_and_size(self):
        old = self.root / "old.txt"
        old.write_text("old")
        self.age(old)

        result = self.run_cleanup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(old.exists())
        self.assertIn("deleted 1 file(s)", result.stdout)
        self.assertIn("agent-tmp", result.stdout)

    def test_keeps_file_with_fresh_atime_even_if_mtime_is_old(self):
        file = self.root / "read-recently.txt"
        file.write_text("keep")
        self.age(file, atime_days=1)

        result = self.run_cleanup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(file.exists())
        self.assertIn("deleted 0 file(s)", result.stdout)

    def test_keeps_fresh_file(self):
        file = self.root / "fresh.txt"
        file.write_text("keep")

        result = self.run_cleanup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(file.exists())

    def test_prunes_old_empty_dirs_and_keeps_fresh_empty_dirs(self):
        old_dir = self.root / "old-empty"
        old_dir.mkdir()
        self.age(old_dir)
        fresh_dir = self.root / "fresh-empty"
        fresh_dir.mkdir()

        result = self.run_cleanup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(old_dir.exists())
        self.assertTrue(fresh_dir.exists())
        self.assertTrue(self.root.exists())

    def test_does_not_follow_symlink_outside_root(self):
        outside = self.home / "outside"
        outside.write_text("keep")
        self.age(outside)
        link = self.root / "link"
        link.symlink_to(outside)
        old = int(time.time()) - 40 * DAY
        os.utime(link, (old, old), follow_symlinks=False)

        result = self.run_cleanup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(link.exists())
        self.assertTrue(outside.exists())

    def test_dry_run_keeps_old_file(self):
        old = self.root / "old.txt"
        old.write_text("keep")
        self.age(old)

        result = self.run_cleanup(AGENT_TMP_DRY_RUN="1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(old.exists())
        self.assertIn("would delete 1 file(s)", result.stdout)

    def test_missing_root_exits_successfully(self):
        shutil.rmtree(self.root)

        result = self.run_cleanup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not found", result.stdout)


if __name__ == "__main__":
    unittest.main()
