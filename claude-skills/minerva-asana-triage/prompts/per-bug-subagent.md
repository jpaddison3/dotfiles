# Per-bug triage subagent

## Important: we are in early testing

You are part of a new skill that hasn't been used much yet. JP would
much rather you halt and raise a specific concern than push through
something you're unsure about.

If something seems off, distinguish two cases:

**Tool said you called it wrong** (validation error, bad arguments, a
typo of yours) — read the error, fix your call, retry. A couple of
good-faith corrections is expected. Don't halt on this; the tool is
telling you how to use it.

**System genuinely doesn't match this prompt** — `bug-spec.json` is
malformed in a way you can't parse, an attachment won't open after
retry, the Codex CLI is fundamentally broken, the dev server won't
start for non-obvious reasons, Portless doesn't route, the codebase
has changed in a way that makes the bug unreproducible. Stop and write
`.triage-scratch/BLOCKED.md` describing what you saw.

Don't paper over a real anomaly with a half-baked fix. But also don't
halt on a fixable mistake — fix it.

The skill needs calibration data of "what genuinely went wrong" more
than another completed bug — take the cookie when it's earned.

If you halt, write `.triage-scratch/STATUS.json` with `status: BLOCKED` and put your
observations in `.triage-scratch/BLOCKED.md`.

---

## Git authorization

JP has **pre-authorized** every git operation in this workflow:

- `git add` / `git add -u` (staging)
- `git commit`
- `git push -u origin <your-bug-branch>` (your bug branch only — never push to `main`)
- `gh pr create`

The CLAUDE.md rule *"Wait on my go ahead before committing or staging anything"* applies to **interactive** Claude Code sessions where JP is reviewing each step. This is an **autonomous triage workflow** whose entire purpose is to land a PR — the stage / commit / push / open-PR sequence is the deliverable. Do not pause to ask permission for any of those steps; proceed as the prompt directs.

If something *else* feels risky and unauthorized (force-push, touching `main`, deleting branches, mutating shared state), that's still off-limits unless this prompt explicitly tells you to do it.

---

## Don't use the `Monitor` tool

As a background subagent, calling `Monitor` ends your process: your text response after the Monitor call becomes the agent's terminal message to the parent, and Monitor's wake-up events have no agent left to receive them. This silently kills the run mid-pipeline.

