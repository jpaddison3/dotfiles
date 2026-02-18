---
name: review-claude
description: Run a full code review for correctness and quality using an independent Claude subagent
allowed-tools:
  - Task
  - Read
  - Edit
  - Bash
  - Grep
  - Glob
---

# Review with Claude

This skill launches an independent Claude subagent to perform a full code review for correctness and quality.

## Usage

- `/review-claude` - Run review and display output (pass-through mode)
- `/review-claude collaborative` - Run review, then Claude discusses findings
- `/review-claude fix` - Run review, then Claude fixes issues autonomously
- `/review-claude base main` - Review changes against a base branch

Modes can be combined: `/review-claude fix base main`

## Execution

**Parse arguments from:** $ARGUMENTS

**Determine mode:**
- If arguments contain "fix" → fix mode, remove it from args
- If arguments contain "collaborative" → collaborative mode, remove it from args
- If arguments contain "base <branch>" → base branch mode
- Default → pass-through mode

**Determine the diff instruction** for the subagent:
- Default: review uncommitted changes (`git diff HEAD`)
- With base branch: review changes against that branch (`git diff <branch>...HEAD`)

### Launch the review subagent

Use the **Task** tool with `subagent_type: "general-purpose"`. Do **not** specify a model (it will inherit yours).

The prompt should instruct the subagent to:

1. Read the project's `CLAUDE.md` files — check the project root and `~/.claude/CLAUDE.md` (global). Follow any file links or references found in them and read those files too. These provide important project conventions and context.

2. Run `git status` and the appropriate `git diff` command to understand the full set of changes under review. For untracked files, read them directly.

3. Explore the surrounding codebase as needed to understand context for the changes.

4. Perform a full review of the changes for **correctness** and **quality**, with particular attention to:

   a) **Types:**
      - Flag any type casts. These require at minimum a comment explaining them, but flag them for human review regardless.
      - Flag weak typings, such as `Record<string, string>` or similar.

   b) **Fail fast, fail loud:**
      - Carefully review what the code does when expected information is missing.
      - Flag patterns like `foo?.bar ?? ""` — these hide missing data.
      - Flag error catching without `recordError`-ing or re-throwing.

   c) **Halfway refactoring:**
      - Flag patterns like `NEW_VAR = x; OLD_VAR = NEW_VAR; // For backwards compatibility`.
      - Flag re-exporting variables/functions that have moved instead of updating consumers.
      - Exception: server/client API boundaries.

   d) **General correctness and quality** — anything else that looks wrong, risky, or could be improved.

5. These issues may be ignored inside test files. When in doubt about whether something is an issue, mention it.

6. **Do not make any changes.** This is a review only.

### Output handling

- **Pass-through mode:** Display the subagent's review output directly. Do not add commentary, analysis, or suggestions. Just show what the subagent said.

- **Collaborative mode:** After showing the review output, provide your own analysis. Note agreements, disagreements, or additional concerns the subagent may have missed. Offer to help address any issues found.

- **Fix mode:** After reviewing the subagent's output, make executive decisions and fix issues autonomously. Use your own judgment on what's worth fixing.

  **One warning:** Your judgment tends to be too lenient on type system issues, fail-fast violations, and backwards-compatibility hacks. When the subagent flags these, lean toward fixing them rather than dismissing them.

  After fixing, briefly summarize what you changed and why. If you skipped any flagged issues, explain your reasoning.
