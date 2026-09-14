# Claude session prompts - CDR Watch v1

How to use:
- One prompt = one fresh Claude Code session opened in this folder. Run `/clear` (or open a new session) between sessions so each starts with a clean context.
- Paste the prompt as-is. Do not add extra wishes to it; put new ideas in `docs/PLAN.md` section 7 first.
- Model: Sonnet 5 is enough for Sessions 2-4. Use Opus 5 for Session 1 (spike decisions) and Session 5 (soak triage).
- After each session: check the report has real pytest output, acceptance output and `cdr-scope-guard: in-scope`. Then push the branch yourself.

---

## Session 1 - Bootstrap + Cloudflare/JavaScript spike (Task 0)

```
Use the task-session skill. Task: Task 0 in docs/PLAN.md.

Goal of this session: prove, before any other code exists, that every one of the 14 sources can be fetched from GitHub Actions, and decide the fetch mode per source.

Do:
1. git init is done. Create the Task 0 files only: pyproject.toml (package cdrwatch under src/, ruff line-length 100, pytest testpaths=tests), requirements.txt (requests, beautifulsoup4, lxml, PyYAML, pinned exact versions), requirements-dev.txt (-r requirements.txt, pytest, ruff, pinned), .gitignore (.venv, __pycache__, .env, *.docx, *.code-workspace, .pytest_cache, .ruff_cache), src/cdrwatch/__init__.py, src/cdrwatch/fetch.py, tests/test_fetch.py, .github/workflows/ci.yml, .github/workflows/spike.yml, docs/SPIKE.md.
2. TDD fetch.py exactly per the Task 0 Interfaces block. Save the real EA page as tests/fixtures/ea-msa.html for the challenge-detection test. No network in tests (mock requests).
3. Add `python -m cdrwatch.fetch --probe` that reads a hard-coded list of the 14 URLs from docs/PLAN.md section 3 and prints: id, status, bytes, challenge flag, and for ha-* sources whether "312211" is in the body. (sources.yaml does not exist yet; this list is replaced in Task 1.)
4. For the two ha-* sources, locally use Playwright network capture (install playwright only in a throwaway venv in the scratchpad, not in requirements) to find a JSON/data URL that carries the occupation data. Record endpoint or "browser required".
5. Tell me when to push and to run the "spike" workflow manually. Wait for me to paste the job log. Then write docs/SPIKE.md: table of 14 sources x (local result, Actions result, decided fetch mode, notes).

Stop and ask me if: any EA source is blocked in Actions; a Home Affairs source has neither a data URL nor a working browser fetch.
Do not: build extract/diff/slack, add sources.yaml, add any dependency beyond the list above.
Finish with the task-session Finish steps.
```

---

## Session 2 - Models, config, extraction (Task 1)

```
Use the task-session skill. Task: Task 1 in docs/PLAN.md. Read docs/SPIKE.md for fetch modes.

Goal: every source in sources.yaml turns a real captured response into clean, stable, noise-free text.

Do:
1. Write sources.yaml with the 14 sources from docs/PLAN.md section 3, fetch modes from docs/SPIKE.md. Use the source-checker agent on each source to confirm selector, required_marker, min_chars and propose ignore_patterns. Ask it to save fixtures to tests/fixtures/. Run checks for different sources in parallel where possible.
2. Write keywords.yaml covering every topic in docs/PLAN.md section 4 (Critical and High lists) with terms, urgency, action, page_types. Actions must be plain instructions ("Update pricing figures..."), never invented facts.
3. TDD models.py, config.py, extract.py per the Task 1 Interfaces block. Tests use fixtures only.
4. Add a minimal run.py stub supporting only `--dry-run --only ID --no-confirm` that fetches and prints extracted length. Task 3 replaces it.
5. If playwright is required by docs/SPIKE.md, add it to requirements.txt and implement browser_get in fetch.py with a wait selector; test it with a mock.

Acceptance: `python -m cdrwatch.run --dry-run --only ea-fees --no-confirm` prints length > 500, and every source prints a length above its min_chars.
Do not: diff, classify, state, slack, tracker, workflow.
```

