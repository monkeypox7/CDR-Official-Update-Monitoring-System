# Claude session prompts - CDR Watch v1

## Rules that prevent collisions

- 1 session = 1 issue = 1 branch = 1 worktree folder = 1 PR. Never run two sessions in the same folder.
- A session edits only the files it owns (`docs/PLAN.md` section 2.4). Hooks + `cdr-scope-guard` enforce it.
- `main` is protected: every change lands by squash-merged PR with CI `test` green. Sessions merge their own PR (`ship` skill).
- Start a wave only when every issue of the previous wave is CLOSED.
- Owner-only files (`CLAUDE.md`, `docs/`, `.claude/`) change between waves, from the main folder, via a PR.

```
Wave 1:  S1 (#1)                         ~1 session, Opus
Wave 2:  S2 (#2)  S3 (#3)  S4 (#4)       3 terminals at the same time, Sonnet
Wave 3:  S5 (#5)                         Sonnet (Opus if live runs misbehave)
Wave 4:  S6 (#6)                         Sonnet
Soak:    7 days of ad-hoc watch-run prompts, then tag v1.0.0
```

## One-time prerequisites (owner)

1. `gh auth refresh -h github.com -s workflow` (lets `gh` merge PRs that contain workflow files).
2. Python 3.12+ on PATH.

## How to launch any session (PowerShell)

Replace `<s>` and `<branch>` from the table.

```powershell
cd "C:\Users\Acer\Desktop\Internal Apps\CDR Official Update Monitoring System"
git pull
git worktree add "..\cdrwatch-wt\<s>" -b <branch> origin/main
cd "..\cdrwatch-wt\<s>"
claude --model <model> --permission-mode acceptEdits
```

| session | issue | branch | model |
|---|---|---|---|
| s1 | #1 | task/0-bootstrap | opus |
| s2 | #2 | task/1-config-extract | sonnet |
| s3 | #3 | task/2-diff-classify-state | sonnet |
| s4 | #4 | task/3-slack-tracker | sonnet |
| s5 | #5 | task/4-run-monitor | sonnet |
| s6 | #6 | task/5-readme-rc | sonnet |

After a session reports "merged, issue closed", clean up from the main folder:

```powershell
cd "C:\Users\Acer\Desktop\Internal Apps\CDR Official Update Monitoring System"
git worktree remove "..\cdrwatch-wt\<s>"
git pull
```

---

## S1 - Task 0 (issue #1)

```
Session S1. Issue #1. Use the task-session skill, then do Task 0 in docs/PLAN.md exactly.

Setup first: python -m venv .venv, activate it, pip install -r requirements-dev.txt once you have created the requirements files.

Priorities, in order:
1. models.py is binding for S2-S6, who run in parallel after you. Copy the Task 0 interface block exactly; no extra fields.
2. Capture raw fixtures for all 14 sources (python -m cdrwatch.probe --save-fixtures). S2-S4 rely on them.
3. Home Affairs data URL hunt: Playwright in a throwaway venv inside the session scratchpad only. Never add it to requirements in S1.
4. Open the PR early (after tests pass) so spike.yml runs on GitHub runners; read it with gh run view --log; then write docs/SPIKE.md and push again.

Ship with the ship skill once CI is green and SPIKE.md decides a fetch mode for all 14 sources.
Stop and comment on #1 if an EA source is blocked in Actions, or a Home Affairs source has no data URL and no working browser fetch.
```

---

## S2 - Task 1 (issue #2) - wave 2, parallel with S3 and S4

```
Session S2. Issue #2. Use the task-session skill, then do Task 1 in docs/PLAN.md exactly. Read docs/SPIKE.md.

Setup: python -m venv .venv, activate, pip install -r requirements-dev.txt.

Notes:
- S3 and S4 are working in parallel. You own only the Task 1 files listed in PLAN.md 2.4. models.py is frozen: if it truly blocks you, comment on #2 and stop.
- Dispatch source-checker agents in parallel (one message, several agents) to verify selectors/markers/ignore_patterns for the 14 sources. They are read-only; you write sources.yaml.
- keywords.yaml: every category from PLAN.md section 4. Actions are instructions, never facts.
- Add playwright + browser_get only if SPIKE.md marks a source "browser".

Acceptance: python -m cdrwatch.probe prints OK for all 14 live sources. Then ship.
```

