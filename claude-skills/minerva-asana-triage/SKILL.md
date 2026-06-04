---
name: minerva-asana-triage
description: Batch-process Asana bugs tagged jpa-bugfixes-today into PRs. Spawns per-bug subagents in parallel worktrees with Codex plan-review and diff-review.
allowed-tools:
  - Read
  - Write
  - Edit
  - Agent
  - Glob
  - Grep
---

# minerva-asana-triage

## Important: we are in early testing

You are running a new skill that hasn't been used much yet. JP would
much rather you halt and raise a specific concern than push through
something you're unsure about.

If something seems off — `dharma` returns an unexpected JSON shape,
state.json contains a phase not in the enum, a worktree already exists
at the target path on a different branch, `codex` CLI hangs, a per-bug
subagent returns malformed STATUS.json, anything — stop and tell JP
what you noticed. Don't paper over confusion.

The skill needs calibration data of "what went wrong" more than
another completed run. No penalty for halting — only thanks. Take the
cookie.

## Talking to JP

When talking to JP, lead with the bug title — he does not memorize
16-digit Asana GIDs. Last-4-digits in parens is fine for
disambiguation.

- Good: "Workers bug: dispatched"; "A/B tests bug (5092) halted"; "Double border (PR #712) merged"
- Bad: "1214783653255092: dispatched"; "Halt on 1214822328764375"

In code (state.json keys, script args, log files), GIDs stay
canonical. Human-facing prose only.

## What this skill does

Reads incomplete Asana tasks tagged `jpa-bugfixes-today`, dispatches
per-bug subagents in parallel git worktrees (siblings to `minerva/`).
Each subagent investigates, writes a plan, runs Codex plan-review,
implements, runs Codex diff-review, opens a PR (or writes
`BLOCKED.md` if it needs human input). You aggregate results into a
summary table at the end.

Design doc: `notes/minerva-asana-triage-plan.md`. State machine
diagram: `triage-state-machine.html`.

## Usage

```
/minerva-asana-triage [--tag <name>] [--max-parallel N] [--limit N] [--dry-run] [--retry-failed] [--retry-abandoned <gid>]
```

Defaults: `--tag jpa-bugfixes-today`, `--max-parallel 4`, `--limit` unlimited.

Parse arguments from `$ARGUMENTS`. Reject unknown flags rather than ignoring.

## Execution

### Step 1: Sanity check

Halt with a clear message if any of:

- `$ANTHROPIC_API_KEY` is set (would silently route to API billing instead of Max).
- `dharma`, `gh`, `git`, or `codex` not on PATH.
- `codex` resolves to a Superconductor-wrapped binary. Use:
  `CODEX_BIN="$(which -a codex | grep -v '/.superconductor/' | head -n1)"`
- You're inside a per-bug triage worktree (cwd matches `*/triage-bug-*`). The skill should be run from the main `minerva/` checkout or any SC worktree of it, not from a bug worktree.

### Step 2: Locate canonical paths

