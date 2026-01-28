---
name: review-codex
description: Run a code review using OpenAI Codex CLI (GPT-5.2)
allowed-tools:
  - Bash
  - Read
  - Edit
  - Grep
  - Glob
---

# Review with Codex

This skill runs a two-step code review using the Codex CLI (GPT-5.2):
1. General review of changes
2. Follow-up with specific review criteria

## Usage

- `/review-codex` - Run review and display output (pass-through mode)
- `/review-codex collaborative` - Run review, then Claude discusses findings
- `/review-codex fix` - Run review, then Claude fixes issues autonomously
- `/review-codex base main` - Review changes against a base branch

Modes can be combined: `/review-codex fix base main`

## Execution

**Parse arguments from:** $ARGUMENTS

**Determine mode:**
- If arguments contain "fix" → fix mode, remove it from args
- If arguments contain "collaborative" → collaborative mode, remove it from args
- If arguments contain "base <branch>" → use `--base <branch>` instead of `--uncommitted`
- Default → pass-through mode with `--uncommitted`

### Step 1: General Review

Run the initial review:

```bash
codex review [--uncommitted OR --base <branch>]
```

### Step 2: Follow-up with Specific Criteria

Resume the session with custom review instructions:

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

- **Pass-through mode:** Display both Codex outputs directly. Do not add commentary, analysis, or suggestions. Just show what Codex said.

- **Collaborative mode:** After showing both Codex outputs, provide your own analysis. Note agreements, disagreements, or additional concerns Codex may have missed. Offer to help address any issues found.

- **Fix mode:** After reviewing the Codex output, make executive decisions and fix issues autonomously. Use your own judgment on what's worth fixing.

  **One warning:** Your judgment tends to be too lenient on type system issues, fail-fast violations, and backwards-compatibility hacks. When Codex flags these, lean toward fixing them rather than dismissing them.

  After fixing, briefly summarize what you changed and why. If you skipped any flagged issues, explain your reasoning.
