from cdrwatch.classify import find_effective_date, tag
from cdrwatch.diff import compare
from cdrwatch.models import Change, KeywordRule, Source

SOURCE = Source(
    id="ea-fees",
    name="Engineers Australia - Assessment fees and additional services",
    kind="page",
    url="https://www.engineersaustralia.org.au/migrants/migration-skills-assessment/assessment-fees-and-additional-services",
    priority="Critical",
    fetch="http",
)

FEES = KeywordRule(
    category="Fees",
    terms=("fee", "fast track", r"\$\d", "AUD"),
    urgency="Critical",
    action="Update pricing figures on all pages that show EA fees.",
    page_types=("Pricing", "MSA guide"),
)
SKILLED = KeywordRule(
    category="Skilled employment",
    terms=("skilled employment",),
    urgency="High",
    action="Review skilled employment guidance.",
    page_types=("Skilled employment guide",),
)
RULES = [SKILLED, FEES]


def test_keyword_only_in_unchanged_lines_is_informational():
    old = "Migration skills assessment fees\nFast-track applications\n$505"
    new = old + "\nAdditional services"
    change = compare("ea-fees", old, new)
    assert change == Change(source_id="ea-fees", added=("Additional services",), removed=())
    alert = tag(SOURCE, change, RULES)
    assert alert.urgency == "Informational"
    assert alert.categories == ()
    assert alert.actions == ()
    assert alert.page_types == ()
    assert alert.source is SOURCE
    assert alert.change is change


def test_fees_term_in_added_line_is_critical():
    change = Change(source_id="ea-fees", added=("$1512.50",), removed=("$1034",))
    alert = tag(SOURCE, change, RULES)
    assert alert.urgency == "Critical"
    assert alert.categories == ("Fees",)
    assert alert.actions == ("Update pricing figures on all pages that show EA fees.",)
    assert alert.page_types == ("Pricing", "MSA guide")


def test_term_in_removed_line_matches():
    change = Change(source_id="ea-fees", added=(), removed=("Fast-track applications",))
    rule = KeywordRule("Fees", ("fast-track",), "Critical", "Update fees.", ("Pricing",))
    assert tag(SOURCE, change, [rule]).urgency == "Critical"


def test_terms_are_case_insensitive():
    change = Change(source_id="ea-fees", added=("Migration skills assessment fees",), removed=())
    rule = KeywordRule("Fees", ("FEES",), "Critical", "Update fees.", ("Pricing",))
    assert tag(SOURCE, change, [rule]).categories == ("Fees",)


def test_two_categories_highest_urgency_and_sorted():
    change = Change(
        source_id="ea-fees",
        added=("Competency demonstration report plus", "relevant skilled employment assessment"),
        removed=("$1375",),
    )
    alert = tag(SOURCE, change, RULES)
    assert alert.urgency == "Critical"
    assert alert.categories == ("Fees", "Skilled employment")
    assert alert.actions == (FEES.action, SKILLED.action)
    assert alert.page_types == ("Pricing", "MSA guide", "Skilled employment guide")


def test_effective_date_from_added_lines():
    change = Change(source_id="ea-fees", added=("$940", "Last updated 02 July 2026"), removed=())
    assert tag(SOURCE, change, RULES).effective_date == "02 July 2026"


def test_effective_date_ignores_removed_lines():
    change = Change(source_id="ea-fees", added=("$940",), removed=("Last updated 02 July 2026",))
    assert tag(SOURCE, change, RULES).effective_date == "Not stated in source"


def test_find_effective_date_day_month_year():
    assert find_effective_date(["$505", "Last updated 02 July 2026"]) == "02 July 2026"


# Lines copied from tests/fixtures/raw/ea-accredited-programs.html and
# leg-migration-instruments.json (id | name | makingDate[:10]).
PDF_LINE = "/sites/default/files/2026-06/engineers-australia-accredited-programs-jun-26.pdf"
LEG_LINE = (
    "F2026L01149 | Migration (Arrangements for Child Visa Applications) Instrument 2026"
    " | 2026-08-31"
)


def test_find_effective_date_iso():
    assert find_effective_date([PDF_LINE, LEG_LINE]) == "2026-08-31"


def test_find_effective_date_first_match_wins():
    assert find_effective_date([LEG_LINE, "Last updated 02 July 2026"]) == "2026-08-31"


def test_find_effective_date_not_stated():
    assert find_effective_date(["Fee excl.", "GST", "AUD"]) == "Not stated in source"
    assert find_effective_date([]) == "Not stated in source"
