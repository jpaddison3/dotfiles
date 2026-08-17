---
name: linear
description: Interact with Linear — issues, teams, projects, cycles, milestones, initiatives, labels, documents. Use whenever JP wants to read or modify Linear data (look up or edit an issue, list issues, comment, find a project, etc.).
---

# linear

Use the `linear` CLI — an agent-friendly wrapper over the Linear API.

Run `linear -h` for the top-level commands, then `linear <command> --help` to drill in. `linear api` makes raw GraphQL API requests for anything the subcommands don't cover.

**Comments: `linear issue comment add <ID> --body-file <path>`** (`-b` for
short bodies); read back with `linear issue comment list <ID>`. There is no
top-level `comment` command — `linear comment …` fails loudly (exit 2, error
on stderr). The 2026-08-07 "silent no-op" was not the CLI: the writes were
piped (`2>&1 | tail -1`), which masked the exit code and truncated the error
away. **Never pipe a write command's output** — run it bare so exit status
and stderr survive, and read-back verify writes that matter.
Also remember `linear issue update -l` REPLACES the full label set.

No need to set priority levels unless asked. If something is tagged with
`agent-*`, add it to ToDo on creation rather than Triage.
