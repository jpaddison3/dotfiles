#!/bin/bash
set -euo pipefail

skill="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/bb-skills/bb-chrome" && pwd -P)"
destination="$HOME/.bb/skills/bb-chrome"

case "$skill" in
  */plugins/environment-git-worktree/host-data/worktrees/*)
    echo "Run the installer from a permanent dotfiles checkout so BB can keep using the skill." >&2
    exit 1 ;;
esac

if [[ ! -f "$skill/SKILL.md" ]]; then
  echo "Missing BB Chrome skill at $skill/SKILL.md" >&2
  exit 1
fi

if [[ -L "$destination" ]]; then
  case "$(readlink "$destination")" in
    "$skill") exit 0 ;;
    # Recognize this installer's links even if the previous checkout is gone.
    /*/bb-skills/bb-chrome)
      ln -sfn "$skill" "$destination"
      exit 0 ;;
  esac
fi

if [[ -e "$destination" || -L "$destination" ]]; then
  echo "BB Chrome skill already exists at $destination. Move it aside before installing from this checkout." >&2
  exit 1
fi

mkdir -p "$(dirname -- "$destination")"
ln -sn "$skill" "$destination"
