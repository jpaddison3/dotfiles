#!/usr/bin/env bash
# Install the inbox-triage Raycast Script Commands without running the full
# dotfiles bootstrap.
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/raycast/inbox-triage" && pwd)"
if [[ -z "${HOME:-}" ]]; then
  echo "error: HOME must be set to install the Raycast scripts" >&2
  exit 1
fi

DEST_DIR="${RAYCAST_INBOX_TRIAGE_DIR:-$HOME/.local/share/raycast/scripts/inbox-triage}"
SCRIPTS=(
  "inbox-triage.sh"
  "inbox-triage-bod.sh"
  "inbox-triage-eod.sh"
)

for script in "${SCRIPTS[@]}"; do
  source="$SOURCE_DIR/$script"
  if [[ ! -f "$source" || ! -x "$source" ]]; then
    echo "error: expected executable Raycast script is missing: $source" >&2
    exit 1
  fi
done

install -d -m 755 "$DEST_DIR"
for script in "${SCRIPTS[@]}"; do
  install -m 755 "$SOURCE_DIR/$script" "$DEST_DIR/$script"
done

echo "installed inbox-triage Raycast scripts in $DEST_DIR"