---

## Session 3 - Diff, classify, state (Task 2)

```
Use the task-session skill. Task: Task 2 in docs/PLAN.md.

Goal: given old and new extracted text, produce the exact change and a correctly tagged Alert, and persist snapshots deterministically.

Do:
1. TDD diff.py, classify.py, state.py exactly per the Task 2 Interfaces block and docs/PLAN.md section 4 rules.
2. Required tests (all listed in Task 2) plus: a keyword only in unchanged text does not tag; date regex returns "Not stated in source" when absent; multiple categories -> highest urgency wins; save_meta output is byte-identical across two runs with same data.
3. Use tests/fixtures copies edited in tmp_path to simulate real changes (for example change one fee figure in the ea-fees fixture).

Acceptance: pytest green; a test named test_fee_change_end_to_end_tags_critical passes using the real ea-fees fixture.
Do not: slack, tracker, run orchestration, workflow.
```

---

## Session 4 - Slack, tracker, run, scheduled workflow (Tasks 3 and 4)

```
Use the task-session skill. Tasks: Task 3 then Task 4 in docs/PLAN.md.

Goal: a daily GitHub Actions run that fetches all sources, confirms changes, posts the section 5 Slack alert (or prints it when no webhook is set), opens a deduplicated GitHub Issue for Critical/High, sends broken/recovered/digest messages, and commits state/.

Do:
1. TDD slack.py, tracker.py, run.py exactly per the Task 3 Interfaces block. Slack copy must match docs/PLAN.md section 5 line by line, ASCII only. Tests mock HTTP; no real Slack or GitHub calls.
2. run.py: per-source try/except, FetchFailure increments fail_count, broken alert exactly once at 3, recovered once, baseline silent, confirm refetch after 60 s unless --no-confirm, digest on --digest or scheduled Sunday-UTC run. Exit 0 on source failures, 1 on config error.
3. Write .github/workflows/monitor.yml per Task 4. No SLACK_WEBHOOK_URL secret yet -> alerts go to the job summary.
4. Run `python -m cdrwatch.run --dry-run` against live sources locally. Paste summary.
5. Tell me to push and trigger monitor.yml manually. Wait for my pasted log. Confirm baseline commit of state/ happened and no alert was sent.

Acceptance: local dry-run exits 0 with 14 baselines; first Actions run green with a state/ commit; second manual run reports 0 changes.
Do not: README, new sources, Slack channel setup, any extra notification channel.
```

---

## Session 5 - Hardening, README, soak, v1 (Task 5)

```
Use the task-session skill. Task: Task 5 in docs/PLAN.md.

Goal: pass the v1 release gate in docs/PLAN.md section 1.5 and hand over an operator-ready repo.

Do:
1. Write README.md for a non-developer operator: what it watches, how alerts look, how to connect Slack (create an incoming webhook in Slack -> add repo secret SLACK_WEBHOOK_URL -> run workflow manually), how to read and close tracker issues, how to add/remove a source (add-source skill), what to do when a source is broken. Internal repo doc, plain English, no marketing.
2. Simulated change: on a throwaway branch, feed an edited ea-fees fixture through run.py with --dry-run and paste the rendered Slack message. Check each field against section 5.
3. Simulated breakage: mock 4 consecutive failures; show exactly one broken alert.
4. Soak: I will paste 7 daily job summaries across this session or follow-up sessions. For each false alert: add an ignore_pattern + regression test via the add-source skill. No other changes.
5. When the gate is met: tick all boxes, commit, and tell me the exact tag command (git tag v1.0.0). I push.

Do not: new features, refactors not required by a soak finding, dependency changes.
```

---

## Ad-hoc prompts (after v1)

Add a source:
```
Use the add-source skill. Add: <URL>. Topic: <doc section 2 topic>.
```

Source broken alert received:
```
Use the add-source skill, "Broken source" section, for source id <id>. Job log: <paste>.
```

False alert received:
```
Source <id> sent a false alert. Slack text: <paste>. Use source-checker to find the noisy lines, add an ignore_pattern and a regression test via the add-source skill. No other changes.
```
