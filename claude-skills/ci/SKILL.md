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

Add exactly one co-author trailer appropriate to the agent making the commit:

- When running in Claude: `Co-authored-by: Claude <noreply@anthropic.com>`
- When running in Codex: `Co-authored-by: OpenAI Codex <codex@openai.com>`
