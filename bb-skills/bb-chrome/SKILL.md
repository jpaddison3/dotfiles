---
name: bb-chrome
description: In BB Codex, use the ChatGPT browser extension when asked to use Google Chrome or inspect an existing Chrome tab or signed-in Chrome session.
---

# Chrome in BB Codex

Use this skill only in Codex threads in BB. For webpage tasks in the user's Chrome session, select extension-backed Chrome explicitly. Start with the session's official Chrome or unified Browser skill if it supports that connection. If native Computer Use has already reported that Chrome was not approved, continue with the extension path.

If that skill is missing or the session reports “The browser access host is unavailable,” read the complete `skills/control-chrome/SKILL.md` from the installed ChatGPT app bundle:

```text
/Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled/plugins/chrome/
```

If ChatGPT is installed in `~/Applications`, use the corresponding path there. Follow the official bootstrap, importing `scripts/browser-client.mjs` by absolute path from the same bundle in the Codex Node tool. This BB skill supplies the Chrome instructions when the official skill is absent from the session. Try the explicit Chrome selector, `agent.browsers.get("chrome")`, even if `bb-chrome` is the only listed Chrome skill, and read the browser documentation before interacting with a tab.

For an explicit tab mention, follow the vendor's exact-tab matching instructions. For an ordinary request about an already open tab, match it in the extension's open-tab list and claim it through the documented API.

Let the extension handle tab and site access. If it denies access, surface the denial without retrying through another client. Keep the user's requested Chrome session and respect any instruction to avoid native Computer Use. Another browser, native app control, and a fresh browser profile cannot substitute for the requested session.

If blocked, report the observed Chrome-specific blocker and the corresponding setup step:

- **App bundle missing or incomplete.** Install or update the ChatGPT desktop app.
- **Extension connection failed.** Follow the bundled Chrome troubleshooting instructions. If the extension is missing or disabled, direct the user to ChatGPT Settings → Computer Use to install or enable the extension in the relevant Chrome profile.
- **Wrong Chrome profile.** If the target tab is in a different profile, have the user connect the extension in that profile or open the tab in the connected profile.
- **Tab or sign-in missing.** If the tab cannot be matched, ask the user to confirm the profile and whether the tab is open. If the page asks for sign-in, have the user sign in in that Chrome profile.
- **Site access blocked.** Point to Manage beside Chrome in ChatGPT Settings → Computer Use so the user can review access for that site.

See the [ChatGPT browser extension guide](https://learn.chatgpt.com/docs/chrome-extension) for setup and permissions.
