"""Slack message builders and webhook post. Copy follows docs/PLAN.md section 5."""

import os
import time
import unicodedata
from typing import Literal

import requests

from cdrwatch import slack_blocks
from cdrwatch.models import Alert, RunSummary, Source
from cdrwatch.slack_blocks import MAX_CHARS, MAX_LINES

POST_RETRIES = 2
VERIFY_LINE = "Verify the official page before changing site content."
NOT_AVAILABLE = "not available"

# Typographic characters seen on official pages -> ASCII (code points keep this file ASCII).
_ASCII_MAP = {
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201C: '"', 0x201D: '"', 0x201E: '"',
    0x2013: "-", 0x2014: "-", 0x2212: "-", 0x2026: "...", 0x00A0: " ", 0x2022: "-",
    0x200B: "", 0xFEFF: "",
}  # fmt: skip


def to_ascii(text: str) -> str:
    """Map common typographic characters to ASCII; replace anything else with '?'."""
    text = unicodedata.normalize("NFC", text).translate(_ASCII_MAP)
    return text.encode("ascii", "replace").decode("ascii")


def _clip(line: str) -> str:
    return line if len(line) <= MAX_CHARS else line[: MAX_CHARS - 3] + "..."


def _side(label: str, lines: tuple[str, ...]) -> list[str]:
    if not lines:
        return [f"{label}: (none)"]
    shown = [_clip(line) for line in lines[:MAX_LINES]]
    out = [f"{label}: {shown[0]}"] + [f"  {line}" for line in shown[1:]]
    if len(lines) > MAX_LINES:
        out.append(f"  ... {len(lines) - MAX_LINES} more lines in full diff")
    return out


def _join(items: tuple[str, ...], sep: str = ", ") -> str:
    return sep.join(items) if items else "none"


def change_lines(alert: Alert) -> list[str]:
    """Body lines shared by the Slack alert and the tracker issue (no header, links, footer)."""
    change, tags = alert.change, _join(alert.categories)
    return [
        f"Change detected: {len(change.added)} lines added, {len(change.removed)} removed. "
        f"Tags: {tags}",
        *_side("Previous", change.removed),
        *_side("New", change.added),
        f"Effective date: {alert.effective_date}",
        f"Who is affected: Applicants affected by: {tags}",
        f"Website pages to review: {_join(alert.page_types)}",
        f"Recommended action: {_join(alert.actions, ' ')}",
        f"Official source: {alert.source.url}",
    ]


def _ascii_tree(value):
    """Apply to_ascii to every string inside a Block Kit structure."""
    if isinstance(value, str):
        return to_ascii(value)
    if isinstance(value, list):
        return [_ascii_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: _ascii_tree(v) for k, v in value.items()}
    return value


def _rich(lines: list[str], blocks: list[dict]) -> dict:
    """Plain fallback text (notifications, job summary) + designed blocks."""
    return {"text": "\n".join(to_ascii(line) for line in lines), "blocks": _ascii_tree(blocks)}


def build_change_blocks(alert: Alert, issue_url: str | None, diff_url: str | None) -> dict:
    lines = [
        f"[{alert.urgency.upper()}] {alert.source.name}",
        *change_lines(alert),
        f"Tracker: {issue_url or NOT_AVAILABLE} | Full diff: {diff_url or NOT_AVAILABLE}",
        VERIFY_LINE,
    ]
    return _rich(lines, slack_blocks.change_blocks(alert, issue_url, diff_url))


def build_health_blocks(
    source: Source, status: Literal["broken", "recovered"], reason: str
) -> dict:
    if status == "broken":
        text = f"[SOURCE BROKEN] {source.name} - failed 3 runs in a row ({reason}). {source.url}"
    else:
        text = f"[SOURCE RECOVERED] {source.name} - fetching normally again. {source.url}"
    return _rich([text], slack_blocks.health_blocks(source, status, reason))


def build_daily_blocks(
    summary: RunSummary, alerted: int, failing: tuple[str, ...], checked_at: str
) -> dict:
    text = (
        f"CDR Watch daily - {checked_at}: {summary.checked} sources checked, "
        f"{alerted} official changes alerted, failing today: {_join(failing)}, "
        f"broken: {_join(summary.broken)}."
    )
    return _rich([text], slack_blocks.daily_blocks(summary, alerted, failing, checked_at))


def build_digest_blocks(summary: RunSummary) -> dict:
    text = (
        f"CDR Watch weekly - {summary.date}: {summary.checked} sources checked, "
        f"broken: {_join(summary.broken)}."
    )
    return _rich([text], slack_blocks.digest_blocks(summary))


def post(payload: dict, webhook_url: str | None) -> bool:
    """Post to Slack. No webhook -> write text to the job summary (or stdout), return False."""
    if not webhook_url:
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as handle:
                handle.write(payload["text"] + "\n")
        else:
            print(payload["text"])
        return False
    for attempt in range(POST_RETRIES + 1):
        if attempt:
            time.sleep(2**attempt)
        try:
            resp = requests.post(webhook_url, json=payload, timeout=30)
        except requests.RequestException:
            continue
        if resp.status_code == 200:
            return True
        if resp.status_code != 429 and resp.status_code < 500:
            return False
    return False
