"""Reachability probe for the v1 sources.

Usage: python -m cdrwatch.probe [--save-fixtures]
Prints one line per source. Never raises. Exit 0.
"""

import argparse
from pathlib import Path

from cdrwatch.fetch import FetchFailure, http_get, looks_like_challenge

EA = "https://www.engineersaustralia.org.au"
MSA = EA + "/migrants/migration-skills-assessment"
HA = "https://immi.homeaffairs.gov.au/visas/working-in-australia"
# $filter + $orderby=makingDate returns HTTP 400 (see docs/SPIKE.md); id desc works.
LEG = (
    "https://api.prod.legislation.gov.au/v1/titles"
    "?%24filter=contains(name,'Migration')&%24orderby=id%20desc&%24top=50"
    "&%24select=id,name,makingDate"
)

SOURCES: list[tuple[str, str]] = [
    ("ea-msa", MSA),
    ("ea-associate-changes", MSA + "/changes-engineering-associate-qualifications"),
    ("ea-fees", MSA + "/assessment-fees-and-additional-services"),
    (
        "ea-prepare-msa",
        EA + "/publications/prepare-your-migration-skills-assessment-application",
    ),
    ("ea-competency-standard", EA + "/about-engineering/national-competency-standard-engineering"),
    ("ea-occupational-categories", EA + "/about-engineering/occupational-categories"),
    ("ea-accreditation", EA + "/about-us/accreditation"),
    ("ea-accredited-programs", EA + "/publications/engineers-australia-accredited-programs"),
    ("ea-migrants-hub", EA + "/migrants"),
    ("ea-news", EA + "/news-and-media"),
    ("ea-rss", EA + "/rss.xml"),
    ("ha-skilled-occupation-list", HA + "/skill-occupation-list"),
    ("ha-skills-assessment", HA + "/skills-assessment"),
    ("leg-migration-instruments", LEG),
]

FIXTURES = Path("tests/fixtures/raw")


def extension(source_id: str) -> str:
    if source_id.endswith("-rss"):
        return "xml"
    if source_id.startswith("leg-"):
        return "json"
    return "html"


def probe_one(source_id: str, url: str, save: bool) -> str:
    try:
        body = http_get(url)
    except FetchFailure as exc:
        return f"{source_id} ERROR {exc.reason}"
    except Exception as exc:  # probe must never raise
        return f"{source_id} ERROR {type(exc).__name__}"
    if save:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        path = FIXTURES / f"{source_id}.{extension(source_id)}"
        path.write_text(body, encoding="utf-8", newline="")
    size = len(body.encode("utf-8"))
    challenge = looks_like_challenge(body)
    return f"{source_id} 200 {size} challenge={challenge} anzsco312211={'312211' in body}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cdrwatch.probe")
    parser.add_argument("--save-fixtures", action="store_true")
    args = parser.parse_args(argv)
    for source_id, url in SOURCES:
        print(probe_one(source_id, url, args.save_fixtures), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
