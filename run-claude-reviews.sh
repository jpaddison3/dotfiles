#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: run-claude-reviews.sh [options]

Run six parallel Claude Code review passes for the current git repo.
For compatibility with older generated scripts, a single positional BRANCH is
also accepted as shorthand for --base BRANCH.

Options:
  --base BRANCH       Review changes against BRANCH using git diff BRANCH...HEAD.
                      If omitted, review current workspace changes with git diff HEAD.
  --mini              Run one Claude review covering all six areas.
  --out-dir DIR       Directory for prompts, stream logs, stderr, and extracted output.
                      Defaults to /tmp/claude-review-<repo>-<timestamp>.
  --timeout SECONDS   Per-review timeout. Default: 900. Use 0 for no timeout.
  -h, --help          Show this help.

Environment:
  CLAUDE_BIN                    Claude binary to run. Defaults to ~/.local/bin/claude if present.
  CLAUDE_REVIEW_ALLOWED_TOOLS   Defaults to "Read,Grep,Glob,Bash(git *)".
  CLAUDE_REVIEW_TIMEOUT_SECONDS Default timeout when --timeout is omitted.
EOF
}

die() {
  printf 'run-claude-reviews.sh: %s\n' "$*" >&2
  exit 2
}

BASE_BRANCH=""
MINI=0
OUT_DIR=""
TIMEOUT_SECONDS="${CLAUDE_REVIEW_TIMEOUT_SECONDS:-900}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base)
      [ "$#" -ge 2 ] || die "--base requires a branch"
      BASE_BRANCH="$2"
      shift 2
      ;;
    --mini)
      MINI=1
      shift
      ;;
    --out-dir)
      [ "$#" -ge 2 ] || die "--out-dir requires a directory"
      OUT_DIR="$2"
      shift 2
      ;;
    --timeout)
      [ "$#" -ge 2 ] || die "--timeout requires seconds"
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [ -z "$BASE_BRANCH" ]; then
        BASE_BRANCH="$1"
        shift
      else
        die "unexpected argument: $1"
      fi
      ;;
  esac
done

case "$TIMEOUT_SECONDS" in
  ''|*[!0-9]*) die "--timeout must be a non-negative integer" ;;
esac

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [ -n "${CLAUDE_BIN:-}" ]; then
  CLAUDE_BIN_RESOLVED="$CLAUDE_BIN"
elif [ -x "$HOME/.local/bin/claude" ]; then
  CLAUDE_BIN_RESOLVED="$HOME/.local/bin/claude"
else
  CLAUDE_BIN_RESOLVED="$(command -v claude || true)"
fi
[ -n "$CLAUDE_BIN_RESOLVED" ] || die "could not find claude binary"

ALLOWED_TOOLS="${CLAUDE_REVIEW_ALLOWED_TOOLS:-Read,Grep,Glob,Bash(git *)}"

REPO_NAME="$(basename "$ROOT")"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
if [ -z "$OUT_DIR" ]; then
  OUT_DIR="${TMPDIR:-/tmp}/claude-review-${REPO_NAME}-${TIMESTAMP}"
fi
mkdir -p "$OUT_DIR"

CONTEXT_FILE="$OUT_DIR/context.md"

append_file_if_present() {
  local label="$1"
  local path="$2"

  if [ -f "$path" ] || [ -L "$path" ]; then
    printf '### %s: `%s`\n\n' "$label" "$path"
    cat "$path"
    printf '\n\n'
  fi
}

append_file_if_distinct() {
  local label="$1"
  local path="$2"
  local comparison_path="$3"

  if [ -f "$path" ] || [ -L "$path" ]; then
    if { [ -f "$comparison_path" ] || [ -L "$comparison_path" ]; } && cmp -s "$path" "$comparison_path"; then
      printf '### %s: `%s`\n\n' "$label" "$path"
      printf 'Same content as `%s`; omitted.\n\n' "$comparison_path"
    else
      append_file_if_present "$label" "$path"
    fi
  fi
}

