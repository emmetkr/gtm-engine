#!/usr/bin/env python3
"""Create a DRAFT HubSpot invoice with one or more line items. Never sends, never finalises.

    # from the lines file the close generator wrote (figures come from commercial.md):
    python3 close/hubspot-create-invoice.py --lines-file clients/acme-corp/close/2026-11-06-acme-corp-lines.json \
        --bill first-period --company <company id> --contact <contact id> --deal <deal id> \
        --invoice-date 2026-12-01 --net 30                                    # dry run
    ... --apply                                                               # create the draft

    # by hand, for a line the generator does not cover (a supplemental, a one-off):
    python3 close/hubspot-create-invoice.py --company <id> --contact <id> \
        --line "Item name|1|<unit price>|Description shown on the invoice" --line "..." \
        --invoice-date 2026-12-01 --due-date 2026-12-31

    python3 close/hubspot-create-invoice.py --probe     # does the token have invoice write scope?
    python3 close/hubspot-create-invoice.py --resume <invoice id> --line ...   # fill an empty draft

Why a token and not the Claude HubSpot connector: the connector lists invoices but refuses to
create them ("Managing invoices is not supported"), even after reauthorising with invoice
scopes. A private-app token works.

Token: HUBSPOT_ACCESS_TOKEN from the environment, or from a .env file at the repo root (it is
gitignored). Never printed. Scopes the private app needs:
  crm.objects.invoices.write, crm.schemas.invoices.write   the invoice
  crm.objects.line_items.write, e-commerce                 the line items (without these the
                                                           invoice is created and shows zero)
  crm.objects.deals.read, crm.objects.companies.read, crm.objects.contacts.read

Optional: HUBSPOT_PORTAL_ID, to print a link to the draft.

Draft only. A person opens the draft in HubSpot, checks it, finalises it and sends it.
"""
import argparse
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://api.hubapi.com"
# HubSpot-defined association type ids (public constants, the same in every portal)
INVOICE_TO = {"contacts": 177, "companies": 179, "deals": 175}
LINE_ITEM_TO_INVOICE = 410


