#!/bin/bash
# Claude Code statusLine command - Pure-inspired prompt, fit to 80 cols
input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
model=$(echo "$input" | jq -r '.model.display_name // ""')
effort=$(echo "$input" | jq -r '.effort.level // empty')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
git_worktree=$(echo "$input" | jq -r '.workspace.git_worktree // empty')
worktree_branch=$(echo "$input" | jq -r '.worktree.branch // empty')

MAX_WIDTH=80

# Shorten home directory to ~
home="$HOME"
short_cwd="${cwd/#$home/~}"

# Use branch from worktree info if available
branch=""
[ -n "$worktree_branch" ] && branch="$worktree_branch"
[ -z "$branch" ] && [ -n "$git_worktree" ] && branch="$git_worktree"

# Build context usage part
if [ -n "$used_pct" ]; then
  ctx_part="ctx:$(printf '%.0f' "$used_pct")%"
else
  ctx_part=""
fi

# Fixed metadata suffix - model/effort/context are never truncated
meta=""
[ -n "$model" ] && meta="$meta  $model"
[ -n "$effort" ] && meta="$meta  $effort"
[ -n "$ctx_part" ] && meta="$meta  $ctx_part"

# Collapse a path to its trailing components so it fits in $2 chars,
# prefixing an ellipsis for whatever got dropped from the front.
truncate_path() {
  local path="$1" maxlen="$2"
  if [ "${#path}" -le "$maxlen" ]; then
    printf '%s' "$path"
    return
  fi

  local IFS=/
  local -a comps
  read -ra comps <<< "$path"
  local n=${#comps[@]}

  local i tail joined candidate
  for ((i = n - 1; i >= 1; i--)); do
    tail=("${comps[@]:$((n - i))}")
    joined="$(IFS=/; echo "${tail[*]}")"
    candidate="…/$joined"
    if [ "${#candidate}" -le "$maxlen" ]; then
      printf '%s' "$candidate"
      return
    fi
  done

  # Even the last component alone doesn't fit - hard-truncate it.
  local last="${comps[$((n - 1))]}"
  local keep=$((maxlen - 3))
  [ "$keep" -lt 1 ] && keep=1
  printf '…/%s…' "${last:0:keep}"
}

avail=$((MAX_WIDTH - ${#meta}))
[ "$avail" -lt 10 ] && avail=10

if [ -n "$branch" ]; then
  full_dir="$short_cwd  $branch"
else
  full_dir="$short_cwd"
fi

if [ "${#full_dir}" -le "$avail" ]; then
  dir_part="$full_dir"
elif [ -z "$branch" ]; then
  dir_part="$(truncate_path "$short_cwd" "$avail")"
else
  # Truncate the path first, keeping the full branch name.
  path_budget=$((avail - ${#branch} - 2))
  [ "$path_budget" -lt 1 ] && path_budget=1
  trunc_path="$(truncate_path "$short_cwd" "$path_budget")"
  dir_part="$trunc_path  $branch"

  if [ "${#dir_part}" -gt "$avail" ]; then
    # Path is already minimal - truncate the branch too.
    trunc_path="$(truncate_path "$short_cwd" 12)"
    branch_room=$((avail - ${#trunc_path} - 2))
    [ "$branch_room" -lt 3 ] && branch_room=3
    if [ "${#branch}" -gt "$branch_room" ]; then
      keep=$((branch_room - 1))
      [ "$keep" -lt 1 ] && keep=1
      trunc_branch="${branch:0:keep}…"
    else
      trunc_branch="$branch"
    fi
    dir_part="$trunc_path  $trunc_branch"
  fi
fi

printf '\033[2m%s\033[0m' "$dir_part$meta"
