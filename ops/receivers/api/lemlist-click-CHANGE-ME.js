// lemlist click -> LinkedIn connect receiver.
//
// Someone clicks a link in one of your outbound emails. lemlist fires an `emailsClicked` webhook
// (team-wide, registered by ../register-lemlist.py) at this route. The route:
//   1. checks the shared secret lemlist echoes in every payload;
//   2. ignores clicks from campaigns not in LEMLIST_SOURCE_CAMPAIGNS;
//   3. drops scanner clicks: corporate email security fetches every link seconds after delivery
//      and lemlist records that as a click. A click fewer than SCANNER_SECONDS after the latest
//      send to that lead is treated as a machine;
//   4. adds the lead once to your LinkedIn campaign in lemlist (profile visit, then a connection
//      request, sent from your connected LinkedIn account). A second click is a no-op;
//   5. while that LinkedIn campaign is NOT running (lemlist's email-only plans refuse LinkedIn
//      steps), opens a HubSpot task on the contact instead, with the LinkedIn URL, so the click
//      is acted on by hand the same day. The day the campaign runs, the tasks stop on their own.
//
// Setup and the reasons behind each rule: outbound/OUTBOUND.md, step 9.
//
// Env vars (Vercel project settings):
//   LEMLIST_API_KEY               lemlist Settings > Integrations > API key
//   LEMLIST_LINKEDIN_CAMPAIGN_ID  the lemlist campaign that holds the LinkedIn steps. Falls back to
//                                 LEMLIST_CAMPAIGN_ID, which the inbound receiver uses for the same job
//   LEMLIST_SOURCE_CAMPAIGNS      which campaigns' clicks count, as id:rail pairs, comma-separated,
//                                 e.g. "cam_xxxxxxxx:cold,cam_yyyyyyyy:warm"
//   HUBSPOT_ACCESS_TOKEN          private app token: contacts read/write, owners read
//   TASK_OWNER_EMAIL              optional, the HubSpot user who gets the fallback tasks
//   SCANNER_SECONDS               optional, default 45
//
// The webhook secret is sha256('lemlist-click:' + LEMLIST_API_KEY). register-lemlist.py derives the
// same value when it creates the hook, so no extra secret is stored anywhere. The unguessable file
// name is the second lock: rename this file with a random suffix (openssl rand -hex 12).
//
// Always answers 200 on its own failures: lemlist disables a hook that returns 404/410, and the
// target URL slot then stays taken until the hook is deleted.
//
// ?dry=1 does the checks and lookups but adds nothing and creates no task; it returns what it would do.

const crypto = require('crypto');
const LEM = 'https://api.lemlist.com/api';
const HS = 'https://api.hubapi.com';
const LINKEDIN_CAMPAIGN = process.env.LEMLIST_LINKEDIN_CAMPAIGN_ID || process.env.LEMLIST_CAMPAIGN_ID || '';
const SOURCE = Object.fromEntries((process.env.LEMLIST_SOURCE_CAMPAIGNS || '')
  .split(',').map(s => s.trim()).filter(Boolean)
  .map(pair => { const [id, rail] = pair.split(':'); return [id.trim(), (rail || 'cold').trim()]; }));
const OWNER_EMAIL = process.env.TASK_OWNER_EMAIL || '';
const SCANNER_SECONDS = Number(process.env.SCANNER_SECONDS || 45);
const TASK_CONTACT_ASSOC = 204;   // HubSpot-defined association type: task -> contact

const hookSecret = () => process.env.LEMLIST_API_KEY
  ? crypto.createHash('sha256').update('lemlist-click:' + process.env.LEMLIST_API_KEY).digest('hex') : null;

async function readJson(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  let raw = '';
  for await (const chunk of req) raw += chunk;
  return raw ? JSON.parse(raw) : {};
}