Resolve once. Note: **state lives in the canonical minerva**, but **scripts live in the current worktree** (so the user's in-flight branch with new scripts is what runs).

```bash
MINERVA_ROOT="$(dirname "$(git rev-parse --git-common-dir)")"  # canonical, for state
WORKTREE_ROOT="$(git rev-parse --show-toplevel)"               # current, for scripts
TRIAGE_DIR="$MINERVA_ROOT/.triage"
STATE_FILE="$TRIAGE_DIR/state.json"
SPECS_DIR="$TRIAGE_DIR/specs"
SCRIPTS_DIR="$WORKTREE_ROOT/scripts"
mkdir -p "$SPECS_DIR"
```

All state.json and bug-spec reads/writes use the absolute `MINERVA_ROOT`-based paths regardless of cwd. Script invocations use `SCRIPTS_DIR`.

### Step 3: Run cleanup

```bash
"$SCRIPTS_DIR/triage-cleanup"
```

If the script doesn't exist (un-merged or wrong worktree), halt with a clear message — don't silently skip. Use the corrigibility framing.

**Ordering is load-bearing.** Cleanup runs *before* any `--retry-abandoned` / `--retry-failed` flips in step 5. Cleanup removes the worktree of an abandoned/failed bug while it's still at that terminal phase; the step-5 flip then transitions the state to `pending` and step-7 dispatch re-creates a fresh worktree. **Do not flip the state before running cleanup** — cleanup would see `pending` (skip), dispatch would reuse the existing (often borked) worktree, and the "retry" would replay the same conditions that caused the original failure.

### Step 4: Resolve tag and fetch tasks

```bash
tag_gid=$(dharma tag list --name "$tag_name" | jq -r '.[0].gid')
dharma task search --tag "$tag_gid" --completed=false \
  --fields name,notes,permalink_url,assignee.email,tags.name,custom_fields
```

If `$tag_gid` is empty or null, halt — tag was renamed/deleted.

**Naming note:** all shell variables in this skill use **lowercase**. `GID`, `UID`, `EGID`, `EUID` are special in zsh — writes to them call `setegid(2)` / `seteuid(2)` and fail with EPERM for non-root. The Bash tool runs zsh. Stick to lowercase (`gid`, `bug_gid`, `tag_gid`, etc.) and you avoid the trap entirely.

### Step 5: Reconcile with state.json

**`--retry-abandoned <gid>` and `--retry-failed` are additive, not filters.** They rescue specific bugs from being skipped — they do NOT restrict which tasks you process. Iterate **every** task returned by step 4's `dharma task search` (and every existing state.json entry). New tagged tickets, existing `pending` bugs, and any retried bugs all queue together for dispatch in step 7.

For each fetched task:

- If gid is in `state.json` at a terminal state (`pr-open`, `merged`, `abandoned`, `manual`):
  - Skip unless `--retry-abandoned <gid>` matches (rescues either `abandoned` or `manual`) — then transition to `pending`.
- If gid is in `state.json` at `failed`:
  - Skip unless `--retry-failed` is set — then transition to `pending`.
- If gid is in `state.json` at `blocked` or `working`:
  - Skip — `blocked` needs `triage-unblock`; `working` was handled by cleanup (demoted to `pending` if stale).
- If gid is in `state.json` at `pending`:
  - Queue for dispatch (existing worktree may or may not exist; re-create if missing).
- If gid is **not** in `state.json`:
  - New entry. Pick a meaningful kebab-case branch slug from the task title (3–6 words). Create worktree:

    **Stay in `$WORKTREE_ROOT` for the `git worktree add` call.** Husky resolves `.husky/` relative to git's invocation cwd, not the new worktree — so the post-checkout hook that runs after worktree creation comes from whatever branch `$WORKTREE_ROOT` is on. The patched hook (skips `prisma generate` when `node_modules/.bin/prisma` is missing, invokes the local binary directly) lives on `main`, so any worktree off `main` or a branch derived from it works correctly.

    The relative `../triage-bug-$gid` lands sibling-to-`minerva/` from any sibling worktree. The subshell below leaves the caller's cwd unchanged — good hygiene in a multi-step skill.

    ```bash
    (cd "$WORKTREE_ROOT" && \
      git worktree add "../triage-bug-$gid" -b "bug/$slug-$gid")
    ```
  - Mirror SC's per-worktree setup:
    ```bash
    "$SCRIPTS_DIR/triage-setup-worktree" "../triage-bug-$gid"
    ```
    This links `.env`, `.env.e2e`, `.env.prod`, `.secrets`, `claude-local-preferences.md` when present, `notes`, and `data`, then runs `npm ci`.
  - Download attachments:
    ```bash
    mkdir -p "$SPECS_DIR/$gid/attachments"
    dharma task download-attachments "$gid" --output-dir "$SPECS_DIR/$gid/attachments"
    ```
  - Fetch comments:
    ```bash
    dharma task stories "$gid" --paginate \
      --fields type,text,html_text,created_at,created_by.name,created_by.email \
      > "$SPECS_DIR/$gid/stories.json"
    ```
    **Filter `type == "comment"`** when assembling — `dharma task stories` returns both human comments and system events (assignment, section moves, etc.); we only want human comments.
  - Assemble `bug-spec.json` and write to `$SPECS_DIR/$gid/bug-spec.json`. Schema:
    ```json
    {
      "bug_gid": "string",
      "title": "string",
      "description": "string (notes field, as-is)",
      "url": "string (permalink_url)",
      "reporter": "string (assignee email)",
      "labels": ["string (tag names)"],
      "attachments": [{"filename":"...","local_path":"absolute path"}],
      "comments": [{"author":"...","timestamp":"...","body":"...","attachments":[]}]
    }
    ```
  - Add entry to `state.json` with `phase: pending`. State.json bug-entry schema:
    ```json
    {
      "phase": "pending|working|pr-open|blocked|failed|merged|abandoned",
      "title": "string (Asana task title)",
      "branch": "string (bug/<slug>-<gid>) — slug-first so the first ~15 chars of the branch name are meaningful in GitHub PR previews",
      "worktree_path": "string (absolute)",
      "spec_path": "string (absolute path to bug-spec.json)",
      "asana_url": "string (permalink)",
      "pr_url": "string|null",
      "created_at": "ISO 8601",
      "last_updated_at": "ISO 8601",
      "phase_detail": "string|null (free-text supplemental)"
    }
    ```

Apply `--limit N` after reconciliation: take the N oldest `pending` entries; defer the rest to the next run with a note in the summary.

### Step 6: Print pre-dispatch summary

```
Found N tagged tasks. M new, K resumed.
Dispatching D in waves of <max-parallel>. Watch progress:
  watch -n 2 "$SCRIPTS_DIR/triage-status"
```

If `--dry-run`, stop here. **`--dry-run` is normalisation-only, not side-effect-free**: worktree creation, env symlinks, `npm ci`, attachment downloads, bug-spec writes, and state.json updates have all already happened in Step 5. What `--dry-run` skips is **subagent dispatch** (Step 7). The point is "let me see what the skill set up before I let it loose on bugs."

### Step 6.5: Sentry MCP authentication check

If **any** pending bug references Sentry — i.e. its tags include `sentry`, OR its description matches `sentry\.io/issues/` (or `MINERVA-[A-Z0-9]+` for our project) — the per-bug subagents may need authenticated Sentry MCP access during investigation. Probe before dispatch.

**Detecting Sentry auth state**:

- If `mcp__sentry__authenticate` is listed in the session's available deferred MCP tools, the MCP is **not** authenticated.
- As a secondary check, call `ToolSearch` with `select:mcp__sentry__find_organizations`. If no match, the operational Sentry tools aren't loaded → not authenticated.
- (After JP runs `/mcp`, the `authenticate` tool disappears and operational tools like `find_organizations`, `search_issues`, `get_sentry_resource` appear.)

**If Sentry MCP is authenticated**: proceed to Step 7 normally.

**If Sentry MCP is *not* authenticated AND there are sentry-referencing bugs**:

1. Partition pending bugs into:
   - **sentry-dependent**: tag includes `sentry`, or description matches the patterns above.
   - **regular**: all others.
2. **Start Step 7 dispatch on the regular cohort only**, in the usual rolling wave of `--max-parallel`. The regular bugs run in the background while JP authenticates.
3. **Immediately** prompt JP with `AskUserQuestion` (do not block the regular dispatch):
   > "Sentry MCP isn't authenticated. {N} regular bugs are dispatching now. {M} Sentry-tagged bugs are paused — please run `/mcp` to authenticate Sentry, then pick an option below:"
   >
   > Options:
   >  - **"Authenticated — dispatch Sentry bugs now"** (recommended)
   >  - **"Skip — mark Sentry bugs blocked"**
4. After JP responds:
   - **"Authenticated"**: re-check the MCP. If still not authenticated, ask once more with the same options. If authenticated, dispatch the sentry-dependent cohort into the same rolling wave (respect `--max-parallel`).
   - **"Skip"**: mark each sentry-dependent bug `blocked` with `phase_detail: "deferred: Sentry MCP not authenticated"`. They show up in Step 8's blocked list with a clear unblock path (re-run after `/mcp`).

This pattern keeps regular bugs moving while JP handles the interactive auth flow.

### Step 7: Dispatch (rolling wave)

For each `pending` bug, dispatch a per-bug subagent via the Agent
tool. Maintain at most `--max-parallel` in flight. As each returns,
read its terminal `STATUS.json` from the worktree, update
`state.json`, dispatch the next from the queue.

Each Agent dispatch:

- **subagent_type**: `general-purpose`
- **Do NOT use `isolation: worktree`** — the worktree is pre-created at `../triage-bug-<gid>`.
- **prompt**: read `~/Documents/dotfiles/claude-skills/minerva-asana-triage/prompts/per-bug-subagent.md` and substitute the placeholders:
  - `{{WORKTREE_PATH}}` — absolute path to `../triage-bug-<gid>`
  - `{{BUG_GID}}`
  - `{{BUG_SPEC_PATH}}` — absolute path to `bug-spec.json`
  - `{{ATTACHMENTS_DIR}}` — absolute path
  - `{{ASANA_TASK_URL}}`
  - `{{BLOCKED_NOTE_PATH}}` — absolute path to `BLOCKED.md` if resuming a previously-blocked bug, else empty string. Check both `<worktree>/.triage-scratch/BLOCKED.md` (new layout) and `<worktree>/BLOCKED.md` (legacy from earlier runs) — use whichever exists.

After each subagent returns, branch on whether the harness reports a clean terminal status or a watchdog kill.

**Acceptance rule — no PR is `pr-open` without a converged final review.** This applies to both branches below. Before you record any bug as `pr-open`, confirm the worker's Step 10 review invariant held: the shipped diff went through a diff-review that converged, with no open disagreements except the Contested items it surfaced in the PR body. The worker self-reports this as `review_converged: true` in STATUS.json — but a watchdog kill is exactly when that step gets skipped, so don't take a PR's mere existence as proof. If `review_converged` is unset/false on a `PR_OPENED`, or `.triage-scratch/` shows diff-review never reached a converged terminal state (empty/wedged `diff-review.out`, or a debate that never settled), treat it as **shipped-without-final-review**: re-dispatch a review-only pass (run Step 9 on the open PR's diff; push a follow-up commit for any Agreed fixes, add any new Contested items to the PR body), record it in `phase_detail`, and only then call it `pr-open`. When in doubt, re-review — it's cheap and idempotent.