{
  printf '# Claude Review Context\n\n'
  printf 'Repository root: `%s`\n' "$ROOT"
  printf 'Current branch: `%s`\n' "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || printf unknown)"
  if remote_url="$(git remote get-url origin 2>/dev/null)"; then
    printf 'Origin: `%s`\n' "$remote_url"
  fi
  if [ -n "$BASE_BRANCH" ]; then
    printf 'Base branch: `%s`\n' "$BASE_BRANCH"
  else
    printf 'Base branch: current `HEAD` plus working tree changes\n'
  fi
  printf '\n## Project Instructions\n\n'
  append_file_if_present "Project Claude" "$ROOT/CLAUDE.md"
  append_file_if_present "Project Codex" "$ROOT/AGENTS.md"
  append_file_if_present "Global Claude" "$HOME/.claude/CLAUDE.md"
  append_file_if_distinct "Global Codex" "$HOME/.codex/AGENTS.md" "$HOME/.claude/CLAUDE.md"
  printf '## Git Status\n\n```text\n'
  git status --short
  printf '```\n\n'
  printf '## Diff\n\n```diff\n'
  if [ -n "$BASE_BRANCH" ]; then
    git diff "$BASE_BRANCH"...HEAD
  else
    git diff HEAD
  fi
  printf '\n```\n'
} > "$CONTEXT_FILE"

run_with_timeout() {
  local pid="$1"
  local slug="$2"
  local stream_file="$3"
  local status_file="$4"
  local start
  local now
  local last_report
  local bytes
  local rc

  start="$(date +%s)"
  last_report="$start"

  while kill -0 "$pid" 2>/dev/null; do
    now="$(date +%s)"
    if [ "$TIMEOUT_SECONDS" -gt 0 ] && [ $((now - start)) -ge "$TIMEOUT_SECONDS" ]; then
      printf 'timeout after %s seconds\n' "$TIMEOUT_SECONDS" > "$status_file"
      kill "$pid" 2>/dev/null || true
      sleep 2
      kill -9 "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 124
    fi

    if [ $((now - last_report)) -ge 30 ]; then
      bytes="$(wc -c < "$stream_file" 2>/dev/null | tr -d ' ' || printf 0)"
      printf '[%s] still running after %ss; stream=%s bytes\n' "$slug" "$((now - start))" "$bytes" >&2
      last_report="$now"
    fi
    sleep 5
  done

  set +e
  wait "$pid"
  rc="$?"
  set -e
  printf 'exit %s\n' "$rc" > "$status_file"
  return "$rc"
}

