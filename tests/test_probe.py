from unittest import mock

from cdrwatch import probe
from cdrwatch.fetch import FetchFailure
from cdrwatch.models import Source

PAGE = Source(
    id="ea-fees",
    name="Fees",
    kind="page",
    url="https://www.engineersaustralia.org.au/x",
    priority="Critical",
    fetch="http",
    selector="main",
    required_marker="fee",
    min_chars=5,
)


def test_probe_one_prints_ok_with_extracted_chars():
    with mock.patch.object(probe, "fetch_source", return_value="<main><p>fee text</p></main>"):
        assert probe.probe_one(PAGE, save=False) == "OK ea-fees 8"


def test_probe_one_reports_fetch_and_extract_failures():
    with mock.patch.object(probe, "fetch_source", side_effect=FetchFailure("http_403")):
        assert probe.probe_one(PAGE, save=False) == "ERROR ea-fees http_403"
    with mock.patch.object(probe, "fetch_source", return_value="<main>nothing</main>"):
        assert probe.probe_one(PAGE, save=False) == "ERROR ea-fees marker_missing"
    with mock.patch.object(probe, "fetch_source", side_effect=RuntimeError("boom")):
        assert probe.probe_one(PAGE, save=False) == "ERROR ea-fees RuntimeError"


def test_probe_saves_fixture_by_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "FIXTURES", tmp_path)
    body = '{"value": []}'
    leg = Source(id="leg-x", name="L", kind="legislation", url="u", priority="High", fetch="http")
    with mock.patch.object(probe, "fetch_source", return_value=body):
        probe.probe_one(leg, save=True)
    assert (tmp_path / "leg-x.json").read_text(encoding="utf-8") == body


def test_main_probes_every_source_in_file(tmp_path, capsys):
    path = tmp_path / "sources.yaml"
    path.write_text(
        "- {id: a, name: A, kind: page, url: 'https://x/a', priority: High, fetch: http}\n"
        "- {id: b, name: B, kind: page, url: 'https://x/b', priority: High, fetch: http}\n",
        encoding="utf-8",
    )
    with mock.patch.object(probe, "fetch_source", side_effect=FetchFailure("timeout")):
        assert probe.main(["--sources", str(path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["ERROR a timeout", "ERROR b timeout"]
