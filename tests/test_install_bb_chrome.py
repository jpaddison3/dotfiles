import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallBBChromeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="bb chrome ")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.checkout = self.home / "dotfiles"
        self.source = self.checkout / "bb-skills/bb-chrome"
        self.destination = self.home / ".bb/skills/bb-chrome"
        self.source.mkdir(parents=True)
        shutil.copy2(ROOT / "install-bb-chrome.sh", self.checkout)
        shutil.copy2(ROOT / "bb-skills/bb-chrome/SKILL.md", self.source)

    def install(self, checkout=None):
        return subprocess.run(
            [str((checkout or self.checkout) / "install-bb-chrome.sh")],
            cwd=self.home,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
        )

    def test_install_and_repeat_install(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.destination.readlink(), self.source.resolve())
        original_inode = self.destination.lstat().st_ino

        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.destination.lstat().st_ino, original_inode)

    def test_repair_link_after_moving_checkout(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        moved_checkout = self.home / "moved dotfiles"
        self.checkout.rename(moved_checkout)
        self.assertFalse(self.destination.exists())

        result = self.install(moved_checkout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.destination.resolve(), moved_checkout.resolve() / "bb-skills/bb-chrome"
        )

    def test_existing_skill_directory_is_preserved(self):
        self.destination.mkdir(parents=True)
        original = self.destination / "SKILL.md"
        original.write_text("User skill")

        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(list(self.destination.iterdir()), [original])
        self.assertEqual(original.read_text(), "User skill")

    def test_unrelated_dangling_link_is_preserved(self):
        self.destination.parent.mkdir(parents=True)
        custom_target = self.home / "custom-skills/bb-chrome"
        self.destination.symlink_to(custom_target)

        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.destination.readlink(), custom_target)

    def test_live_link_with_installer_target_shape_is_preserved(self):
        self.destination.parent.mkdir(parents=True)
        custom_target = self.home / "custom-config/bb-skills/bb-chrome"
        custom_target.mkdir(parents=True)
        (custom_target / "SKILL.md").write_text("User skill")
        self.destination.symlink_to(custom_target)

        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.destination.readlink(), custom_target)

    def test_missing_source_directory_reports_missing_skill(self):
        self.source.rename(self.checkout / "moved-skill")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing BB Chrome skill", result.stderr)
        self.assertFalse(self.destination.is_symlink())

    def test_temporary_bb_checkout_is_rejected(self):
        temporary_checkout = self.home / (
            ".bb/plugins/environment-git-worktree/host-data/worktrees/test/dotfiles"
        )
        temporary_checkout.parent.mkdir(parents=True)
        self.checkout.rename(temporary_checkout)

        result = self.install(temporary_checkout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("permanent dotfiles checkout", result.stderr)
        self.assertFalse(self.destination.is_symlink())


if __name__ == "__main__":
    unittest.main()
