#!/usr/bin/env python3
"""PreToolUse (Bash) hook: deny a `gdoc cat` whose output is sent to /dev/null.

`gdoc cat` is gdoc's read-baseline step; its stderr carries the "doc edited by
JP Addison (vN -> vM)" guard. Silencing it makes the next `gdoc write` clobber
JP's edits (happened 2026-08-20). Read to a file and diff instead.

Statement-aware since 2026-08-29, replacing a whole-text grep (.sh) that
denied any command merely *mentioning* both `gdoc cat` and `/dev/null` -- a
heredoc body documenting this very rule, or a discard in an unrelated
statement of the same command, tripped it. Now the deny fires only when a
statement actually headed by `gdoc cat` carries a real, top-level /dev/null
redirect, as judged by stderr-to-logfile.py's quote/heredoc/subshell-aware
scanner. A command that scanner can't parse falls back to the old
conservative whole-text grep, so nothing the .sh would have caught slips
through unparsed.
"""
import importlib.util
import json
import os
import re
import sys

GDOC_CAT = re.compile(r"(?:^|[\s;|&({])(?:\S*/)?gdoc\s+cat(?=\s|$)")
# Discard kinds whose target is literally /dev/null; a redirect on some other
# fd (3>/dev/null) doesn't silence anything gdoc prints.
DEVNULL_KINDS = {"stderr_null", "stdout_null_only", "combined_null", "stdout_null_dup"}
REASON = (
    "BLOCKED: `gdoc cat` with output sent to /dev/null. That silences gdoc's "
    '"doc edited by JP" baseline guard, and the next `gdoc write` then '
    "clobbers JP's edits (it happened 2026-08-20). Instead: "
    "`gdoc cat DOC > some-file.md` (keep stderr visible), diff against your "
    "last-written file, merge JP's edits, then write."
)


def _scan(cmd):
    here = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(here, "stderr-to-logfile.py")
    spec = importlib.util.spec_from_file_location("stderr_to_logfile", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.scan(cmd)


def should_deny(cmd):
    # The old .sh's two conditions, kept as a fast path and as the floor the
    # unparseable fallback preserves.
    if "/dev/null" not in cmd or not GDOC_CAT.search(cmd):
        return False
    try:
        scanned = _scan(cmd)
    except Exception:
        scanned = None
    if scanned is None:
        return True
    matches, statement_start = scanned
    for m in matches:
        if m.kind not in DEVNULL_KINDS:
            continue
        start = statement_start.get(m.statement_id, 0)
        end = statement_start.get(m.statement_id + 1, len(cmd))
        if GDOC_CAT.search(cmd[start:end]):
            return True
    return False


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    tool_input = payload.get("tool_input")
    cmd = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(cmd, str) or not cmd.strip():
        return
    if should_deny(cmd):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": REASON,
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
