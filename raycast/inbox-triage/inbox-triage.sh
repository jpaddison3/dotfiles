#!/usr/bin/env bash
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Inbox Triage
# @raycast.mode compact
# @raycast.packageName Inbox Triage
# @raycast.icon 📥
# @raycast.description Launch inbox triage using the local-time mode
# @raycast.needsConfirmation false

set -euo pipefail

if [[ -z "${HOME:-}" ]]; then
  echo "error: HOME is not set; cannot find inbox-triage-launch" >&2
  exit 1
fi

backend="$HOME/.local/bin/inbox-triage-launch"
if [[ ! -x "$backend" ]]; then
  echo "error: inbox-triage-launch is missing or not executable at $backend; install the backend first with make install-inbox-triage" >&2
  exit 1
fi

exec "$backend" --mode auto
