// Inbound receiver: HubSpot -> Clay -> HubSpot, then a card in your sales Slack channel.
//
// Two HubSpot workflows call this the moment a lead arrives (setup: ops/receivers/INBOUND.md):
//   Booking  (a meeting is booked)  -> POST ?kind=booking
//   Form     (a form is submitted)  -> POST ?kind=form
// For each contact it:
//   1. looks the company up in Clay by email domain and the person by name at that company, and
//      writes the clay_* contact properties;
//   2. finds or creates the HubSpot company for that domain, links it, writes the Clay facts to
//      the company (name, domain, description, LinkedIn only where blank: never overwrite a person);
//   3. rolls attribution up to one inbound_channel / inbound_campaign / basis;
//   4. scores ICP fit 0-100 with the reasons (rules, not a model, so the same lead always scores
//      the same and the card can say why). EDIT THE FIT RULES BELOW to match company-context;
//   5. posts a five-line card to Slack straight away. A booking that follows the same person's
//      form card within the hour rewrites that card in place: one card per person;
//   6. optionally queues a LinkedIn connect through lemlist for A/B fits (LEMLIST_* env vars).
// If enrichment throws, a bare card still posts, so no inbound goes unannounced.
//
// Env vars (Vercel project settings):
//   HUBSPOT_ACCESS_TOKEN  private app token: contacts + companies read/write, lists read, owners read
//   HUBSPOT_PORTAL_ID     your portal id (for record links)
//   CLAY_API_KEY          a clay_scoped_... key from Clay Settings > Account > API keys (beta).
//                         The older clay_user_... key is rejected by the Public API.
//   SLACK_BOT_TOKEN       a Slack app bot token with chat:write, and the app INVITED to the channel
//                         (not_in_channel otherwise)
//   SLACK_CHANNEL         channel id, e.g. C0123456789
//   SLACK_MENTIONS        optional, comma-separated user ids to @ on every card
//   TIMEZONE              optional, IANA zone for meeting times on the card (default America/New_York)
//   POSTHOG_PROJECT_URL   optional, e.g. https://us.posthog.com/project/12345 (links the visitor)
//   LEMLIST_API_KEY, LEMLIST_CAMPAIGN_ID  optional, LinkedIn connect for A/B fits
//
// Rename this file with a random suffix (openssl rand -hex 12). The unguessable path is the
// shared secret between HubSpot and this function.
// ?dry=1 does everything except post to Slack and stamp the ping fields; it returns the card.
// Always answers 200: a non-200 makes HubSpot redeliver on a backoff.

const CLAY = 'https://api.clay.com/public/v0';
const HS = 'https://api.hubapi.com';
const PORTAL = process.env.HUBSPOT_PORTAL_ID || '';
const SLACK_CHANNEL = process.env.SLACK_CHANNEL || '';
const MENTIONS = (process.env.SLACK_MENTIONS || '').split(',').map(s => s.trim()).filter(Boolean);
const TZ = process.env.TIMEZONE || 'America/New_York';
const POSTHOG = process.env.POSTHOG_PROJECT_URL || '';
const OWN_DOMAINS = /example\.com$/;   // CHANGE ME: your site's domains, so internal referrers are ignored
const FREE_MAIL = new Set(['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com', 'aol.com',
  'me.com', 'live.com', 'msn.com', 'protonmail.com', 'proton.me', 'ymail.com', 'googlemail.com', 'mail.com']);

