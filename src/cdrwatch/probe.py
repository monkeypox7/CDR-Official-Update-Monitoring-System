"""Live probe: fetch and extract every source in sources.yaml.

Usage: python -m cdrwatch.probe [--sources sources.yaml] [--save-fixtures]
Prints "OK <id> <chars>" or "ERROR <id> <reason>" per source. Never raises. Exit 0.
"""

import argparse
from pathlib import Path

from cdrwatch.config import load_sources
from cdrwatch.extract import extract
from cdrwatch.fetch import FetchFailure, fetch_source
from cdrwatch.models import Source

FIXTURES = Path("tests/fixtures/raw")
EXTENSIONS = {"rss": "xml", "legislation": "json", "occupations": "json"}


def probe_one(source: Source, save: bool) -> str:
    try:
        body = fetch_source(source)
        if save:
            FIXTURES.mkdir(parents=True, exist_ok=True)
            path = FIXTURES / f"{source.id}.{EXTENSIONS.get(source.kind, 'html')}"
            path.write_text(body, encoding="utf-8", newline="")
        text = extract(body, source)
    except FetchFailure as exc:
        return f"ERROR {source.id} {exc.reason}"
    except Exception as exc:  # probe must never raise
        return f"ERROR {source.id} {type(exc).__name__}"
    return f"OK {source.id} {len(text)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cdrwatch.probe")
    parser.add_argument("--sources", default="sources.yaml")
    parser.add_argument("--save-fixtures", action="store_true")
    args = parser.parse_args(argv)
    for source in load_sources(args.sources):
        print(probe_one(source, args.save_fixtures), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
