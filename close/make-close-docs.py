#!/usr/bin/env python3
"""Build the close documents for one deal: Summary of Terms, Order Form, terms email, lines file.

    python3 close/make-close-docs.py clients/acme-corp/close/deal.json            # dry run
    python3 close/make-close-docs.py clients/acme-corp/close/deal.json --write
    python3 close/make-close-docs.py ... --write --order-form-base path/to/lawyer-order-form.docx
    python3 close/make-close-docs.py ... --write --preview     # order form with [[LAWYER]] gaps

Inputs, and the only places a figure may come from:
  deal.json          who, what offer, which add-ons, term, start date. NO FIGURES. A deal file
                     carrying a price, amount, fee, discount or total is refused.
  commercial.md      §1 Offers and §2 Add-ons tables (price and billing), §4 Terms (payment text).
  custom-offer.md    clients/<slug>/custom-offer.md, if it exists and is not lapsed. Its
                     "Variance from standard" table overrides a canon line for this client only.
                     Its Standard column must still match canon, or the build stops: a custom
                     deal described against a price you no longer charge is stale.
  seller.json        close/templates/seller.json: your company, signer, signature block.

Outputs, into clients/<slug>/close/:
  <date>-<slug>-summary-of-terms.docx / .pdf
  <date>-<slug>-order-form.docx / .pdf
  <date>-<slug>-email.txt / .html      body and htmlBody for the Gmail draft (signature included)
  <date>-<slug>-lines.json             the priced lines, read by close/hubspot-create-invoice.py

Guards (each one exists because the failure happened):
  - any "DRAFT" text anywhere in a document, headers and footers included, stops the build.
    A base document once carried a "[DRAFT]" run in its first-page header, invisible on the
    page, and it went to a client.
  - an unfilled {{placeholder}} stops the build.
  - a [[LAWYER: ...]] placeholder stops the order form unless --preview.
  - an output path listed in clients/<slug>/record.md (already sent) is never overwritten.
  - banned terms from ops/checks.json and em dashes are reported before anything is written.

Needs: pip install python-docx. PDF: LibreOffice (soffice) for a faithful render; otherwise
reportlab for a text-only render (a warning says so); otherwise no PDF and a warning.
"""
import argparse
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANON = ROOT / ".claude/skills/sales-playbook/references/commercial.md"
TEMPLATES = ROOT / "close/templates"
CHECKS = ROOT / "ops/checks.json"

FIGURE_KEYS = re.compile(r"price|amount|fee|cost|total|discount|rate", re.I)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
LAWYER = re.compile(r"\[\[LAWYER:[^\]]*\]\]")
DRAFT = re.compile(r"\bDRAFT\b|\[(?i:draft)\]")
PER_WORD = {"month": "per month", "quarter": "per quarter", "year": "per year", "one-time": "one time"}
COMMENT = re.compile(r"<!--.*?-->", re.S)


def die(msg):
    sys.exit(f"STOP: {msg}")


# ---------- reading canon ----------

