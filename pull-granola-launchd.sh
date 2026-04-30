#!/bin/bash
# Wrapper invoked by the com.jpaddison.pull-granola launchd agent.
#
# Both this wrapper and pull-granola.py must live in ~/.local/bin — macOS's
# App Management sandbox blocks launchd-spawned bash from executing files
# inside ~/Documents (even via symlink). newcomputer.bash copies both from
# the dotfiles canonical source; re-run it (or the copy block within) after
# editing either file.

LOG_DIR="$HOME/.local/share/pull-granola"
LOG="$LOG_DIR/pull-granola.log"
mkdir -p "$LOG_DIR"
exec >> "$LOG" 2>&1

echo "--- $(date -u '+%Y-%m-%dT%H:%M:%SZ') pull-granola tick ---"

export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
if [ -s "$NVM_DIR/nvm.sh" ]; then . "$NVM_DIR/nvm.sh"; fi

# Homebrew on Apple Silicon
export PATH="/opt/homebrew/bin:$PATH"

# Refresh creds from the Granola desktop app's keychain entry. The CLI's auth
# token expires every few days; importing again is idempotent and ~free as long
# as the desktop session is healthy. Without this, the agent silently 500s for
# days until JP notices via missing transcripts.
granola auth login >/dev/null 2>&1 || echo "WARN: granola auth login failed at $(date -u +%FT%TZ)"

exec "$HOME/.local/bin/pull-granola.py"
