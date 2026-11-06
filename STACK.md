# Stack recommendations

What we ran at Kartel, why, what larger GTM teams run instead, and how to actually wire each
piece. The architecture does not depend on any one vendor: every tool below sits behind one
skill or one runbook file, so swapping a tool means editing that one file, not the system.

**The rule for picking a tool:** it needs a Claude connector (MCP), an MCP server it ships
itself, or a clean documented API. If an agent cannot read and write it, it is a manual step,
and manual steps are where the system leaks. A tool with a beautiful UI and no API is a tool a
person has to operate by hand forever.

**This file does not pick for you.** `SETUP.md` step 1 asks what you already use or want to use
before anything gets wired. Read this to understand the tradeoff, then tell Claude your choice.

## Quick reference

| Layer | What we ran | Why | Alternatives | Who tends to run which |
|---|---|---|---|---|
| **Agent runtime** | Claude Code | Skills, hooks, subagents, scheduled cloud Routines in one tool; the repo is the agent's brain | Claude Agent SDK, if you are productizing this yourself | — |
| **The bus / versioning** | GitHub | Agents share work through branches; Actions run the checks and the watchdog | GitLab | — |
| **CRM** | HubSpot | Official Claude connector, custom properties, workflows that post to Slack on a field change | Attio (API-first, lighter), Salesforce (deepest customization) | Attio is an early-stage choice; most teams move HubSpot → Salesforce as they scale past a few reps, not the other way |
| **Call recording** | Tactiq | Claude connector returns full transcript text directly | Fathom (clean read-only API), Granola (API is read-only, paid tier only), Gong (the enterprise standard, but closed — no public API an agent can script against) | Gong dominates at scale on capability; it is not an agent-friendly choice |
| **Enrichment** | Clay | MCP connector + public API; orchestrates 75+ data providers rather than holding its own database | Apollo (all-in-one: data + sequencing), ZoomInfo (accuracy/enterprise) | Scaled teams run a *source* (Apollo or ZoomInfo) with Clay *on top* as the orchestration layer, not source vs. Clay |
| **Outbound sequencing** | lemlist | Strong multichannel personalization (email + LinkedIn in one sequence) | Smartlead (deepest API, unlimited on paid tiers — the better fit if an agent needs to read/write campaigns), Instantly (gates API behind its Growth tier) | If an agent is going to manage campaigns programmatically, Smartlead is the stronger technical fit even though lemlist's UI is nicer |
| **Scheduling** | Calendly | Webhook carries UTMs so bookings stay attributable | Cal.com (self-hostable, open API), HubSpot Meetings (no separate tool, weaker UTM handling) | — |
| **Webhook receivers** | Vercel functions | Free tier, deploys straight from `ops/receivers/` | Cloudflare Workers, Netlify | — |
| **Team signal** | Slack | One sales channel; the CRM workflow posts the card (on a CRM plan without workflows, `sales-intake` posts it through the Slack connector) | Teams | — |
| **Email** | Gmail connector | Agents draft in the rep's own thread; a person sends | Outlook connector | — |
| **Docs** | Google Drive connector | Proposals and prep land where the team already works | Notion | — |
| **Web + booking analytics** | PostHog | Booking conversions, funnels, all queryable by an agent | GA4 | — |
| **Billing (self-serve)** | Stripe | Promo codes and trials with no engineering | — | — |

## Two layers larger teams add that this scaffold intentionally skips

**Sales engagement suite** — Outreach or Salesloft for sequencing, Gong or Chorus for
conversation intelligence, Clari or Aviso for forecasting. This is the layer that shows up once
a team has enough reps that pipeline forecasting and call coaching become their own discipline.
None of it has a clean agent-scriptable API at the tier a solo founder or small team would pay
for, and the whole point of this scaffold is that Claude Code *is* your sales engagement suite.
Revisit this once you have a RevOps hire, not before.

**Intent / signal tools** — Common Room (community and product-led-growth signals, people-level)
and Warmly (website-visitor intent) sit upstream of the CRM and tell you *who to reach out to
before they raise a hand*. Both show up repeatedly in 2026 "modern GTM stack" writeups.
Genuinely useful once outbound volume justifies it; skip for your first twenty calls.

## The missing layer worth naming: integration / automation

Nothing above mentions **Zapier, Make, or n8n** — the no-code glue that connects tools without
an agent writing custom receiver code for each one. This scaffold defaults to Claude Code
writing small Vercel functions (`ops/receivers/`) instead, because a function in git is
reviewable and versioned the same way a skill is. But if a tool you want to use has no MCP
connector and no API an agent can call directly, one of these is the honest fallback:

- **n8n** has the deepest native MCP support (dedicated MCP client/server nodes) and is
  self-hostable, which fits a technical founder who wants this to stay in their own
  infrastructure.
- **Zapier** has the widest reach (8,000+ app integrations) and ships its own MCP server plus
  open-sourced GTM agent skills, which is the easiest on-ramp if you are not going to hand-write
  receivers.
- **Make** sits in between on both reach and MCP depth.

Rule of thumb: write a receiver in `ops/receivers/` when the logic needs to read context, make a
decision, or touch the CRM in a way worth versioning. Reach for Zapier/Make/n8n when it is truly
"when X happens, copy field to Y" with no judgment involved.

## Minimum viable stack

You can run the core loop with four things: **Claude Code + GitHub + a CRM with a connector +
a call recorder with a connector.** Add Slack for the card and Gmail for drafts next.
Enrichment, sequencing, receivers and analytics are the outbound and attribution layer, and can
come later.

