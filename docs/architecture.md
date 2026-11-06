# Architecture

## Two layers

| | Knowledge layer | Agent layer |
|---|---|---|
| Where | `.claude/skills/`, `docs/` | `agents/`, Claude Code sessions |
| Holds | what is true, what to do | when to do it, with which tools |
| Changes when | the business changes | the plumbing changes |
| Read by | every agent, every session | the schedule |

An agent that carries its own copy of a price or a rule will drift from the canon. Agents read
skills at run time; they never embed them.

## Two corpora

| | Company knowledge | Client evidence |
|---|---|---|
| Where | `.claude/skills/`, `docs/` | `clients/<slug>/` |
| Shape | stable canon, read whole | grows with every deal |
| When wrong | corrected in place; git keeps the old | annotated, never corrected: it is a record |
| Prices | `commercial.md` sets them | cited, never stated (except `[contracted]` lines and `custom-offer.md`) |

## The six loops

```
1 INBOUND    booking page ─▶ scheduler webhook ─▶ receiver ─▶ CRM contact (+UTMs)
                                                          └▶ CRM workflow creates deal ─▶ Slack ping
2 PREP       calendar ─▶ meeting-prep ─▶ battle plan doc
3 POSTCALL   recorder ─▶ hourly routine ─▶ sales-intake ─▶ sales-call-scorer
                                              ├▶ CRM deal (log, next step, blockers, last_call_*)
                                              │      └▶ CRM workflow posts card to Slack
                                              ├▶ CRM tasks per gap
                                              └▶ email draft in the rep's thread
4 WEEKLY     CRM ─▶ weekly-exec-update + pipeline-analysis ─▶ Friday doc
5 HYGIENE    KEEPER ─▶ checks ─▶ fixes / tasks / NEEDS / reach-back
6 OUTBOUND   enrichment lists ─▶ sequencer ─▶ clicks ─▶ CRM tasks for a call
```

**Why the CRM posts the card, not the agent.** The card has the same shape every time, it fires
for a human edit as well as an agent write, and the agent needs no Slack permission. The agent
writes five properties; the CRM renders them. Exception: `card_route: slack-connector`, where
`sales-intake` posts it.

## Who does what

| Decision | Who |
|---|---|
| Score, tier, next-step proposal | agent |
| Move a stage, send an email, merge records, change a price | person |
| Fix a dead pointer, close a finished task | KEEPER |
| Change a rule | the person who owns it, recorded with a date in `non-negotiables.md` |
