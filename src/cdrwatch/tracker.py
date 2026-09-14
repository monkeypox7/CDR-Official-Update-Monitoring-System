"""GitHub Issue tracker for material changes (REST API via requests, no gh CLI)."""

import hashlib
import sys

import requests

from cdrwatch.models import Alert
from cdrwatch.slack import NOT_AVAILABLE, VERIFY_LINE, change_lines, to_ascii

API = "https://api.github.com"
TIMEOUT = 30


class _GitHubError(Exception):
    pass


def issue_title(alert: Alert) -> str:
    return to_ascii(f"[{alert.urgency}] {alert.source.name}: {', '.join(alert.categories)}")


def _change_hash(alert: Alert) -> str:
    joined = "\n".join(alert.change.added + alert.change.removed)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def _body(alert: Alert, diff_url: str | None, marker: str) -> str:
    lines = [*change_lines(alert), f"Full diff: {diff_url or NOT_AVAILABLE}", VERIFY_LINE]
    return to_ascii("\n".join([*lines, "", marker]))


def _check(resp: requests.Response, ok: tuple[int, ...], what: str) -> requests.Response:
    if resp.status_code not in ok:
        raise _GitHubError(f"{what}: HTTP {resp.status_code}")
    return resp


def open_issue(alert: Alert, repo: str, token: str | None, diff_url: str | None) -> str | None:
    """Open (or find the open duplicate of) the tracker issue. Returns its url or None."""
    if not token:
        return None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"{API}/repos/{repo}"
    title = issue_title(alert)
    marker = f"change-hash: {_change_hash(alert)}"
    labels = [f"priority:{alert.urgency}", *(f"category:{c}" for c in alert.categories)]
    try:
        for label in labels:
            resp = requests.post(
                f"{base}/labels", json={"name": label}, headers=headers, timeout=TIMEOUT
            )
            _check(resp, (201, 422), f"label {label}")
        resp = requests.get(
            f"{base}/issues",
            params={"state": "open", "labels": labels[0], "per_page": 100},
            headers=headers,
            timeout=TIMEOUT,
        )
        for item in _check(resp, (200,), "list issues").json():
            if (
                "pull_request" not in item
                and item.get("title") == title
                and marker in (item.get("body") or "").split("\n")
            ):
                return item["html_url"]
        resp = requests.post(
            f"{base}/issues",
            json={"title": title, "body": _body(alert, diff_url, marker), "labels": labels},
            headers=headers,
            timeout=TIMEOUT,
        )
        return _check(resp, (201,), "create issue").json()["html_url"]
    except (requests.RequestException, _GitHubError) as exc:
        print(f"tracker: {exc}", file=sys.stderr)
        return None
