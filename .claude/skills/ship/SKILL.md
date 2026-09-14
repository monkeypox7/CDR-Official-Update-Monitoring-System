---
name: ship
description: Deliver a finished CDR Watch task - rebase on main, push the task branch, open a PR that closes the task issue, watch CI, fix failures, squash-merge, confirm the issue closed. Use when a task-session reaches its Finish step, or on "ship it", "open PR", "merge", "raise PR".
---

# Ship a task

Preconditions: you are in the task worktree on branch `task/<n>-<slug>`, `cdr-scope-guard` verdict is `in-scope`, all work committed.

## 1. Sync
```
git fetch origin
git rebase origin/main
pytest -q && ruff check . && ruff format --check .
```
Rebase conflict -> only in files your task owns (PLAN.md 2.4)? resolve, rerun tests. Conflict in a file you do not own -> `git rebase --abort`, comment on the issue, stop and ask the owner.

## 2. Push and open PR
```
git push -u origin HEAD
gh pr create --base main --title "<type>(<scope>): <task title>" --body-file <scratchpad>/pr.md
```
`pr.md` (plain ASCII):
```
Closes #<issue>

## What
- <files and one-line purpose each>

## Evidence
- pytest: <last line>
- ruff: <last line>
- acceptance: <command> -> <key output lines>
- cdr-scope-guard: in-scope

## Risks / follow-ups
- <or "none">

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## 3. Watch CI
```
gh pr checks --watch --fail-fast
```
Failure -> `gh run view <run-id> --log-failed`, fix in the branch, commit, `git push`, watch again. After 3 failed fix attempts stop and comment the failing log excerpt on the issue.

## 4. Merge
```
gh pr merge --squash
```
Never `--admin`. Do not use `--delete-branch` from a worktree (the repo auto-deletes the remote branch).
Merge refused with "workflow scope" -> tell the owner to run `gh auth refresh -h github.com -s workflow`, then retry.

## 5. Confirm
```
gh issue view <issue> --json state -q .state     # expect CLOSED
```
Not closed -> `gh issue close <issue> --comment "Done in #<pr>"`.

## 6. Report to owner
PR url, merged commit, issue closed, and the cleanup commands for the owner to run from the main folder:
```
git worktree remove "../cdrwatch-wt/<session>"
git pull
```
