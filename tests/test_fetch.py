from pathlib import Path
from unittest import mock

import pytest
import requests

from cdrwatch import fetch
from cdrwatch.fetch import BROWSER_HEADERS, FetchFailure, http_get, looks_like_challenge

RAW = Path(__file__).parent / "fixtures" / "raw"
URL = "https://www.engineersaustralia.org.au/migrants"


def response(status: int, text: str = "") -> mock.Mock:
    resp = mock.Mock()
    resp.status_code = status
    resp.text = text
    return resp


@pytest.fixture
def no_sleep():
    with mock.patch.object(fetch.time, "sleep") as sleep:
        yield sleep


def test_200_returns_body(no_sleep):
    with mock.patch.object(fetch.requests, "get", return_value=response(200, "<html>ok")) as get:
        assert http_get(URL) == "<html>ok"
    get.assert_called_once()
    assert get.call_args.kwargs["headers"] == BROWSER_HEADERS
    assert get.call_args.kwargs["timeout"] == 30
    no_sleep.assert_not_called()


def test_browser_headers_look_like_chrome_en_au():
    assert "Chrome" in BROWSER_HEADERS["User-Agent"]
    assert "Accept" in BROWSER_HEADERS
    assert "en-AU" in BROWSER_HEADERS["Accept-Language"]


def test_403_raises_after_three_attempts_with_backoff(no_sleep):
    with mock.patch.object(fetch.requests, "get", return_value=response(403)) as get:
        with pytest.raises(FetchFailure) as exc:
            http_get(URL)
    assert exc.value.reason == "http_403"
    assert get.call_count == 3
    assert [c.args[0] for c in no_sleep.call_args_list] == [2, 4]


def test_retry_then_success(no_sleep):
    side = [response(503), response(200, "body")]
    with mock.patch.object(fetch.requests, "get", side_effect=side) as get:
        assert http_get(URL) == "body"
    assert get.call_count == 2


def test_timeout_reason(no_sleep):
    with mock.patch.object(fetch.requests, "get", side_effect=requests.Timeout()):
        with pytest.raises(FetchFailure) as exc:
            http_get(URL, retries=3)
    assert exc.value.reason == "timeout"


def test_network_reason(no_sleep):
    with mock.patch.object(fetch.requests, "get", side_effect=requests.ConnectionError()):
        with pytest.raises(FetchFailure) as exc:
            http_get(URL)
    assert exc.value.reason == "network"


def test_fetch_failure_str_is_reason():
    err = FetchFailure("too_short")
    assert err.reason == "too_short"
    assert str(err) == "too_short"


def test_challenge_detected_on_cloudflare_page():
    html = "<html><title>Just a moment...</title><script src='/cdn-cgi/challenge-platform/x'>"
    assert looks_like_challenge(html) is True
    assert looks_like_challenge('<div id="cf-chl-widget"></div>') is True


def test_challenge_false_when_article_present():
    assert looks_like_challenge("<script>challenge-platform</script><article>x") is False


@pytest.mark.parametrize("name", ["ea-msa.html", "ea-prepare-msa.html"])
def test_challenge_false_on_real_ea_pages(name):
    html = (RAW / name).read_text(encoding="utf-8")
    assert "challenge-platform" in html
    assert looks_like_challenge(html) is False
