---
name: bb-chrome
description: In BB Codex, use the ChatGPT browser extension when asked to use Google Chrome or inspect an existing Chrome tab or signed-in Chrome session.
---

# Chrome in BB Codex

For webpage tasks in the user's Chrome session, use the Chrome extension before any native Computer Use. Start with the session's official Chrome or unified Browser skill if it is available and supports extension-backed Chrome. Follow its instructions for selecting Chrome and working with existing tabs.

If that skill is missing or the session's browser host is unavailable, read the complete `skills/control-chrome/SKILL.md` under:

```text
/Applications/ChatGPT.app/Contents/Resources/plugins/openai-bundled/plugins/chrome/
```

Follow its bootstrap, importing `scripts/browser-client.mjs` by absolute path from that same bundle in the Codex Node tool. Use the explicit Chrome selection, `agent.browsers.get("chrome")`, and read its documentation before interacting with a tab. For an explicit tab mention, follow the vendor's exact-tab matching instructions. For an ordinary request about an already open tab, match it in the extension's open-tab list and claim it through the documented API.

Let the extension handle tab and site access. If it denies access, surface the denial without retrying through another client. Keep the user's requested Chrome session and respect any instruction to avoid native Computer Use. Another browser, native app control, and a fresh browser profile cannot substitute for the requested session.

If blocked, report the observed Chrome-specific blocker and the corresponding setup step:

- **App bundle missing or incomplete.** Install or update the ChatGPT desktop app in `/Applications`.
- **Extension connection failed.** Follow the bundled Chrome troubleshooting instructions. If the extension is missing or disabled, direct the user to ChatGPT Settings → Computer Use to install or enable the extension in the relevant Chrome profile.
- **Tab or sign-in missing.** Have the user open the target tab and sign in, if needed, in the Chrome profile with the connected extension.
- **Site access blocked.** Point to Manage beside Chrome in ChatGPT Settings → Computer Use so the user can review access for that site.

See the [ChatGPT browser extension guide](https://learn.chatgpt.com/docs/chrome-extension) for setup and permissions.
