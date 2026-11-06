# Receivers

Vercel functions, one project. Each has its own guide:

| Function | Guide |
|---|---|
| `api/booking-*.js` | this page |
| `api/inbound-*.js` | [INBOUND.md](INBOUND.md): Clay enrichment, fit score, Slack card |
| `api/lemlist-click-*.js` | [outbound/OUTBOUND.md](../../outbound/OUTBOUND.md): click → LinkedIn connect |
| `api/sign-*.js` | [close/CLOSE.md](../../close/CLOSE.md): DocuSign envelope completed → Closed Won |
| `api/invoice-*.js` | [close/CLOSE.md](../../close/CLOSE.md): Closed Won → draft invoice |

## Booking attribution

A scheduler's native CRM sync usually creates the contact with name and email only. The UTMs
your booking links carry stop inside the scheduler. This receiver closes the gap.

1. The scheduler fires `invitee.created` with `tracking` (UTMs) and form answers.
2. `api/booking-<secret>.js` on Vercel receives it and submits a **hidden CRM form**. The forms
   endpoint needs no token, so the function holds no secrets; the unguessable path segment is
   the shared secret.
3. The CRM upserts the contact by email with `booking_utm_*` fields. An untagged booking gets
   `booking_utm_source = (none)` so silence is visible.
4. The inbound receiver (`api/inbound-<secret>.js`) reads those fields, enriches the contact
   through Clay and posts the Slack card. See [INBOUND.md](INBOUND.md).

## Deploy

1. Rename `api/booking-CHANGE-ME.js` with a random suffix (`openssl rand -hex 12`).
2. Create a HubSpot form named Booking attribution with `email`, `firstname`, `lastname`,
   `booking_utm_source`, `booking_utm_medium`, `booking_utm_campaign`, `booking_utm_content`,
   `booking_event_type`, `booking_answers` and `booking_start_time`. Copy its GUID from the form's
   URL into `FORM_ID` and your portal id into `PORTAL_ID` (public values). A field missing from the
   form rejects the whole submission, and the receiver still returns 200, so read `crm` in its
   response: it must be 200.
3. `npx vercel deploy --prod` from this folder. Turn Vercel Authentication off for production.
4. Register the webhook with your scheduler's API (organization scope, `invitee.created`). For
   Calendly see `STACK.md` § Scheduler, step 3 (paid plan, personal access token).
5. Prove it: POST a fake payload and check the test contact in the CRM, then delete it.