def token():
    t = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if t:
        return t
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("HUBSPOT_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("no HUBSPOT_ACCESS_TOKEN in the environment or in .env at the repo root")


def api(method, path, tok, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            return e.code, {}


def assoc(obj_id, type_id):
    return {"to": {"id": str(obj_id)},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": type_id}]}


def lines_from_file(path, bill):
    """first-period: one month of each monthly line, one year of each yearly line, plus every
    one-time line. term: each line's total over the whole term."""
    data = json.loads(pathlib.Path(path).read_text())
    out = []
    for l in data["lines"]:
        if bill == "term":
            qty, price = 1, l["term_total"]
            desc = f"{l['name']}, {data['term_months']} months from {data['start_date']}"
        else:
            qty, price = l["quantity"], l["unit_price"]
            desc = {"month": "First month", "year": "First year", "one-time": "One time"}[l["period"]]
            desc = f"{l['name']}, {desc.lower()} from {data['start_date']}"
        out.append({"name": l["name"], "quantity": qty, "price": price, "description": desc})
    return out, data


def lines_from_args(specs):
    out = []
    for spec in specs:
        parts = spec.split("|", 3)
        if len(parts) < 3:
            sys.exit(f"--line needs NAME|QUANTITY|UNIT_PRICE[|DESCRIPTION]: {spec}")
        try:
            out.append({"name": parts[0], "quantity": int(parts[1]), "price": float(parts[2]),
                        "description": parts[3] if len(parts) > 3 else ""})
        except ValueError:
            sys.exit(f"--line quantity and unit price must be numbers: {spec}")
    return out


def attach_lines(inv, lines, tok):
    for l in lines:
        body = {"properties": {"name": l["name"], "quantity": str(l["quantity"]),
                               "price": f"{l['price']:.2f}", "description": l["description"]},
                "associations": [assoc(inv, LINE_ITEM_TO_INVOICE)]}
        s, r = api("POST", "/crm/v3/objects/line_items", tok, body)
        if s not in (200, 201):
            sys.exit(f"line item '{l['name']}' failed on draft invoice {inv}: {s} {r.get('message', '')}\n"
                     f"The draft exists and is short this line. Fix the scope (crm.objects.line_items.write, "
                     f"e-commerce) and re-run with --resume {inv} and only the missing lines.")
        print(f"  line item {r['id']}: {l['name']} x{l['quantity']} at {l['price']:.2f}")


def main():
    ap = argparse.ArgumentParser(description="Create a DRAFT HubSpot invoice. Dry run unless --apply.")
    ap.add_argument("--deal", help="optional: an invoice can sit on company + contact only")
    ap.add_argument("--company")
    ap.add_argument("--contact", action="append", default=[], help="repeatable; the first is the billing contact")
    ap.add_argument("--lines-file", help="the <date>-<slug>-lines.json from close/make-close-docs.py")
    ap.add_argument("--bill", choices=["first-period", "term"], default="first-period")
    ap.add_argument("--line", action="append", default=[], metavar="NAME|QTY|UNIT_PRICE|DESCRIPTION")
    ap.add_argument("--invoice-date", default=datetime.date.today().isoformat())
    ap.add_argument("--due-date")
    ap.add_argument("--net", type=int, help="days from invoice date to due date, instead of --due-date")
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--comments", default="", help="shown on the invoice")
    ap.add_argument("--payment-methods", default="", help="e.g. ach; empty leaves HubSpot's default")
    ap.add_argument("--allow-second", action="store_true",
                    help="the deal already has an invoice and this one is a supplemental, not a replacement")
    ap.add_argument("--resume", help="attach --line items to an existing empty draft instead of creating one")
    ap.add_argument("--probe", action="store_true", help="check invoice write scope (400 = yes, 403 = no); creates nothing")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    tok = token()

    if a.probe:
        s, r = api("POST", "/crm/v3/objects/invoices", tok, {"properties": {}})
        verdict = {400: "token CAN write invoices (empty body rejected as expected)",
                   403: "token CANNOT write invoices: add crm.objects.invoices.write to the private app"}
        print(s, verdict.get(s, r.get("message", "")[:200]))
        return

    lines, meta = [], None
    if a.lines_file:
        lines, meta = lines_from_file(a.lines_file, a.bill)
    if a.line:
        print("  NOTE: typed line figures. Confirm each against commercial.md or the client's custom-offer.md.")
        lines += lines_from_args(a.line)
    if not lines:
        sys.exit("no lines: pass --lines-file or at least one --line")
    total = round(sum(l["price"] * l["quantity"] for l in lines), 2)

    if a.resume:
        s, r = api("GET", f"/crm/v3/objects/invoices/{a.resume}?properties=hs_invoice_status,hs_number", tok)
        if s != 200:
            sys.exit(f"invoice {a.resume}: {s} {r.get('message')}")
        if r["properties"].get("hs_invoice_status") != "draft":
            sys.exit(f"invoice {a.resume} is {r['properties'].get('hs_invoice_status')}, not draft; leave it alone")
        print(json.dumps({"resume": a.resume, "line_items": lines, "total": total}, indent=1))
        if a.apply:
            attach_lines(a.resume, lines, tok)
        else:
            print("dry run; add --apply")
        return

    crm = (meta or {}).get("crm") or {}
    deal = a.deal or crm.get("deal_id") or None
    company = a.company or crm.get("company_id") or None
    contacts = a.contact or [str(c) for c in crm.get("contact_ids", [])]
    if not company or not contacts:
        sys.exit("--company and at least one --contact are required (or crm ids in the lines file)")
    due = a.due_date
    if not due and a.net is not None:
        due = (datetime.date.fromisoformat(a.invoice_date) + datetime.timedelta(days=a.net)).isoformat()
    if not due:
        sys.exit("--due-date or --net is required (read the payment terms in commercial.md §4 or the Order Form)")

    # the records exist, the deal has no invoice yet, and the amount agrees
    checks = [("companies", company)] + [("contacts", c) for c in contacts]
    if deal:
        checks.insert(0, ("deals", deal))
    for obj, i in checks:
        s, r = api("GET", f"/crm/v3/objects/{obj}/{i}?properties=dealname,amount,name,email", tok)
        if s != 200:
            sys.exit(f"{obj} {i}: {s} {r.get('message')}")
        p = r["properties"]
        print(f"  {obj} {i}: {p.get('dealname') or p.get('name') or p.get('email')}")
        if obj == "deals" and p.get("amount") and abs(float(p["amount"]) - total) > 0.005:
            print(f"  ! deal amount {p['amount']} differs from this invoice's total {total} "
                  f"(expected when billing one period of a longer term; check it otherwise)")
    if deal:
        s, r = api("GET", f"/crm/v4/objects/deals/{deal}/associations/invoices", tok)
        existing = [x["toObjectId"] for x in r.get("results", [])] if s == 200 else []
        if existing and not a.allow_second:
            sys.exit(f"deal {deal} already has invoice(s) {existing}. If this is a supplemental "
                     f"(an additional bill, not a replacement), re-run with --allow-second. If one is "
                     f"an empty draft from a failed run, use --resume.")

    props = {"hs_currency": a.currency, "hs_invoice_date": a.invoice_date, "hs_due_date": due,
             "hs_comments": a.comments}
    if a.payment_methods:
        props["hs_allowed_payment_methods"] = a.payment_methods
    associations = [assoc(company, INVOICE_TO["companies"])] + \
        [assoc(c, INVOICE_TO["contacts"]) for c in contacts]
    if deal:
        associations.append(assoc(deal, INVOICE_TO["deals"]))
    invoice = {"properties": props, "associations": associations}
    print(json.dumps({"invoice": invoice, "line_items": lines, "total": total}, indent=1))
    if not a.apply:
        print("dry run; add --apply to create the DRAFT invoice")
        return

    s, r = api("POST", "/crm/v3/objects/invoices", tok, invoice)
    if s not in (200, 201):
        sys.exit(f"invoice create failed: {s} {r.get('message', '')}")
    inv = r["id"]
    print(f"created draft invoice {inv}")
    attach_lines(inv, lines, tok)
    s, r = api("GET", f"/crm/v3/objects/invoices/{inv}?properties=hs_number,hs_invoice_status,hs_amount_billed,hs_due_date", tok)
    p = r.get("properties", {})
    print(json.dumps(p, indent=1))
    if p.get("hs_invoice_status") not in (None, "draft"):
        print(f"  ! status is {p.get('hs_invoice_status')}, expected draft. Check it in HubSpot now.")
    portal = os.environ.get("HUBSPOT_PORTAL_ID")
    if portal:
        print(f"https://app.hubspot.com/contacts/{portal}/objects/0-53/views/all/list?invoiceId={inv}")
    print("Draft only. A person finalises and sends it from HubSpot.")


if __name__ == "__main__":
    main()
