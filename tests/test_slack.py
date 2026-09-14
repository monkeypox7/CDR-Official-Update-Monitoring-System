from unittest import mock

import pytest
import requests

from cdrwatch import slack
from cdrwatch.models import Alert, Change, RunSummary, Source
from cdrwatch.slack import build_change_blocks, build_digest_blocks, build_health_blocks, post

WEBHOOK = "https://hooks.slack.test/services/T000/B000/XXXX"

SOURCE = Source(
    id="ea-fees",
    name="Engineers Australia - Assessment fees and additional services",
    kind="page",
    url="https://www.engineersaustralia.org.au/fees",
    priority="Critical",
    fetch="http",
)

# Illustrative test data from docs/PLAN.md section 5, not real EA fees.
ALERT = Alert(
    source=SOURCE,
    change=Change(
        source_id="ea-fees",
        added=("Fast Track fee $395",),
        removed=("Fast Track fee $360",),
    ),
    categories=("Fees",),
    urgency="Critical",
    actions=("Update pricing figures on all pages that show EA fees.",),
    page_types=("Pricing", "MSA guide"),
    effective_date="1 October 2026",
)


def with_change(added: tuple[str, ...], removed: tuple[str, ...]) -> Alert:
    change = Change(source_id="ea-fees", added=added, removed=removed)
    return Alert(**{**ALERT.__dict__, "change": change})


def response(status: int) -> mock.Mock:
    resp = mock.Mock()
    resp.status_code = status
    return resp


@pytest.fixture
def no_sleep():
    with mock.patch.object(slack.time, "sleep") as sleep:
        yield sleep


def test_change_text_matches_plan_section_5():
    payload = build_change_blocks(
        ALERT, "https://github.com/o/r/issues/9", "https://github.com/o/r/commit/abc"
    )
    assert payload["text"].split("\n") == [
        "[CRITICAL] Engineers Australia - Assessment fees and additional services",
        "Change detected: 1 lines added, 1 removed. Tags: Fees",
        "Previous: Fast Track fee $360",
        "New: Fast Track fee $395",
        "Effective date: 1 October 2026",
        "Who is affected: Applicants affected by: Fees",
        "Website pages to review: Pricing, MSA guide",
        "Recommended action: Update pricing figures on all pages that show EA fees.",
        "Official source: https://www.engineersaustralia.org.au/fees",
        "Tracker: https://github.com/o/r/issues/9 | Full diff: https://github.com/o/r/commit/abc",
        "Verify the official page before changing site content.",
    ]


def test_multi_line_sides_are_listed_one_per_line():
    lines = build_change_blocks(with_change(("a1", "a2"), ("r1",)), None, None)["text"].split("\n")
    assert lines[1] == "Change detected: 2 lines added, 1 removed. Tags: Fees"
    assert lines[2:5] == ["Previous: r1", "New: a1", "  a2"]
    assert "Tracker: not available | Full diff: not available" in lines


def test_empty_side_shows_none():
    text = build_change_blocks(with_change(("Only added",), ()), None, None)["text"]
    assert "Previous: (none)" in text.split("\n")


def test_line_and_length_limits():
    added = tuple(f"line {i} " + "x" * 400 for i in range(20))
    lines = build_change_blocks(with_change(added, ()), None, None)["text"].split("\n")
    assert lines[1].startswith("Change detected: 20 lines added, 0 removed.")
    start = lines.index(next(line for line in lines if line.startswith("New: ")))
    shown = [line.removeprefix("New: ").removeprefix("  ") for line in lines[start : start + 15]]
    assert all(len(line) == 300 and line.endswith("...") for line in shown)
    assert shown[14].startswith("line 14 ")
    assert lines[start + 15] == "  ... 5 more lines in full diff"
    assert lines[start + 16].startswith("Effective date:")


