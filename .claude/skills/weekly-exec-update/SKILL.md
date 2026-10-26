---
name: weekly-exec-update
description: >
  The weekly executive sales update: a cross-deal digest of every active deal with status,
  latest call score, next step and blockers. Use for "weekly exec update", "Friday update",
  "brief leadership on the pipeline". For one deal, use call-debrief.
---

# Weekly exec update

## Workflow

1. Pull every deal in the active stages of the pipeline (`crm-records`).
2. From each description log, read the newest entries since last Friday and the latest
   `Call score:` line.
3. Classify each deal: ADVANCED / HELD / SLIPPED / NEW / CLOSED.
4. Roll up.

## Output

```
Status: [N] active deals, [n] advanced, [n] slipped, [n] new. Weighted pipeline [figure from CRM].

MOVED THIS WEEK
- [Deal]: [stage change], [why, one line]

NEEDS A DECISION
- [Deal]: [decision], [who decides], [by when]

AT RISK
- [Deal]: [blocker], [move]

ALL DEALS
| Deal | Stage | Last call | Score | Next step | Blocker |
```

## Hard rules

- Open with plain status facts. No narrative arc, no triumphal framing.
- Every figure comes from the CRM or the log. Nothing estimated.
