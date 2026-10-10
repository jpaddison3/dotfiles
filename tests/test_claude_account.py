import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHIM_SRC = ROOT / "codex-shim" / "claude-account"
BASH = "/bin/bash"

FAKE_CLAUDE = """#!/bin/sh
echo "FAKE-CLAUDE"
echo "CCD=${CLAUDE_CONFIG_DIR-<unset>}"
echo "TOKEN=${CLAUDE_CODE_OAUTH_TOKEN-<unset>}"
echo "ARGS=$*"
"""

DEFAULT_TABLE = """# comment
~/Documents/dotfiles ~/.claude-gmail
~/personal-coding/gdoc ~/.claude-gmail

~/80k/ai-products-research  ~/.claude-team
"""


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True,
    )


class ClaudeAccountShimTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.shim_dir = self.tmp / "shim"
        self.shim_dir.mkdir()
        (self.shim_dir / "claude").symlink_to(SHIM_SRC)
        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()
        fake = self.bin_dir / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(0o755)
        for d in (".claude", ".claude-gmail", ".claude-team"):
            (self.home / d).mkdir()
        (self.home / ".config").mkdir()
        self.write_table(DEFAULT_TABLE)

    # -- helpers -----------------------------------------------------------
    def write_table(self, text):
        (self.home / ".config" / "claude-accounts").write_text(text)

    def repo(self, rel):
        path = self.home / rel
        path.mkdir(parents=True)
        git(path, "init", "-q")
        git(path, "commit", "-q", "--allow-empty", "-m", "init")
        return path

    def run_shim(self, cwd, args=(), env=None, path=None):
        base = {
            "HOME": str(self.home),
            "PATH": path or f"{self.shim_dir}:{self.bin_dir}:/usr/bin:/bin",
        }
        base.update(env or {})
        return subprocess.run(
            [str(self.shim_dir / "claude"), *args],
            cwd=cwd, env=base, capture_output=True, text=True, timeout=30,
        )

    def ccd(self, result):
        for line in result.stdout.splitlines():
            if line.startswith("CCD="):
                return line[4:]
        self.fail(f"no CCD in output: {result.stdout!r} / {result.stderr!r}")

    def transcript(self, config_dir, session_id):
        d = self.home / config_dir / "projects" / "-some-project"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{session_id}.jsonl").write_text("{}\n")

    # -- repo identity -----------------------------------------------------
    def test_main_checkout_match(self):
        repo = self.repo("Documents/dotfiles")
        r = self.run_shim(repo, ["--version"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ccd(r), str(self.home / ".claude-gmail"))
        self.assertIn("ARGS=--version", r.stdout)

    def test_linked_worktree_match(self):
        repo = self.repo("Documents/dotfiles")
        wt = self.home / "dev" / "worktrees" / "dotfiles" / "jpa-x"
        wt.parent.mkdir(parents=True)
        git(repo, "worktree", "add", "-q", "-b", "x", str(wt))
        r = self.run_shim(wt)
        self.assertEqual(self.ccd(r), str(self.home / ".claude-gmail"))
        self.assertIn("repo", self.run_shim(wt, env={"CLAUDE_ACCOUNT_DEBUG": "1"}).stderr)

    def test_subdirectory_match(self):
        repo = self.repo("personal-coding/gdoc")
        sub = repo / "a" / "b"
        sub.mkdir(parents=True)
        self.assertEqual(self.ccd(self.run_shim(sub)), str(self.home / ".claude-gmail"))

    def test_non_git_directory_matches_on_cwd(self):
        d = self.home / "80k" / "ai-products-research" / "sub"
        d.mkdir(parents=True)
        r = self.run_shim(d, env={"CLAUDE_ACCOUNT_DEBUG": "1"})
        self.assertIn("rule=cwd", r.stderr)
        self.assertIn(f"config={self.home}/.claude-team", r.stderr)

    def test_symlinked_cwd_resolves_physically(self):
        repo = self.repo("personal-coding/gdoc")
        link = self.tmp / "link"
        link.symlink_to(repo)
        self.assertEqual(self.ccd(self.run_shim(link)), str(self.home / ".claude-gmail"))

    def test_directory_boundary(self):
        self.repo("personal-coding/gdoc")
        other = self.repo("personal-coding/gdoc-foo")
        r = self.run_shim(other)
        self.assertEqual(self.ccd(r), "<unset>")

    def test_longest_match_wins(self):
        self.write_table(
            "~/personal-coding ~/.claude-team\n"
            "~/personal-coding/gdoc ~/.claude-gmail\n"
        )
        gdoc = self.repo("personal-coding/gdoc")
        other = self.repo("personal-coding/other")
        self.assertEqual(self.ccd(self.run_shim(gdoc)), str(self.home / ".claude-gmail"))
        self.assertEqual(self.ccd(self.run_shim(other)), str(self.home / ".claude-team"))

    def test_no_match_leaves_config_dir_unset(self):
        repo = self.repo("somewhere/else")
        r = self.run_shim(repo, env={"CLAUDE_CODE_OAUTH_TOKEN": "tok"})
        self.assertEqual(self.ccd(r), "<unset>")
        self.assertIn("TOKEN=tok", r.stdout)

    # -- explicit / token --------------------------------------------------
    def test_explicit_config_dir_passthrough(self):
        repo = self.repo("Documents/dotfiles")
        r = self.run_shim(repo, env={"CLAUDE_CONFIG_DIR": "/x/custom", "CLAUDE_CODE_OAUTH_TOKEN": "tok"})
        self.assertEqual(self.ccd(r), "/x/custom")
        self.assertIn("TOKEN=tok", r.stdout)

    def test_token_dropped_on_remap(self):
        repo = self.repo("Documents/dotfiles")
        r = self.run_shim(repo, env={"CLAUDE_CODE_OAUTH_TOKEN": "tok"})
        self.assertEqual(self.ccd(r), str(self.home / ".claude-gmail"))
        self.assertIn("TOKEN=<unset>", r.stdout)

    # -- resume ------------------------------------------------------------
    def test_resume_follows_transcript_account(self):
        repo = self.repo("80k/ai-products-research")
        self.transcript(".claude-gmail", "abc123")
        for args in (["--resume", "abc123"], ["--resume=abc123"], ["-r", "abc123"]):
            r = self.run_shim(repo, args)
            self.assertEqual(self.ccd(r), str(self.home / ".claude-gmail"), args)
            self.assertIn("ARGS=" + " ".join(args), r.stdout)

    def test_resume_transcript_in_default_unsets_variable(self):
        repo = self.repo("80k/ai-products-research")
        self.transcript(".claude", "abc123")
        r = self.run_shim(repo, ["--resume", "abc123"], env={"CLAUDE_CODE_OAUTH_TOKEN": "tok"})
        self.assertEqual(self.ccd(r), "<unset>")
        self.assertIn("TOKEN=tok", r.stdout)

    def test_resume_prefers_cwd_account_among_holders(self):
        repo = self.repo("80k/ai-products-research")
        self.transcript(".claude", "abc123")
        self.transcript(".claude-team", "abc123")
        self.transcript(".claude-gmail", "abc123")
        self.assertEqual(self.ccd(self.run_shim(repo, ["-r", "abc123"])), str(self.home / ".claude-team"))

    def test_resume_multiple_holders_none_is_cwd_prefers_default(self):
        repo = self.repo("somewhere/else")
        self.transcript(".claude", "abc123")
        self.transcript(".claude-team", "abc123")
        self.assertEqual(self.ccd(self.run_shim(repo, ["-r", "abc123"])), "<unset>")

    def test_resume_id_not_found_falls_through_to_cwd(self):
        repo = self.repo("Documents/dotfiles")
        r = self.run_shim(repo, ["--resume", "nope"])
        self.assertEqual(self.ccd(r), str(self.home / ".claude-gmail"))

    def test_bare_resume_and_continue_use_cwd(self):
        repo = self.repo("Documents/dotfiles")
        self.transcript(".claude-team", "abc123")
        for args in (["--resume"], ["--resume", "--model", "x"], ["-c"], ["--continue"]):
            self.assertEqual(self.ccd(self.run_shim(repo, args)), str(self.home / ".claude-gmail"), args)

    # -- fail open ---------------------------------------------------------
    def test_missing_table_fails_open(self):
        (self.home / ".config" / "claude-accounts").unlink()
        repo = self.repo("Documents/dotfiles")
        r = self.run_shim(repo)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.ccd(r), "<unset>")
        self.assertIn("claude-account:", r.stderr)

    def test_malformed_line_skipped_rest_applies(self):
        self.write_table(
            "just-one-field\n"
            "relative/path ~/.claude-team\n"
            "~/a ~/b ~/c\n"
            "~/Documents/dotfiles ~/.claude-gmail\n"
        )
        repo = self.repo("Documents/dotfiles")
        r = self.run_shim(repo)
        self.assertEqual(self.ccd(r), str(self.home / ".claude-gmail"))
        self.assertEqual(r.stderr.count("malformed"), 3)

    def test_missing_mapped_dir_falls_back_to_default(self):
        shutil.rmtree(self.home / ".claude-gmail")
        repo = self.repo("Documents/dotfiles")
        r = self.run_shim(repo, env={"CLAUDE_CODE_OAUTH_TOKEN": "tok"})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.ccd(r), "<unset>")
        self.assertIn("TOKEN=tok", r.stdout)
        self.assertIn("does not exist", r.stderr)
        self.assertFalse((self.home / ".claude-gmail").exists())

    # -- real binary resolution -------------------------------------------
    def test_no_real_binary_exits_127(self):
        r = self.run_shim(self.home, path=f"{self.shim_dir}:/usr/bin:/bin")
        self.assertEqual(r.returncode, 127)
        self.assertIn("claude: command not found", r.stderr)

    def test_shim_dir_first_on_path_does_not_self_exec(self):
        r = self.run_shim(self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("FAKE-CLAUDE", r.stdout)

    def test_runs_under_system_bash(self):
        r = subprocess.run(
            [BASH, str(SHIM_SRC)], cwd=self.home, capture_output=True, text=True, timeout=30,
            env={"HOME": str(self.home), "PATH": f"{self.bin_dir}:/usr/bin:/bin"},
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("FAKE-CLAUDE", r.stdout)

    # -- debug knob --------------------------------------------------------
    def test_debug_knob_reports_and_does_not_exec(self):
        repo = self.repo("Documents/dotfiles")
        r = self.run_shim(repo, env={"CLAUDE_ACCOUNT_DEBUG": "1", "CLAUDE_CODE_OAUTH_TOKEN": "tok"})
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("FAKE-CLAUDE", r.stdout)
        self.assertIn(f"real={self.bin_dir}/claude", r.stderr)
        self.assertIn(f"config={self.home}/.claude-gmail rule=repo token=dropped", r.stderr)

    def test_debug_knob_default_and_explicit(self):
        repo = self.repo("somewhere/else")
        r = self.run_shim(repo, env={"CLAUDE_ACCOUNT_DEBUG": "1"})
        self.assertIn("config=default rule=none token=absent", r.stderr)
        r = self.run_shim(repo, env={"CLAUDE_ACCOUNT_DEBUG": "1", "CLAUDE_CONFIG_DIR": "/x"})
        self.assertIn("config=/x rule=explicit", r.stderr)


if __name__ == "__main__":
    unittest.main()
