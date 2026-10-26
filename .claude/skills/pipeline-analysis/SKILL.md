---
name: pipeline-analysis
description: >
  Deal-by-deal pipeline health: every open deal scored with its deep blocker, an explicit
  NOT-a-blocker callout, and one named strategic move. Use for "pipeline analysis", "which deals
  are at risk", "what needs attention this week". Deal intelligence (what to DO), not a status
  digest (that is weekly-exec-update).
---

# Pipeline analysis

## Read first

`company-context`, `crm-records` (stage ladder), `sales-playbook`.

## For each open deal

1. Pull the deal, contacts and roles, description log, open tasks.
2. Check the calendar and inbox for the last 14 days. A meeting the client booked from their
   side never reaches the CRM.
3. Score health 1–5 on: momentum (days since last real exchange), qualification depth, champion
   strength, next step dated, stage honesty (is the stage earned?).
4. Name the deep blocker (root cause), what is NOT a blocker, and one move.

A deal whose record is known to be wrong gets fixed or a fix proposed now, not noted.

## Output

```
PIPELINE — [date] — [N] open deals

[Deal] — [stage] — health [n]/5 — [days since last touch]d
  Blocker: ...
  Not a blocker: ...
  Move: [owner] [action] by [date]
```

Sort by (value × risk). Lead with the three deals where one move changes the outcome.