**Normal return** (subagent finished and emitted a terminal `status`):

- Read `<worktree>/.triage-scratch/STATUS.json` (new layout) or `<worktree>/STATUS.json` (legacy) — whichever exists. If both exist, prefer `.triage-scratch/`. If neither exists or it's malformed, treat as `failed` with `phase_detail: "missing/malformed STATUS.json"`.
- Map subagent's terminal `status` field to coarse state:
  - `PR_OPENED` → `pr-open`
  - `BLOCKED` → `blocked`
  - `NO_FIX` → `failed`
- Update `state.json` atomically (`.tmp` + `mv`).

**Watchdog kill** (the harness reports `failed` with a message matching `/Agent stalled: no progress for \d+s|stream watchdog/`):

Do **not** trust the harness's `failed` verdict. The watchdog fires when the subagent's LLM token stream goes idle for ~600s — most commonly during silent Bash calls (`npm run parallel-check:quiet`, `gh pr create`, Codex `exec`) under multi-subagent CPU contention. The recovery path inside Claude Code is dead code ([anthropics/claude-code#39755](https://github.com/anthropics/claude-code/issues/39755)), so the subagent is simply terminated — its real progress lives in the worktree, not in the harness status.

Cross-reference three sources of ground truth:

1. `<worktree>/.triage-scratch/STATUS.json`
2. `gh pr list --search "head:<branch>" --state all --json number,url,state`
3. `git -C <worktree> log --oneline -3` and `git -C <worktree> status --short`

Then dispatch (or don't) by case:

- **STATUS=`PR_OPENED` AND `gh` confirms the PR exists**: the PR shipped — but a kill this close to the end is exactly when the final review gets skipped, so apply the **acceptance rule above** before calling it done. If the review invariant holds (`review_converged: true`, corroborated), record `pr-open` with the `pr_url`, no re-dispatch, `phase_detail` "watchdog landed at exit; work complete". If it doesn't, handle as shipped-without-final-review per the acceptance rule.
- **Commit on branch but no PR** (`git log` shows a fresh commit, `gh` returns empty): re-dispatch with a resume prompt that picks up at Step 10. The resume must **not** skip Step 10's review gate — point the agent at it, since a commit alone is no guarantee the committed diff was review-converged.
- **Staged/unstaged changes only, mid-pipeline phase** (`implementing` / `testing` / `diff-review` per STATUS.json, with `PLAN.md` + maybe `diff-review.out` in `.triage-scratch/`): re-dispatch with a resume prompt naming the prior phase and listing the artifacts present. Tell the new agent to verify state itself, then continue from the appropriate step.
- **Barely started** (phase `reading` or no useful artifacts): re-dispatch fresh; tell the new subagent to overwrite the stale `STATUS.json`.

**Resume prompt contents** (when re-dispatching after a watchdog kill):

- Bug title + GID + Asana URL + absolute worktree path.
- One paragraph stating that the prior subagent was watchdog-killed at `<phase>` and listing the artifacts now in `.triage-scratch/` plus the git state (staged / committed / unpushed).
- A pointer to `/tmp/triage-prompts/<gid>.md` as the original task definition (for reference; the new agent does not need to redo Steps 1-N).
- An instruction to **verify the prior state itself** (read `STATUS.json`, `PLAN.md`, `diff-review.out` if present; run `git diff --cached` and `git diff`) **before acting**.
- The exact step to continue from.
- Restated key invariants: no `--no-verify` (unless a pre-existing flake is confirmed via stash-test-restore), no `Monitor` tool, pre-authorized for git ops, and **the Step 10 review gate** — don't open or finalize a PR whose final diff wasn't review-converged; when unsure, re-run Step 9 first.

Track each resume in `state.json` `phase_detail` so the Step 8 summary can call it out as "resumed after watchdog kill at `<phase>`".

### Step 8: Final summary

Group entries by terminal state:

```
PRs opened (5):
  bug-1234  PR #4521  Fix footer overlap on /advice
  ...

Blocked (2):
  bug-1238  Two candidate fixes — see BLOCKED.md
  ...

Failed (1):
  bug-1240  Dev server wouldn't start

Manual (k):
  bug-1242  JP handling outside skill — worktree preserved at /Users/.../triage-bug-1242

Deferred by --limit (3): bug-1241, bug-1242, bug-1243
```

Print absolute paths to BLOCKED.md, failed-bug worktrees, and manual-bug worktrees so JP can `cd` directly. (Manual bugs show every run as a reminder that worktrees still exist — JP can `triage-abandon` them later to reap, or leave them indefinitely.)

### Step 9: Post-cycle batch product-research summary (on request)

This step is **JP-triggered**, not automatic. It runs after JP has merged the last PR from a triage cycle. The output is a single batch markdown file in the product research knowledge base, covering every PR from the cycle in one place — bugfix runs land many small PRs and the per-PR `rpr` flow would create too much noise if it fired on each one.

**When to nudge JP** (don't write the file proactively; just mention it):

After Step 3 cleanup, for each distinct `created_at` date represented in `state.json`, check whether (a) every bug from that date is in a terminal state (`merged | abandoned | manual | failed`) and (b) no batch file already exists at `~/80k/ai-products-research/automated-inputs/pr-summaries/<YYYY-MM-DD>-batch-prs-*.md`. If both are true for some date, mention in your end-of-session summary text: "Heads-up: the `<YYYY-MM-DD>` triage cycle is now fully wrapped — say the word if you'd like me to write the batch product-research summary." Don't write it without JP saying so — they may be intentionally waiting (e.g. on a closed-PR re-open) or want to write notes themselves first.

**What to write** (when JP says go):

A single file at `~/80k/ai-products-research/automated-inputs/pr-summaries/<YYYY-MM-DD>-batch-prs-<list>.md`, where `<YYYY-MM-DD>` is the cycle's `created_at` date and `<list>` is the PR numbers joined by hyphens (e.g. `745-746-747-748-750-751`).

Frontmatter:

```yaml
---
date: <YYYY-MM-DD>
tags: [pr-summary, advisorbot, batch]
source: pr-summary
status: raw
prs: [<comma-separated PR numbers>]
author: jpaddison3
---
```

Then a `## PR #NNN: <title>` section per PR, each with the standard per-PR template fields: **What changed**, **Why**, **Product area**, **User-facing changes**, **Links**. Source the content from `gh pr view <pr> --json title,body,files` — preserve the technical detail but rephrase the PR's "What was the bug" content as descriptive prose (don't copy-paste).

For PRs that closed without merging, include a brief stub: title, "What was attempted", "Why it didn't ship", "Product area" (note the bug is still un-mitigated if relevant), "User-facing changes: None — PR did not ship", link.

**Dedupe pass** (the critical "less is more" step — do this *after* writing the file):

For each PR section in the batch, check `~/80k/ai-products-research/automated-inputs/pr-summaries/` for any file matching `*-pr-<NNN>-*.md` (match by PR number only — the file's date prefix may differ from the cycle date because the per-PR file is timestamped at merge, not cycle-start). If a per-PR file exists, **remove that PR's section from the batch file** — the per-PR note is canonical and the duplicate would create noise.

If after dedupe the batch is empty (every PR has its own per-PR file already), `trash` the batch file entirely.

The motivation for dedupe: per-PR notes from `rpr` are reviewer-curated and authoritative; the batch is only to fill the gaps where no per-PR note ever got written.

**Then reap the cycle.** Once the batch summary is written and deduped, the cycle is fully wrapped and its product-research is captured — so run cleanup to reap its now-terminal worktrees instead of leaving them to linger until some future run's Step 3:

```bash
"$SCRIPTS_DIR/triage-cleanup"
```

Same as Step 3 (halt with the corrigibility framing if the script is missing). It's safe to run here: cleanup **preserves** `manual` worktrees, so anything JP is holding offline stays put — it only reaps the cycle's finished work.

## State.json write protocol

Only this skill (and the `triage-*` scripts) writes `state.json`. Subagents write only to their own worktree's `STATUS.json`. All writes use `.tmp` + `mv`.

State enum: `pending` / `working` / `pr-open` / `blocked` / `failed` / `merged` / `abandoned` / `manual`. Reject any other value when reading.

- **`manual`** is a user-set terminal state meaning "JP is handling this outside the skill." Like `abandoned` it is terminal (future runs skip it), but unlike `abandoned` the worktree + branch are **preserved** by `triage-cleanup`. Set via `scripts/triage-manual <gid>`. Use this when JP wants to keep artifacts in `.triage-scratch/` (rankings, investigation notes, downloaded data) accessible after taking the bug offline.

## Cross-worktree concurrency

`state.json` is canonical and shared across all SC worktrees of the same minerva repo. If JP runs the skill from two SC worktrees concurrently (or while a prior session is still mid-flight), they'll race on state.json writes and may both try to create the same `../triage-bug-<gid>` path. There is **no advisory lock** in v1.

Best-effort guard: before Step 4, check whether any bug in state.json is at `phase: working` with a recent `last_updated_at` (< 60 min). If so, halt with a message naming the in-flight bug and ask JP to either wait or `triage-abandon` it.

## When to halt and ask JP

Beyond the corrigibility framing at top, halt explicitly on:

- A task in `state.json` with a phase not in the enum.
- A worktree at `../triage-bug-<gid>` that exists but is on a different branch than `bug/*-<gid>`.
- `dharma task search` returning a task whose gid is already at `pr-open` but whose PR was closed without merging — ambiguous; ask.
- Any per-bug subagent returning before completing any phase (immediate crash) more than once in a row.
- `codex` repeatedly hangs (>2 min with no output) on the plan-review or diff-review pass.
