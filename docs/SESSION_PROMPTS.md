# Claude session prompts - CDR Watch v1 (VS Code)

## How sessions are run

- All sessions are Claude Code tabs in the **same VS Code workspace** (this folder). No terminal needed.
- Isolation is automatic: each session creates and works in its own git worktree `..\cdrwatch-wt\<s>` on its own branch. The main folder stays on `main` and is never edited by a build session.
- 1 session = 1 issue = 1 branch = 1 worktree = 1 PR. Each session edits only files it owns (`docs/PLAN.md` 2.4).
- A session merges its own PR (`ship` skill) and removes its own worktree. You only paste prompts and answer questions.
- Start a wave only when every issue of the previous wave is CLOSED.

```
Wave 1:  S1 (#1)                         Opus
Wave 2:  S2 (#2)  S3 (#3)  S4 (#4)       3 tabs at the same time, Sonnet
Wave 3:  S5 (#5)                         Sonnet
Wave 4:  S6 (#6)                         Sonnet
Soak:    7 daily watch-run checks, then tag v1.0.0
```

## To start a session in VS Code

1. Open a new Claude Code tab (Command Palette -> "Claude Code: Open in New Tab").
2. Pick the model in the tab (`/model sonnet` or `/model opus`).
3. Paste the prompt. Nothing else.

One-time: the `gh` login needs the `workflow` permission. In the VS Code terminal run `gh auth refresh -h github.com -s workflow` and approve in the browser.

---

## S1 - Task 0 (issue #1) - running

Already started. When S1 finishes it must leave, in `docs/SPIKE.md` under "Notes for later sessions", every owner-approved deviation from `docs/PLAN.md` (for example the challenge rule that also checks `<main`, and the working Legislation API query), and copy the same list into the PR body.

---

## S2 - Task 1 (issue #2) - wave 2, parallel with S3 and S4

```
Session S2. Issue #2. Branch task/1-config-extract. Worktree ../cdrwatch-wt/s2.
Use the task-session skill, then do Task 1 in docs/PLAN.md exactly.

- Read docs/SPIKE.md fully first: fetch modes, selector hints, the working Legislation query and "Notes for later sessions" override PLAN.md where they differ.
- S3 and S4 run in parallel. Own only the Task 1 files. models.py is frozen; if it blocks you, comment on #2 and stop.
- Verify the 14 sources with source-checker agents launched together in one message (absolute worktree path in each brief). They report; you write sources.yaml.
- keywords.yaml covers every category in PLAN.md section 4. Actions are instructions, never facts.
- Add playwright + browser_get only if SPIKE.md marks a source "browser".

Acceptance: .venv/Scripts/python -m cdrwatch.probe prints OK for all 14 live sources. Then ship.
```

---

## S3 - Task 2 (issue #3) - wave 2, parallel with S2 and S4

```
Session S3. Issue #3. Branch task/2-diff-classify-state. Worktree ../cdrwatch-wt/s3.
Use the task-session skill, then do Task 2 in docs/PLAN.md exactly.

- Read docs/SPIKE.md "Notes for later sessions" first.
- S2 and S4 run in parallel. Own only diff.py, classify.py, state.py and their tests. Do not create sources.yaml, keywords.yaml, config.py or extract.py.
- KeywordRule lists in tests are built inline. Test lines copy real wording from tests/fixtures/raw/ea-fees.html.
- No network in tests. Deterministic output.

Acceptance: .venv/Scripts/python -m pytest -q tests/test_diff.py tests/test_classify.py tests/test_state.py green. Then ship.
```

---

## S4 - Task 3 (issue #4) - wave 2, parallel with S2 and S3

```
Session S4. Issue #4. Branch task/3-slack-tracker. Worktree ../cdrwatch-wt/s4.
Use the task-session skill, then do Task 3 in docs/PLAN.md exactly.

- Read docs/SPIKE.md "Notes for later sessions" first.
- S2 and S3 run in parallel. Own only slack.py, tracker.py and their tests. Build Alert/Source/RunSummary objects in tests from models.py.
- Slack text matches PLAN.md section 5 line by line, ASCII only. Mock all HTTP; never call real Slack or GitHub.
- GitHub REST via requests with a token header; no gh CLI inside library code.

Acceptance: .venv/Scripts/python -m pytest -q tests/test_slack.py tests/test_tracker.py green. Then ship.
```

---

## S5 - Task 4 (issue #5)

```
Session S5. Issue #5. Branch task/4-run-monitor. Worktree ../cdrwatch-wt/s5.
Use the task-session skill, then do Task 4 in docs/PLAN.md exactly. #2, #3 and #4 must be CLOSED.

- Read docs/SPIKE.md and the "Notes for later sessions" sections of PRs #2-#4 (gh pr list --state merged, gh pr view <n>).
Order:
1. TDD run.py + tests/test_integration.py (mocked fetch, tmp_path state, real fixtures).
2. Live local check: .venv/Scripts/python -m cdrwatch.run --dry-run. Every source OK.
3. monitor.yml per Task 4; delete spike.yml. Ship.
4. After merge, watch-run skill: gh workflow run monitor.yml, watch it, confirm the state branch has 14 snapshots and no alerts. Run a second time: 0 changes, 0 failures.
5. Comment both run summaries on #5; confirm #5 is CLOSED.

A live-run failure after merge: new worktree ../cdrwatch-wt/s5fix on branch task/4-fix-<slug> from origin/main, fix, ship.
```

---

## S6 - Task 5 (issue #6)

```
Session S6. Issue #6. Branch task/5-readme-rc. Worktree ../cdrwatch-wt/s6.
Use the task-session skill, then do Task 5 in docs/PLAN.md exactly. #5 must be CLOSED.

- README is an internal operator doc: plain English, short sections, real commands, VS Code friendly (Claude Code tab prompts, not terminal-only steps).
- Put the rendered simulated Slack alert in the PR body.
- After merge, from the main folder: git fetch origin, git tag v1.0.0-rc1 origin/main, git push origin v1.0.0-rc1. Then use watch-run and comment the health report on #6.
```

---

## Operations (new Claude Code tab each time)

Daily soak check (7 days):
```
Use the watch-run skill. Report today's soak status. If a false alert or failing source appears, open an issue with label false-alert or source-broken and stop.
```

Fix a false alert or broken source:
```
Issue #<n>. Worktree ../cdrwatch-wt/fix-<n>, branch fix/<n>-<slug>. Use the task-session skill (task = this issue) and the add-source skill to fix source <id>: find the noisy or broken lines with source-checker, add an ignore_pattern or selector fix plus a regression test. No other changes. Ship.
```

Add a source:
```
Open an issue for adding <URL> (topic: <doc section 2 topic>). Worktree ../cdrwatch-wt/src-<n>, branch feat/source-<id>. Use the task-session skill and the add-source skill. Ship.
```

Release v1.0.0 (after 7 clean days):
```
Use the watch-run skill to confirm 7 consecutive green runs and no open false-alert or source-broken issues. If true: in the main folder run git fetch origin, git tag v1.0.0 origin/main, git push origin v1.0.0, and report.
```
