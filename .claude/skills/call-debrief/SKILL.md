---
name: call-debrief
description: >
  Post-call leadership debrief: the writeup leadership reads after a call. Use for "debrief this
  call", "what did we learn", or a transcript asking for a deal-level readout rather than a
  grade. Produces summary, quantified pain, what landed, buying-committee status, action items,
  real quotes, deep blockers with explicit NOT-a-blocker callouts, and one recommended move.
  Reuses sales-call-scorer for the execution score.
---

# Call debrief

**Boundary.** `sales-call-scorer` grades the rep. `sales-intake` writes the CRM. This skill tells
leadership what the call means for the deal. It does not re-score; it calls the scorer.

## Hard rules

- Read the entire transcript. Never debrief from a summary.
- Quotes are verbatim, with the speaker.
- Name what is NOT a blocker as clearly as what is. Teams waste weeks on false blockers.

## Output

```
DEBRIEF: [company] — [call type] — [date]
SUMMARY: three sentences.
PAIN (quantified): ...
WHAT LANDED: ...
ADVANCEMENT: [rating] because ...
SIZING: [deal size if known, cite source]
BUYING COMMITTEE: [role: name, status]
ACTIONS — US: [owner, item, date]  THEM: [owner, item, date]
HIGHLIGHTS: "quote" — speaker
IMPROVE: [honest, specific]
DEEP BLOCKERS: [root cause, not symptom]
NOT A BLOCKER: [thing that looks like one and isn't, and why]
EXECUTION SCORE: [from sales-call-scorer]
RECOMMENDED MOVE: one move.
```
