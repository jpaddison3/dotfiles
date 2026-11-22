#!/bin/bash
# Daily updates for the shared native Claude Code install. Claude's built-in
# background updater doesn't run in the headless sessions bb starts, so without
# this job the CLI stalls until someone opens an interactive terminal session.
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
# binary in ~/.local/share/claude/versions. Anything else (a missing binary, a
# custom launcher, an npm install) is not the install this job updates.
target="$(readlink "$cli" || true)"
[[ -z "$target" || "$target" = /* ]] || target="$(dirname -- "$cli")/$target"
if [[ ! -L "$cli" || ! -x "$cli" || -z "$target" ]] \
    || ! [[ "$(dirname -- "$target")" -ef "$install_dir/versions" ]]; then
  echo "ERROR: $cli is not the native Claude Code installation; nothing changed."
  exit 1
fi

# Run with only what launchd would supply, so a manual run from an agent session
# behaves like the scheduled one: no inherited CLAUDE_CONFIG_DIR (the default
# ~/.claude settings choose the release channel), DISABLE_UPDATES, or other
# session variables. Work outside any project so no project settings apply. The
# official updater owns download verification, locking, and switching versions.
cd "$install_dir"
run_cli() {
  env -i HOME="$HOME" PATH="$PATH" USER="${USER:-$(id -un)}" \
    LOGNAME="${LOGNAME:-$(id -un)}" SHELL=/bin/bash TMPDIR="${TMPDIR:-/tmp}" \
    "$cli" "$@"
}
printf 'Before: '
run_cli --version
if run_cli update; then
  printf 'After: '
  run_cli --version
  echo "Update completed. Existing sessions keep their current executable."
else
  status=$?
  echo "ERROR: Claude Code update failed (exit $status); see output above."
  exit "$status"
fi
