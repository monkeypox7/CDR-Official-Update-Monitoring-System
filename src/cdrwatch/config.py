"""Load and validate sources.yaml and keywords.yaml into model dataclasses."""

import re
from dataclasses import fields
from pathlib import Path
from typing import get_args

import yaml

from cdrwatch.models import KeywordRule, Kind, Source, Urgency

PRIORITIES = ("Critical", "High")
SOURCE_FIELDS = {f.name for f in fields(Source)}
REQUIRED = ("id", "name", "kind", "url", "priority", "fetch")


def _read_list(path: str | Path) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(e, dict) for e in data):
        raise ValueError(f"{path}: expected a list of mappings")
    return data


def _check_regexes(label: str, field: str, patterns) -> None:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except (re.error, TypeError) as exc:
            raise ValueError(f"{label}: {field}: bad regex {pattern!r} ({exc})") from exc


def _source(entry: dict) -> Source:
    label = f"source {entry.get('id')}"
    for key in entry:
        if key not in SOURCE_FIELDS:
            raise ValueError(f"{label}: {key}: unknown field")
    for key in REQUIRED:
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"{label}: {key}: missing or not a string")
    if entry["kind"] not in get_args(Kind):
        raise ValueError(f"{label}: kind: unknown kind {entry['kind']!r}")
    if entry["fetch"] == "browser":
        raise ValueError(f"{label}: fetch: browser fetch not supported in v1")
    if entry["fetch"] != "http":
        raise ValueError(f"{label}: fetch: unknown fetch {entry['fetch']!r}")
    if entry["priority"] not in PRIORITIES:
        raise ValueError(f"{label}: priority: unknown priority {entry['priority']!r}")
    min_chars = entry.get("min_chars", 200)
    if not isinstance(min_chars, int) or isinstance(min_chars, bool) or min_chars < 0:
        raise ValueError(f"{label}: min_chars: expected a non-negative integer")
    ignore = entry.get("ignore_patterns") or []
    if not isinstance(ignore, list):
        raise ValueError(f"{label}: ignore_patterns: expected a list")
    _check_regexes(label, "ignore_patterns", ignore)
    if entry.get("link_pattern") is not None:
        _check_regexes(label, "link_pattern", [entry["link_pattern"]])
    return Source(**{**entry, "min_chars": min_chars, "ignore_patterns": tuple(ignore)})


def load_sources(path: str | Path) -> list[Source]:
    sources: list[Source] = []
    seen: set[str] = set()
    for entry in _read_list(path):
        source = _source(entry)
        if source.id in seen:
            raise ValueError(f"source {source.id}: id: duplicate id")
        seen.add(source.id)
        sources.append(source)
    return sources


def _rule(entry: dict) -> KeywordRule:
    label = f"keyword {entry.get('category')}"
    for key in ("category", "action"):
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError(f"{label}: {key}: missing or not a string")
    terms = entry.get("terms")
    if not isinstance(terms, list) or not terms:
        raise ValueError(f"{label}: terms: expected a non-empty list")
    _check_regexes(label, "terms", terms)
    if entry.get("urgency") not in get_args(Urgency):
        raise ValueError(f"{label}: urgency: unknown urgency {entry.get('urgency')!r}")
    page_types = entry.get("page_types") or []
    if not isinstance(page_types, list):
        raise ValueError(f"{label}: page_types: expected a list")
    return KeywordRule(
        category=entry["category"],
        terms=tuple(terms),
        urgency=entry["urgency"],
        action=entry["action"],
        page_types=tuple(page_types),
    )


def load_keywords(path: str | Path) -> list[KeywordRule]:
    return [_rule(entry) for entry in _read_list(path)]
