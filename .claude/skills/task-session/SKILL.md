---
name: task-session
description: Start and finish ritual for every CDR Watch build session. Use at the start of any session that implements a task from docs/PLAN.md ("start session", "do task N", "S2", "continue the build") and before saying a task is done. Keeps the session inside its task and its owned files, forces TDD and real verification evidence, then hands off to the ship skill.
---

# Task session ritual

## Start (before touching code)
1. Confirm location: `git worktree list` and `git branch --show-current`. You must be in `cdrwatch-wt/<session>` on `task/<n>-<slug>`, not in the main folder on `main`. Wrong place -> stop and print the launch commands from `docs/SESSION_PROMPTS.md`.
2. Confirm dependencies: `gh issue view <issue>` - every issue listed under "Depends on" must be CLOSED. `git fetch origin && git rebase origin/main`.
3. Read `CLAUDE.md`, then only `docs/PLAN.md` "Global Constraints", section 2.4 (ownership) and your task section. Read other sections only when your task text points to them.
4. Comment on the issue: `gh issue comment <issue> --body "Started in branch task/<n>-<slug>"`.
5. Echo back in 5 lines max: task, owned files, interfaces to produce, acceptance command, stop conditions.

## Build loop (per checkbox group)
1. Failing tests first. Run them. Confirm they fail for the right reason.
2. Minimal code to pass. No extra options, no future-proofing.
3. `pytest -q` and `ruff check .` green.
4. Commit: Conventional Commit message, ASCII, attribution line.

Use subagents only for independent read-only work (for example `source-checker` on several sources at once). Never let two agents edit the same file.

## Finish (all required, in order)
1. Run the task's acceptance command. Keep the real output.
2. Dispatch `cdr-scope-guard` with the task number. Fix findings, rerun until `in-scope`.
3. Use the `ship` skill (PR closes the issue, CI green, squash merge).
4. Report: PR url, evidence lines, open risks, which session(s) this unblocks.

Do not edit `docs/PLAN.md`, `CLAUDE.md`, `docs/SESSION_PROMPTS.md` or `.claude/` - propose changes as an issue comment.

## Stop and ask when
- A file you need to change is owned by another session.
- A source is blocked from GitHub Actions or a plan interface cannot work as written.
- A dependency outside the approved list seems needed.
- A test can only pass by weakening it.
