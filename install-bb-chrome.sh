#!/bin/bash
set -euo pipefail

checkout="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
home_path="$(cd -- "$HOME" && pwd -P)"
skill="$checkout/bb-skills/bb-chrome"
destination="$home_path/.bb/skills/bb-chrome"

case "$checkout" in
  "$home_path"/Documents|"$home_path"/Documents/*|\
  "$home_path"/Desktop|"$home_path"/Desktop/*|\
  "$home_path"/Downloads|"$home_path"/Downloads/*)
    echo "Keep the dotfiles checkout outside Documents, Desktop, and Downloads so macOS allows BB to read the skill link." >&2
    exit 1 ;;
  */plugins/environment-git-worktree/host-data/worktrees/*|"$home_path"/.cache/agent-tmp|"$home_path"/.cache/agent-tmp/*)
    echo "Run the installer from a permanent dotfiles checkout so BB can keep using the skill." >&2
    exit 1 ;;
esac

if [[ -f "$checkout/.git" ]]; then
  (
    unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
    git_dir="$(git -C "$checkout" rev-parse --absolute-git-dir)"
    common_git_dir="$(git -C "$checkout" rev-parse --path-format=absolute --git-common-dir)"
    if [[ "$git_dir" != "$common_git_dir" ]]; then
      echo "Run the installer from the main dotfiles checkout so BB can keep using the skill." >&2
      exit 1
    fi
  )
fi

if [[ ! -f "$skill/SKILL.md" ]]; then
  echo "Missing BB Chrome skill at $skill/SKILL.md" >&2
  exit 1
fi

if [[ -L "$destination" ]]; then
  if [[ "$destination" -ef "$skill" ]]; then
    exit 0
  fi

  # Repair a link with the installer's target shape only when stat returns ENOENT.
  previous_target="$(readlink "$destination")"
  if [[ "$previous_target" == /*/bb-skills/bb-chrome ]] &&
      /usr/bin/perl -MErrno=ENOENT -e 'exit((!stat($ARGV[0]) && $! == ENOENT) ? 0 : 1)' -- "$previous_target"; then
    ln -sfn "$skill" "$destination"
    printf 'Updated dangling BB Chrome skill link from %s to %s\n' "$previous_target" "$skill"
    exit 0
  fi

  echo "BB Chrome skill already exists at $destination and points to $previous_target. Check that target before moving the link aside." >&2
  exit 1
fi

if [[ -e "$destination" ]]; then
  echo "BB Chrome skill already exists at $destination. Move it aside before installing from this checkout." >&2
  exit 1
fi

mkdir -p "$(dirname -- "$destination")"
ln -sn "$skill" "$destination"
