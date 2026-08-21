---
name: codex
description: How to invoke the Codex CLI (`codex`) from the shell. Read this BEFORE shelling out to `codex` for any nontrivial task — it covers capturing output with `-o` so the answer doesn't get buried in the agent-session stream, and piping the prompt via stdin.
allowed-tools:
  - Bash
  - Read
---

# Calling Codex from the shell

Whenever you invoke `codex` from Bash, follow these rules. They are not
review-specific — they apply to any `codex exec`, `codex review`, or other
non-interactive call.

## 1. For anything nontrivial, capture output with `-o` and read the file

When Codex actually thinks for a while, **don't read its answer from stdout** —
add `-o <file>` and read that file instead:

```bash
CODEX_OUT="$(mktemp)"
codex exec -o "$CODEX_OUT" "your prompt"   # or: codex review --uncommitted -o "$CODEX_OUT"
# then Read "$CODEX_OUT"
```

**Why.** Codex streams its **entire agent session** to stdout — a config
banner, then every tool call it makes (file reads, greps, scratch scripts) and
each command's output — and prints the actual answer only as the final message.
The longer it thinks, the more the real answer is buried in tool noise.
Reading / skimming / `tail`-ing stdout makes the answer look like just more of
the transcript, and it gets misread or silently lost. `-o` writes **only** that
final message to the file, so you Read a clean result.

A non-empty `$CODEX_OUT` is the answer; an empty/absent file is the only true
"Codex produced nothing" signal (exit code is 0 either way). Re-create
`$CODEX_OUT` each call — Bash state doesn't persist.

Skip `-o` only for genuinely trivial one-shots where you expect a couple of
lines and no tool use (e.g. `codex --version`).

## 2. Pipe the prompt in via stdin

For `codex exec`, pass long or special-character-laden prompts via **stdin**, not
argv — interpolating into the argv breaks on quotes/backticks and can blow
`ARG_MAX`:

```bash
codex exec -o "$CODEX_OUT" - <<'EOF'
<your prompt here>
EOF
```

## One pass

Treat each call as one pass — no `resume`/follow-up unless the task specifically
calls for it.
