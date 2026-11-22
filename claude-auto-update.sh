#!/bin/bash
# Daily updates for the shared native Claude Code install. Claude's built-in
# background updater appears to run only in interactive terminal sessions, so
# with nearly every session started headless by bb, the CLI stalled for days.
# Invoke the real CLI, bypassing the account shim in ~/.local/codex-shim. Every
# account profile runs this same binary.
set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
log_dir="$HOME/.local/share/claude-auto-update"
mkdir -p "$log_dir"
exec >> "$log_dir/claude-auto-update.log" 2>&1
printf '\n--- %s ---\n' "$(date '+%Y-%m-%d %I:%M:%S %p %Z')"

cli="$HOME/.local/bin/claude"
install_dir="$HOME/.local/share/claude"
# The native installer owns ~/.local/bin/claude as a symlink to a version
# binary, a regular file, in ~/.local/share/claude/versions. Anything else (a
# missing binary, a custom launcher, a chained symlink, an npm install) is not
# the install this job updates.
target="$(readlink "$cli" || true)"
[[ -z "$target" || "$target" = /* ]] || target="$(dirname -- "$cli")/$target"
if [[ ! -L "$cli" || -z "$target" || -L "$target" || ! -f "$target" || ! -x "$target" ]] \
    || ! [[ "$(dirname -- "$target")" -ef "$install_dir/versions" ]]; then
  echo "ERROR: $cli is not the native Claude Code installation; nothing changed."
  exit 1
fi

# Run with a minimal environment, close to what launchd supplies, so a manual
# run from an agent session behaves like the scheduled one: no inherited
# CLAUDE_CONFIG_DIR (the default ~/.claude settings choose the release channel),
# DISABLE_UPDATES, or other session variables. TMPDIR is the per-user temp dir
# launchd jobs get, not a session's sandbox temp dir. Work outside any project
# so no project settings apply. The official updater owns download
# verification, locking, and switching versions.
cd "$install_dir"
user="$(id -un)"
tmp="$(getconf DARWIN_USER_TEMP_DIR 2>/dev/null || echo /tmp)"
# Bound each call so a hung download can't hold launchd's single instance of
# this job (and every later scheduled run) indefinitely. SIGALRM survives exec.
limit="${CLAUDE_AUTO_UPDATE_TIME_LIMIT:-1800}"
run_cli() {
  env -i HOME="$HOME" PATH="$PATH" USER="$user" LOGNAME="$user" \
    SHELL=/bin/bash TMPDIR="$tmp" \
    /usr/bin/perl -e 'alarm shift; exec @ARGV or die "exec: $!\n"' "$limit" "$cli" "$@"
}
fail() {
  local status=$?
  [[ -z "${2-}" ]] || printf '%s\n' "$2"
  local hint=""
  [[ "$status" -ne 142 ]] || hint=", stopped at the ${limit}s time limit"
  echo "ERROR: $1 (exit $status$hint); see output above."
  exit "$status"
}

before="$(run_cli --version)" || fail "claude --version failed before updating" "$before"
echo "Before: $before"
run_cli update || fail "Claude Code update failed"
after="$(run_cli --version)" || fail "claude --version failed after updating" "$after"
echo "After: $after"
if [[ "$after" == "$before" ]]; then
  echo "Version unchanged; see claude update's output above."
else
  echo "Updated. Existing sessions keep their current executable."
fi