def section(text, n):
    m = re.search(rf"^##\s*§{n}\b[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def md_table(block):
    rows = [l.strip() for l in block.splitlines() if l.strip().startswith("|")]
    rows = [r for r in rows if not re.fullmatch(r"\|[\s\-:|]+\|?", r)]
    if not rows:
        return []
    split = lambda r: [c.strip() for c in r.strip("|").split("|")]
    head = [h.lower() for h in split(rows[0])]
    return [dict(zip(head, split(r))) for r in rows[1:]]


def money(cell):
    """The number in a price cell, or None. '$X/mo' style placeholders give None."""
    m = NUMBER.search(cell or "")
    if not m:
        return None
    if re.match(r"\s?[kKmMbB]\b", (cell or "")[m.end():]):
        die(f"price cell {cell!r} uses a shorthand magnitude. Write the full number")
    return float(m.group(0).replace(",", ""))


def period(billing, default=None):
    """The billing period a cell names. The price in the same row is the price for that period.

    Stops rather than guesses: a wrong period prints a wrong contract total on an order form.
    """
    raw = billing or ""
    b = raw.lower()
    # Phrases that mention a period without being one: "two months free", "12-month term".
    b = re.sub(r"\b[\w-]+[ -]months?\s+free\b", " ", b)
    b = re.sub(r"\b\d+[ -](?:months?|years?)\b(?:\s+(?:term|contract|minimum|commitment))?", " ", b)
    found = [name for name, rx in (("quarter", r"\bquarter(?:ly|s)?\b"),
                                   ("year", r"\b(?:annual|annually|yearly|years?|yr)\b"),
                                   ("month", r"\b(?:monthly|months?|mo)\b")) if re.search(rx, b)]
    if len(found) > 1:
        die(f"billing {raw!r} names more than one period. Give each billing variant its own row, "
            f"priced for that period (for example 'per quarter' at the quarterly price)")
    if found:
        return found[0]
    if re.search(r"\b(?:one[- ]time|once|each|flat|free|trial|per [a-z]+)\b", b):
        return "one-time"
    if default:
        return default
    die(f"billing {raw!r} names no period. Say per month, per quarter, per year or one time")


def load_canon():
    if not CANON.exists():
        die(f"{CANON.relative_to(ROOT)} not found")
    text = CANON.read_text()
    offers = {r.get("offer", "").lower(): r for r in md_table(section(text, 1)) if r.get("offer")}
    addons = {r.get("item", "").lower(): r for r in md_table(section(text, 2)) if r.get("item")}
    raw = [l.strip() for l in COMMENT.sub("", section(text, 4)).splitlines()
           if l.strip() and not l.strip().startswith(("|", "#"))]
    bullets = any(l.startswith(("-", "*")) for l in raw)
    terms = ("; " if bullets else " ").join(l.lstrip("-* ").strip() for l in raw)
    return offers, addons, terms


def load_custom(slug):
    p = ROOT / "clients" / slug / "custom-offer.md"
    if not p.exists():
        return None, {}
    text = p.read_text()
    status = re.search(r"\*\*Status:\*\*\s*(.+)", text)
    status = status.group(1).strip() if status else ""
    if status.startswith("<proposed"):
        return None, {}   # the blank template, copied with the folder: this deal is standard
    if "<" in status or not status:
        die(f"{p.relative_to(ROOT)} has no Status line filled in; fill it or delete the file")
    if "lapsed" in status.lower():
        die(f"{p.relative_to(ROOT)} is lapsed; this deal is on standard terms or needs a new offer")
    if not re.search(r"\*\*Approved by:\*\*\s*[^<\s]", text):
        die(f"{p.relative_to(ROOT)} has no approver; a custom figure needs a named person")
    m = re.search(r"^#+\s*Variance from standard\s*$(.*?)(?=^#|\Z)", text, re.M | re.S | re.I)
    rows = md_table(m.group(1)) if m else []
    return p, {r.get("line", "").lower(): r for r in rows if r.get("line")}


# ---------- deal file ----------

def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def check_deal(deal, cur):
    for path, v in walk(deal):
        leaf = re.split(r"[.\[]", path)[-1]
        if path.startswith("_") or leaf.startswith("_"):
            continue
        if FIGURE_KEYS.search(leaf) and leaf != "quantity":
            die(f"deal file has a figure field '{path}'. Figures come from commercial.md or "
                f"custom-offer.md only; delete it")
        if isinstance(v, str) and re.search(re.escape(cur) + r"\s?\d", v):
            die(f"deal file has a typed figure in '{path}': {v!r}. Cite the line, not the price")
    for k in ("client", "contact", "offer", "term_months", "start_date"):
        if not deal.get(k):
            die(f"deal file is missing '{k}'")
    if not re.fullmatch(r"[a-z0-9-]+", deal["client"].get("slug", "")):
        die("client.slug must be lowercase letters, digits and hyphens")


# ---------- pricing ----------

def price_line(name, quantity, canon_row, custom, kind, cur, term_months):
    key = name.lower()
    src = "commercial.md"
    billing = (canon_row or {}).get("billing") or (canon_row or {}).get("unit") or ""
    unit_price = money((canon_row or {}).get("price"))
    detail = (canon_row or {}).get("includes") or (canon_row or {}).get("unit") or ""
    if key in custom:
        row = custom[key]
        std = money(row.get("standard"))
        if canon_row is not None and std != unit_price:
            die(f"custom offer line '{name}' says standard is {row.get('standard')!r} but "
                f"commercial.md now says {canon_row.get('price')!r}. The custom offer is measured "
                f"against a baseline that no longer exists; have the approver restate it")
        unit_price = money(row.get("this deal"))
        if canon_row is None:
            billing = row.get("this deal", "")
        src = "custom-offer.md"
    if canon_row is None and key not in custom:
        die(f"'{name}' is not in commercial.md ({kind} table) or in this client's custom offer")
    if unit_price is None:
        die(f"'{name}' has no number in its price cell ({src}). Fill commercial.md first")
    per = period(billing, default=None if canon_row is not None else "one-time")
    if per == "month":
        term_total = unit_price * quantity * term_months
    elif per == "quarter":
        term_total = unit_price * quantity * term_months / 3
    elif per == "year":
        term_total = unit_price * quantity * term_months / 12
    else:
        term_total = unit_price * quantity
    return {"name": name, "kind": kind, "quantity": quantity, "unit_price": unit_price,
            "period": per, "term_total": round(term_total, 2), "detail": detail, "source": src}


def fmt(cur, x):
    return f"{cur}{x:,.2f}".replace(".00", "")


def terms_rows(lines, cur, deal, payment_terms):
    per_word = PER_WORD
    rows = ["| Item | Terms | Details |", "|---|---|---|"]
    for l in lines:
        qty = f" x {l['quantity']}" if l["quantity"] != 1 else ""
        rows.append(f"| {l['name']}{qty} | {fmt(cur, l['unit_price'])}{' each' if qty else ''} {per_word[l['period']]} | {l['detail']} |")
    total = sum(l["term_total"] for l in lines)
    months = f"{deal['term_months']} month{'s' if deal['term_months'] != 1 else ''}"
    rows.append(f"| Term | {months} | Starting {long_date(deal['start_date'])} |")
    rows.append(f"| Total over the term | {fmt(cur, total)} | The lines above across {months} |")
    if payment_terms:
        rows.append(f"| Payment | {payment_terms} | |")
    return "\n".join(rows), total


# ---------- filling ----------

def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def lookup(ctx, dotted):
    v = ctx
    for part in dotted.split("."):
        if not isinstance(v, dict) or part not in v:
            return None
        v = v[part]
    return v


def fill(template, ctx):
    missing = []

    def sub(m):
        v = lookup(ctx, m.group(1))
        if v is None or (isinstance(v, str) and "CHANGE ME" in v):
            missing.append(m.group(1))
            return m.group(0)
        return str(v)

    out = PLACEHOLDER.sub(sub, COMMENT.sub("", template)).strip() + "\n"
    if missing:
        die(f"unfilled fields: {', '.join(sorted(set(missing)))} (deal.json or seller.json)")
    return out


def copy_findings(text, label):
    hits = []
    if CHECKS.exists():
        terms = {k: v for k, v in json.loads(CHECKS.read_text()).get("banned_terms", {}).items()
                 if not k.startswith("_")}
        for t, fix in terms.items():
            if re.search(rf"\b{re.escape(t)}\b", text, re.I):
                hits.append(f"{label}: banned term '{t}' -> {fix}")
    if "—" in text:
        hits.append(f"{label}: em dash in client copy")
    return hits


# ---------- markdown -> docx ----------

INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*]+\*)")


