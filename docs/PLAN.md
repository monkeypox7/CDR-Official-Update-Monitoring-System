# CDR Watch v1 - Product and Implementation Plan

> **For agentic workers:** Execute one session at a time from `docs/SESSION_PROMPTS.md`. Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. Do not start a task until the previous task's acceptance checks pass.

**Goal:** Detect meaningful changes on official CDR / Engineers Australia / Home Affairs / Legislation sources once a day and post a structured alert to Slack, with a GitHub Issue as the change tracker.

**Architecture:** One small Python package run by a scheduled GitHub Actions workflow. Each run fetches every source in `sources.yaml`, extracts the meaningful text (or link list / feed items / legislation titles), compares it with the last committed snapshot in `state/`, tags changes with keywords from `keywords.yaml`, posts material changes to a Slack incoming webhook, opens a GitHub Issue per material change, then commits the new snapshots. No server, no database, no AI, no paid service.

**Tech Stack:** Python 3.12, requests, beautifulsoup4 + lxml, PyYAML, pytest, ruff. Playwright (Chromium) only for sources proven to need JavaScript. GitHub Actions (free, public repo). Slack incoming webhook (free).

## Global Constraints

- Scope: official sources only. Competitor sites are out of scope for v1.
- Zero cost: no paid API, no hosted server, no LLM.
- No Rails, no database. State lives in `state/` committed to git.
- Alerts: deterministic diff + keyword tags. Never infer requirements the source does not state (doc "Publishing rule").
- Schedule: daily at 23:00 UTC (09:00 AEST next day / 04:45 NPT) + manual `workflow_dispatch`.
- Slack is optional at runtime: missing `SLACK_WEBHOOK_URL` means print the alert to the job summary and exit 0.
- ASCII only in code, comments, commits, docs and Slack copy.
- File size: no source file over 300 lines. No new dependency without a one-line reason in the commit body.
- Every task ends with `pytest -q` and `ruff check .` passing, plus the task's own acceptance command.
- Repo: `git@github.com:monkeypox7/CDR-Official-Update-Monitoring-System.git` (public). The source `.docx` is not committed.

---

## 1. Product definition

### 1.1 Problem
Engineers Australia (EA), Home Affairs and the Federal Register of Legislation change CDR rules, fees, occupations and pathways without notice. Our website pages go stale. Manual weekly checking is slow and gets skipped.

### 1.2 Users
- Content / SEO team: reads Slack, updates website pages.
- Owner (Sabin): adds or removes sources, triages the tracker.

### 1.3 v1 in scope
1. Daily check of 14 official sources (section 3).
2. Noise filter: ignore cosmetic change (scripts, nav, footer, timestamps, whitespace, per-source ignore patterns).
3. Change confirmation: refetch once after 60 s; alert only if the second fetch matches the first new version.
4. Keyword tagging from doc section 2 -> category + urgency (Critical / High / Informational).
5. Slack alert in the doc's "Recommended Alert Format" (section 5).
6. GitHub Issue per Critical/High change = the "CDR Update Tracker" (label = category + priority, open = Pending, closed = Done).
7. Discovery of new official pages: EA RSS, EA news listing link diff, EA `/migrants` hub link diff, Legislation API new titles.
8. Health: a source that fails 3 runs in a row sends one "source broken" Slack alert; recovery sends one "source recovered" alert.
9. Weekly Monday digest: one Slack line with sources checked, Informational changes count, broken sources. Proof the cron is alive.

### 1.4 v1 out of scope (YAGNI)
Competitor sites, AI summaries, web dashboard, database, Google `site:` search scraping (against Google ToS and blocked from CI; replaced by discovery sources above), screenshots, email, multi-channel routing, website-page auto-editing.

### 1.5 Success criteria (v1 release gate)
- 14 of 14 sources return valid content from GitHub Actions for 7 consecutive daily runs (Session 5 soak).
- Zero false alerts in those 7 runs, or each false alert fixed with an ignore rule + regression test.
- A simulated real change (fixture edit) produces a correct Slack message and GitHub Issue end to end.
- A simulated broken source produces exactly one "source broken" alert, not one per day.

---

## 2. Architecture

### 2.1 Run flow

