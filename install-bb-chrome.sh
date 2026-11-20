#!/bin/bash
set -euo pipefail

skill="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/bb-skills/bb-chrome" && pwd -P)"
destination="$HOME/.bb/skills/bb-chrome"

if [[ ! -f "$skill/SKILL.md" ]]; then
  echo "Missing BB Chrome skill at $skill/SKILL.md" >&2
  exit 1
fi

if [[ -L "$destination" && "$destination" -ef "$skill" ]]; then
  exit 0
fi

if [[ -e "$destination" || -L "$destination" ]]; then
  echo "BB Chrome skill already exists at $destination. Move it aside before installing from this checkout." >&2
  exit 1
fi

mkdir -p "$(dirname -- "$destination")"
ln -sh "$skill" "$destination"
