---
name: sentry
description: Interact with Sentry — issues, errors, events, traces, releases, projects, dashboards. Use whenever JP wants to read or modify Sentry data (triage an issue, look up an error, inspect a trace, manage a release, etc.).
---

# sentry

Use the `sentry` CLI — Sentry's official command-line interface.

Run `sentry -h` for the top-level commands, then `sentry <command> --help` to drill in. Add `--json` for machine-readable output. `sentry api <endpoint>` makes raw authenticated API requests, and `sentry schema` browses the API schema.

## Correlate with BetterStack

When investigating a failure, it's often worth calling `betterheap` — the BetterStack CLI — to pull logs and telemetry from around the time of the error, for more context on the surrounding failure than Sentry alone gives. Run `betterheap -h` to discover its commands. (It's in active development, so expect rough edges or missing features.)
