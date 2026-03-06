---
name: ci
description: Stage and commit changes. Creates a new branch if on main/master (unless CLAUDE.md says otherwise).
allowed-tools:
  - Bash(git checkout *)
  - Bash(git switch *)
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git branch *)
  - Read
  - Grep
  - Glob
---

# Commit

Stage and commit the current changes. Follow the standard git commit protocol
including from the user's preferences. If on main/master, check CLAUDE.md for
branch policies and create a new branch if needed.

Run each command one at a time, though you may queue them, don't use `&&`.

For commit messages, use the Write tool to write the message to a file, then
`git commit -F <file>`. Use `project_root/tmp/commit-msg-[short-descriptor].txt`
if a `tmp/` directory exists in the project root, otherwise fall back to `/tmp`.
This keeps the command single-line so it matches the allowed-tools pattern.

Example: `project_root/tmp/commit-msg-pr-428-review-fixes.txt` (Make it not
conflict with another commit message file.)
