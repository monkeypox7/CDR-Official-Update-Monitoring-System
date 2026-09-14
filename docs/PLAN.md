# CDR Watch v1 - Product and Implementation Plan

> **For agentic workers:** One Claude session = one task = one GitHub issue = one branch = one worktree = one squash-merged PR. Prompts live in `docs/SESSION_PROMPTS.md`. Use the `task-session` skill to work and the `ship` skill to deliver. Checkboxes below are guidance only - progress is tracked by closing the GitHub issue, never by editing this file during a build session.

**Goal:** Detect meaningful changes on official CDR / Engineers Australia / Home Affairs / Legislation sources once a day and post a structured alert to Slack, with a GitHub Issue as the change tracker.

**Architecture:** One small Python package run by a scheduled GitHub Actions workflow. Each run fetches every source in `sources.yaml`, extracts the meaningful text (or link list / feed items / legislation titles), compares it with the last snapshot stored on the `state` branch, tags changes with keywords from `keywords.yaml`, posts material changes to a Slack incoming webhook, opens a GitHub Issue per material change, then commits the new snapshots to the `state` branch. No server, no database, no AI, no paid service.

**Tech Stack:** Python 3.12, requests, beautifulsoup4 + lxml, PyYAML, pytest, ruff. Playwright (Chromium) only for sources proven to need JavaScript. GitHub Actions (free, public repo). Slack incoming webhook (free).

## Global Constraints

- Scope: official sources only. Competitor sites are out of scope for v1.
- Zero cost: no paid API, no hosted server, no LLM.
- No Rails, no database. Snapshots live in `state/` on the orphan branch `state`, never on `main`.
- Alerts: deterministic diff + keyword tags. Never infer requirements the source does not state (doc "Publishing rule").
- Schedule: daily at 23:00 UTC (09:00 AEST next day) + manual `workflow_dispatch`.
- Slack is optional at runtime: missing `SLACK_WEBHOOK_URL` means print the alert to the job summary and exit 0.
- ASCII only in code, comments, commits, docs and Slack copy.
- File size: no source file over 300 lines. No new dependency beyond the approved list in `CLAUDE.md`.
- Git: `main` is protected (required check `test`, no direct push, no force push). All work lands via squash-merged PR whose body contains `Closes #<issue>`.
- Every PR: `pytest -q` and `ruff check .` green locally and in CI, plus the task's acceptance output pasted in the PR body.
- Repo: `git@github.com:monkeypox7/CDR-Official-Update-Monitoring-System.git` (public). The source `.docx` is never committed.

---

## 1. Product definition

### 1.1 Problem
Engineers Australia (EA), Home Affairs and the Federal Register of Legislation change CDR rules, fees, occupations and pathways without notice. Website pages go stale. Manual weekly checking is slow and gets skipped.

### 1.2 Users
- Content / SEO team: reads Slack, updates website pages.
- Owner (Sabin): adds or removes sources, triages the tracker.

### 1.3 v1 in scope
1. Daily check of 14 official sources (section 3).
2. Noise filter: ignore cosmetic change (scripts, nav, footer, timestamps, whitespace, per-source ignore patterns).
3. Change confirmation: refetch once after 60 s; alert only if the second fetch matches the first new version.
4. Keyword tagging from doc section 2 -> category + urgency (Critical / High / Informational).
5. Slack alert in the doc's "Recommended Alert Format" (section 5).
6. GitHub Issue per Critical/High change = the "CDR Update Tracker" (labels = category + priority, open = Pending, closed = Done).
7. Discovery of new official pages: EA RSS, EA news listing link diff, EA `/migrants` hub link diff, Legislation API new titles.
8. Health: a source that fails 3 runs in a row sends one "source broken" Slack alert; recovery sends one "source recovered" alert.
9. Weekly digest (Monday AEST): sources checked, Informational change count, broken sources. Proof the cron is alive.

### 1.4 v1 out of scope (YAGNI)
Competitor sites, AI summaries, web dashboard, database, Google `site:` search scraping (against Google ToS and blocked from CI; replaced by discovery sources above), screenshots, email, multi-channel routing, website-page auto-editing.

### 1.5 Success criteria (v1 release gate)
- 14 of 14 sources return valid content from GitHub Actions for 7 consecutive daily runs (soak).
- Zero false alerts in those 7 runs, or each false alert fixed with an ignore rule + regression test.
- A simulated real change (fixture edit) produces a correct Slack message and GitHub Issue payload end to end.
- A simulated broken source produces exactly one "source broken" alert, not one per day.
- `v1.0.0-rc1` tagged after Session 6; `v1.0.0` tagged after the soak passes.

