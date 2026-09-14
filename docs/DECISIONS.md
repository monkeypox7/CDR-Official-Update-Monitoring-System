# Owner decisions (binding, override docs/PLAN.md where they differ)

Date: 2026-09-14, after S1 (PR #7). Source facts: `docs/SPIKE.md`.

## D1 - Legislation: two sources (total sources = 15)
- `leg-migration-instruments`, kind `legislation`, url
  `https://api.prod.legislation.gov.au/v1/titles?%24filter=contains(name,'Migration')&%24orderby=id%20desc&%24top=50&%24select=id,name,makingDate`
- `leg-migration-acts`, kind `legislation`, url
  `https://api.prod.legislation.gov.au/v1/titles?%24filter=contains(name,'Migration')&%24orderby=year%20desc&%24top=50&%24select=id,name,makingDate`
- Both: priority High, fetch http, required_marker `Migration`, min_chars 200.
- Snapshot line: `id | name | makingDate[:10]`, sorted. Every "14 sources" in PLAN.md means "all sources in sources.yaml" (15).

## D2 - Home Affairs occupation list via POST (S2 owns these additions)
- `models.py` (only these two changes):
  - `Kind` gains `"occupations"` and `"schema_json"`.
  - `Source` gains a last field `post_json: str | None = None`.
- `fetch.py` additions:
  - `http_post_json(url: str, body: str, *, timeout: int = 60, retries: int = 3) -> str` - `BROWSER_HEADERS` + `Content-Type: application/json; charset=utf-8`, same retry/backoff/FetchFailure rules as `http_get`.
  - `fetch_source(source: Source) -> str` - `post_json` set -> `http_post_json`; else `http_get`. S5 `run.py` calls only `fetch_source`.
- Source `ha-skilled-occupation-list`: kind `occupations`, url `https://immi.homeaffairs.gov.au/_layouts/15/api/Data.aspx/GetSkillOccupation`, post_json `{"webUrl":"/work-in-australia","listname":"Occupations"}`, priority Critical, required_marker `312211`, min_chars 200.
- `occupations` extractor: parse `d.data`; keep rows whose stripped `assessauth` contains `Engineers Australia`; strip HTML from values; line `anzscocode | occupation | list | visas`; sorted.
- S2 PR must show the spike/probe job returning OK for this POST from GitHub Actions (probe.py changes trigger `spike.yml`).

## D3 - ha-skills-assessment
- kind `schema_json`: parse JSON in `input#ctl00_PlaceHolderMain_PageSchemaHiddenField_Input[value]`; for each item in `content` emit the `text` heading, then the visible text lines of its `block` HTML.

## D4 - No browser fetch in v1
- Do not add playwright. `config.load_sources` rejects `fetch: browser` with ValueError ("browser fetch not supported in v1").

## D5 - Page details
- EA publication pages (`ea-prepare-msa`, `ea-accredited-programs`): selector `main`, min_chars 200. PDF name/date changes count as changes.
- Ignore pattern `^UnPublished$` wherever it appears.
- Challenge rule as implemented in S1 (checks `<article` and `<main`).

## D6 - Running modules
- `python -m cdrwatch.<module>` needs `PYTHONPATH=src` locally and in `monitor.yml`.

## D7 - Parallel start (to finish fast)
- S2, S3, S4, S5, S6 start at the same time.
- S5 writes `run.py`, `tests/test_integration.py` and `monitor.yml` immediately against the PLAN + D2 interfaces, but does not open its PR until #2, #3, #4 are CLOSED; then it rebases, runs tests, ships, and does the live runs.
- S6 ships `README.md` first as its own PR (`Refs #6`); after #5 is CLOSED it ships the simulation tests (`Closes #6`) and tags `v1.0.0-rc1`.