```
GitHub Actions cron (daily) / manual run
  -> cdrwatch.run
     -> config.load()            sources.yaml + keywords.yaml -> dataclasses, validated
     -> for each source:
          fetch.get(source)       HTTP with browser headers, 3 retries, backoff; browser mode if source.fetch == "browser"
          extract.run(source)     page -> normalized text | links -> sorted URL set | rss -> items | legislation -> titles
          validate                min_chars, required_marker present, else FetchFailure
          state.load(source.id)   previous snapshot
          diff.compare(old, new)  -> Change | None
          confirm                 refetch after 60 s, must equal new
          classify.tag(change)    keywords -> categories, urgency, actions
          state.save(...)         new snapshot + meta (last_ok, fail_count, last_hash)
     -> notify
          Critical/High -> slack.post(alert) + tracker.open_issue(alert)
          Informational -> counted for weekly digest only
          broken/recovered -> slack.post(health)
     -> write GitHub job summary (always)
  -> workflow commits state/ ("chore(state): run YYYY-MM-DD")
```

### 2.2 Why this is stable
- **No moving infrastructure.** Nothing to keep alive between runs. A failed run changes nothing; the next run retries.
- **Snapshots in git.** Full history of every source for free. `git log state/ea-fees.txt` = fee page history. Rollback = `git revert`.
- **Per-source isolation.** One source crashing never stops the others (try/except per source, recorded in meta).
- **Silent-death guards.** min_chars + required_marker catch Cloudflare challenge pages and redesigns that empty a selector. fail_count catches blocks. Weekly digest catches a dead cron.
- **Daily state commit** keeps the repo active, so GitHub does not auto-disable the schedule after 60 days of inactivity.
- **First baseline is silent.** A source with no snapshot saves one and sends no alert.
- **Pinned dependencies** in `requirements.txt`; CI runs tests on every push.

### 2.3 Known risks (verified 2026-09-14 from a local IP)

| Risk | Evidence | Mitigation |
|---|---|---|
| EA is behind Cloudflare | `Server: cloudflare`; plain `Python-urllib` UA -> 403; browser UA -> 200 with real content | Browser headers. Session 1 spike runs the fetch from GitHub Actions. If blocked there, switch EA sources to `fetch: browser` (Playwright). If still blocked, stop and ask the owner. |
| Home Affairs occupation list is JS-rendered | Raw HTML (1.29 MB) contains no ANZSCO codes | Session 1 spike: find the JSON feed via Playwright network log; else `fetch: browser` with a wait selector. |
| EA `last-modified` header changes every request | Observed | Never use headers for change detection; compare extracted text only. |
| EA has no sitemap (404) | Observed | Discovery via RSS + link diff on listing pages. |
| GitHub cron can start late (minutes to hours) | GitHub documented behaviour | Acceptable for a daily check. Optional free cron-job.org trigger later. |

### 2.4 Repository layout

```
.
|-- CLAUDE.md                     project rules for Claude sessions
|-- README.md                     operator guide (Session 5)
|-- sources.yaml                  watched sources
|-- keywords.yaml                 keyword -> category, urgency, action, affected page types
|-- requirements.txt              pinned runtime deps
|-- requirements-dev.txt          pytest, ruff
|-- pyproject.toml                ruff + pytest config, package metadata
|-- src/cdrwatch/
|   |-- __init__.py
|   |-- models.py                 Source, Snapshot, Change, Alert, SourceMeta dataclasses
|   |-- config.py                 load + validate YAML
|   |-- fetch.py                  http_get, browser_get, FetchFailure
|   |-- extract.py                page_text, link_set, rss_items, legislation_titles
|   |-- diff.py                   compare
|   |-- classify.py               tag
|   |-- state.py                  load_snapshot, save_snapshot, load_meta, save_meta
|   |-- slack.py                  build_change_blocks, build_health_blocks, build_digest_blocks, post
|   |-- tracker.py                open_issue (GitHub REST)
|   `-- run.py                    CLI entry: python -m cdrwatch.run [--dry-run] [--only ID] [--no-confirm]
|-- tests/
|   |-- fixtures/                 saved real HTML/XML/JSON per source
|   `-- test_*.py
|-- state/                        <source_id>.txt snapshots + meta.json (bot-written only)
|-- .github/workflows/
|   |-- ci.yml                    ruff + pytest on push and PR
|   `-- monitor.yml               daily cron + workflow_dispatch, commits state/
`-- .claude/                      settings, hooks, agents, skills (already set up)
```

