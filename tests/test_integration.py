"""End-to-end run over real raw fixtures with fetch, Slack and tracker mocked."""

from pathlib import Path

import pytest

from cdrwatch import config, fetch, run, slack, state, tracker
from cdrwatch.fetch import FetchFailure

ROOT = Path(__file__).parents[1]
RAW = Path(__file__).parent / "fixtures" / "raw"
SOURCES = ROOT / "sources.yaml"
KEYWORDS = ROOT / "keywords.yaml"
EXT = {"rss": "xml", "legislation": "json", "occupations": "json"}


def fixture_text(source) -> str:
    path = RAW / f"{source.id}.{EXT.get(source.kind, 'html')}"
    return path.read_text(encoding="utf-8")


class Harness:
    def __init__(self, monkeypatch, tmp_path):
        self.state_dir = tmp_path / "state"
        self.overrides: dict[str, str] = {}
        self.failing: set[str] = set()
        self.posts: list[dict] = []
        self.issues: list = []
        self.sleeps: list[float] = []
        monkeypatch.setattr(fetch, "fetch_source", self.fetch)
        monkeypatch.setattr(slack, "post", lambda payload, url: self.posts.append(payload))
        monkeypatch.setattr(tracker, "open_issue", self.open_issue)
        monkeypatch.setattr(run.time, "sleep", self.sleeps.append)
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

    def fetch(self, source) -> str:
        if source.id in self.failing:
            raise FetchFailure("http_503")
        return self.overrides.get(source.id) or fixture_text(source)

    def open_issue(self, alert, repo, token, diff_url):
        self.issues.append(alert)
        return f"https://github.com/{repo}/issues/{len(self.issues)}"

    def main(self, *extra: str) -> int:
        argv = ["--state-dir", str(self.state_dir), "--sources", str(SOURCES)]
        return run.main([*argv, "--keywords", str(KEYWORDS), "--no-confirm", *extra])


@pytest.fixture
def h(monkeypatch, tmp_path):
    return Harness(monkeypatch, tmp_path)


def edited_fees() -> str:
    raw = (RAW / "ea-fees.html").read_text(encoding="utf-8")
    assert "$505" in raw
    return raw.replace("$505", "$999")


def snapshot_ids(state_dir: Path) -> list[str]:
    return sorted(p.stem for p in state_dir.glob("*.txt"))


def test_baseline_run_is_silent_and_saves_every_source(h, capsys):
    assert h.main() == 0
    ids = sorted(s.id for s in config.load_sources(SOURCES))
    assert snapshot_ids(h.state_dir) == ids
    assert (h.state_dir / "meta.json").exists()
    assert h.posts == [] and h.issues == []
    assert f"{len(ids)} sources checked, 0 changes, 0 failures" in capsys.readouterr().out


def test_second_run_unchanged_reports_zero_changes(h, capsys):
    h.main()
    capsys.readouterr()
    assert h.main() == 0
    assert h.posts == [] and h.issues == []
    assert "0 changes, 0 failures" in capsys.readouterr().out


def test_edited_fee_fixture_sends_one_alert_and_one_issue(h):
    h.main()
    h.overrides["ea-fees"] = edited_fees()
    assert h.main() == 0
    assert len(h.issues) == 1
    alert = h.issues[0]
    assert alert.source.id == "ea-fees"
    assert alert.urgency == "Critical"
    assert "Fees" in alert.categories
    assert any("$999" in line for line in alert.change.added)
    assert len(h.posts) == 1
    assert "$999" in (h.state_dir / "ea-fees.txt").read_text(encoding="utf-8")
    h.main()
    assert len(h.posts) == 1 and len(h.issues) == 1


def test_three_failures_send_one_broken_alert_then_one_recovered(h):
    h.main("--only", "ea-fees")
    h.failing.add("ea-fees")
    for _ in range(2):
        h.main("--only", "ea-fees")
    assert h.posts == []
    h.main("--only", "ea-fees")
    assert len(h.posts) == 1
    assert "SOURCE BROKEN" in h.posts[0]["text"]
    h.main("--only", "ea-fees")
    assert len(h.posts) == 1
    h.failing.clear()
    h.main("--only", "ea-fees")
    assert len(h.posts) == 2
    assert "SOURCE RECOVERED" in h.posts[1]["text"]
    h.main("--only", "ea-fees")
    assert len(h.posts) == 2 and h.issues == []


