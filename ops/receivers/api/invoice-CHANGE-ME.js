// Invoice receiver: Closed Won -> a DRAFT HubSpot invoice built from the deal, and a task to send it.
//
// A HubSpot deal workflow ("deal stage is Closed Won") POSTs the deal here. Setup and the
// workflow: close/CLOSE.md, section 6. For each deal it:
//   1. reads the deal, its company, its contacts and its line items;
//   2. builds the invoice lines: a copy of each line item on the deal if it has any, otherwise
//      one line named for the deal at the deal amount. No figure is authored here: the deal's
//      lines came from the close documents, which came from commercial.md;
//   3. creates the invoice as a DRAFT, billed to the deal's contacts (a finance title first) and
//      company, associated to the deal, due INVOICE_NET_DAYS after today;
//   4. writes the invoice number into the deal's Next step and creates a task on the deal owner
//      to check, finalise and send it.
// It never finalises or sends. A person does that from HubSpot.
//
// Idempotent: a deal that already has an invoice is left alone, unless that invoice is a draft
// with no line items (a previous run died halfway); then this run fills it.
//
// Env vars (Vercel project settings):
//   HUBSPOT_ACCESS_TOKEN  private app token. Scopes: crm.objects.invoices.write,
//                         crm.schemas.invoices.write, crm.objects.line_items.read/write,
//                         e-commerce, crm.objects.deals.read/write, crm.objects.contacts.read,
//                         crm.objects.companies.read. The Claude HubSpot connector refuses
//                         invoice writes, which is why this route exists.
//   HUBSPOT_PORTAL_ID     your portal id (for the link in the task)
//   CLOSED_WON_STAGE      optional, your Closed Won stage id (crm-records stage table); deals in
//                         any other stage are skipped, so a mis-built workflow cannot bill early
//   INVOICE_NET_DAYS      optional, days until due (default 30). Match commercial.md §4
//   INVOICE_CURRENCY      optional (default USD)
//   INVOICE_COMMENTS      optional, text printed on every invoice (e.g. "Per the Order Form.")
//
// Rename this file with a random suffix (openssl rand -hex 12). The unguessable path is the
// shared secret between HubSpot and this function.
// ?dry=1 reads everything and returns the invoice it would create; nothing is written.
// Always answers 200: a non-200 makes HubSpot redeliver on a backoff.

const HS = 'https://api.hubapi.com';
const PORTAL = process.env.HUBSPOT_PORTAL_ID || '';
// HubSpot-defined association type ids (public constants, the same in every portal)
const INVOICE_TO = { contacts: 177, companies: 179, deals: 175 };
const LINE_ITEM_TO_INVOICE = 410;
const TASK_TO_DEAL = 216;
const FINANCE = /cfo|financ|controller|account|payable|procure/i;

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

const assoc = (id, typeId) => ({ to: { id: String(id) }, types: [{ associationCategory: 'HUBSPOT_DEFINED', associationTypeId: typeId }] });

