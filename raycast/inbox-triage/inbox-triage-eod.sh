#!/usr/bin/env bash
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Inbox Triage — EOD
# @raycast.mode compact
# @raycast.packageName Inbox Triage
# @raycast.icon 📥
# @raycast.description Launch the end-of-day inbox triage
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

set +e
backend_output="$("$backend" --mode eod)"
backend_status=$?
set -e

if summary="$(
  printf '%s' "$backend_output" | TMPDIR="${TMPDIR:-/tmp}" python3 -c '
import json
import sys

raw = sys.stdin.read()
try:
    payload, _ = json.JSONDecoder().raw_decode(raw.lstrip())
except (json.JSONDecodeError, TypeError):
    sys.stdout.write(raw)
    raise SystemExit(0)

if not isinstance(payload, dict):
    sys.stdout.write(raw)
    raise SystemExit(0)

def one_line(value):
    return str(value).replace("\\n", " ")

action = payload.get("action")
if action == "launched":
    mode = one_line(payload.get("mode", "unknown"))
    pane = payload.get("terminal_handle")
    if pane:
        print(f"launched: mode={mode} pane={one_line(pane)}")
    elif payload.get("run_id"):
        run_id = one_line(payload["run_id"])
        print(f"launched: mode={mode} run={run_id}")
    else:
        sys.stdout.write(raw)
elif action == "already-preparing":
    since = payload.get("opened_at") or payload.get("updated_at")
    if since:
        print(f"already-preparing: since={one_line(since)}")
    else:
        sys.stdout.write(raw)
elif action == "reopened" and not payload.get("opened", False):
    error = one_line(payload.get("open_error", "unknown error"))
    print(f"reopen failed: {error}")
else:
    sys.stdout.write(raw)
'
)"; then
  printf '%s\n' "$summary"
else
  printf '%s\n' "$backend_output"
fi

exit "$backend_status"
