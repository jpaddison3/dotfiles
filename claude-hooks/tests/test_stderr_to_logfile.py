#!/usr/bin/env python3
"""Regression tests for stderr-to-logfile.py's rewrite() — run directly
(no pytest dependency): ./claude-hooks/tests/test_stderr_to_logfile.py
"""
import importlib.util
import os
import sys
import unittest

HOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "stderr-to-logfile.py")
spec = importlib.util.spec_from_file_location("stderr_to_logfile", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
rewrite = mod.rewrite


class RewriteCases(unittest.TestCase):
    def assert_rewritten(self, cmd):
        result = rewrite(cmd)
        self.assertIsNotNone(result, f"expected a rewrite for: {cmd!r}")
        return result

    def assert_untouched(self, cmd):
        result = rewrite(cmd)
        self.assertIsNone(result, f"expected no rewrite for: {cmd!r}, got: {result!r}")

    # --- the three target forms ---

    def test_stderr_only(self):
        out = self.assert_rewritten("npm test 2>/dev/null")
        self.assertIn("npm test 2> >(", out)
        # The live redirect target is gone; /dev/null only survives inside
        # the quoted label (the original command text, kept verbatim).
        live_part = out.split(mod.SINK_CMD)[0]
        self.assertNotIn("/dev/null", live_part)

    def test_stderr_only_spaced(self):
        out = self.assert_rewritten("npm test 2> /dev/null")
        self.assertIn("2> >(", out)

    def test_combined(self):
        out = self.assert_rewritten("noisy-tool &>/dev/null")
        self.assertIn(">/dev/null 2> >(", out)

    def test_combined_alt_operator(self):
        out = self.assert_rewritten("noisy-tool >&/dev/null")
        self.assertIn(">/dev/null 2> >(", out)

    def test_stdout_then_dup(self):
        out = self.assert_rewritten("make build >/dev/null 2>&1")
        self.assertIn(">/dev/null 2> >(", out)
        live_part = out.split(mod.SINK_CMD)[0]
        self.assertNotIn("2>&1", live_part)

    def test_stdout_then_dup_explicit_fd1(self):
        out = self.assert_rewritten("make build 1>/dev/null 2>&1")
        self.assertTrue(out.startswith("make build 1>/dev/null 2> >("))

    def test_stdout_then_dup_append(self):
        out = self.assert_rewritten("make build >>/dev/null 2>&1")
        self.assertIn(">>/dev/null 2> >(", out)

    def test_label_is_full_original_command(self):
        cmd = "npm test 2>/dev/null"
        out = self.assert_rewritten(cmd)
        self.assertIn(cmd, out)  # shlex.quote of a space-only string is unquoted

    def test_stdout_and_stderr_separately_to_null(self):
        # Each fd names its own target explicitly -- no cross-fd dependency,
        # so the stderr leg alone is eligible.
        out = self.assert_rewritten("cmd >/dev/null 2>/dev/null")
        self.assertIn(">/dev/null 2> >(", out)
        live_part = out.split(mod.SINK_CMD)[0]
        self.assertNotIn("/dev/null 2>/dev/null", live_part)

    # --- exclusions the acceptance criteria call out by name ---

    def test_plain_stdout_discard_untouched(self):
        self.assert_untouched("build-thing > /dev/null")

    def test_stderr_already_routed_elsewhere_untouched(self):
        self.assert_untouched("flaky-tool 2>error.log")

    def test_stderr_visible_via_reordered_dup_untouched(self):
        # 2>&1 before the stdout redirect: stderr goes to the *original*
        # stdout (terminal), not to null. Must not be treated as a discard.
        self.assert_untouched("cmd 2>&1 >/dev/null")

    def test_fd1_follows_fd2_untouched(self):
        # Effectively both -> null, but written via order-dependent dups
        # rather than an explicit target; too order-sensitive to rewrite.
        self.assert_untouched("cmd 2>/dev/null 1>&2")

    def test_redundant_conflicting_redirect_untouched(self):
        self.assert_untouched("cmd 2>/dev/null 2>&1")

    def test_discard_inside_double_quotes_untouched(self):
        self.assert_untouched('echo "run with 2>/dev/null to silence"')

    def test_discard_inside_single_quotes_untouched(self):
        self.assert_untouched("echo 'redirect stderr via 2>/dev/null'")

    def test_heredoc_body_mentioning_discard_untouched(self):
        cmd = "cat <<'EOF'\nsome text 2>/dev/null in here\nEOF\n"
        self.assert_untouched(cmd)

    def test_real_redirect_before_heredoc_in_same_command_rewritten(self):
        # A qualifying redirect in an earlier statement must not be thrown
        # away just because a later, unrelated statement uses a heredoc.
        cmd = "pkill -f server.py 2>/dev/null; cat <<'EOF'\nbody text\nEOF\n"
        out = self.assert_rewritten(cmd)
        self.assertIn("pkill -f server.py 2> >(", out)
        self.assertIn("cat <<'EOF'\nbody text\nEOF\n", out)

    def test_heredoc_with_real_redirect_after_untouched_conservatively(self):
        # A real, rewritable redirect can appear after a heredoc closes; this
        # is in-scope in principle, but exercised here mainly to prove the
        # heredoc body itself was correctly skipped rather than mis-scanned.
        cmd = "cat <<EOF\nhello 2>/dev/null\nEOF\n"
        self.assert_untouched(cmd)

    def test_probe_command_v_exempt(self):
        self.assert_untouched("command -v rg 2>/dev/null")

    def test_probe_which_exempt(self):
        self.assert_untouched("which rg 2>/dev/null")

    def test_probe_hash_exempt(self):
        self.assert_untouched("hash rg 2>/dev/null")

    def test_probe_type_exempt(self):
        self.assert_untouched("type rg 2>/dev/null")

    def test_probe_only_exempts_its_own_statement(self):
        out = self.assert_rewritten("which rg 2>/dev/null; npm test 2>/dev/null")
        self.assertIn("which rg 2>/dev/null", out)  # left alone
        self.assertIn("npm test 2> >(", out)  # rewritten

    def test_unterminated_heredoc_untouched(self):
        self.assert_untouched("cat <<EOF\nno closing delimiter 2>/dev/null")

    def test_unbalanced_quote_untouched(self):
        self.assert_untouched("echo 'unterminated 2>/dev/null")

    def test_positional_param_not_mistaken_for_fd(self):
        # $2 immediately followed by '>' is a param expansion + plain fd1
        # redirect in real bash, not an fd-2 redirect.
        self.assert_untouched("myfunc $2>/dev/null")

    def test_no_redirect_at_all_untouched(self):
        self.assert_untouched("echo hello")

    def test_empty_command_untouched(self):
        self.assert_untouched("")

    # --- compound commands: only the matching statement is touched ---

    def test_second_statement_in_chain_rewritten(self):
        out = self.assert_rewritten("echo hi && npm test 2>/dev/null")
        self.assertTrue(out.startswith("echo hi && npm test 2> >("))

    def test_pipeline_segment_rewritten(self):
        out = self.assert_rewritten("gen-data 2>/dev/null | wc -l")
        self.assertIn("gen-data 2> >(", out)
        self.assertTrue(out.endswith("| wc -l"))

    def test_subshell_redirect_untouched(self):
        # Redirect lives inside a $(...) / (...) grouping -- too risky to
        # rewrite in place, left alone by design.
        self.assert_untouched("result=$(flaky-tool 2>/dev/null)")


if __name__ == "__main__":
    unittest.main()
