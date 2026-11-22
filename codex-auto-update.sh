#!/bin/bash
# Daily updates for the shared standalone CLI, independent of app-server daemons.
# Invoke the real CLI, bypassing the account/speed shim. Both account profiles
# use this same installation; CODEX_HOME must point at its owning home.
set -euo pipefail

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
log_dir="$HOME/.local/share/codex-auto-update"
mkdir -p "$log_dir"
exec >> "$log_dir/codex-auto-update.log" 2>&1
printf '\n--- %s ---\n' "$(date '+%Y-%m-%d %I:%M:%S %p %Z')"

cli="$HOME/.local/bin/codex"
install_home="$HOME/.codex"
package="$install_home/packages/standalone/current"
if [[ ! -x "$cli" ]] || ! { [[ "$cli" -ef "$package/bin/codex" ]] || [[ "$cli" -ef "$package/codex" ]]; }; then
  echo "ERROR: $cli is not the shared standalone Codex installation; nothing changed."
  exit 1
fi

# Work outside a project and select the shared installation explicitly, even
# when run manually from a personal-account session. The official updater owns
# download verification, install locking, and switching to the new release.
cd "$install_home"
printf 'Before: '
"$cli" --version
if env CODEX_HOME="$install_home" CODEX_RELEASE=latest CODEX_NON_INTERACTIVE=1 \
    CODEX_INSTALL_DIR="$HOME/.local/bin" "$cli" update; then
  printf 'After: '
  "$cli" --version
  echo "Update completed. Existing sessions keep their current executable."
else
  status=$?
  echo "ERROR: Codex update failed (exit $status); see output above."
  exit "$status"
fi