---

## 3. Sources (v1)

All URLs returned HTTP 200 from a local IP on 2026-09-14 except where marked spike.

| id | kind | url | priority | fetch |
|---|---|---|---|---|
| ea-msa | page | https://www.engineersaustralia.org.au/migrants/migration-skills-assessment | Critical | http |
| ea-associate-changes | page | https://www.engineersaustralia.org.au/migrants/migration-skills-assessment/changes-engineering-associate-qualifications | Critical | http |
| ea-fees | page | https://www.engineersaustralia.org.au/migrants/migration-skills-assessment/assessment-fees-and-additional-services | Critical | http |
| ea-prepare-msa | page | https://www.engineersaustralia.org.au/publications/prepare-your-migration-skills-assessment-application | Critical | http |
| ea-competency-standard | page | https://www.engineersaustralia.org.au/about-engineering/national-competency-standard-engineering | Critical | http |
| ea-occupational-categories | page | https://www.engineersaustralia.org.au/about-engineering/occupational-categories | High | http |
| ea-accreditation | page | https://www.engineersaustralia.org.au/about-us/accreditation | High | http |
| ea-accredited-programs | page | https://www.engineersaustralia.org.au/publications/engineers-australia-accredited-programs | High | http |
| ea-migrants-hub | links | https://www.engineersaustralia.org.au/migrants | High | http |
| ea-news | links | https://www.engineersaustralia.org.au/news-and-media | High | http |
| ea-rss | rss | https://www.engineersaustralia.org.au/rss.xml | High | http |
| ha-skilled-occupation-list | page | https://immi.homeaffairs.gov.au/visas/working-in-australia/skill-occupation-list | Critical | spike |
| ha-skills-assessment | page | https://immi.homeaffairs.gov.au/visas/working-in-australia/skills-assessment | Critical | spike |
| leg-migration-instruments | legislation | https://api.prod.legislation.gov.au/v1/titles | High | http |

EA page content container: `<article class="node node--type-page ...">` inside `<main>` (verified in raw HTML).
Legislation API: OData. `$` must be URL-encoded as `%24`. Verified: `/v1/titles?%24filter=contains(name,'Engineers')&%24top=5&%24select=id,name` returns `@odata.count` + `value[]`. Watch query for v1: titles whose name contains `Migration` made in the last 30 days, then keyword filter.

`sources.yaml` entry shape:

```yaml
- id: ea-fees
  name: "Engineers Australia - Assessment fees and additional services"
  kind: page            # page | links | rss | legislation
  url: "https://www.engineersaustralia.org.au/migrants/migration-skills-assessment/assessment-fees-and-additional-services"
  priority: Critical    # floor urgency for any tagged change on this source
  fetch: http           # http | browser
  selector: "main article"
  required_marker: "fee"      # case-insensitive text that must exist, else FetchFailure
  min_chars: 500
  ignore_patterns: []         # regex lines dropped before diff
  link_pattern: null          # links kind only: regex of hrefs to keep
```

---

## 4. Keyword and urgency rules

`keywords.yaml` holds one entry per doc section 2 topic:

```yaml
- category: Fees
  terms: ["fee", "fast track", "\\$\\d", "AUD", "charge"]
  urgency: Critical
  action: "Update pricing figures on all pages that show EA fees."
  page_types: ["Pricing", "MSA guide"]
```

Rules (in `classify.tag`):
1. Match terms case-insensitively against added + removed lines only (not the whole page).
2. Critical categories (doc section 6 "Immediate action"): Fees, CDR evidence, Career Episode, Summary Statement, ANZSCO/Occupations, Pathways, Deadlines/Interim arrangements, Plagiarism/AI, Assessing authority, Engineering Associate.
3. High categories: CPD, English, Accreditation/RTO, Professional Engineer, Engineering Technologist, Engineering Manager, Processing times, Skilled employment, Review/Appeal, Competency standards, MSA guidance.
4. Urgency = highest matched category urgency. No match -> Informational (digest only, no Slack alert, no issue).
5. Effective date: first date found in added lines by regex (`\d{1,2} (Jan|...|Dec)[a-z]* \d{4}`, `\d{4}-\d{2}-\d{2}`). None -> "Not stated in source". Never guessed.

---

## 5. Slack alert format (maps doc "Recommended Alert Format")

