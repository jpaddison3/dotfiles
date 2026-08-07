#!/usr/bin/env bash
#
# keep-awake.sh — Keep this Mac awake (even with the lid shut) while the
# battery is at/above a threshold. Below it, allow normal sleep and force sleep
# after a long period without keyboard/trackpad input, even if another process
# (such as Claude Code) is inhibiting idle sleep. Runs indefinitely, flipping
# back and forth as the battery rises and falls.
#
# Overheat safety (on battery, lid shut, unattended): while it's keeping the Mac
# awake AND on battery AND the lid is closed AND there's been no recent input, it
# also watches thermal pressure; if the machine runs hot (Heavy or worse) for a
# couple of polls in a row, it drops the override and forces an immediate sleep
# to cool down. On AC, with the lid open, or while you're actively using it, it
# never force-sleeps — macOS's own throttling protects the hardware and it won't
# sleep the Mac out from under an active user (incl. a docked-but-unplugged
# machine used in clamshell with an external keyboard).
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
#   - Reading thermal pressure uses `powermetrics`, which also needs that root.
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
DIAGNOSTIC_INTERVAL_SECONDS=300  # periodic safety snapshot; avoids 10s log spam
PAUSE_FILE="/tmp/keep-awake.pause"   # present + unexpired = temporarily allow sleep

# Overheat safety knobs (see the loop below).
TRIGGER_LEVEL="Heavy"   # force sleep at this thermal pressure or worse:
                        #   Nominal < Moderate < Heavy < Trapping < Sleeping
THERMAL_DEBOUNCE=2      # consecutive elevated reads required before forcing sleep
COOLDOWN_SECONDS=300    # after a forced sleep, the overheat trigger can't fire
                        # again for this long (measured from wake) — anti-loop
                        # safety, so a still-warm Mac can't keep sleeping itself
                        # the moment you try to wake it
IDLE_SECONDS=60         # require no keyboard/trackpad input for this long before
                        # force-sleeping, so a docked-but-unplugged Mac used in
                        # clamshell isn't slept while you're typing on an external
                        # keyboard. A bagged Mac idles past this within a minute
                        # anyway, so it doesn't delay the real case.
LOW_BATTERY_IDLE_SECONDS=1800  # below the battery threshold, force sleep after
                               # 30 minutes without keyboard/trackpad input.
                               # This deliberately overrides app-level idle
                               # inhibitors, but leaves ample time for short
                               # unattended jobs and normal breaks.

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

timestamp() { date '+%Y-%m-%d %-I:%M:%S%p %Z'; }
log_message() { echo "$(timestamp) — $*"; }

set_sleep() {  # $1: 1 = disable sleep (stay awake), 0 = allow normal sleep
  pmset -a disablesleep "$1"
}

power_source() {  # "battery", "ac", or "unknown"
  local status
  status="$(pmset -g batt 2>/dev/null || true)"
  if [[ "${status}" == *"Battery Power"* ]]; then
    echo "battery"
  elif [[ "${status}" == *"AC Power"* ]]; then
    echo "ac"
  else
    echo "unknown"
  fi
}

lid_state() {  # "closed", "open", or "unknown"
  local state
  state="$(ioreg -r -k AppleClamshellState 2>/dev/null \
    | awk '/"AppleClamshellState" = Yes/{found="closed"} /"AppleClamshellState" = No/{found="open"} END{print found}' \
    || true)"
  echo "${state:-unknown}"
}

# Seconds since the last keyboard/trackpad input (HIDIdleTime is nanoseconds);
# empty if unreadable → callers default it to 0 ("active"), so a bad read never
# forces sleep. `|| true`: ioreg's output is large and awk's `exit` SIGPIPEs it,
# which under pipefail would otherwise surface as a non-zero pipeline.
idle_seconds() {
  ioreg -c IOHIDSystem 2>/dev/null \
    | awk '/HIDIdleTime/{printf "%d", $NF/1000000000; exit}' || true
}

