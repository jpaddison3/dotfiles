---
name: gdoc
description: Interact with Google Docs & Drive — read, edit, search, comment, share, create docs, list/pull/push content. Use whenever JP wants to read or modify a Google Doc or Drive file (fetch a doc's text, leave a comment, find a file, etc.).
---

# gdoc

Use the `gdoc` CLI — a CLI for Google Docs & Drive.

Run `gdoc -h` for the top-level commands, then `gdoc <command> --help` to drill in. Add `--json` for machine-readable output.

## Gotcha: multi-tab docs

Google Docs can have multiple tabs (left-sidebar), each effectively its own document body, and **`gdoc cat` can silently miss tabs** — it sometimes prints `# Tab 1` markers and sometimes drops whole tabs with no indication (observed on v0.7.6, where it returned an old "(ignore)" tab and never showed the "Final Copy" tab the user's link pointed at).

- A doc URL with a `?tab=t.XXXX` param pins a specific tab — that tab is the one that matters. Don't ignore the param.
- Before trusting `gdoc cat` on a doc that has (or might have) tabs, enumerate them via the Docs API using gdoc's own stored OAuth creds (`~/.config/gdoc/token.json`, venv python `/Users/jpaddison/.local/share/uv/tools/gdoc/bin/python3`):
  `documents().get(documentId=…, includeTabsContent=True)` → walk `tabs[].tabProperties` (`tabId`, `title`, nested `childTabs`), match the URL's tab id, and extract that tab's `documentTab.body.content`.
- Never print the token file's contents.
