---
name: review-claude
description: Run a Claude code review. In Claude, use focused subagents; in Codex, invoke Claude Code from the command line.
allowed-tools:
  - Agent
  - Task
  - Read
  - Edit
  - Bash
  - Grep
  - Glob
---

# Review with Claude

Run a Claude review. The implementation depends on which agent is executing
this skill:

- **Claude runtime:** launch focused review subagents in parallel.
- **Codex runtime:** invoke the Claude CLI non-interactively.

## Usage

- `/review-claude` or `$review-claude` - run review and display output
  (pass-through mode)
- `/review-claude collaborative` or `$review-claude collaborative` - run
  review, then discuss findings
- `/review-claude fix` or `$review-claude fix` - run review, then fix issues
  autonomously
- `/review-claude base main` or `$review-claude base main` - review changes
  against a base branch
- `/review-claude mini` or `$review-claude mini` - run a single-pass Claude
  review

Modes can be combined: `/review-claude mini fix base main`.

## Execution

**Parse arguments from:** `$ARGUMENTS` in Claude, or the user's prompt after
`$review-claude` in Codex.

**Determine mode:**

- If arguments contain "mini" → mini mode, remove it from args
- If arguments contain "fix" → fix mode, remove it from args
- If arguments contain "collaborative" → collaborative mode, remove it from args
- If arguments contain "base <branch>" → base branch mode
- Default → pass-through mode

**Determine the diff command:**

- Default: `git diff HEAD` (uncommitted changes)
- With base branch: `git diff <branch>...HEAD`

### Step 1: Gather context

Before launching agents, run the diff command yourself and capture the output. You'll pass the full diff text to each agent in its prompt so they don't all independently run git commands.

Also read the project's `CLAUDE.md` files — check the project root and `~/.claude/CLAUDE.md` (global). Follow any file links or references found in them. You'll include the relevant project conventions in each agent's prompt.

### Step 2: Launch six review agents in parallel

When running from Claude: Use the **Agent** tool to launch **all six agents concurrently** in a single message. This ensures targeted reviews and the parallelism maintains speed.

When running from Codex: use the global script
`~/Documents/dotfiles/run-claude-reviews.sh`, passing `--base <branch>` when a
base branch is specified and `--mini` in mini mode. The script shells out to
Claude in parallel for the six review areas below and handles streaming logs,
timeouts, and output aggregation.

Pass each agent the full diff and relevant project conventions so it has complete context. Each agent should also explore the surrounding codebase as needed to understand context for the changes.

Each agent must **not make any changes** — review only. Issues may be ignored inside test files. When in doubt about whether something is an issue, the agent should mention it.

#### Agent 1: Correctness

Bug hunt. Focus on things that are **wrong or will break**:

- Logic errors, off-by-ones, incorrect edge cases, race conditions.
- Null/undefined access that will throw at runtime.
- Incorrect assumptions about data shapes, API contracts, or return values.
- State mutations in the wrong order or at the wrong time.
- Missing error handling at system boundaries (external APIs, user input, file I/O).

Do not flag style issues, naming, or "could be cleaner" — that's another agent's job. Do not flag security issues — that's another agent's job.

#### Agent 2: Code Quality

Review for craftsmanship and maintainability:

- Redundant state: state that duplicates existing state, cached values that could be derived, observers/effects that could be direct calls.
- Parameter sprawl: adding new parameters instead of generalizing or restructuring.
- Copy-paste with slight variation: near-duplicate blocks that should be unified.
- Leaky abstractions: exposing internal details or breaking existing abstraction boundaries.
- Stringly-typed code: raw strings where constants, enums, or branded types already exist.
- Unnecessary comments: comments explaining WHAT (well-named identifiers already do that), narrating the change, or referencing the task/caller. Keep only non-obvious WHY (hidden constraints, subtle invariants, workarounds).
- Unnecessary JSX nesting: wrapper elements that add no layout value.
- Clarity over brevity: nested ternaries should be if/else or switch. Flag overly clever one-liners.

#### Agent 3: Codebase Standards

Review for adherence to the project's established conventions. The agent receives the project's CLAUDE.md content and should flag deviations:

- **Types:**
  - Flag any type casts. These require at minimum a comment explaining them, but flag them for human review regardless.
  - Flag weak typings, such as `Record<string, string>` or similar.

- **Fail fast, fail loud:**
  - Carefully review what the code does when expected information is missing.
  - Flag patterns like `foo?.bar ?? ""` — these hide missing data.
  - Flag error catching without `recordError`-ing or re-throwing.

- **Halfway refactoring:**
  - Flag patterns like `NEW_VAR = x; OLD_VAR = NEW_VAR; // For backwards compatibility`.
  - Flag re-exporting variables/functions that have moved instead of updating consumers.
  - Exception: server/client API boundaries.

- Any other project-specific conventions from CLAUDE.md (import ordering, naming, component patterns, etc.).

#### Agent 4: Code Reuse

Search the codebase for existing code that the changes should be using instead of writing new:

- Search for existing utilities and helpers that could replace newly written code. Look for similar patterns elsewhere in the codebase — common locations are utility directories, shared modules, and files adjacent to the changed ones.
- Flag new functions that duplicate existing functionality. Suggest the existing function to use instead.
- Flag inline logic that could use an existing utility — hand-rolled string manipulation, manual path handling, custom environment checks, ad-hoc type guards.

This agent should spend most of its time **exploring the codebase**, not just reading the diff.

#### Agent 5: Security

Focused security review. Only flag issues where you're >80% confident of actual exploitability — minimize false positives. Trace data flow from user inputs to sensitive operations.

- **Injection:** SQL injection, command injection in system calls/subprocesses, template injection, NoSQL injection, path traversal in file operations.
- **Auth & authorization:** Authentication bypass logic, privilege escalation paths, authorization logic bypasses, session management flaws, JWT vulnerabilities.
- **Secrets & crypto:** Hardcoded API keys/passwords/tokens, weak cryptographic algorithms, improper key storage, certificate validation bypasses.
- **Code execution:** Remote code execution via deserialization (pickle, YAML, etc.), eval injection, XSS (reflected, stored, DOM-based) — but note that React/Angular are generally safe unless using `dangerouslySetInnerHTML` or similar.
- **Data exposure:** Sensitive data in logs (secrets, PII — not URLs), API endpoint data leakage, debug information exposure in production.

**Exclusions:** Do not flag denial of service, rate limiting, resource exhaustion, theoretical race conditions, outdated dependencies, or missing hardening measures. Environment variables and CLI flags are trusted. Client-side JS/TS does not need auth checks (that's the server's job).

#### Agent 6: Efficiency

Review for performance and resource usage:

- Unnecessary work: redundant computations, repeated file reads, duplicate network/API calls, N+1 patterns.
- Missed concurrency: independent operations run sequentially when they could run in parallel.
- Hot-path bloat: new blocking work added to startup or per-request/per-render hot paths.
- Recurring no-op updates: state/store updates that fire unconditionally — add change-detection guards. Also: if a wrapper function takes an updater/reducer callback, verify it honors same-reference returns (or whatever the "no change" signal is).
- Unnecessary existence checks: pre-checking file/resource existence before operating (TOCTOU anti-pattern) — operate directly and handle the error.
- Memory: unbounded data structures, missing cleanup, event listener leaks.
- Overly broad operations: reading entire files/collections when only a portion is needed.

### Step 3: Aggregate findings

Wait for all six agents to complete. Collect their outputs and present the results.

### Output handling

- **Pass-through mode:** Display each agent's findings under its category heading. Do not add commentary.

- **Collaborative mode:** Display findings, then provide your own synthesis. Deduplicate across agents (if correctness and efficiency both flag the same issue, that's one issue — note the agreement). Add your own judgment on each finding.

- **Fix mode:** Synthesize and deduplicate findings first, then fix issues autonomously. Use your own judgment on what's worth fixing.

  **One warning:** Your judgment tends to be too lenient on type system issues, fail-fast violations, and backwards-compatibility hacks. When any agent flags these, lean toward fixing them rather than dismissing them.

  After fixing, briefly summarize what you changed and why. If you skipped any flagged issues, explain your reasoning.
