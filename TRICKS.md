# Tricks

Every gotcha below cost real time on a live system. Each has the symptom, why it happens and the
fix. Flow-specific gotchas also sit next to their flow (`ops/receivers/INBOUND.md`,
`outbound/OUTBOUND.md`, `close/CLOSE.md`); this file is the one place to scan them all.

When you hit a new one, add it here in the same shape and commit.

## lemlist

**Deleting a lead unsubscribes them from your whole team.**
`DELETE /api/campaigns/{campaignId}/leads/{leadIdOrEmail}` puts the address on the team-wide
unsubscribe list unless the query carries `?action=remove`. The response is a 200 with the lead
body either way, so nothing looks wrong until their other campaigns show `unsubscribed`.
Fix: always send `?action=remove`. To undo it, delete the address from the unsubscribe list
(`DELETE /api/v2/unsubscribes/variables/{email}`, legacy `DELETE /api/unsubscribes/{email}`),
then resume or re-add the lead in each campaign.

**Security scanners click every link.** Corporate mail filters open and click links seconds
after delivery. Treat a click within a minute or two of the send, or a burst of clicks on every
link at once, as a scanner, not a human, before it triggers anything (a LinkedIn connect, a call
task, a "hot lead" alert).

**Some automations need a higher plan.** LinkedIn steps and some webhook features are gated by
plan tier. Check before you build the flow around one; the fallback is a CRM task for a person.

## Gmail (Claude connector)

**Drafts carry no signature.** Gmail adds your signature only in its own compose window. A draft
made through the API gets exactly the body you send. Fix: build the signature into the draft's
HTML body (and a plain-text alternative). Keep it in one file the drafting skills read.

**Updating a reply draft breaks the thread.** `update_draft` on a reply drops the In-Reply-To
header, so the draft becomes a new email in its own thread. Fix: never update a reply draft;
create a new draft with the reply-to message id and delete the old one.

**Attachments must be small.** Large attachments through the connector fail or time out. Link to
a document instead of attaching it, or keep the file compact.

## HubSpot

**The Claude connector can't write lists or segments.** Even with every scope approved, list and
active-segment writes fail if the HubSpot user lacks the permission behind the scope (a lock icon
on the consent screen). Reconnecting doesn't fix it. Fix: Claude gives you the filters, you build
the list in the UI, then Claude attaches it by id.

**The connector can't create invoices.** "Managing invoices is not supported." Fix: a private
app token with `crm.objects.invoices.write`, `crm.schemas.invoices.write` and
`crm.objects.line_items.write`. Without the line-items scope the invoice is created at $0 and the
line item fails with a 403. Check a token's scopes with
`POST /oauth/v2/private-apps/get/access-token-info`. Keep invoices as drafts; a person sends them.

**Duplicate workflows create duplicate records.** An old draft of a workflow left switched on
next to the final one fires too. Two copies of a create-deal workflow made two identical deals 29
milliseconds apart. Fix: build each workflow once; when you rebuild, delete the old one first.

**A create-deal action attaches the contact only.** The deal shows no company. Fix: add a second
association on the same action, copying the contact's primary company onto the deal.

**Agents that create deals must dedupe first.** An agent creating deals from forwarded emails
made seven deals in one night, every one a duplicate of an existing deal. Fix: match on company
domain and open deals before creating anything; merge into the older deal, which carries the
history.

**Webhook actions time out and redeliver.** HubSpot's "send webhook" action gives up before slow
work finishes, marks the call failed, and retries on a backoff. Fix: answer 200 always, and make
the receiver idempotent (claim and stamp fields on the record). See `ops/receivers/INBOUND.md`.

**Forms API rejects fields not on the form.** Every hidden field you send must exist as a
property and be added to the form in HubSpot, or the whole submission is rejected.

## Clay

**Use the right key.** The Public API takes a `clay_scoped_...` key from Settings → Account →
API keys (beta). The older `clay_user_...` key is rejected.

**A miss is a lookup failure, not a fact about the lead.** Mail domains that differ from the web
domain (a short corporate mail domain), people filed under a parent company, nicknames and
hyphenated surnames all miss. Never let a miss lower a fit score below "unknown".

**Bursts get rate-limited.** Several leads at once return 429. Wait and retry, within your
function's time limit.

## Slack

**The bot must be in the channel.** A bot token with `chat:write` still fails with
`not_in_channel` until someone invites the app. Every card silently falls back until then.

## Calls and scoring

**Never score from a summary.** Read the entire transcript, and confirm it's the right call
(attendees, date, company) before scoring. Summaries drop the objections and the exact next
step, which are what the score turns on.

**The CRM lags the calendar and inbox.** A meeting the client booked from their side, or a reply
in Gmail, never reaches the deal on its own. Check the last 14 days of calendar and inbox before
scoring a deal or writing the digest.

**Score the motion the call is in.** A demo graded against discovery objectives always fails.
Give every stage its own objectives (`sales-call-scorer/RUBRIC.md`).

## Website and tracking

**Calendly embeds need `embed_domain`.** It must match the host actually serving the page, or
the embed renders blank on preview and staging domains.

**UTMs die at the scheduler unless you carry them.** Store first-touch UTMs in a cookie on
landing and append them to every Calendly link (`site/attribution.js`), then write them to the
CRM from Calendly's webhook (`ops/receivers/`).

**Scheme-less referrers parse as nothing.** `new URL("www.linkedin.com")` throws; add a scheme
first or every LinkedIn visitor reads as Direct.

**Consent banners hide tracking.** Anything loaded only after Accept never sees visitors who
don't click it. Decide what loads before consent, and know that your numbers undercount.

**Vercel previews are password-protected by default.** Turn Vercel Authentication off for the
production deployment of a webhook receiver, or the sender gets a login page.

## Agents and git

**Scheduled agents push to their own branches.** A routine that can push to `main` is an
unreviewed merge. Give each agent a `claude/<agent>` branch and merge by PR.

**Cloud routines need GitHub connected to the Claude account** that creates them, and the Claude
GitHub app installed on the repo. Without it, creating the routine is refused.

**Several sessions at once share a checkout.** Two Claude sessions committing in the same folder
collide. Use `git worktree add` per session.
