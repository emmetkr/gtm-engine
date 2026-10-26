---
name: crm-records
description: >
  How CRM records are created and kept: contact, company, deal, associations, required fields,
  the deal stage ladder with real IDs, and the custom properties the post-call loop writes. Use
  for creating or updating a contact, qualifying a lead, creating a deal, or looking up a stage
  ID. The one home for pipeline and stage IDs.
---

# CRM records

Written for HubSpot; the shape holds for any CRM. Replace every `<ID>` with your portal's
values and verify them against the live portal before the first unattended run.

## One creator per object

| Object | Created by | Never created by |
|---|---|---|
| Contact | booking receiver, inbound form, enrichment | the post-call loop |
| Deal | CRM workflow when a meeting is booked | any agent reading email or transcripts |
| Task | `sales-intake`, people | — |

Two creators for one object is how duplicate deals happen.

## Pipeline

**Deals pipeline `<PIPELINE_ID>`** is the only pipeline the post-call loop touches.

## Stage ladder

| Stage | ID | Probability | Enters when | Scorer call type |
|---|---|---|---|---|
| Lead | `<ID>` | 0.05 | Created, not yet qualified | Discovery |
| Qualified | `<ID>` | 0.10 | Qualified and first meeting booked | Discovery |
| Demo | `<ID>` | 0.20 | First meeting held | Demo |
| Trial | `<ID>` | 0.40 | Trial access granted | Proposal prep |
| Proposal Sent | `<ID>` | 0.60 | Proposal delivered | Proposal |
| Verbal | `<ID>` | 0.80 | Option chosen, paperwork pending | Negotiation |
| Closed Won | `<ID>` | 1.0 | Signed | — |
| Stalled | `<ID>` | 0 | No motion, not dead | infer from the call |
| Closed Lost | `<ID>` | 0 | Dead, with a reason | — |

Stages are moved by a person. Agents propose.

## Required fields

**Contact:** first name, last name, email, company, job title, lead source, buying role.
**Company:** name, domain, industry, size.
**Deal:** name (`<Company> — <offer>`), pipeline, stage, owner, amount if known, close date.
Associations: deal ↔ company ↔ contacts, all three.

## Properties the post-call loop writes

| Property | Type | Rule |
|---|---|---|
| `description` | text | **Append** a dated activity-log entry per call. Never replace. This is the record |
| `hs_next_step` | text | Replace. Must carry owner and date |
| `blockers` | text | Replace. Point in time |
| `last_call_at` | date | Writing it fires the Slack card workflow |
| `last_call_score` | number | 0–100 |
| `last_call_grade` | enum | A–F |
| `last_call_tier` | enum | same_day / standard / escalate |
| `last_call_headline` | text | `[call type] ([duration]) with [attendees] - [next step, owner, date]` |

The five `last_call_*` fields restate the log entry so a workflow can render them. The log
wins if they disagree.

## Activity-log entry format

```
M/D CALL NOTE: [call type] ([duration]) with [attendees].
Call score: [N]/100 ([grade]).
- What happened, in three to five bullets
- Decisions and signals, with short quotes
NEXT: [owner] [action] by [date]
```