async function lem(method, path, body) {
  const r = await fetch(LEM + path, {
    method,
    headers: { Authorization: 'Basic ' + Buffer.from(':' + process.env.LEMLIST_API_KEY).toString('base64'), 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  let json = null; try { json = JSON.parse(text); } catch (_) {}
  return { status: r.status, ok: r.ok, json, text };
}

async function hs(method, path, body) {
  const r = await fetch(HS + path, {
    method,
    headers: { Authorization: `Bearer ${process.env.HUBSPOT_ACCESS_TOKEN}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`hubspot ${method} ${path} ${r.status} ${text.slice(0, 200)}`);
  return text ? JSON.parse(text) : {};
}

let ownerId;
async function taskOwnerId() {
  if (ownerId !== undefined) return ownerId;
  ownerId = null;
  if (OWNER_EMAIL) {
    const o = await hs('GET', `/crm/v3/owners?email=${encodeURIComponent(OWNER_EMAIL)}`);
    ownerId = o.results?.[0]?.id || null;
  }
  return ownerId;
}

// Seconds between the click and the latest send to this lead in the source campaign; null if unknown.
// Unknown is treated as human: a lookup failure is not evidence of a scanner.
async function secondsSinceSend(ev) {
  const at = ev.createdAt ? Date.parse(ev.createdAt) : Date.now();
  const got = await lem('GET', `/activities?campaignId=${encodeURIComponent(ev.campaignId)}&leadId=${encodeURIComponent(ev.leadId)}&type=emailsSent&limit=50&version=v2`);
  const acts = Array.isArray(got.json) ? got.json : (got.json?.activities || got.json?.data || []);
  const sends = acts.map(a => Date.parse(a.createdAt)).filter(t => t && t <= at + 5000);
  if (!sends.length) return null;
  return Math.round((at - Math.max(...sends)) / 1000);
}

async function contactIdFor(lead, email) {
  if (lead.hubspotLeadId) return String(lead.hubspotLeadId);
  if (!email) return null;
  const found = await hs('POST', '/crm/v3/objects/contacts/search', {
    filterGroups: [{ filters: [{ propertyName: 'email', operator: 'EQ', value: email }] }], properties: ['email'], limit: 1 });
  return found.results?.[0]?.id || null;
}

// Fallback while the LinkedIn campaign cannot run: a HubSpot task, due now.
async function openTask(lead, v, ev, rail) {
  const cid = await contactIdFor(lead, v.email);
  const who = [v.firstName, v.lastName].filter(Boolean).join(' ') || v.email;
  const props = {
    hs_task_subject: `Connect on LinkedIn: ${who}${v.companyName ? ` (${v.companyName})` : ''}`,
    hs_task_body: [
      `Clicked a link in "${ev.subject || 'an outbound email'}" (${ev.campaignName || ev.campaignId}, ${rail} rail).`,
      v.linkedinUrl ? `LinkedIn: ${v.linkedinUrl}` : 'No LinkedIn URL on the lemlist lead.',
      v.jobTitle ? `Title: ${v.jobTitle}` : null,
      'Created by the lemlist click receiver because the LinkedIn campaign in lemlist is not running.',
    ].filter(Boolean).join('\n'),
    hs_timestamp: new Date().toISOString(),
    hs_task_status: 'NOT_STARTED',
    hs_task_priority: 'HIGH',
    hs_task_type: 'TODO',
  };
  const owner = await taskOwnerId();
  if (owner) props.hubspot_owner_id = owner;
  const body = { properties: props };
  if (cid) body.associations = [{ to: { id: cid }, types: [{ associationCategory: 'HUBSPOT_DEFINED', associationTypeId: TASK_CONTACT_ASSOC }] }];
  const t = await hs('POST', '/crm/v3/objects/tasks', body);
  return { taskId: t.id, contactId: cid };
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ ok: false, error: 'POST only' });
  const dry = /[?&]dry=1\b/.test(req.url || '');
  let ev;
  try { ev = await readJson(req); } catch (e) { return res.status(400).json({ ok: false, error: 'bad json' }); }
  const want = hookSecret();
  if (!want || typeof ev.secret !== 'string' || ev.secret !== want) {
    return res.status(401).json({ ok: false, error: 'bad secret' });
  }
  if (!LINKEDIN_CAMPAIGN) return res.status(200).json({ ok: false, error: 'LEMLIST_LINKEDIN_CAMPAIGN_ID not set' });
  const rail = SOURCE[ev.campaignId];
  if (ev.type !== 'emailsClicked' || !rail) {
    return res.status(200).json({ ok: true, ignored: true, type: ev.type, campaignId: ev.campaignId });
  }
  if (!ev.leadId) return res.status(200).json({ ok: false, error: 'no leadId' });

  const out = { ok: true, dry, rail, leadId: ev.leadId };
  try {
    if (ev.bot === true) {
      out.scanner = true; out.added = false; out.note = 'lemlist flagged the click as a bot';
      return res.status(200).json(out);
    }
    out.secondsSinceSend = await secondsSinceSend(ev);
    if (out.secondsSinceSend !== null && out.secondsSinceSend < SCANNER_SECONDS) {
      out.scanner = true; out.added = false;
      console.log('click', rail, ev.leadId, 'dropped as scanner,', out.secondsSinceSend, 's after send');
      return res.status(200).json(out);
    }
    const got = await lem('GET', `/leads?id=${encodeURIComponent(ev.leadId)}&version=v2`);
    const lead = Array.isArray(got.json) ? got.json[0] : got.json;
    if (!lead || !lead._id) throw new Error(`lead lookup ${got.status} ${got.text.slice(0, 120)}`);
    const v = lead.variables || {};
    out.email = v.email;

    if (!v.linkedinUrl) {
      out.added = false; out.note = 'no linkedinUrl on lead';
    } else if (dry) {
      out.added = false; out.wouldAdd = true;
    } else {
      // deduplicate=false: the same person may sit in the source campaign; dedup would refuse them.
      // A second add to the LinkedIn campaign itself comes back 400 "already in", which we treat as done.
      const add = await lem('POST', `/campaigns/${LINKEDIN_CAMPAIGN}/leads/?deduplicate=false`, {
        email: v.email, firstName: v.firstName, lastName: v.lastName, companyName: v.companyName,
        linkedinUrl: v.linkedinUrl, jobTitle: v.jobTitle,
        sourceCampaign: ev.campaignName || ev.campaignId, sourceRail: rail,
        clickedAt: ev.createdAt || new Date().toISOString(), clickedSubject: ev.subject || '',
      });
      if (add.ok) { out.added = true; out.linkedinLeadId = add.json?._id; }
      else if (add.status === 400 && /already in/i.test(add.text)) { out.added = false; out.already = true; }
      else throw new Error(`add to LinkedIn campaign ${add.status} ${add.text.slice(0, 160)}`);
    }

    if (out.already) return res.status(200).json(out);   // second click: nothing more to do

    const camp = await lem('GET', `/campaigns/${LINKEDIN_CAMPAIGN}`);
    out.linkedinCampaignStatus = camp.json?.status || 'unknown';
    if (out.linkedinCampaignStatus !== 'running') {
      if (dry) out.wouldOpenTask = true;
      else Object.assign(out, await openTask(lead, v, ev, rail));
    }
    console.log('click', rail, v.email, 'added', out.added, 'campaign', out.linkedinCampaignStatus, 'task', out.taskId || '-');
    return res.status(200).json(out);
  } catch (e) {
    console.log('lemlist-click failed', ev.leadId, String(e).slice(0, 300));
    return res.status(200).json({ ok: false, error: String(e).slice(0, 200) });
  }
};