---

## 2. Architecture

### 2.1 Run flow

```
GitHub Actions cron (daily) / manual run
  checkout main (code) + checkout branch "state" into ./state
  -> python -m cdrwatch.run
     -> config.load_sources / load_keywords      validated dataclasses
     -> for each source (isolated try/except):
          fetch.http_get | fetch.browser_get     browser headers, 3 retries, backoff
          extract.<kind>(...)                     normalized text, validated (min_chars, marker, challenge)
          state.load_snapshot(id)                 previous text or None
          diff.compare(id, old, new)              Change | None  (None = baseline or equal)
          confirm                                  refetch after 60 s, must equal new
          classify.tag(source, change, rules)     Alert with categories, urgency, date
          state.save_snapshot / meta              last_ok, fail_count, broken_alerted
     -> Critical/High: tracker.open_issue + slack.post(build_change_blocks)
        Informational: counted for digest only
        broken/recovered: slack.post(build_health_blocks)
        Sunday UTC scheduled run or --digest: slack.post(build_digest_blocks)
     -> job summary (always)
  commit ./state to branch "state"  ("chore(state): run YYYY-MM-DD")
  keepalive: gh api -X PUT .../actions/workflows/monitor.yml/enable
```

### 2.2 Why this is stable
- **No moving infrastructure.** Nothing to keep alive between runs. A failed run changes nothing; the next run retries.
- **Snapshots on a separate branch.** Full history per source (`git log state -- state/ea-fees.txt`), rollback by revert, and bot commits never collide with feature PRs on `main`.
- **Per-source isolation.** One source crashing never stops the others.
- **Silent-death guards.** min_chars + required_marker + challenge detection catch Cloudflare pages and redesigns. fail_count catches blocks. Weekly digest catches a dead cron.
- **Keepalive.** The workflow re-enables itself via the Actions API each run, so the 60-day inactivity auto-disable never triggers.
- **First baseline is silent.** A source with no snapshot saves one and sends no alert.
- **Pinned dependencies**, CI on every PR, protected `main`.

### 2.3 Known risks (verified 2026-09-14 from a local IP)

| Risk | Evidence | Mitigation |
|---|---|---|
| EA is behind Cloudflare | `Server: cloudflare`; `Python-urllib` UA -> 403; browser UA -> 200 with real content | Browser headers. Session 1 spike runs the fetch from GitHub Actions. Blocked there -> `fetch: browser`. Still blocked -> stop and ask the owner. |
| Home Affairs occupation list is JS-rendered | Raw HTML (1.29 MB) contains no ANZSCO codes | Session 1: find the JSON feed via Playwright network log; else `fetch: browser` with a wait selector. |
| EA `last-modified` header changes every request | Observed | Never use headers for change detection; compare extracted text only. |
| EA has no sitemap (404) | Observed | Discovery via RSS + link diff on listing pages. |
| GitHub cron can start late | GitHub documented behaviour | Acceptable for a daily check. |
| `gh` token lacks `workflow` scope | `gh auth status` 2026-09-14 | Owner runs `gh auth refresh -h github.com -s workflow` once. |

### 2.4 Repository layout and file ownership

The owner column prevents collisions between parallel sessions. A session edits only files it owns. Anything else -> comment on its issue and stop.

