---
name: review-codex
description: Run a code review with Codex. In Codex, use native review behavior; in Claude, invoke the Codex CLI.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Grep
  - Glob
---

# Review with Codex

Run a Codex review. The implementation depends on which agent is executing this
skill:

- **Codex runtime:** use Codex's native review behavior. Use a review-only
  Codex subagent when the current runtime allows one.
- **Claude runtime:** invoke the Codex CLI review harness from the shell.

## Usage

- `/review-codex` or `$review-codex` - run review and display output
  (pass-through mode)
- `/review-codex collaborative` or `$review-codex collaborative` - run review,
  then discuss findings
- `/review-codex fix` or `$review-codex fix` - run review, then fix issues
  autonomously
- `/review-codex base main` or `$review-codex base main` - review changes
  against a base branch
- `/review-codex mini` or `$review-codex mini` - run the basic review without
  the extra standards checklist

Modes can be combined: `/review-codex mini fix base main`.

## Execution

**Parse arguments from:** `$ARGUMENTS` in Claude, or the user's prompt after
`$review-codex` in Codex.

**Determine mode:**

- If arguments contain "mini" → mini mode, remove it from args
- If arguments contain "fix" → fix mode, remove it from args
- If arguments contain "collaborative" → collaborative mode, remove it from args
- If arguments contain "base <branch>" → review against that base branch
- Default → pass-through mode

### Codex runtime

Spawn two subagents in parallel:

For the first, please ask for a general review, and then the "follow-up" can be run in parallel.

### Claude runtime

Do **not** invoke bare `codex`. Superconductor installs a wrapper at `~/.superconductor/bin/codex` (first on PATH) that injects its own MCP server via `-c` config overrides. That MCP handshake can hang `codex review` indefinitely when run non-interactively from inside a Superconductor-managed Claude session. Call the real binary directly:

```bash
CODEX_BIN="$(which -a codex | grep -v '/.superconductor/' | head -n1)"
```

Bash state does not persist between your tool calls, so either re-resolve `$CODEX_BIN` each call or substitute the absolute path (e.g. `~/.nvm/versions/node/v22.16.0/bin/codex`) into subsequent commands.

#### Step 1: General review

Run the initial review:

```bash
"$CODEX_BIN" review [--uncommitted OR --base <branch>]
```

#### Step 2: Follow-up with specific criteria

Skip this step in mini mode.

Resume the session with custom review instructions:

```bash
"$CODEX_BIN" exec resume --last "A few things I like to double check with code that my AI coding agent has produced:

1) Types:
   a) Are there any type casts that it added. (I often find it doesn't tell me about them like I ask it to.) It's required to at least add a comment explaining them, but I like to review them myself in any case.
   b) Are there any weak typings, such as Record<string, string> or similar.

2) We follow a \"Fail fast, fail loud\" philosophy here. I want you to carefully review what the code does when expected information is missing. The classic thing I don't want is \`foo?.bar ?? \"\"\` – that's just hiding the fact that data is missing. I also don't like catching errors without \`recordError\`-ing them or re-throwing.

3) (Pet peeve): when refactoring, it likes to go halfway. \`NEW_VAR = x; OLD_VAR = NEW_VAR; // For backwards compatibility\`. Or similar for re-exporting variables/functions that have moved. It should fix the consumer to use the new name, with the exception of server/client API boundaries.

You may ignore these issues inside test files. When in doubt, tell me about something you're unsure about.

**IMPORTANT**: Do not make any changes. This is only a review."
```

### Output handling

- **Pass-through mode:** Display the Codex output directly. Do not add commentary, analysis, or suggestions. Just show what Codex said.

- **Collaborative mode:** After showing the Codex output, provide your own analysis. Note agreements, disagreements, or additional concerns Codex may have missed. Offer to help address any issues found.

- **Fix mode:** After reviewing the Codex output, make executive decisions and fix issues autonomously. Use your own judgment on what's worth fixing.

  **One warning:** Your judgment tends to be too lenient on type system issues, fail-fast violations, and backwards-compatibility hacks. When Codex flags these, lean toward fixing them rather than dismissing them.

  After fixing, briefly summarize what you changed and why. If you skipped any flagged issues, explain your reasoning.
