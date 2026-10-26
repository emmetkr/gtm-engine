// Scheduler webhook -> hidden CRM form, so booking UTMs reach the contact record.
// Holds no secrets: the CRM forms submit endpoint is public; this file's path is the secret.
const PORTAL_ID = "YOUR_PORTAL_ID";
const FORM_ID = "YOUR_HIDDEN_FORM_ID";

export default async function handler(req, res) {
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
  };
  if (!fields.email) return res.status(200).json({ skipped: "no email" });
  const r = await fetch(`https://api.hsforms.com/submissions/v3/integration/submit/${PORTAL_ID}/${FORM_ID}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields: Object.entries(fields).map(([name, value]) => ({ name, value })) }),
  });
  return res.status(200).json({ crm: r.status });
}
