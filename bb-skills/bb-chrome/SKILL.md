---
name: bb-chrome
description: BB Codex only. Use when asked to open a standalone local HTML preview in desktop Google Chrome, browse in Chrome, or use an existing Chrome tab or signed-in Chrome session.
---

# Chrome in BB Codex

In other BB providers, follow that provider's browser instructions. In BB Codex, choose between a file handoff and a browser task before starting a browser client.

## Open a local HTML preview for the user

When the user explicitly asks to open a known, agent-created standalone HTML file for their own viewing in desktop Chrome on their Mac, confirm that the file exists on that Mac and hand it directly to macOS. Pass the exact absolute file path as one shell-quoted argument, including when the name has spaces.

```sh
/usr/bin/open -a "Google Chrome" '/absolute/path/Preview Page.html'
```

Run this launch through the shell's normal approval flow if it needs to run outside the Codex sandbox to reach desktop Chrome. In a sandboxed BB Codex session with an approval option, request that execution up front. Keep the approval scoped to the single launch.

Browser Use limits page URLs to HTTP(S). Its permissions apply to origins by scheme, host, and port, with no way to grant inspection for a single local file. Broad local-file access could expose unrelated private files that Chrome can render. That risk is an inference from the permission model. [OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)

The macOS handoff opens that specific artifact as Finder would. Chrome can run its JavaScript and load its resources, so use this route only for the known artifact. The handoff grants no browser permissions and returns no page content or tab control. Stop when macOS accepts it. Report launch acceptance and claim a visible load only if independently verified. Leave the tab for the user to view.

If the file or Chrome is unavailable, or the command fails, report the specific blocker. When the file exists, give its exact absolute path and tell the user to press **⌘O** in Chrome and select that file.

Carry any Browser Use denial through as issued. Choose the file handoff at the start of a user request specifically for their own viewing. Never switch to `open`, another shell command, or another browser route to fulfill a request that Browser Use has denied.

## Browse or use an existing Chrome session

Select extension-backed Chrome for approved webpage navigation, inspection, and interaction, including requests involving an existing tab or signed-in session. If native Computer Use has already reported that Chrome was not approved, continue with the extension path.

Choose the source before starting the browser client. Prefer the session's OpenAI `control-chrome` or Browser skill when its bootstrap client file exists and its browser selection instructions document a selector scoped to Chrome. Older clients may document only the generic extension selector. Treat those clients and sessions with only BB Browser Automation as missing a usable Chrome integration.

If the session has no usable Chrome integration, or it reports “The browser access host is unavailable” before connecting to Chrome, read the complete `skills/control-chrome/SKILL.md` from the installed ChatGPT app bundle:

```text
/Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled/plugins/chrome/
```

If ChatGPT is installed in `~/Applications`, use the corresponding path there. If the layout has changed, look under the app's bundled plugins directory for the OpenAI skill that documents Chrome family selection and its matching client. Follow that skill's bootstrap and import its client by absolute path from the same bundle in the Codex Node tool. For the vendor's availability rule, `bb-chrome` counts as the listed Chrome skill in BB Codex. Chrome still needs to connect successfully through the extension.

For an explicit tab mention, follow the vendor's exact-tab matching instructions. For a plain Chrome request, use the selected skill's documented Chrome family selector. Read the selected browser's documentation before interacting with a tab. To use an already open tab, match it in the extension's open-tab list and claim it through the documented API.

Let the extension handle tab and site access. If it denies access, surface the denial without retrying through another client. Keep the user's requested Chrome session and respect any instruction to avoid native Computer Use. Another browser, native app control, and a fresh browser profile cannot substitute for the requested session.

If blocked, use the guidance below for the observed Chrome-specific blocker in BB:

- **App bundle missing, incomplete, or lacking Chrome selection.** Install or update the ChatGPT desktop app.
- **Browser tooling unavailable.** Follow the bundled instructions to discover `node_repl js`. If it's still unavailable, explain that this BB session lacks the tooling to connect to the Chrome extension and suggest a fresh local BB Codex thread.
- **Extension connection failed.** Follow the bundled Chrome troubleshooting instructions for the specific failure, including steps to enable the extension in the relevant Chrome profile if needed.
- **Wrong Chrome profile.** If the target tab is in a different profile, have the user connect the extension in that profile or open the tab in the connected profile.
- **Tab or sign-in missing.** If the tab cannot be matched, ask the user to confirm the profile and whether the tab is open. If the page asks for sign-in, have the user sign in in that Chrome profile.
- **Site access blocked.** Direct the user to review access for that site in ChatGPT's Chrome website permissions. Use the extension guide below for the current settings path.

See the [ChatGPT browser extension guide](https://learn.chatgpt.com/docs/chrome-extension) for setup and permissions.
