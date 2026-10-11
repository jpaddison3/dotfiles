#!/bin/bash
# Expire Codex sessions older than N days (default 120). Invoked nightly by the
# com.jpaddison.codex-expire-sessions launchd agent.
#
# Why this exists
#   Claude Code expires transcripts itself (cleanupPeriodDays: 120 in each
#   profile's settings.json). Codex has no retention setting and keeps every
#   rollout forever, so this mirrors the same window for ~/.codex.
#   120 days ≈ one quarter plus overlap, so the previous quarterly planning
#   cycle's sessions are still around at the next one.
#
# How
#   Threads whose last activity (threads.updated_at) is older than the cutoff
#   are expired oldest-first: the rollout file goes to the macOS Trash first
#   (recoverable), then `codex delete --force` removes the thread from Codex's
#   own index so the resume picker doesn't list dead sessions. If trashing
#   fails, the thread is skipped — `codex delete` would otherwise remove the
#   file permanently. Pinned threads are never expired.
#
#   `codex delete` goes through the running app-server daemon (~4s/call),
#   falling back to a standalone call (~12s) if the daemon is unavailable.
#
# Like pull-granola, this must be hard-linked into ~/.local/bin — see the
# App Management note in newcomputer.bash.
#
# Env knobs
#   CODEX_EXPIRE_DAYS=120   retention window in days
#   CODEX_EXPIRE_DRY_RUN=1  list what would be expired, change nothing

set -u

DAYS="${CODEX_EXPIRE_DAYS:-120}"
DRY_RUN="${CODEX_EXPIRE_DRY_RUN:-0}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
DB="$CODEX_HOME/state_5.sqlite"
CODEX="$HOME/.local/bin/codex"
TRASH=/opt/homebrew/bin/trash

LOG_DIR="$HOME/.local/share/codex-expire-sessions"
mkdir -p "$LOG_DIR"
if [ -z "${CODEX_EXPIRE_TTY:-}" ]; then exec >> "$LOG_DIR/codex-expire-sessions.log" 2>&1; fi

echo "--- $(date '+%Y-%m-%d %I:%M:%S %p %Z') codex-expire-sessions (days=$DAYS dry_run=$DRY_RUN) ---"

# The first sweep runs for hours; don't let the next night's tick overlap it.
LOCK="$LOG_DIR/lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another run holds $LOCK; exiting"
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT

if [ ! -f "$DB" ]; then
  echo "ERROR: $DB not found (Codex state schema changed?); nothing done"
  exit 1
fi

cutoff=$(( $(date +%s) - DAYS * 86400 ))
rows=$(/usr/bin/sqlite3 -readonly -separator $'\t' "$DB" \
  "SELECT id, rollout_path FROM threads WHERE updated_at < $cutoff AND is_pinned = 0 ORDER BY updated_at")
total=$(printf '%s' "$rows" | grep -c . || true)
echo "cutoff $(date -r "$cutoff" '+%Y-%m-%d'); $total thread(s) to expire"

expired=0; failed=0
while IFS=$'\t' read -r id path; do
  [ -n "$id" ] || continue
  if [ "$DRY_RUN" = 1 ]; then
    echo "would expire $id $path"
    continue
  fi
  if [ -e "$path" ] && ! "$TRASH" "$path"; then
    echo "SKIP $id: could not trash $path"
    failed=$((failed + 1)); continue
  fi
  if "$CODEX" delete --remote unix:// --force "$id" >/dev/null 2>&1 \
    || "$CODEX" delete --force "$id" >/dev/null 2>&1; then
    expired=$((expired + 1))
  else
    echo "FAIL $id: codex delete failed (rollout already trashed)"
    failed=$((failed + 1))
  fi
done <<< "$rows"

echo "done: expired=$expired failed=$failed"
