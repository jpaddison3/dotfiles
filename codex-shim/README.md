# codex-shim — mirror Claude Code's `/fast` onto Codex

`codex-mirror` makes Codex's `service_tier` follow Claude Code's current `/fast`
state, so a `codex` call made from inside a Claude session runs at the same speed
tier as Claude.

It is installed as a **transparent PATH shim**, so there is nothing to invoke by
hand and no skill to remember — every `codex` call routes through it
automatically, including the review skills (`review-codex`, `review-multi`,
`swarm-loop-review`) and ad-hoc calls.

## How it works

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
- is a transparent passthrough outside a Claude session (no
  `CLAUDE_CODE_SESSION_ID` → injects nothing), so plain CLI `codex` is unchanged;
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
