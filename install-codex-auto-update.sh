#!/bin/bash
# Install/reload only the Codex CLI updater, without running newcomputer.bash.
set -euo pipefail
repo="$(cd -- "$(dirname -- "$0")" && pwd -P)"
label=com.jpaddison.codex-auto-update
domain="gui/$(id -u)"
log_dir="$HOME/.local/share/codex-auto-update"
mkdir -p "$HOME/.local/bin" "$HOME/Library/LaunchAgents" "$log_dir"
# Follow the launchd hard-link convention documented in newcomputer.bash.
ln -f "$repo/codex-auto-update.sh" "$HOME/.local/bin/codex-auto-update.sh"
ln -f "$repo/$label.plist" "$HOME/Library/LaunchAgents/$label.plist"
/usr/bin/plutil -lint "$HOME/Library/LaunchAgents/$label.plist"
if launchctl print "$domain/$label" > "$log_dir/previous-launchd-status.log" 2>&1; then
  launchctl bootout "$domain/$label"
fi
launchctl enable "$domain/$label"
launchctl bootstrap "$domain" "$HOME/Library/LaunchAgents/$label.plist"
echo "Installed $label: runs now, at login, and daily at 4:00am."
echo "Update log: $log_dir/codex-auto-update.log"
