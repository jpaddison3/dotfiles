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
        shutil.copy2(ROOT / "Makefile", self.checkout)
        result = subprocess.run(
            ["make", "install-bb-chrome"],
            cwd=self.checkout,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
        )
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
        self.assertIn("Updated dangling BB Chrome skill link", result.stdout)
        self.assertEqual(
            self.destination.resolve(), moved_checkout.resolve() / "bb-skills/bb-chrome"
        )

    def test_relative_link_to_current_skill_is_a_noop(self):
        self.destination.parent.mkdir(parents=True)
        relative_target = Path(os.path.relpath(self.source, self.destination.parent))
        self.destination.symlink_to(relative_target)

        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.destination.readlink(), relative_target)

    def test_existing_skill_directory_is_preserved(self):
        self.destination.mkdir(parents=True)
        original = self.destination / "SKILL.md"
        original.write_text("User skill")

        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(list(self.destination.iterdir()), [original])
        self.assertEqual(original.read_text(), "User skill")

    def test_relative_dangling_link_is_preserved(self):
        self.destination.parent.mkdir(parents=True)
        custom_target = Path("../custom/bb-skills/bb-chrome")
        self.destination.symlink_to(custom_target)

        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.destination.readlink(), custom_target)

    def test_unrelated_absolute_dangling_link_is_preserved(self):
        self.destination.parent.mkdir(parents=True)
        custom_target = self.home / "custom-skills/bb-chrome"
        self.destination.symlink_to(custom_target)

        result = self.install()
        self.assertNotEqual(result.returncode, 0)
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

    @unittest.skipIf(os.geteuid() == 0, "root can traverse a mode 000 directory")
    def test_inaccessible_link_target_is_preserved(self):
        self.destination.parent.mkdir(parents=True)
        old_checkout = self.home / "old checkout"
        old_skill = old_checkout / "bb-skills/bb-chrome"
        old_skill.mkdir(parents=True)
        self.destination.symlink_to(old_skill)

        old_checkout.chmod(0o000)
        try:
            result = self.install()
        finally:
            old_checkout.chmod(0o755)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.destination.readlink(), old_skill)

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

    def test_checkout_in_agent_scratch_is_rejected(self):
        scratch_checkout = self.home / ".cache/agent-tmp/dotfiles"
        scratch_checkout.parent.mkdir(parents=True)
        self.checkout.rename(scratch_checkout)

        result = self.install(scratch_checkout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("permanent dotfiles checkout", result.stderr)
        self.assertFalse(self.destination.is_symlink())

    def test_git_linked_worktree_is_rejected(self):
        git = [
            "git", "-C", str(self.checkout),
            "-c", "user.name=Installer Test",
            "-c", "user.email=installer-test@example.com",
            "-c", "commit.gpgSign=false",
            "-c", "core.hooksPath=/dev/null",
        ]
        subprocess.run([*git, "init", "--quiet"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "--quiet", "-m", "Test checkout"], check=True)
        worktree = self.home / "linked worktree"
        subprocess.run([*git, "worktree", "add", "--detach", "--quiet", worktree], check=True)

        result = self.install(worktree)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("main dotfiles checkout", result.stderr)
        self.assertFalse(self.destination.is_symlink())


if __name__ == "__main__":
    unittest.main()
