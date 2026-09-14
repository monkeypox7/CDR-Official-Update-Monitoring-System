"""Turn a raw fetched body into normalized, validated snapshot text per source kind."""

import json
import re
from collections.abc import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from cdrwatch.fetch import FetchFailure, looks_like_challenge
from cdrwatch.models import Source

# SharePoint editor label on Home Affairs pages (docs/DECISIONS.md D5).
GLOBAL_IGNORE = ("^UnPublished$",)
DROP_TAGS = ("script", "style", "nav", "footer", "header", "form", "noscript")
SCHEMA_INPUT = "input#ctl00_PlaceHolderMain_PageSchemaHiddenField_Input"
# Zero-width space and BOM survive str.split(); Home Affairs values contain them.
INVISIBLE = {0x200B: None, 0xFEFF: None}


def _norm(text: str) -> str:
    return " ".join(text.translate(INVISIBLE).split())


def _text_lines(text: str) -> list[str]:
    return [line for line in (_norm(part) for part in text.splitlines()) if line]


def _finish(lines: Iterable[str], source: Source, *, sort: bool) -> str:
    patterns = [re.compile(p) for p in (*GLOBAL_IGNORE, *source.ignore_patterns)]
    kept = [line for line in lines if not any(p.search(line) for p in patterns)]
    if sort:
        kept = sorted(set(kept))
    return "\n".join(kept)


def _html_text(html: str) -> str:
    return BeautifulSoup(html, "lxml").get_text("\n")


def _container(html: str, source: Source):
    soup = BeautifulSoup(html, "lxml")
    return soup.select_one(source.selector) if source.selector else soup


def page_text(html: str, source: Source) -> str:
    container = _container(html, source)
    if container is None:
        return ""
    for tag in container.find_all(DROP_TAGS):
        tag.decompose()
    for tag in container.select('[aria-hidden="true"]'):
        tag.decompose()
    return _finish(_text_lines(container.get_text("\n")), source, sort=False)


def link_set(html: str, source: Source) -> str:
    container = _container(html, source)
    if container is None:
        return ""
    lines = []
    for anchor in container.find_all("a", href=True):
        url = urljoin(source.url, anchor["href"].strip())
        if source.link_pattern and not re.search(source.link_pattern, url):
            continue
        lines.append(f"{_norm(anchor.get_text(' '))} | {url}")
    return _finish(lines, source, sort=True)


def rss_items(xml: str, source: Source) -> str:
    soup = BeautifulSoup(xml, "xml")
    lines = []
    for item in soup.find_all("item"):
        title = _norm(item.title.get_text()) if item.title else ""
        link = _norm(item.link.get_text()) if item.link else ""
        lines.append(f"{title} | {link}")
    return _finish(lines, source, sort=True)


def legislation_titles(json_text: str, source: Source) -> str:
    lines = [
        f"{_norm(row['id'])} | {_norm(row['name'])} | {(row.get('makingDate') or '')[:10]}"
        for row in json.loads(json_text)["value"]
    ]
    return _finish(lines, source, sort=True)


def occupations(json_text: str, source: Source) -> str:
    lines = []
    for row in json.loads(json_text)["d"]["data"]:
        values = {k: _norm(_html_text(str(v or ""))) for k, v in row.items()}
        if "Engineers Australia" not in values.get("assessauth", ""):
            continue
        cols = ("anzscocode", "occupation", "list", "visas")
        lines.append(" | ".join(values.get(k, "") for k in cols))
    return _finish(lines, source, sort=True)


def schema_json(html: str, source: Source) -> str:
    field = BeautifulSoup(html, "lxml").select_one(SCHEMA_INPUT)
    if field is None or not field.get("value"):
        return ""
    lines = []
    for item in json.loads(field["value"]).get("content", []):
        lines.extend(_text_lines(str(item.get("text") or "")))
        lines.extend(_text_lines(_html_text(str(item.get("block") or ""))))
    return _finish(lines, source, sort=False)


EXTRACTORS = {
    "page": page_text,
    "links": link_set,
    "rss": rss_items,
    "legislation": legislation_titles,
    "occupations": occupations,
    "schema_json": schema_json,
}


def extract(raw: str, source: Source) -> str:
    """Dispatch by kind, then validate in order: challenge, marker, length."""
    if looks_like_challenge(raw):
        raise FetchFailure("challenge_page")
    try:
        text = EXTRACTORS[source.kind](raw, source)
    except (ValueError, KeyError, TypeError, AttributeError):
        text = ""  # malformed JSON or unexpected shape: fails marker/length below
    if source.required_marker and source.required_marker.lower() not in text.lower():
        raise FetchFailure("marker_missing")
    if len(text) < source.min_chars:
        raise FetchFailure("too_short")
    return text
