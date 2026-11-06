# Inbound: book a demo → enriched lead → Slack card

What it does, end to end, with nobody typing:

```
visitor lands on a tagged link
  └─ site/attribution.js stores UTMs + referrer + landing page (90-day cookie)
visitor books on Calendly            or      fills a form on your site
  └─ booking receiver writes              └─ form posts inbound_* hidden fields
     booking_utm_* to the contact
HubSpot workflow fires (Booking or Form)
  └─ POSTs the contact to the inbound receiver
       ├─ Clay: company by domain, person by name  → clay_* properties
       ├─ company found or created, linked to the contact
       ├─ channel + campaign rolled up              → inbound_channel, inbound_campaign
       ├─ ICP fit 0-100 with reasons                → inbound_fit_score, inbound_fit_reasons
       ├─ optional: LinkedIn connect via lemlist for A/B fits
       └─ card posted in your sales Slack channel (seconds, not minutes)
HubSpot workflow creates a Lead deal with contact AND company attached
```

The card reads like this:

```
📅 Jane Doe booked a demo for Tue, Nov 11, 2:00 PM EST
VP Marketing at Acme · Software, 51-200 staff, Austin, Texas
Fit: A (83) · senior buyer, target industry, 51-200 staff, in band, in region, booked a demo
Came from: LinkedIn paid · q4-launch / video-a
Said: "We want to see how it handles enterprise SSO"
HubSpot · LinkedIn · email · site visits
```

Files:

| File | Job |
|---|---|
| `site/attribution.js` | First-touch capture, Calendly handoff, hidden form fields |
| `ops/receivers/api/booking-CHANGE-ME.js` | Calendly `invitee.created` → `booking_utm_*` on the contact (see `README.md`) |
| `ops/receivers/api/inbound-CHANGE-ME.js` | Clay enrichment, fit score, Slack card |
| `ops/receivers/vercel.json` | 60-second limit; Clay lookups take 10-50 seconds |

Do the steps in order. Each ends with a check.

## 1. Contact properties (HubSpot → Settings → Properties → Contact)

Create these as single-line text unless noted. Group them as "Inbound" so they're findable.

| Property | Written by |
|---|---|
| `inbound_utm_source`, `inbound_utm_medium`, `inbound_utm_campaign`, `inbound_utm_content` | your site's forms |
| `inbound_referrer`, `inbound_landing_page`, `inbound_form_page`, `posthog_distinct_id` | your site's forms |
| `booking_utm_source`, `booking_utm_medium`, `booking_utm_campaign`, `booking_utm_content`, `booking_event_type`, `booking_answers`, `booking_start_time` | booking receiver |
| `clay_company_name`, `clay_company_size`, `clay_company_industry`, `clay_company_revenue`, `clay_company_location`, `clay_company_linkedin`, `clay_job_title`, `clay_person_location` | inbound receiver |
| `clay_company_description`, `clay_match_note` (multi-line text), `clay_enriched_at` | inbound receiver |
| `inbound_channel`, `inbound_campaign`, `inbound_channel_basis`, `inbound_fit_reasons` | inbound receiver |
| `inbound_fit_score` (number) | inbound receiver |
| `ping_posted_at`, `ping_slack_ts`, `ping_kind`, `ping_claim_at`, `ping_claim_kind` | inbound receiver (duplicate guard) |
| `lemlist_campaign_id` | inbound receiver, only if you use the LinkedIn connect |

Claude can create these for you through the HubSpot connector if it has property write access;
otherwise it's ten minutes in the UI.

**Check:** every property above exists. A missing one makes the receiver's PATCH fail, which
posts the bare "enrichment failed" card instead of the full one.

## 2. The site snippet

1. Set `OWN_DOMAIN` in `site/attribution.js` and load it on every page.
2. On each form that posts to HubSpot, add `window.gtmAttribution.hubspotFields()` to the fields
   (example at the bottom of the file). In HubSpot, add every `inbound_*` property and
   `posthog_distinct_id` to that form as hidden fields, or the Forms API rejects the submission.
3. Calendly links and embeds on the page are patched automatically.

