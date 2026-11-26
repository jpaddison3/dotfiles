# bb-wide instructions (symlinked to ~/.bb/AGENTS.md)

- bb expands `$BB_THREAD_STORAGE` only inside ui blocks (`Load()`, `Image()`, `Snippet()`). Anywhere else you show me a path under it, such as a Markdown link or a path in prose, expand the variable yourself and write the absolute path; a link to `$BB_THREAD_STORAGE/brief.md` shows "File not found."
- For evals, probes, and parallel checks whose results are yours to handle, pass
  `--parent-self --parent-notifications auto --lifecycle-owner-thread "$BB_THREAD_ID" --visibility hidden`
  to `bb thread spawn`. This keeps the helper under your Ready row, reports its outcome to you,
  and archives it with your thread. For a read-only check against your current files, pass your
  environment ID to `--environment` (`bb thread show --self` shows it). Give checks that switch
  revisions or write files their own worktree. Omit `--plan` and tell the helper to report plans,
  questions, or findings in plain text. Cards, prompts, or errors can put the row on my turn,
  so handle blockers in your thread and archive temporary helpers after collecting their outcomes.
  Reserve top-level threads for work meant for me, since they can put a separate row on my turn.
- Playwright browsers (Chromium, WebKit) crash within a second of launch inside the agent sandbox,
  both Claude's and Codex's, because the sandbox blocks the Mach port registration they need at
  startup. It isn't flakiness. For browsing, screenshots and page checks that don't need my
  sign-ins or open tabs, use `bb browser-automation open --backend local --machine Apophis --headless`;
  bb starts that browser outside the sandbox. Scripts that must call Playwright directly, such as
  e2e tests, should run outside the sandbox from the first attempt.
- A browser task that needs my sign-ins or open tabs goes to my Chrome, not the headless
  browser, even if the request never mentions Chrome. In BB Codex, use the `bb-chrome` skill:
  "The browser access host is unavailable" or "Chrome isn't approved" means following its
  recovery, not that Chrome is unavailable. Report any blocker at the step where it happens;
  don't switch browsers.