// ---------------------------------------------------------------------------------------------
// ICP FIT. Edit to match .claude/skills/company-context. Points per signal; bands A 75+, B 60+,
// C 40+, D below. A Clay miss lands in the "unknown" branch, never a penalty: a miss is a lookup
// failure, not a fact about the lead.
const FIT = {
  seniority: [   // first match wins, tested against the job title and HubSpot's seniority
    [/founder|owner|partner|chief|\bceo\b|\bcmo\b|\bcro\b|\bcoo\b|president|\bvp\b|vice president|head of|managing director/, 25, 'senior buyer'],
    [/director/, 15, 'director-level'],
    [/manager|lead|principal/, 8, 'manager-level'],
  ],
  seniorityUnknown: 5, seniorityJunior: 2,
  industry: [    // tested against Clay's industry and description
    [/software|saas|internet|information technology/, 25, 'target industry'],   // CHANGE ME
    [/financial services|consulting|marketing/, 15, 'adjacent industry'],       // CHANGE ME
  ],
  industryUnknown: 5, industryOther: 3,
  sizeBand: [50, 500],   // CHANGE ME: employee range you sell to best (+20 in band)
  geo: /united states|\busa?\b/,   // CHANGE ME: where you sell (+10)
  bookedDemo: 8, businessEmail: 5, freeMail: -10, warmChannel: 5,
};

function fitScore(p, out, kind) {
  const lc = v => (v == null ? '' : String(v)).toLowerCase();
  const reasons = []; let s = 0;
  const title = lc(out.clay_job_title || p.jobtitle), sen = lc(p.hs_seniority);
  const hit = FIT.seniority.find(([re]) => re.test(title + ' ' + sen));
  if (hit) { s += hit[1]; reasons.push(hit[2]); }
  else if (!title && !sen) { s += FIT.seniorityUnknown; reasons.push('title unknown'); }
  else { s += FIT.seniorityJunior; reasons.push('junior title'); }

  const ind = lc(out.clay_company_industry || p.industry) + ' ' + lc(out.clay_company_description);
  const ih = FIT.industry.find(([re]) => re.test(ind));
  if (ih) { s += ih[1]; reasons.push(ih[2]); }
  else if (!ind.trim()) { s += FIT.industryUnknown; reasons.push('industry unknown'); }
  else { s += FIT.industryOther; reasons.push((out.clay_company_industry || 'other industry').slice(0, 40)); }

  const size = String(out.clay_company_size || ''), m = size.replace(/,/g, '').match(/(\d+)\s*-\s*(\d+)|(\d+)\s*\+/);
  if (m) {
    const lo = Number(m[1] || m[3]), hi = m[2] ? Number(m[2]) : Infinity, [blo, bhi] = FIT.sizeBand;
    if (hi >= blo && lo <= bhi) { s += 20; reasons.push(`${size} staff, in band`); }
    else if (hi < blo) { s += 8; reasons.push(`${size} staff, small`); }
    else { s += 10; reasons.push(`${size} staff, large`); }
  } else { s += 5; reasons.push('size unknown'); }

  const loc = lc([out.clay_company_location, out.clay_person_location, p.country, p.state].filter(Boolean).join(' | '));
  if (FIT.geo.test(loc)) { s += 10; reasons.push('in region'); }
  else if (!loc) { s += 4; reasons.push('location unknown'); }
  else { s += 2; reasons.push('outside region'); }

  if (kind === 'booking') { s += FIT.bookedDemo; reasons.push('booked a demo'); }
  const domain = lc(p.hs_email_domain || (p.email || '').split('@')[1]);
  if (FREE_MAIL.has(domain)) { s += FIT.freeMail; reasons.push('free-mail address'); } else if (domain) s += FIT.businessEmail;
  if (/Warm email|Referral|Team share/.test(out.inbound_channel || '')) { s += FIT.warmChannel; reasons.push('warm channel'); }

  s = Math.max(0, Math.min(100, s));
  return { score: s, band: s >= 75 ? 'A' : s >= 60 ? 'B' : s >= 40 ? 'C' : 'D', reasons: reasons.join(', ') };
}
// ---------------------------------------------------------------------------------------------

async function readJson(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  let raw = '';
  for await (const chunk of req) raw += chunk;
  return raw ? JSON.parse(raw) : {};
}

