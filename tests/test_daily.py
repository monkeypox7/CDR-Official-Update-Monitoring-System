"""Daily check-in message: posted every scheduled run so a quiet day is visible in Slack."""

from datetime import UTC, datetime

import pytest

from cdrwatch import run
from test_integration import RAW, Harness, edited_fees


@pytest.fixture
def h(monkeypatch, tmp_path):
    return Harness(monkeypatch, tmp_path)


def test_daily_summary_posts_all_clear_on_quiet_day(h):
    h.main("--only", "ea-fees")
    h.main("--only", "ea-fees", "--daily-summary")
    assert len(h.posts) == 1
    text = h.posts[0]["text"]
    assert text.startswith("CDR Watch daily - ")
    assert "Nepal time: 1 sources checked, 0 official changes alerted" in text
    assert "minor changes: none, failing today: none, broken: none." in text
    assert h.posts[0]["blocks"][0]["text"]["text"] == ":white_check_mark: CDR Watch - daily check"


def test_daily_summary_counts_alerts_and_failures_and_replaces_digest(h):
    h.main("--only", "ea-fees")
    h.main("--only", "ea-msa")
    h.overrides["ea-fees"] = edited_fees()
    h.failing.add("ea-msa")
    h.main("--daily-summary", "--digest")
    daily = [p for p in h.posts if p["text"].startswith("CDR Watch daily")]
    weekly = [p for p in h.posts if p["text"].startswith("CDR Watch weekly")]
    assert len(daily) == 1 and weekly == []
    assert "1 official changes alerted" in daily[0]["text"]
    assert "failing today: ea-msa," in daily[0]["text"]
    assert daily[0]["blocks"][0]["text"]["text"] == ":warning: CDR Watch - daily check"
    assert h.posts[-1] is daily[0]


def test_no_daily_summary_without_flag(h):
    h.main("--only", "ea-fees")
    h.main("--only", "ea-fees")
    assert h.posts == []


def test_nepal_time_format():
    assert run.nepal_time(datetime(2026, 9, 14, 22, 17, tzinfo=UTC)) == (
        "15 Sep 2026, 04:02 AM Nepal time"
    )


def test_daily_summary_lists_minor_changes(h):
    h.main("--only", "ea-msa")
    raw = (RAW / "ea-msa.html").read_text(encoding="utf-8")
    extra = "<p>Plain untagged sentence.</p></article>"
    h.overrides["ea-msa"] = raw.replace("</article>", extra, 1)
    h.main("--only", "ea-msa", "--daily-summary")
    text = h.posts[-1]["text"]
    assert "0 official changes alerted, minor changes: ea-msa," in text
