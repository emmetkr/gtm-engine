// Scheduler webhook -> hidden CRM form, so booking UTMs reach the contact record.
// Holds no secrets by default: the CRM forms submit endpoint is public; this file's path is the secret.
//
// CRM plan without the "send webhook" workflow action (ops/receivers/INBOUND.md §8)? Set INBOUND_URL
// (the inbound receiver's full URL) and HUBSPOT_ACCESS_TOKEN in Vercel, and this function hands the
// contact to the inbound receiver itself. The inbound receiver's duplicate guard makes it safe if a
// workflow also fires.
const PORTAL_ID = "YOUR_PORTAL_ID";
const FORM_ID = "YOUR_HIDDEN_FORM_ID";

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();
  const p = (req.body && req.body.payload) || {};
  const t = p.tracking || {};
  const answers = (p.questions_and_answers || []).map((q) => `${q.question}: ${q.answer}`).join("\n");
  const fields = {
    email: p.email,
    firstname: p.first_name || (p.name || "").split(" ")[0],
    lastname: p.last_name || (p.name || "").split(" ").slice(1).join(" "),
    booking_utm_source: t.utm_source || "(none: untagged link or direct)",
    booking_utm_medium: t.utm_medium || "",
    booking_utm_campaign: t.utm_campaign || "",
    booking_utm_content: t.utm_content || "",
    booking_event_type: (p.scheduled_event && p.scheduled_event.name) || "",
    booking_answers: answers,
    booking_start_time: (p.scheduled_event && p.scheduled_event.start_time) || "",
  };
  if (!fields.email) return res.status(200).json({ skipped: "no email" });
  const r = await fetch(`https://api.hsforms.com/submissions/v3/integration/submit/${PORTAL_ID}/${FORM_ID}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields: Object.entries(fields).map(([name, value]) => ({ name, value })) }),
  });
  let inbound = "off";
  if (r.ok && process.env.INBOUND_URL && process.env.HUBSPOT_ACCESS_TOKEN) {
    inbound = await handOff(fields.email).catch((e) => `failed: ${String(e).slice(0, 120)}`);
  }
  return res.status(200).json({ crm: r.status, inbound });
}

// The form write takes a few seconds to reach the contact, and search lags it, so look twice.
async function handOff(email) {
  for (let attempt = 0; attempt < 2; attempt++) {
    await new Promise((s) => setTimeout(s, 8000));
    const found = await fetch("https://api.hubapi.com/crm/v3/objects/contacts/search", {
      method: "POST",
      headers: { Authorization: `Bearer ${process.env.HUBSPOT_ACCESS_TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify({ filterGroups: [{ filters: [{ propertyName: "email", operator: "EQ", value: email }] }], limit: 1 }),
    }).then((x) => x.json());
    const id = found.results && found.results[0] && found.results[0].id;
    if (!id) continue;
    // The inbound run takes up to a minute. Start it and move on: the abort ends this wait, not
    // that function, so the scheduler gets its answer quickly.
    await fetch(`${process.env.INBOUND_URL}?kind=booking&id=${id}`, { method: "POST", signal: AbortSignal.timeout(5000) })
      .catch((e) => { if (e.name !== "TimeoutError") throw e; });
    return `started for ${id}`;
  }
  return "contact not found yet";
}
