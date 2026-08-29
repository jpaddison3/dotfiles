# claude-hooks — Claude Code PreToolUse hooks

Tracked source for hooks registered in `~/.claude/settings.json`, which is
itself untracked (personal, machine-local) and so isn't managed by this repo.
`newcomputer.bash` symlinks everything here into `~/.claude/hooks/`; the
settings.json registration is a manual, one-time edit per machine (see below).

## stderr-to-logfile.py + logfile-sink.py

Every AI-run Bash command that discards output into /dev/null — stderr
(`2>/dev/null`), stdout (`>/dev/null`), or both merged (`&>/dev/null`,
`>/dev/null 2>&1`) — gets that redirect transparently rewritten to a
process substitution that pipes into `logfile-sink.py` instead, which
prefixes each line with a timestamp, a stream tag (`[err]` / `[out]` /
`[out+err]`), and the full original command (whitespace-flattened to one
line) and appends it to `~/.logs/YYYY-MM-DD.log`. The AI's command is
never shown the rewrite and doesn't need to cooperate; non-discarded
streams and exit status are untouched. Grep `~/.logs/` (`loggrep <term>`)
when hunting a failure whose output would otherwise be gone.

`stderr-to-logfile.py` is conservative by construction: it only rewrites
when it can find an unambiguous, unquoted, top-level discard redirect, in a
statement where that redirect is the only thing touching its fd and no
order-dependent dup redirect (a bare `2>&1`, `>&2`, `>&3`) appears, outside
heredoc bodies, quoted strings, and `$(...)`/`(...)` subshells, and that
isn't a `command -v`/`which`/`hash`/`type` probe. It also declines to
rewrite at all when `logfile-sink.py` isn't installed and executable, since a
process substitution with no reader SIGPIPEs the command on a large enough
output burst. Anything it isn't sure about is left alone — a missed rewrite is cheap, a mangled command
isn't. See `tests/test_stderr_to_logfile.py` for the case-by-case
behavior.

The sink is hardened against what stdout discards can carry that stderr
rarely does: it reads in chunks, suppresses binary streams (NUL sniff),
flushes never-terminated lines (`\r` progress bars) at 64KB, and caps one
invocation's total append at 5MB (then drains the pipe and notes how many
bytes it dropped) — so a `cat huge.bin >/dev/null` can neither swamp
`~/.logs` nor stall the producing command. Note the cap means a long-lived
daemon launched with `>/dev/null 2>&1 &` logs its first ~5MB and then
nothing.

**Measured coverage** (2026-08-27, against a corpus pulled from JP's actual
Claude Code history — see PR body for full methodology): on a 200-command
random sample independently judged should/shouldn't-rewrite by a fresh
agent with no visibility into this implementation, the hook caught 79/81
(97.5%) of the commands that should have been rewritten, with 0 false
positives (100% precision) — the 2 misses are both discards sitting inside
a `$(...)` command substitution, excluded by design. Zero exceptions across
the full ~27k unique historical commands that mention a candidate redirect
token. (That sample judged the stderr policy; stdout/merged coverage was
added 2026-08-29 and validated by replaying old-vs-new over the full ~50k
unique historical commands: 0 lost rewrites, 0 exceptions, `bash -n` clean
on all 7,937 rewritten results, and every one of the 170 newly-rewritten
commands reviewed by hand.)

### Registering the hook (manual, per machine)

Add to the `PreToolUse` → `Bash` matcher list in `~/.claude/settings.json`,
after `block-gdoc-cat-devnull.py` (the deny hook should be listed first):

```json
{
  "type": "command",
  "command": "\"$HOME/.claude/hooks/stderr-to-logfile.py\"",
  "timeout": 10,
  "statusMessage": "Checking for a discarded stderr redirect"
}
```

`updatedInput` is returned bare, with no `permissionDecision` — this does
not bypass or auto-approve anything; the tool call still goes through the
normal permission flow with the rewritten command as its input.

## block-gdoc-cat-devnull.py

Denies a `gdoc cat` invocation whose output is sent to `/dev/null`, since
that silences gdoc's edit-conflict guard (see the script for the full
story). Statement-aware via `stderr-to-logfile.py`'s scanner: a command
merely *mentioning* the pattern (a heredoc body, a quoted string, a discard
in an unrelated statement) is allowed — the whole-text-grep `.sh` it
replaces denied all of those, including the PR-body edit that documented
this rule. A command the scanner can't parse falls back to the old grep, so
the deny never gets weaker than the original. Previously lived only as an
untracked file on this machine; moved here so a rebuild doesn't silently
lose it.
