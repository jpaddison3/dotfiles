import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASH = Path("/bin/bash")
CLOCK0 = 1791448000
COOLDOWN = 300

STUBS = {
    "pmset": """#!/bin/sh
d="$STUB_DIR"
case "$1 $2" in
  "-g systemstate")
    if [ -f "$d/fail_wake" ]; then echo 'Current System Capabilities are: CPU Graphics'; exit 1; fi
    if [ -f "$d/wake_delay" ]; then
      echo $(( $(cat "$d/clock") + $(cat "$d/wake_delay") )) > "$d/clock"
      : > "$d/wake_delay.done"
    fi
    if [ -f "$d/wake_sequence" ]; then
      head -n 1 "$d/wake_sequence"
      tail -n +2 "$d/wake_sequence" > "$d/wake.tmp" && mv "$d/wake.tmp" "$d/wake_sequence"
    elif [ -f "$d/wake" ]; then cat "$d/wake"; else echo 'Current System Capabilities are: CPU Graphics'; fi
    ;;
  "-g batt")
    status="$(cat "$d/battery_status")"
    [ ! -f "$d/battery_status_sequence" ] || status="$(head -n 1 "$d/battery_status_sequence")"
    battery="$(cat "$d/battery")"
    [ ! -f "$d/battery_sequence" ] || battery="$(head -n 1 "$d/battery_sequence")"
    power="$(cat "$d/power")"
    [ ! -f "$d/power_sequence" ] || power="$(head -n 1 "$d/power_sequence")"
    printf "Now drawing from '%s'\\n" "$power"
    printf ' -InternalBattery-0 (id=1)\\t%s%%; %s; 5:00 remaining present: true\\n' "$battery" "$status"
    ;;
  "-g ")
    printf ' SleepDisabled\\t\\t%s\\n' "$(cat "$d/state")"
    ;;
  "-a disablesleep")
    if [ -f "$d/fail_setting" ] && [ "$3" = "1" ]; then exit 1; fi
    echo "$3" > "$d/state"
    echo "disablesleep $3 @$(cat "$d/clock")" >> "$d/pmset.log"
    ;;
  "sleepnow ")
    echo "sleepnow @$(cat "$d/clock")" >> "$d/pmset.log"
    echo $(( $(cat "$d/clock") + 600 )) > "$d/clock"
    ;;
esac
""",
    "ioreg": """#!/bin/sh
d="$STUB_DIR"
if [ "$1" = "-r" ]; then
  echo "    \\"AppleClamshellState\\" = $(cat "$d/lid")"
else
  echo "    \\"HIDIdleTime\\" = $(( $(cat "$d/idle") * 1000000000 ))"
fi
""",
    "powermetrics": """#!/bin/sh
d="$STUB_DIR"
level="$(head -n 1 "$d/thermal")"
if [ "$(wc -l < "$d/thermal")" -gt 1 ]; then
  tail -n +2 "$d/thermal" > "$d/thermal.tmp" && mv "$d/thermal.tmp" "$d/thermal"
fi
echo "Current pressure level: $level"
""",
    "date": """#!/bin/sh
if [ "$*" = "+%s" ]; then
  cat "$STUB_DIR/clock"
elif [ "$1" = "-r" ]; then
  exec /bin/date "$@"
else
  exec /bin/date -r "$(cat "$STUB_DIR/clock")" "$@"
fi
""",
    "sleep": """#!/bin/sh
d="$STUB_DIR"
n=$(( $(cat "$d/sleep_count") + 1 ))
echo "$n" > "$d/sleep_count"
echo $(( $(cat "$d/clock") + $1 )) > "$d/clock"
if [ -f "$d/clock_jump_after" ]; then
  read after secs < "$d/clock_jump_after"
  if [ "$n" -eq "$after" ]; then
    echo $(( $(cat "$d/clock") + secs )) > "$d/clock"
  fi
fi
if [ -f "$d/battery_sequence" ]; then
  tail -n +2 "$d/battery_sequence" > "$d/battery_sequence.tmp" && mv "$d/battery_sequence.tmp" "$d/battery_sequence"
fi
if [ -f "$d/battery_status_sequence" ]; then
  tail -n +2 "$d/battery_status_sequence" > "$d/battery_status_sequence.tmp" && mv "$d/battery_status_sequence.tmp" "$d/battery_status_sequence"
fi
if [ -f "$d/power_sequence" ]; then
  tail -n +2 "$d/power_sequence" > "$d/power_sequence.tmp" && mv "$d/power_sequence.tmp" "$d/power_sequence"
fi
if [ -f "$d/external_override_after_sleep" ]; then
  echo 1 > "$d/state"
  : > "$d/battery"
fi
[ "$n" -lt "$(cat "$d/max_sleeps")" ] || exit 99
""",
}