def test_failure_does_not_stop_other_sources(h):
    h.failing.add("ea-fees")
    assert h.main() == 0
    ids = snapshot_ids(h.state_dir)
    assert "ea-fees" not in ids and "ea-msa" in ids


def test_unconfirmed_change_is_not_alerted_or_saved(h, monkeypatch):
    h.main("--only", "ea-fees")
    edited = edited_fees()
    calls = iter([edited, (RAW / "ea-fees.html").read_text(encoding="utf-8")])
    monkeypatch.setattr(fetch, "fetch_source", lambda s: next(calls))
    argv = ["--state-dir", str(h.state_dir), "--sources", str(SOURCES)]
    assert run.main([*argv, "--keywords", str(KEYWORDS), "--only", "ea-fees"]) == 0
    assert h.sleeps == [run.CONFIRM_DELAY]
    assert h.posts == [] and h.issues == []
    assert "$999" not in (h.state_dir / "ea-fees.txt").read_text(encoding="utf-8")


def test_dry_run_writes_nothing_and_posts_nothing(h, capsys):
    h.main("--only", "ea-fees")
    before = (h.state_dir / "ea-fees.txt").read_bytes()
    h.overrides["ea-fees"] = edited_fees()
    assert h.main("--only", "ea-fees", "--dry-run") == 0
    assert h.posts == [] and h.issues == []
    assert (h.state_dir / "ea-fees.txt").read_bytes() == before
    assert "1 changes" in capsys.readouterr().out


def test_digest_flag_posts_one_digest(h):
    h.main("--only", "ea-fees")
    h.main("--only", "ea-fees", "--digest")
    assert len(h.posts) == 1


def test_unknown_snapshot_file_is_ignored(h):
    h.state_dir.mkdir(parents=True)
    (h.state_dir / "removed-source.txt").write_text("old\n", encoding="utf-8")
    assert h.main("--only", "ea-fees") == 0
    assert h.posts == []


def test_config_error_exits_1(h, tmp_path):
    bad = tmp_path / "sources.yaml"
    text = SOURCES.read_text(encoding="utf-8")
    assert "kind: page" in text
    bad.write_text(text.replace("kind: page", "kind: bogus", 1), encoding="utf-8")
    argv = ["--state-dir", str(h.state_dir), "--sources", str(bad), "--keywords", str(KEYWORDS)]
    assert run.main(argv) == 1


def test_unknown_only_id_exits_1(h):
    assert h.main("--only", "no-such-source") == 1


# Simulations for the v1 release gate (docs/PLAN.md section 1.5, Task 5).

EA_FEES_URL = (
    "https://www.engineersaustralia.org.au/migrants/migration-skills-assessment/"
    "assessment-fees-and-additional-services"
)

SIMULATED_FEE_ALERT = "\n".join(
    [
        "[CRITICAL] Engineers Australia - Assessment fees and additional services",
        "Change detected: 1 lines added, 1 removed. Tags: Fees",
        "Previous: $505",
        "New: $999",
        "Effective date: Not stated in source",
        "Who is affected: Applicants affected by: Fees",
        "Website pages to review: Pricing, MSA guide",
        "Recommended action: Update pricing figures on all pages that show EA fees.",
        f"Official source: {EA_FEES_URL}",
        "Tracker: https://github.com/owner/repo/issues/1"
        " | Full diff: https://github.com/owner/repo/commits/state/ea-fees.txt",
        "Verify the official page before changing site content.",
    ]
)


def test_simulated_fee_change_renders_exact_slack_text(h, monkeypatch):
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    h.main("--only", "ea-fees")
    h.overrides["ea-fees"] = edited_fees()
    assert h.main("--only", "ea-fees") == 0
    assert len(h.posts) == 1 and len(h.issues) == 1
    assert h.posts[0]["text"] == SIMULATED_FEE_ALERT
    assert h.posts[0]["text"].isascii()


def test_four_consecutive_failures_send_exactly_one_broken_alert(h):
    h.main("--only", "ea-fees")
    h.failing.add("ea-fees")
    for _ in range(4):
        assert h.main("--only", "ea-fees") == 0
    assert [p["text"] for p in h.posts] == [
        "[SOURCE BROKEN] Engineers Australia - Assessment fees and additional services"
        f" - failed 3 runs in a row (http_503). {EA_FEES_URL}"
    ]
    meta = state.load_meta(h.state_dir)["ea-fees"]
    assert meta.fail_count == 4 and meta.broken_alerted
    assert h.issues == []