def test_blocks_are_sections_under_slack_limit_and_escaped():
    side = tuple("a < b & c > d " + "y" * 290 for _ in range(15))
    payload = build_change_blocks(with_change(side, side), None, None)
    assert len(payload["blocks"]) > 1
    for block in payload["blocks"]:
        assert block["type"] == "section"
        assert block["text"]["type"] == "mrkdwn"
        assert len(block["text"]["text"]) <= 3000
    joined = "\n".join(b["text"]["text"] for b in payload["blocks"])
    assert "a &lt; b &amp; c &gt; d" in joined
    assert "a < b & c > d" in payload["text"]
    assert joined.count("y" * 280) == 30


def test_output_is_ascii():
    fancy = (
        chr(0x201C) + "Fee" + chr(0x201D) + " " + chr(0x2013) + " now "
        + chr(0x2019) + "$395" + chr(0x2019) + chr(0x2026) + " caf" + chr(0xE9)
    )  # fmt: skip
    payload = build_change_blocks(with_change((fancy,), ()), None, None)
    assert payload["text"].isascii()
    assert "New: \"Fee\" - now '$395'... caf?" in payload["text"]
    assert all(b["text"]["text"].isascii() for b in payload["blocks"])


def test_health_broken_and_recovered():
    broken = build_health_blocks(ALERT.source, "broken", "http_403")
    assert broken["text"] == (
        "[SOURCE BROKEN] Engineers Australia - Assessment fees and additional services"
        " - failed 3 runs in a row (http_403). https://www.engineersaustralia.org.au/fees"
    )
    recovered = build_health_blocks(ALERT.source, "recovered", "")
    assert recovered["text"] == (
        "[SOURCE RECOVERED] Engineers Australia - Assessment fees and additional services"
        " - fetching normally again. https://www.engineersaustralia.org.au/fees"
    )
    assert broken["blocks"][0]["type"] == "section"


def test_digest_text():
    summary = RunSummary(date="2026-09-20", checked=15, informational=3, broken=("a", "b"))
    assert build_digest_blocks(summary)["text"] == (
        "CDR Watch weekly - 2026-09-20: 15 sources checked, broken: a, b."
    )
    empty = RunSummary(date="2026-09-20", checked=15, informational=0, broken=())
    assert build_digest_blocks(empty)["text"].endswith("broken: none.")


def test_no_webhook_writes_step_summary(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    summary.write_text("existing\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    with mock.patch.object(slack.requests, "post") as post_mock:
        assert post({"text": "hello", "blocks": []}, None) is False
    post_mock.assert_not_called()
    assert summary.read_text(encoding="utf-8") == "existing\nhello\n"


def test_no_webhook_no_summary_prints(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert post({"text": "hello", "blocks": []}, None) is False
    assert capsys.readouterr().out == "hello\n"


def test_post_200_true():
    payload = {"text": "hi", "blocks": []}
    with mock.patch.object(slack.requests, "post", return_value=response(200)) as post_mock:
        assert post(payload, WEBHOOK) is True
    post_mock.assert_called_once_with(WEBHOOK, json=payload, timeout=30)


def test_post_429_then_200_true(no_sleep):
    with mock.patch.object(
        slack.requests, "post", side_effect=[response(429), response(200)]
    ) as post_mock:
        assert post({"text": "hi"}, WEBHOOK) is True
    assert post_mock.call_count == 2


def test_post_5xx_two_retries_then_false(no_sleep):
    with mock.patch.object(slack.requests, "post", return_value=response(503)) as post_mock:
        assert post({"text": "hi"}, WEBHOOK) is False
    assert post_mock.call_count == 3


def test_post_400_no_retry(no_sleep):
    with mock.patch.object(slack.requests, "post", return_value=response(400)) as post_mock:
        assert post({"text": "hi"}, WEBHOOK) is False
    assert post_mock.call_count == 1


def test_post_network_error_retries_then_false(no_sleep):
    with mock.patch.object(
        slack.requests, "post", side_effect=requests.ConnectionError("down")
    ) as post_mock:
        assert post({"text": "hi"}, WEBHOOK) is False
    assert post_mock.call_count == 3
