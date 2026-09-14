# CDR Watch - project rules

## Goal (the only goal)
Once a day, detect meaningful changes on official CDR / Engineers Australia / Home Affairs / Legislation sources and post a structured alert to Slack, with a GitHub Issue as the tracker. Free, no server, no AI.

Done for v1 = the release gate in `docs/PLAN.md` section 1.5. Nothing else counts as progress.

## Source of truth, in order
1. `docs/PLAN.md` - scope, architecture, interfaces, tasks. Names and signatures there are binding.
2. `docs/SESSION_PROMPTS.md` - what the current session is allowed to do.
3. `docs/SPIKE.md` (after Session 1) - verified fetch mode per source.
4. `CDR_Official_Update_Monitoring_System.docx` (local only, not in git) - business requirements.

If the code and the plan disagree, stop and ask. Do not silently pick one.

## Hard boundaries (never, without the owner's explicit yes in chat)
- No work outside the current session's task. No "while I'm here" refactors, no extra features, no speculative config options.
- No competitor sites. No LLM / AI calls or SDKs. No paid service. No Rails, database, web UI, Docker, server.
- No new dependency. Allowed runtime deps: requests, beautifulsoup4, lxml, PyYAML, playwright (only if `docs/SPIKE.md` says browser). Dev: pytest, ruff.
- No renaming of interfaces defined in `docs/PLAN.md`. A needed change -> propose a plan edit first.
- Never hand-edit `state/` (bot-written snapshots). Tests use `tests/fixtures/` and `tmp_path`.
- Never commit the `.docx`, `.env`, or any webhook URL / token. Secrets only via GitHub secrets.
- Git: never commit or push to `main`, never force push, never `gh pr merge --admin`. Work only in your session worktree + `task/<n>-<slug>` branch; deliver via the `ship` skill (PR with `Closes #<issue>`, CI `test` green, squash merge).
- Edit only files your session owns (`docs/PLAN.md` section 2.4). `CLAUDE.md`, `docs/`, `.claude/` are owner-only during build sessions.

## How to work
- Read only what the task needs. `docs/PLAN.md` section for the task + files it names.
- TDD: failing test -> minimal code -> green -> commit. One commit per plan checkbox group.
- Real fixtures only. Save real HTML/XML/JSON from the live source; never invent page markup.
- Small files: under 300 lines each (hook-enforced). One responsibility per module.
- Errors: per-source failures are caught, recorded in meta, reported. Only config errors exit non-zero.
- Determinism: sorted output, stable JSON, no timestamps inside snapshots.
- Never guess a fact the source does not state (effective date, fee, ANZSCO code). Output "Not stated in source".
- ASCII only everywhere (code, comments, commits, Slack copy).

## Commands
```
python -m venv .venv && .venv/Scripts/activate      # Windows; source .venv/bin/activate on Linux/CI
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
ruff check . && ruff format --check .
python -m cdrwatch.run --dry-run [--only SOURCE_ID] [--no-confirm] [--digest]
```

## Definition of done for any task
1. `pytest -q` green and `ruff check .` clean - paste the real output.
2. The task's acceptance command from `docs/PLAN.md` run - paste the real output.
3. `cdr-scope-guard` agent run on the diff returns `in-scope` (or each finding fixed).
4. `ship` skill completed: PR merged, CI green, task issue CLOSED. Short recap: PR url, evidence, what is unblocked.
Never report done without steps 1-4 evidence. Progress lives in GitHub issues, not in plan checkboxes.

## Helpers in this repo
- Skill `add-source` - the only way to add or change a watched source.
- Skill `task-session` - start/finish ritual for every build session.
- Skill `ship` - rebase, push, PR, watch CI, squash merge, confirm issue closed.
- Skill `watch-run` - trigger/inspect the monitor workflow and report production health.
- Agent `cdr-scope-guard` - reviews a diff against the plan task; flags scope creep, plan drift, missing tests.
- Agent `source-checker` - live-checks one source (reachability, selector, marker, noise) and reports.
- Hooks (`.claude/settings.json`) - block edits to `state/` and secrets, AI SDK imports, unapproved deps, files over 300 lines, commits/pushes to `main`, force push, non-squash or admin merges, protection/secret API changes; auto-run ruff on edited Python.
