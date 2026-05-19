---
name: minerva-asana-triage
description: Batch-process Asana bugs tagged jpa-bugfixes-today into PRs. Spawns per-bug subagents in parallel worktrees with Codex plan-review and diff-review.
allowed-tools:
  - Bash
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

### Step 4: Resolve tag and fetch tasks

```bash
tag_gid=$(dharma tag list --name "$tag_name" | jq -r '.[0].gid')
dharma task search --tag "$tag_gid" --completed=false \
  --fields name,notes,permalink_url,assignee.email,tags.name,custom_fields
```

If `$tag_gid` is empty or null, halt — tag was renamed/deleted.

**Naming note:** all shell variables in this skill use **lowercase**. `GID`, `UID`, `EGID`, `EUID` are special in zsh — writes to them call `setegid(2)` / `seteuid(2)` and fail with EPERM for non-root. The Bash tool runs zsh. Stick to lowercase (`gid`, `bug_gid`, `tag_gid`, etc.) and you avoid the trap entirely.

### Step 5: Reconcile with state.json

For each fetched task:

- If gid is in `state.json` at a terminal state (`pr-open`, `merged`, `abandoned`):
  - Skip unless `--retry-abandoned <gid>` matches — then transition to `pending`.
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
    cd "../triage-bug-$gid"
    ln -sf ../minerva/.env ./.env
    ln -sf ../minerva/.env.e2e ./.env.e2e
    ln -sf ../minerva/.env.prod ./.env.prod
    ln -sf ../minerva/.secrets ./.secrets
    ln -sfn ../minerva/notes ./notes
    ln -sfn ../minerva/data ./data
    npm ci  # ~15s on warm cache
    ```
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

After each subagent returns:

- Read `<worktree>/.triage-scratch/STATUS.json` (new layout) or `<worktree>/STATUS.json` (legacy) — whichever exists. If both exist, prefer `.triage-scratch/`. If neither exists or it's malformed, treat as `failed` with `phase_detail: "missing/malformed STATUS.json"`.
- Map subagent's terminal `status` field to coarse state:
  - `PR_OPENED` → `pr-open`
  - `BLOCKED` → `blocked`
  - `NO_FIX` → `failed`
- Update `state.json` atomically (`.tmp` + `mv`).

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

Deferred by --limit (3): bug-1241, bug-1242, bug-1243
```

Print absolute paths to BLOCKED.md and failed-bug worktrees so JP can `cd` directly.

## State.json write protocol

Only this skill (and the `triage-*` scripts) writes `state.json`. Subagents write only to their own worktree's `STATUS.json`. All writes use `.tmp` + `mv`.

State enum: `pending` / `working` / `pr-open` / `blocked` / `failed` / `merged` / `abandoned`. Reject any other value when reading.

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
