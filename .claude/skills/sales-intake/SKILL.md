---
name: sales-intake
description: >
  The single "drop it here after a call" entry point. Use when someone drops a call transcript,
  fills INTAKE-FORM.md, or says "process this call", "log and score this call", "I just got off
  a call with X", "update the deal from this transcript". Runs the post-call flow: match the
  deal, score via sales-call-scorer, write the CRM deal (log entry, next step, blockers, roles,
  the five last_call_* fields), tier the call, create tasks, draft the follow-up email. Runs
  interactively, or unattended from the postcall routine.
---

# Sales intake — post-call

Self-contained: the CRM write lives here. The only other skill it calls is `sales-call-scorer`.

**Scope.** Starts after the deal exists. Never creates a deal (one creator per object; see
`crm-records`). Never moves a stage. Never sends an email.

**Two modes.** *Interactive:* a person pastes a transcript and confirms each write.
*Unattended:* `agents/postcall/RUNBOOK.md` runs this with no one watching. Confirmations are
waived; anything that would have been a question becomes a line on the card and a CRM task for
the deal owner.

Plain text only in every output. No emojis.

## Step 0 — Is it a call to process?

At least one attendee outside your domain, and a transcript of more than a few hundred words.
Internal meetings are skipped. In unattended mode, the runbook also checks the transcript is
finished (see its stub rules).

## Step 1 — Match the deal

1. Company from the transcript and attendee email domains.
2. Search active deals in the pipeline named in `crm-records`.
3. One match → go on. Several → ask (unattended: task for a person, stop). **None → stop.** Do
   not create a deal. Say which deal is missing and who should create it.
4. Pull the deal, its contacts with buying roles, and its full description log.
5. **Dedup.** If the log already has an entry dated to this call, stop: it was processed.
   `hs_next_step` and `blockers` are replaced, not appended, so re-running an old call
   overwrites current state with stale state.

## Step 2 — Score

Call `sales-call-scorer` with the transcript and the deal's stage mapped to a call type
(`crm-records` stage table). Keep the gaps; they become tasks.

## Step 3 — Tier

| Tier | Trigger | Effect |
|---|---|---|
| `same_day` | A buying signal from `PLAYBOOK.md` (trial ask, "can my whole team see this", a pricing or contract ask) | Card names the person who acts today. Tasks due today |
| `escalate` | Grade D or F, sentiment at-risk or critical, or `DEAL OVER-ADVANCED` | Card leads with the recommended move |
| `standard` | Everything else | Recap, tasks, follow-up draft |

`same_day` beats `escalate` when both fire. The buying signal is the thing to act on.

## Step 4 — Write the deal

| From the call | Field | Rule |
|---|---|---|
| Agreed next action | `hs_next_step` | Replace. Owner and date or it is not a next step |
| What happened | `description` | **Append** a dated entry (`crm-records` format) with the `Call score:` line |
| Current obstacles | `blockers` | Replace. Lead with the scorecard's "MEDDPICC open" letters, then the obstacle in one line each (`E: CFO not met`) |
| Stakeholder roles | contact `hs_buying_role` | Set when named or confirmed |
| Stage readiness | — | Propose only, in the recap |
| The call, for the card | the five `last_call_*` fields | Write all five in the same update. `last_call_at` fires the Slack card |

If `crm-records` records `card_route: slack-connector` (a CRM plan with no workflows), post the
card yourself through the Slack connector right after the write, with the fields the workflow
would show: deal, grade, score, tier, headline, next step, blockers, owner, record link.

Interactive: show the proposed writes and confirm. Unattended: write.

## Step 5 — Tasks

One CRM task per scorecard gap not already covered by an open task. Owner is the deal owner
(unowned deal → the default owner named in `NEEDS.md`), due date set. Every task has an owner
and a date or it is not a task.

## Step 6 — Follow-up draft

A draft in the rep's email, replying in the existing thread when there is one: what was agreed,
in the client's own words from the transcript, and the next step with its date. The rep sends
it. No invented claims; capabilities only from `product-context`, prices only from
`commercial.md`.

## Step 7 — Recap

```
[company] — [call type] — [grade] [score]/100 — tier [tier]
NEXT STEP: [owner, action, date]
BLOCKERS: ...
STAGE: stays [X] | propose [Y] because ...
TASKS CREATED: ...
FOLLOW-UP: drafted in [thread]
```
