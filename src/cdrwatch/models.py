"""Shared data types. Binding interface from docs/PLAN.md Task 0; frozen after S1."""

from dataclasses import dataclass
from typing import Literal

Kind = Literal["page", "links", "rss", "legislation", "occupations", "schema_json"]
Urgency = Literal["Critical", "High", "Informational"]
URGENCY_RANK: dict[str, int] = {"Informational": 0, "High": 1, "Critical": 2}


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    kind: Kind
    url: str
    priority: Urgency
    fetch: Literal["http", "browser"]
    selector: str | None = None
    required_marker: str | None = None
    min_chars: int = 200
    ignore_patterns: tuple[str, ...] = ()
    link_pattern: str | None = None
    post_json: str | None = None


@dataclass(frozen=True)
class KeywordRule:
    category: str
    terms: tuple[str, ...]
    urgency: Urgency
    action: str
    page_types: tuple[str, ...]


@dataclass(frozen=True)
class Change:
    source_id: str
    added: tuple[str, ...]
    removed: tuple[str, ...]


@dataclass(frozen=True)
class Alert:
    source: Source
    change: Change
    categories: tuple[str, ...]
    urgency: Urgency
    actions: tuple[str, ...]
    page_types: tuple[str, ...]
    effective_date: str


@dataclass
class SourceMeta:
    last_ok: str | None = None
    fail_count: int = 0
    broken_alerted: bool = False


@dataclass(frozen=True)
class RunSummary:
    date: str
    checked: int
    informational: int
    broken: tuple[str, ...]
