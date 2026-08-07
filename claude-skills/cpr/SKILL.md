---
name: cpr
description: Commit the current intended changes, push them, and create a GitHub pull request. Use when the user asks to commit and open a PR, publish the current work as a PR, or invokes cpr.
---

# Commit and Create PR

Stage changes, commit, and create a GitHub pull request.

1. Read the applicable repository and agent instructions, including `AGENTS.md`
   and `CLAUDE.md` where present. Follow the host environment's higher-priority
   branch and worktree rules.
2. Inspect the status, diff, recent log, current branch, and remote. Include only
   changes that belong to the user's requested work; do not bundle unrelated
   changes.
3. Handle the branch before committing:
   - If the host provides managed worktree or target-branch tooling, inspect and
     use it as instructed. Do not create a worktree merely because the current
     branch is the default branch.
   - In an unmanaged repository, create a descriptive branch when the current
     branch is the default branch and repository policy does not permit direct
     commits.
   - If a required branch change needs explicit user authorization under the
     host's rules, stop and ask.
4. Run the relevant local checks when practical, then stage and commit the
   intended changes. Follow repository conventions and the user's commit
   preferences; do not bypass hooks.

In an unmanaged repository, consider improving a stale or generic branch name
when it has no commits ahead of the base branch and has not been pushed. Do not
rename a branch managed by the host environment outside its prescribed workflow.

Add exactly one co-author trailer appropriate to the agent making the commit:

- When running in Claude: `Co-authored-by: Claude <noreply@anthropic.com>`
- When running in Codex: `Co-authored-by: OpenAI Codex <codex@openai.com>`

Push the branch and create a non-draft PR with `gh`. Use the repository's pull
request template when present; otherwise summarize the actual diff and tests.
Do not create a separate PR-description file or ask the user to pre-review the
description. Do not pass `--draft` unless the user explicitly asks for a draft
PR.
