---
name: meeting-options
description: Present candidate meeting times to JP as a rendered Google-Calendar-style week view (like typing guests into "Meet with…"), with every guest's events overlaid in their own color and the options marked A/B/C, opened in Orca. Use whenever you propose times for a meeting, ask JP to pick a slot, or recommend when to book something with other people.
---
# meeting-options

JP picks times faster from a picture than from a list of slots. Whenever you put meeting options in front of him, render them over the guests' calendars and open the image. Then give your recommendation in text as usual.

## Steps

1. **Pull calendars.** For JP and each guest, call the Google Calendar connector's `list_events` with `calendarId` set to the guest's email, over the week you're showing. Colleagues' 80k calendars are usually readable. Check `80k-org-chart` if you aren't sure who someone is.
2. **Pick the options yourself.** Choose 2–4 slots that are free for everyone and sensible in each person's local hours (JP's day starts at 9:30am ET). Mark your pick with `"recommended": true`, and give every option a short `note` saying why it's there or what it costs.
   - **Free means free.** Don't count a slot as open just because the meeting in it looks movable, optional, or overlaps the same people. If an option does sit on top of an existing event, it displaces that event. Say so in the option's `note` (for example "moves Luca 1:1 → Wed 12pm"), and in your text name each displaced meeting, who owns it, and where it would go. Prefer rescheduling over canceling, and treat 1:1s and other people's own blocks as costly to move unless you have evidence otherwise.
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
   - **Check every option for overlap.** For each option, list the events from every person's calendar that intersect it, working from the data rather than the picture. Then confirm in the PNG that each of those events' titles is still readable under the option box and its label. If a label collides with an event title, or titles are truncated past recognition, fix it before showing JP: shorten the event titles in the spec, or put the displaced meetings in the option's `note` so the legend spells them out. Your text should never mention a displaced meeting that the picture hides.

## Notes

- Your own calendar's connector times come back with the calendar's offset (often `+01:00` London). Convert carefully when transcribing, or pass the offset through unchanged.
- Shared meetings appear once per attendee, side by side, the same way Google's Meet-with view shows them.
- Use `"busy_only": true` on a person to hide their titles, for example when the image might be shared.
- Rendering needs Google Chrome at its default path. It runs headless.
- In Codex, run `render.py` with escalated execution from the start. Headless Chrome and `orca file open` both fail inside the sandbox.
