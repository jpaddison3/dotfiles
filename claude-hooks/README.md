# claude-hooks — Claude Code PreToolUse hooks

Tracked source for hooks registered in `~/.claude/settings.json`, which is
itself untracked (personal, machine-local) and so isn't managed by this repo.
`newcomputer.bash` symlinks everything here into `~/.claude/hooks/`; the
settings.json registration is a manual, one-time edit per machine (see below).

## stderr-to-logfile.py + logfile-sink.sh

Every AI-run Bash command that discards its stderr (`2>/dev/null`,
`&>/dev/null`, `>/dev/null 2>&1`, ...) gets that redirect transparently
rewritten to a process substitution that pipes into `logfile-sink.sh`
instead, which prefixes each line with a timestamp and the full original
command and appends it to `~/.logs/YYYY-MM-DD.log`. The AI's command is
never shown the rewrite and doesn't need to cooperate; stdout and exit
status are untouched. Grep `~/.logs/` (`loggrep <term>`) when hunting a
failure whose stderr would otherwise be gone.

`stderr-to-logfile.py` is conservative by construction: it only rewrites
when it can find an unambiguous, unquoted, top-level redirect matching one
of the three forms above, in a statement that touches fd 2 exactly once,
outside heredoc bodies, quoted strings, and `$(...)`/`(...)` subshells, and
that isn't a `command -v`/`which`/`hash`/`type` probe. Anything it isn't
sure about is left alone — a missed rewrite is cheap, a mangled command
isn't. See `tests/test_stderr_to_logfile.py` for the case-by-case
behavior.

**Measured coverage** (2026-08-27, against a corpus pulled from JP's actual
Claude Code history — see PR body for full methodology): on a 200-command
random sample independently judged should/shouldn't-rewrite by a fresh
agent with no visibility into this implementation, the hook caught 79/81
(97.5%) of the commands that should have been rewritten, with 0 false
positives (100% precision) — the 2 misses are both discards sitting inside
a `$(...)` command substitution, excluded by design. Zero exceptions across
the full ~27k unique historical commands that mention a candidate redirect
token.

### Registering the hook (manual, per machine)

Add to the `PreToolUse` → `Bash` matcher list in `~/.claude/settings.json`,
alongside `block-gdoc-cat-devnull.sh`:

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

## block-gdoc-cat-devnull.sh

Denies any `gdoc cat` invocation whose output is sent to `/dev/null`,
since that silences gdoc's edit-conflict guard (see the script for the
full story). Previously lived only as an untracked file on this machine;
moved here so a rebuild doesn't silently lose it.