def docx_from_md(md, out):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    def shade(cell, hexc):
        s = OxmlElement("w:shd")
        s.set(qn("w:val"), "clear")
        s.set(qn("w:fill"), hexc)
        cell._tc.get_or_add_tcPr().append(s)

    def inline(par, text, size=10, bold=False, color=None):
        for chunk in INLINE.split(text):
            if not chunk:
                continue
            r = par.add_run()
            if chunk.startswith("**") and chunk.endswith("**"):
                r.text, r.bold = chunk[2:-2], True
            elif chunk.startswith("*") and chunk.endswith("*") and len(chunk) > 2:
                r.text, r.italic = chunk[1:-1], True
            else:
                r.text = chunk
                r.bold = bold or None
            r.font.size = Pt(size)
            if color:
                r.font.color.rgb = color

    doc = Document()
    s = doc.sections[0]
    s.top_margin = s.bottom_margin = Inches(0.8)
    s.left_margin = s.right_margin = Inches(0.9)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|[\s\-:|]+\|?", lines[i + 1].strip()):
            split = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            head = split(ln)
            i += 2
            body = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append(split(lines[i]))
                i += 1
            t = doc.add_table(rows=0, cols=len(head))
            t.style = "Table Grid"
            def pad(par):
                par.paragraph_format.space_before = Pt(3)
                par.paragraph_format.space_after = Pt(3)
                return par

            cells = t.add_row().cells
            for c, h in zip(cells, head):
                shade(c, "262626")
                inline(pad(c.paragraphs[0]), h, 9, True, RGBColor(0xFF, 0xFF, 0xFF))
            for row in body:
                row += [""] * (len(head) - len(row))
                for c, v in zip(t.add_row().cells, row):
                    inline(pad(c.paragraphs[0]), v, 9)
            doc.add_paragraph()
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10 if len(m.group(1)) > 1 else 2)
            inline(p, m.group(2), {1: 16, 2: 12, 3: 11}[len(m.group(1))], True)
        elif ln.strip() == "---":
            p = doc.add_paragraph()
            b = OxmlElement("w:pBdr")
            bot = OxmlElement("w:bottom")
            for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "BFBFBF")):
                bot.set(qn(k), v)
            b.append(bot)
            p._p.get_or_add_pPr().append(b)
        elif re.match(r"^\s*[-*]\s+", ln):
            inline(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*]\s+", "", ln))
        elif ln.strip():
            small = ln.startswith("*") and not ln.startswith("**")
            p = doc.add_paragraph()
            inline(p, ln, 8 if small else 10, color=RGBColor(0x55, 0x55, 0x55) if small else None)
            if small:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        i += 1
    doc.save(out)


