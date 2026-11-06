# Outbound: target list → lemlist → clicks → LinkedIn → call list

What it does, end to end:

```
company-context "Outbound targeting" says who to aim at and who never to touch
  └─ Claude builds the list in Clay (companies, then people in the buying roles, then work email)
       └─ each person gets a rail
            ├─ WARM  already in your CRM or knows you  → sent from your main mailbox
            └─ COLD  found by Clay, not in your CRM    → lemlist, from a separate sending domain
  └─ outbound/load-lemlist.py checks the list against the CRM and loads it into a campaign
every link in every email is UTM-tagged by rail, so a booking files as "Warm email" or
"Cold email (lemlist)" on the inbound card (ops/receivers/INBOUND.md)
someone clicks a link
  └─ lemlist webhook → ops/receivers/api/lemlist-click-<suffix>.js
       ├─ scanner click (seconds after delivery)? dropped
       ├─ queued once into a lemlist LinkedIn campaign: profile visit, then connection request
       └─ LinkedIn campaign not running (plan gate)? a HubSpot task to connect by hand instead
every morning
  └─ outbound/daily-call-list.py rank   → top 30 by human clicks and opens
  └─ Claude runs Clay's phone lookup     → mobile numbers (needs the LinkedIn URL)
  └─ outbound/daily-call-list.py write  → mobilephone on the contact + one CALL task each
```

Files:

| File | Job |
|---|---|
| `outbound/load-lemlist.py` | CSV → CRM checks (customers, open deals, warm vs cold, per-company cap) → lemlist campaign. Dry run by default |
| `ops/receivers/api/lemlist-click-CHANGE-ME.js` | lemlist `emailsClicked` webhook → scanner filter → LinkedIn campaign, or a HubSpot task while LinkedIn is off |
| `ops/receivers/register-lemlist.py` | Create, list, delete and replay the lemlist webhook; check the LinkedIn campaign's status |
| `outbound/daily-call-list.py` | Ranks leads by human engagement; writes phones and CALL tasks to HubSpot |
| `ops/lemlist-resubscribe.py` | Repair for the one lemlist call that silently unsubscribes people (see gotchas) |

What is automated and what is not, plainly:

| Piece | State |
|---|---|
| Building the list in Clay | **Not automated.** Claude runs it in a session, on your ask, through the Clay connector or Clay's Public API. A person approves the list |
| Loading into lemlist | Script, run by Claude in a session. Dry run first, then `--apply` |
| Writing the emails | **Yours.** Claude places tagged links and structures; the words come from you |
| Starting a campaign | **A person**, in lemlist. Nothing here sends |
| Click → LinkedIn connect | Automated by the receiver. The LinkedIn send itself needs a lemlist plan with LinkedIn; until then it is a HubSpot task you do by hand |
| Daily call list | Two scripts with a Clay lookup between them, run by Claude in a session. Not a scheduled routine yet |
| Reply handling | **Not automated.** Replies land in the sending inbox and in lemlist. lemlist's HubSpot integration can log them on the contact; set it up in step 2 if you want that |

Do the steps in order. Each ends with a check.

## 1. Say who outbound is for

Fill **Outbound targeting** in `.claude/skills/company-context/SKILL.md` (setup step 1b does this
by interview): who to target, the signal that makes someone worth reaching now, the channel, the
exclusions, and who approves a list before it goes live. Who outbound aims at is narrower than who
buys. Write the vertical split here if your proof differs by vertical: one campaign per vertical,
each opening with the story that vertical will recognise.

Then write the exclusions as a plain file Claude can pass to the scripts, one domain per line:

```
# outbound/exclude-domains.txt  (keep it out of git if it names customers: add it to .gitignore)
your-own-domain.com
a-customer.com
a-competitor.com
```

**Check:** the Outbound targeting table has no blank rows, and the approver is a named person.

## 2. Sending setup (lemlist, or Smartlead)

Cold mail goes from a **separate domain**, never your main one. A spam complaint on a cold
campaign should cost you a throwaway domain, not the inbox your customers write to.

