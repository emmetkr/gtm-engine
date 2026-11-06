// Signature receiver: DocuSign envelope completed -> the deal moves to Closed Won.
//
// DocuSign Connect POSTs here when every signer has signed. This function finds the deal the
// envelope belongs to and moves it to Closed Won, which is what fires the Closed Won -> draft
// invoice workflow. Setup: close/CLOSE.md, setup step 7. A completed envelope is the buyer's own
// signature, so this is the one stage move that happens with no person in it
// (docs/non-negotiables.md, section 5). Nothing else is decided here.
//
// Finding the deal, in order:
//   1. an envelope custom field named hubspot_deal_id (close/docusign-draft.py sets it);
//   2. the signers' emails -> CRM contacts -> their deals in DEALS_PIPELINE at an OPEN_STAGES
//      stage. Exactly one match moves. Zero or several are logged and left alone, so a wrong
//      deal is never closed by accident.
// Either way the deal must be in DEALS_PIPELINE at an OPEN_STAGES stage, or nothing moves.
//
// Only a completed envelope does anything. Declined, voided and sent events are acknowledged and
// ignored. A deal already in Closed Won is left alone, so a redelivery is harmless. The envelope
// id and the signers are appended to the deal's description.
//
// Env vars (Vercel project settings):
//   HUBSPOT_ACCESS_TOKEN  private app token (close/CLOSE.md, setup step 5)
//   DEALS_PIPELINE        your pipeline id (crm-records)
//   CLOSED_WON_STAGE      your Closed Won stage id (crm-records stage table)
//   OPEN_STAGES           comma-separated stage ids a deal may be signed from, usually your
//                         proposal and verbal-commitment stages
//   OWN_DOMAINS           comma-separated email domains of your own signers, e.g. example.com
//
// Rename this file with a random suffix (openssl rand -hex 12). The unguessable path is the
// shared secret between DocuSign and this function.
// ?dry=1 finds the deal and returns what it would do; nothing is written.
// A CRM failure answers 500 so Connect retries. Every other outcome answers 200.

