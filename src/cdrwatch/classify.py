"""Keyword tagging, urgency and effective date for a change (docs/PLAN.md section 4)."""

import re
from collections.abc import Iterable

from cdrwatch.models import URGENCY_RANK, Alert, Change, KeywordRule, Source

NOT_STATED = "Not stated in source"

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE_RE = re.compile(rf"\b\d{{1,2}} (?:{_MONTHS}) \d{{4}}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b")


def find_effective_date(lines: Iterable[str]) -> str:
    """First date in the lines, or "Not stated in source". Never guessed."""
    for line in lines:
        match = _DATE_RE.search(line)
        if match:
            return match.group(0)
    return NOT_STATED


def _matches(rule: KeywordRule, lines: tuple[str, ...]) -> bool:
    patterns = [re.compile(term, re.IGNORECASE) for term in rule.terms]
    return any(p.search(line) for p in patterns for line in lines)


def tag(source: Source, change: Change, rules: list[KeywordRule]) -> Alert:
    """Tag a change with every rule whose terms hit an added or removed line."""
    changed = change.added + change.removed
    matched = sorted((r for r in rules if _matches(r, changed)), key=lambda r: r.category)
    urgency = "Informational"
    for rule in matched:
        if URGENCY_RANK[rule.urgency] > URGENCY_RANK[urgency]:
            urgency = rule.urgency
    return Alert(
        source=source,
        change=change,
        categories=tuple(dict.fromkeys(r.category for r in matched)),
        urgency=urgency,
        actions=tuple(dict.fromkeys(r.action for r in matched)),
        page_types=tuple(dict.fromkeys(p for r in matched for p in r.page_types)),
        effective_date=find_effective_date(change.added),
    )