---

## S3 - Task 2 (issue #3) - wave 2, parallel with S2 and S4

```
Session S3. Issue #3. Use the task-session skill, then do Task 2 in docs/PLAN.md exactly.

Setup: python -m venv .venv, activate, pip install -r requirements-dev.txt.

Notes:
- S2 and S4 are working in parallel. You own only diff.py, classify.py, state.py and their tests. Do not create sources.yaml, keywords.yaml, config.py or extract.py.
- KeywordRule lists in tests are built inline. Test text lines are copied from the real tests/fixtures/raw/ea-fees.html wording.
- No network in tests. Deterministic output only.

Acceptance: pytest -q tests/test_diff.py tests/test_classify.py tests/test_state.py green. Then ship.
```

---

## S4 - Task 3 (issue #4) - wave 2, parallel with S2 and S3

```
Session S4. Issue #4. Use the task-session skill, then do Task 3 in docs/PLAN.md exactly.

Setup: python -m venv .venv, activate, pip install -r requirements-dev.txt.

Notes:
- S2 and S3 are working in parallel. You own only slack.py, tracker.py and their tests. Build Alert/Source/RunSummary objects directly in tests from models.py.
- Slack text must match PLAN.md section 5 line by line, ASCII only. Mock every HTTP call; never call real Slack or GitHub.
- GitHub REST via requests with the token header; no gh CLI inside library code.

Acceptance: pytest -q tests/test_slack.py tests/test_tracker.py green. Then ship.
```

---

## S5 - Task 4 (issue #5)

```
Session S5. Issue #5. Use the task-session skill, then do Task 4 in docs/PLAN.md exactly. Confirm #2, #3, #4 are CLOSED first.

Setup: python -m venv .venv, activate, pip install -r requirements-dev.txt.

Order:
1. TDD run.py + tests/test_integration.py (mocked fetch, tmp_path state, real fixtures).
2. Local live check: python -m cdrwatch.run --dry-run. Every source must be OK.
3. monitor.yml per Task 4, delete spike.yml. Ship (PR, CI, squash merge).
4. After merge, use the watch-run skill: gh workflow run monitor.yml, watch it, confirm the state branch has 14 snapshots and no alerts. Run it a second time: 0 changes, 0 failures.
5. Paste both run summaries as a comment on #5, then confirm #5 is CLOSED.

If a live run fails after merge, fix it in a new branch task/4-fix-<slug> from the same worktree (git switch -c ... origin/main) and ship again.
```

---

## S6 - Task 5 (issue #6)

```
Session S6. Issue #6. Use the task-session skill, then do Task 5 in docs/PLAN.md exactly. Confirm #5 is CLOSED first.

Setup: python -m venv .venv, activate, pip install -r requirements-dev.txt.

Notes:
- README is an internal operator doc: plain English, short sections, real commands, no marketing.
- Put the rendered simulated Slack alert in the PR body.
- After merge: git fetch origin, git tag v1.0.0-rc1 origin/main, git push origin v1.0.0-rc1. Then use watch-run to report current health on #6.
```

---

## Soak and operations (run from the main folder, `claude --model sonnet`)

Daily soak check (7 days):
```
Use the watch-run skill. Report today's soak status. If a false alert or failing source appears, open an issue with label false-alert or source-broken and stop.
```

Fix a false alert or broken source (new worktree, branch fix/<id>-<slug>):
```
Issue #<n>. Use the task-session skill (task = this issue) and the add-source skill to fix source <id>: find the noisy or broken lines with source-checker, add an ignore_pattern or selector fix plus a regression test. No other changes. Ship.
```

Add a source (new worktree, branch feat/source-<id>):
```
Use the add-source skill. Add: <URL>. Topic: <doc section 2 topic>. Open an issue for it first, then ship.
```

Release v1.0.0 (after 7 clean days):
```
Use the watch-run skill to confirm 7 consecutive green runs with no open false-alert or source-broken issues. If true: git fetch origin, git tag v1.0.0 origin/main, git push origin v1.0.0, and report.
```