# Current thermal pressure level, e.g. "Nominal"/"Heavy"; empty if unreadable.
# There's no reliable raw-temperature path on Apple Silicon (the `smc`
# powermetrics sampler is Intel-only), so we key off the OS's own thermal
# *pressure* level instead.
thermal_level() {
  # `|| true`: awk's early `exit` can SIGPIPE powermetrics, and powermetrics
  # itself can transiently fail; under `set -o pipefail` that non-zero pipeline
  # status would otherwise kill the whole script at the `level="$(thermal_level)"`
  # assignment below. Same guard as battery_pct.
  powermetrics -n 1 -i 200 --samplers thermal 2>/dev/null \
    | awk -F': ' '/Current pressure level/{print $2; exit}' || true
}

# Order the pressure levels for comparison; unknown/empty → 0, so an unreadable
# sample can never trigger a force-sleep.
thermal_rank() {
  case "$1" in
    Nominal)  echo 0 ;;
    Moderate) echo 1 ;;
    Heavy)    echo 2 ;;
    Trapping) echo 3 ;;
    Sleeping) echo 4 ;;
    *)        echo 0 ;;
  esac
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
  log_message "Exiting — restoring normal sleep behavior…"
  pmset -a disablesleep 0 || true
  log_message "Done — the Mac can sleep normally again."
}
trap cleanup EXIT INT TERM

# Read the OS's actual disablesleep value ("0"/"1"), so we can reconcile to it
# rather than trusting a cached memory of what we last set. This is what makes
# external flips — e.g. `keep-awakectl pause` setting the flag directly for
# instant effect — self-correct on the next pass instead of drifting.
current_disablesleep() { pmset -g | awk '/SleepDisabled/{print $2; exit}'; }

force_sleep_and_start_cooldown() {
  set_sleep 0                # must drop the override first, or sleepnow is ignored
  pmset sleepnow || true

  # Wait for the real suspend+wake before starting the cooldown, so opening the
  # lid cannot immediately trigger another forced sleep before the first input.
  # A genuine suspend shows up as the wall clock jumping beyond the time spent
  # in this loop. Bail out after ~30s if another assertion blocks the sleep.
  local sleep_start ticked
  sleep_start="$(date +%s)"; ticked=0
  while (( ticked < 30 )); do
    sleep 2; ticked=$(( ticked + 2 ))
    # ≥8s of wall clock beyond what we actually slept ⇒ we were suspended.
    if (( "$(date +%s)" - sleep_start - ticked >= 8 )); then break; fi
  done
  cooldown_until=$(( "$(date +%s)" + COOLDOWN_SECONDS ))
  last_logged=""
}

echo "Watching battery: stay awake (lid open or shut) while ≥ ${THRESHOLD}%, allow sleep below. Ctrl-C to stop."