function dealId(body) {
  return body.objectId || body.hs_object_id
    || (body.properties && (body.properties.hs_object_id?.value || body.properties.hs_object_id))
    || (body.object && body.object.objectId) || null;
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).send('POST only');
  const dry = req.query && (req.query.dry === '1' || req.query.dry === 'true');
  let body;
  try { body = await readJson(req); } catch (e) { return res.status(200).json({ ok: false, reason: 'bad json' }); }
  const id = dealId(body);
  if (!id) return res.status(200).json({ ok: false, reason: 'no deal id in the payload' });

  try {
    const props = 'dealname,amount,dealstage,hubspot_owner_id';
    const deal = await hs('GET', `/crm/v3/objects/deals/${id}?properties=${props}&associations=companies,contacts,line_items`);
    const p = deal.properties;
    const stage = process.env.CLOSED_WON_STAGE;
    if (stage && p.dealstage !== stage) return res.status(200).json({ ok: false, reason: `deal stage ${p.dealstage} is not Closed Won` });

    // idempotency
    const existing = await hs('GET', `/crm/v4/objects/deals/${id}/associations/invoices`);
    let resumeId = null;
    for (const r of existing.results || []) {
      const inv = await hs('GET', `/crm/v3/objects/invoices/${r.toObjectId}?properties=hs_invoice_status`);
      const items = await hs('GET', `/crm/v4/objects/invoices/${r.toObjectId}/associations/line_items`);
      if (inv.properties.hs_invoice_status === 'draft' && !(items.results || []).length) { resumeId = r.toObjectId; continue; }
      return res.status(200).json({ ok: true, reason: 'deal already has an invoice', invoiceId: r.toObjectId });
    }

    // lines: copy the deal's line items, else one line at the deal amount
    const lines = [];
    for (const li of deal.associations?.line_items?.results || []) {
      const l = await hs('GET', `/crm/v3/objects/line_items/${li.id}?properties=name,quantity,price,description`);
      lines.push({ name: l.properties.name, quantity: l.properties.quantity || '1', price: l.properties.price, description: l.properties.description || '' });
    }
    if (!lines.length) {
      if (!p.amount || Number(p.amount) <= 0) return res.status(200).json({ ok: false, reason: 'deal has no line items and no amount' });
      lines.push({ name: p.dealname, quantity: '1', price: Number(p.amount).toFixed(2), description: '' });
    }

    const companies = [...new Set((deal.associations?.companies?.results || []).map(a => a.id))];
    const contacts = [];
    for (const cid of new Set((deal.associations?.contacts?.results || []).map(a => a.id))) {
      const c = await hs('GET', `/crm/v3/objects/contacts/${cid}?properties=email,firstname,lastname,jobtitle`);
      if (c.properties.email) contacts.push({ id: cid, ...c.properties });
    }
    if (!contacts.length) return res.status(200).json({ ok: false, reason: 'no contact with an email on the deal' });
    contacts.sort((a, b) => (FINANCE.test(b.jobtitle || '') ? 1 : 0) - (FINANCE.test(a.jobtitle || '') ? 1 : 0));
    const billing = contacts[0];

    const today = new Date().toISOString().slice(0, 10);
    const due = new Date(Date.now() + Number(process.env.INVOICE_NET_DAYS || 30) * 86400000).toISOString().slice(0, 10);
    const invoiceBody = {
      properties: {
        hs_currency: process.env.INVOICE_CURRENCY || 'USD', hs_invoice_date: today, hs_due_date: due,
        hs_comments: process.env.INVOICE_COMMENTS || '',
      },
      associations: [
        ...companies.map(c => assoc(c, INVOICE_TO.companies)),
        assoc(id, INVOICE_TO.deals),
        ...contacts.map(c => assoc(c.id, INVOICE_TO.contacts)),
      ],
    };
    if (dry) return res.status(200).json({ ok: true, dry: true, resumeId, invoice: invoiceBody, lines, billing: billing.email });

    const invoice = resumeId ? { id: String(resumeId) } : await hs('POST', '/crm/v3/objects/invoices', invoiceBody);
    for (const l of lines) {
      await hs('POST', '/crm/v3/objects/line_items', { properties: l, associations: [assoc(invoice.id, LINE_ITEM_TO_INVOICE)] });
    }
    const inv = await hs('GET', `/crm/v3/objects/invoices/${invoice.id}?properties=hs_number,hs_invoice_status,hs_amount_billed`);
    const number = inv.properties.hs_number || `invoice ${invoice.id}`;
    const link = PORTAL ? `https://app.hubspot.com/contacts/${PORTAL}/objects/0-53/views/all/list?invoiceId=${invoice.id}` : '';
    const who = `${billing.firstname || ''} ${billing.lastname || ''}`.trim() || billing.email;

    await hs('PATCH', `/crm/v3/objects/deals/${id}`, {
      properties: { hs_next_step: `${number} drafted, billed to ${who}, due ${due}. Check it, finalise it and send it from HubSpot. ${link}`.trim() },
    });
    const taskDue = new Date(); taskDue.setUTCHours(17, 0, 0, 0); taskDue.setUTCDate(taskDue.getUTCDate() + 1);
    await hs('POST', '/crm/v3/objects/tasks', {
      properties: {
        hs_task_subject: `Finalise and send ${number} to ${who} (${p.dealname})`,
        hs_task_body: `Draft invoice made on Closed Won from the deal's ${deal.associations?.line_items?.results?.length ? 'line items' : 'amount'}. Open ${link || 'it in HubSpot'}, check the lines against the signed Order Form and the billing address, then finalise and send.`,
        hs_task_status: 'NOT_STARTED', hs_task_priority: 'HIGH', hs_task_type: 'TODO',
        hs_timestamp: taskDue.toISOString(), hubspot_owner_id: p.hubspot_owner_id || '',
      },
      associations: [assoc(id, TASK_TO_DEAL)],
    });
    console.log(`deal ${id} -> ${number}, ${lines.length} line(s), billing ${billing.email}`);
    return res.status(200).json({ ok: true, invoiceId: invoice.id, number, billing: billing.email, resumed: !!resumeId });
  } catch (e) {
    console.error('invoice failed', String(e));
    return res.status(200).json({ ok: false, reason: String(e).slice(0, 300) });
  }
}
