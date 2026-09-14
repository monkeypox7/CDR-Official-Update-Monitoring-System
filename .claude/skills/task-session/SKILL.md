---
name: task-session
description: Start and finish ritual for every CDR Watch build session. Use at the start of any session that implements a task from docs/PLAN.md ("start session", "do task N", "S2", "continue the build") and before saying a task is done. Keeps the session inside its own worktree and owned files, forces TDD and real verification evidence, then hands off to the ship skill.
---

# Task session ritual

Sessions run inside the main VS Code workspace (several at once). Isolation comes from a per-session git worktree, not from the editor folder.

- `MAIN` = `/c/Users/Acer/Desktop/Internal Apps/CDR Official Update Monitoring System` (stays on `main`, never edited by build sessions)
- `WT` = `/c/Users/Acer/Desktop/Internal Apps/cdrwatch-wt/<s>` (your only work area)

## Start (before touching code)
1. Dependencies: `gh issue view <issue>` - every issue under "Depends on" must be CLOSED. Otherwise stop and say which.
2. Worktree: if `WT` does not exist, create it:
   `cd "$MAIN" && git fetch origin && git worktree add "../cdrwatch-wt/<s>" -b <branch> origin/main`
   If it exists: `cd "$WT" && git branch --show-current` must print `<branch>`; then `git fetch origin && git rebase origin/main`.
3. Venv: `cd "$WT" && (test -d .venv || py -3.13 -m venv .venv) && .venv/Scripts/python -m pip install -q -r requirements-dev.txt`
4. Read from `WT`: `CLAUDE.md`, `docs/PLAN.md` "Global Constraints" + section 2.4 + your task section, and `docs/SPIKE.md` (including "Notes for later sessions") and `docs/DECISIONS.md`. Precedence: `docs/DECISIONS.md` > `docs/SPIKE.md` notes > `docs/PLAN.md`.
5. `gh issue comment <issue> --body "Started in branch <branch>"`.
6. Echo back in 5 lines max: task, owned files, interfaces, acceptance command, stop conditions.

## Command rules
- Every Bash command starts with `cd "$WT" && ...`. Never run git, pytest or ruff in `MAIN`.
- Tools: `.venv/Scripts/python -m pytest -q`, `.venv/Scripts/ruff check .`, `.venv/Scripts/ruff format .`, `.venv/Scripts/python -m cdrwatch.<module>`.
- Read/Edit/Write with absolute `WT` paths (`C:\Users\Acer\Desktop\Internal Apps\cdrwatch-wt\<s>\...`). Never edit files under `MAIN`.

## Build loop (per checkbox group)
1. Failing tests first; confirm they fail for the right reason.
2. Minimal code to pass. No extra options, no future-proofing.
3. pytest + ruff green.
4. Commit: Conventional Commit, ASCII, `Refs #<issue>`, attribution line.

Subagents only for independent read-only work (for example several `source-checker` runs in one message). Give them the absolute `WT` path. Never let two agents edit the same file.

## Finish (all required, in order)
1. Run the task's acceptance command; keep real output.
2. `cdr-scope-guard` with task number and `WT` path. Fix findings until `in-scope`.
3. `ship` skill.
4. Report: PR url, evidence lines, risks, which sessions are unblocked.

Do not edit `docs/PLAN.md`, `CLAUDE.md`, `docs/SESSION_PROMPTS.md` or `.claude/` - propose changes as an issue comment. S1 alone owns `docs/SPIKE.md`.

## Stop and ask when
- A file you need is owned by another session.
- A source is blocked from GitHub Actions or a plan interface cannot work as written.
- A dependency outside the approved list seems needed.
- A test can only pass by weakening it.