```
path                               owner session
CLAUDE.md, docs/PLAN.md            owner only (between waves)
docs/SESSION_PROMPTS.md            owner only
.claude/                           owner only
pyproject.toml, requirements*.txt  S1   (S2 may add playwright only)
.gitignore                         S1
src/cdrwatch/__init__.py           S1
src/cdrwatch/models.py             S1   (all dataclasses, frozen after S1)
src/cdrwatch/fetch.py              S1   (S2 may add browser_get only)
src/cdrwatch/probe.py              S1 -> S2
src/cdrwatch/config.py             S2
src/cdrwatch/extract.py            S2
sources.yaml, keywords.yaml        S2
src/cdrwatch/diff.py               S3
src/cdrwatch/classify.py           S3
src/cdrwatch/state.py              S3
src/cdrwatch/slack.py              S4
src/cdrwatch/tracker.py            S4
src/cdrwatch/run.py                S5
.github/workflows/ci.yml           S1
.github/workflows/spike.yml        S1   (deleted by S5)
.github/workflows/monitor.yml      S5
docs/SPIKE.md                      S1
README.md                          S6
tests/fixtures/raw/<id>.<ext>      S1 (captured), S2 may refresh
tests/test_<module>.py             owner of <module>
tests/test_integration.py          S5
state/ on branch "state"           bot only
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

EA page content container: `<article class="node node--type-page ...">` inside `<main>`. The EA page contains the string `challenge-platform` in a normal script, so challenge detection must also check for missing `<article`.
Legislation API: OData; `$` must be URL-encoded as `%24`. Verified: `/v1/titles?%24filter=contains(name,'Engineers')&%24top=5&%24select=id,name` returns `@odata.count` + `value[]`. v1 query: titles whose name contains `Migration`, ordered by `makingDate desc`, top 50; the snapshot is the id/name/date list.

`sources.yaml` entry shape:

```yaml
- id: ea-fees
  name: "Engineers Australia - Assessment fees and additional services"
  kind: page            # page | links | rss | legislation
  url: "https://www.engineersaustralia.org.au/migrants/migration-skills-assessment/assessment-fees-and-additional-services"
  priority: Critical    # Critical | High (shown in alert; never raises an untagged change)
  fetch: http           # http | browser
  selector: "main article"
  required_marker: "fee"      # case-insensitive text that must exist, else FetchFailure
  min_chars: 500
  ignore_patterns: []         # regex; matching lines dropped before diff
  link_pattern: null          # links kind only: regex of hrefs to keep
```

---

## 4. Keyword and urgency rules

`keywords.yaml`, one entry per doc section 2 topic:

```yaml
- category: Fees
  terms: ["fee", "fast track", "\\$\\d", "AUD"]
  urgency: Critical
  action: "Update pricing figures on all pages that show EA fees."
  page_types: ["Pricing", "MSA guide"]
```

Rules (in `classify.tag`):
1. Terms are regexes, case-insensitive, matched against added + removed lines only.
2. Critical categories (doc section 6 "Immediate action"): Fees, CDR evidence, Career Episode, Summary Statement, ANZSCO/Occupations, Pathways, Deadlines/Interim arrangements, Plagiarism/AI rules, Assessing authority, Engineering Associate.
3. High categories: CPD, English, Accreditation/RTO, Professional Engineer, Engineering Technologist, Engineering Manager, Processing times, Skilled employment, Review/Appeal, Competency standards, MSA guidance.
4. Urgency = highest matched urgency. No match -> "Informational" (digest only).
5. Effective date: first date in added lines matching `\b\d{1,2} (January|February|March|April|May|June|July|August|September|October|November|December) \d{4}\b` or `\b\d{4}-\d{2}-\d{2}\b`. None -> "Not stated in source". Never guessed.

---

## 5. Slack alert format (maps doc "Recommended Alert Format")

```
[CRITICAL] Engineers Australia - Assessment fees and additional services
Change detected: 2 lines added, 1 removed. Tags: Fees
Previous: Fast Track fee $360
New: Fast Track fee $395
Effective date: 1 October 2026
Who is affected: Applicants affected by: Fees
Website pages to review: Pricing, MSA guide
Recommended action: Update pricing figures on all pages that show EA fees.
Official source: <url>
Tracker: <issue url> | Full diff: <state commit url>
Verify the official page before changing site content.
```
(The fee figures above are illustrative test data, not real EA fees.)

Limits: max 15 changed lines per side, each line max 300 chars, full diff via commit link. Health: `[SOURCE BROKEN] <name> - failed 3 runs in a row (<reason>). <url>` and `[SOURCE RECOVERED] <name> - fetching normally again. <url>`. Digest: `CDR Watch weekly - <date>: <n> sources checked, <n> informational changes, broken: <ids or none>.`

---

## 6. Tasks (execution waves)

```
Wave 1:  S1 Task 0  bootstrap + models + fetch + spike + raw fixtures
Wave 2:  S2 Task 1  config + extract + sources/keywords      (parallel)
         S3 Task 2  diff + classify + state                   (parallel)
         S4 Task 3  slack + tracker                           (parallel)
