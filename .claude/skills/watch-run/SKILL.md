---
name: watch-run
description: Monitor CDR Watch in production - trigger or inspect the daily monitor workflow, read its job summary, check the state branch and open tracker issues, and report health. Use for "check today's run", "is the monitor working", "run the monitor now", "soak check", "why no alert", "source broken".
---

# Watch the monitor

Read-only unless the owner asks to trigger a run. Never edit `state/`.

## Trigger (only if asked, or Session 5/6 acceptance)
```
gh workflow run monitor.yml                 # add: -f digest=true for a digest
gh run list --workflow monitor.yml -L 1 --json databaseId -q ".[0].databaseId"
gh run watch <id> --exit-status
```

## Inspect latest runs
```
gh run list --workflow monitor.yml -L 7 --json databaseId,conclusion,createdAt,event
gh run view <id> --log | grep -E "OK |CHANGE|FAIL|BROKEN|RECOVERED|summary" | head -60
git fetch origin state && git log origin/state --oneline -7
gh issue list --label "priority:Critical" --state open
gh issue list --label "priority:High" --state open
```

## Report (exactly this shape)
```
runs (last 7): <date conclusion> ...
sources ok: <n>/14   failing: <ids or none>
changes: critical <n>, high <n>, informational <n>
open tracker issues: <n> (<urls>)
soak day: <n>/7   false alerts: <n>
verdict: healthy | attention: <one line>
```

## Diagnose
- Run missing for a day -> check `gh run list` event times (cron can be late) and that the workflow is enabled: `gh workflow list`.
- Source failing -> use the add-source skill "Broken source" section.
- Alert looks wrong -> the false-alert ad-hoc prompt in `docs/SESSION_PROMPTS.md`.
