---
name: task-session
description: Start and finish ritual for every CDR Watch build session. Use at the start of any session that implements a task from docs/PLAN.md ("start session", "do task N", "continue the build") and before saying a task is done. Keeps the session inside its task, forces TDD and real verification evidence.
---

# Task session ritual

## Start (before touching code)
1. Read `CLAUDE.md`, then only `docs/PLAN.md` "Global Constraints" + the task section named in the prompt. Do not read other tasks.
2. Run `git status` and `git log --oneline -5`. Confirm the previous task's checkboxes are ticked. If not, stop and report.
3. Echo back in 5 lines max: task, files allowed, interfaces to produce, acceptance command, stop conditions.
4. Anything in the task unclear or contradicting code -> ask the owner now, before coding.

## Build loop (per checkbox group)
1. Write failing tests. Run them. Confirm they fail for the right reason.
2. Minimal code to pass. No extra options, no future-proofing.
3. `pytest -q` and `ruff check .` green.
4. Commit with a Conventional Commit message (`feat:`, `test:`, `fix:`, `chore:`).

## Finish (all required, in order)
1. Run the task's acceptance command. Paste real output.
2. Dispatch `cdr-scope-guard` with the task number. Fix every finding, rerun until `in-scope`.
3. Tick the task's checkboxes in `docs/PLAN.md`; commit `docs(plan): complete task N`.
4. Report: what changed (files), evidence (pytest line, acceptance output, guard verdict), open risks, next session number. Do not push - tell the owner the branch is ready to push.

## Stop and ask when
- A source is blocked from GitHub Actions or the plan's interface cannot work as written.
- A dependency outside the approved list seems needed.
- A test can only pass by weakening it.
