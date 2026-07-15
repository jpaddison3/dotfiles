#!/usr/bin/env bash
# clip-to-asana.sh — create an Asana task in My Tasks from the clipboard.
#
# Replaces the old Zapier webhook flow (clipboard -> hooks.zapier.com -> task).
# Now it talks to Asana directly via `dharma`, so no webhook/secret is involved.
#
# Mapping: the first line of the clipboard becomes the task name; any remaining
# lines become the task notes. The task is assigned to you, so it lands in
# My Tasks ("Recently assigned").
#
# Auth + workspace come from dharma's stored login (`dharma auth login`);
# nothing sensitive lives in this file. Safe for a public repo.
#
# Bind this script to a BetterTouchTool hotkey via "Execute Shell Script":
#   /Users/jpaddison/Documents/dotfiles/clip-to-asana.sh

set -euo pipefail

# BTT runs with a minimal PATH, so resolve dharma explicitly.
DHARMA="${DHARMA:-$HOME/.go/bin/dharma}"
[ -x "$DHARMA" ] || DHARMA="$(command -v dharma || true)"

notify() { osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1 || true; }

if [ -z "${DHARMA:-}" ] || [ ! -x "$DHARMA" ]; then
  notify "Clip → Asana ✗" "dharma binary not found"
  echo "dharma not found (set \$DHARMA or install to ~/.go/bin)" >&2
  exit 1
fi

clip="$(pbpaste)"

# Bail if the clipboard is empty or whitespace-only.
if [ -z "$(printf '%s' "$clip" | tr -d '[:space:]')" ]; then
  notify "Clip → Asana" "Clipboard empty — nothing created"
  exit 0
fi

name="$(printf '%s\n' "$clip" | sed -n '1p')"
notes="$(printf '%s\n' "$clip" | sed '1d')"

args=(task create --name "$name" --assignee me)
[ -n "$notes" ] && args+=(--notes "$notes")

if out="$("$DHARMA" "${args[@]}" 2>&1)"; then
  notify "Clip → Asana ✓" "$name"
else
  notify "Clip → Asana ✗" "${out:0:120}"
  echo "$out" >&2
  exit 1
fi
