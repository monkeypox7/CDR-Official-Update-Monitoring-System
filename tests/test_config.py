from pathlib import Path

import pytest
import yaml

from cdrwatch.config import load_keywords, load_sources
from cdrwatch.models import KeywordRule, Source

ROOT = Path(__file__).parent.parent

VALID = {
    "id": "ea-fees",
    "name": "Engineers Australia - Assessment fees and additional services",
    "kind": "page",
    "url": "https://www.engineersaustralia.org.au/migrants/migration-skills-assessment/assessment-fees-and-additional-services",
    "priority": "Critical",
    "fetch": "http",
    "selector": "main article",
    "required_marker": "fee",
    "min_chars": 500,
    "ignore_patterns": ["^UnPublished$"],
    "link_pattern": None,
}

RULE = {
    "category": "Fees",
    "terms": ["fee", "\\$\\d"],
    "urgency": "Critical",
    "action": "Update pricing figures on all pages that show EA fees.",
    "page_types": ["Pricing", "MSA guide"],
}

SECTION_4_CATEGORIES = {
    "Fees",
    "CDR evidence",
    "Career Episode",
    "Summary Statement",
    "ANZSCO/Occupations",
    "Pathways",
    "Deadlines/Interim arrangements",
    "Plagiarism/AI rules",
    "Assessing authority",
    "Engineering Associate",
    "CPD",
    "English",
    "Accreditation/RTO",
    "Professional Engineer",
    "Engineering Technologist",
    "Engineering Manager",
    "Processing times",
    "Skilled employment",
    "Review/Appeal",
    "Competency standards",
    "MSA guidance",
}


def write(tmp_path: Path, data) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_load_sources_builds_source(tmp_path):
    [src] = load_sources(write(tmp_path, [VALID]))
    assert src == Source(**{**VALID, "ignore_patterns": ("^UnPublished$",)})


def test_load_sources_defaults_and_post_json(tmp_path):
    entry = {k: VALID[k] for k in ("id", "name", "kind", "url", "priority", "fetch")}
    entry["post_json"] = '{"a":1}'
    [src] = load_sources(write(tmp_path, [entry]))
    assert (src.selector, src.min_chars, src.ignore_patterns) == (None, 200, ())
    assert src.post_json == '{"a":1}'


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"kind": "pdf"}, "kind"),
        ({"fetch": "curl"}, "fetch"),
        ({"priority": "Low"}, "priority"),
        ({"url": None}, "url"),
        ({"ignore_patterns": ["("]}, "ignore_patterns"),
        ({"link_pattern": "[a-"}, "link_pattern"),
        ({"min_chars": "many"}, "min_chars"),
        ({"selectr": "main"}, "selectr"),
    ],
)
def test_invalid_source_names_id_and_field(tmp_path, override, field):
    entry = {**VALID, **override}
    if override.get("url", "x") is None:
        del entry["url"]
    with pytest.raises(ValueError) as exc:
        load_sources(write(tmp_path, [entry]))
    assert "ea-fees" in str(exc.value)
    assert field in str(exc.value)


def test_duplicate_id_rejected(tmp_path):
    with pytest.raises(ValueError, match="ea-fees.*id"):
        load_sources(write(tmp_path, [VALID, VALID]))


def test_browser_fetch_rejected_in_v1(tmp_path):
    with pytest.raises(ValueError, match="browser fetch not supported in v1"):
        load_sources(write(tmp_path, [{**VALID, "fetch": "browser"}]))


def test_sources_file_must_be_list(tmp_path):
    with pytest.raises(ValueError):
        load_sources(write(tmp_path, {"id": "x"}))


def test_load_keywords_builds_rule(tmp_path):
    [rule] = load_keywords(write(tmp_path, [RULE]))
    assert rule == KeywordRule(
        category="Fees",
        terms=("fee", "\\$\\d"),
        urgency="Critical",
        action=RULE["action"],
        page_types=("Pricing", "MSA guide"),
    )


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"terms": ["("]}, "terms"),
        ({"terms": []}, "terms"),
        ({"urgency": "Urgent"}, "urgency"),
    ],
)
def test_invalid_keyword_names_field(tmp_path, override, field):
    with pytest.raises(ValueError) as exc:
        load_keywords(write(tmp_path, [{**RULE, **override}]))
    assert "Fees" in str(exc.value)
    assert field in str(exc.value)


def test_repo_sources_yaml_loads_15_sources():
    sources = load_sources(ROOT / "sources.yaml")
    assert len(sources) == 15
    assert all(s.required_marker for s in sources)


def test_repo_keywords_yaml_covers_every_section_4_category():
    rules = load_keywords(ROOT / "keywords.yaml")
    assert {r.category for r in rules} == SECTION_4_CATEGORIES
    critical = {r.category for r in rules if r.urgency == "Critical"}
    assert critical == {
        "Fees",
        "CDR evidence",
        "Career Episode",
        "Summary Statement",
        "ANZSCO/Occupations",
        "Pathways",
        "Deadlines/Interim arrangements",
        "Plagiarism/AI rules",
        "Assessing authority",
        "Engineering Associate",
    }
