#!/Users/jpaddison/Documents/dotfiles/py313/bin/python3
"""Fetch all review data for a GitHub PR and output human-readable text.

Usage:
    ./fetch-pr-reviews.py https://github.com/owner/repo/pull/123
    ./fetch-pr-reviews.py owner/repo 123
    ./fetch-pr-reviews.py          # auto-detect from current branch
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone


# Bots whose issue comments are pure noise (deploy previews, coverage, CI status)
NOISE_BOTS = {"vercel", "netlify", "codecov", "github-actions"}

# Known review bots we track status for
KNOWN_REVIEW_BOTS = {"gemini", "copilot"}


def run_gh(args: list[str]) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error running gh {' '.join(args)}:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout


def parse_paginated_json(raw: str) -> list:
    """Parse gh --paginate output which concatenates JSON arrays.

    gh --paginate outputs multiple JSON arrays concatenated, e.g.:
    [{"a":1}][{"b":2}]

    We need to split on ][ boundaries and parse each chunk.
    """
    raw = raw.strip()
    if not raw:
        return []

    # Try parsing as a single array first (common case: single page)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Split on ][ boundaries — find positions where ] is immediately followed by [
    results = []
    # Use a simple approach: replace ][ with ]\n[ then split
    chunks = raw.replace("][", "]\n[").split("\n")
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk:
            results.extend(json.loads(chunk))
    return results


def parse_pr_args(args: list[str]) -> tuple[str, str, int]:
    """Parse command-line args into (owner, repo, pr_number).

    Supports:
    - https://github.com/owner/repo/pull/123
    - owner/repo 123
    - (no args) auto-detect from current branch
    """
    if not args:
        # Auto-detect from current branch
        raw = run_gh(["pr", "view", "--json", "url", "--jq", ".url"])
        url = raw.strip()
        return parse_pr_url(url)

    if len(args) == 1:
        return parse_pr_url(args[0])

    if len(args) == 2:
        owner_repo, number = args
        if "/" in owner_repo:
            owner, repo = owner_repo.split("/", 1)
            return owner, repo, int(number)

    print(f"Usage: {sys.argv[0]} [PR_URL | owner/repo number]", file=sys.stderr)
    sys.exit(1)


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Extract owner, repo, number from a GitHub PR URL."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if not m:
        print(f"Could not parse PR URL: {url}", file=sys.stderr)
        sys.exit(1)
    return m.group(1), m.group(2), int(m.group(3))


def fetch_endpoint(owner: str, repo: str, endpoint: str) -> list:
    """Fetch a paginated GitHub API endpoint."""
    raw = run_gh([
        "api", "--paginate",
        f"repos/{owner}/{repo}/{endpoint}",
    ])
    return parse_paginated_json(raw)


def classify_bot(login: str) -> str | None:
    """Return the known bot name if login matches, else None."""
    login_lower = login.lower()
    if "gemini" in login_lower or login_lower.startswith("google-labs"):
        return "gemini"
    if "copilot" in login_lower:
        return "copilot"
    return None


def is_noise_bot(login: str) -> bool:
    """Check if a login belongs to a noise bot we should filter out."""
    login_lower = login.lower()
    return any(bot in login_lower for bot in NOISE_BOTS)


def is_gemini_boilerplate_comment(body: str) -> bool:
    """Detect Gemini's summary-of-changes issue comment (not the actual review)."""
    if not body:
        return False
    # Gemini posts a "Summary of Changes" or "Summary" issue comment
    # that duplicates info from its actual review
    first_lines = body[:300].lower()
    return "summary of changes" in first_lines or (
        first_lines.startswith("## summary") and "key changes" in first_lines
    )


def compute_bot_status(reviews: list, review_comments: list, issue_comments: list) -> dict:
    """Determine which known bots have posted reviews."""
    status = {}
    for bot_name in KNOWN_REVIEW_BOTS:
        status[bot_name] = {"status": "not_seen", "review_count": 0}

    # Check reviews
    for r in reviews:
        login = r.get("user", {}).get("login", "")
        bot = classify_bot(login)
        if bot:
            status[bot]["review_count"] += 1
            status[bot]["status"] = "reviewed"

    # Check review comments (inline)
    for c in review_comments:
        login = c.get("user", {}).get("login", "")
        bot = classify_bot(login)
        if bot and status[bot]["status"] == "not_seen":
            status[bot]["status"] = "reviewed"

    return status


def compute_readiness(bot_status: dict, age_minutes: float) -> dict:
    """Compute readiness heuristics for the AI to use."""
    gemini_reviewed = bot_status.get("gemini", {}).get("status") == "reviewed"
    copilot_reviewed = bot_status.get("copilot", {}).get("status") == "reviewed"

    reasons = []
    is_likely_complete = True

    if gemini_reviewed:
        reasons.append("gemini has reviewed")
    elif age_minutes < 5:
        reasons.append("gemini hasn't reviewed yet (PR is very new)")
        is_likely_complete = False
    else:
        reasons.append("gemini hasn't reviewed (may not be enabled)")

    if copilot_reviewed:
        reasons.append("copilot has reviewed")
    elif age_minutes < 10:
        reasons.append("copilot hasn't reviewed yet (typically takes ~6 min)")
        is_likely_complete = False
    else:
        reasons.append("copilot hasn't reviewed (may not have been triggered)")

    return {
        "is_likely_complete": is_likely_complete,
        "reason": f"PR is {int(age_minutes)} min old; " + "; ".join(reasons),
    }


def format_output(
    pr_meta: dict,
    age_minutes: float,
    bot_status: dict,
    readiness: dict,
    reviews: list,
    review_comments: list,
    issue_comments: list,
) -> str:
    """Format all PR review data as human-readable text."""
    lines = []

    # Header
    lines.append(f"# PR Review Data: {pr_meta['title']}")
    lines.append(f"URL: {pr_meta['url']}")
    lines.append(f"Created: {pr_meta['created_at']} ({int(age_minutes)} minutes ago)")
    lines.append("")

    # Readiness
    lines.append(f"## Readiness")
    complete_str = "YES" if readiness["is_likely_complete"] else "NO"
    lines.append(f"Likely complete: {complete_str}")
    lines.append(readiness["reason"])
    lines.append("")

    # Bot status
    lines.append("## Bot Status")
    for bot, info in bot_status.items():
        if info["status"] == "reviewed":
            lines.append(f"- {bot}: reviewed ({info['review_count']} review(s))")
        else:
            lines.append(f"- {bot}: not seen")
    lines.append("")

    # Counts
    lines.append(f"## Counts")
    lines.append(f"- Reviews: {len(reviews)}")
    lines.append(f"- Inline review comments: {len(review_comments)}")
    lines.append(f"- Discussion comments: {len(issue_comments)}")
    lines.append("")

    # Reviews
    if reviews:
        lines.append("## Reviews")
        for r in reviews:
            user = r.get("user", {}).get("login", "unknown")
            state = r.get("state", "")
            submitted = r.get("submitted_at", "")
            body = (r.get("body") or "").strip()
            lines.append(f"### {user} ({state}) — {submitted}")
            if body:
                lines.append(body)
            else:
                lines.append("(no body)")
            lines.append("")

    # Review comments grouped by file
    if review_comments:
        lines.append("## Inline Review Comments")
        by_file: dict[str, list] = {}
        for c in review_comments:
            path = c.get("path", "(unknown file)")
            by_file.setdefault(path, []).append(c)

        for path, comments in by_file.items():
            lines.append(f"### {path}")
            for c in comments:
                user = c.get("user", {}).get("login", "unknown")
                line_num = c.get("line") or c.get("original_line") or "?"
                body = (c.get("body") or "").strip()
                reply_to = c.get("in_reply_to_id")
                reply_str = f" (reply to #{reply_to})" if reply_to else ""
                lines.append(f"**{user}** at line {line_num}{reply_str}:")
                lines.append(body)
                lines.append("")

    # Issue comments
    if issue_comments:
        lines.append("## Discussion Comments")
        for c in issue_comments:
            user = c.get("user", {}).get("login", "unknown")
            created = c.get("created_at", "")
            body = (c.get("body") or "").strip()
            lines.append(f"### {user} — {created}")
            lines.append(body)
            lines.append("")

    if not reviews and not review_comments and not issue_comments:
        lines.append("No reviews or comments found.")

    return "\n".join(lines)


def main():
    owner, repo, pr_number = parse_pr_args(sys.argv[1:])

    # Fetch PR metadata
    pr_raw = run_gh([
        "api", f"repos/{owner}/{repo}/pulls/{pr_number}",
        "--jq", '{url: .html_url, title: .title, created_at: .created_at}',
    ])
    pr_meta = json.loads(pr_raw)

    # Compute age
    created = datetime.fromisoformat(pr_meta["created_at"].replace("Z", "+00:00"))
    age_minutes = (datetime.now(timezone.utc) - created).total_seconds() / 60

    # Fetch all three endpoints
    reviews_raw = fetch_endpoint(owner, repo, f"pulls/{pr_number}/reviews")
    review_comments_raw = fetch_endpoint(owner, repo, f"pulls/{pr_number}/comments")
    issue_comments_raw = fetch_endpoint(owner, repo, f"issues/{pr_number}/comments")

    # Filter issue comments: remove noise bots and Gemini boilerplate
    issue_comments_filtered = [
        c for c in issue_comments_raw
        if not is_noise_bot(c.get("user", {}).get("login", ""))
        and not is_gemini_boilerplate_comment(c.get("body", ""))
    ]

    # Bot status and readiness
    bot_status = compute_bot_status(reviews_raw, review_comments_raw, issue_comments_raw)
    readiness = compute_readiness(bot_status, age_minutes)

    print(format_output(
        pr_meta, age_minutes, bot_status, readiness,
        reviews_raw, review_comments_raw, issue_comments_filtered,
    ))


if __name__ == "__main__":
    main()
