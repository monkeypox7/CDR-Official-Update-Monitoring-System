---
name: ship
description: Deliver a finished CDR Watch task - rebase on main, push the task branch, open or update the PR that closes the task issue, watch CI, fix failures, squash-merge, confirm the issue closed, remove the worktree. Use when a task-session reaches its Finish step, or on "ship it", "open PR", "merge", "raise PR".
---

# Ship a task

Preconditions: work committed in `WT` (`/c/Users/Acer/Desktop/Internal Apps/cdrwatch-wt/<s>`) on `<branch>`; `cdr-scope-guard` verdict `in-scope`. Every command below runs as `cd "$WT" && ...`.

## 1. Sync
```
git fetch origin && git rebase origin/main
.venv/Scripts/python -m pytest -q && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
```
Conflict only in files you own -> resolve, rerun tests. Conflict in a file you do not own -> `git rebase --abort`, comment on the issue, stop.

## 2. Push and PR
```
git push -u origin <branch>
gh pr list --head <branch> --json number -q ".[0].number"     # existing PR?
```
- No PR: `gh pr create --base main --head <branch> --title "<type>(<scope>): <task title>" --body-file <scratchpad>/pr.md`
- Draft PR: update body `gh pr edit <n> --body-file <scratchpad>/pr.md`, then `gh pr ready <n>`.

`pr.md` (ASCII):
```
Closes #<issue>

## What
- <file: purpose>

## Evidence
- pytest: <last line>
- ruff: <last line>
- acceptance: <command> -> <key lines>
- cdr-scope-guard: in-scope

## Notes for later sessions
- <deviations from PLAN approved by owner, or "none">

## Risks
- <or "none">

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## 3. Watch CI
```
gh pr checks <n> --watch --fail-fast
```
Failure -> `gh run view <run-id> --log-failed`, fix, commit, `git push`, watch again. 3 failed attempts -> comment the log excerpt on the issue and stop.

## 4. Merge
```
gh pr merge <n> --squash
```
Never `--admin`, never `--delete-branch` (repo auto-deletes the remote branch).
- "branch is not up to date" -> repeat steps 1-3 (another session merged first).
- "workflow scope" error -> tell the owner: run `gh auth refresh -h github.com -s workflow` in the VS Code terminal, then retry.

## 5. Confirm and clean up
```
gh issue view <issue> --json state -q .state        # expect CLOSED; else gh issue close <issue> --comment "Done in #<n>"
cd "/c/Users/Acer/Desktop/Internal Apps/CDR Official Update Monitoring System" && git worktree remove "../cdrwatch-wt/<s>" && git worktree prune
```
If `worktree remove` refuses (locked files from VS Code or venv), leave it and tell the owner; it is harmless.

## 6. Report
PR url, merge commit (`gh pr view <n> --json mergeCommit -q .mergeCommit.oid`), issue CLOSED, sessions now unblocked.
