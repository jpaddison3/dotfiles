---
name: cpr
description: Commit changes and create a GitHub PR. Creates a new branch if on main/master (unless CLAUDE.md says otherwise).
allowed-tools:
  - Bash(git checkout *)
  - Bash(git switch *)
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git branch *)
  - Bash(git push *)
  - Bash(gh pr create *)
  - Bash(gh pr view *)
  - Read
  - Grep
  - Glob
---

# Commit and Create PR

Stage changes, commit, and create a GitHub pull request.

Stage and commit the current changes. Follow the standard git commit protocol
including from the user's preferences. If on main/master, check CLAUDE.md for
branch policies and create a new branch if needed.

No need to create a separate file for the PR description draft or to ask the
user to review it. Simply push to the remote and create a PR using `gh`.
