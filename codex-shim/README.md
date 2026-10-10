# codex-shim — route Codex account and mirror Claude Code's `/fast`

`codex-mirror` selects JP's Codex account from the current repo and makes
Codex's `service_tier` follow Claude Code's current `/fast` state, so a `codex`
call uses the right account and speed tier.

It is installed as a **transparent PATH shim**, so there is nothing to invoke by
hand and no skill to remember — every `codex` call routes through it
automatically, including the review skills (`review-codex`, `review-multi`,
`swarm-loop-review`) and ad-hoc calls.

## Account routing

The shim sets `CODEX_HOME=~/.codex-gmail` in the same personal repos that use
Claude's Gmail account. That home is logged into `johnpaddison@gmail.com`.
Everywhere else it leaves `CODEX_HOME` unset, so Codex uses the default
`~/.codex` home logged into `jp.addison@80000hours.org`.

An explicit `CODEX_HOME` from the caller always wins. Credential storage is
configured as file-based so the homes use separate `auth.json` files rather
than converging through the macOS Keychain.

Because routing lives in the PATH shim rather than a shell function, it also
applies to review skills and other subprocesses that invoke `codex`.

## Speed mirroring

1. Claude Code's `/fast` toggle is echoed back by the API as `usage.speed`
   (`"fast"` | `"standard"`) and persisted to the session transcript at
   `~/.claude/projects/<cwd-slug>/$CLAUDE_CODE_SESSION_ID.jsonl`, path
   `.message.usage.speed`.
2. Codex exposes an equivalent **Fast tier**: the request `service_tier`
   `"priority"` ("1.5x speed, increased usage" — same model, same intelligence),
   selected via the config key `service_tier = "fast"` (which maps to request
   `priority`); `"default"` is standard.
3. `codex-mirror` reads Claude's speed and injects `-c service_tier=fast` or
   `-c service_tier=default` (a global, position-independent override) before
   execing the real Codex binary.

> Note: the `features.fast_mode` flag only gates the TUI's `/fast` command and
> does **nothing** for non-interactive `codex exec`/`review` — `service_tier` is
> the lever that actually drives the request tier.

## Install (the PATH shim)

`codex-mirror` is symlinked as `codex` into `~/.local/codex-shim/`, and `.zshrc`
inserts that dir into PATH **immediately before nvm's node bin** — that's where
npm puts the real binary, and nvm prepends itself to the very front of PATH.

The symlink is created by `newcomputer.bash`; the PATH insertion lives in
`zshrc.zsh`. A fresh shell / Claude Code restart is needed after changing PATH.

The shim:

- skips its own dir when resolving the real codex (no infinite loop);
- routes personal repos to the Gmail Codex home and otherwise uses the default;
- leaves speed unchanged outside a Claude session (`CLAUDE_CODE_SESSION_ID` is
  absent, so it injects no service-tier override);
- fails safe — if nvm ever ends up ahead of the shim on PATH, the shim is simply
  bypassed and codex runs normally.

## Gotchas

- **Nothing behind the shim.** If no real codex is on PATH the shim exits 127
  with a plain `codex: command not found`, so it doesn't disguise the real
  problem. The usual cause is nvm: globals live under one node version, and
  switching versions (an `.nvmrc`, or `nvm alias default 22` floating to a newer
  release) leaves them behind. `nvm reinstall-packages <old-version>` fixes it.
- **One-turn lag.** `usage.speed` reflects the last *persisted* assistant turn,
  so a `/fast` toggle in the same message that launches the work reads the prior
  state. Harmless for multi-turn flows (reviews, debates).

## Manual use / debugging

The shim is on PATH, but you can also call the script directly:

```bash
~/.local/codex-shim/codex review --uncommitted                          # via the shim
/Users/jpaddison/Documents/dotfiles/codex-shim/codex-mirror exec "..."  # the script
```

### Knobs

- `CODEX_MIRROR_SPEED=fast|standard` — force the mode, skipping detection.
- `CODEX_MIRROR_DEBUG=1` — print the resolved binary, detected speed, and the
  command it *would* run, then exit without calling Codex.

```bash
CODEX_MIRROR_DEBUG=1 ~/.local/codex-shim/codex review --uncommitted
CODEX_MIRROR_DEBUG=1 CODEX_MIRROR_SPEED=standard ~/.local/codex-shim/codex review
```

## Behavior parity (confirmed)

Per OpenAI's Codex docs, Fast mode runs the **same model** ~**1.5x faster** at
higher credit cost (intelligence unchanged) — semantically identical to Claude's
`/fast`. So mirroring is the right thing to do.

Not network-verified: that `-c service_tier=fast` produces the 1.5x speedup on a
given `codex exec`/`review` run (Codex doesn't record the tier in its session
rollouts, so it can't be confirmed after the fact). But `service_tier` is the
documented, config-level lever — and JP's `~/.codex/config.toml` already uses
`service_tier = "default"` as its standard, so injecting `fast`/`default` is the
correct, intended mechanism.

## Also in this dir: `orca-open-guard`

A second PATH shim, symlinked as `orca`. It rewrites `orca open` to `orca status`
whenever Orca is already running, because `orca open` raises the Orca window
(focus steal) and Codex agents run it reflexively. Everything else passes
through. `ORCA_OPEN_GUARD=0` bypasses it. See the script header for details.

## Also in this dir: `claude-account`

A third PATH shim, symlinked as `claude`. It sets `CLAUDE_CONFIG_DIR` from the
repo that owns the current directory, then execs the real Claude Code. It replaces
the old `claude()` zsh function, which only ran in interactive zsh and matched on
a `$PWD` prefix (so Orca panes, pane restore, estra and worktrees all missed).

The repo → account table is `claude-accounts` in this repo, symlinked to
`~/.config/claude-accounts` (one `<repo-path> <config-dir>` per line, `~` expands,
`#` comments). The default account (`~/.claude`) is never listed: no match leaves
`CLAUDE_CONFIG_DIR` **unset** (never set to `~/.claude`).

Resolution order:

1. `CLAUDE_CONFIG_DIR` already set → pass through untouched (token included).
2. `--resume <id>` / `--resume=<id>` / `-r <id>` → the account whose config dir
   holds `projects/*/<id>.jsonl`. Several holders: the cwd's account, else default.
3. Otherwise the git repo's main checkout (parent of `--git-common-dir`, so linked
   worktrees anywhere map like their repo), else the cwd. Longest path match on a
   directory boundary wins.

When it remaps to a non-default account it unsets `CLAUDE_CODE_OAUTH_TOKEN` (the
personal account's token would override the chosen dir's login). It fails open:
a missing/malformed table, `git` failure, or missing mapped dir prints a
`claude-account: …` warning and launches on the default account.

`CLAUDE_ACCOUNT_DEBUG=1 claude` prints the real binary, chosen dir, rule
(`explicit`/`resume`/`repo`/`cwd`/`none`) and token handling, then exits without
launching. Tests: `tests/test_claude_account.py`.
