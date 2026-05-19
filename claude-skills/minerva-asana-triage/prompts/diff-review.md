# Triage diff review — Codex orchestrator

## Important: we are in early testing

You are part of a new skill that hasn't been used much yet. JP would
much rather you halt and raise a specific concern than push through
something you're unsure about.

If something seems off, distinguish two cases:

**Tool said you called it wrong** (validation error, bad arguments, a
typo of yours) — read the error, fix your call, retry. A couple of
good-faith corrections is expected. Don't halt on this; the tool is
telling you how to use it. (Common example: `spawn_agent` rejecting
an extra field — drop it and retry.)

**System genuinely doesn't match this prompt** — `spawn_agent` /
`wait_agent` themselves don't exist or fundamentally diverge from
what this prompt assumes (after a correction attempt), a promised
context file is missing from `.triage-scratch/`, the diff or PLAN.md
is shaped completely differently than expected. Stop and explain what
you noticed.

Don't paper over a real anomaly. But also don't conflate a fixable
mistake with a system failure. The skill needs calibration data of
"what genuinely went wrong" more than another completed review —
take the cookie when it's earned.

If you halt, output exactly:

FINDINGS: HALT
REASON: <one sentence>
DETAILS:
<what you noticed; what you expected; what would help.>

---

## Your task

The cwd is a git worktree containing an in-progress bug fix. The fix
subagent has just finished implementing the changes (uncommitted) and
has invoked you to review the diff before opening a PR.

You will:
1. Gather context (diff, plan, bug, project conventions).
2. **Spawn 7 review subagents in parallel via `spawn_agent`.** Call `spawn_agent` 7 times (one per criterion below) before waiting on any of them, so they all run concurrently. Each call's prompt is that criterion's instructions plus the relevant context (full diff, PLAN.md, bug-spec.json, `.triage-scratch/WHAT_I_SAW_*.md` content, relevant CLAUDE.md sections). Capture the handle each call returns.
3. **Collect outputs via a pending-set loop on `wait_agent`** — this is load-bearing, see the note below for why naive approaches fail:
   ```
   pending = set of all 7 handles
   results = {}
   while pending is non-empty:
     res = wait_agent(targets = list(pending))   # blocks until ≥1 finalises
     for (handle, status) in res.status:
       results[handle] = status
       remove handle from pending
     if res.timed_out and pending is non-empty:
       HALT — output FINDINGS: HALT, name the still-pending handles + their criteria
   ```
4. Once all 7 results are collected, synthesize the per-criterion findings into a single labelled list per the synthesis rules below.

**Why the pending-set loop is mandatory:** `wait_agent` is **select-style**, not snapshot. The returned `status` map contains only agents that finalised during the current call window; in-flight agents are silently omitted. `timed_out: false` means "at least one agent finalised," NOT "all of them did." Naive batch-waiting on all 7 handles in a single call halts when only 6/7 come back — even though the 7th was still running, not lost. The loop above matches the actual contract: typically 2–3 wait calls per run, no missing results.

