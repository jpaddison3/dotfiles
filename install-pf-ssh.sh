#!/usr/bin/env bash
#
# install-pf-ssh.sh — Allow SSH only from this Mac and Tailscale, using pf.
#
# Copies pf-ssh.rules to /etc/pf.anchors/com.jpaddison.ssh and a root LaunchDaemon that
# loads it into anchor com.apple/150.jpaddison-ssh at boot (macOS's own com.apple.pfctl job
# loads /etc/pf.conf, whose `anchor "com.apple/*"` evaluates it). /etc/pf.conf is left alone,
# since macOS updates can reset it. The Application Firewall in System Settings can't do this:
# it filters by app, not by source address, and always lets built-in sshd through.
#
# Usage:  ./install-pf-ssh.sh            # prompts for sudo once
# Off until next boot:
#         sudo pfctl -a com.apple/150.jpaddison-ssh -F rules
# Undo:   sudo launchctl bootout system/com.jpaddison.pf-ssh
#         sudo pfctl -a com.apple/150.jpaddison-ssh -F rules
#         sudo rm /Library/LaunchDaemons/com.jpaddison.pf-ssh.plist \
#                 /etc/pf.anchors/com.jpaddison.ssh
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.jpaddison.pf-ssh"
ANCHOR="com.apple/150.jpaddison-ssh"
RULES_SRC="${REPO_DIR}/pf-ssh.rules"
RULES_DEST="/etc/pf.anchors/com.jpaddison.ssh"
PLIST_SRC="${REPO_DIR}/${LABEL}.plist"
PLIST_DEST="/Library/LaunchDaemons/${LABEL}.plist"

if [[ $EUID -ne 0 ]]; then
  echo "Re-running with sudo (needed to install pf rules and a root LaunchDaemon)…"
  exec sudo "$0" "$@"
fi

# Validate before installing, so a typo never reaches the live ruleset.
pfctl -nf "$RULES_SRC" -a "$ANCHOR" 2>&1 | grep -v -e ALTQ -e 'could result in flushing' \
  -e 'present in the main ruleset' -e 'See /etc/pf.conf' -e '^$' || true
plutil -lint -s "$PLIST_SRC"

install -o root -g wheel -m 644 "$RULES_SRC" "$RULES_DEST"
install -o root -g wheel -m 644 "$PLIST_SRC" "$PLIST_DEST"

# Load the rules now (the daemon does the same at boot), then (re)load the daemon.
pfctl -a "$ANCHOR" -f "$RULES_DEST" 2>/dev/null
launchctl bootout "system/${LABEL}" 2>/dev/null || true
for _ in {1..50}; do
  launchctl print "system/${LABEL}" >/dev/null 2>&1 || break
  sleep 0.1
done
launchctl bootstrap system "$PLIST_DEST"
launchctl enable "system/${LABEL}"

echo "Installed ${LABEL}. Active rules in ${ANCHOR}:"
pfctl -a "$ANCHOR" -sr 2>/dev/null
