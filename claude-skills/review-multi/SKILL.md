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

This skill runs two code reviews in parallel — several via `/review-claude` and one via `/review-codex` — then presents both sets of findings.

## Usage

- `/review-multi` - Run reviews, then Claude discusses findings
- `/review-multi fix` - Run reviews, then Claude fixes issues autonomously
- `/review-multi base main` - Review changes against a base branch
- `/review-multi mini` - Faster review: single Claude agent, Codex step 1 only

Modes can be combined: `/review-multi mini fix base main`

## Execution

**Parse arguments from:** $ARGUMENTS

**Determine mode:**
- If arguments contain "mini" → mini mode, remove it from args
- If arguments contain "fix" → fix mode, remove it from args
- If arguments contain "passthrough" → passthrough mode, remove it from args
- If arguments contain "base <branch>" → base branch mode

### Gather review procedures

Read the skill definitions from the sibling skill directories:
- `claude-skills/review-claude/SKILL.md`
- `claude-skills/review-codex/SKILL.md`

These define the review procedures for each reviewer. Follow their execution instructions, but with these modifications:
1. **Run reviews in parallel** — launch them simultaneously using **Agent** tool calls in a single message.
2. **Both run in pass-through mode** regardless of the mode argument — mode handling is done here, not by the individual reviews.

For the Claude review, use `subagent_type: "general-purpose"` (do not specify a model). For the Codex review, use `subagent_type: "Bash"`. Pass along the base branch argument if present.

#### Full mode (default)

Launch both Claude and Codex reviews in parallel (two Agent calls in one message). Claude launches its full 6 sub-agents internally. Don't forget the Codex follow-up step (step 2 with specific criteria).

#### Mini mode

Launch both Claude and Codex reviews in parallel (two Agent calls in one message), but:
- **Claude**: Tell the agent to run all 6 review areas in a single pass (no sub-agents). Include all review criteria from review-claude's agents 1–6 combined into one prompt.
- **Codex**: Run Step 1 only (the general `codex review` command). Skip Step 2 (the follow-up with specific criteria).

### Output handling

- **Collaborative mode:** After showing all outputs, provide your own synthesis. Deduplicate the findings, and summarize the points to address. Offer to help address issues found. Do **not** make fixes yourself in this mode. Do this by default.

- **Pass-through mode:** Display both review outputs directly. Do not add commentary, analysis, or suggestions.

- **Fix mode:** After reviewing both outputs, make executive decisions and fix issues autonomously. Use your own judgment on what's worth fixing.

  **One warning:** Your judgment tends to be too lenient on type system issues, fail-fast violations, and backwards-compatibility hacks. When either reviewer flags these, lean toward fixing them rather than dismissing them.

  After fixing, briefly summarize what you changed and why. If you skipped any flagged issues, explain your reasoning.

**The default mode is collaborative** — if no mode argument is provided, synthesize the findings and offer to help with fixes, but don't fix autonomously.
