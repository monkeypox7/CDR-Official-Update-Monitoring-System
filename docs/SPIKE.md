# Session 1 spike - fetch mode per source

Date: 2026-09-14. Local = home IP, Windows, `python -m cdrwatch.probe --save-fixtures`.
Actions = GitHub `ubuntu-latest` runner, workflow `spike`, run 34826682076 on PR #7.
Probe line format: `id status bytes challenge=<bool> anzsco312211=<bool>`.
Raw fixtures: `tests/fixtures/raw/<id>.<ext>`, captured locally on the date above.

## Results

"Text" = characters of visible text in the named container, measured on the local fixture.

| id | local | Actions | fetch | selector hint | notes |
|---|---|---|---|---|---|
| ea-msa | 200, 101611 B | 200, 101611 B | http | `main article` | text 8456 |
| ea-associate-changes | 200, 74105 B | 200, 74105 B | http | `main article` | text 5738; contains 312211 |
| ea-fees | 200, 72348 B | 200, 72348 B | http | `main article` | text 4112 |
| ea-prepare-msa | 200, 59256 B | 200, 59256 B | http | `main` | publication page, no `<article`; text 373 |
| ea-competency-standard | 200, 96779 B | 200, 96779 B | http | `main article` | text 11543 |
| ea-occupational-categories | 200, 75612 B | 200, 75612 B | http | `main article` | text 3537 |
| ea-accreditation | 200, 78857 B | 200, 78857 B | http | `main article` | text 4800 |
| ea-accredited-programs | 200, 59118 B | 200, 59118 B | http | `main` | publication page, no `<article`; text 328 |
| ea-migrants-hub | 200, 73113 B | 200, 73113 B | http | `main article` | links kind; 26 links in `main`, 4 under `/migrants` |
| ea-news | 200, 122354 B | 200, 122354 B | http | `main article` | links kind; 86 links in `main`, filter facets and `/cdn-cgi` included |
| ea-rss | 200, 612577 B | 200, 612577 B | http | `item` | 10 `<item>` elements |
| ha-skilled-occupation-list | 200, 1288602 B | 200, 1288515 B | http | `main` + data endpoint | table is loaded by JS; see notes |
| ha-skills-assessment | 200, 1300355 B | 200, 1300348 B | http | hidden input, see notes | `main` text is 40 chars; body is embedded JSON |
| leg-migration-instruments | 200, 7682 B | 200, 7682 B | http | JSON `value[]` | see Legislation notes |

Every source returned HTTP 200 with `challenge=False` from GitHub Actions. No source is blocked. Fetch mode `http` for all 14; no source needs `browser`.

Home Affairs byte counts differ by under 100 B between runs, so those pages carry per-request noise; the extractor must not compare raw HTML.

## Notes for later sessions

Owner-approved deviations from `docs/PLAN.md` (approved in the S1 chat, 2026-09-14):

1. **Challenge rule also checks `<main`.** `looks_like_challenge(html)` is
   `("cf-chl" or "Just a moment" or "challenge-platform") in html and "<article" not in html and "<main" not in html`.
   Reason: every EA page loads a normal `/cdn-cgi/challenge-platform/scripts/jsd/main.js`
   script, and EA publication pages (`node--type-publication`: ea-prepare-msa,
   ea-accredited-programs) have `<main>` but no `<article>`. The plan rule flagged both
   as challenge pages. Test: `tests/test_fetch.py::test_challenge_false_on_real_ea_pages`.
2. **Legislation query in PLAN section 3 does not work.** Recorded here for S2; the
   probe uses a query that works. Details below.

Facts S2-S4 must know:

3. **Legislation API (base `https://api.prod.legislation.gov.au/v1/titles`).**
   - Probe query, HTTP 200 (saved as `leg-migration-instruments.json`):
     `?%24filter=contains(name,'Migration')&%24orderby=id%20desc&%24top=50&%24select=id,name,makingDate`
   - Output shape: `{"@odata.context": str, "@odata.count": 2454, "value": [{"id": "F2026L01149", "name": "...", "makingDate": "2026-08-31T00:00:00"}, ...]}`.
   - HTTP 400 ("Exception has been thrown by the target of an invocation."):
     `$filter=contains(...)` combined with `$orderby=makingDate` (asc or desc), and
     `$filter` with `year ge 2025` or `makingDate ge 2025-01-01`.
   - HTTP 200: `$orderby=makingDate desc` without `$filter` (returns all legislation, not just Migration).
   - Limitation of the probe query: `id desc` puts every `F` id (instruments) before any
     `C` id (Acts), so the top 50 held only instruments (first row 2026-08-31, last row 2025-08-05) and
     missed `C2026A00039` "Migration Amendment (Combatting Migrant Exploitation) Act 2026".
   - `$orderby=year%20desc` with the same filter is HTTP 200 and returns 30 Acts + 20
     instruments, but misses 2026 instruments such as `F2026L01149`.
   - `$top` is capped (the API error names a limit of 500 in one query and 100 in another); `$skip` paging works.
   - Owner decision needed before S2 builds the legislation extractor: which query
     (or union of the `id desc` and `year desc` queries, sorted by `makingDate` in code)
     defines the snapshot.
4. **ha-skilled-occupation-list data URL.** The occupation table is rendered by
   `/AssetLibrary/dist/angular/table-search.js` from inline config:
   - `POST https://immi.homeaffairs.gov.au/_layouts/15/api/Data.aspx/GetSkillOccupation`
   - headers: browser headers + `Content-Type: application/json; charset=utf-8`
   - body: `{"webUrl":"/work-in-australia","listname":"Occupations"}`
   - result locally: HTTP 200, 2101239 B, `{"d": {"__type", "success": true, "data": [714 rows], "message"}}`;
     row keys `occupation, anzscocode, visacaveats, list, assessauth, visas` (values contain HTML).
     312211 = "Civil Engineering Draftsperson", list `MLTSSL;CSOL`, authority Engineers Australia.
   - Saved as `tests/fixtures/raw/ha-skilled-occupation-list.json`.
   - GET on the same URL returns HTTP 200 with 12797 B and no data.
   - Verified from the local IP only, not from Actions.
   - `fetch.http_get` is GET-only and PLAN allows S2 to add only `browser_get`, so using
     this endpoint needs an owner decision (a POST helper, or monitor only the page text).
5. **Browser fetch does not work for Home Affairs.** Headless Chromium (Playwright
   1.62.0, scratchpad venv) gets HTTP 403 "Access Denied" (Akamai) on both ha-* pages,
   with default and Chrome user agents. Plain `requests` with `BROWSER_HEADERS` gets 200.
   Do not switch HA sources to `fetch: browser`.
6. **ha-skills-assessment body lives in a hidden input.** `main` text is only the title.
   The page text is JSON in
   `input#ctl00_PlaceHolderMain_PageSchemaHiddenField_Input[value]`:
   `{"content": [{"text": "Overview", "block": "<html>"}, ...]}`. The extractor must parse that JSON and the HTML blocks.
7. **EA publication pages are PDF landing pages.** Visible text is 328-373 chars:
   date, title, one sentence and a PDF link such as
   `/sites/default/files/2026-06/engineers-australia-accredited-programs-jun-26.pdf`.
   A new edition shows as a new PDF name and date. PDF contents are not monitored.
   `min_chars: 500` would fail these two; the default 200 passes.
8. **ha-skilled-occupation-list `main` starts with "UnPublished"** (SharePoint editor label). Candidate `ignore_patterns` entry.
9. **Running modules.** No package install: CI tests use pytest `pythonpath = ["src"]`;
   `python -m cdrwatch.<module>` needs `PYTHONPATH=src` (set in `spike.yml`). S5 needs the same in `monitor.yml`.
10. **Ruff excludes `.claude` and `docs`** (`pyproject.toml`). Ruff 0.16 formats Python code blocks in
    `docs/PLAN.md` and flags `.claude/hooks/post_edit.py`; both are owner-only files.
11. **Python.** CI runs 3.12. S1 local venv used 3.13 (3.12 not installed on the owner machine).
