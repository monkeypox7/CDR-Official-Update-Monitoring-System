import hashlib
from unittest import mock

import pytest
import requests

from cdrwatch import tracker
from cdrwatch.models import Alert, Change, Source
from cdrwatch.tracker import issue_title, open_issue

REPO = "owner/cdrwatch"
TOKEN = "test-token"
DIFF = "https://github.com/owner/cdrwatch/commit/abc123"
API = "https://api.github.com/repos/owner/cdrwatch"

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
        source_id="ea-fees", added=("Fast Track fee $395",), removed=("Fast Track fee $360",)
    ),
    categories=("Fees", "Deadlines/Interim arrangements"),
    urgency="Critical",
    actions=("Update pricing figures on all pages that show EA fees.",),
    page_types=("Pricing",),
    effective_date="Not stated in source",
)

HASH = hashlib.sha256(b"Fast Track fee $395\nFast Track fee $360").hexdigest()[:12]
TITLE = (
    "[Critical] Engineers Australia - Assessment fees and additional services: "
    "Fees, Deadlines/Interim arrangements"
)


def response(status: int, body: object = None) -> mock.Mock:
    resp = mock.Mock()
    resp.status_code = status
    resp.json.return_value = body
    return resp


@pytest.fixture
def github():
    with (
        mock.patch.object(tracker.requests, "post") as post,
        mock.patch.object(tracker.requests, "get") as get,
    ):
        yield post, get


def created_issue_call(post: mock.Mock) -> mock.call:
    return next(c for c in post.call_args_list if c.args[0] == f"{API}/issues")


def test_issue_title():
    assert issue_title(ALERT) == TITLE


def test_no_token_returns_none(github):
    post, get = github
    assert open_issue(ALERT, REPO, None, DIFF) is None
    post.assert_not_called()
    get.assert_not_called()


def test_creates_labels_and_issue(github):
    post, get = github
    post.side_effect = [
        response(201),
        response(201),
        response(201),
        response(201, {"html_url": "https://github.com/owner/cdrwatch/issues/7"}),
    ]
    get.return_value = response(200, [])
    assert open_issue(ALERT, REPO, TOKEN, DIFF) == "https://github.com/owner/cdrwatch/issues/7"

    label_calls = [c for c in post.call_args_list if c.args[0] == f"{API}/labels"]
    assert [c.kwargs["json"]["name"] for c in label_calls] == [
        "priority:Critical",
        "category:Fees",
        "category:Deadlines/Interim arrangements",
    ]
    headers = label_calls[0].kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-token"
    assert get.call_args.kwargs["params"]["state"] == "open"

    sent = created_issue_call(post).kwargs["json"]
    assert sent["title"] == TITLE
    assert sent["labels"] == [
        "priority:Critical",
        "category:Fees",
        "category:Deadlines/Interim arrangements",
    ]
    body = sent["body"]
    assert f"change-hash: {HASH}" in body
    assert "Verify the official page before changing site content." in body.split("\n")
    assert "Previous: Fast Track fee $360" in body
    assert f"Full diff: {DIFF}" in body
    assert "Effective date: Not stated in source" in body
    assert body.isascii()


def test_label_422_tolerated(github):
    post, get = github
    post.side_effect = [
        response(422),
        response(422),
        response(422),
        response(201, {"html_url": "https://github.com/owner/cdrwatch/issues/8"}),
    ]
    get.return_value = response(200, [])
    assert open_issue(ALERT, REPO, TOKEN, None) == "https://github.com/owner/cdrwatch/issues/8"
    assert "Full diff: not available" in created_issue_call(post).kwargs["json"]["body"]


def test_dedupe_returns_existing_issue(github):
    post, get = github
    post.return_value = response(422)
    get.return_value = response(
        200,
        [
            {"title": TITLE, "body": "change-hash: 000000000000", "html_url": "u-other-hash"},
            {"title": TITLE, "body": f"x\nchange-hash: {HASH}", "html_url": "u-pr",
             "pull_request": {}},
            {"title": "other", "body": f"change-hash: {HASH}", "html_url": "u-other-title"},
            {"title": TITLE, "body": f"x\n\nchange-hash: {HASH}\n", "html_url": "u-match"},
        ],
    )  # fmt: skip
    assert open_issue(ALERT, REPO, TOKEN, DIFF) == "u-match"
    assert all(c.args[0] == f"{API}/labels" for c in post.call_args_list)


def test_same_title_new_hash_opens_new_issue(github):
    post, get = github
    post.side_effect = [response(422)] * 3 + [response(201, {"html_url": "u-new"})]
    get.return_value = response(
        200, [{"title": TITLE, "body": "change-hash: abc", "html_url": "u"}]
    )
    assert open_issue(ALERT, REPO, TOKEN, DIFF) == "u-new"


def test_label_error_returns_none(github, capsys):
    post, get = github
    post.return_value = response(403)
    assert open_issue(ALERT, REPO, TOKEN, DIFF) is None
    get.assert_not_called()
    assert "403" in capsys.readouterr().err


def test_create_failure_returns_none(github):
    post, get = github
    post.side_effect = [response(201)] * 3 + [response(500)]
    get.return_value = response(200, [])
    assert open_issue(ALERT, REPO, TOKEN, DIFF) is None


def test_network_error_returns_none(github):
    post, get = github
    post.side_effect = requests.ConnectionError("down")
    assert open_issue(ALERT, REPO, TOKEN, DIFF) is None
