# Receivers — booking attribution

A scheduler's native CRM sync usually creates the contact with name and email only. The UTMs
your booking links carry stop inside the scheduler. This receiver closes the gap.

1. The scheduler fires `invitee.created` with `tracking` (UTMs) and form answers.
2. `api/booking-<secret>.js` on Vercel receives it and submits a **hidden CRM form**. The forms
   endpoint needs no token, so the function holds no secrets; the unguessable path segment is
   the shared secret.
3. The CRM upserts the contact by email with `booking_utm_*` fields. An untagged booking gets
   `booking_utm_source = (none)` so silence is visible.
4. A CRM workflow on the meeting waits a few minutes for this write, then pings Slack with the
   source on it.

## Deploy

1. Rename `api/booking-CHANGE-ME.js` with a random suffix (`openssl rand -hex 12`).
2. Set `PORTAL_ID` and `FORM_ID` in it (public values).
3. `npx vercel deploy --prod` from this folder. Turn Vercel Authentication off for production.
4. Register the webhook with your scheduler's API (organization scope, `invitee.created`).
5. Prove it: POST a fake payload and check the test contact in the CRM, then delete it.