def fill_lawyer_docx(base, ctx, out):
    """Fill {{placeholders}} in a lawyer's Order Form. Only paragraphs holding a placeholder
    change; the assert at the end proves every other paragraph is identical to the base."""
    from docx import Document

    doc = Document(str(base))

    def paragraphs(d):
        for p in d.paragraphs:
            yield p
        for t in d.tables:
            for row in t.rows:
                for cell in row.cells:
                    yield from cell.paragraphs
        for s in d.sections:
            for part in (s.header, s.first_page_header, s.even_page_header,
                         s.footer, s.first_page_footer, s.even_page_footer):
                yield from part.paragraphs
                for t in part.tables:
                    for row in t.rows:
                        for cell in row.cells:
                            yield from cell.paragraphs

    before = [p.text for p in paragraphs(Document(str(base)))]
    for p in paragraphs(doc):
        if not PLACEHOLDER.search(p.text) or not p.runs:
            continue
        runs = p.runs
        parts = fill(p.text, ctx).rstrip("\n").split("\n")
        # keep the first run's formatting, put the filled text in it, drop the rest
        runs[0].text = parts[0]
        for extra in parts[1:]:
            runs[0].add_break()
            runs[0].add_text(extra)
        for r in runs[1:]:
            r._element.getparent().remove(r._element)
    after = [p.text for p in paragraphs(doc)]
    if len(before) != len(after) or any(b != o for b, o in zip(before, after)
                                        if not PLACEHOLDER.search(b)):
        die("a paragraph outside the placeholders changed in the lawyer's document; nothing saved")
    doc.save(out)


def docx_text(path):
    from docx import Document

    d = Document(str(path))
    texts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            texts += [c.text for c in row.cells]
    for s in d.sections:
        for part in (s.header, s.first_page_header, s.even_page_header,
                     s.footer, s.first_page_footer, s.even_page_footer):
            texts += [p.text for p in part.paragraphs]
            for t in part.tables:
                for row in t.rows:
                    texts += [c.text for c in row.cells]
    texts.append(d.core_properties.title or "")
    texts.append(d.core_properties.subject or "")
    return "\n".join(texts)


def guard_docx(path):
    text = docx_text(path)
    if DRAFT.search(text):
        path.unlink()
        die(f"'DRAFT' appears in {path.name} (check headers and footers, which do not show in "
            f"the body). Remove it from the template or base document; this file was not saved")
    if PLACEHOLDER.search(text):
        path.unlink()
        die(f"unfilled placeholder left in {path.name}; this file was not saved")


