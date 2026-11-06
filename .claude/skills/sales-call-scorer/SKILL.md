---
name: sales-call-scorer
description: >
  Scores a sales call 0–100 against the playbook ("did we run the play?") from a transcript.
  Use for "score this call", "grade my call", "how did that call go", or a transcript dropped
  for feedback. Scores execution (stage objectives, qualification depth, mechanics, next step),
  with an evidence quote for every sub-score. Qualification is scored on MEDDPICC. Evaluates only; never writes to the CRM.
  sales-intake calls it and does the writing.
---

# Sales call scorer

**Never writes the CRM.** It returns a scorecard. Run it alone when someone only wants feedback.

## Inputs

- A transcript, or a filled `sales-intake/INTAKE-FORM.md`.
- The deal's current stage, if a deal is matched (`crm-records` maps stage → call type).

## Workflow

1. **Read the entire transcript.** Never score from a summary. Confirm it is the right call:
   attendees, date, company.
2. **Determine the call type.** From the deal stage, else from content. If the call matches an
   earlier stage than the deal is in, score against the call's actual stage and raise
   `DEAL OVER-ADVANCED`. If the call cleanly qualifies the prospect out, apply the qualified-out
   rule in `RUBRIC.md`.
3. **Apply `RUBRIC.md` and `PLAYBOOK.md`.** Four dimensions. Every sub-score cites a quote or
   records the explicit absence. Too little transcript to judge → "insufficient evidence", not a
   guess.
4. **Return the scorecard.**

## Output

```
CALL SCORE: [N]/100 - Grade [A-F]  ([call type], [date], [duration])
Deal: [name]   [DEAL OVER-ADVANCED: call was X, deal is in Y]

A. Stage objectives ...... [n]/40
   - [objective]: [MET/PARTIAL/MISSED] - "[quote]"
B. Qualification (MEDDPICC) [n]/25
   - [letter] [signal] [n] - "[quote]"   (out-of-scope letters: N/A)
   MEDDPICC open: [letters still unknown across the deal log and this call, e.g. E, C-competition]
C. Call mechanics ........ [n]/20
D. Advancement ........... [n]/15
   - Next step: "[quote or 'none secured']"

PLAYS: [RAN]/[PARTIAL]/[MISSED]/[N/A] per play in scope
STRENGTHS: top 3
GAPS: top 3 (each becomes a follow-up task)
DEEP BLOCKERS: ...
RECOMMENDED MOVE: one move
COACHING: two or three sentences, direct
SENTIMENT: on-track / at-risk / critical
```

Plain text, no emojis: the output is pasted into a CRM and Slack.
