"""Slack Block Kit layout for CDR Watch messages (design v2, approved 2026-09-14).

Builds blocks only. Plain fallback text and ASCII mapping live in slack.py.
"""

import os

from cdrwatch.models import Alert, RunSummary, Source

MAX_LINES = 15
MAX_CHARS = 300
SECTION_CHARS = 3000
FIELD_CHARS = 2000
HEADER_CHARS = 150
FOOTER = "CDR Watch"
VERIFY = ":warning: Verify the official page before changing site content."

URGENCY_STYLE = {
    "Critical": (":rotating_light:", "Critical"),
    "High": (":large_orange_circle:", "High"),
    "Informational": (":white_circle:", "Informational"),
}
REASONS = {
    "timeout": "The website did not answer in time.",
    "network": "Could not connect to the website.",
    "too_short": "Page content was much shorter than expected - possible redesign.",
    "marker_missing": "Expected text is missing from the page - possible redesign.",
    "challenge_page": "The website showed a bot-check page instead of content.",
}


def clip(line: str) -> str:
    return line if len(line) <= MAX_CHARS else line[: MAX_CHARS - 3] + "..."


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def reason_text(reason: str) -> str:
    if reason.startswith("http_"):
        return f"The website returned HTTP {reason.removeprefix('http_')}."
    return REASONS.get(reason, "Fetch failed.")


def header(text: str) -> dict:
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": text[:HEADER_CHARS], "emoji": True},
    }


def section(md: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": md[:SECTION_CHARS]}}


def fields(pairs: list[tuple[str, str]]) -> dict:
    items = [{"type": "mrkdwn", "text": f"*{k}*\n{v}"[:FIELD_CHARS]} for k, v in pairs]
    return {"type": "section", "fields": items}


def context(md: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": md}]}


def divider() -> dict:
    return {"type": "divider"}


def link(label: str, url: str) -> str:
    return f"<{url}|{esc(label)}>"


def links_row(pairs: list[tuple[str, str | None]]) -> dict | None:
    parts = [f":link: {link(label, url)}" for label, url in pairs if url]
    return section("   |   ".join(parts)) if parts else None


def quote_sections(title: str, lines: tuple[str, ...]) -> list[dict]:
    """Quoted lines split across sections so no section exceeds the Slack limit."""
    if not lines:
        return [section(f"{title}\n>_(none)_")]
    body = [f">{esc(clip(line))}" for line in lines[:MAX_LINES]]
    if len(lines) > MAX_LINES:
        body.append(f"_... {len(lines) - MAX_LINES} more lines in full diff_")
    chunks, current = [], title
    for line in body:
        if len(current) + 1 + len(line) > SECTION_CHARS:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line
    chunks.append(current)
    return [section(c) for c in chunks]


def repo_url(path: str = "") -> str | None:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    return f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}{path}"


def run_url() -> str | None:
    run_id = os.environ.get("GITHUB_RUN_ID")
    return repo_url(f"/actions/runs/{run_id}") if run_id else None


def change_blocks(alert: Alert, issue_url: str | None, diff_url: str | None) -> list[dict]:
    emoji, label = URGENCY_STYLE[alert.urgency]
    src, change = alert.source, alert.change
    tags = "  ".join(f"`{esc(c)}`" for c in alert.categories) or "_untagged_"
    topics = esc(", ".join(alert.categories)) or "none"
    actions = "\n".join(f"- {esc(a)}" for a in alert.actions) or "- Review the change."
    blocks = [
        header(f"{emoji} {label.upper()}: official change detected"),
        section(f"*{link(src.name, src.url)}*\n{tags}"),
        fields(
            [
                ("Effective date", esc(alert.effective_date)),
                ("Urgency", label),
                ("Who is affected", f"Applicants affected by: {topics}"),
                ("Website pages to review", esc(", ".join(alert.page_types)) or "none"),
            ]
        ),
        divider(),
        section(f"*What changed*  _{len(change.added)} added, {len(change.removed)} removed_"),
        *quote_sections(":heavy_minus_sign: *Previous*", change.removed),
        *quote_sections(":heavy_plus_sign: *New*", change.added),
        divider(),
        section(f":memo: *Recommended action*\n{actions}"),
        links_row(
            [("Official source", src.url), ("Tracker issue", issue_url), ("Full diff", diff_url)]
        ),
        context(f"{VERIFY}  |  {FOOTER}"),
    ]
    return [b for b in blocks if b]


def health_blocks(source: Source, status: str, reason: str) -> list[dict]:
    name = f"*{link(source.name, source.url)}*"
    if status == "broken":
        blocks = [
            header(":red_circle: Source broken"),
            section(
                f"{name} has failed *3 daily runs in a row*.\n"
                f"*Reason:* {reason_text(reason)}  `{esc(reason)}`"
            ),
            links_row([("Run log", run_url()), ("Open source", source.url)]),
            context(
                "Checks continue every day. You get one message when it works again. "
                f"Fix with the add-source skill in Claude Code.  |  {FOOTER}"
            ),
        ]
    else:
        blocks = [
            header(":large_green_circle: Source recovered"),
            section(f"{name} is fetching normally again."),
            context(f"No action needed.  |  {FOOTER}"),
        ]
    return [b for b in blocks if b]


def daily_blocks(
    summary: RunSummary,
    alerted: int,
    failing: tuple[str, ...],
    checked_at: str,
    minor: tuple[str, ...] = (),
) -> list[dict]:
    clear = not alerted and not failing and not summary.broken
    icon = ":white_check_mark:" if clear else ":warning:"
    if clear:
        note = "All clear - no official change detected today."
    elif alerted:
        note = "See the alert message(s) above and the tracker."
    else:
        note = "Some sources could not be checked today; they are retried tomorrow."
    failing_md = ", ".join(f"`{esc(s)}`" for s in failing) or "None"
    blocks = [
        header(f"{icon} CDR Watch - daily check"),
        fields(
            [
                ("Checked at", esc(checked_at)),
                ("Sources checked", str(summary.checked)),
                ("Official changes alerted", str(alerted)),
                ("Sources failing today", failing_md),
            ]
        ),
        section(
            "*Minor changes (no alert keyword matched)*\n"
            + "\n".join(f"- `{esc(s)}`" for s in minor)
        )
        if minor
        else None,
        section("*Broken sources*\n" + "\n".join(f"- `{esc(s)}`" for s in summary.broken))
        if summary.broken
        else None,
        links_row([("Run log", run_url()), ("Tracker", repo_url("/issues"))]),
        context(f"{note}  |  {FOOTER}"),
    ]
    return [b for b in blocks if b]


def digest_blocks(summary: RunSummary) -> list[dict]:
    broken = "\n".join(f"- `{esc(s)}`" for s in summary.broken) or ":white_check_mark: None"
    blocks = [
        header(":bar_chart: CDR Watch - weekly check"),
        fields([("Week ending", esc(summary.date)), ("Sources checked", str(summary.checked))]),
        section(f"*Broken sources*\n{broken}"),
        links_row(
            [
                ("Run history", repo_url("/actions/workflows/monitor.yml")),
                ("Tracker", repo_url("/issues")),
            ]
        ),
        context(f"No other messages this week means no official change was detected.  |  {FOOTER}"),
    ]
    return [b for b in blocks if b]
