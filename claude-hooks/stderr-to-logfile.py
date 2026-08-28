#!/usr/bin/env python3
"""PreToolUse (Bash) hook: rewrite a discarded stderr into the log sink.

Detects the three ways a command throws stderr into /dev/null (`2>/dev/null`,
`&>/dev/null`, and `>/dev/null 2>&1`) and swaps just that redirect for a
process substitution piping into logfile-sink.py, labelled with the full
original command. Everything else about the command is untouched: stdout
keeps whatever destination it already had, and output redirects never affect
exit status, so callers see identical behavior.

This is string surgery on arbitrary shell, so it is conservative by
construction: anything not confidently recognized (heredocs, the discard
text sitting inside a quoted string, multiple redirects touching the same
fd, `command -v`/which/hash/type probes) is left alone. A missed rewrite is
cheap; a mangled command is not.
"""
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass

DEVNULL = "/dev/null"
BOUNDARY_AFTER = set(" \t\n;&|)")
# Chars that, immediately before a candidate fd digit or bare '>', mean it's
# part of something else (a word, a number, a parameter expansion) rather
# than a fresh redirect token.
PRECEDE_BLOCKERS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$}'\""
)
PROBE_RE = re.compile(r"^(command\s+-v|which|hash|type)(\s|$)")
SINK_PATH = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "logfile-sink.py")
SINK_CMD = '"$HOME/.claude/hooks/logfile-sink.py"'

# Match kinds that touch fd 2 (or, for stdout_null_dup, fold in the fd1 leg
# too) and therefore count toward the "only one redirect may touch this fd"
# ambiguity guard. Only these three are ever eligible for rewriting.
REWRITABLE = {"stderr_null", "combined_null", "stdout_null_dup"}
# Everything else that also counts toward the ambiguity tally: further fd2
# redirects we don't specifically target, and dup-style redirects whose
# target depends on redirect order (2>&1 alone, 1>&2/>&2) rather than naming
# /dev/null outright.
RISKY = REWRITABLE | {"dup_2_to_1", "other_fd2", "fd1_follows_fd2"}


@dataclass
class Match:
    start: int
    end: int
    kind: str
    statement_id: int
    keep_prefix_end: int = -1  # for stdout_null_dup: end of the ">... /dev/null" leg


def _boundary_after(s, i):
    return i >= len(s) or s[i] in BOUNDARY_AFTER


def _boundary_before(s, i):
    return i == 0 or s[i - 1] not in PRECEDE_BLOCKERS


def _skip_spaces(s, i):
    n = len(s)
    while i < n and s[i] in " \t":
        i += 1
    return i


