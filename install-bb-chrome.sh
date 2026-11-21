#!/bin/bash
set -euo pipefail

checkout="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
skill="$checkout/bb-skills/bb-chrome"
destination="$HOME/.bb/skills/bb-chrome"

case "$checkout" in
  */plugins/environment-git-worktree/host-data/worktrees/*)
    echo "Run the installer from a permanent dotfiles checkout so BB can keep using the skill." >&2
    exit 1 ;;
esac

if [[ ! -f "$skill/SKILL.md" ]]; then
  echo "Missing BB Chrome skill at $skill/SKILL.md" >&2
  exit 1
fi

if [[ -L "$destination" && "$destination" -ef "$skill" ]]; then
  exit 0
fi

# Repair a dangling link with the target shape created by this installer.
if [[ -L "$destination" && ! -e "$destination" &&
      "$(readlink "$destination")" == /*/bb-skills/bb-chrome ]]; then
  ln -sfn "$skill" "$destination"
  exit 0
fi

if [[ -e "$destination" || -L "$destination" ]]; then
  echo "BB Chrome skill already exists at $destination. Move it aside before installing from this checkout." >&2
  exit 1
fi

mkdir -p "$(dirname -- "$destination")"
ln -sn "$skill" "$destination"