async function clay(path, body) {
  const r = await fetch(CLAY + path, {
    method: 'POST',
    headers: { 'clay-api-key': process.env.CLAY_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`clay ${path} ${r.status} ${text.slice(0, 200)}`);
  return JSON.parse(text);
}

// One Clay search = create the query, then run its first page.
//   company: select from companies where domain = "acme.com"
//   person:  select from people where full_name contains "Jane Doe" and clay.filter_to_companies(("acme.com"))
// People cannot be filtered by email or by first_name/last_name; full_name contains is a
// plain substring test.
async function claySearch(query, limit) {
  const s = await clay('/search/query-mode', { query });
  const page = await clay(`/search/query-mode/${s.search_id}/run`, { limit });
  return page.data || [];
}

// Clay answers 429 when several leads land at once. Wait ten seconds and retry, at most twice
// per request, so the function stays inside its time limit.
async function claySearchRetrying(query, limit, budget) {
  for (;;) {
    try { return await claySearch(query, limit); }
    catch (e) {
      if (!String(e).includes(' 429 ') || budget.left <= 0) throw e;
      budget.left -= 1;
      await new Promise(r => setTimeout(r, 10000));
    }
  }
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

// Channel roll-up: one reportable channel + campaign per contact, decided in a fixed order:
// tagged link (UTMs) > referrer > sequence enrolment > HubSpot's own source.
// Extend the rules here, not the card, when you add a channel.
function classify(p) {
  const lc = v => (v || '').toString().trim().toLowerCase();
  const none = v => !v || /^\(none/.test(v);
  const src = !none(p.inbound_utm_source) ? 'inbound' : !none(p.booking_utm_source) ? 'booking' : null;
  const u = src ? { source: lc(p[`${src}_utm_source`]), medium: lc(p[`${src}_utm_medium`]),
                    campaign: p[`${src}_utm_campaign`] || '', content: p[`${src}_utm_content`] || '' } : null;
  const camp = u ? [u.campaign, u.content].filter(Boolean).join(' / ') : '';
  if (u) {
    const paid = /paid|cpc|ppc|paid_social|display|sponsored/.test(u.medium);
    // A link a teammate handed over by hand: ?utm_source=<firstname>&utm_medium=direct
    if (/^(direct|dm|share|personal|referral)$/.test(u.medium)) return [`Team share (${u.source})`, camp, 'utm'];
    if (/lemlist|smartlead|instantly|apollo/.test(u.source)) return [`Cold email (${u.source})`, camp, 'utm'];
    if (/^(sequence|hubspot)$/.test(u.source) && /email/.test(u.medium || 'email')) return ['Warm email (sequence)', camp, 'utm'];
    if (u.source === 'hs_email') return ['Warm email (marketing email)', camp, 'utm'];
    if (/linkedin|^li$/.test(u.source)) return [paid ? 'LinkedIn paid' : 'LinkedIn organic', camp, 'utm'];
    if (/google|bing/.test(u.source)) return [paid ? 'Google paid' : 'Organic search', camp, 'utm'];
    if (/facebook|instagram|meta/.test(u.source)) return [paid ? 'Meta paid' : 'Meta organic', camp, 'utm'];
    if (/^(x|twitter)$/.test(u.source)) return ['X organic', camp, 'utm'];
    if (u.medium === 'email') return ['Email (other)', camp, 'utm'];
    return [`Tagged: ${u.source}${u.medium ? '/' + u.medium : ''}`, camp, 'utm'];
  }
  // The site stores the referrer's bare hostname; new URL() throws on anything scheme-less,
  // which silently files every LinkedIn visitor as Direct. Add a scheme when one is missing.
  let host = '';
  const ref = p.inbound_referrer || p.hs_analytics_first_referrer || '';
  try { host = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(ref) ? ref : 'https://' + ref).hostname.replace(/^www\./, ''); } catch (_) {}
  if (host && !OWN_DOMAINS.test(host)) {
    if (/linkedin\.com$|lnkd\.in$/.test(host)) return ['LinkedIn organic', '', 'referrer'];
    if (/google\.|bing\.com$|duckduckgo\.com$|yahoo\./.test(host)) return ['Organic search', '', 'referrer'];
    if (/^t\.co$|twitter\.com$|^x\.com$/.test(host)) return ['X organic', '', 'referrer'];
    if (/facebook\.com$|instagram\.com$/.test(host)) return ['Meta organic', '', 'referrer'];
    return [`Referral: ${host}`, '', 'referrer'];
  }
  if (Number(p.hs_sequences_enrolled_count) > 0) return ['Warm email (sequence)', '(untagged)', 'sequence'];
  const hsrc = lc(p.hs_analytics_source);
  if (hsrc === 'paid_social') return ['Paid social', p.hs_analytics_source_data_2 || '', 'hs_source'];
  if (hsrc === 'organic_search') return ['Organic search', '', 'hs_source'];
  if (hsrc === 'social_media') return ['Social organic', p.hs_analytics_source_data_1 || '', 'hs_source'];
  if (hsrc === 'referrals') return [`Referral: ${p.hs_analytics_source_data_1 || ''}`, '', 'hs_source'];
  if (hsrc === 'email_marketing') return ['Warm email (marketing email)', p.hs_analytics_source_data_1 || '', 'hs_source'];
  return ['Direct / unknown', '', 'none'];
}

const q = v => JSON.stringify(String(v));   // quote a value for Clay's query language

// Real names defeat a substring match: middle initials, nicknames, hyphenated surnames. On a
// full-name miss, search the surname's last token (survives hyphenation) and pick the row on
// first_name client-side. Two exact matches is ambiguity we refuse rather than guess: a wrong
// name on the card is worse than none.
const NAME_NORM = s => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
  .toLowerCase().replace(/[^a-z\s]/g, ' ').replace(/\s+/g, ' ').trim();
function pickPerson(rows, first, lastToken) {
  const f = NAME_NORM(first), l = NAME_NORM(lastToken);
  const onSurname = rows.filter(r => NAME_NORM(r.name).split(' ').some(t => t === l));
  const exact = onSurname.filter(r => NAME_NORM(r.first_name) === f);
  if (exact.length === 1) return [exact[0], ''];
  if (exact.length > 1) return [null, `ambiguous: ${exact.length} people named ${first} ${lastToken}`];
  // Dan/Daniel, Xander/Alexander: containment either way, only when it is the sole candidate.
  const near = onSurname.filter(r => {
    const c = NAME_NORM(r.first_name);
    return c && f && c.length >= 4 && f.length >= 4 && (c.includes(f) || f.includes(c));
  });
  if (near.length === 1) return [near[0], `matched "${first}" to the one ${lastToken} at this company, "${near[0].name}"`];
  return [null, ''];
}

const clip = (v, n = 250) => (v == null ? '' : String(v)).slice(0, n);

// HubSpot's webhook action payload shape has varied across versions; accept the id from any.
function contactIdFrom(body) {
  return body.objectId || body.vid || body.hs_object_id
    || (body.properties && (body.properties.hs_object_id?.value || body.properties.hs_object_id))
    || (body.object && body.object.objectId) || null;
}

const RECORD = id => `https://app.hubspot.com/contacts/${PORTAL}/record/0-1/${id}`;
const esc = v => (v == null ? '' : String(v)).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const link = (url, text) => (url ? `<${url}|${esc(text || url)}>` : esc(text || ''));
const atMentions = () => MENTIONS.map(u => `<@${u}>`).join(' ');

async function ownerName(id) {
  if (!id) return '';
  try { const o = await hs('GET', `/crm/v3/owners/${id}`); return [o.firstName, o.lastName].filter(Boolean).join(' ') || o.email || String(id); }
  catch (_) { return String(id); }
}

const fmtTime = v => {
  const t = Date.parse(v || '');
  if (!t) return '';
  return new Date(t).toLocaleString('en-US', { timeZone: TZ, weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
};
const bareUrl = v => (v || '').replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');

// The card: five or six short lines a person reads in five seconds. Who, what they did and when,
// the company, fit, where they came from, what they said, links. A blank line is dropped, not
// printed as a dash. Everything else stays on the HubSpot record, one click away.
function card(kind, id, p, out, fit, links, owner, li) {
  const name = [p.firstname, p.lastname].filter(Boolean).join(' ').trim() || p.email || `contact ${id}`;
  const title = out.clay_job_title || p.jobtitle || '';
  const co = p.company || out.clay_company_name || p.hs_email_domain || '';
  const L = [];
  if (MENTIONS.length) L.push(atMentions());
  const when = fmtTime(p.hs_latest_meeting_activity) || p.booking_start_time || '';
  const form = (p.recent_conversion_event_name || '').replace(/:.*$/, '').trim();
  L.push(kind === 'booking'
    ? `:calendar: *${esc(name)}* booked a demo${when ? ` for *${esc(when)}*` : ''}`
    : `:inbox_tray: *${esc(name)}* filled out ${form ? `the ${esc(form)} form` : 'a form'}${p.inbound_form_page ? ` on ${esc(bareUrl(p.inbound_form_page))}` : ''}`);
  const facts = [out.clay_company_industry || p.industry, out.clay_company_size && `${out.clay_company_size} staff`,
    out.clay_company_location || [p.city, p.country].filter(Boolean).join(', ')].filter(Boolean);
  L.push([title && esc(title), co && `*${esc(co)}*`].filter(Boolean).join(' at ') + (facts.length ? ` · ${esc(facts.join(', '))}` : ''));
  L.push(`Fit: *${fit.band} (${fit.score})* · ${esc(fit.reasons)}`);
  L.push(`Came from: ${esc(out.inbound_channel || 'Direct / unknown')}${out.inbound_campaign ? ` · ${esc(out.inbound_campaign)}` : ''}`);
  const said = [p.message, p.booking_answers].filter(Boolean).join(' / ').trim();
  if (said) L.push(`Said: "${esc(said.slice(0, 300))}"`);
  if (!owner) L.push('*Unowned*: claim it in HubSpot');
  const ln = [link(RECORD(id), 'HubSpot'),
    links.linkedin ? link(links.linkedin, 'LinkedIn') : link(links.linkedinSearch, 'find on LinkedIn'),
    p.email && link(`mailto:${p.email}`, 'email'),
    links.posthog && link(links.posthog, 'site visits')].filter(Boolean);
  if (li && li.added) ln.push('LinkedIn invite queued');
  L.push(ln.join(' · '));
  return L.join('\n');
}

// Optional LinkedIn connect through lemlist. LinkedIn has no API for connection requests, and
// scripting your own account is how accounts get restricted; lemlist sends from your connected
// account at its own daily limit. This only adds the lead; the invite note lives in lemlist.
// Gates: a real profile URL and fit A or B. Idempotent via lemlist's deduplicate flag.
async function lemlistConnect(p, out, fit, links, kind) {
  const key = process.env.LEMLIST_API_KEY, campaign = process.env.LEMLIST_CAMPAIGN_ID;
  if (!key || !campaign) return { added: false, why: 'lemlist not configured' };
  if (p.lemlist_campaign_id) return { added: false, why: `already in ${p.lemlist_campaign_id}` };
  if (!links.linkedin) return { added: false, why: 'no LinkedIn URL on the record' };
  if (!/^[AB]$/.test(fit.band)) return { added: false, why: `fit ${fit.score} (${fit.band}) below B` };
  const lead = {
    firstName: p.firstname || '', lastName: p.lastname || '', companyName: p.company || out.clay_company_name || '',
    jobTitle: out.clay_job_title || p.jobtitle || '', linkedinUrl: links.linkedin,
    inboundKind: kind, inboundChannel: out.inbound_channel || '', fitScore: String(fit.score), fitBand: fit.band,
  };
  const r = await fetch(`https://api.lemlist.com/api/campaigns/${campaign}/leads/${encodeURIComponent(p.email)}?deduplicate=true&linkedinEnrichment=false&findEmail=false&verifyEmail=false`, {
    method: 'POST', headers: { Authorization: 'Basic ' + Buffer.from(':' + key).toString('base64'), 'Content-Type': 'application/json' },
    body: JSON.stringify(lead),
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`lemlist ${r.status} ${text.slice(0, 160)}`);
  return { added: true, why: 'queued' };
}

async function slack(method, body) {
  const r = await fetch(`https://slack.com/api/${method}`, {
    method: 'POST', headers: { Authorization: `Bearer ${process.env.SLACK_BOT_TOKEN}`, 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ channel: SLACK_CHANNEL, unfurl_links: false, unfurl_media: false, ...body }),
  });
  const d = await r.json();
  if (!d.ok) throw new Error(`slack ${d.error}`);
  return d.ts;
}
const slackPost = (text, threadTs) => slack('chat.postMessage', threadTs ? { text, thread_ts: threadTs } : { text });
const slackUpdate = (ts, text) => slack('chat.update', { ts, text });

function queryOf(req) {
  if (req.query && typeof req.query === 'object') return req.query;
  try { return Object.fromEntries(new URL(req.url, 'http://x').searchParams); } catch (_) { return {}; }
}

const PROPS = ['email', 'firstname', 'lastname', 'company', 'hs_email_domain', 'jobtitle', 'hs_seniority', 'industry',
  'city', 'state', 'country', 'message', 'hs_linkedin_url', 'hubspot_owner_id', 'recent_conversion_event_name',
  'hs_latest_meeting_activity', 'hs_object_id',
  'inbound_utm_source', 'inbound_utm_medium', 'inbound_utm_campaign', 'inbound_utm_content', 'inbound_referrer', 'inbound_form_page',
  'booking_utm_source', 'booking_utm_medium', 'booking_utm_campaign', 'booking_utm_content', 'booking_event_type', 'booking_start_time', 'booking_answers',
  'hs_analytics_first_referrer', 'hs_analytics_source', 'hs_analytics_source_data_1', 'hs_analytics_source_data_2', 'hs_sequences_enrolled_count',
  'posthog_distinct_id', 'ping_posted_at', 'ping_slack_ts', 'ping_kind', 'ping_claim_kind', 'ping_claim_at', 'lemlist_campaign_id'];

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).send('POST only');
  let body;
  try { body = await readJson(req); } catch (e) { return res.status(400).send('bad json'); }
  const qs = queryOf(req);
  const dry = qs.dry === '1' || qs.dry === 'true';
  const id = contactIdFrom(body) || qs.id;
  if (!id) return res.status(200).json({ ok: false, reason: 'no contact id' });

  const notes = [];
  const retry429 = { left: 2 };
  const out = { clay_enriched_at: new Date().toISOString() };
  let p = {}, kind = qs.kind === 'booking' ? 'booking' : qs.kind === 'form' ? 'form' : '';
  try {
    const c = await hs('GET', `/crm/v3/objects/contacts/${id}?properties=${PROPS.join(',')}&associations=companies`);
    p = c.properties || {};
    if (!kind) kind = p.booking_event_type ? 'booking' : 'form';

    // Duplicate-delivery guard. HubSpot's webhook action times out before ~50s of Clay work
    // finishes, marks the call failed, and redelivers on a doubling backoff. Without this, one
    // lead produced five cards. A card of this kind in the last 30 minutes means done; a claim
    // younger than 90 seconds means a sibling run is mid-flight. An abandoned claim ages out.
    const ageMs = t => Date.now() - Date.parse(t);
    if (!dry) {
      if (p.ping_kind === kind && p.ping_posted_at && ageMs(p.ping_posted_at) < 30 * 60 * 1000)
        return res.status(200).json({ ok: true, contact: id, kind, skipped: 'card already posted' });
      if (p.ping_claim_kind === kind && p.ping_claim_at && ageMs(p.ping_claim_at) < 90 * 1000)
        return res.status(200).json({ ok: true, contact: id, kind, skipped: 'a sibling run holds the claim' });
      await hs('PATCH', `/crm/v3/objects/contacts/${id}`, { properties: { ping_claim_kind: kind, ping_claim_at: new Date().toISOString() } });
    }

    const [channel, campaign, basis] = classify(p);
    Object.assign(out, { inbound_channel: clip(channel), inbound_campaign: clip(campaign), inbound_channel_basis: basis });
    const domain = (p.hs_email_domain || (p.email || '').split('@')[1] || '').toLowerCase();
    const fullName = [p.firstname, p.lastname].filter(Boolean).join(' ').trim();

    // Company by email domain. Known miss: a mail domain that differs from the web domain
    // (estee.com vs esteelauder.com). The note records it; the fit falls to "unknown".
    let company = null;
    if (!domain) notes.push('no email domain');
    else if (FREE_MAIL.has(domain)) notes.push(`free-mail domain ${domain}, company skipped`);
    else {
      const rows = await claySearchRetrying(`select from companies where domain = ${q(domain)}`, 1, retry429);
      company = rows[0] || null;
      if (!company) notes.push(`no Clay company for ${domain}`);
    }
    if (company) {
      Object.assign(out, {
        clay_company_name: clip(company.name), clay_company_size: clip(company.size),
        clay_company_industry: clip(company.industry), clay_company_revenue: clip(company.annual_revenue),
        clay_company_location: clip(company.location), clay_company_linkedin: clip(company.linkedin_url),
        clay_company_description: clip(company.description, 2000),
      });
    }

    let person = null;
    if (!fullName) notes.push('no name, person skipped');
    else if (company) {
      const inCo = `clay.filter_to_companies((${q(domain)}))`;
      const rows = await claySearchRetrying(`select from people where full_name contains ${q(fullName)} and ${inCo}`, 1, retry429);
      person = rows[0] || null;
      const lastToken = (p.lastname || '').trim().split(/[\s-]+/).filter(Boolean).pop() || '';
      if (!person && lastToken) {
        const cands = await claySearchRetrying(`select from people where full_name contains ${q(lastToken)} and ${inCo}`, 25, retry429);
        const [hit, why] = pickPerson(cands, p.firstname, lastToken);
        person = hit;
        if (why) notes.push(why);
        if (!hit && !why) notes.push(`no Clay person "${fullName}" at ${domain}`);
      } else if (!person) notes.push(`no Clay person "${fullName}" at ${domain}`);
    }
    if (person) {
      const exp = (person.matched_experiences || [])[0] || {};
      Object.assign(out, { clay_job_title: clip(exp.title), clay_person_location: clip(person.location && person.location.name) });
    }
    out.clay_match_note = clip(notes.join('; ') || 'company and person matched', 500);

    const fit = fitScore(p, out, kind);
    out.inbound_fit_score = fit.score;
    out.inbound_fit_reasons = clip(`${fit.band}: ${fit.reasons}`, 500);
    if (!dry) await hs('PATCH', `/crm/v3/objects/contacts/${id}`, { properties: out });

    // Company record: the one already linked, else one with this domain, else create it. Link
    // it, then fill name/domain/description/LinkedIn only where blank.
    if (company && !dry) {
      let coId = c.associations?.companies?.results?.[0]?.id || null;
      if (!coId) {
        const found = await hs('POST', '/crm/v3/objects/companies/search', {
          filterGroups: [{ filters: [{ propertyName: 'domain', operator: 'EQ', value: domain }] }], properties: ['domain'], limit: 1 });
        coId = found.results?.[0]?.id || null;
        if (!coId) coId = (await hs('POST', '/crm/v3/objects/companies', { properties: { name: clip(company.name) || domain, domain } })).id;
        await hs('PUT', `/crm/v4/objects/contacts/${id}/associations/default/companies/${coId}`);
      }
      const cp = (await hs('GET', `/crm/v3/objects/companies/${coId}?properties=name,domain,description,linkedin_company_page`)).properties || {};
      const fill = {};
      if (!cp.name && company.name) fill.name = clip(company.name);
      if (!cp.domain) fill.domain = domain;
      if (!cp.description && company.description) fill.description = clip(company.description, 2000);
      if (!cp.linkedin_company_page && company.linkedin_url) fill.linkedin_company_page = clip(company.linkedin_url);
      if (Object.keys(fill).length) await hs('PATCH', `/crm/v3/objects/companies/${coId}`, { properties: fill });
    }

    const links = {
      linkedin: /linkedin\.com/.test(p.hs_linkedin_url || '') ? p.hs_linkedin_url : '',
      linkedinSearch: `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent([fullName, p.company || out.clay_company_name].filter(Boolean).join(' '))}`,
      posthog: POSTHOG && p.posthog_distinct_id ? `${POSTHOG}/person/${encodeURIComponent(p.posthog_distinct_id)}` : '',
    };
    const owner = await ownerName(p.hubspot_owner_id);
    let li = { added: false, why: 'dry run' };
    if (!dry) {
      try { li = await lemlistConnect(p, out, fit, links, kind); }
      catch (e) { li = { added: false, why: String(e).slice(0, 120) }; }
      if (li.added) { try { await hs('PATCH', `/crm/v3/objects/contacts/${id}`, { properties: { lemlist_campaign_id: process.env.LEMLIST_CAMPAIGN_ID } }); } catch (_) {} }
    }
    const text = card(kind, id, p, out, fit, links, owner, li);
    if (dry) return res.status(200).json({ ok: true, dry: true, contact: id, kind, fit, out, card: text });

    // One card per person: a booking within an hour of this person's form card rewrites that
    // card in place, plus a one-line thread reply so mentions still notify. Re-read the ping
    // fields now; the opening read is a Clay round-trip stale and the form run may have posted.
    let ping = { at: p.ping_posted_at, ts: p.ping_slack_ts, kind: p.ping_kind };
    if (kind === 'booking') {
      try { const f = (await hs('GET', `/crm/v3/objects/contacts/${id}?properties=ping_posted_at,ping_slack_ts,ping_kind`)).properties; ping = { at: f.ping_posted_at, ts: f.ping_slack_ts, kind: f.ping_kind }; } catch (_) {}
    }
    const recent = ping.at && (Date.now() - Date.parse(ping.at)) < 60 * 60 * 1000;
    const threadTs = kind === 'booking' && ping.kind === 'form' && recent && ping.ts ? ping.ts : '';
    let ts;
    if (threadTs) {
      ts = await slackUpdate(threadTs, text);
      try { await slackPost(`${atMentions()} ${esc(fullName)} also booked a demo. Card above updated.`.trim(), threadTs); } catch (_) {}
    } else ts = await slackPost(text, '');
    await hs('PATCH', `/crm/v3/objects/contacts/${id}`, { properties: { ping_posted_at: new Date().toISOString(), ping_slack_ts: threadTs || ts, ping_kind: kind } });
    return res.status(200).json({ ok: true, contact: id, kind, note: out.clay_match_note, fit: fit.score, slack_ts: ts });
  } catch (e) {
    console.log('inbound failed', id, String(e).slice(0, 300));
    try { await hs('PATCH', `/crm/v3/objects/contacts/${id}`, { properties: { clay_match_note: clip('receiver error: ' + e, 500), clay_enriched_at: out.clay_enriched_at } }); } catch (_) {}
    // Never let an inbound go unannounced: a bare card, stamped so the workflow fallback does
    // not post a second one.
    if (!dry && !/^Error: slack/.test(String(e))) {
      try {
        const name = [p.firstname, p.lastname].filter(Boolean).join(' ').trim() || p.email || `contact ${id}`;
        const text = [atMentions(), `${kind === 'booking' ? ':calendar: New booking' : ':inbox_tray: New inbound'}: *${esc(name)}*, ${esc(p.jobtitle || '')} at ${esc(p.company || p.hs_email_domain || '')} · ${link(RECORD(id), 'HubSpot')}`,
          `Enrichment failed (${esc(String(e).slice(0, 160))}). The record has what the form sent.`].filter(Boolean).join('\n');
        const ts = await slackPost(text, '');
        await hs('PATCH', `/crm/v3/objects/contacts/${id}`, { properties: { ping_posted_at: new Date().toISOString(), ping_slack_ts: ts, ping_kind: kind || 'form' } });
      } catch (_) {}
    }
    return res.status(200).json({ ok: false, error: String(e).slice(0, 200) });
  }
};
