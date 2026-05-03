---
name: review-multi
description: Run parallel code reviews with both Claude and Codex, then synthesize findings
allowed-tools:
  - Task
  - Agent
  - Read
  - Edit
  - Bash
  - Grep
  - Glob
---

# Review (Parallel Claude + Codex)

This skill runs two code reviews in parallel: one via the installed
`review-claude` adapter and one via the installed `review-codex` adapter. Then
it presents both sets of findings.

## Usage

- `/review-multi` or `$review-multi` - run reviews, then discuss findings
- `/review-multi fix` or `$review-multi fix` - run reviews, then fix issues
  autonomously
- `/review-multi base main` or `$review-multi base main` - review changes
  against a base branch
- `/review-multi mini` or `$review-multi mini` - faster review

Modes can be combined: `/review-multi mini fix base main`.

## Execution

**Parse arguments from:** `$ARGUMENTS` in Claude, or the user's prompt after
`$review-multi` in Codex.

**Determine mode:**
- If arguments contain "mini" → mini mode, remove it from args
- If arguments contain "fix" → fix mode, remove it from args
- If arguments contain "passthrough" → passthrough mode, remove it from args
- If arguments contain "base <branch>" → base branch mode

### Gather review procedures

Read the skill definitions from the sibling skill directories:
- `../review-claude/SKILL.md`
- `../review-codex/SKILL.md`

These define the review procedures for each reviewer. Follow their execution instructions, but with these modifications:
1. **Run reviews in parallel** using the current runtime's available parallel
   mechanism.
2. **Both run in pass-through mode** regardless of the mode argument — mode handling is done here, not by the individual reviews.

#### Full mode (default)

Launch both Claude and Codex reviews in parallel. Pass along the base branch
argument if present.

#### Mini mode

Launch both Claude and Codex reviews in parallel, but pass `mini` to both
review adapters.

### Output handling

- **Collaborative mode:** After showing all outputs, provide your own synthesis. Deduplicate the findings, and summarize the points to address. Offer to help address issues found. Do **not** make fixes yourself in this mode. Do this by default.

- **Pass-through mode:** Display both review outputs directly. Do not add commentary, analysis, or suggestions.

- **Fix mode:** After reviewing both outputs, make executive decisions and fix issues autonomously. Use your own judgment on what's worth fixing.

  **One warning:** Your judgment tends to be too lenient on type system issues, fail-fast violations, and backwards-compatibility hacks. When either reviewer flags these, lean toward fixing them rather than dismissing them.

  After fixing, briefly summarize what you changed and why. If you skipped any flagged issues, explain your reasoning.

**The default mode is collaborative** — if no mode argument is provided, synthesize the findings and offer to help with fixes, but don't fix autonomously.
