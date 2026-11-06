# Sales call scoring rubric

**Version:** 1 (YYYY-MM-DD)

**Total 100, four dimensions.** Evidence-based: every sub-score cites a quote or its absence.

> Lessons built in from a live system: (1) give every stage in your pipeline its own objectives,
> or demos get graded against discovery; (2) never charge the same moment twice for the same reason;
> (3) scale the play checklist to the call's length. Score the motion the call is actually in,
> not the one three stages ahead.

## A — Stage objectives (40)

Use the block for the call type. Points split evenly across that stage's objectives unless
weighted. MET = full points, PARTIAL = half, MISSED = 0.

### Discovery
- Surfaced and sized the acute pain
- Learned how they solve it today and why that fails
- Mapped who decides and how they buy
- Secured a next meeting with the right people (its date is scored in D)

### Demo
- Opened by restating their pain in their words
- Demoed to that pain, not the feature menu
- Handled the capability questions truthfully (`product-context`)
- Secured a trial or proposal meeting

### Proposal
- Walked options and let them choose
- Confirmed budget fit
- Named the path to signature (who signs, what paper, what date)

### Negotiation / Procurement
- Held price within `commercial.md` or routed the variance to an approver
- Cleared legal, security, procurement steps with owners and dates

### Qualified out
A call that surfaces budget, authority and fit and correctly parks or disqualifies the prospect
with a stated reason has met its objectives. Score A on the quality of the qualification, and
mark `[QUALIFIED OUT]`. Never grade a clean disqualification as a failed advance.

## B — Qualification depth: MEDDPICC (25)

The eight MEDDPICC signals. Score only signals advanced on THIS call and only signals in scope
for the stage. Dimension A judges whether an objective was attempted and met; B judges how
deep each signal went. A signal may count in both. Metrics is the target they would measure
success by, not the current state ("30 hours per release today" is Pain; "get it under 5" is a
Metric).

| Letter | Signal | Pts | Full | Half | Zero |
|---|---|---|---|---|---|
| M | Metrics | 3 | The outcome they'd measure, with a number ("cut onboarding from 6 weeks to 2") | Outcome named, no number | Not surfaced |
| E | Economic buyer | 4 | The person who signs is engaged, or a dated path to them; budget range known | Named, not engaged; budget vague | Unknown |
| D | Decision criteria | 3 | What they'll judge vendors on, in their words | Partial | Unknown |
| D | Decision process | 3 | Steps, people and dates from here to a decision | Partial | Unknown |
| P | Paper process | 2 | Legal, security, procurement steps, owners and lead time | Mentioned | Unknown |
| I | Identify pain | 4 | Acute pain, quantified, with the cost of doing nothing | Named, not sized | Not surfaced |
| C | Champion | 4 | Has power, wants us to win, and is coaching us | Friendly contact | None |
| C | Competition | 2 | Who else they're looking at, including doing nothing or building it | Hinted | Unknown |

| Stage | In scope | N/A |
|---|---|---|
| Discovery | I, M, E, D-process, C-champion, C-competition | D-criteria, P |
| Demo | I, M, D-criteria, C-champion, C-competition | E, D-process, P |
| Proposal | all eight | — |
| Negotiation / Procurement | E, D-process, P, C-competition | I, M, D-criteria |

`B = (earned ÷ available in scope) × 25`

Open letters are worked out across the whole deal log plus this call, not this call alone: a
letter nailed on an earlier call stays closed, and a letter surfaced on this call is closed even
if it was N/A for the score. `sales-intake` writes the open letters to the deal's `blockers`,
and the digest and pipeline analysis read them.

## C — Call mechanics (20)

| Factor | Pts |
|---|---|
| Talk-to-listen (rep ≤ 40% in discovery; no demo monologues) | 4 |
| Question quality (open, layered, follow-up "why/how") | 4 |
| Objection handling (acknowledged, explored, answered; not dodged) | 4 |
| Rapport and credibility | 4 |
| Play execution (checklist below) | 4 |

**Play checklist, scaled to call length.** Plays come from `PLAYBOOK.md` by number.

| Length | In scope |
|---|---|
| ≤ 30 min | the reframe (3), and demo to the pain (11) on demo calls only |
| 31–45 min | + mine the acute pain (6) + one qualification question (8, 9 or 10) |
| > 45 min | the full playbook |

Play 12 (the next step) is scored in D, not here, so one missing date is charged once.

Everything else is `[N/A — call length]`, never `[MISSED]`. Unknown duration: treat as ≤ 30 min
and say so. A play left blank in `PLAYBOOK.md`: `[N/A — not defined]`. Insufficient evidence on
any factor: half points, flagged. Factors in C and D score full, half or zero, like B.

## D — Advancement (15)

| Factor | Pts |
|---|---|
| Next step with who, what and **when** | 6 |
| Mutual commitment (they agreed to do something too) | 5 |
| Moved the deal materially toward its next gate, beyond booking the next meeting | 4 |

## Grades

| Score | Grade | Meaning |
|---|---|---|
| 90–100 | A | Play run cleanly, deal advanced |
| 75–89 | B | Solid, one or two fixable gaps |
| 60–74 | C | Real gaps, specific coaching |
| 40–59 | D | Key objectives missed; risk of stalling |
| < 40 | F | Call failed its purpose; escalate |

## Changing this rubric

Change it when five scored calls disagree with your judgment in the same direction. Bump the
version, note what changed and why at the top, commit.
