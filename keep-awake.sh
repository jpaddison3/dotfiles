#!/usr/bin/env bash
#
# keep-awake.sh — Keep this Mac awake (even with the lid shut) while the
# battery is at/above a threshold; allow normal sleep below it. Runs
# indefinitely, flipping back and forth as the battery rises and falls
# (e.g. re-engages once you plug in and charge back above the threshold).
#
# Usage:
#   keep-awake [THRESHOLD]        # Ctrl-C to stop
#
#   THRESHOLD  Battery percent at/above which to stay awake. Default: 50.
#
# Temporarily allow sleep without stopping the daemon (no sudo needed):
#   keep-awakectl pause [DURATION]   # e.g. 45m, 2h; bare = until resume/reboot
#   keep-awakectl resume
#   keep-awakectl status
# These touch/remove /tmp/keep-awake.pause, which the loop below honors.
#
# How root works here:
#   - Blocking LID-CLOSED sleep needs root (`pmset disablesleep`); `caffeinate`
#     alone only blocks idle sleep. The script re-execs itself with sudo, so
#     you get ONE password prompt at launch and everything afterward runs in
#     that single root process — no later re-prompts.
#   - Don't add this script to a sudoers NOPASSWD rule: it's user-writable, so
#     that's passwordless root for arbitrary code. For an unattended launch,
#     run it as a root LaunchDaemon instead (runs as root, no password needed).
#   - On exit (Ctrl-C / kill) it always restores normal sleep.
#
# Caveat: while below the threshold the Mac is allowed to sleep, and a sleeping
# Mac can't poll — so it only notices the battery climbing back up once it
# wakes (you plug in, open the lid, etc.), at which point it re-engages.
#
set -euo pipefail

THRESHOLD="${1:-50}"
POLL_SECONDS=10
PAUSE_FILE="/tmp/keep-awake.pause"   # present + unexpired = temporarily allow sleep

# Re-exec as root so the single sudo prompt happens now, at launch.
if [[ "${EUID}" -ne 0 ]]; then
  echo "Re-running with sudo (needed to override lid-closed sleep)…"
  exec sudo "$0" "$@"
fi

battery_pct() {
  # e.g. " -InternalBattery-0 (id=...) 83%; discharging; ..."  ->  83
  # grep -m1 (not head) avoids a SIGPIPE that pipefail would treat as failure.
  pmset -g batt | grep -Eom1 '[0-9]+%' | tr -d '%' || true
}

set_sleep() {  # $1: 1 = disable sleep (stay awake), 0 = allow normal sleep
  pmset -a disablesleep "$1"
}

# A temporary pause is in effect if PAUSE_FILE exists and hasn't expired. Its
# contents are either "indefinite" or an epoch-seconds expiry. Managed by
# keep-awakectl (which just writes/removes the file — no sudo needed).
pause_active() {
  [[ -f "${PAUSE_FILE}" ]] || return 1
  local exp; exp="$(cat "${PAUSE_FILE}" 2>/dev/null || true)"
  [[ "${exp}" == "indefinite" ]] && return 0
  [[ "${exp}" =~ ^[0-9]+$ ]] || return 1     # malformed → not a valid pause
  (( "$(date +%s)" < exp ))
}

cleanup() {
  echo
  echo "Exiting — restoring normal sleep behavior…"
  pmset -a disablesleep 0 || true
  echo "Done — the Mac can sleep normally again."
}
trap cleanup EXIT INT TERM

# Read the OS's actual disablesleep value ("0"/"1"), so we can reconcile to it
# rather than trusting a cached memory of what we last set. This is what makes
# external flips — e.g. `keep-awakectl pause` setting the flag directly for
# instant effect — self-correct on the next pass instead of drifting.
current_disablesleep() { pmset -g | awk '/SleepDisabled/{print $2; exit}'; }

echo "Watching battery: stay awake (lid open or shut) while ≥ ${THRESHOLD}%, allow sleep below. Ctrl-C to stop."

last_logged=""   # log only when the decision changes, not every tick
while true; do
  # Decide the desired state: a temporary pause (see keep-awakectl) wins,
  # otherwise it's driven by the battery threshold.
  if pause_active; then
    desired=0; reason="paused: allowing sleep"
  else
    if [[ -f "${PAUSE_FILE}" ]]; then
      rm -f "${PAUSE_FILE}" 2>/dev/null || true   # expired/malformed — clear it
    fi
    pct="$(battery_pct)"
    if [[ -z "${pct}" ]]; then
      echo "$(date '+%-I:%M%p') — couldn't read battery; retrying."
      sleep "${POLL_SECONDS}"
      continue
    elif (( pct >= THRESHOLD )); then
      desired=1; reason="battery ${pct}% (≥ ${THRESHOLD}%): keeping awake"
    else
      desired=0; reason="battery ${pct}% (< ${THRESHOLD}%): allowing sleep"
    fi
  fi

  # Apply only when the OS isn't already there (this also repairs any external
  # change made behind our back, e.g. by keep-awakectl's instant pause).
  [[ "$(current_disablesleep)" == "${desired}" ]] || set_sleep "${desired}"

  if [[ "${reason}" != "${last_logged}" ]]; then
    echo "$(date '+%-I:%M%p') — ${reason}"
    last_logged="${reason}"
  fi

  sleep "${POLL_SECONDS}"
done
