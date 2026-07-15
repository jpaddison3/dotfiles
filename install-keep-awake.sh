#!/usr/bin/env bash
#
# install-keep-awake.sh — Deploy keep-awake.sh as a root LaunchDaemon.
#
# Installs a ROOT-OWNED copy of the script into /usr/local/sbin (a root-only
# writable dir) so the auto-at-boot root process can't be hijacked by anyone
# who can edit the user-writable repo copy. Then (re)loads the daemon.
#
# Usage:  ./install-keep-awake.sh          # prompts for sudo once
# Undo:   sudo launchctl bootout system/com.jpaddison.keep-awake
#         sudo rm /Library/LaunchDaemons/com.jpaddison.keep-awake.plist \
#                 /usr/local/sbin/keep-awake.sh
#         sudo pmset -a disablesleep 0      # clear the flag if left set
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.jpaddison.keep-awake"
SRC="${REPO_DIR}/keep-awake.sh"
DEST="/usr/local/sbin/keep-awake.sh"
CTL_SRC="${REPO_DIR}/keep-awakectl"
CTL_DEST="/usr/local/sbin/keep-awakectl"
SUDOERS_SRC="${REPO_DIR}/keep-awake.sudoers"
SUDOERS_DEST="/etc/sudoers.d/keep-awake"
PLIST_SRC="${REPO_DIR}/${LABEL}.plist"
PLIST_DEST="/Library/LaunchDaemons/${LABEL}.plist"

if [[ $EUID -ne 0 ]]; then
  echo "Re-running with sudo (needed to install a root LaunchDaemon)…"
  exec sudo "$0" "$@"
fi

# Root-owned copy of the script + the plist.
install -d -o root -g wheel -m 755 /usr/local/sbin
install -o root -g wheel -m 755 "$SRC" "$DEST"
install -o root -g wheel -m 755 "$CTL_SRC" "$CTL_DEST"
install -o root -g wheel -m 644 "$PLIST_SRC" "$PLIST_DEST"

# Scoped passwordless sudo for the instant `keep-awakectl pause` flag flip.
# Validate BEFORE installing so a syntax error can never wedge sudo.
visudo -cf "$SUDOERS_SRC" >/dev/null
install -o root -g wheel -m 440 "$SUDOERS_SRC" "$SUDOERS_DEST"

# Reload cleanly if already present, then bootstrap + enable.
launchctl bootout "system/${LABEL}" 2>/dev/null || true
launchctl bootstrap system "$PLIST_DEST"
launchctl enable "system/${LABEL}"

echo "Installed and loaded ${LABEL}."
