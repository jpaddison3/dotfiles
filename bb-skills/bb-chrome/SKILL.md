---
name: bb-chrome
description: BB Codex only. Use the ChatGPT browser extension when asked to use Google Chrome or inspect an existing Chrome tab or signed-in Chrome session.
---

# Chrome in BB Codex

In other BB providers, follow that provider's browser instructions. In BB Codex, select extension-backed Chrome explicitly for webpage tasks in the user's Chrome session. If native Computer Use has already reported that Chrome was not approved, continue with the extension path.

Choose the source before starting the browser client. Prefer the session's OpenAI `control-chrome` or Browser skill when its bootstrap client file exists and its browser selection instructions document a selector scoped to Chrome. Older clients may document only the generic extension selector. Treat those clients and sessions with only BB Browser Automation as missing a usable Chrome integration.

If the session has no usable Chrome integration, or it reports “The browser access host is unavailable” before connecting to Chrome, read the complete `skills/control-chrome/SKILL.md` from the installed ChatGPT app bundle:

```text
/Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled/plugins/chrome/
```

If ChatGPT is installed in `~/Applications`, use the corresponding path there. Follow the official bootstrap, importing `scripts/browser-client.mjs` by absolute path from the same bundle in the Codex Node tool. For the vendor's availability rule, `bb-chrome` counts as the listed Chrome skill in BB Codex. Chrome still needs to connect successfully through the extension.

For an explicit tab mention, follow the vendor's exact-tab matching instructions. For a plain Chrome request, use the selected skill's documented Chrome family selector. Read the selected browser's documentation before interacting with a tab. To use an already open tab, match it in the extension's open-tab list and claim it through the documented API.

Let the extension handle tab and site access. If it denies access, surface the denial without retrying through another client. Keep the user's requested Chrome session and respect any instruction to avoid native Computer Use. Another browser, native app control, and a fresh browser profile cannot substitute for the requested session.

If blocked, report the observed Chrome-specific blocker and the corresponding setup step:

- **App bundle missing, incomplete, or lacking Chrome selection.** Install or update the ChatGPT desktop app.
- **Browser tooling unavailable.** Follow the bundled instructions to discover `node_repl js`. If it's still unavailable, explain that this BB session lacks the tooling to connect to the Chrome extension and suggest a fresh local BB Codex thread.
- **Extension connection failed.** Follow the bundled Chrome troubleshooting instructions for the specific failure, including steps to enable the extension in the relevant Chrome profile if needed.
- **Wrong Chrome profile.** If the target tab is in a different profile, have the user connect the extension in that profile or open the tab in the connected profile.
- **Tab or sign-in missing.** If the tab cannot be matched, ask the user to confirm the profile and whether the tab is open. If the page asks for sign-in, have the user sign in in that Chrome profile.
- **Site access blocked.** Direct the user to review access for that site in ChatGPT's Chrome website permissions. Use the extension guide below for the current settings path.

See the [ChatGPT browser extension guide](https://learn.chatgpt.com/docs/chrome-extension) for setup and permissions.