last_logged=""   # log only when the decision changes, not every tick
last_diagnostic_at=0                           # periodic full safety snapshot
hot_count=0                                    # consecutive hot reads (overheat safety)
cooldown_until=0                               # epoch until the trigger can fire again
trigger_rank="$(thermal_rank "${TRIGGER_LEVEL}")"
while true; do
  now="$(date +%s)"
  pct="$(battery_pct)"
  source="$(power_source)"
  lid="$(lid_state)"
  idle="$(idle_seconds)"

  if [[ -z "${pct}" ]]; then
    log_message "couldn't read battery; retrying"
    sleep "${POLL_SECONDS}"
    continue
  fi

  # Decide the desired state: a temporary pause (see keep-awakectl) wins,
  # otherwise it's driven by the battery threshold.
  below_threshold=0
  if pause_active; then
    desired=0; reason="paused: allowing sleep"
  else
    if [[ -f "${PAUSE_FILE}" ]]; then
      rm -f "${PAUSE_FILE}" 2>/dev/null || true   # expired/malformed — clear it
    fi
    if (( pct >= THRESHOLD )); then
      desired=1; reason="battery ${pct}% (≥ ${THRESHOLD}%): keeping awake"
    else
      desired=0; below_threshold=1
      reason="battery ${pct}% (< ${THRESHOLD}%): allowing sleep"
    fi
  fi

  # Once the battery is below the threshold, don't let an app-level idle
  # inhibitor keep an unattended Mac running indefinitely. HIDIdleTime measures
  # actual keyboard/trackpad inactivity, independent of caffeinate assertions.
  # This applies with the lid either open or closed: an open Mac forgotten
  # overnight should not drain merely because an agent is still marked busy.
  if (( below_threshold == 1 )) && [[ "${source}" == "battery" ]] \
    && [[ "${idle}" =~ ^[0-9]+$ ]] \
    && (( idle >= LOW_BATTERY_IDLE_SECONDS )) \
    && (( now >= cooldown_until )); then
    log_message "battery ${pct}%, no user input for 30m: forcing sleep"
    force_sleep_and_start_cooldown
    continue
  fi

  # Overheat safety: only while we're keeping the Mac awake (desired=1), on
  # battery, with the lid shut, AND unattended (no recent input) — that's the
  # case worth interrupting for (lid shut in a bag, no power, no airflow). Lid
  # open, or any recent keypress, means someone may be using it — including a
  # docked-but-unplugged machine in clamshell — so we never sleep it out from
  # under them. If it's running hot, stop feeding the fire — drop the override
  # and force sleep. The debounce keeps a momentary spike from slamming it shut;
  # the cooldown caps this to once per COOLDOWN_SECONDS so a still-warm Mac can't
  # keep sleeping itself the moment you wake it.
  level="not-sampled"
  thermal_check="skipped"
  if (( desired != 1 )); then
    thermal_check="skipped:not-keeping-awake"
  elif [[ "${source}" != "battery" ]]; then
    thermal_check="skipped:power-${source}"
  elif [[ "${lid}" != "closed" ]]; then
    thermal_check="skipped:lid-${lid}"
  elif [[ ! "${idle}" =~ ^[0-9]+$ ]]; then
    thermal_check="skipped:idle-unknown"
  elif (( idle < IDLE_SECONDS )); then
    thermal_check="skipped:recent-input"
  elif (( now < cooldown_until )); then
    thermal_check="skipped:cooldown"
  else
    thermal_check="sampled"
    level="$(thermal_level)"
    [[ -n "${level}" ]] || level="unreadable"
    if (( "$(thermal_rank "${level:-}")" >= trigger_rank )); then
      hot_count=$(( hot_count + 1 ))
    else
      hot_count=0
    fi
    if (( hot_count >= THERMAL_DEBOUNCE )); then
      log_message "thermal ${level} (x${hot_count}): forcing sleep to cool down"
      hot_count=0
      force_sleep_and_start_cooldown
      continue
    fi
  fi
  if [[ "${thermal_check}" != "sampled" ]]; then
    hot_count=0
  fi

  # Apply only when the OS isn't already there (this also repairs any external
  # change made behind our back, e.g. by keep-awakectl's instant pause).
  [[ "$(current_disablesleep)" == "${desired}" ]] || set_sleep "${desired}"

  state_changed=0
  if [[ "${reason}" != "${last_logged}" ]]; then
    log_message "${reason}"
    last_logged="${reason}"
    state_changed=1
  fi

  if (( state_changed == 1 || now - last_diagnostic_at >= DIAGNOSTIC_INTERVAL_SECONDS )); then
    idle_display="${idle:-unknown}"
    log_message "diagnostics: battery=${pct}%; power=${source}; lid=${lid}; idle=${idle_display}s; thermal=${level}; thermal_check=${thermal_check}; hot_count=${hot_count}/${THERMAL_DEBOUNCE}; desired_disablesleep=${desired}; actual_disablesleep=$(current_disablesleep)"
    last_diagnostic_at="${now}"
  fi

  sleep "${POLL_SECONDS}"
done