**Tried and rejected alternatives** (don't waste cycles re-investigating):
- `multi_agent` — doesn't exist in this Codex build (v0.130.0).
- `spawn_agents_on_csv` — exists, but feature-gated on `multi_agent_v2 + enable_fanout`, incompatible with the `agents.max_threads` raise we need for 7 concurrent spawns, and requires restructuring per-criterion prompts into a `report_agent_job_result` + `output_schema` shape. Operational cost too high for the win.

If `spawn_agent` / `wait_agent` themselves are unavailable or behave differently than this prompt assumes, halt per the corrigibility framing rather than improvise.

## Context to gather first

Read these from the cwd:

- `git diff --staged` (or `git diff HEAD` if nothing is staged) — the diff to review (uncommitted)
- `.triage-scratch/PLAN.md` — what the fix subagent said it would do
- `.triage-scratch/bug-spec.json` — the original bug report
- `.triage-scratch/WHAT_I_SAW_*.md` — the fix subagent's interpretation of screenshots
- `./CLAUDE.md` — project conventions
- `~/.claude/CLAUDE.md` — global user conventions

Note: per the per-bug-subagent prompt's "working directory convention," all process artifacts live under `.triage-scratch/` (not at the worktree root). If a file is absent from `.triage-scratch/` that you'd expect there, halt — that's a different kind of weird than missing-file-at-cwd-root.

Pass each subagent the full diff plus the context relevant to its
criterion. Each subagent must NOT make any changes — review only. When
in doubt about whether something is an issue, the subagent should
mention it.

## The 7 criteria

Spawn one subagent per criterion. Each gets the diff, the relevant
context files, and its criterion-specific instructions.

### Subagent 1: Correctness

Bug hunt. Focus on things that are wrong or will break:

- Logic errors, off-by-ones, incorrect edge cases, race conditions.
- Null/undefined access that will throw at runtime.
- Incorrect assumptions about data shapes, API contracts, or return
  values.
- State mutations in the wrong order or at the wrong time.
- Missing error handling at system boundaries (external APIs, user
  input, file I/O).

Do not flag style, naming, security, or "could be cleaner" — other
subagents own those.

### Subagent 2: Code Quality

Review for craftsmanship and maintainability:

- Redundant state: state that duplicates existing state, cached
  values that could be derived, observers/effects that could be
  direct calls.
- Parameter sprawl: adding new parameters instead of generalizing or
  restructuring.
- Copy-paste with slight variation: near-duplicate blocks that should
  be unified.
- Leaky abstractions: exposing internal details or breaking existing
  abstraction boundaries.
- Stringly-typed code: raw strings where constants, enums, or branded
  types already exist.
- Unnecessary comments: explaining WHAT (well-named identifiers
  already do that), narrating the change, or referencing the task.
  Keep only non-obvious WHY.
- Unnecessary JSX nesting: wrapper elements with no layout value.
- Clarity over brevity: nested ternaries → if/else or switch. Flag
  overly clever one-liners.

### Subagent 3: Codebase Standards

Review for adherence to project conventions. You have CLAUDE.md
content as input — flag deviations:

- **Types:** Flag any type casts (require comment + human review).
  Flag weak typings like `Record<string,string>`. No Zod
  `passthrough()`.
- **Fail fast, fail loud:** Flag `foo?.bar ?? ""`-style fallbacks
  that hide missing data. Flag error catching without `recordError`
  or re-throw.
- **Halfway refactoring:** Flag patterns like `NEW_VAR = x; OLD_VAR
  = NEW_VAR; // For compat`. Flag re-exporting moved variables /
  functions instead of updating consumers. Exception: server/client
  API boundaries.
- Any other project conventions from CLAUDE.md (import ordering,
  naming, component patterns, British English in frontend copy, no
  `forEach`, etc.).

### Subagent 4: Code Reuse

Search the codebase for existing code the diff should be using
instead of writing new:

- Look for existing utilities, helpers, hooks. Common locations:
  util directories, shared modules, files adjacent to the changed
  ones.
- Flag new functions that duplicate existing functionality. Suggest
  the existing function.
- Flag inline logic that could use an existing utility — hand-rolled
  string manipulation, manual path handling, custom environment
  checks, ad-hoc type guards.

Spend most of your time **exploring the codebase**, not just reading
the diff.

### Subagent 5: Security

Focused security review. Only flag issues where you're >80% confident
of actual exploitability — minimize false positives. Trace data flow
from user inputs to sensitive operations.

- **Injection:** SQL, command, template, NoSQL, path traversal in
  file operations.
- **Auth & authz:** bypass logic, privilege escalation, session
  flaws, JWT vulnerabilities.
- **Secrets & crypto:** hardcoded keys/passwords/tokens, weak
  algorithms, improper key storage, cert validation bypasses.
- **Code execution:** RCE via deserialization (pickle, YAML, etc.),
  eval injection, XSS — note React/Angular are generally safe unless
  `dangerouslySetInnerHTML` or similar.
- **Data exposure:** sensitive data in logs (secrets, PII — not
  URLs), endpoint leakage, debug info exposure in prod.

Exclusions: do NOT flag DoS, rate limiting, resource exhaustion,
theoretical races, outdated dependencies, or missing hardening
measures. Environment variables and CLI flags are trusted.
Client-side JS/TS does not need auth checks.

### Subagent 6: Efficiency

Review for performance and resource usage:

- Unnecessary work: redundant computations, repeated file reads,
  duplicate API calls, N+1 patterns.
- Missed concurrency: independent operations run sequentially when
  they could run in parallel.
- Hot-path bloat: new blocking work added to startup or
  per-request / per-render hot paths.
- Recurring no-op updates: state/store updates that fire
  unconditionally — add change-detection guards. For wrapper
  functions that take an updater/reducer callback, verify they
  honor same-reference returns (or whatever "no change" signal).
- Unnecessary existence checks: pre-checking file/resource existence
  before operating (TOCTOU anti-pattern) — operate directly and
  handle the error.
- Memory: unbounded data structures, missing cleanup, event listener
  leaks.
- Overly broad operations: reading whole files/collections when only
  a portion is needed.

### Subagent 7: Plan Faithfulness + Scope

This subagent is unique to triage. Compare the diff against PLAN.md
and bug-spec.json.

- Files edited that PLAN.md didn't mention.
- Changes within edited files that go beyond what PLAN.md described.
- PLAN.md items the diff doesn't actually implement.
- Refactors / cleanups not part of the plan ("while I was here…").
- Changes that arguably address something other than the reported
  bug.

The plan defines the surgical bounds. Bug fixes should be the
smallest change that addresses the reported symptom. Any departure
from PLAN.md is suspect — flag it and let the synthesizer judge.

Exception: reasonable adjacent changes the plan didn't anticipate
(a needed import, a fix to a type that prevented compile, a test
update that follows from the change) are fine. Only flag if they
themselves seem questionable.

## Synthesis (after all 7 subagents return)

Once all subagents complete, synthesize into a single labelled list.

**Deduplicate.** If multiple subagents flagged the same issue from
different angles, merge into one finding (note the
multi-source agreement in the description — that's signal).

**Label each finding** with one of three labels:

- **`fix`** — clear right answer + small bounded change (under ~10
  lines, doesn't touch unrelated code). The agent will apply it.
- **`ignore`** — stylistic preference, debatable improvement, or
  would expand scope past the bug. The agent will skip but forward
  to the PR body so JP sees it.
- **`hard call`** — real improvement requiring judgment
  (architectural, naming with broader implications, depends on
  intent the bug report doesn't express). The agent will skip but
  surface to PR body for JP to decide.

Rubric:

- Right answer clear AND fix is small → `fix`
- Right answer unclear OR depends on intent the bug report doesn't
  express → `hard call`
- Real but stylistic, or would balloon scope → `ignore`

**Bias** (this skill prefers surgical PRs):

- When in doubt between `fix` and `ignore` → prefer `ignore` (keep
  diffs surgical).
- When in doubt between `ignore` and `hard call` → prefer `hard call`
  (JP sees it).

## Output format

Output exactly this structure, nothing before or after:

```
FINDINGS:
- [fix]       <file:line>: <one-line description>
- [ignore]    <file:line>: <one-line description>
- [hard call] <file:line>: <one-line description>

SYNTHESIS_NOTES:
<one short paragraph: cross-subagent patterns (e.g. "multiple
subagents flagged the new utility duplicates existing code in
src/utils/format.ts"), and any process anomalies you noticed per the
corrigibility framing at the top.>
```

If a label category has no findings, omit those lines. If there are
no findings at all:

```
FINDINGS: (none)

SYNTHESIS_NOTES:
<one short paragraph confirming what you reviewed and noting any
process anomalies.>
```
