#!/usr/bin/env python3
"""Pull Granola meeting transcripts + summaries into automated-inputs/meeting-transcripts/.

Wraps the `granola` CLI (https://github.com/magarcia/granola-cli). Requires a
one-time `granola auth login` beforehand so the CLI has your desktop-app
credentials in the keychain.

Usage:
    ./pull-granola.py                    # today's meetings (local date)
    ./pull-granola.py 2026-04-20         # a specific date
    ./pull-granola.py --id <uuid>        # a specific meeting
    ./pull-granola.py --force            # overwrite existing output files
    ./pull-granola.py --dry-run          # show what would be written, don't write

Output: automated-inputs/meeting-transcripts/YYYY-MM-DD-<slug>-granola.md
The `-granola` suffix keeps these from colliding with Google Meet outputs.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

DEFAULT_OUT_DIR = (
    Path.home() / "80k/ai-products-research/automated-inputs/meeting-transcripts"
)
GRANOLA = "granola"


NOT_FOUND_PREFIXES = ("no transcript found", "no enhanced notes found")


def granola(*args: str) -> tuple[str, str, int]:
    """Run the granola CLI. Returns (stdout, stderr, returncode). Callers handle errors.

    The CLI emits "No transcript found for ..." / "No enhanced notes found ..." to
    stderr with rc != 0; those are expected and should be treated as empty, not errors.
    """
    result = subprocess.run(
        [GRANOLA, "--no-pager", *args], capture_output=True, text=True
    )
    stderr = (result.stderr or "").strip()
    if result.returncode != 0 and not stderr.lower().startswith(NOT_FOUND_PREFIXES):
        print(f"granola {' '.join(args)}: {stderr}", file=sys.stderr)
    return result.stdout, stderr, result.returncode


def list_meetings_on(day: str) -> list[dict]:
    out, _, rc = granola(
        "meeting", "list", "--date", day, "-o", "json", "--limit", "100"
    )
    if rc != 0:
        sys.exit(f"failed to list meetings for {day}")
    return json.loads(out) if out.strip() else []


def fetch_transcript(meeting_id: str) -> str:
    """Transcript text with speaker labels. Empty string if unavailable."""
    out, _, rc = granola("meeting", "transcript", meeting_id, "--timestamps")
    return out.rstrip() + "\n" if rc == 0 and out.strip() else ""


def fetch_summary(meeting_id: str) -> str:
    out, _, rc = granola("meeting", "enhanced", meeting_id)
    return out.rstrip() + "\n" if rc == 0 and out.strip() else ""


def slugify(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return s or "untitled"


def _person_name(p: dict | None) -> str | None:
    if not p:
        return None
    name = (((p.get("details") or {}).get("person") or {}).get("name") or {}).get(
        "fullName"
    ) or p.get("name")
    if name:
        return name
    email = p.get("email") or ""
    return email_to_name(email) if email else None


def extract_attendees(meeting: dict) -> list[str]:
    """Return attendee display names, including the creator (which is often JP)."""
    people = meeting.get("people") or {}
    names: list[str] = []
    if n := _person_name(people.get("creator")):
        names.append(n)
    for p in people.get("attendees") or []:
        if n := _person_name(p):
            names.append(n)
    if names:
        return dedupe_preserve_order(names)

    # Fallback: google_calendar_event.attendees → emails only
    gce = meeting.get("google_calendar_event") or {}
    for a in gce.get("attendees") or []:
        if email := a.get("email"):
            names.append(email_to_name(email))
    return dedupe_preserve_order(names)


def email_to_name(email: str) -> str:
    local = email.split("@", 1)[0]
    # "jp.addison" → "JP Addison"; "louise.verkin" → "Louise Verkin"
    parts = [p for p in re.split(r"[._-]+", local) if p]
    return " ".join(p.upper() if len(p) <= 2 else p.capitalize() for p in parts)


def dedupe_preserve_order(xs: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in xs:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def meeting_date(meeting: dict) -> str:
    """Prefer the calendar event start date (local-ish) over created_at UTC."""
    gce = meeting.get("google_calendar_event") or {}
    start = (gce.get("start") or {}).get("dateTime") or (gce.get("start") or {}).get(
        "date"
    )
    if start:
        return start[:10]
    return (meeting.get("created_at") or "")[:10]


def render(meeting: dict, summary: str, transcript: str) -> str:
    title = meeting.get("title") or "Untitled meeting"
    d = meeting_date(meeting) or "unknown-date"
    attendees = extract_attendees(meeting)
    mid = meeting["id"]

    fm_lines = [
        "---",
        f"date: {d}",
        "tags: [meeting-transcript, daily, granola]",
        "source: granola",
        "status: raw",
        f"meeting: {json.dumps(title, ensure_ascii=False)}",
        f"attendees: [{', '.join(attendees)}]" if attendees else "attendees: []",
        f"granola_id: {mid}",
        f"granola_url: https://notes.granola.ai/d/{mid}",
        "---",
        "",
        f"# {title} — {d}",
    ]

    body: list[str] = []
    if summary:
        body += ["", "## Summary", "", summary.rstrip()]
    if transcript:
        body += ["", "## Transcript", "", transcript.rstrip()]
    if not summary and not transcript:
        body += ["", "_No summary or transcript available for this meeting._"]

    return "\n".join(fm_lines + body) + "\n"


def process_meeting(
    meeting: dict, *, out_dir: Path, force: bool, dry_run: bool
) -> tuple[str, Path | None]:
    """Returns (status_label, path_written_or_None)."""
    mid = meeting["id"]
    d = meeting_date(meeting)
    title = meeting.get("title") or "untitled"
    slug = slugify(title)
    out_path = out_dir / f"{d}-{slug}-granola.md"

    if out_path.exists() and not force:
        return (f"skip (exists): {out_path.name}", None)

    transcript = fetch_transcript(mid)
    summary = fetch_summary(mid)

    if not transcript and not summary:
        return (f"skip (empty): {title} [{mid[:8]}]", None)

    content = render(meeting, summary, transcript)

    if dry_run:
        return (f"DRY-RUN would write {len(content)} bytes to {out_path.name}", None)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content)
    parts = []
    if summary:
        parts.append("summary")
    if transcript:
        parts.append(f"transcript ({transcript.count(chr(10))} lines)")
    return (f"wrote {out_path.name} [{' + '.join(parts)}]", out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("date", nargs="?", default=date.today().isoformat())
    ap.add_argument("--id", help="Pull a single meeting by ID (ignores date)")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files")
    ap.add_argument(
        "--dry-run", action="store_true", help="Show what would be written"
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR})",
    )
    args = ap.parse_args()

    if args.id:
        # `meeting list` has no by-ID filter; sweep recent windows until we find it.
        from datetime import timedelta

        meeting: dict | None = None
        for back in (7, 30, 90, 365):
            since = (date.today() - timedelta(days=back)).isoformat()
            out, _, rc = granola(
                "meeting", "list", "--since", since, "-o", "json", "--limit", "500"
            )
            if rc == 0 and out.strip():
                for m in json.loads(out):
                    if m["id"] == args.id:
                        meeting = m
                        break
            if meeting:
                break
        if not meeting:
            sys.exit(f"meeting {args.id} not found in your Granola account")
        status, _ = process_meeting(
            meeting, out_dir=args.out_dir, force=args.force, dry_run=args.dry_run
        )
        print(status)
        return 0

    meetings = list_meetings_on(args.date)
    if not meetings:
        print(f"No Granola meetings on {args.date}.")
        return 0

    print(f"{len(meetings)} meeting(s) on {args.date}:")
    for m in meetings:
        status, _ = process_meeting(
            m, out_dir=args.out_dir, force=args.force, dry_run=args.dry_run
        )
        print(f"  {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
