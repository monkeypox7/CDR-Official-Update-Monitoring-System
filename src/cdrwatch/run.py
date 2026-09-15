"""Daily run: fetch, extract, diff, confirm, tag, alert, save. docs/PLAN.md Task 4."""

import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cdrwatch import classify, config, diff, extract, fetch, slack, state, tracker
from cdrwatch.models import Alert, Change, RunSummary, Source, SourceMeta

BROKEN_AFTER = 3
CONFIRM_DELAY = 60
ALERT_URGENCIES = ("Critical", "High")
NEPAL_OFFSET = timedelta(hours=5, minutes=45)


def nepal_time(now: datetime) -> str:
    return (now + NEPAL_OFFSET).strftime("%d %b %Y, %I:%M %p") + " Nepal time"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m cdrwatch.run")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", metavar="ID")
    p.add_argument("--no-confirm", action="store_true")
    p.add_argument("--digest", action="store_true")
    p.add_argument("--daily-summary", action="store_true")
    p.add_argument("--state-dir", default="state")
    p.add_argument("--sources", default="sources.yaml")
    p.add_argument("--keywords", default="keywords.yaml")
    return p.parse_args(argv)


def fetch_text(source: Source) -> str:
    return extract.extract(fetch.fetch_source(source), source)


def check(source: Source) -> tuple[str | None, str]:
    """Return (text, "") on success or (None, reason) on any failure."""
    try:
        return fetch_text(source), ""
    except fetch.FetchFailure as exc:
        return None, exc.reason
    except Exception as exc:  # one source must never stop the run
        return None, f"error_{type(exc).__name__}"


def diff_url(source_id: str) -> str | None:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server}/{repo}/commits/state/{source_id}.txt"


def is_digest_run(args: argparse.Namespace, now: datetime) -> bool:
    # Sunday 23:00 UTC is Monday 09:00 AEST. Shift back 12h so a delayed start after
    # midnight UTC still counts as the Sunday run.
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    return args.digest or (scheduled and (now - timedelta(hours=12)).weekday() == 6)


class Run:
    def __init__(self, args: argparse.Namespace, rules: list, today: str):
        self.args = args
        self.rules = rules
        self.today = today
        self.state_dir = Path(args.state_dir)
        self.meta: dict[str, SourceMeta] = state.load_meta(self.state_dir)
        self.lines: list[str] = []
        self.changes = 0
        self.failures = 0
        self.informational = 0
        self.slack_failed = 0
        self.failed_ids: list[str] = []

    def send(self, payload: dict) -> None:
        if self.args.dry_run:
            print(payload["text"])
            return
        webhook = os.environ.get("SLACK_WEBHOOK_URL") or None
        if not slack.post(payload, webhook) and webhook:
            self.slack_failed += 1

    def record_failure(self, source: Source, reason: str) -> None:
        self.failures += 1
        self.failed_ids.append(source.id)
        self.lines.append(f"FAIL {source.id} {reason}")
        m = self.meta.setdefault(source.id, SourceMeta())
        m.fail_count += 1
        if m.fail_count >= BROKEN_AFTER and not m.broken_alerted:
            m.broken_alerted = True
            self.send(slack.build_health_blocks(source, "broken", reason))

    def record_success(self, source: Source) -> None:
        m = self.meta.setdefault(source.id, SourceMeta())
        if m.broken_alerted:
            self.send(slack.build_health_blocks(source, "recovered", ""))
        m.fail_count = 0
        m.broken_alerted = False
        m.last_ok = self.today

    def save(self, source_id: str, text: str) -> None:
        if not self.args.dry_run:
            state.save_snapshot(self.state_dir, source_id, text)

    def alert(self, alert: Alert) -> None:
        self.changes += 1
        sid = alert.source.id
        self.lines.append(f"CHANGE {sid} {alert.urgency} {', '.join(alert.categories) or '-'}")
        if alert.urgency not in ALERT_URGENCIES:
            self.informational += 1
            return
        url = diff_url(sid)
        issue = None
        if not self.args.dry_run:
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            issue = tracker.open_issue(alert, repo, os.environ.get("GITHUB_TOKEN") or None, url)
        self.send(slack.build_change_blocks(alert, issue, url))

    def process(self, sources: list[Source]) -> None:
        pending: list[tuple[Source, str, Change]] = []
        for source in sources:
            text, reason = check(source)
            if text is None:
                self.record_failure(source, reason)
                continue
            self.record_success(source)
            old = state.load_snapshot(self.state_dir, source.id)
            change = diff.compare(source.id, old, text)
            if old is None:
                self.lines.append(f"BASELINE {source.id} {len(text)}")
                self.save(source.id, text)
            elif change is None:
                self.lines.append(f"OK {source.id} {len(text)}")
            else:
                pending.append((source, text, change))
        if pending and not self.args.no_confirm:
            time.sleep(CONFIRM_DELAY)
        for source, text, change in pending:
            if not self.args.no_confirm and check(source)[0] != text:
                self.lines.append(f"UNCONFIRMED {source.id}")
                continue
            self.save(source.id, text)
            self.alert(classify.tag(source, change, self.rules))

    def finish(self, sources: list[Source], digest: bool, checked_at: str = "") -> int:
        """Send daily summary or digest, save meta, write the summary. 1 if a Slack post failed."""
        checked = len(sources)
        ids = {s.id for s in sources}
        broken = tuple(sorted(k for k, m in self.meta.items() if m.broken_alerted and k in ids))
        summary = RunSummary(self.today, checked, self.informational, broken)
        if self.args.daily_summary:
            alerted = self.changes - self.informational
            failing = tuple(sorted(self.failed_ids))
            self.send(slack.build_daily_blocks(summary, alerted, failing, checked_at))
        elif digest:
            self.send(slack.build_digest_blocks(summary))
        if not self.args.dry_run:
            state.save_meta(self.state_dir, self.meta)
        head = (
            f"CDR Watch run {self.today}: {checked} sources checked, "
            f"{self.changes} changes, {self.failures} failures"
        )
        lines = [head, "", *self.lines]
        if self.slack_failed:
            lines.append(f"SLACK DELIVERY FAILED: {self.slack_failed} message(s)")
        write_summary(lines)
        return 1 if self.slack_failed else 0


def write_summary(lines: list[str]) -> None:
    text = "\n".join(lines) + "\n"
    print(text, end="")
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("```\n" + text + "```\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        sources = config.load_sources(args.sources)
        rules = config.load_keywords(args.keywords)
        if args.only:
            sources = [s for s in sources if s.id == args.only]
            if not sources:
                raise ValueError(f"--only: unknown source id {args.only!r}")
    except (ValueError, OSError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1
    now = datetime.now(UTC)
    if not args.dry_run:
        Path(args.state_dir).mkdir(parents=True, exist_ok=True)
    run = Run(args, rules, now.date().isoformat())
    run.process(sources)
    return run.finish(sources, is_digest_run(args, now), nepal_time(now))


if __name__ == "__main__":
    sys.exit(main())