const HS = 'https://api.hubapi.com';
const list = (v) => (v || '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);

async function readJson(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  let raw = '';
  for await (const chunk of req) raw += chunk;
  return raw ? JSON.parse(raw) : {};
}

async function hs(method, path, body) {
  const r = await fetch(HS + path, {
    method,
    headers: { Authorization: `Bearer ${process.env.HUBSPOT_ACCESS_TOKEN}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`hubspot ${method} ${path} ${r.status} ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : {};
}

function parseEnvelope(body) {
  // Connect v2 JSON: { event, data: { envelopeId, envelopeSummary: { status, emailSubject, recipients, customFields } } }
  const data = body.data || body;
  const summary = data.envelopeSummary || data;
  const signers = (summary.recipients?.signers || []).map((s) => ({ email: (s.email || '').toLowerCase(), name: s.name, status: s.status }));
  const custom = {};
  for (const f of summary.customFields?.textCustomFields || []) custom[f.name] = f.value;
  return {
    event: body.event || '', envelopeId: data.envelopeId || summary.envelopeId || '',
    status: (summary.status || '').toLowerCase(), subject: summary.emailSubject || '', signers, custom,
  };
}

async function dealFromSigners(env, pipeline, open) {
  const own = list(process.env.OWN_DOMAINS);
  const emails = env.signers.map((s) => s.email).filter((e) => e && !own.includes(e.split('@')[1]));
  if (!emails.length) return { reason: 'no customer signer email' };
  const found = await hs('POST', '/crm/v3/objects/contacts/search', {
    filterGroups: [{ filters: [{ propertyName: 'email', operator: 'IN', values: emails }] }], properties: ['email'], limit: 20,
  });
  const contactIds = (found.results || []).map((c) => c.id).slice(0, 5);   // the search API takes five filter groups
  if (!contactIds.length) return { reason: 'signers are not CRM contacts', emails };
  const deals = await hs('POST', '/crm/v3/objects/deals/search', {
    filterGroups: contactIds.map((cid) => ({
      filters: [
        { propertyName: 'pipeline', operator: 'EQ', value: pipeline },
        { propertyName: 'dealstage', operator: 'IN', values: open },
        { propertyName: 'associations.contact', operator: 'EQ', value: cid },
      ],
    })),
    properties: ['dealname', 'dealstage'], limit: 10,
  });
  const ids = [...new Set((deals.results || []).map((d) => d.id))];
  if (ids.length !== 1) return { reason: `${ids.length} candidate deals, not closing any`, dealIds: ids };
  return { dealId: ids[0] };
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).send('POST only');
  let body;
  try { body = await readJson(req); } catch (e) { return res.status(400).send('bad json'); }
  const env = parseEnvelope(body);
  if (env.event !== 'envelope-completed' && env.status !== 'completed') {
    return res.status(200).json({ ok: true, ignored: env.event || env.status || 'no event' });
  }
  const pipeline = process.env.DEALS_PIPELINE, closedWon = process.env.CLOSED_WON_STAGE;
  const open = (process.env.OPEN_STAGES || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (!pipeline || !closedWon || !open.length) {
    console.error('sign: DEALS_PIPELINE, CLOSED_WON_STAGE and OPEN_STAGES must all be set');
    return res.status(200).json({ ok: false, reason: 'receiver not configured', envelopeId: env.envelopeId });
  }
  const dry = (req.query && req.query.dry) || /[?&]dry=1/.test(req.url || '');
  try {
    let dealId = env.custom.hubspot_deal_id ? String(env.custom.hubspot_deal_id).trim() : null;
    let how = 'custom field';
    if (!dealId) {
      const m = await dealFromSigners(env, pipeline, open);
      if (!m.dealId) {
        console.log(`envelope ${env.envelopeId}: ${m.reason}`);
        return res.status(200).json({ ok: false, envelopeId: env.envelopeId, ...m });
      }
      dealId = m.dealId; how = 'signer email';
    }

    const deal = await hs('GET', `/crm/v3/objects/deals/${dealId}?properties=dealname,dealstage,pipeline,description`);
    const p = deal.properties;
    if (p.dealstage === closedWon) return res.status(200).json({ ok: true, reason: 'already Closed Won', dealId });
    if (p.pipeline !== pipeline || !open.includes(p.dealstage)) {
      console.log(`envelope ${env.envelopeId}: deal ${dealId} is at ${p.pipeline}/${p.dealstage}, not moved`);
      return res.status(200).json({ ok: false, reason: 'deal is not at a signable stage, not moved', dealId, stage: p.dealstage, envelopeId: env.envelopeId });
    }
    if (dry) return res.status(200).json({ ok: true, dry: true, dealId, dealname: p.dealname, matchedBy: how, wouldMoveTo: closedWon });
    const today = new Date().toISOString().slice(0, 10);
    const who = env.signers.filter((s) => s.status === 'completed' || !s.status).map((s) => `${s.name} <${s.email}>`).join(', ');
    const note = `\n\n[${today}, DocuSign] Envelope ${env.envelopeId} completed ("${env.subject}"). Signed: ${who}. Deal matched by ${how}; moved to Closed Won by the signature receiver.`;
    await hs('PATCH', `/crm/v3/objects/deals/${dealId}`, {
      properties: { dealstage: closedWon, closedate: `${today}T00:00:00Z`, description: (p.description || '') + note },
    });
    console.log(`envelope ${env.envelopeId} -> deal ${dealId} (${p.dealname}) Closed Won, matched by ${how}`);
    return res.status(200).json({ ok: true, dealId, dealname: p.dealname, matchedBy: how, envelopeId: env.envelopeId });
  } catch (e) {
    console.error('sign failed', String(e));
    return res.status(500).json({ ok: false, reason: String(e).slice(0, 300) });
  }
};