extract_output() {
  local stream_file="$1"
  local output_file="$2"
  local partial_file="$3"

  if command -v jq >/dev/null 2>&1; then
    jq -r 'select(.type == "result" and (.result // "") != "") | .result' "$stream_file" > "$output_file.tmp" 2>/dev/null || true
    if [ -s "$output_file.tmp" ]; then
      mv "$output_file.tmp" "$output_file"
    else
      rm -f "$output_file.tmp"
    fi

    : > "$partial_file.tmp"
    jq -r '
        select(.type == "assistant")
        | .message.content[]?
        | select(.type == "text")
        | .text
      ' "$stream_file" >> "$partial_file.tmp" 2>/dev/null || true
    jq -j '
        select(.type == "stream_event")
        | select(.event.type == "content_block_start")
        | select(.event.content_block.type == "text")
        | (.event.content_block.text // "")
      ' "$stream_file" >> "$partial_file.tmp" 2>/dev/null || true
    jq -j '
        select(.type == "stream_event")
        | select(.event.type == "content_block_delta")
        | select(.event.delta.type == "text_delta")
        | .event.delta.text
      ' "$stream_file" >> "$partial_file.tmp" 2>/dev/null || true
    if [ -s "$partial_file.tmp" ]; then
      printf '\n' >> "$partial_file.tmp"
    fi
    if [ -s "$partial_file.tmp" ]; then
      mv "$partial_file.tmp" "$partial_file"
    else
      rm -f "$partial_file.tmp"
    fi
  fi
}

run_review() {
  local slug="$1"
  local title="$2"
  local instructions="$3"
  local prompt_file="$OUT_DIR/$slug.prompt.md"
  local stream_file="$OUT_DIR/$slug.stream.jsonl"
  local output_file="$OUT_DIR/$slug.out.md"
  local partial_file="$OUT_DIR/$slug.partial.md"
  local error_file="$OUT_DIR/$slug.err.txt"
  local status_file="$OUT_DIR/$slug.status.txt"
  local pid
  local rc

  {
    printf 'You are reviewing this repository.\n\n'
    printf 'Focus area: %s\n\n' "$title"
    printf '%s\n\n' "$instructions"
    printf 'Do not make changes. Review only.\n\n'
    printf 'Output concise, actionable findings only. For each finding include file path, line number if available, severity, and reasoning. If there are no findings, say so.\n\n'
    cat "$CONTEXT_FILE"
  } > "$prompt_file"

  "$CLAUDE_BIN_RESOLVED" \
    --print \
    --verbose \
    --output-format stream-json \
    --include-partial-messages \
    --no-chrome \
    --mcp-config '{"mcpServers":{}}' \
    --strict-mcp-config \
    --permission-mode dontAsk \
    --allowedTools "$ALLOWED_TOOLS" \
    --add-dir "$ROOT" \
    < "$prompt_file" > "$stream_file" 2> "$error_file" &
  pid="$!"

  if run_with_timeout "$pid" "$slug" "$stream_file" "$status_file"; then
    rc=0
  else
    rc="$?"
  fi

  extract_output "$stream_file" "$output_file" "$partial_file"
  return "$rc"
}

SLUGS=(correctness code-quality standards reuse security efficiency)
TITLES=(Correctness "Code Quality" "Codebase Standards" "Code Reuse" Security Efficiency)
INSTRUCTIONS=(
  "Bug hunt. Focus on logic errors, runtime failures, incorrect edge cases, state mutations in the wrong order, incorrect assumptions about API/data contracts, and missing error handling at system boundaries. Do not flag style, naming, security, or performance issues."
  "Review craftsmanship and maintainability: redundant state, parameter sprawl, copy-paste, leaky abstractions, stringly-typed code, unnecessary comments, unnecessary JSX nesting, nested ternaries, and overly clever code. Do not flag issues that are only taste."
  "Review adherence to project conventions. In particular, flag type casts, weak typings, fail-fast violations, silent fallbacks for expected data, swallowed errors, and halfway refactors/re-exports. Ignore these issues inside test files when reasonable."
  "Look for code newly added in the diff that duplicates existing utilities or local patterns. Suggest concrete existing helpers/modules when applicable. Spend most attention exploring surrounding code for reusable helpers."
  "Security review only. Only flag issues where you are more than 80 percent confident of practical exploitability. Focus on injection, auth/authorization bypass, secrets/crypto, code execution, XSS, and sensitive data exposure. Do not flag DoS, rate limiting, theoretical hardening, outdated dependencies, or client-side auth checks."
  "Review performance and resource usage: duplicate work, missed concurrency, hot-path bloat, recurring no-op updates, TOCTOU existence checks, memory leaks, unbounded structures, and overly broad operations. Keep the bar practical."
)

if [ "$MINI" -eq 1 ]; then
  SLUGS=(combined)
  TITLES=("Combined Review")
  INSTRUCTIONS=("Review correctness, code quality, codebase standards, code reuse, security, and efficiency in one pass. Apply the same criteria as the focused review agents.")
fi

printf 'Writing Claude review artifacts to: %s\n' "$OUT_DIR" >&2

PIDS=()
for i in "${!SLUGS[@]}"; do
  run_review "${SLUGS[$i]}" "${TITLES[$i]}" "${INSTRUCTIONS[$i]}" &
  PIDS+=("$!")
done

FAILED=0
for pid in "${PIDS[@]}"; do
  if ! wait "$pid"; then
    FAILED=1
  fi
done

for slug in "${SLUGS[@]}"; do
  printf '\n===== Claude %s =====\n' "$slug"
  if [ -s "$OUT_DIR/$slug.out.md" ]; then
    cat "$OUT_DIR/$slug.out.md"
  elif [ -s "$OUT_DIR/$slug.partial.md" ]; then
    printf '[partial output only]\n'
    cat "$OUT_DIR/$slug.partial.md"
  else
    printf '[no final output]\n'
  fi

  if [ -s "$OUT_DIR/$slug.status.txt" ]; then
    printf '\n--- status ---\n'
    cat "$OUT_DIR/$slug.status.txt"
  fi

  if [ -s "$OUT_DIR/$slug.err.txt" ]; then
    printf '\n--- stderr ---\n'
    cat "$OUT_DIR/$slug.err.txt"
  fi
  printf '\n'
done

printf '\nClaude review artifacts: %s\n' "$OUT_DIR" >&2
exit "$FAILED"
