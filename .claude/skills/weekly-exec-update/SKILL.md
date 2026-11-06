---
name: weekly-exec-update
description: >
  The weekly executive sales update: a cross-deal digest of every active deal with status,
  latest call score, next step and the real blocker named by its MEDDPICC letter. Use for "weekly exec update", "Friday update",
  "brief leadership on the pipeline". For one deal, use call-debrief.
---

# Weekly exec update

## Workflow

1. Pull every deal in the active stages of the pipeline (`crm-records`).
2. From each description log, read the newest entries since last Friday and the latest
   `Call score:` line.
3. Check the calendar and inbox for the week. The CRM lags: a meeting the client booked from
   their side, or a reply in Gmail, never reaches the record on its own.
4. Name each deal's real blocker by its MEDDPICC letter (`sales-call-scorer/RUBRIC.md` §B):
   the deal's `blockers` field and the latest scorecard's "MEDDPICC open" line say which
   letters are still unknown for its stage.
5. Classify each deal: ADVANCED / HELD / SLIPPED / NEW / CLOSED.
6. Roll up.

## Output

```
Status: [N] active deals, [n] advanced, [n] slipped, [n] new. Weighted pipeline [figure from CRM].

MOVED THIS WEEK
- [Deal]: [stage change], [why, one line]

NEEDS A DECISION
- [Deal]: [decision], [who decides], [by when]

AT RISK
- [Deal]: [MEDDPICC letter] [blocker], [move]

ALL DEALS
| Deal | Stage | Last call | Score | Next step | Blocker (MEDDPICC) |
```

## Hard rules

- Open with plain status facts. No narrative arc, no triumphal framing.
- Every figure comes from the CRM or the log. Nothing estimated.
