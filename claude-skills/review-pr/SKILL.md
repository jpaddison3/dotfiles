---
name: review-pr
description: Run parallel local + remote PR reviews, then synthesize all findings
allowed-tools:
  - Task
  - Read
  - Edit
  - Bash
  - Grep
  - Glob
---

# Review PR (Local + Remote)

This skill orchestrates the full review pipeline: local AI reviews (Claude + Codex) and remote GitHub PR reviews (Gemini, Copilot, humans) — all fetched in parallel, then synthesized.

## Usage

- `/review-pr` — auto-detect PR from current branch, full local + remote review
- `/review-pr <pr-url>` — specify PR explicitly
- `/review-pr fix` — same but fix issues found
- `/review-pr base develop` — override base branch (defaults to `main`)

Modes can be combined: `/review-pr fix base develop`

## Execution

**Parse arguments from:** $ARGUMENTS

**Determine mode:**
- If arguments contain "fix" → fix mode, remove it from args
- If arguments contain "passthrough" → passthrough mode, remove it from args
- If arguments contain "base <branch>" → base branch mode
- Extract PR URL if present (anything starting with `https://` or matching `owner/repo number`)
- Default mode is **collaborative**

### Step 1: Gather review procedures and launch everything in parallel

Read `claude-skills/review-multi/SKILL.md` to understand how to launch the Claude and Codex reviews. It in turn references `claude-skills/review-claude/SKILL.md` and `claude-skills/review-codex/SKILL.md`.

Then **launch all three processes in parallel** (single message, three tool calls):

1. **Claude review** — per review-multi's instructions for the Claude reviewer, in passthrough mode, with base branch if specified. Use `subagent_type: "general-purpose"` (do not specify a model).
2. **Codex review** — per review-multi's instructions for the Codex reviewer, in passthrough mode, with base branch if specified.
3. **Remote review fetch** — run:
   ```
   ~/Documents/dotfiles/fetch-pr-reviews.py <pr-url-or-auto>
   ```
   If no PR URL was provided in arguments, just run `~/Documents/dotfiles/fetch-pr-reviews.py` with no args (it auto-detects from the current branch).

### Step 2: Evaluate remote review readiness

After the fetch completes, check `bot_status` in the output. Use your judgment:

- **Copilot hasn't reviewed and PR is < 10 min old:** Copilot typically finishes in under 10 min. Wait bit longer. After 10 minutes, go with what you have.
- **Gemini hasn't reviewed and PR is > 10 min old:** Gemini typically finishes in under 5 min. Consider a brief wait. After 10 minutes, go with what you have.
- **Both have reviewed**, or the PR is old enough that missing bots likely aren't coming: proceed.
- **In doubt:** Report what you see and ask the user.

### Step 3: Synthesize all findings

Read all outputs from the three parallel processes. Deduplicate findings across sources — if Claude, Codex, and Gemini all flag the same issue, that's one issue (note the agreement). Assign each unique issue a canonical number.

### Step 4: Product research notes

Check if this repo is one of the following product repos (match against the `origin` remote URL):
- `eighty-thousand-hours/minerva` (may be checked out under various directory names like `minerva`, `minerva-claude1`, etc.)
- `80000hours/job-board`

If it is **not** one of these repos, skip this step entirely.

If it **is** a product repo, write a descriptive PR summary for the product research system. This is a **factual, descriptive** document — not a review. Do not include review opinions, recommendations, or code quality judgments. Focus on what changed and its product implications.

1. Write a file at `notes/YYYY-MM-DD-pr-NNN-slug.md` (in the current repo's `notes/` directory) using this template:

   ```markdown
   ---
   date: YYYY-MM-DD
   tags: [pr-summary, PRODUCT-AREA]
   source: pr-summary
   status: raw
   pr: NUMBER
   author: GITHUB-USERNAME
   ---

   # PR #NUMBER: TITLE

   ## What changed
   Brief summary of the diff — what was added/modified/removed.

   ## Why
   Motivation and context from the PR description and diff.

   ## Product area
   Which part of the product this touches (e.g. advisorbot, career-quiz, explore-jobs, job-board).

   ## User-facing changes
   Any behavior changes a user would notice. "None" is fine.

   ## Links
   - PR: URL
   ```

2. Copy it to the product research folder:
   ```
   ~/Documents/dotfiles/copy-to-research.sh notes/YYYY-MM-DD-pr-NNN-slug.md
   ```

### Output handling

- **Collaborative mode (default):** Use the format specified below. Do **not** make fixes yourself.

- **Pass-through mode:** Display all review outputs and remote data directly. Do not add commentary.

- **Fix mode:** Use the collaborative format below first, then fix issues autonomously.

  **One warning:** Your judgment tends to be too lenient on type system issues, fail-fast violations, and backwards-compatibility hacks. When any reviewer flags these, lean toward fixing them rather than dismissing them.

  After fixing, briefly summarize what you changed and why. If you skipped any flagged issues, explain your reasoning.

### Collaborative output format

Structure your output exactly like this:

```
## PR Review: <title>

(Summary)

## Issues

<Start with a numbered list — one line per issue with its number, the terse description, and your recommendation.>

Then move onto more detailed explations of each issue.

**1. <One-line description of the issue with enough context to understand it> (<your recommendation: should fix / consider / ignore>)**

<Paragraph(s) explaining the issue in detail. Include file paths and line numbers where relevant.
State which reviewers flagged this (e.g. "Flagged by: Gemini, Copilot").
Give your own opinion — do you agree? Is it important? Is it easy to fix?>

**2. <Next issue> (<recommendation>)**

<Detail...>

...
```

**Ordering:** Sort issues by your estimated importance, not by the priority labels reviewers assigned.

**Recommendations:** Each issue gets one of:
- **should fix** — real problem, worth addressing before merge, or alternatively, easy fix that is slighly net-beneficial
- **ignore** — not worth acting on (explain why)

**Context:** For each issue, state clearly what the comment is about and provide enough context that the reader can understand it without switching to GitHub. Include the relevant file path and line number.

**Your opinion matters:** Don't just relay what reviewers said. Add your own judgment — do you agree? Is this actually important? Is there a simpler fix than what was suggested?
