"""HTTP fetching with browser headers, retries and Cloudflare challenge detection."""

import time

import requests

BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}


class FetchFailure(Exception):
    """Reason is one of http_<code>, timeout, network, too_short, marker_missing,
    challenge_page."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def http_get(url: str, *, timeout: int = 30, retries: int = 3) -> str:
    """GET url and return the body. Backoff 2/4/8 s between attempts."""
    reason = "network"
    for attempt in range(retries):
        if attempt:
            time.sleep(2**attempt)
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
        except requests.Timeout:
            reason = "timeout"
            continue
        except requests.RequestException:
            reason = "network"
            continue
        if resp.status_code == 200:
            return resp.text
        reason = f"http_{resp.status_code}"
    raise FetchFailure(reason)


def looks_like_challenge(html: str) -> bool:
    # EA pages load a normal challenge-platform script; publication pages have
    # <main> but no <article> (owner-approved deviation, see docs/SPIKE.md).
    markers = ("cf-chl", "Just a moment", "challenge-platform")
    has_content = "<article" in html or "<main" in html
    return any(m in html for m in markers) and not has_content
