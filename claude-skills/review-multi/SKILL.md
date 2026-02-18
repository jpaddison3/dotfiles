---
name: review-multi
description: Run parallel code reviews with both Claude and Codex, then synthesize findings
allowed-tools:
  - Task
  - Read
  - Edit
  - Bash
  - Grep
  - Glob
---

# Review (Parallel Claude + Codex)

This skill runs two independent code reviews in parallel — one from a Claude subagent and one from Codex (GPT-5.2) — then presents both sets of findings.

## Usage

- `/review-multi` - Run both reviews and display outputs (pass-through mode)
- `/review-multi collaborative` - Run both reviews, then Claude discusses findings
- `/review-multi fix` - Run both reviews, then Claude fixes issues autonomously
- `/review-multi base main` - Review changes against a base branch

Modes can be combined: `/review-multi fix base main`

## Execution

**Parse arguments from:** $ARGUMENTS

**Determine mode:**
- If arguments contain "fix" → fix mode, remove it from args
- If arguments contain "collaborative" → collaborative mode, remove it from args
- If arguments contain "base <branch>" → base branch mode
- Default → pass-through mode

**Determine the diff/review target:**
- Default: uncommitted changes
- With base branch: changes against that branch

### Launch both reviews in parallel

Use **two Task tool calls in a single message** so they run concurrently.

#### Task 1: Claude review

`subagent_type: "general-purpose"` — do **not** specify a model.

The prompt should instruct the subagent to:

1. Read the project's `CLAUDE.md` files — check the project root and `~/.claude/CLAUDE.md` (global). Follow any file links or references found in them and read those files too.

2. Run `git status` and the appropriate `git diff` command (`git diff HEAD` for uncommitted, `git diff <branch>...HEAD` for base branch) to understand the changes under review. For untracked files, read them directly.

3. Explore the surrounding codebase as needed to understand context.

4. Perform a full review of the changes for **correctness** and **quality**, with particular attention to:

   a) **Types:** Flag type casts (require a comment at minimum) and weak typings like `Record<string, string>`.

   b) **Fail fast, fail loud:** Flag patterns that hide missing data (`foo?.bar ?? ""`), error catching without `recordError`-ing or re-throwing.

   c) **Halfway refactoring:** Flag `NEW_VAR = x; OLD_VAR = NEW_VAR` patterns, re-exports instead of updating consumers (exception: API boundaries).

   d) **General correctness and quality.**

5. Ignore these issues inside test files. When in doubt, mention it.

6. **Do not make any changes.** This is a review only.

#### Task 2: Codex review

`subagent_type: "Bash"`.

Run the following two commands sequentially:

```bash
codex review [--uncommitted OR --base <branch>]
```

Then:

```bash
codex exec resume --last "A few things I like to double check with code that my AI coding agent has produced:

1) Types:
   a) Are there any type casts that it added. (I often find it doesn't tell me about them like I ask it to.) It's required to at least add a comment explaining them, but I like to review them myself in any case.
   b) Are there any weak typings, such as Record<string, string> or similar.

2) We follow a \"Fail fast, fail loud\" philosophy here. I want you to carefully review what the code does when expected information is missing. The classic thing I don't want is \`foo?.bar ?? \"\"\` – that's just hiding the fact that data is missing. I also don't like catching errors without \`recordError\`-ing them or re-throwing.

3) (Pet peeve): when refactoring, it likes to go halfway. \`NEW_VAR = x; OLD_VAR = NEW_VAR; // For backwards compatibility\`. Or similar for re-exporting variables/functions that have moved. It should fix the consumer to use the new name, with the exception of server/client API boundaries.

You may ignore these issues inside test files. When in doubt, tell me about something you're unsure about.

**IMPORTANT**: Do not make any changes. This is only a review."
```

### Output handling

Present the results under clear headings: **Claude Review** and **Codex Review**.

- **Pass-through mode:** Display both review outputs directly. Do not add commentary, analysis, or suggestions.

- **Collaborative mode:** After showing both outputs, provide your own synthesis. Highlight where they agree, where they disagree, and any additional concerns neither caught. Offer to help address issues found.

- **Fix mode:** After reviewing both outputs, make executive decisions and fix issues autonomously. Use your own judgment on what's worth fixing.

  **One warning:** Your judgment tends to be too lenient on type system issues, fail-fast violations, and backwards-compatibility hacks. When either reviewer flags these, lean toward fixing them rather than dismissing them.

  After fixing, briefly summarize what you changed and why. If you skipped any flagged issues, explain your reasoning.