def scan(cmd):
    """Walk cmd once, tracking quote/paren/heredoc state, and return the list
    of top-level redirect matches, or None if the command doesn't parse
    cleanly enough to trust (unbalanced quotes/parens, unterminated heredoc).
    """
    n = len(cmd)
    i = 0
    squote = dquote = backtick = False
    depth = 0
    statement_id = 0
    statement_start = {0: 0}
    pending_heredocs = []
    in_heredoc = False
    heredoc_delim = None
    heredoc_strip = False
    matches = []

    def new_statement(next_i):
        nonlocal statement_id
        statement_id += 1
        statement_start[statement_id] = next_i

    while i < n:
        c = cmd[i]

        if in_heredoc:
            nl = cmd.find("\n", i)
            line_end = nl if nl != -1 else n
            line = cmd[i:line_end]
            test = line.lstrip("\t") if heredoc_strip else line
            if test == heredoc_delim:
                i = line_end + 1 if nl != -1 else n
                if pending_heredocs:
                    heredoc_delim, heredoc_strip = pending_heredocs.pop(0)
                else:
                    in_heredoc = False
                continue
            i = line_end + 1 if nl != -1 else n
            continue

        if squote:
            if c == "'":
                squote = False
            i += 1
            continue
        if dquote:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                dquote = False
            i += 1
            continue
        if backtick:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == "`":
                backtick = False
            i += 1
            continue

        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "'":
            squote = True
            i += 1
            continue
        if c == '"':
            dquote = True
            i += 1
            continue
        if c == "`":
            backtick = True
            i += 1
            continue
        if c == "(":
            depth += 1
            i += 1
            continue
        if c == ")":
            depth = max(0, depth - 1)
            i += 1
            continue

        if depth != 0:
            i += 1
            continue

        # --- top-level (depth 0, unquoted) from here down ---

        if cmd[i : i + 3] == "<<<":
            i += 3
            continue

        if cmd[i : i + 2] == "<<":
            j = i + 2
            strip = False
            if j < n and cmd[j] == "-":
                strip = True
                j += 1
            j = _skip_spaces(cmd, j)
            delim = None
            if j < n and cmd[j] in ("'", '"'):
                q = cmd[j]
                end = cmd.find(q, j + 1)
                if end == -1:
                    return None
                delim = cmd[j + 1 : end]
                j = end + 1
            else:
                m = re.match(r"[A-Za-z0-9_]+", cmd[j:])
                if not m:
                    return None
                delim = m.group(0)
                j += len(delim)
            pending_heredocs.append((delim, strip))
            i = j
            continue

        if cmd[i : i + 2] == "&&" or cmd[i : i + 2] == "||":
            new_statement(i + 2)
            i += 2
            continue
        if c == "\n" and pending_heredocs and not in_heredoc:
            # The rest of the *current* line (redirects, pipes, &&...) is
            # still normal top-level syntax; the heredoc body proper only
            # starts on the line after the <<DELIM token.
            heredoc_delim, heredoc_strip = pending_heredocs.pop(0)
            in_heredoc = True
            new_statement(i + 1)
            i += 1
            continue
        if c in ";\n|":
            new_statement(i + 1)
            i += 1
            continue

        if c == "&":
            # '&&' and bare '&' (background separator) are handled above /
            # below; '&>' must be checked before either, since it starts
            # with the same character bare-'&' would otherwise claim.
            if cmd[i : i + 2] == "&>":
                tok_start = i
                j = i + 2
                if j < n and cmd[j] == ">":
                    j += 1
                j2 = _skip_spaces(cmd, j)
                if cmd[j2 : j2 + len(DEVNULL)] == DEVNULL and _boundary_after(
                    cmd, j2 + len(DEVNULL)
                ):
                    end = j2 + len(DEVNULL)
                    matches.append(
                        Match(tok_start, end, "combined_null", statement_id)
                    )
                    i = end
                    continue
                # &> to something other than /dev/null (real file, fd, ...):
                # touches both fds via a target we don't specifically parse.
                m = re.match(r"[^\s;|()<>]*", cmd[j2:])
                end = j2 + (m.end() if m else 0)
                matches.append(Match(tok_start, end, "other_fd2", statement_id))
                i = max(end, j)
                continue
            new_statement(i + 1)
            i += 1
            continue

        if c == "2" and _boundary_before(cmd, i) and i + 1 < n and cmd[i + 1] == ">":
            tok_start = i
            j = i + 2
            if j < n and cmd[j] == ">":
                j += 1
            if cmd[j : j + 2] == "&1" and _boundary_after(cmd, j + 2):
                matches.append(Match(tok_start, j + 2, "dup_2_to_1", statement_id))
                i = j + 2
                continue
            j2 = _skip_spaces(cmd, j)
            if cmd[j2 : j2 + len(DEVNULL)] == DEVNULL and _boundary_after(
                cmd, j2 + len(DEVNULL)
            ):
                end = j2 + len(DEVNULL)
                matches.append(Match(tok_start, end, "stderr_null", statement_id))
                i = end
                continue
            j3 = _skip_spaces(cmd, j)
            m = re.match(r"[^\s;|()<>]*", cmd[j3:])
            end = j3 + (m.end() if m else 0)
            matches.append(Match(tok_start, end, "other_fd2", statement_id))
            i = max(end, j)
            continue

        if c == ">":
            # '>&' must be checked before plain '>' handling, for the same
            # reason as '&>' above (e.g. '>&2', or '1>&2' reached via the
            # '1' falling through as plain text and landing here on '>').
            if cmd[i : i + 2] == ">&":
                tok_start = i
                j = i + 2
                if cmd[j : j + 1] == "2" and _boundary_after(cmd, j + 1):
                    matches.append(
                        Match(tok_start, j + 1, "fd1_follows_fd2", statement_id)
                    )
                    i = j + 1
                    continue
                j2 = _skip_spaces(cmd, j)
                if cmd[j2 : j2 + len(DEVNULL)] == DEVNULL and _boundary_after(
                    cmd, j2 + len(DEVNULL)
                ):
                    end = j2 + len(DEVNULL)
                    matches.append(
                        Match(tok_start, end, "combined_null", statement_id)
                    )
                    i = end
                    continue
                # >& to some other fd we don't specifically parse (>&3, >&-).
                m = re.match(r"[^\s;|()<>]*", cmd[j:])
                end = j + (m.end() if m else 0)
                matches.append(Match(tok_start, end, "other_fd2", statement_id))
                i = max(end, j)
                continue

            tok_start = i
            j = i + 1
            if j < n and cmd[j] == ">":
                j += 1
            real_start = tok_start
            if (
                tok_start > 0
                and cmd[tok_start - 1] == "1"
                and _boundary_before(cmd, tok_start - 1)
            ):
                real_start = tok_start - 1

            j2 = _skip_spaces(cmd, j)
            if cmd[j2 : j2 + len(DEVNULL)] == DEVNULL and _boundary_after(
                cmd, j2 + len(DEVNULL)
            ):
                end = j2 + len(DEVNULL)
                k = _skip_spaces(cmd, end)
                if (
                    cmd[k : k + 4] == "2>&1"
                    and _boundary_before(cmd, k)
                    and _boundary_after(cmd, k + 4)
                ):
                    matches.append(
                        Match(
                            real_start,
                            k + 4,
                            "stdout_null_dup",
                            statement_id,
                            keep_prefix_end=end,
                        )
                    )
                    i = k + 4
                    continue
                matches.append(
                    Match(real_start, end, "stdout_null_only", statement_id)
                )
                i = end
                continue
            i = j
            continue

        i += 1

    if in_heredoc or pending_heredocs:
        return None
    if squote or dquote or backtick or depth != 0:
        return None

    return matches, statement_start