| Stage of company | Stack |
|---|---|
| Solo founder, first 20 calls | Claude Code, GitHub, HubSpot free, Tactiq, Gmail, Slack (free HubSpot has no workflows, so the card posts through the Slack connector) |
| Founder + 1–3 sellers | + Slack card, Calendly receiver, Clay, a weekly digest routine |
| Running outbound | + Smartlead or lemlist, PostHog, the keeper routine and its watchdog |
| RevOps hire on board | + the sales engagement suite above, intent signals, n8n/Zapier for the long tail of small integrations |

## How to actually wire each one

Each of these assumes you have already told Claude which tool you picked in `SETUP.md` step 1.
"Wire it" means: get a credential, tell Claude where it lives, and have Claude build or confirm
the one file that owns that integration.

### CRM (HubSpot, Attio, or Salesforce)

1. Settings → Connectors (claude.ai or Claude Code) → connect your CRM. This covers most
   contact/company/deal reads and writes.
2. Create the custom properties `crm-records` lists (`last_call_at`, `last_call_score`,
   `last_call_grade`, `last_call_tier`, `last_call_headline`, `blockers`) in your portal's UI —
   Settings → Properties → the relevant object.
3. Copy your real pipeline and stage IDs into the stage table in `crm-records`. Ask Claude to
   pull them through the connector and fill the table rather than typing them by hand.
4. Build one native CRM workflow: *when `last_call_at` changes → post to Slack* with the fields
   named in `crm-records`. This runs inside the CRM, not as an agent action — it is the one
   notification path that should never depend on an agent being alive.
5. **If a write is refused** (some connectors expose fewer scopes than the full API — list
   membership and invoicing are common gaps), the fallback is a private-app or API-key token
   held in `ops/` behind a dry-run flag, never in chat or committed to git.

### Call recorder (Tactiq, Fathom)

1. Connect the recorder's Claude connector.
2. Confirm it returns full transcript text, not just a summary — some tiers gate this.
3. Tell `sales-intake` and `agents/postcall/RUNBOOK.md` which tool you're using; the runbook's
   transcript-timing rules (don't score a stub, wait for duration to stabilize) apply to any
   recorder, but the tool name changes which connector it looks for.

### Scheduler + attribution (Calendly)

The scheduler is the easy part — embed its booking widget on your site, with UTMs in the link.
The actual work is that Calendly's own CRM integration drops the UTMs; it hands your CRM a name
and email only. Fix:

1. Create a hidden CRM form (Forms → create, no visible fields, one per booking-attribution
   use) and note its portal ID and form ID.
2. Deploy `ops/receivers/api/booking-CHANGE-ME.js` (rename it) to Vercel. Fill in
   `PORTAL_ID`/`FORM_ID`. The function holds no secret — the CRM forms-submit endpoint is
   public, and the function's own URL path is the shared secret between Calendly and Vercel.
3. Register a webhook subscription pointed at that URL for the `invitee.created` event. Calendly
   requires a personal access token with `webhooks:read` + `webhooks:write`
   (Integrations & apps → API and webhooks). Ask Claude to write a small `register.py` that
   lists/creates/deletes the subscription — the logic is identical regardless of company,
   it is maybe twenty lines.
4. Test by booking a real slot through the widget with a tagged link, then check the CRM
   contact for the UTM fields. Cancel the test booking after.

### Enrichment (Clay)

1. Get a Clay API key from **Settings → Account → API keys (beta)**. It starts `clay_scoped_`.
   The older Account → API key (`clay_user_...`) is rejected by the Public API.
2. Clay's public API takes a `clay-api-key` header; endpoints exist for company-by-domain and
   person-by-name lookups, and for firing a custom enrichment workflow (a "table") you've built
   in Clay's UI.
3. The pattern: a CRM workflow fires a webhook on contact creation → a receiver in
   `ops/receivers/` fetches the contact, calls Clay, writes back only blank fields. Writing
   only blank fields means a human-entered value is never overwritten.
4. Clay sits *on top of* a data source (Apollo or ZoomInfo) rather than replacing one — decide
   which source(s) you're paying for before building the enrichment table, since that is what
   Clay waterfalls across.

### Outbound sequencing (lemlist or Smartlead)

1. Get an API key from the tool's settings.
2. If you want an agent to read campaign state and add/remove leads (not just fire-and-forget a
   sequence), check the tier gate first — Instantly locks API access behind its Growth plan;
   lemlist's API is lighter on campaign management than Smartlead's.
3. **The gotcha that cost us real time:** in at least one of these tools, deleting a lead from a
   campaign unsubscribes them *team-wide* unless you pass the exact right flag/parameter. Test
   every destructive call against yourself first, not a real lead.
4. If you want click/reply events to trigger something (a task, a Slack ping), register a
   webhook the same way as the Calendly receiver above: one small function, one documented
   event type, written back to the CRM.

### Webhook receivers (Vercel)

1. `npx vercel login` once.
2. Each receiver is one file in `ops/receivers/api/`. Deploy with the project's `deploy.sh` or
   `vercel --prod`.
3. Secrets (API keys, tokens) go in Vercel's project environment variables, never in the
   committed file.

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

## Our picks (filled at setup)

<!-- Setup step 1c writes the tools you chose here, one line per layer, so later steps wire
     those instead of the defaults above. -->

| Layer | Our tool | Notes |
|---|---|---|
| CRM | | |
| Call recorder | | |
| Enrichment | | |
| Outbound sequencing | | |
| Scheduler | | |
| Team signal | | |