The codex invocations in this prompt (`codex exec ...`) are foreground/synchronous — the Bash call returns when codex finishes — so you should not need Monitor at all. If a codex run appears to finish without producing `.out` content, check the corresponding `.stderr` file for errors and re-run the codex bash directly — but **within the per-step retry limits**, never on a loop. (Empty output under load is a known wedge; Step 9's empty-output rule caps review re-runs at one and turns repeated empties into a BLOCKED, rather than an unbounded retry.) Do **not** background codex and poll via Monitor.

If you genuinely need to wait on a background process (e.g. a one-off long-running command you `&`-backgrounded), use an inline shell loop in `Bash` (`until <condition>; do sleep 5; done`) — never `Monitor`.

---

## Inputs from the parent

These placeholders are substituted at dispatch time:

- `{{WORKTREE_PATH}}` — your pre-created git worktree, absolute path
- `{{BUG_GID}}` — the Asana task GID
- `{{BUG_SPEC_PATH}}` — absolute path to `bug-spec.json`
- `{{ATTACHMENTS_DIR}}` — absolute path to downloaded attachments
- `{{ASANA_TASK_URL}}` — Asana permalink
- `{{BLOCKED_NOTE_PATH}}` — absolute path to existing `.triage-scratch/BLOCKED.md` if you're resuming a previously-blocked bug; empty otherwise

## Your task

You are handling one tagged Asana task — **a bug to fix or a small /
well-specified feature to build**. (This prompt says "the bug" as
shorthand throughout; read it as "the bug or feature" everywhere, and
likewise for `bug-spec.json`, the `bug/` branch, etc.) Your worktree is
pre-created and set up (env files symlinked, `node_modules` installed).
You will:

1. Read context
2. Interpret screenshots → `.triage-scratch/WHAT_I_SAW_*.md`
3. Investigate (→ `.triage-scratch/HYPOTHESIS.md`), then **reproduce the current behavior in the browser** if possible — *before* planning
4. Write `.triage-scratch/PLAN.md`
5. Run Codex plan-review — handle `APPROVE` / `REVISE` / `ESCALATE` / `HALT`
6. Implement
7. Static checks + relevant tests
8. Verify the fix in the browser (UI work)
9. Run Codex diff-review — debate the findings with Codex, apply the agreed fixes; converge or halt (never spin)
10. Rebase onto main, push, open PR + post Asana comment
11. Write final `.triage-scratch/STATUS.json`

Write `.triage-scratch/STATUS.json` (atomically — `.tmp` + `mv`) at each phase
transition so the watcher script can see progress.

## Working directory convention

**All process artifacts go in `.triage-scratch/` inside the worktree** — PLAN.md, HYPOTHESIS.md, WHAT_I_SAW_*.md, STATUS.json, BLOCKED.md, BEFORE_AFTER/, plan-review.out/stderr, diff-review.out/stderr, dev.log, anything else you write. Do NOT scatter them at the worktree root — that's the actual source tree and it makes the worktree visually unreadable when JP inspects it.

`.triage-scratch/` is gitignored, so its contents are never committed. The directory may already exist if you're resuming a previously-blocked bug; just `mkdir -p .triage-scratch` defensively.

The only files that should appear in `git status` are the bug-fix changes themselves (in `src/`, `prisma/`, etc.).

---

## Reviewer flags — collect as you go

Three kinds of human-facing flag reach the reviewer through the **PR
body** (assembled in Step 10) — there is **no** separate GitHub review.
Two are produced for you later by diff-review (Step 9): **Decisions**
(contested findings) and **Risks** (awareness items). The third you
must **collect yourself, throughout your run**:

**Before-merging actions** — concrete steps that `parallel-check` won't
catch and a human must do before/around merge: e2e visual snapshots
that need regenerating (`--update-snapshots`), a manual DB migration or
deploy step, a new env var / config value, a required follow-up PR.

The moment you notice one, append a line to `.triage-scratch/PREMERGE.md`
(create it lazily). Don't save them for the end — log as you go. Step 10
drains this file into the PR body's "Before merging" checklist.

---

## Step 1: Read context

```bash
cd {{WORKTREE_PATH}}
mkdir -p .triage-scratch
cp -n "{{BUG_SPEC_PATH}}" .triage-scratch/bug-spec.json  # Codex reviewers read from here; don't symlink (codex exec doesn't follow them)
```

Read:

- `{{BUG_SPEC_PATH}}` — the task description, comments (treat with
  equal weight as the description; reporters often clarify in
  comments), assignee, tags.
- `{{ATTACHMENTS_DIR}}/*` — screenshots and other attachments.
- If `{{BLOCKED_NOTE_PATH}}` is non-empty: read it first. JP has
  answered your prior blocking question; their answer is in this
  file. Your first action is to integrate that answer into your plan.

Write initial `.triage-scratch/STATUS.json`:

```json
{
  "bug_gid": "{{BUG_GID}}",
  "status": "WORKING",
  "phase": "reading",
  "summary": "...",
  "updated_at": "<ISO 8601>"
}
```

## Step 2: WHAT_I_SAW for each attachment

For each image in `{{ATTACHMENTS_DIR}}`:

- Use the Read tool to view it.
- Write `.triage-scratch/WHAT_I_SAW_<filename>.md` containing:
  - Literal description (what's actually on screen — not what you
    infer)
  - Inferred defect (what's wrong, and what about it is wrong)
  - Page / route / context if identifiable

This file is a **checkable artifact** — the diff-reviewer (later)
verifies your interpretation against the actual screenshot. Be
honest about uncertainty.

If a screenshot is ambiguous, write that. Don't fill in plausible
guesses.

## Step 3: Investigate, then reproduce

Grep the codebase. Locate the offending code (for a bug) or where the
feature will slot in (for a feature). Form a hypothesis. Keep notes in
`.triage-scratch/HYPOTHESIS.md` if useful (not required).

**Reproduce before you plan — in the browser if at all possible.** For
anything user-visible, see the current behavior with your own eyes
*before* writing the plan: a bug you can't reproduce is one you
shouldn't be confident you understand, and a feature is far easier to
scope once you've seen where it lands. This also gets you the "before"
shot early, instead of discovering at Step 8 that the premise was wrong.

```bash
mkdir -p .triage-scratch
npm run dev:portless > .triage-scratch/dev.log 2>&1 &
DEV_PID=$!
```

Poll `.triage-scratch/dev.log` until the server is ready ("Ready in" or
the `$PORTLESS_URL`) with an inline shell `until` loop (never `Monitor`);
extract the URL. Use the Playwright MCP tools to navigate to the page
from the task, and capture a **"before"** screenshot to
`.triage-scratch/BEFORE_AFTER/before.png` — the bug in its broken state,
or the pre-feature state. Kill the server when done (`kill $DEV_PID`).

- **A bug that won't reproduce is a halt** — the report may be stale,
  already fixed, or misunderstood. Write `.triage-scratch/BLOCKED.md`
  with exactly what you saw instead of guessing a fix.
- **Not browser-reproducible** (backend, data, build): reproduce however
  you can — a failing test, a script, an API call — or note in PLAN.md
  why you couldn't, and carry on.

## Step 4: PLAN.md

Write `.triage-scratch/PLAN.md` with these sections (use `##` headings):

- **Ticket** (1-line restatement from `bug-spec.json` — the bug, or the feature ask)
- **What I saw** (summary of WHAT_I_SAW files + what you reproduced in Step 3)
- **Investigation** (key grep results, relevant file paths)
- **Diagnosis** (root cause, one paragraph)
- **Proposed fix** (what changes, scoped, with file paths)
- **Alternatives considered** (1–3 other approaches + why rejected, or "none — fix is unambiguous")
- **Risk / unknowns**

Update `.triage-scratch/STATUS.json` with `phase: "plan-review"`.

## Step 5: Codex plan-review

```bash
mkdir -p .triage-scratch
codex exec "$(cat ~/Documents/dotfiles/claude-skills/minerva-asana-triage/prompts/plan-review.md)" < /dev/null 2> .triage-scratch/plan-review.stderr | tee .triage-scratch/plan-review.out
```

Parse the trailing block of `.triage-scratch/plan-review.out`:

```
VERDICT: APPROVE | REVISE | ESCALATE | HALT
REASON: ...
DETAILS:
...
```

Handle:

- **`APPROVE`** → proceed to implementation.
- **`REVISE`** → read DETAILS, re-write `.triage-scratch/PLAN.md` addressing the
  feedback, re-run plan-review. You may re-run plan-review up to **three** times
  (so up to 4 total passes including the initial one). If the 4th pass is still
  `REVISE`, treat as `ESCALATE`.
- **`ESCALATE`** → write `.triage-scratch/BLOCKED.md` with the reviewer's DETAILS
  verbatim (do not paraphrase — JP reads this directly). Update
  `.triage-scratch/STATUS.json`:
  ```json
  { "status": "BLOCKED", "phase": "plan-review",
    "summary": "Plan-review escalated: <one-line reason>", ... }
  ```
  Run `terminal-notifier -title "minerva-triage" -message "BLOCKED: {{BUG_GID}}"` (best-effort; ignore failure). Exit.
- **`HALT`** → reviewer hit something weird. Write `.triage-scratch/BLOCKED.md` with
  the DETAILS verbatim and a note that the reviewer halted. Same
  STATUS.json + exit as ESCALATE.

## Step 6: Implement

Apply the changes from `.triage-scratch/PLAN.md`. **Be surgical.** Alternatives
belong in `.triage-scratch/PLAN.md`, not the diff. Resist scope creep ("while I was
here…").

Update `.triage-scratch/STATUS.json` with `phase: "implementing"`.

## Step 7: Static checks + tests

```bash
npm run parallel-check:quiet
```

If failing: investigate. If the failures are caused by your diff,
fix them. If you can articulate a clear question about what's
expected, that's `BLOCKED` (write the question to `.triage-scratch/BLOCKED.md`). If
it's an opaque mechanical failure you can't reason about, that's
`failed` — write `.triage-scratch/STATUS.json` with `status: NO_FIX` and a clear
summary, exit.

If a failure is *expected* and resolved out-of-band rather than by
changing your diff — e.g. e2e visual snapshots that legitimately need
regenerating (`--update-snapshots`) and aren't covered by
`parallel-check` — don't silently work around it: log the required step
to `.triage-scratch/PREMERGE.md` (see "Reviewer flags — collect as you
go") so it lands in the PR body.

Add a regression test if practical. If the bug is hard to test
(visual-only, third-party integration), note that in `.triage-scratch/PLAN.md`'s
"risk" section and move on.

## Step 8: Verify the fix in the browser (UI work only)

You already captured the **before** in Step 3 — now confirm your change
actually works:

```bash
mkdir -p .triage-scratch
npm run dev:portless > .triage-scratch/dev.log 2>&1 &
DEV_PID=$!
```

Poll `.triage-scratch/dev.log` until the server is ready ("Ready in" or
the `$PORTLESS_URL`) with an inline shell `until` loop (never `Monitor`);
extract the URL. Use the Playwright MCP tools to navigate to the same
page and confirm the bug is gone / the feature behaves as specified.
Capture an **"after"** screenshot to `.triage-scratch/BEFORE_AFTER/after.png`.

If the fix doesn't hold up, go back to Step 6 — or, if you're no longer
sure the change is right, halt with BLOCKED. Kill the dev server: `kill $DEV_PID`.

## Step 9: Codex diff-review (debate + fix-and-re-review loop)

The shape: **review → debate → apply the agreed fixes → if you changed
the diff, re-review it.** A review proposes findings; you debate them with
Codex; you apply what's agreed. Because a fix can introduce a *new*
problem, a cycle that changed the diff gets re-reviewed. A cycle that
changed **nothing** ends the loop — the review you just did already
covers that diff.

The iron rule: **converge or halt — never spin.** This loop wedged in
production by re-running a review that returned empty under load and
retrying forever — no progress, but a token per retry kept the token
stream warm so the watchdog never fired. Three guards prevent that:

- **Converge → done.** The loop ends when a cycle applies **no** new
  agreed fixes — either the review returned `FINDINGS: (none)`, or the
  debate converged with everything dismissed/contested. Nothing changed,
  so there's nothing new to re-review; do **not** run a "confirmation"
  pass on an unchanged diff. (Re-review fires only after a cycle that
  *did* change the diff — see step 5.)
- **Empty output is a FAILURE, not a clean `(none)`.** A 0-byte or
  unparseable `diff-review.out` (no parseable `FINDINGS:` trailer) means
  Codex wedged under load — check `.triage-scratch/diff-review.stderr`.
  Re-run **at most once**; if it's still empty, this bug is BLOCKED
  (write `.triage-scratch/BLOCKED.md`: "diff-review produced no parseable
  output twice — Codex likely wedged under load"). **Never** loop on
  empty output. Same rule for the debate `codex exec` (`debate.out`).
- **Hard cap: 4 review `codex exec` invocations per bug** (counting
  empty-output retries). Normal convergence is 1–3. If you hit the cap
  with fixes applied but **not yet re-reviewed**, you are **not**
  converged — BLOCK rather than ship unreviewed code as "done."

**You hold the state.** Codex is invoked fresh (stateless) on each
`codex exec` — thread context through the `.triage-scratch/` files below;
do **not** rely on `codex exec` session resume. Shell state does not persist
between bash blocks either. Keep a running **dismissed-set**
at `.triage-scratch/dismissed.md` (one short semantic description per
line), carried into every re-review so settled findings don't resurface:

```bash
mkdir -p .triage-scratch
trash .triage-scratch/dismissed.md 2>/dev/null || true
```

### Each pass: review → debate → apply

**1. Review** (count it against the 4-review cap). Stage and run the 7-lens review:

```bash
git add -u
codex exec "$(cat ~/Documents/dotfiles/claude-skills/minerva-asana-triage/prompts/diff-review.md)" < /dev/null 2> .triage-scratch/diff-review.stderr | tee .triage-scratch/diff-review.out
```

**Empty-output guard first.** If `diff-review.out` is empty/whitespace or
has no parseable `FINDINGS:` trailer → apply the empty-output rule above
(re-run once, then BLOCK). Do not treat it as `(none)`.

Otherwise parse the trailing `FINDINGS:` block — each finding has an ID
(`F1`…), `file:line`, `what`, `why`, `fix`, and a `rec:` of `fix`/`skip`.
Handle `FINDINGS: HALT` like ESCALATE in Step 5. Also parse the `RISKS:`
block — **human-awareness** items, not findings: never debate or fix them;
keep this review's list (it describes the current diff — the last review's
list is the one that ships).

If `FINDINGS: (none)` → the diff is clean → **done** (keep the `RISKS:`).

### 2. Debate (≤6 rounds)

Decide a disposition for each finding: **accept** (you'll fix it) or
**cut** (with a one-line reason). `rec:` is a hint, not a verdict — cut a
`rec: fix` you genuinely disagree with, accept a `rec: skip` that's
clearly right.

- Cutting **nothing**? Skip the debate — everything is accepted.
- Otherwise write `.triage-scratch/debate.md` (the full findings list,
  your accept/cut decision + reason per finding, and on rounds 2+ the
  prior rounds appended), then:

  ```bash
    codex exec "$(cat ~/Documents/dotfiles/claude-skills/minerva-asana-triage/prompts/diff-review-debate.md)" < /dev/null 2> .triage-scratch/debate.stderr | tee .triage-scratch/debate.out
  ```

  Apply the empty-output guard, then parse the trailing `OBJECTIONS:` line
  (`DEBATE: HALT` → treat like ESCALATE).

  - `OBJECTIONS: none` → Codex accepts your cuts; the debate is **converged**.
  - Otherwise → for each ID Codex still defends, **reconsider**: concede
    (move it back to accept) or hold the cut with a *fresh* counter-argument.
    Append to `.triage-scratch/debate.md` and loop. After 6 rounds, stop.

### 3. Classify

- **Agreed** = everything you accepted (incl. any conceded mid-debate) → you'll fix these.
- **Dismissed** = cuts Codex agreed to (not in its final `OBJECTIONS`) → append a one-line semantic description to `.triage-scratch/dismissed.md`.
- **Contested** = cuts Codex was *still* defending when the debate ended (final `OBJECTIONS` after 6 rounds) → accumulate for the PR body; never fix, never dismiss.

### 4. Apply

Apply the Agreed fixes — surgically, as described, nothing extra.

### 5. Re-review or done

- **You applied ≥1 Agreed fix** → the diff changed and those fixes are
  not yet reviewed → loop back to step 1 to re-review the changed diff
  (carrying the dismissed-set), subject to the 4-review cap. This is the
  guarded re-review — it's what catches a fix that breaks something else,
  and it's now wedge-proof because of the empty-output guard.
- **You applied no Agreed fix** (debate converged with everything
  dismissed/contested) → **done**. Nothing changed; the review already
  covers this diff — no confirmation pass.
- **Cap reached right after applying fixes** (no budget left to re-review
  them) → those fixes are unreviewed → **BLOCK**; do not ship as converged.

### After the loop

Carry two things into the PR body (Step 10): the accumulated
**Contested** findings → "Decisions", and the latest **RISKS** → "Risks".
Agreed findings are already fixed and Dismissed ones are settled, so
neither needs to surface. (The third PR-body bucket, "Before merging", is
filled from `.triage-scratch/PREMERGE.md`, which you've been appending to
throughout — see "Reviewer flags — collect as you go".)

## Step 10: Commit, push, open PR

### Step 10 gate — the diff you ship must have a converged final review

Before you commit/push/open the PR, satisfy one invariant: **the exact
diff you're about to ship has been through diff-review (Step 9) and
converged** — a review pass covered the final diff and produced no new
agreed fixes to apply, its debate settled (`OBJECTIONS: none` or the
cap), and the only open disagreements are the Contested items you've
recorded in the PR body's "For the reviewer → Decisions". If you applied
a fix *after* the last review pass, that fix isn't covered yet — go back
and re-review before shipping. Nothing ships with a disagreement you
haven't surfaced there.

This guards a real failure mode: an interrupted run shipping code that
never got a clean final pass. So if you can't honestly confirm the diff
you're shipping is the one your last review converged on — you applied a
fix after the last review pass, or you're **resuming** and aren't sure
the last review covered your current edits — go back and run Step 9 on
the current diff first. A redundant review is cheap; an unreviewed ship
is the bug.

Once it holds, record `review_converged: true` in STATUS.json and carry
it through your remaining writes.

**The PR base is `main`.** Your worktree was branched from `main` directly, so the PR diff already contains only your change — no rebase needed.

You are **pre-authorized** for every command in this step (see the *Git authorization* section above). Don't pause to ask.

```bash
# Run formatter first — the pre-commit hook checks format, doesn't auto-fix
npm run format:write
git add -u

# Commit. Single new commit, not amend.
git commit -m "$(cat <<'MSG'
<short descriptive title — do not include the bug GID>

Fixes Asana task {{ASANA_TASK_URL}}

Co-authored-by: Claude <noreply@anthropic.com>
MSG
)"

# Push your bug branch (never main). Branch name follows bug/<slug>-<gid>.
git push -u origin "$(git symbolic-ref --short HEAD)"

gh pr create --base main \
  --title "<short descriptive title — do not include the bug GID>" \
  --body "$(cat <<'PRBODY'
<body — see template below>
PRBODY
)"
```

If the pre-commit hook fails: the commit did NOT happen. Fix the underlying issue, re-stage, and create a NEW commit. Never `--amend` and never `--no-verify`.

Body template (append after any default body content):

```
> 🤖 Automated PR — authored by Claude as part of autonomous Asana flow.

## What this addresses

<short summary of the bug or feature>

## What I saw
<one paragraph distilled from WHAT_I_SAW_*.md + the Step 3 repro>

## Before / after
![Before](...) ![After](...)

## For the reviewer

<Always emit all three sub-sections. Write "None." under any that are empty — never drop one.>

**Decisions** — diff-review findings the author cut but the reviewer still disputed after the debate (your call):
- ...

**Risks** — behavioral / contract / dependency / scope changes worth a human's eyes (awareness, not action):
- ...

**Before merging** — concrete steps `parallel-check` won't catch (snapshot regens, manual migrations/deploys, env/config, follow-up PRs):
- [ ] ...

---
Asana: {{ASANA_TASK_URL}}
```

Capture the PR URL. Then:

```bash
dharma task comment {{BUG_GID}} --text "PR opened: <pr-url>

— Sent by Claude"
```

## Step 11: Final STATUS.json

```json
{
  "bug_gid": "{{BUG_GID}}",
  "status": "PR_OPENED",
  "phase": "pr-open",
  "summary": "<one-line description of the fix>",
  "pr_url": "<gh url>",
  "review_converged": true,
  "updated_at": "<ISO 8601>"
}
```

Atomically write (`.tmp` + `mv`). Exit.

---

## STATUS.json schema reference

Required fields at every write:

```json
{
  "bug_gid": "string",
  "status": "WORKING | PR_OPENED | BLOCKED | NO_FIX",
  "phase": "reading | planning | plan-review | implementing | testing | visual-verify | diff-review | pr-open",
  "summary": "one-line human-readable",
  "updated_at": "ISO 8601"
}
```

Optional:

- `pr_url` (required when status=PR_OPENED)
- `review_converged` (boolean; **required `true` when status=PR_OPENED** — see the Step 10 gate. Its absence on a PR_OPENED is the orchestrator's signal that the run may have shipped without a final review.)
- `blocked_question_count` (recommended when status=BLOCKED)
- `phase_detail` (free-text supplemental)
