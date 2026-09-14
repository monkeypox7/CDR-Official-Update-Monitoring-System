---
name: add-source
description: Add, change or remove a watched official source in CDR Watch (sources.yaml). Use for any request like "watch this page", "add source", "monitor this URL", "remove source", "source is broken", "change selector". Enforces official-only scope, live verification, a real fixture, a regression test, and a silent baseline.
---

# Add / change / remove a source

## Gate (stop if any fails)
- URL domain is official: `engineersaustralia.org.au`, `homeaffairs.gov.au`, `legislation.gov.au`, or another `.gov.au` the owner named. Anything else (competitors, blogs, agents) -> refuse and say it is out of v1 scope.
- The page is relevant to a doc section 2 topic (CDR, MSA, fees, ANZSCO, accreditation, competency, pathways...). Name the topic.

## Add or change
1. Dispatch `source-checker` agent with the URL, proposed kind (`page|links|rss|legislation`) and selector. Ask it to save the fixture.
2. Verdict must be `monitorable` or `needs-browser`. `blocked` or `wrong-selector` -> fix selector once and recheck; still failing -> stop and report.
3. Add the entry to `sources.yaml` using the exact shape in `docs/PLAN.md` section 3. id = kebab-case, prefix `ea-`, `ha-` or `leg-`. Put proposed `ignore_patterns` from the checker.
4. Add one test in `tests/test_extract.py`: fixture -> extracted text contains a stable heading and has length >= `min_chars`.
5. Run `pytest -q`, `ruff check .`, then `python -m cdrwatch.run --dry-run --only <id> --no-confirm`. Paste output.
6. Commit: `feat(sources): watch <id>` (body: topic + checker verdict). The first live run saves a baseline and sends no alert - say so.

## Remove
1. Delete the entry from `sources.yaml` and its fixture/test.
2. Leave `state/<id>.txt` for history; the run ignores snapshots without a source.
3. Commit: `chore(sources): stop watching <id>` with the reason.

## Broken source
Run `source-checker` on the id. Selector drift -> update selector + fixture + test. Blocked -> switch `fetch: browser` only if the checker shows browser works; otherwise report to owner. Never delete a broken source silently.