1. Register a second domain close to your own name. Add Google Workspace (or your mail host),
   and set SPF, DKIM and DMARC (`p=none` to start). Create one mailbox per sender.
2. In lemlist, connect each mailbox as a sender and turn on lemwarm (lemlist's warm-up). **No
   campaign sends for the first 14 days**, then a further week of warm-up beside a light ramp.
3. **Custom tracking domain.** lemlist blocks open and click tracking until one verifies. In your
   DNS: `CNAME track → custom.lemlist.com` (any subdomain name), plus the `TXT` record lemlist
   shows after you add the CNAME. Settings → Sending settings → Custom tracking domain → Check.
   If the certificate fails, add `CAA @ issue "letsencrypt.org"`.
4. **Ramp per mailbox** after warm-up: 10 a day for a week, 20 the next, cap around 35. Bounce
   above 3% on any mailbox: pause it and send the list back to verification.
5. API key: lemlist Settings → Integrations → API. Keep it in your shell environment or an
   untracked `.env` as `LEMLIST_API_KEY`, never in a committed file.
6. Optional: lemlist's HubSpot integration, to log sends and replies on the contact. Do **not**
   let it create deals; your booking workflow is the one deal writer (`INBOUND.md` step 8).

**Check:** the tracking subdomain opens in a browser; a test send to your own address lands in
the inbox, not spam; `curl -s -u ":$LEMLIST_API_KEY" https://api.lemlist.com/api/team` returns
your team.

## 3. CRM properties (HubSpot → Settings → Properties → Contact)

| Property | Type | Written by |
|---|---|---|
| `outbound_rail` | dropdown: `warm`, `cold` | `load-lemlist.py --create-contacts`, or you |
| `outbound_campaign` | single-line text | same; holds the `utm_campaign` value |
| `mobilephone` | built in | `daily-call-list.py write` |
| `lemlist_campaign_id` | single-line text | already created if you did `INBOUND.md` step 1 |

**Check:** both new properties exist. A missing one makes `--create-contacts` fail per row.

## 4. Decide the rail for each person

| Rail | Who | Sent from | `utm_source` |
|---|---|---|---|
| **Warm** | Already in your CRM: a past meeting, an inbound form, a reply, someone met at an event, a contact a teammate knows. No open deal | Your main mailbox: a HubSpot sequence, or a second lemlist campaign connected to your main-domain mailbox | `sequence` |
| **Cold** | Found by Clay, not in your CRM | lemlist, the separate domain, all senders in rotation | `lemlist` |

The rule `load-lemlist.py` enforces: a cold load skips anyone who is already a contact (they are
warm), a warm load skips anyone who is not, and both skip any company with a deal in the CRM.

Warm copy can carry a line of shared context; cold copy cannot. Keep them as separate campaigns
even when the emails are nearly the same, so the rails report separately.

Tag each person three ways so any one view tells you the rail: `outbound_rail` on the contact, a
lemlist campaign tag (`<campaign>-cold` / `<campaign>-warm`), and the UTM source on every link.

**Check:** every row in your list has a rail, and no row is both in the CRM and on the cold rail.

## 5. UTM convention

The inbound receiver's `classify()` (`ops/receivers/api/inbound-CHANGE-ME.js`) turns the tags on
the link someone booked from into one channel on the contact and the Slack card. **Tag by rail,
not by tool.** `classify()` reads `utm_source`, so a warm campaign sent through lemlist must still
say `sequence`, or every warm booking files as cold.

```
https://<your-site>/<path>/?utm_source=<source>&utm_medium=email&utm_campaign=<campaign>&utm_content=e<N>
```

| You send | `utm_source` | The card says |
|---|---|---|
| Cold email, any tool | `lemlist` (or `smartlead`, `instantly`, `apollo`) | Cold email (lemlist) |
| Warm email, any tool | `sequence` | Warm email (sequence) |
| HubSpot marketing email | `hs_email` (HubSpot adds it) | Warm email (marketing email) |
| A link you hand someone yourself | your first name, with `utm_medium=direct` | Team share (name) |

- `utm_campaign`: kebab-case, stable for the campaign's life: `outbound-<vertical>`.
- `utm_content`: the step, `e1` … `e7`.
- Lowercase, no spaces. A new source or medium value goes into `classify()` in the same change;
  anything unknown shows as `Tagged: source/medium` on the card, which is the sign the table is
  out of date.
- Point cold links at the page that converts a stranger (a case page, or a qualifying form in
  front of the calendar), not your homepage.

**Check:** open one tagged link in a private window, book a test slot from an outside address,
and confirm the card shows the right channel and `outbound-<vertical> / e1`. Delete the test
records after.

## 6. Build the list in Clay

Claude does this in a session when you ask ("build a cold list for <vertical>, 150 people"). It
reads Outbound targeting first, then:

1. **Companies.** Clay company search on the ICP: industry, headcount, location, plus your
   exclusions. Clay's `industry` filter is a fixed list; Claude reads Clay's reference values
   rather than guessing a label.
2. **People.** One or two per company in the buying roles `company-context` names, current role
   only. Through the Public API the filter is shaped like
   `experiences.any(is_current = true and seniority in (...) and job_title is_similar_to (...))`.
3. **Work email.** Clay's work-email function, run as a routine. **Poll the run until it reports
   `complete`**; reading early returns a fraction of the real hits.
4. **Columns out:** `email, firstName, lastName, companyName, companyDomain, jobTitle,
   linkedinUrl, vertical`. Keep `linkedinUrl` even if you never use LinkedIn: the phone lookup in
   step 10 cannot run without it.
5. **Volume.** About half of a raw pull survives the ICP and email checks. A month of sending
   from three warmed mailboxes is roughly 150 qualified people per vertical. Top up weekly.

The no-code alternative: a Clay table per audience with Clay's native "Add to lemlist campaign"
action on rows that pass. Then skip step 7's loader, but do its CRM checks inside the table.

Clay key and the `clay_scoped_` gotcha: `INBOUND.md` step 4.

**Check:** the CSV has a work email on every row, a LinkedIn URL on most, and the approver named
in Outbound targeting has looked at it.

## 7. Load the list into lemlist

1. Create the campaign in lemlist (one per vertical, per rail). Copy its id from the URL.
2. Dry run:
   ```
   python3 outbound/load-lemlist.py leads.csv --campaign <id> --rail cold \
     --name outbound-<vertical> --exclude-file outbound/exclude-domains.txt
   ```
   Read every skip reason. "Already a HubSpot contact" on the cold rail means that person moves to
   the warm list, not that they are dropped.
3. `--apply` to load. Add `--create-contacts` on the cold rail to create each person in HubSpot
   with `outbound_rail=cold`, so a later booking matches a known contact.

**Check:** the campaign's lead count in lemlist equals the "loaded" line, and nobody from your
exclusions file is in it.

## 8. Write the sequence and start it

- **The words are yours.** Claude can place tagged links, order steps and cut; it does not write
  your outbound copy. Prospects can tell, and so can you.
- Shape that worked: one story per email, each opening with proof the vertical recognises, one
  link, one ask. Four to seven steps, four days apart. The signature comes from the mailbox
  settings, not the copy.
- Every link tagged per step 5. A booking from an untagged link is unattributable forever.
- Send the sequence to your own address from a test campaign. **Read it there, never from the
  sender's Sent folder** (gotchas).
- A person starts the campaign in lemlist.

**Check:** the first real send day shows sends in lemlist and zero bounces above 3%.

## 9. Click → LinkedIn connect

LinkedIn has no API for connection requests, and scripting your own account is how accounts get
restricted. lemlist sends from your connected LinkedIn account at its own daily limit.

1. **One LinkedIn campaign in lemlist**: sender is the founder only, sequence is a profile visit
   (day 0) then a connection request (day 1), no note. If you use the inbound receiver's LinkedIn
   connect, use the same campaign (`LEMLIST_CAMPAIGN_ID` there).
   **Plan gate:** lemlist's email-only plans refuse LinkedIn steps ("Upgrade your plan to use
   this feature"). On that plan, create the campaign with no steps and leave it in draft; the
   receiver queues clickers in it and opens a HubSpot task per click instead (below).
2. Rename `ops/receivers/api/lemlist-click-CHANGE-ME.js` with a random suffix
   (`openssl rand -hex 12`).
3. Vercel env vars: `LEMLIST_API_KEY`, `LEMLIST_LINKEDIN_CAMPAIGN_ID`,
   `LEMLIST_SOURCE_CAMPAIGNS` (`cam_xxx:cold,cam_yyy:warm`: the campaigns whose clicks count),
   `HUBSPOT_ACCESS_TOKEN`, optionally `TASK_OWNER_EMAIL` and `SCANNER_SECONDS`. Deploy from
   `ops/receivers/` (`npx vercel deploy --prod`).
4. Register the hook:
   ```
   export LEMLIST_HOOK_URL=https://<project>.vercel.app/api/lemlist-click-<suffix>
   export LEMLIST_SOURCE_CAMPAIGNS=cam_xxx:cold,cam_yyy:warm
   python3 ops/receivers/register-lemlist.py create
   ```
5. If clicks already happened before the hook existed: `register-lemlist.py replay`. Replayed
   events carry no click time, so the scanner guard cannot judge them; review the tasks a replay
   opens and delete the machine ones (corporate security domains, all at once).
6. **The day LinkedIn is on your plan:** add the two steps to the LinkedIn campaign in lemlist,
   start it, and run `register-lemlist.py status`. The tasks stop on their own once it reads
   `running`.

Why a webhook into a second campaign, rather than a "clicked → LinkedIn" branch inside the email
sequence: lemlist refuses edits to a sequence's branches once leads have walked it, so a running
campaign cannot gain the branch. The webhook also catches a click on any step of any campaign.

**Check:** click a link in a test email sent to your own address, from a different device, at
least a minute after it arrived. Within seconds the receiver's log shows the click; you are in
the LinkedIn campaign; if it is not running, a HubSpot task "Connect on LinkedIn: <you>" exists.
Remove yourself with `?action=remove` (gotchas) and delete the task.

## 10. Daily call list

The people worth a call today are the ones who clicked or kept opening. Phones come from Clay.

1. **Rank.**
   ```
   python3 outbound/daily-call-list.py rank --days 14 --limit 30 \
     --exclude-file outbound/exclude-domains.txt --out call-list.json
   ```
   Score is human clicks x10 plus human opens x2. lemlist's bot flag is honoured; a click within
   45 seconds or an open within 90 seconds of the send is dropped as a scanner. Anyone who replied
   is left off (answer the reply instead), and so is anyone whose HubSpot contact has a deal.
2. **Phones (Claude, through the Clay connector).** In Clay, set up a mobile-phone enrichment as
   a workspace function (Clay's phone waterfall, saved so the connector can see it). Claude lists
   the workspace functions, then runs it on every row with `"needsPhone": true`, passing the
   LinkedIn URL, full name, company name, company domain and work email, and writes the result
   into `phone` in the JSON. **The LinkedIn URL is required**; a row without one errors in Clay
   and stays without a phone. Clay's Public API had no phone function when this was built, which
   is why this step runs through the connector and not inside the script.
3. **Write.** `python3 outbound/daily-call-list.py write call-list.json`, read the dry run, then
   `--apply`. Each number goes to `mobilephone` (only when blank) and one CALL task opens per
   person, due today, with the signal, number, title and LinkedIn URL in the body.
4. Call. Log the outcome on the task. A connect that wants a meeting is booked from a tagged link
   (`utm_source=<your first name>&utm_medium=direct`) so it still attributes.

Check the rules where your prospects are before you dial a mobile. Business-to-business calling
rules differ by country and some places require consent or do-not-call list checks; the
simplest safe default is to exclude regions you have not checked, using the exclude file.

**Check:** the HubSpot task list shows today's CALL tasks with numbers in them, and nobody on the
list has replied or has a deal.

## The daily loop, once it runs

| When | What | Who |
|---|---|---|
| Morning | `daily-call-list.py rank`, Clay phones, `write` | Claude, on your ask |
| Morning | Clear the "Connect on LinkedIn" tasks, if LinkedIn is not on your plan | You |
| Through the day | Calls, replies in the sending inboxes | You |
| Weekly | New list per vertical (steps 6–7), approved before load | Claude builds, a person approves |
| Weekly | Bounce rate per mailbox; pause any above 3% | Claude reports |

## Known gotchas (all of these happened)

- **Deleting a lead unsubscribes them, team-wide.** `DELETE /campaigns/{id}/leads/{lead}`
  without `?action=remove` does not remove the lead from that campaign: it puts the address on
  the team's unsubscribe list and stops the person in every campaign. The response is a 200 with
  the lead body either way. It stopped a batch of live leads before anyone noticed. Always pass
  `action=remove`; the repair is `ops/lemlist-resubscribe.py`. Test any destructive call on your
  own address first.
- **Most first-day clicks are scanners.** Corporate email security fetches every link 15 to 30
  seconds after delivery, and lemlist records it as a click. On the first day of one campaign
  every cold-rail "click" was a scanner at large holding-company agencies; the real clicks came
  a minute to several hours after the send. Treat raw click counts as inflated until filtered.
- **Opening your own campaign from the Sent folder records the prospect opening it.** Tracking
  pixels and link redirects are keyed to the recipient. Bursts of opens across different
  prospects inside the same minute or two are one person paging a mailbox, not an audience.
  Check links from a test send to yourself, in a private window.
- **A cluster filter that chains eats real opens.** A rule that grouped events "until a gap
  exceeds the window" merged a steady trickle of genuine opens into one giant cluster and threw
  it all away, so the best batch read as the worst. Use anchored windows or a per-lead
  send-to-event latency test (what these scripts do), and sanity-check: adjusted opens can never
  be fewer than human replies.
- **Out-of-office replies are not engagement.** An auto-responder fires without loading the
  pixel. A foreign-language out-of-office counted as a real reply for three days. Classify
  replies before counting them.
- **Warm sends through lemlist report as cold** if their links say `utm_source=lemlist`.
  `classify()` reads the source. Tag by rail (step 5).
- **LinkedIn steps need a lemlist plan that includes LinkedIn.** The account can show LinkedIn
  as connected while the API still refuses the steps. The click receiver's HubSpot-task fallback
  exists for exactly this.
- **lemlist will not edit a running sequence's branches** (`409` once leads have walked it), so
  "add a LinkedIn branch for clickers" to a live campaign is impossible. Hence the webhook.
- **One webhook per target URL.** lemlist accepts a given `targetUrl` once, so it is one
  team-wide hook and the receiver filters on `LEMLIST_SOURCE_CAMPAIGNS`. A hook that answers 404
  or 410 is disabled and keeps its slot until deleted; the receiver always answers 200.
- **lemlist returns 403 to Python's default User-Agent** (Cloudflare error 1010); curl works.
  Every script here sets its own User-Agent.
- **Clay work-email lookups read early look like a 17% hit rate.** The routine is asynchronous;
  poll until `complete` and the real rate was around 70%.
- **Clay's phone lookup needs a LinkedIn URL.** Rows without one fail rather than skip. Keep the
  URL from the first pull.
- **The lemlist→HubSpot integration was never finished in the source system.** Without it,
  replies and sends live only in lemlist; the scripts here do the CRM writes they need
  themselves. Decide on day one whether you want it.
- **New sending domains burn fast.** Two weeks of warm-up before any campaign send, and a slow
  per-mailbox ramp, or the domain lands in spam and takes the campaign with it.
