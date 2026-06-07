# codex-shim — mirror Claude Code's `/fast` onto Codex

`codex-mirror` makes Codex's `fast_mode` feature flag follow Claude Code's
current `/fast` state, so a `codex` call made from inside a Claude session runs
at the same speed tier as Claude.

It is installed as a **transparent PATH shim**, so there is nothing to invoke by
hand and no skill to remember — every `codex` call routes through it
automatically, including the review skills (`review-codex`, `review-multi`,
`swarm-loop-review`) and ad-hoc calls.

## How it works

1. Claude Code's `/fast` toggle is echoed back by the API as `usage.speed`
   (`"fast"` | `"standard"`) and persisted to the session transcript at
   `~/.claude/projects/<cwd-slug>/$CLAUDE_CODE_SESSION_ID.jsonl`, path
   `.message.usage.speed`.
2. Codex exposes an equivalent **`fast_mode`** feature flag (stable).
3. `codex-mirror` reads Claude's speed and injects `-c features.fast_mode=true`
   or `=false` (a global, position-independent override) before execing the real
   Codex binary.

## Install (the PATH shim)

`codex-mirror` is symlinked as `codex` into `~/.local/codex-shim/`, and `.zshrc`
inserts that dir into PATH **immediately before nvm's node bin**. Both
Superconductor's `find_real_binary` and every review skill resolve codex as
*"first non-superconductor `codex` on PATH"* — which is now the shim. (nvm tends
to prepend its bin to the very front, ahead of Superconductor, so the shim must
beat nvm, not merely sit after Superconductor.)

The symlink is created by `newcomputer.bash`; the PATH insertion lives in
`zshrc.zsh`. A fresh shell / Claude Code restart is needed after changing PATH.

The shim:

- skips superconductor dirs **and its own dir** when resolving the real codex
  (no infinite loop);
- is a transparent passthrough outside a Claude session (no
  `CLAUDE_CODE_SESSION_ID` → injects nothing), so plain CLI `codex` is unchanged;
- fails safe — if nvm ever ends up ahead of the shim on PATH, the shim is simply
  bypassed and codex runs normally.

## Two things it deliberately handles

- **Bypasses Superconductor's wrapper for resolution.** `codex` on PATH resolves
  to `~/.superconductor/bin/codex`, whose injected MCP server can hang
  `codex review` when run non-interactively from a Claude session. The shim (and
  the review skills) resolve the real binary instead.
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

## Caveat

The `fast_mode` name matches Claude's concept and the flag toggles correctly,
but it has not been confirmed that Codex's `fast_mode` changes behavior in
exactly the same way (output-speed / priority tier) as Claude's `/fast`.