def make_pdf(docx_path):
    pdf = docx_path.with_suffix(".pdf")
    if shutil.which("soffice"):
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir",
                        str(docx_path.parent), str(docx_path)], check=True, capture_output=True)
        if pdf.exists():
            return pdf, "LibreOffice"
    try:
        from docx import Document
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
        from xml.sax.saxutils import escape
    except ImportError:
        print(f"  WARNING: no LibreOffice and no reportlab; no PDF for {docx_path.name}. "
              f"Install LibreOffice and re-run before sending")
        return None, None
    st = getSampleStyleSheet()["BodyText"]
    d = Document(str(docx_path))
    flow = [Paragraph(escape(p.text), st) if p.text.strip() else Spacer(1, 6) for p in d.paragraphs]
    for t in d.tables:
        flow.append(Table([[Paragraph(escape(c.text), st) for c in row.cells] for row in t.rows]))
    SimpleDocTemplate(str(pdf), pagesize=LETTER).build(flow)
    print(f"  WARNING: {pdf.name} was rendered without LibreOffice: every word, not the layout "
          f"(tables follow the body text). Install LibreOffice for a faithful PDF before sending")
    return pdf, "reportlab"


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("deal", type=pathlib.Path)
    ap.add_argument("--write", action="store_true", help="write the files (default is a dry run)")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--order-form-base", type=pathlib.Path,
                    help="your lawyer's Order Form .docx with {{placeholders}} in its order table")
    ap.add_argument("--preview", action="store_true",
                    help="build the order form despite [[LAWYER]] gaps, into close/preview/ (never sent)")
    ap.add_argument("--skip-order-form", action="store_true")
    a = ap.parse_args()

    if a.order_form_base and not a.order_form_base.exists():
        die(f"{a.order_form_base} not found. Save your lawyer's Word form there, or use --preview or --skip-order-form")
    seller = json.loads((TEMPLATES / "seller.json").read_text())
    unfilled = [p for p, v in walk(seller) if isinstance(v, str) and "CHANGE ME" in v and not p.startswith("_")]
    if unfilled:
        die(f"close/templates/seller.json still says CHANGE ME in: {', '.join(unfilled)}")
    cur = seller.get("currency_symbol") or "$"
    deal = json.loads(a.deal.read_text())
    check_deal(deal, cur)
    slug = deal["client"]["slug"]
    offers, addons, payment_terms = load_canon()
    custom_path, custom = load_custom(slug)
    if "payment terms" in custom:
        payment_terms = custom["payment terms"].get("this deal", payment_terms)
    if payment_terms.lower().startswith("payment terms, contract length"):
        payment_terms = ""  # commercial.md §4 still holds the template prompt
    if not payment_terms:
        print("  NOTE: commercial.md §4 has no payment terms yet; the Payment row is left out")

    term = int(deal["term_months"])
    lines = [price_line(deal["offer"], 1, offers.get(deal["offer"].lower()), custom, "offer", cur, term)]
    for ad in deal.get("addons", []):
        lines.append(price_line(ad["item"], int(ad.get("quantity", 1)), addons.get(ad["item"].lower()),
                                custom, "add-on", cur, term))
    used = {l["name"].lower() for l in lines} | {"payment terms"}
    for k in custom:
        if k not in used:
            print(f"  NOTE: custom offer line '{k}' is not on this deal and was not used")

    table, total = terms_rows(lines, cur, deal, payment_terms)
    contact = dict(deal["contact"])
    contact.setdefault("first_name", contact.get("name", "").split(" ")[0])
    ctx = {"seller": seller, "client": deal["client"], "contact": contact,
           "signer": deal.get("signer") or contact, "term_months": term,
           "date_long": long_date(a.date), "start_date_long": long_date(deal["start_date"]),
           "terms_table": table, "fees_table": table, "term_total": fmt(cur, total),
           "fees_lines": "\n".join(f"{l['name']}{' x ' + str(l['quantity']) if l['quantity'] != 1 else ''}: "
                                   f"{fmt(cur, l['unit_price'])} {PER_WORD[l['period']]}" for l in lines), "payment_terms": payment_terms or "Per the Agreement."}

    summary_md = fill((TEMPLATES / "summary-of-terms.md").read_text(), ctx)
    email_raw = fill((TEMPLATES / "terms-email.md").read_text(), ctx)
    subject_m = re.match(r"Subject:\s*(.+)\n", email_raw)
    subject = subject_m.group(1).strip() if subject_m else ""
    email_body = email_raw[subject_m.end():].strip() if subject_m else email_raw.strip()
    if re.search(re.escape(cur) + r"\s?\d", email_body):
        die("the email template carries a figure; prices go in the attachment, never the body")

    order_md, order_is_preview = None, False
    if not a.skip_order_form and not a.order_form_base:
        order_md = fill((TEMPLATES / "order-form.md").read_text(), ctx)
        gaps = LAWYER.findall(order_md)
        if gaps:
            if not a.preview:
                print(f"  ORDER FORM NOT BUILT: {len(gaps)} [[LAWYER]] placeholder(s) in "
                      f"close/templates/order-form.md. Have your lawyer write them, or pass "
                      f"--order-form-base with their document. --preview builds an unsendable copy.")
                order_md = None
            else:
                order_is_preview = True

    findings = copy_findings(summary_md, "summary") + copy_findings(email_body, "email")
    if order_md:
        findings += copy_findings(order_md, "order form")

    print(f"deal: {deal['client']['legal_name']} ({slug}), offer {deal['offer']}, {term} months")
    print(f"custom offer: {custom_path.relative_to(ROOT) if custom_path else 'none (standard terms)'}")
    for l in lines:
        print(f"  {l['name']} x{l['quantity']}: {fmt(cur, l['unit_price'])} {PER_WORD[l['period']]}, "
              f"term {fmt(cur, l['term_total'])}  [{l['source']}]")
    print(f"  total over the term: {fmt(cur, total)}")
    for f in findings:
        print(f"  COPY: {f}")

    if not a.write:
        print("\n--- summary of terms ---\n" + summary_md)
        print(f"--- email ---\nSubject: {subject}\n\n{email_body}\n")
        print("dry run; add --write to build the files")
        return

    out_dir = ROOT / "clients" / slug / "close"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{a.date}-{slug}"
    record = ROOT / "clients" / slug / "record.md"
    sent = record.read_text() if record.exists() else ""

    def target(name, preview=False):
        d = out_dir / "preview" if preview else out_dir
        d.mkdir(exist_ok=True)
        p = d / f"{stem}-{name}"
        if p.stem in sent or f"{a.date}-SENT-{pathlib.Path(name).stem}" in sent:
            die(f"{p.name} is listed in {record.relative_to(ROOT)} as sent. It is in the client's "
                f"hands: build a reissue with a new --date, never overwrite")
        return p

    built = []
    p = target("summary-of-terms.docx")
    docx_from_md(summary_md, p)
    guard_docx(p)
    built.append(p)

    if a.order_form_base:
        p = target("order-form.docx")
        fill_lawyer_docx(a.order_form_base, ctx, p)
        guard_docx(p)
        built.append(p)
    elif order_md:
        p = target("order-form.docx", preview=order_is_preview)
        docx_from_md(order_md, p)
        guard_docx(p)
        built.append(p)

    for p in list(built):
        pdf, how = make_pdf(p)
        if pdf:
            built.append(pdf)

    txt = target("email.txt")
    txt.write_text(f"Subject: {subject}\n\n{email_body}\n\n{seller.get('signature_text', '')}\n")
    html_body = "".join(f"<p>{para.replace(chr(10), '<br>')}</p>" for para in email_body.split("\n\n"))
    html = target("email.html")
    html.write_text(f"<div style=\"font-family:Arial,sans-serif;font-size:14px\">{html_body}</div>"
                    f"{seller.get('signature_html', '')}\n")
    lj = target("lines.json")
    lj.write_text(json.dumps({"client": slug, "date": a.date, "term_months": term,
                              "start_date": deal["start_date"], "crm": deal.get("crm", {}),
                              "custom_offer": str(custom_path.relative_to(ROOT)) if custom_path else None,
                              "lines": lines, "term_total": round(total, 2)}, indent=1) + "\n")
    built += [txt, html, lj]
    print("\nbuilt:")
    for p in built:
        print(f"  {p.relative_to(ROOT)}")
    if order_is_preview:
        print("\n  The order form is a PREVIEW with lawyer gaps. Never attach it.")
    print("\nNext: read the PDF, then draft the email (close/CLOSE.md, Per deal, step 5). Nothing has been sent.")


if __name__ == "__main__":
    main()
