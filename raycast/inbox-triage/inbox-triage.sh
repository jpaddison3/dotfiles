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

set +e
# A sentinel keeps command substitution from stripping backend newlines.
backend_output="$(
  "$backend" --mode auto
  status=$?
  printf '.'
  exit "$status"
)"
backend_status=$?
set -e
backend_output="${backend_output%.}"

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
    return " ".join(str(value).splitlines())

action = payload.get("action")
if action == "launched":
    label = "launched" if sys.argv[1] == "0" else "launch failed"
    mode = one_line(payload.get("mode", "unknown"))
    pane = payload.get("terminal_handle")
    if pane:
        print(f"{label}: mode={mode} pane={one_line(pane)}")
    elif payload.get("run_id"):
        run_id = one_line(payload["run_id"])
        print(f"{label}: mode={mode} run={run_id}")
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
' "$backend_status" && printf '.'
)"; then
  printf '%s' "${summary%.}"
else
  printf '%s' "$backend_output"
fi

exit "$backend_status"
