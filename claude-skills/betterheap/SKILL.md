---
name: betterheap
description: Query Better Stack Telemetry logs — errors, warnings, full-text search, request traces, tail, stats. Use whenever JP wants to look at logs or investigate the context around a failure (what happened around an error, logs for a request id, recent errors, etc.).
---

# betterheap

Use the `betterheap` CLI — it queries Better Stack Telemetry logs as one continuous window across the live hot buffer and the S3 archive, so the time range you ask for is the time range you get.

Run `betterheap -h` for the top-level commands, then `betterheap <command> --help` to drill in. Add `--format json` (or `ndjson`) for machine-readable output, and `betterheap schema` dumps the field map and output fields. Useful starting points: `betterheap errors --since 7d`, `betterheap search "<text>" --since 14d`, `betterheap trace <request-id>` (all logs for one request, merged by time).

When investigating a Sentry failure, reach for this to pull the surrounding logs.