def rewrite(cmd):
    """Return a rewritten command string, or None if nothing should change."""
    if not os.access(SINK_PATH, os.X_OK):
        # No reader for the process substitution means the command's stderr
        # writes hit a dead pipe -- a big enough burst kills it with SIGPIPE.
        # Leaving the discard alone is strictly better than that.
        return None
    scanned = scan(cmd)
    if scanned is None:
        return None
    matches, statement_start = scanned
    if not matches:
        return None

    by_statement = {}
    for m in matches:
        by_statement.setdefault(m.statement_id, []).append(m)

    to_replace = []  # (start, end, replacement_text)
    for sid, ms in by_statement.items():
        risky = [m for m in ms if m.kind in RISKY]
        if len(risky) != 1:
            continue
        target = risky[0]
        if target.kind not in REWRITABLE:
            continue
        prefix = cmd[statement_start.get(sid, 0) : target.start]
        if PROBE_RE.match(prefix.lstrip(" \t")):
            continue

        label = shlex.quote(cmd)
        sink = f">({SINK_CMD} {label})"
        if target.kind == "stderr_null":
            to_replace.append((target.start, target.end, f"2> {sink}"))
        elif target.kind == "combined_null":
            to_replace.append((target.start, target.end, f">{DEVNULL} 2> {sink}"))
        elif target.kind == "stdout_null_dup":
            keep = cmd[target.start : target.keep_prefix_end]
            to_replace.append((target.start, target.end, f"{keep} 2> {sink}"))

    if not to_replace:
        return None

    to_replace.sort(key=lambda t: t[0])
    out = []
    cursor = 0
    for start, end, replacement in to_replace:
        out.append(cmd[cursor:start])
        out.append(replacement)
        cursor = end
    out.append(cmd[cursor:])
    new_cmd = "".join(out)
    return new_cmd if new_cmd != cmd else None


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    cmd = tool_input.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return

    new_cmd = rewrite(cmd)
    if new_cmd is None:
        return

    updated = dict(tool_input)
    updated["command"] = new_cmd
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": updated,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
    sys.exit(0)
