#!/bin/bash
# PreToolUse (Bash) hook: deny any `gdoc cat` invocation whose output is sent
# to /dev/null. `gdoc cat` is gdoc's read-baseline step; its stderr carries the
# "doc edited by JP Addison (vN -> vM)" guard. Silencing it makes the next
# `gdoc write` clobber JP's edits (happened 2026-08-20). Read to a file and diff.
cmd="$(jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$cmd" ] && exit 0
if printf '%s' "$cmd" | grep -Eq 'gdoc[[:space:]]+cat' && printf '%s' "$cmd" | grep -q '/dev/null'; then
  reason='BLOCKED: `gdoc cat` with output sent to /dev/null. That silences gdoc'"'"'s "doc edited by JP" baseline guard, and the next `gdoc write` then clobbers JP'"'"'s edits (it happened 2026-08-20). Instead: `gdoc cat DOC > some-file.md` (keep stderr visible), diff against your last-written file, merge JP'"'"'s edits, then write.'
  jq -cn --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
fi
exit 0