@unittest.skipUnless(BASH.exists(), "needs /bin/bash (3.2) to match the launchd daemon")
class KeepAwakeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="keep awake ")
        self.dir = Path(self.temp_dir.name)
        self.cooldown_file = self.dir / "cooldown"
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        for name, body in STUBS.items():
            stub = bin_dir / name
            stub.write_text(body)
            stub.chmod(0o755)
        self.write("clock", CLOCK0)
        self.write("sleep_count", 0)
        self.write("max_sleeps", 40)
        self.write("state", 0)
        self.write("battery", 80)
        self.write("battery_status", "charging")
        self.write("power", "AC Power")
        self.write("lid", "No")
        self.write("idle", 0)
        self.write("thermal", "Nominal")
        self.write("wake", "Current System Capabilities are: CPU Graphics")
        (self.dir / "pmset.log").write_text("")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, name, value):
        (self.dir / name).write_text(f"{value}\n")

    def set_thermal(self, *levels):
        self.write("thermal", "\n".join(levels))

    def set_battery_status(self, status):
        self.write("battery_status", status)

    def set_battery_status_sequence(self, *statuses):
        self.write("battery_status_sequence", "\n".join(statuses))

    def run_daemon(self):
        env = {
            "PATH": f"{self.dir / 'bin'}:/usr/bin:/bin",
            "KEEP_AWAKE_NO_SUDO": "1",
            "KEEP_AWAKE_PAUSE_FILE": str(self.dir / "pause"),
            "KEEP_AWAKE_COOLDOWN_FILE": str(self.cooldown_file),
            "STUB_DIR": str(self.dir),
        }
        result = subprocess.run(
            [str(BASH), str(ROOT / "keep-awake.sh"), "50"],
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        # The stub sleep exits 99 once max_sleeps is hit; that's how runs end.
        self.assertEqual(result.returncode, 99, output)
        self.assertNotIn("syntax error", output)
        self.assertNotIn("command not found", output)
        self.assertIn("Done — the Mac can sleep normally again.", output)
        self.assertEqual(self.pmset_events()[-1][0], "disablesleep 0", "exit must restore sleep")
        return output

    def pmset_events(self):
        events = []
        for line in (self.dir / "pmset.log").read_text().splitlines():
            action, clock = line.rsplit(" @", 1)
            events.append((action, int(clock)))
        return events

    def enables(self):
        return [clock for action, clock in self.pmset_events() if action == "disablesleep 1"]

    def test_overheat_forced_sleep_completes(self):
        self.write("power", "Battery Power")
        self.write("lid", "Yes")
        self.write("idle", 120)
        self.set_thermal("Nominal", "Heavy")  # engage first, then run hot
        output = self.run_daemon()

        events = self.pmset_events()
        actions = [action for action, _ in events]
        self.assertIn("thermal Heavy (x2): forcing sleep to cool down", output)
        sleepnow = actions.index("sleepnow")
        self.assertEqual(actions[sleepnow - 1], "disablesleep 0")
        woke = events[sleepnow][1] + 600
        cooldown = int((self.cooldown_file).read_text())
        self.assertTrue(woke + COOLDOWN <= cooldown <= woke + COOLDOWN + 40, cooldown)
        self.assertNotIn("disablesleep 1", actions[sleepnow:])

    def test_low_battery_idle_forced_sleep_completes(self):
        self.write("power", "Battery Power")
        self.write("battery", 30)
        self.write("idle", 1900)
        output = self.run_daemon()

        self.assertIn("no user input for 30m: forcing sleep", output)
        self.assertIn("sleepnow", [action for action, _ in self.pmset_events()])
        self.assertTrue(self.cooldown_file.read_text().strip().isdigit())

    def test_restart_during_cooldown_holds_sleep_allowed(self):
        cooldown_until = CLOCK0 + 200
        self.cooldown_file.write_text(f"{cooldown_until}\n")
        self.write("max_sleeps", 60)
        self.write("clock_jump_after", "5 300")
        output = self.run_daemon()

        self.assertIn("resuming cooldown", output)
        self.assertIn("cooldown after forced sleep: allowing sleep until", output)
        enables = self.enables()
        self.assertTrue(enables, "keep-awake should engage once the cooldown ends")
        self.assertGreaterEqual(min(enables), cooldown_until)

    def test_hot_at_startup_does_not_enable_until_cool(self):
        for level in ("Heavy", "Trapping", "Sleeping"):
            with self.subTest(level=level):
                (self.dir / "pmset.log").write_text("")
                self.write("state", 0)
                self.write("clock", CLOCK0)
                self.write("sleep_count", 0)
                self.set_thermal(level, level, level, "Nominal")
                self.write("max_sleeps", 6)
                output = self.run_daemon()

                self.assertIn(f"thermal {level} (≥ Heavy): not enabling keep-awake", output)
                self.assertEqual(len(self.enables()), 1)
                self.assertEqual(
                    self.enables()[0], CLOCK0 + 3 * 10, "should enable on the first cool read"
                )

    def test_inherited_disablesleep_is_reset_when_hot(self):
        self.write("state", 1)
        self.set_thermal("Heavy")
        self.run_daemon()

        # Reset at startup (clock not yet advanced), not just by the exit cleanup.
        self.assertEqual(self.pmset_events()[0], ("disablesleep 0", CLOCK0))
        self.assertEqual(self.enables(), [])

    def test_partial_wake_leaves_inherited_override_cleared(self):
        self.write("state", 1)
        self.write("wake", "Current System Capabilities are: CPU Network")
        self.write("max_sleeps", 5)
        output = self.run_daemon()
        self.assertIn("wake partial: allowing sleep", output)
        self.assertEqual(self.enables(), [])

    def test_unknown_wake_never_enables_even_if_battery_unreadable(self):
        self.write("wake", "Current Power State: 1")
        self.write("battery", "")
        self.write("max_sleeps", 4)
        output = self.run_daemon()
        self.assertIn("wake unknown: allowing sleep", output)
        self.assertEqual(self.enables(), [])

    def test_failed_wake_command_is_unknown_even_with_output(self):
        self.write("fail_wake", 1)
        self.write("max_sleeps", 3)
        output = self.run_daemon()
        self.assertIn("wake unknown: allowing sleep", output)
        self.assertEqual(self.enables(), [])

    def test_malformed_capabilities_are_unknown(self):
        for malformed in (
            "CPU Graphics",
            "Current System Capabilities are: Graphics",
            "Current System Capabilities are: CPU Graphics\nCurrent System Capabilities are: CPU",
            "Current System Capabilities are: CPU Graphics\nDesired State: 2\nSystem State is changing to Sleep",
            "Current System Capabilities are: CPU Graphics\nSystem is waking from sleep",
            "Current System Capabilities are: CPU No Graphics",
            "Current System Capabilities are: NotCPU Graphics",
        ):
            with self.subTest(malformed=malformed):
                self.write("wake", malformed)
                self.write("max_sleeps", 2)
                output = self.run_daemon()
                self.assertIn("wake unknown: allowing sleep", output)
                self.assertEqual(self.enables(), [])
                self.write("clock", CLOCK0)
                self.write("sleep_count", 0)
                self.write("state", 0)
                self.write("max_sleeps", 40)
                (self.dir / "pmset.log").write_text("")

    def test_fullwake_with_display_off_remains_capable(self):
        self.write("wake", "Current System Capabilities are: CPU Graphics Audio Network\nDisplay: off")
        self.write("max_sleeps", 2)
        self.run_daemon()
        self.assertTrue(self.enables())

    def test_fresh_wake_gate_and_later_fullwake_resume_policy(self):
        self.write("wake_sequence", "\n".join([
            "Current System Capabilities are: CPU Graphics",       # loop observation
            "Current System Capabilities are: CPU Network",    # gate observes transition
            "Current System Capabilities are: CPU Graphics",       # next loop recovers
            "Current System Capabilities are: CPU Graphics",       # fresh enable gate
        ]))
        self.write("max_sleeps", 3)
        output = self.run_daemon()
        self.assertIn("wake partial: allowing sleep", output)
        self.assertTrue(self.enables(), "policy should resume on later FullWake")
        self.assertGreaterEqual(min(self.enables()), CLOCK0 + 10)

    def test_delayed_sensor_and_loop_gap_are_reported_as_wall_clock_observations(self):
        self.write("wake_delay", 12)
        self.write("max_sleeps", 2)
        output = self.run_daemon()
        self.assertIn("late progress: phase=wake; duration=12s; wall-clock observation", output)
        self.assertIn("acquisition_durations=", output)
        self.assertIn("consecutive loop starts 34s apart", output)
        self.assertEqual(self.enables(), [CLOCK0 + 24])

    def test_failed_sleep_setting_is_not_reported_as_reconciled(self):
        self.write("fail_setting", 1)
        self.write("max_sleeps", 2)
        output = self.run_daemon()
        self.assertIn("sleep setting failed: requested_disablesleep=1; observed_actual_disablesleep=0", output)

    def test_low_battery_idle_still_forces_sleep_during_partial_wake(self):
        self.write("power", "Battery Power")
        self.write("battery", 30)
        self.write("idle", 1900)
        self.write("wake", "Current System Capabilities are: CPU Network")
        self.run_daemon()
        self.assertIn("sleepnow", [action for action, _ in self.pmset_events()])
        self.assertEqual(self.enables(), [])

    def test_fullwake_darkwake_fullwake_reconciles_held_override(self):
        self.write("wake_sequence", "\n".join([
            "Current System Capabilities are: CPU Graphics",
            "Current System Capabilities are: CPU Graphics",
            "Current System Capabilities are: CPU Network",
            "Current System Capabilities are: CPU Graphics",
            "Current System Capabilities are: CPU Graphics",
        ]))
        self.write("max_sleeps", 3)
        self.run_daemon()
        self.assertEqual(self.pmset_events(), [
            ("disablesleep 0", CLOCK0), ("disablesleep 1", CLOCK0),
            ("disablesleep 0", CLOCK0 + 10), ("disablesleep 1", CLOCK0 + 20),
            ("disablesleep 0", CLOCK0 + 30),
        ])

    def test_partial_wake_clears_external_override_before_failed_battery_skip(self):
        self.write("wake", "Current System Capabilities are: CPU Network")
        self.write("external_override_after_sleep", 1)
        self.write("max_sleeps", 2)
        self.run_daemon()
        self.assertEqual(self.enables(), [])
        self.assertIn(("disablesleep 0", CLOCK0 + 10), self.pmset_events())

    def test_recovery_preserves_existing_policy_gates(self):
        for name, settings, allowed in (
            ("paused", {"pause": "indefinite"}, False),
            ("expired-pause", {"pause": CLOCK0 - 1}, True),
            ("low-battery", {"power": "Battery Power", "battery": 49}, False),
            ("threshold-equality", {"power": "Battery Power", "battery": 50}, True),
            ("cooldown", {"cooldown": CLOCK0 + 200}, False),
            ("hot", {"thermal": "Heavy"}, False),
        ):
            with self.subTest(gate=name):
                for filename in ("pause", "cooldown"):
                    (self.dir / filename).unlink(missing_ok=True)
                self.write("battery", 80)
                self.write("thermal", "Nominal")
                self.write("state", 1)
                self.write("clock", CLOCK0)
                self.write("sleep_count", 0)
                self.write("max_sleeps", 2)
                (self.dir / "pmset.log").write_text("")
                for filename, value in settings.items():
                    self.write(filename, value)
                self.write("wake_sequence", "\n".join([
                    "Current System Capabilities are: CPU Network",
                    "Current System Capabilities are: CPU Graphics",
                    "Current System Capabilities are: CPU Graphics",
                ]))
                self.run_daemon()
                self.assertEqual(self.enables(), [CLOCK0 + 10] if allowed else [])
                self.assertNotIn("sleepnow", [action for action, _ in self.pmset_events()])

    def test_backward_sensor_clock_reports_unknown_duration(self):
        self.write("wake_delay", -12)
        self.write("max_sleeps", 1)
        output = self.run_daemon()
        self.assertIn("wake:unknowns", output)
        self.assertIn("policy:unknown", output)
        self.assertNotIn("late progress:", output)

    def test_between_loop_delay_is_separate_from_sensor_duration(self):
        self.write("clock_jump_after", "1 100")
        self.write("max_sleeps", 2)
        output = self.run_daemon()
        self.assertIn("consecutive loop starts 110s apart", output)
        self.assertNotIn("late progress: phase=", output)
        self.assertEqual(self.enables(), [CLOCK0])

    def test_garbage_cooldown_file(self):
        with self.subTest(case="not a number"):
            self.cooldown_file.write_text("abc\n")
            output = self.run_daemon()
            self.assertNotIn("resuming cooldown", output)
            self.assertEqual(self.enables()[0], CLOCK0)

        with self.subTest(case="far future is clamped"):
            self.write("clock", CLOCK0)
            self.write("sleep_count", 0)
            self.write("max_sleeps", 60)
            (self.dir / "pmset.log").write_text("")
            self.cooldown_file.write_text(f"{CLOCK0 + 99999}\n")
            output = self.run_daemon()
            self.assertIn("resuming cooldown", output)
            enables = self.enables()
            self.assertTrue(enables)
            self.assertTrue(CLOCK0 + COOLDOWN <= min(enables) <= CLOCK0 + COOLDOWN + 10, enables)

    def test_no_quoted_substitution_in_arithmetic(self):
        # /bin/bash 3.2 rejects "$(…)" inside $(( )) (the CS-2434 crash).
        pattern = re.compile(r'\$\(\(\s*"\$\(')
        for name in ("keep-awake.sh", "keep-awakectl"):
            with self.subTest(script=name):
                self.assertIsNone(pattern.search((ROOT / name).read_text()))

    def test_ac_keeps_awake_regardless_of_percentage_when_charging(self):
        for percentage, status in ((4, "charging"), (15, "charging"), (50, "charging"), (80, "charging"), (15, "full"), (50, "charged"), (80, "not charging")):
            with self.subTest(percentage=percentage, status=status):
                self.write("battery", percentage)
                self.set_battery_status(status)
                self.write("max_sleeps", 3)
                output = self.run_daemon()
                self.assertIn(f"AC {'not-charging' if status == 'not charging' else 'unknown' if status in ('full', 'charged') else status}: keeping awake", output)
                self.assertTrue(self.enables())
                self.assertNotIn("AC discharging for", output)
                self.write("clock", CLOCK0)
                self.write("sleep_count", 0)
                self.write("state", 0)
                (self.dir / "pmset.log").write_text("")

    def test_unknown_power_source_falls_back_to_percentage_policy(self):
        self.write("power", "Mystery Power")
        self.write("battery", 4)
        self.write("max_sleeps", 3)
        output = self.run_daemon()

        self.assertIn("battery 4% (< 50%): allowing sleep", output)
        self.assertEqual(self.enables(), [])
        self.assertNotIn("AC discharging", output)

    def test_ac_discharge_releases_after_confirmation_without_forcing_sleep(self):
        self.write("idle", 1900)
        for percentage in (4, 80):
            with self.subTest(percentage=percentage):
                self.write("battery", percentage)
                self.set_battery_status("discharging")
                self.write("max_sleeps", 9)
                self.run_daemon()
                self.assertEqual(self.pmset_events(), [
                    ("disablesleep 0", CLOCK0),
                    ("disablesleep 1", CLOCK0),
                    ("disablesleep 0", CLOCK0 + 60),
                    ("disablesleep 0", CLOCK0 + 90),  # exit cleanup
                ])
                self.write("clock", CLOCK0)
                self.write("sleep_count", 0)
                (self.dir / "pmset.log").write_text("")

    def test_transient_ac_discharge_must_be_consecutive(self):
        self.set_battery_status_sequence("discharging", "discharging", "charging", "discharging", "discharging", "discharging", "discharging", "discharging", "discharging", "charging")
        self.write("max_sleeps", 11)
        output = self.run_daemon()

        self.assertNotIn("AC discharging for 60s (≥ 60s): allowing sleep", output)
        self.assertIn("AC charging: keeping awake", output)
        self.assertEqual(self.pmset_events(), [
            ("disablesleep 0", CLOCK0), ("disablesleep 1", CLOCK0),
            ("disablesleep 0", CLOCK0 + 110),  # only exit cleanup releases
        ])

    def test_unplugging_below_threshold_restores_battery_policy_next_poll(self):
        self.write("battery", 4)
        self.set_battery_status_sequence("charging", "charging", "charging", "charging", "charging", "charging", "charging", "charging")
        self.write("max_sleeps", 4)
        # The source changes on the next snapshot; the stub uses the same
        # sequence machinery for a deterministic per-poll transition.
        self.write("power_sequence", "AC Power\nBattery Power")
        output = self.run_daemon()

        self.assertIn("battery 4% (< 50%): allowing sleep", output)
        self.assertEqual(self.pmset_events(), [
            ("disablesleep 0", CLOCK0), ("disablesleep 1", CLOCK0),
            ("disablesleep 0", CLOCK0 + 10),
            ("disablesleep 0", CLOCK0 + 40),
        ])

    def test_charging_recovery_reasserts_override_next_poll(self):
        self.write("battery", 4)
        self.set_battery_status_sequence(*(["discharging"] * 7 + ["charging"] * 3))
        self.write("max_sleeps", 9)
        self.run_daemon()
        self.assertEqual(self.pmset_events(), [
            ("disablesleep 0", CLOCK0), ("disablesleep 1", CLOCK0),
            ("disablesleep 0", CLOCK0 + 60),
            ("disablesleep 1", CLOCK0 + 70),
            ("disablesleep 0", CLOCK0 + 90),
        ])

    def test_interrupted_discharge_restarts_full_confirmation_window(self):
        for interruption in ("charging", "not charging", "", "malformed", "source", "percentage"):
            with self.subTest(interruption=interruption):
                fixture = KeepAwakeTests()
                fixture.setUp()
                self.addCleanup(fixture.tearDown)
                statuses = ["discharging"] * 12
                if interruption == "source":
                    fixture.write("power_sequence", "\n".join(["AC Power"] * 3 + ["Mystery Power"] + ["AC Power"] * 8))
                elif interruption == "percentage":
                    fixture.write("battery_sequence", "\n".join(["80"] * 3 + [""] + ["80"] * 8))
                else:
                    statuses[3] = interruption
                fixture.set_battery_status_sequence(*statuses)
                fixture.write("max_sleeps", 12)
                fixture.run_daemon()
                self.assertEqual(fixture.pmset_events(), [
                    ("disablesleep 0", CLOCK0), ("disablesleep 1", CLOCK0),
                    ("disablesleep 0", CLOCK0 + 100),
                    ("disablesleep 0", CLOCK0 + 120),
                ])

    def test_backward_clock_restarts_confirmation(self):
        self.set_battery_status("discharging")
        self.write("clock_jump_after", "5 -20")
        self.write("max_sleeps", 12)
        self.run_daemon()
        # At poll 5 the clock falls from +40 to +30. A fresh 60 seconds
        # must be observed from +30, even though it is still after startup.
        self.assertEqual(self.pmset_events(), [
            ("disablesleep 0", CLOCK0), ("disablesleep 1", CLOCK0),
            ("disablesleep 0", CLOCK0 + 90),
            ("disablesleep 0", CLOCK0 + 100),
        ])

    def test_pause_and_cooldown_win_on_low_percentage_ac(self):
        self.write("battery", 4)
        self.write("pause", CLOCK0 + 20)
        self.cooldown_file.write_text(f"{CLOCK0 + 40}\n")
        self.write("max_sleeps", 6)
        self.run_daemon()
        self.assertEqual(self.enables(), [CLOCK0 + 40])

    def test_plugging_in_below_threshold_enables_next_poll(self):
        self.write("battery", 4)
        self.write("power_sequence", "Battery Power\nAC Power\nAC Power")
        self.write("max_sleeps", 3)
        self.run_daemon()
        self.assertEqual(self.enables(), [CLOCK0 + 10])

    def test_battery_at_threshold_stays_awake_after_unplugging(self):
        self.write("battery", 50)
        self.write("power_sequence", "AC Power\nBattery Power\nBattery Power")
        self.write("max_sleeps", 3)
        self.run_daemon()
        self.assertEqual(self.pmset_events(), [
            ("disablesleep 0", CLOCK0), ("disablesleep 1", CLOCK0),
            ("disablesleep 0", CLOCK0 + 30),
        ])


if __name__ == "__main__":
    unittest.main()
