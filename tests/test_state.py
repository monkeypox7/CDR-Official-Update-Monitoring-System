from cdrwatch.models import SourceMeta
from cdrwatch.state import load_meta, load_snapshot, save_meta, save_snapshot

TEXT = "Assessment fees and additional services\nFast-track applications\n$505"


def test_missing_snapshot_is_none(tmp_path):
    assert load_snapshot(tmp_path, "ea-fees") is None


def test_snapshot_round_trip(tmp_path):
    save_snapshot(tmp_path, "ea-fees", TEXT)
    assert load_snapshot(tmp_path, "ea-fees").splitlines() == TEXT.splitlines()


def test_snapshot_has_single_trailing_newline_and_lf(tmp_path):
    save_snapshot(tmp_path, "ea-fees", TEXT)
    save_snapshot(tmp_path, "ea-msa", TEXT + "\n")
    expected = (TEXT + "\n").encode("utf-8")
    assert (tmp_path / "ea-fees.txt").read_bytes() == expected
    assert (tmp_path / "ea-msa.txt").read_bytes() == expected


def test_snapshot_is_utf8(tmp_path):
    save_snapshot(tmp_path, "ea-fees", "Fee incl. GST é")
    assert load_snapshot(tmp_path, "ea-fees") == "Fee incl. GST é\n"


def test_missing_meta_is_empty(tmp_path):
    assert load_meta(tmp_path) == {}


def test_meta_round_trip(tmp_path):
    meta = {
        "ea-msa": SourceMeta(last_ok=None, fail_count=3, broken_alerted=True),
        "ea-fees": SourceMeta(last_ok="2026-09-14", fail_count=0, broken_alerted=False),
    }
    save_meta(tmp_path, meta)
    assert load_meta(tmp_path) == meta


def test_save_meta_is_byte_identical_and_sorted(tmp_path):
    meta_a = {"ea-msa": SourceMeta(fail_count=1), "ea-fees": SourceMeta(last_ok="2026-09-14")}
    meta_b = {"ea-fees": SourceMeta(last_ok="2026-09-14"), "ea-msa": SourceMeta(fail_count=1)}
    save_meta(tmp_path, meta_a)
    first = (tmp_path / "meta.json").read_bytes()
    save_meta(tmp_path, meta_b)
    second = (tmp_path / "meta.json").read_bytes()
    assert first == second
    assert first.endswith(b"}\n")
    assert b"\r" not in first
    assert first.index(b'"ea-fees"') < first.index(b'"ea-msa"')
    assert b'\n  "ea-fees": {\n' in first
