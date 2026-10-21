#!/bin/bash
# Delete agent scratch files after 30 days of inactivity. Invoked daily by the
# com.jpaddison.agent-tmp-cleanup launchd agent.
#
# Files must be old by both access and modification time. This handles systems
# where reads update atime and systems where they do not; mtime is the fallback.
# Empty directories are pruned separately, one level per run at most.
#
# Env knobs
#   AGENT_TMP_DAYS=30       inactivity window in days
#   AGENT_TMP_DRY_RUN=1     report the count without deleting
#   AGENT_TMP_TTY=1         write to the terminal instead of the log

set -u

DAYS="${AGENT_TMP_DAYS:-30}"
DRY_RUN="${AGENT_TMP_DRY_RUN:-0}"
ROOT="$HOME/.cache/agent-tmp"
LOG_DIR="$HOME/.local/share/agent-tmp-cleanup"
mkdir -p "$LOG_DIR"
if [ -z "${AGENT_TMP_TTY:-}" ]; then
  exec >> "$LOG_DIR/agent-tmp-cleanup.log" 2>&1
fi

echo "--- $(date '+%Y-%m-%d %I:%M:%S %p %Z') agent-tmp-cleanup (days=$DAYS dry_run=$DRY_RUN) ---"

if [ ! -d "$ROOT" ]; then
  echo "scratch directory $ROOT not found; nothing to clean"
  exit 0
fi

if [ "$DRY_RUN" = 1 ]; then
  count=$(find "$ROOT" -xdev -mindepth 1 ! -type d -atime "+$DAYS" -mtime "+$DAYS" -print | wc -l | tr -d ' ')
  echo "would delete $count file(s)"
else
  count=$(find "$ROOT" -xdev -mindepth 1 ! -type d -atime "+$DAYS" -mtime "+$DAYS" -print -delete | wc -l | tr -d ' ')
  echo "deleted $count file(s)"
  find "$ROOT" -xdev -mindepth 1 -type d -empty -mtime +1 -delete
fi

du -sh "$ROOT"
