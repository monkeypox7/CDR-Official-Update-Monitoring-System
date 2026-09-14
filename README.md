# CDR Watch

Internal operator guide. CDR Watch checks official Engineers Australia, Home Affairs
and Federal Register of Legislation sources once a day. When something meaningful
changes, it posts an alert to Slack and opens a GitHub Issue to track the follow-up.

- Runs on GitHub Actions: daily at 23:00 UTC (09:00 AEST) plus manual runs.
- No server, no database, no AI, no paid service.
- Compares extracted text only. Scripts, menus, footers, whitespace and per-source
  ignore patterns are dropped first, so cosmetic edits do not alert.
- A new version must be seen twice (refetch after 60 seconds) before it alerts.

## What it watches

15 sources, defined in `sources.yaml`.

| id | what | priority |
| --- | --- | --- |
| ea-msa | EA Migration Skills Assessment page | Critical |
| ea-associate-changes | EA changes to Engineering Associate qualifications | Critical |
| ea-fees | EA assessment fees and additional services | Critical |
| ea-prepare-msa | EA "Prepare your MSA application" publication (PDF name and date) | Critical |
| ea-competency-standard | EA National Competency Standard | Critical |
| ea-occupational-categories | EA occupational categories | High |
| ea-accreditation | EA accreditation | High |
| ea-accredited-programs | EA accredited programs publication (PDF name and date) | High |
| ea-migrants-hub | Links on the EA `/migrants` hub (new pages) | High |
| ea-news | Links on EA news and media (new articles) | High |
| ea-rss | EA RSS feed items | High |
| ha-skilled-occupation-list | Home Affairs occupation list, rows assessed by Engineers Australia | Critical |
| ha-skills-assessment | Home Affairs skills assessment page | Critical |
| leg-migration-instruments | Legislation titles containing "Migration", newest ids | High |
| leg-migration-acts | Legislation titles containing "Migration", newest years | High |

PDF contents are not read. A new PDF edition shows up as a new file name and date.

## What an alert looks like

Each changed line is tagged with categories from `keywords.yaml`. The highest
matched category sets the urgency:

- Critical or High: Slack alert + tracker issue.
- No keyword match: Informational. No alert; counted in the weekly digest.

Example (the fee figures are test data, not real EA fees):

```text
[CRITICAL] Engineers Australia - Assessment fees and additional services
Change detected: 2 lines added, 1 removed. Tags: Fees
Previous: Fast Track fee $360
New: Fast Track fee $395
Effective date: 1 October 2026
Who is affected: Applicants affected by: Fees
Website pages to review: Pricing, MSA guide
Recommended action: Update pricing figures on all pages that show EA fees.
Official source: <url>
Tracker: <issue url> | Full diff: <state commit url>
Verify the official page before changing site content.
```

- Effective date is copied from the changed lines. If the source gives none, the
  alert says "Not stated in source". It is never guessed.
- Up to 15 changed lines per side are shown. The full diff is behind the commit link.
- Other messages:
  - `[SOURCE BROKEN] <name> - failed 3 runs in a row (<reason>). <url>`
  - `[SOURCE RECOVERED] <name> - fetching normally again. <url>`
  - `CDR Watch weekly - <date>: <n> sources checked, <n> informational changes, broken: <ids or none>.`

## Connect Slack

Without a webhook the monitor still runs and prints alerts to the Actions job
summary. To send them to a channel:

1. In Slack, create an incoming webhook for the target channel
   (Slack app settings -> Incoming Webhooks -> Add New Webhook to Workspace).
2. In GitHub, open the repo -> Settings -> Secrets and variables -> Actions ->
   New repository secret. Name `SLACK_WEBHOOK_URL`, value = the webhook URL.
3. Open the Actions tab -> the monitor workflow (`monitor.yml`) -> "Run workflow" to test it.
   Or run `gh workflow run monitor.yml` in a terminal.

The webhook URL is a secret. Never paste it into code, issues, chat or commits.

## Tracker issues

The repo's GitHub Issues are the CDR Update Tracker.

- One issue per Critical or High change. Title: `[<urgency>] <source name>: <categories>`.
- Labels: `priority:<urgency>` and `category:<category>`.
- Open = pending website update. Close the issue when the website is updated.
- The same change is not opened twice while its issue is still open.
- Always check the official page before editing website content.

## Add or remove a source

Use the `add-source` skill. Do not edit `sources.yaml` by hand.

1. In VS Code, open a new Claude Code tab in this repo.
2. Ask, for example: `add source <url>` or `remove source <id>`.
3. The skill checks the URL is official and reachable, saves a real fixture,
   adds a test and commits the change for a PR.

- Only official sources: `engineersaustralia.org.au`, `homeaffairs.gov.au`,
  `legislation.gov.au`, or another `.gov.au` site the owner approves.
- A new source saves a silent baseline on its first run. Changes after that alert
  normally.
- A removed source keeps its old snapshot on the `state` branch for history.

## Broken source

A source is broken when it fails 3 runs in a row: HTTP error, timeout, a
Cloudflare challenge page, a missing required marker, or too little text.

- One `[SOURCE BROKEN]` alert is sent, not one per day.
- One `[SOURCE RECOVERED]` alert is sent on the first good run after that.
- Other sources keep running normally.

To fix: open a Claude Code tab and ask `source <id> is broken`. The `add-source`
skill runs the source checker. Selector drift gets a selector, fixture and test
update. If the site blocks GitHub Actions, it reports to the owner; browser fetch
is not supported in v1.

## False alert

An alert for a change that does not matter (a date stamp, a banner, a counter):

1. Close the tracker issue with a comment "false alert".
2. Open a Claude Code tab and ask the `add-source` skill to add an ignore pattern
   for that source, quoting the line from the alert.
3. The fix must include a regression test built from the real page, so the same
   line never alerts again.

## History

Snapshots live on the `state` branch, never on `main`. The bot commits there once
per run (`chore(state): run YYYY-MM-DD`).

- One text file per source (`<id>.txt`) plus `meta.json` (last success, fail count).
- History of one source:
  `git fetch origin state && git log -p origin/state -- '*ea-fees.txt'`
- Do not edit the `state` branch by hand. A bad snapshot is fixed by reverting
  the bot commit.

## Health check

Use the `watch-run` skill in a Claude Code tab ("check today's run") to trigger
or inspect the monitor, read the job summary and list open tracker issues.
