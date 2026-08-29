#!/usr/bin/env python3
"""Tests for block-gdoc-cat-devnull.py's statement-aware deny."""
import importlib.util
import json
import os
import subprocess
import unittest

HOOK = os.path.join(
    os.path.dirname(__file__), "..", "block-gdoc-cat-devnull.py"
)
spec = importlib.util.spec_from_file_location("block_gdoc", HOOK)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
should_deny = mod.should_deny


class ShouldDeny(unittest.TestCase):
    # --- the incident shapes: deny ---

    def test_stdout_discarded(self):
        self.assertTrue(should_deny("gdoc cat 1abc >/dev/null"))

    def test_stderr_discarded(self):
        self.assertTrue(should_deny("gdoc cat 1abc > baseline.md 2>/dev/null"))

    def test_merged_discard(self):
        self.assertTrue(should_deny("gdoc cat 1abc >/dev/null 2>&1"))
        self.assertTrue(should_deny("gdoc cat 1abc &>/dev/null"))

    def test_deny_survives_other_statements(self):
        self.assertTrue(
            should_deny("echo start; gdoc cat 1abc 2>/dev/null; echo done")
        )

    def test_unparseable_falls_back_to_text_grep(self):
        # Unbalanced quote: scanner refuses, old .sh behavior is the floor.
        self.assertTrue(should_deny("gdoc cat 1abc >/dev/null; echo 'oops"))

    def test_path_prefixed_gdoc(self):
        self.assertTrue(should_deny("~/bin/gdoc cat 1abc 2>/dev/null"))

    # --- the false-positive classes the .sh had: allow ---

    def test_recommended_pattern_allowed(self):
        self.assertFalse(should_deny("gdoc cat 1abc > baseline.md"))

    def test_mention_in_heredoc_body_allowed(self):
        # The PR-body edit this hook denied on 2026-08-29: the command only
        # *documented* the rule inside a heredoc.
        cmd = (
            "cat > pr-body.md <<'EOF'\n"
            "the motivating incident was `gdoc cat DOC >/dev/null`\n"
            "EOF\n"
            "gh pr edit 2 --body-file pr-body.md"
        )
        self.assertFalse(should_deny(cmd))

    def test_discard_in_unrelated_statement_allowed(self):
        self.assertFalse(
            should_deny("gdoc cat 1abc > baseline.md; pgrep -f x >/dev/null")
        )

    def test_pipe_downstream_discard_allowed(self):
        # gdoc cat's own stderr stays visible; the discard belongs to grep.
        self.assertFalse(should_deny("gdoc cat 1abc | grep -c foo 2>/dev/null"))

    def test_plain_gdoc_cat_allowed(self):
        self.assertFalse(should_deny("gdoc cat 1abc"))

    def test_unrelated_command_allowed(self):
        self.assertFalse(should_deny("ls /nonexistent 2>/dev/null"))


class EndToEnd(unittest.TestCase):
    def run_hook(self, cmd):
        payload = json.dumps({"tool_input": {"command": cmd}})
        proc = subprocess.run(
            [HOOK], input=payload, capture_output=True, text=True, timeout=30
        )
        self.assertEqual(proc.returncode, 0)
        return proc.stdout.strip()

    def test_denies_with_reason(self):
        out = self.run_hook("gdoc cat 1abc >/dev/null")
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("gdoc write", decision["permissionDecisionReason"])

    def test_silent_on_allowed_command(self):
        self.assertEqual(self.run_hook("gdoc cat 1abc > baseline.md"), "")

    def test_silent_on_non_json_stdin(self):
        proc = subprocess.run(
            [HOOK], input="not json", capture_output=True, text=True, timeout=30
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
