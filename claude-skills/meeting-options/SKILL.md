---
name: meeting-options
description: Present candidate meeting times to JP as a rendered Google-Calendar-style week view (like typing guests into "Meet with…"), with every guest's events overlaid in their own color and the options marked A/B/C, opened in Orca. Use whenever you propose times for a meeting, ask JP to pick a slot, or recommend when to book something with other people.
---
# meeting-options

JP picks times faster from a picture than from a list of slots. Whenever you put meeting options in front of him, render them over the guests' calendars and open the image. Then give your recommendation in text as usual.

## Steps

1. **Pull calendars.** For JP and each guest, call the Google Calendar connector's `list_events` with `calendarId` set to the guest's email, over the week you're showing. Colleagues' 80k calendars are usually readable. Check `80k-org-chart` if you aren't sure who someone is.
2. **Pick the options yourself.** Choose 2–4 slots that are free for everyone and sensible in each person's local hours. Mark your pick with `"recommended": true`, and give every option a short `note` saying why it's there or what it costs.
3. **Write a spec** to your scratchpad. The full schema is in the docstring of `render.py`. For each person, pass either:
   - `gcal_json`: the path of a `list_events` result the harness saved to a file. Large results are saved automatically, so this costs nothing.
   - `events`: a compact list of `{title, start, end, status}`, transcribed from a result that came back inline.

   Times are ISO 8601. A time without an offset is read in `tz`. Status is `accepted` (default), `needsAction`/`tentative` (drawn as an outline), or `free` (drawn as a light tint). Leave out declined events. Use a bare date for all-day events. Set `secondary_tz` when a guest is in another time zone, for example `Europe/London` for Huon, so the second gutter shows their local time.
4. **Render and open:**
   ```bash
   python3 ~/.claude/skills/meeting-options/render.py <spec.json> --open
   ```
   Run it from inside the current worktree. Orca only opens files inside the worktree, so `--open` copies the PNG into `<worktree>/.meeting-options/`, adds that folder to the repo's local `.git/info/exclude`, and runs `orca file open`. That opens a tab without moving JP's view. Add `--focus` only if JP asked to be taken to it. Outside Orca, the image opens in Preview instead. Never run `orca open`.
5. **Check the PNG yourself** with Read before telling JP it's open. Look for clipped or mislabeled options and events at the wrong times.

## Notes

- Your own calendar's connector times come back with the calendar's offset (often `+01:00` London). Convert carefully when transcribing, or pass the offset through unchanged.
- Shared meetings appear once per attendee, side by side, the same way Google's Meet-with view shows them.
- Use `"busy_only": true` on a person to hide their titles, for example when the image might be shared.
- Rendering needs Google Chrome at its default path. It runs headless.
- In Codex, run `render.py` with escalated execution from the start. Headless Chrome and `orca file open` both fail inside the sandbox.
