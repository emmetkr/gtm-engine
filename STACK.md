# Stack recommendations

What we ran, why, what to use instead, and the gotchas that cost us time. The architecture does
not depend on any one vendor: every tool below sits behind a skill or a runbook, so swapping
one means editing one file.

**The rule for picking a tool:** it needs a Claude connector (MCP) or a clean API. If an agent
cannot read and write it, it is a manual step, and manual steps are where the system leaks.

## The stack, layer by layer

| Layer | Recommended | Why | Alternatives |
|---|---|---|---|
| **Agent runtime** | **Claude Code** | Skills, hooks, subagents and scheduled cloud **Routines** in one tool. The repo is the agent's brain | Claude Agent SDK if you are productizing this |
| **The bus / versioning** | **GitHub** | Agents share work through branches; Actions run the checks and the watchdog | GitLab |
| **CRM** | **HubSpot** | Official Claude connector; custom properties; workflows can post to Slack when a property changes, which is how the post-call card works | Attio (lighter, API-first), Salesforce (enterprise) |
| **Call recording + transcripts** | **Tactiq** | Claude connector returns full transcript text, so the post-call routine reads it directly. Needs a Team plan or above for full text | Fathom, Granola, Gong (enterprise; API rather than connector) |
| **Enrichment + list building** | **Clay** | MCP connector and public API; company by domain, person by name, custom enrichment functions | Apollo |
| **Outbound sequencing** | **lemlist** | Email and LinkedIn steps in one sequence; API covers leads, campaigns and activity | Smartlead, Instantly (email volume) |
| **Scheduling** | **Calendly** | Webhook carries UTMs and form answers, so every booking can be attributed in the CRM | Cal.com, HubSpot Meetings |
| **Webhook receivers** | **Vercel** functions | Tiny, free tier, deploys from `ops/receivers/` | Cloudflare Workers, Netlify |
| **Team signal** | **Slack** | One sales channel; the CRM posts the cards, agents do not | Teams |
| **Email** | **Gmail** connector | Agents write drafts in the rep's thread; a person sends | Outlook connector |
| **Docs** | **Google Drive** connector | Proposals, prep docs and order forms land where the team already works | Notion |
| **Web + booking analytics** | **PostHog** | Booking conversions, page views, funnels, all queryable by an agent | GA4 |
| **Billing (self-serve)** | **Stripe** | Promo codes and trials without engineering | — |

## Minimum viable stack

You can run the core loop with four things: **Claude Code + GitHub + a CRM with a connector +
a call recorder with a connector.** Add Slack for the card and Gmail for drafts next. Everything
else (enrichment, sequencing, receivers, analytics) is the outbound and attribution layer, and
can come later.

| Stage of company | Stack |
|---|---|
| Solo founder, first 20 calls | Claude Code, GitHub, HubSpot free, Tactiq, Gmail |
| Founder + 1–3 sellers | + Slack card, Calendly receiver, Clay, a weekly digest routine |
| Running outbound | + lemlist or Smartlead, PostHog, the keeper routine and its watchdog |

## Gotchas we paid for

**Claude Code Routines**
- Create scheduled Routines in the console UI, where repositories and connectors are real
  fields. A Routine created from inside a session can land with no repo and no connectors, fire
  on schedule into an empty container, and look healthy for days.
- Cron day-of-week filters run in UTC. "Weekdays 9–5 Pacific" written naively skips Friday
  evening and fires Sunday. Hourly with no day filter is simpler; let the runbook decide what
  to skip.
- A heartbeat only the next run reads is circular: when the agent is down there is no next
  run. Put the watchdog somewhere else (`.github/workflows/heartbeat-watch.yml`).

**Call recorders**
- Transcripts render asynchronously. A meeting can list as finished with a seven-minute stub
  of a forty-minute call. Wait 30 minutes after the end, check the duration is stable across
  two runs, and reprocess if it grows. A wrong F card posted mid-call is not recoverable.
- A call that drops and reconnects arrives as two meetings. Process the pair together.

**CRM**
- Dedup against the deal's own activity log, not a cursor file. Cursors get lost and a
  re-shared recording arrives with a new id. Re-running an old call overwrites current next
  step and blockers with stale ones.
- Rendered fields (score, grade, headline) are copies of the log entry so a workflow can show
  them. The log is the record.
- Agents that create deals from forwarded emails will create duplicates. One creator per object,
  named in the runbook, and a merge script that only a person may run with `--apply`.
- Some connectors expose fewer scopes than the API (lists, invoices). Keep a private-app token
  route in `ops/` for those, behind a dry run.

**Outbound**
- In some sequencing APIs, deleting a lead from a campaign unsubscribes them team-wide unless
  you pass the right flag. Test destructive calls on yourself first.
- Connector-built Gmail drafts carry no signature, and updating a draft can detach it from its
  thread. Build the signature into the body; recreate rather than update.

**Calendly**
- Its native CRM sync creates the contact with name and email only; the UTMs stop inside
  Calendly. A webhook receiver that submits a hidden CRM form fixes attribution
  (`ops/receivers/`).
