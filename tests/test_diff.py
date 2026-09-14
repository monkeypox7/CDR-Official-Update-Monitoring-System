from cdrwatch.diff import compare

# Lines copied from tests/fixtures/raw/ea-fees.html visible text.
FEES_OLD = "\n".join(
    [
        "Assessment fees and additional services",
        "Migration skills assessment fees",
        "Our migration skills assessment fees for the 2026 to 2027 period are set out below.",
        "Standard competency demonstration report",
        "$940",
        "$1034",
    ]
)


def test_baseline_returns_none():
    assert compare("ea-fees", None, FEES_OLD) is None


def test_identical_text_returns_none():
    assert compare("ea-fees", FEES_OLD, FEES_OLD) is None


def test_reordered_identical_lines_returns_none():
    reordered = "\n".join(reversed(FEES_OLD.splitlines()))
    assert compare("ea-fees", FEES_OLD, reordered) is None


def test_blank_lines_are_ignored():
    assert compare("ea-fees", FEES_OLD, FEES_OLD.replace("\n", "\n\n") + "\n") is None


def test_one_line_changed():
    new = FEES_OLD.replace("$1034", "$1512.50")
    change = compare("ea-fees", FEES_OLD, new)
    assert change is not None
    assert change.source_id == "ea-fees"
    assert change.added == ("$1512.50",)
    assert change.removed == ("$1034",)


def test_added_and_removed_keep_new_and_old_order():
    old = "\n".join(["Fast-track applications", "$505", "$555.50"])
    new = "\n".join(["$780", "Fast-track applications", "$858"])
    change = compare("ea-fees", old, new)
    assert change is not None
    assert change.added == ("$780", "$858")
    assert change.removed == ("$505", "$555.50")