Wave 3:  S5 Task 4  run orchestration + monitor workflow + first live runs
Wave 4:  S6 Task 5  README + simulations + rc tag; soak via ad-hoc prompts
```
A wave starts only when every issue of the previous wave is closed.

### Task 0 (S1): Bootstrap, models, fetch, spike

**Files:** `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore` (append only), `src/cdrwatch/__init__.py`, `src/cdrwatch/models.py`, `src/cdrwatch/fetch.py`, `src/cdrwatch/probe.py`, `tests/test_fetch.py`, `tests/test_models.py`, `tests/fixtures/raw/*`, `.github/workflows/ci.yml`, `.github/workflows/spike.yml`, `docs/SPIKE.md`.

**Interfaces - Produces (binding for all later sessions):**

```python
# models.py - all frozen dataclasses unless noted
Kind = Literal["page", "links", "rss", "legislation"]
Urgency = Literal["Critical", "High", "Informational"]
URGENCY_RANK: dict[str, int] = {"Informational": 0, "High": 1, "Critical": 2}

@dataclass(frozen=True)
class Source:
    id: str; name: str; kind: Kind; url: str; priority: Urgency; fetch: Literal["http", "browser"]
    selector: str | None = None; required_marker: str | None = None; min_chars: int = 200
    ignore_patterns: tuple[str, ...] = (); link_pattern: str | None = None

@dataclass(frozen=True)
class KeywordRule:
    category: str; terms: tuple[str, ...]; urgency: Urgency; action: str; page_types: tuple[str, ...]

@dataclass(frozen=True)
class Change:
    source_id: str; added: tuple[str, ...]; removed: tuple[str, ...]

@dataclass(frozen=True)
class Alert:
    source: Source; change: Change; categories: tuple[str, ...]; urgency: Urgency
    actions: tuple[str, ...]; page_types: tuple[str, ...]; effective_date: str

@dataclass
class SourceMeta:
    last_ok: str | None = None; fail_count: int = 0; broken_alerted: bool = False

@dataclass(frozen=True)
class RunSummary:
    date: str; checked: int; informational: int; broken: tuple[str, ...]
```

```python
# fetch.py
class FetchFailure(Exception):
    def __init__(self, reason: str): ...   # .reason in {"http_<code>", "timeout", "network", "too_short", "marker_missing", "challenge_page"}
BROWSER_HEADERS: dict[str, str]           # Chrome UA, Accept, Accept-Language en-AU
def http_get(url: str, *, timeout: int = 30, retries: int = 3) -> str   # backoff 2/4/8 s, raises FetchFailure
def looks_like_challenge(html: str) -> bool   # ("cf-chl" or "Just a moment" or "challenge-platform") and "<article" not in html
```

`probe.py`: `python -m cdrwatch.probe [--save-fixtures]` over a hard-coded list of the 14 sources (id, url) -> prints `id status bytes challenge=<bool> anzsco312211=<bool>`; `--save-fixtures` writes `tests/fixtures/raw/<id>.<html|xml|json>`. Never raises; prints `ERROR <reason>` per failed source. Exit 0.

`ci.yml`: on `pull_request` and `push` to main; one job with id and name `test`: Python 3.12, pip cache, install requirements-dev, `ruff check .`, `ruff format --check .`, `pytest -q`.
`spike.yml`: on `pull_request` (paths: `src/cdrwatch/probe.py`, `.github/workflows/spike.yml`) and `workflow_dispatch`; installs requirements, runs `python -m cdrwatch.probe`.

- [ ] Tests first: models construct and are frozen; URGENCY_RANK order; 200 returns body (mock); 403 raises `FetchFailure("http_403")` after 3 attempts with sleep mocked; timeout -> "timeout"; `looks_like_challenge` true on a Cloudflare challenge string, false on the real `tests/fixtures/raw/ea-msa.html`.
- [ ] Capture raw fixtures for all 14 sources with `--save-fixtures` (local IP).
- [ ] Home Affairs: in a throwaway scratchpad venv with Playwright, record network responses on both ha-* pages; find a JSON/data URL containing `312211`. Record URL or "browser required".
- [ ] Open PR; spike workflow runs on the PR from GitHub's runners; read its log with `gh run view --log`.
- [ ] `docs/SPIKE.md`: table of 14 sources x (local result, Actions result, decided fetch mode, selector hint, notes).
- **Acceptance:** CI `test` green; spike job log shows a result for all 14; SPIKE.md decides a fetch mode for every source.
- **Stop:** any EA source blocked in Actions, or a Home Affairs source with neither a data URL nor a working browser fetch -> comment on the issue, ask the owner.

### Task 1 (S2): Config, extraction, sources, keywords

**Files:** `src/cdrwatch/config.py`, `src/cdrwatch/extract.py`, `src/cdrwatch/probe.py` (switch to sources.yaml + extraction), `sources.yaml`, `keywords.yaml`, `tests/test_config.py`, `tests/test_extract.py`, `tests/fixtures/raw/*` (refresh only). If SPIKE.md requires browser: add `playwright` to `requirements.txt` and `browser_get` to `fetch.py`.

**Interfaces - Consumes:** `Source`, `KeywordRule`, `FetchFailure`, `looks_like_challenge`, `http_get`.
**Produces:**
```python
def load_sources(path: str | Path) -> list[Source]     # ValueError naming id + field: duplicate id, unknown kind/fetch/priority, bad regex, missing url
def load_keywords(path: str | Path) -> list[KeywordRule]  # ValueError: bad regex, unknown urgency, empty terms
def extract(raw: str, source: Source) -> str            # dispatch by kind; validates; raises FetchFailure
def page_text(html: str, source: Source) -> str         # container via selector; drop script,style,nav,footer,header,form,noscript,[aria-hidden=true]; one line per block; collapse spaces; drop ignore_patterns lines
def link_set(html: str, source: Source) -> str          # "text | absolute_url" lines matching link_pattern, deduped, sorted
def rss_items(xml: str, source: Source) -> str          # "title | link" lines, sorted
def legislation_titles(json_text: str, source: Source) -> str  # "id | name | makingDate[:10]" lines, sorted
def browser_get(url: str, *, wait_selector: str | None = None, timeout: int = 60) -> str  # only if SPIKE.md requires
```
Validation order in `extract`: challenge page -> `FetchFailure("challenge_page")`; missing marker -> "marker_missing"; length < min_chars -> "too_short".

- [ ] `source-checker` agent per source (parallel) confirms selector, marker, min_chars, ignore_patterns.
- [ ] Tests: each raw fixture extracts >= min_chars and contains its marker; EA page text excludes nav/cookie text; applying an ignore pattern removes the matching line; link_set is order-independent; each invalid config case raises ValueError naming the field; keywords.yaml loads with every category from section 4.
- **Acceptance:** `python -m cdrwatch.probe` prints `OK <id> <chars>` for all 14 against live sources.

### Task 2 (S3): Diff, classify, state

**Files:** `src/cdrwatch/diff.py`, `src/cdrwatch/classify.py`, `src/cdrwatch/state.py`, `tests/test_diff.py`, `tests/test_classify.py`, `tests/test_state.py`.

**Interfaces - Consumes:** `Source`, `KeywordRule`, `Change`, `Alert`, `SourceMeta`, `URGENCY_RANK`.
**Produces:**
```python
def compare(source_id: str, old: str | None, new: str) -> Change | None   # None if old is None or line sets equal; added/removed keep new/old order
def find_effective_date(lines: Iterable[str]) -> str                      # section 4 rule 5
def tag(source: Source, change: Change, rules: list[KeywordRule]) -> Alert
def load_snapshot(state_dir: Path, source_id: str) -> str | None         # state_dir/<id>.txt, utf-8
def save_snapshot(state_dir: Path, source_id: str, text: str) -> None     # trailing newline, LF
def load_meta(state_dir: Path) -> dict[str, SourceMeta]                   # state_dir/meta.json; missing -> {}
def save_meta(state_dir: Path, meta: dict[str, SourceMeta]) -> None       # indent=2, sort_keys, trailing newline
```
- [ ] Tests: baseline -> None; reordered identical lines -> None; one line changed -> 1 added 1 removed; keyword only in unchanged lines -> Informational; Fees term in added line -> Critical with actions/page_types; two categories -> highest urgency and both categories sorted; date found / "Not stated in source"; snapshot and meta round-trip; save_meta byte-identical across two calls. Test data: lines copied from `tests/fixtures/raw/ea-fees.html` text, not invented wording.
- **Acceptance:** `pytest -q tests/test_diff.py tests/test_classify.py tests/test_state.py` green.

### Task 3 (S4): Slack and tracker

**Files:** `src/cdrwatch/slack.py`, `src/cdrwatch/tracker.py`, `tests/test_slack.py`, `tests/test_tracker.py`.

**Interfaces - Consumes:** `Alert`, `Source`, `RunSummary`.
**Produces:**
```python
def build_change_blocks(alert: Alert, issue_url: str | None, diff_url: str | None) -> dict   # {"text": fallback, "blocks": [...]}, copy per section 5
def build_health_blocks(source: Source, status: Literal["broken", "recovered"], reason: str) -> dict
def build_digest_blocks(summary: RunSummary) -> dict
def post(payload: dict, webhook_url: str | None) -> bool   # None -> append text to $GITHUB_STEP_SUMMARY or stdout, return False; 429/5xx -> 2 retries; True on 200
def issue_title(alert: Alert) -> str                       # "[<urgency>] <source.name>: <categories joined ', '>"
def open_issue(alert: Alert, repo: str, token: str | None, diff_url: str | None) -> str | None
    # None token -> None. Ensures labels "priority:<urgency>" and "category:<c>" exist (POST /labels, 422 ok).
    # Dedupe: open issue with same title whose body contains "change-hash: <sha256 of added+removed>[:12]" -> return its url.
```
- [ ] Tests with mocked `requests`: payload text matches section 5 exactly for a sample Alert; line/length limits applied; no webhook -> summary file written; 429 then 200 -> True; issue dedupe returns existing url; label 422 tolerated; body contains change-hash and the "Verify the official page" line; all output ASCII.
- **Acceptance:** `pytest -q tests/test_slack.py tests/test_tracker.py` green.

### Task 4 (S5): Run orchestration, monitor workflow, first live runs

**Files:** `src/cdrwatch/run.py`, `tests/test_integration.py`, `.github/workflows/monitor.yml`; delete `.github/workflows/spike.yml`.

**Interfaces - Consumes:** everything above.
**Produces:** `main(argv: list[str] | None = None) -> int`; CLI `python -m cdrwatch.run [--dry-run] [--only ID] [--no-confirm] [--digest] [--state-dir state] [--sources sources.yaml] [--keywords keywords.yaml]`.
Behaviour: section 2.1. `--dry-run` = no Slack, no issues, no snapshot writes, print alerts. Broken alert when fail_count reaches 3 and not broken_alerted; recovered on first success after broken_alerted. Unknown snapshot files ignored. Exit 1 only on config ValueError.

`monitor.yml`: cron `0 23 * * *` + `workflow_dispatch` (input `digest` boolean); `permissions: contents: write, issues: write, actions: write`; `concurrency: {group: cdr-watch, cancel-in-progress: false}`; `timeout-minutes: 20`; checkout main; checkout `state` branch into `./state` (create orphan branch on first run if missing); Python 3.12 + pip cache; Playwright install only if `sources.yaml` has `fetch: browser`; run with env `SLACK_WEBHOOK_URL`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_SERVER_URL`; commit `./state` to `state` if changed (one pull-rebase retry); keepalive `gh api -X PUT repos/${{ github.repository }}/actions/workflows/monitor.yml/enable`.

- [ ] Integration tests (mocked fetch, tmp state): baseline run -> no posts, 14 snapshots; edited ea-fees fixture -> one change payload + one issue call; 3 failures -> one broken payload, 4th -> none; recovery -> one recovered payload; config error -> exit 1.
- [ ] Local `python -m cdrwatch.run --dry-run` against live sources.
- [ ] After merge: `gh workflow run monitor.yml`, `gh run watch`; confirm `state` branch has 14 snapshots and no alert; run again -> 0 changes.
- **Acceptance:** both live runs green; second run summary shows 0 changes, 0 failures.

### Task 5 (S6): README, simulations, release candidate

**Files:** `README.md`, `tests/test_integration.py` (append simulation tests only).
- [ ] README (internal operator doc, plain English): what is watched, alert example, connect Slack (incoming webhook -> repo secret `SLACK_WEBHOOK_URL` -> `gh workflow run monitor.yml`), tracker issues, add/remove a source (add-source skill), broken source, false alert, where history lives (`state` branch).
- [ ] Simulation tests: rendered Slack text for an edited ea-fees fixture pasted into the PR body; 4 consecutive failures -> exactly one broken alert.
- [ ] After merge: `git tag v1.0.0-rc1` on main and push the tag.
- **Acceptance:** CI green; rc tag exists on origin.
- Soak (7 days) uses the ad-hoc prompts; `v1.0.0` after the gate in 1.5.

---

## 7. Later (not v1)
- Slack channel wiring (owner: one secret, no code).
- Competitor sites as a separate `sources-competitors.yaml` if ever needed.
- External cron trigger if GitHub cron lateness becomes a problem.
