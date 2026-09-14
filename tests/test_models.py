import dataclasses

import pytest

from cdrwatch.models import (
    URGENCY_RANK,
    Alert,
    Change,
    KeywordRule,
    RunSummary,
    Source,
    SourceMeta,
)


def make_source() -> Source:
    return Source(
        id="ea-fees",
        name="Engineers Australia - Assessment fees and additional services",
        kind="page",
        url="https://www.engineersaustralia.org.au/migrants/migration-skills-assessment/assessment-fees-and-additional-services",
        priority="Critical",
        fetch="http",
    )


def test_source_defaults():
    src = make_source()
    assert src.selector is None
    assert src.required_marker is None
    assert src.min_chars == 200
    assert src.ignore_patterns == ()
    assert src.link_pattern is None


@pytest.mark.parametrize(
    "obj",
    [
        make_source(),
        KeywordRule(
            category="Fees",
            terms=("fee",),
            urgency="Critical",
            action="Update pricing figures.",
            page_types=("Pricing",),
        ),
        Change(source_id="ea-fees", added=("a",), removed=("b",)),
        RunSummary(date="2026-09-14", checked=14, informational=0, broken=()),
    ],
)
def test_frozen_dataclasses_reject_mutation(obj):
    field = dataclasses.fields(obj)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, field, "x")


def test_alert_is_frozen():
    src = make_source()
    alert = Alert(
        source=src,
        change=Change(source_id=src.id, added=("fee $1",), removed=()),
        categories=("Fees",),
        urgency="Critical",
        actions=("Update pricing figures.",),
        page_types=("Pricing",),
        effective_date="Not stated in source",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        alert.urgency = "High"


def test_source_meta_is_mutable_with_defaults():
    meta = SourceMeta()
    assert (meta.last_ok, meta.fail_count, meta.broken_alerted) == (None, 0, False)
    meta.fail_count = 3
    assert meta.fail_count == 3


def test_urgency_rank_order():
    assert URGENCY_RANK == {"Informational": 0, "High": 1, "Critical": 2}
    assert URGENCY_RANK["Critical"] > URGENCY_RANK["High"] > URGENCY_RANK["Informational"]