```
[CRITICAL] Engineers Australia - Assessment fees and additional services
Change detected: 2 lines added, 1 removed. Tags: Fees
Previous: Fast Track fee $360
New:      Fast Track fee $395
Effective date: 1 October 2026
Who is affected: Fees applicants (tags: Fees)
Website pages to review: Pricing, MSA guide
Recommended action: Update pricing figures on all pages that show EA fees.
Official source: <url>
Tracker: <GitHub issue url>   |   Full diff: <commit url>
Verify the official page before changing site content.
```

Limits: max 15 changed lines shown per side, each line max 300 chars, full diff always via commit link.

---

## 6. Tasks

Each task = one Claude session unless noted. Full prompts in `docs/SESSION_PROMPTS.md`.

### Task 0: Repo bootstrap + Cloudflare/JS spike (Session 1)

**Files:** Create `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `src/cdrwatch/__init__.py`, `src/cdrwatch/fetch.py`, `tests/test_fetch.py`, `.github/workflows/ci.yml`, `.github/workflows/spike.yml`, `docs/SPIKE.md`.

**Interfaces - Produces:**
- `class FetchFailure(Exception)` with `.reason: str` (`"http_403"`, `"timeout"`, `"too_short"`, `"marker_missing"`, `"challenge_page"`).
- `http_get(url: str, *, timeout: int = 30, retries: int = 3) -> str` - browser UA + Accept/Accept-Language headers, backoff 2 s / 4 s / 8 s, raises `FetchFailure`.
- `looks_like_challenge(html: str) -> bool` - true when html contains `cf-chl`, `Just a moment`, or `challenge-platform` AND has no `<article`.

- [ ] Tests first: 200 returns body (mocked), 403 raises `FetchFailure("http_403")` after 3 attempts, challenge html detected, real EA html fixture NOT flagged as challenge (the verified EA page contains `challenge-platform` in a script and also `<article`).
- [ ] `spike.yml` (workflow_dispatch): runs `python -m cdrwatch.fetch --probe` over all 14 URLs from GitHub's runner, prints status, bytes, challenge flag, whether `312211` appears (Home Affairs).
- [ ] Owner pushes and runs spike. Record results in `docs/SPIKE.md`.
- [ ] For each Home Affairs source: use Playwright `page.on("response")` locally to find a JSON feed with occupation data. Record the endpoint or "browser required".
- **Acceptance:** `pytest -q` green; `docs/SPIKE.md` lists each of the 14 sources with a decided `fetch` mode. **Stop condition:** any EA source blocked in Actions with both http and browser -> stop, report, wait for owner.

### Task 1: Models, config, extraction (Session 2)

**Files:** `models.py`, `config.py`, `extract.py`, `sources.yaml`, `keywords.yaml`, `tests/fixtures/*`, `tests/test_config.py`, `tests/test_extract.py`.

**Interfaces - Produces:**
- `@dataclass(frozen=True) Source(id, name, kind, url, priority, fetch, selector, required_marker, min_chars, ignore_patterns: tuple[str, ...], link_pattern: str | None)`
- `@dataclass(frozen=True) KeywordRule(category, terms: tuple[str, ...], urgency, action, page_types: tuple[str, ...])`
- `load_sources(path) -> list[Source]`, `load_keywords(path) -> list[KeywordRule]` - raise `ValueError` naming the bad field (duplicate id, unknown kind, bad regex, missing url).
- `page_text(html, source) -> str` - select container, drop `script,style,nav,footer,header,form,noscript,[aria-hidden=true]`, one line per block element, collapse whitespace, drop `ignore_patterns` lines, validate `min_chars` / `required_marker`.
- `link_set(html, source) -> str` - absolute URLs matching `link_pattern`, sorted, deduped, newline-joined, each as `title | url`.
- `rss_items(xml) -> str` - `title | link` per item, sorted.
- `legislation_titles(json_text) -> str` - `id | name | makingDate` per title, sorted.

- [ ] Save one real fixture per source kind (curl from the owner's machine). Tests: EA fixture -> text contains the page heading, excludes nav/cookie text; same fixture with a changed timestamp line in an ignore pattern -> identical output; config errors for each invalid case.
- **Acceptance:** `python -m cdrwatch.run --dry-run --only ea-fees --no-confirm` (stub run in this task) prints extracted text length > 500.

### Task 2: Diff, classify, state (Session 3)

**Files:** `diff.py`, `classify.py`, `state.py`, tests.

**Interfaces - Produces:**
- `@dataclass Change(source_id, added: list[str], removed: list[str])`; `compare(old: str | None, new: str) -> Change | None` (None when old is None = baseline, or equal).
- `@dataclass Alert(source: Source, change: Change, categories: list[str], urgency: str, actions: list[str], page_types: list[str], effective_date: str)`; `tag(source, change, rules) -> Alert`. Urgency = max(matched rule urgency). No match -> "Informational". Source `priority` never raises an untagged change above Informational.
- `load_snapshot(dir, id) -> str | None`, `save_snapshot(dir, id, text)`; `@dataclass SourceMeta(last_ok: str | None, fail_count: int, broken_alerted: bool)`; `load_meta(dir) -> dict[str, SourceMeta]`, `save_meta(dir, meta)` (sorted keys, stable JSON so git diffs stay small).
- [ ] Tests: baseline -> None; reorder-only link list -> None; fee number change -> Change with 1 added 1 removed; tag Fees -> Critical with date extracted; untagged change -> Informational; meta round-trip.
- **Acceptance:** all tests green.

### Task 3: Slack, tracker, run orchestration (Session 4)

**Files:** `slack.py`, `tracker.py`, `run.py`, tests.

**Interfaces - Produces:**
- `build_change_blocks(alert, issue_url, diff_url) -> dict` (Slack Block Kit payload, text fallback included), `build_health_blocks(source, status: "broken" | "recovered", reason) -> dict`, `build_digest_blocks(summary) -> dict`, `post(payload, webhook_url: str | None) -> bool` (None -> write to `$GITHUB_STEP_SUMMARY` or stdout, return False; 429/5xx -> 2 retries).
- `open_issue(alert, repo: str, token: str | None) -> str | None` - title `[{urgency}] {source.name}: {categories}`; labels `priority:{urgency}`, `category:{c}`; dedupe: skip if an open issue with the same title and same added-lines hash exists.
- `main(argv) -> int` - flow from section 2.1; confirm refetch after 60 s unless `--no-confirm`; broken alert when `fail_count` hits 3 and `broken_alerted` is false; recovered alert on first success after broken; digest when the scheduled run starts on a UTC Sunday (Sunday 23:00 UTC = Monday 09:00 AEST) or `--digest`; exit 0 even when sources fail (failures are reported, not crashes); exit 1 only on config error.
- [ ] Tests with mocked fetch: end-to-end over fixtures -> baseline run sends nothing; edited fixture -> one Slack payload matching section 5; third consecutive failure -> one broken payload; fourth -> none.
- **Acceptance:** `python -m cdrwatch.run --dry-run` against live sources prints baseline for all 14 and exits 0.

### Task 4: Scheduled workflow (Session 4, same session)

**Files:** `.github/workflows/monitor.yml`.
- cron `0 23 * * *` + `workflow_dispatch` (input `digest: boolean`).
- `permissions: contents: write, issues: write`; `concurrency: cdr-watch` (no overlapping runs); `timeout-minutes: 20`.
- Python 3.12 with pip cache; Playwright install only if any source has `fetch: browser`.
- Env: `SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`.
- Commit step: `git add state/ && git diff --cached --quiet || git commit -m "chore(state): run $(date -u +%F)" && git push` with pull-rebase retry once.
- **Acceptance:** manual run on GitHub green; `state/` commit appears; job summary shows 14 sources.

### Task 5: Hardening, README, soak, v1 tag (Session 5)

- README: what it does, add/remove a source (points to `add-source` skill), connect Slack (create incoming webhook -> repo secret `SLACK_WEBHOOK_URL`), read the tracker, troubleshoot broken source.
- 7-day soak: daily check of job summary; every false alert -> ignore rule + regression test.
- Simulated change test: edit a snapshot in a branch run with `--dry-run` and confirm payload.
- **Acceptance:** section 1.5 gate met -> `git tag v1.0.0`.

---

## 7. Later (not v1)
- Slack channel wiring (owner does it: one secret, no code).
- Competitor sites as a separate `sources-competitors.yaml` if ever needed.
- cron-job.org trigger if GitHub cron lateness becomes a problem.
