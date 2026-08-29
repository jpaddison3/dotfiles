#!/usr/bin/env python3
"""Regression tests for stderr-to-logfile.py's rewrite() — run directly
(no pytest dependency): ./claude-hooks/tests/test_stderr_to_logfile.py
"""
import glob
import importlib.util
import os
import pathlib
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "stderr-to-logfile.py")
spec = importlib.util.spec_from_file_location("stderr_to_logfile", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
rewrite = mod.rewrite
SINK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# rewrite() refuses to act when the sink isn't installed, so point it at this
# checkout's copy rather than depending on ~/.claude/hooks being symlinked.
mod.SINK_PATH = os.path.join(SINK_DIR, "logfile-sink.py")


class RewriteCases(unittest.TestCase):
    def assert_rewritten(self, cmd):
        result = rewrite(cmd)
        self.assertIsNotNone(result, f"expected a rewrite for: {cmd!r}")
        return result

    def assert_untouched(self, cmd):
        result = rewrite(cmd)
        self.assertIsNone(result, f"expected no rewrite for: {cmd!r}, got: {result!r}")

    # --- the target forms ---

    def test_stderr_only(self):
        out = self.assert_rewritten("npm test 2>/dev/null")
        self.assertIn("npm test 2> >(", out)
        self.assertIn("--stream=err", out)
        # The live redirect target is gone; /dev/null only survives inside
        # the quoted label (the original command text, kept verbatim).
        live_part = out.split(mod.SINK_CMD)[0]
        self.assertNotIn("/dev/null", live_part)

    def test_stderr_only_spaced(self):
        out = self.assert_rewritten("npm test 2> /dev/null")
        self.assertIn("2> >(", out)

    def test_stdout_only(self):
        out = self.assert_rewritten("build-thing > /dev/null")
        self.assertTrue(out.startswith("build-thing > >("))
        self.assertIn("--stream=out ", out)
        live_part = out.split(mod.SINK_CMD)[0]
        self.assertNotIn("/dev/null", live_part)

    def test_combined(self):
        out = self.assert_rewritten("noisy-tool &>/dev/null")
        self.assertIn("noisy-tool > >(", out)
        self.assertIn("--stream=out+err", out)
        self.assertTrue(out.endswith(") 2>&1"))

    def test_combined_alt_operator(self):
        out = self.assert_rewritten("noisy-tool >&/dev/null")
        self.assertIn("noisy-tool > >(", out)
        self.assertTrue(out.endswith(") 2>&1"))

    def test_stdout_then_dup(self):
        out = self.assert_rewritten("make build >/dev/null 2>&1")
        self.assertTrue(out.startswith("make build > >("))
        self.assertIn("--stream=out+err", out)
        self.assertTrue(out.endswith(") 2>&1"))
        # the original ">/dev/null 2>&1" span survives only inside the label
        live_part = out.split(mod.SINK_CMD)[0]
        self.assertNotIn("/dev/null", live_part)

    def test_stdout_then_dup_explicit_fd1(self):
        out = self.assert_rewritten("make build 1>/dev/null 2>&1")
        self.assertTrue(out.startswith("make build > >("))
        self.assertTrue(out.endswith(") 2>&1"))

    def test_stdout_then_dup_append(self):
        out = self.assert_rewritten("make build >>/dev/null 2>&1")
        self.assertTrue(out.startswith("make build > >("))
        self.assertTrue(out.endswith(") 2>&1"))

    def test_label_is_full_original_command(self):
        cmd = "npm test 2>/dev/null"
        out = self.assert_rewritten(cmd)
        self.assertIn(cmd, out)  # shlex.quote of a space-only string is unquoted

    def test_stdout_and_stderr_separately_to_null(self):
        # Each fd names its own target explicitly -- no cross-fd dependency,
        # so both legs are rewritten, each to its own labelled sink.
        out = self.assert_rewritten("cmd >/dev/null 2>/dev/null")
        self.assertTrue(out.startswith("cmd > >("))
        self.assertIn("--stream=out ", out)
        self.assertIn("2> >(", out)
        self.assertIn("--stream=err", out)

    # --- exclusions the acceptance criteria call out by name ---

    def test_stdout_already_routed_elsewhere_untouched(self):
        # >file plus >/dev/null in one statement: fd 1 is touched twice, so
        # the ambiguity guard refuses to pick one.
        self.assert_untouched("cmd >out.log >/dev/null")

    def test_nonstandard_fd_to_null_untouched(self):
        self.assert_untouched("cmd 3>/dev/null")
        self.assert_untouched("cmd 12>/dev/null")

    def test_stdout_discard_with_real_file_redirect_still_rewrites_stderr(self):
        # The fd-1 tally must not leak into the fd-2 decision.
        out = self.assert_rewritten("cmd >out.log 2>/dev/null")
        self.assertTrue(out.startswith("cmd >out.log 2> >("))

    def test_stdout_discard_beside_stderr_file_redirect(self):
        out = self.assert_rewritten("cmd >/dev/null 2>err.log")
        self.assertTrue(out.startswith("cmd > >("))
        self.assertTrue(out.endswith("2>err.log"))

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
        # redirect in real bash, not an fd-2 redirect: a stdout discard.
        out = self.assert_rewritten("myfunc $2>/dev/null")
        self.assertTrue(out.startswith("myfunc $2> >("))
        self.assertIn("--stream=out ", out)

    def test_probe_stdout_discard_exempt(self):
        self.assert_untouched("command -v rg >/dev/null")
        self.assert_untouched("which rg >/dev/null 2>&1")

    def test_heredoc_into_file_untouched(self):
        self.assert_untouched("cat > out.txt <<'EOF'\nbody\nEOF\n")

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


class SinkMissing(unittest.TestCase):
    def test_no_rewrite_when_sink_is_not_installed(self):
        # Without a live sink the rewrite would point stderr at a pipe nobody
        # reads, and a large burst then SIGPIPEs the command outright.
        original = mod.SINK_PATH
        mod.SINK_PATH = "/nonexistent/logfile-sink.py"
        try:
            self.assertIsNone(rewrite("npm test 2>/dev/null"))
        finally:
            mod.SINK_PATH = original
        self.assertIsNotNone(rewrite("npm test 2>/dev/null"))



class EndToEnd(unittest.TestCase):
    """The rewritten command must actually run under bash and land in ~/.logs."""

    def run_rewritten(self, cmd, expect=()):
        """expect: substrings to poll for in the log before returning -- the
        sink is a process substitution child bash does not wait for."""
        rewritten = rewrite(cmd)
        self.assertIsNotNone(rewritten, f"expected a rewrite for: {cmd!r}")
        home = tempfile.mkdtemp()
        try:
            env = dict(os.environ, HOME=home)
            proc = subprocess.run(
                ["bash", "-c", rewritten.replace("$HOME/.claude/hooks", SINK_DIR)],
                env=env, capture_output=True, text=True, timeout=60,
            )
            deadline = time.time() + 10
            body = ""
            while time.time() < deadline:
                logs = glob.glob(os.path.join(home, ".logs", "*.log"))
                body = pathlib.Path(logs[0]).read_text() if logs else ""
                if body and all(s in body for s in expect):
                    break
                time.sleep(0.05)
            return proc, body
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_stderr_lands_in_logfile_stdout_untouched(self):
        proc, body = self.run_rewritten(
            "sh -c 'echo out; echo boom >&2; exit 3' 2>/dev/null"
        )
        self.assertEqual(proc.stdout, "out\n")
        self.assertEqual(proc.returncode, 3, "exit status must survive the rewrite")
        self.assertEqual(proc.stderr, "", "stderr must not leak back to the caller")
        self.assertIn("boom", body)
        self.assertIn("2>/dev/null", body, "line is labelled with the original command")

    def test_multiline_command_label_is_flattened_to_one_line(self):
        _, body = self.run_rewritten("sh -c 'echo a >&2' 2>/dev/null\nsh -c 'true'")
        self.assertEqual(len(body.strip().splitlines()), 1, body)

    def test_sink_releases_inherited_stdout(self):
        # The sink inherits the caller's stdout, which in a pipeline is the pipe
        # to the next stage. It must let go of it, or that stage blocks for as
        # long as the sink lives.
        read_fd, write_fd = os.pipe()
        proc = subprocess.Popen(
            [os.path.join(SINK_DIR, "logfile-sink.py"), "label"],
            stdin=subprocess.PIPE, stdout=write_fd,
            env=dict(os.environ, HOME=tempfile.mkdtemp()),
        )
        os.close(write_fd)
        try:
            ready, _, _ = select.select([read_fd], [], [], 10)
            self.assertTrue(ready, "sink never released the inherited stdout pipe")
            self.assertEqual(os.read(read_fd, 1), b"", "sink wrote to stdout")
            self.assertIsNone(proc.poll(), "sink should still be running")
        finally:
            os.close(read_fd)
            proc.stdin.close()
            proc.wait(timeout=10)

    def test_high_volume_stderr_is_not_a_bottleneck(self):
        start = time.time()
        _, body = self.run_rewritten(
            "python3 -c \"import sys;[print(i,file=sys.stderr) for i in range(5000)]\""
            " 2>/dev/null"
        )
        elapsed = time.time() - start
        self.assertEqual(len(body.strip().splitlines()), 5000)
        self.assertLess(elapsed, 10, f"5000 stderr lines took {elapsed:.1f}s")

    def test_stdout_lands_in_logfile_stderr_untouched(self):
        proc, body = self.run_rewritten(
            "sh -c 'echo data; echo boom >&2; exit 3' >/dev/null"
        )
        self.assertEqual(proc.stdout, "", "stdout must not leak back to the caller")
        self.assertEqual(proc.stderr, "boom\n", "stderr must still reach the caller")
        self.assertEqual(proc.returncode, 3)
        self.assertIn("[out]", body)
        contents = [l.rsplit("] ", 1)[-1] for l in body.strip().splitlines()]
        self.assertIn("data", contents)
        self.assertNotIn("boom", contents, "stderr content must not be logged")

    def test_merged_discard_lands_both_streams(self):
        proc, body = self.run_rewritten(
            "sh -c 'echo data; echo boom >&2; exit 3' >/dev/null 2>&1",
            expect=("data", "boom"),
        )
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.returncode, 3)
        self.assertIn("[out+err]", body)
        self.assertIn("data", body)
        self.assertIn("boom", body)

    def test_both_fds_discarded_separately_lands_both_labelled(self):
        proc, body = self.run_rewritten(
            "sh -c 'echo data; echo boom >&2' >/dev/null 2>/dev/null",
            expect=("data", "boom"),
        )
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")
        self.assertIn("[out]", body)
        self.assertIn("[err]", body)
        self.assertIn("data", body)
        self.assertIn("boom", body)

    def test_binary_stdout_is_suppressed_not_logged(self):
        proc, body = self.run_rewritten(
            "head -c 100000 /dev/zero >/dev/null", expect=("bytes discarded",)
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("binary output detected", body)
        self.assertIn("bytes discarded", body)
        self.assertLess(len(body), 2000, "raw binary must not land in the log")

    def test_write_cap_bounds_a_flood(self):
        # ~12MB of stdout against the 5MB cap: the log stops growing, the
        # command still exits cleanly (the sink keeps draining the pipe).
        proc, body = self.run_rewritten(
            "python3 -c \"[print('x'*1023) for _ in range(12000)]\" >/dev/null",
            expect=("output cap reached",),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("output cap reached", body)
        self.assertLess(len(body), 6 * 1024 * 1024)

    def test_no_newline_stream_is_flushed_bounded(self):
        # A \r-only progress stream never sends \n; the sink must flush at
        # MAX_LINE instead of buffering without bound, and not stall the pipe.
        proc, body = self.run_rewritten(
            "python3 -c \"import sys;sys.stdout.write('p\\r'*100000)\" >/dev/null",
            expect=("line truncated",),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("line truncated", body)


if __name__ == "__main__":
    unittest.main()