**Check:** open your site with `?utm_source=test&utm_medium=check`, then click a Calendly link.
The Calendly URL carries `utm_source=test`. Open a second tab without the query string and click
again: still carried (that's the cookie).

## 3. Booking receiver

Follow `README.md` in this folder. It writes the booking UTMs onto the contact.

## 4. Clay key

In Clay: **Settings → Account → API keys (beta)**. The key starts `clay_scoped_`. The older key
under Account → API key (`clay_user_...`) is for in-Clay table lookups and the Public API
rejects it.

**Check:** `curl -s https://api.clay.com/public/v0/me -H "clay-api-key: $KEY"` returns your user.

## 5. Slack app

1. api.slack.com/apps → Create app → From scratch. Bot scope: `chat:write`. Install to workspace.
2. Copy the Bot User OAuth Token (`xoxb-...`).
3. **Invite the app to your sales channel** (`/invite @yourapp`). Without this every post fails
   with `not_in_channel`, and the cards silently fall back.
4. Copy the channel id (channel details, bottom of the About tab).

## 6. HubSpot private app

Settings → Integrations → Private apps → Create. Scopes: `crm.objects.contacts.read/write`,
`crm.objects.companies.read/write`, `crm.objects.owners.read`. Copy the token.

## 7. Deploy the inbound receiver

1. Rename `api/inbound-CHANGE-ME.js` with a random suffix (`openssl rand -hex 12`).
2. Edit the `FIT` block at the top to match your ICP in `company-context`, and set
   `OWN_DOMAINS`.
3. In the Vercel project, set `HUBSPOT_ACCESS_TOKEN`, `HUBSPOT_PORTAL_ID`, `CLAY_API_KEY`,
   `SLACK_BOT_TOKEN`, `SLACK_CHANNEL`, and optionally `SLACK_MENTIONS`, `TIMEZONE`,
   `POSTHOG_PROJECT_URL`, `LEMLIST_API_KEY`, `LEMLIST_CAMPAIGN_ID`.
4. `npx vercel deploy --prod` from this folder. Turn Vercel Authentication off for production
   (HubSpot can't log in).

**Check:** dry run against a real contact id. Nothing is written or posted; you get the card back.

```
curl -s -X POST "https://<project>.vercel.app/api/inbound-<suffix>?dry=1&kind=booking" \
  -H "Content-Type: application/json" -d '{"objectId": "<contact id>"}'
```

Read the `card` and `out.clay_match_note`. If the fit feels wrong, edit `FIT`, redeploy, repeat.

## 8. HubSpot workflows

**Plan check.** The "Send webhook" action needs Operations Hub (Data Hub) Professional or above,
and any workflow needs a paid plan. Without them, skip this step: set `INBOUND_URL` (the inbound
receiver's full URL) and `HUBSPOT_ACCESS_TOKEN` in Vercel, and the booking receiver hands every
booking to the inbound receiver itself. Create deals by hand. Form fills then get no card, because
nothing can tell the receiver about them; check your plan's custom-property limit too.

Build three workflows. **Build each once.** Duplicate copies of a
workflow (an old draft left on next to the final one) each fire, and two copies of the deal
workflow create two identical deals 29 milliseconds apart.

**Booking.** Trigger: the contact's `booking_event_type` is known. Don't trigger on the meeting
activity: it can fire before the UTMs land. Actions:
1. Send webhook: POST to `https://<project>.vercel.app/api/inbound-<suffix>?kind=booking`,
   contact object.
2. Delay 3 minutes.
3. If/then: `ping_posted_at` is unknown → send a Slack notification with name, company and the
   record link. This is the fallback for the day Vercel is down, not the main path; the
   receiver normally posts in seconds and stamps `ping_posted_at`, so this branch stays quiet.

**Form.** Trigger: form submission on your site's forms. Exclude the Booking attribution form, or
each booking posts two cards. Same three actions with `?kind=form`.

**Create deal.** Trigger: same as Booking, plus "contact has no open deal". Delay 3 minutes first:
the receiver creates and links the company 10 to 50 seconds after the trigger, so an immediate
copy finds no company. Action: create a deal in your pipeline's first stage, named from the company. Then add a second association on
that action: **copy association** from the contact's primary company to the deal. Without it
the deal shows no company.

**Check:** book a real slot from an outside email address with a tagged link. Within a minute:
one card in Slack, the contact carries `clay_*` and `inbound_*` values, one deal exists with
contact and company attached. Cancel the booking and delete the test records after.

## Known gotchas (all of these happened)

- **HubSpot redelivers.** Its webhook action times out before Clay finishes, marks the call
  failed, and retries on a backoff. The receiver's claim/stamp guard stops the five-cards-per-lead
  storm; keep the `ping_*` properties.
- **Scheme-less referrers.** The site stores `www.linkedin.com`; parsing it without a scheme
  throws and files LinkedIn traffic as Direct. The receiver adds the scheme.
- **Mail domain ≠ web domain.** `estee.com` is `esteelauder.com` in Clay; the company lookup
  misses. The note says so, and the fit falls to "unknown" rather than a penalty. Not automated.
- **Names.** Middle initials, nicknames and hyphenated surnames miss a full-name match. The
  receiver retries on the surname and picks on first name; two exact matches is refused, not
  guessed.
- **Free-mail.** Gmail and friends skip the company lookup, and the person lookup needs a
  company, so the card shows what the form sent.
- **Clay 429s** when several leads land at once. The receiver waits 10 seconds and retries twice.
- **Calendly embeds** need `embed_domain` to match the host serving the page, or they render
  blank on preview domains. The snippet sets it.
- **Consent banners.** If analytics load only after Accept, a visitor who never clicks Accept
  has no PostHog id. The attribution cookie holds campaign parameters only; check your own rules
  on whether it needs consent.
