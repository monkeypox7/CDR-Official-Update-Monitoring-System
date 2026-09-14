import dataclasses
import json
from pathlib import Path

import pytest

from cdrwatch.config import load_sources
from cdrwatch.extract import (
    extract,
    legislation_titles,
    link_set,
    occupations,
    page_text,
    rss_items,
    schema_json,
)
from cdrwatch.fetch import FetchFailure

ROOT = Path(__file__).parent.parent
RAW = ROOT / "tests" / "fixtures" / "raw"
SOURCES = {s.id: s for s in load_sources(ROOT / "sources.yaml")}
EXT = {"occupations": "json", "legislation": "json", "rss": "xml"}
ZWSP = chr(0x200B)


def raw(source_id: str) -> str:
    ext = EXT.get(SOURCES[source_id].kind, "html")
    return (RAW / f"{source_id}.{ext}").read_text(encoding="utf-8")


def with_(source_id: str, **changes):
    return dataclasses.replace(SOURCES[source_id], **changes)


@pytest.mark.parametrize("source_id", sorted(SOURCES))
def test_fixture_extracts_min_chars_and_marker(source_id):
    source = SOURCES[source_id]
    text = extract(raw(source_id), source)
    assert len(text) >= source.min_chars
    assert source.required_marker.lower() in text.lower()
    assert text == extract(raw(source_id), source)  # deterministic


def test_ea_page_text_excludes_nav_footer_and_scripts():
    html = raw("ea-msa")
    assert "Get Chartered" in html and "Back to homepage" in html
    text = page_text(html, SOURCES["ea-msa"])
    assert text.startswith("Migration skills assessment\n")
    for junk in ("Get Chartered", "Back to homepage", "Top Menu", "<script", "function("):
        assert junk not in text
    assert "Share this page" not in text.splitlines()
    assert all(line == line.strip() and "  " not in line for line in text.splitlines())


def test_ignore_pattern_removes_matching_line():
    html = raw("ea-fees")
    base = page_text(html, with_("ea-fees", ignore_patterns=())).splitlines()
    line = base[0]
    filtered = page_text(html, with_("ea-fees", ignore_patterns=(f"^{line}$",))).splitlines()
    assert line not in filtered
    assert len(filtered) == len(base) - base.count(line)


def test_unpublished_label_dropped_everywhere():
    source = with_("ea-prepare-msa", ignore_patterns=())
    text = page_text("<main><p>UnPublished</p><p>Real text</p></main>", source)
    assert text == "Real text"


def test_link_set_is_order_independent_absolute_and_filtered():
    source = SOURCES["ea-migrants-hub"]
    a = '<a href="/migrants/migration-agents">For migration agents</a>'
    b = '<a href="https://www.engineersaustralia.org.au/migrants/x-y">X  Y</a>'
    other = '<a href="/news-and-media?page=2">Next</a>'
    first = link_set(f"<main><article>{a}{b}{other}{a}</article></main>", source)
    second = link_set(f"<main><article>{b}{other}{a}</article></main>", source)
    assert first == second
    assert first.splitlines() == [
        "For migration agents | https://www.engineersaustralia.org.au/migrants/migration-agents",
        "X Y | https://www.engineersaustralia.org.au/migrants/x-y",
    ]


def test_news_links_exclude_facets_and_email_protection():
    text = link_set(raw("ea-news"), SOURCES["ea-news"])
    assert text
    assert "?" not in text and "cdn-cgi" not in text


def test_rss_items_title_link_sorted():
    lines = rss_items(raw("ea-rss"), SOURCES["ea-rss"]).splitlines()
    assert len(lines) == 10
    assert lines == sorted(lines)
    assert all(" | https://www.engineersaustralia.org.au/" in line for line in lines)


def test_legislation_titles_format_and_sorted():
    body = raw("leg-migration-instruments")
    lines = legislation_titles(body, SOURCES["leg-migration-instruments"]).splitlines()
    first = json.loads(body)["value"][0]
    assert f"{first['id']} | {first['name']} | {first['makingDate'][:10]}" in lines
    assert lines == sorted(lines) and len(lines) == 50


def test_occupations_fixture_keeps_only_engineers_australia_rows():
    text = occupations(raw("ha-skilled-occupation-list"), SOURCES["ha-skilled-occupation-list"])
    lines = text.splitlines()
    assert lines == sorted(lines)
    assert any("312211" in line and "Civil Engineering Draftsperson" in line for line in lines)
    assert all(line.count(" | ") >= 3 for line in lines)
    assert "<" not in text and ZWSP not in text


def test_occupations_strips_html_and_filters_authority():
    rows = [
        {
            "anzscocode": "<a href='x'>312211</a>",
            "occupation": f"Civil Engineering{ZWSP} Draftsperson",
            "list": "MLTSSL;CSOL",
            "assessauth": "<p> Engineers Australia </p>",
            "visas": "189;<br>190",
        },
        {"anzscocode": "1", "occupation": "Other", "assessauth": "VETASSESS"},
    ]
    body = json.dumps({"d": {"data": rows}})
    expected = "312211 | Civil Engineering Draftsperson | MLTSSL;CSOL | 189; 190"
    assert occupations(body, SOURCES["ha-skilled-occupation-list"]) == expected


def test_schema_json_emits_headings_then_block_text():
    text = schema_json(raw("ha-skills-assessment"), SOURCES["ha-skills-assessment"])
    assert text.splitlines()[0] == "Overview"
    assert "<" not in text


def test_extract_validation_order():
    source = SOURCES["ea-fees"]
    challenge = "<title>Just a moment...</title><script src='/cdn-cgi/challenge-platform/x'>"
    with pytest.raises(FetchFailure, match="challenge_page"):
        extract(challenge, source)
    with pytest.raises(FetchFailure, match="marker_missing"):
        extract("<main><article><p>" + "x" * 500 + "</p></article></main>", source)
    with pytest.raises(FetchFailure, match="too_short"):
        extract("<main><article><p>fee</p></article></main>", source)


def test_extract_malformed_json_is_fetch_failure():
    with pytest.raises(FetchFailure, match="marker_missing"):
        extract("not json", SOURCES["leg-migration-acts"])
