# Close: Summary of Terms, Order Form, invoice

What it does, end to end. Agents draft every piece; a person approves and sends every piece.

```
deal is ready to close (a person says so, or it reaches your proposal stage)
  └─ Claude reads the deal from the CRM and writes clients/<slug>/close/deal.json
       (who, which offer, which add-ons, term, start date; never a figure)
  └─ close/make-close-docs.py
       ├─ prices every line from commercial.md, or from clients/<slug>/custom-offer.md
       ├─ Summary of Terms   .docx + .pdf   (one page, plain contract paperwork)
       ├─ Order Form         .docx + .pdf   (your lawyer's document, only the order table filled)
       ├─ terms email        .txt + .html   (short, one ask, signature built in, no prices)
       └─ lines file         .json          (the priced lines, for the invoice)
  └─ Gmail draft to the contact, PDF attached        ← a person reads it and sends it
  └─ sent copy filed in clients/<slug>/outreach/, row in record.md, git tag client/<slug>-<date>

deal signed, a person moves it to Closed Won
  └─ HubSpot workflow POSTs the deal to the invoice receiver
       └─ DRAFT invoice from the deal's line items (or amount), task on the owner
  or, by hand: close/hubspot-create-invoice.py --lines-file …
  └─ a person checks the draft against the signed Order Form, finalises it and sends it
```

Files:

| File | Job |
|---|---|
| `close/make-close-docs.py` | Deal file + canon → Summary of Terms, Order Form, email, lines file |
| `close/hubspot-create-invoice.py` | Draft HubSpot invoice from the lines file or typed lines. Token route |
| `ops/receivers/api/invoice-CHANGE-ME.js` | Closed Won → draft invoice + task on the owner |
| `close/templates/summary-of-terms.md` | The one-page terms sheet. Edit the words, keep the shape |
| `close/templates/order-form.md` | Starter Order Form for founders with no lawyer's form yet. Gaps marked `[[LAWYER: …]]` |
| `close/templates/terms-email.md` | The terms-send email. Replace with your own words from a real sent email |
| `close/templates/seller.json` | Your company, signer and email signature. `CHANGE ME` |
| `close/templates/deal.example.json` | The shape of a deal file |

Needs: `pip install python-docx`. For PDFs, LibreOffice (`brew install --cask libreoffice`, or
your OS package manager). Without it the script falls back to a text-only render through
`reportlab` and says so; read that PDF before you send it, because the layout is not the Word
layout.

Do the setup steps once, in order. Each ends with a check. Then run the per-deal steps for every
deal.

## Setup

### 1. Fill the commercial canon

`close/make-close-docs.py` reads three parts of
`.claude/skills/sales-playbook/references/commercial.md`, by heading:

| Section | Table columns it reads | Used for |
|---|---|---|
| `## §1 Offers` | Offer, Price, Billing, Includes | the main line. Billing containing "month" or "year" sets the period; anything else is one time |
| `## §2 Add-ons` | Item, Price, Unit | extra lines. Unit doubles as billing ("per seat per month") |
| `## §4 Terms` | prose or bullets | the Payment row and the Order Form's payment terms |

A Price cell must hold a number. A cell reading "custom" or left blank stops the build for that
line, by design: fill canon first, then quote.

**Check:** `python3 ops/check-corpus.py` reports no figures outside `commercial.md`, and every
offer you sell has a number in its Price cell.

### 2. Say who is selling

Fill every `CHANGE ME` in `close/templates/seller.json`: trading name, legal name, the product
name for the header line, the signer, and the email signature (text and HTML). The generator
stops on any field still reading `CHANGE ME`.

The signature lives here because a Gmail draft made through the Claude connector carries no
signature: Gmail adds yours only in its own compose window, so the draft goes out unsigned
unless the body already ends with it.

**Check:** copy `close/templates/deal.example.json` to a scratch path, change the offer to one
in your §1 table, and run `python3 close/make-close-docs.py <that file>`. The dry run prints the
priced lines and the filled Summary of Terms with no `STOP`.

### 3. The Order Form

Two routes. Use the first as soon as you have a lawyer's form.

**a. Your lawyer's Order Form (recommended).** Open their Word document. In the order table
only (customer, fees, term, signatures), replace the variable text with placeholders:

| Placeholder | Filled with |
|---|---|
| `{{client.legal_name}}`, `{{client.address}}` | from the deal file |
| `{{contact.name}}`, `{{contact.title}}`, `{{contact.email}}` | from the deal file |
| `{{signer.name}}`, `{{signer.title}}` | the client's signer (defaults to the contact) |
| `{{seller.legal_name}}`, `{{seller.signer_name}}`, `{{seller.signer_title}}` | from `seller.json` |
| `{{date_long}}`, `{{start_date_long}}`, `{{term_months}}` | dates and term |
| `{{fees_lines}}` | one line per priced item, from canon or the custom offer |
| `{{term_total}}` | the sum over the term |
| `{{payment_terms}}` | `commercial.md` §4, or the custom offer's "Payment terms" line |

Save it somewhere in the repo (for example `close/templates/order-form-base.docx`) and pass it
with `--order-form-base`. The script fills only paragraphs that hold a placeholder and then
checks that every other paragraph in the document is identical to the source. The terms and
conditions are your lawyer's words: the script never edits them, and neither should an agent.
A defect in them goes back to the lawyer to fix in their source.

**Before you save it, open the header and footer of every section** (in Word: double-click the
top margin of page 1, and check "Different first page"). A lawyer's working draft often carries
a "DRAFT" mark there that does not show in the body. The script stops on any "DRAFT" anywhere in
the output, headers and footers included.

**b. The starter template.** `close/templates/order-form.md` has the order table and three
clauses marked `[[LAWYER: …]]`: service description, term and renewal, governing agreement.
**Have your lawyer write those.** Until every marker is gone the script will not build a
sendable Order Form; `--preview` builds one into `clients/<slug>/close/preview/` for you to read,
and nothing in `preview/` is ever attached.

**Check:** run the generator with `--write` on the scratch deal file. With route a, the Order
Form PDF shows your lawyer's terms unchanged and the order table filled. With route b, it prints
`ORDER FORM NOT BUILT` until the lawyer's text is in.

### 4. Gmail

Connect the Gmail connector in Claude (Settings → Connectors). Agents create drafts only.

**Check:** ask Claude to create a test draft to yourself with the body and HTML body from the
scratch run's `…-email.txt` and `…-email.html`. Open it in Gmail: your signature is at the
bottom, and nothing has been sent.

### 5. HubSpot private app (invoices)

The Claude HubSpot connector can read invoices but refuses to create them ("Managing invoices is
not supported"), even with invoice scopes granted. Invoices go through a private-app token.

1. HubSpot → Settings → Integrations → Private apps → Create (or edit the one from
   `ops/receivers/INBOUND.md`).
2. Scopes: `crm.objects.invoices.write`, `crm.schemas.invoices.write`,
   `crm.objects.line_items.read`, `crm.objects.line_items.write`, `e-commerce`,
   `crm.objects.deals.read`, `crm.objects.deals.write`, `crm.objects.contacts.read`,
   `crm.objects.companies.read`.
3. Put the token in `.env` at the repo root as `HUBSPOT_ACCESS_TOKEN=…` (gitignored), and in the
   Vercel project if you use the receiver. Add `HUBSPOT_PORTAL_ID` to both for links.

**Check:** `python3 close/hubspot-create-invoice.py --probe` prints `400 token CAN write
invoices`. A `403` means the invoice scope is missing.

### 6. Closed Won → draft invoice (optional)

1. Rename `ops/receivers/api/invoice-CHANGE-ME.js` with a random suffix
   (`openssl rand -hex 12`).
2. In Vercel set `HUBSPOT_ACCESS_TOKEN`, `HUBSPOT_PORTAL_ID`, `CLOSED_WON_STAGE` (your Closed Won
   stage id from the `crm-records` stage table), `INVOICE_NET_DAYS` (match `commercial.md` §4),
   and optionally `INVOICE_CURRENCY` and `INVOICE_COMMENTS`. Deploy from `ops/receivers/`.
3. Build **one** HubSpot deal workflow: trigger "deal stage is Closed Won" in your pipeline, no
   re-enrolment. Actions: send webhook, POST to
   `https://<project>.vercel.app/api/invoice-<suffix>`; then, if you like, a short delay and a
   Slack notification carrying the deal name and `hs_next_step`, which the receiver has just
   rewritten to name the invoice.

The receiver copies the deal's line items onto the invoice. If the deal has none, it bills one
line at the deal amount. So put on the deal what the **first invoice** should carry: Claude can
create deal line items from the lines file through the HubSpot connector (line items are
allowed; only invoices are refused). If your first invoice is not a simple copy of the deal,
skip the receiver and use the script by hand (per-deal step 8).

**Check:** on a test deal with a test contact, call the receiver with `?dry=1`:

```
curl -s -X POST "https://<project>.vercel.app/api/invoice-<suffix>?dry=1" \
  -H "Content-Type: application/json" -d '{"objectId": "<deal id>"}'
```

It returns the invoice and lines it would create and writes nothing. Then move the test deal to
Closed Won: one draft invoice appears on the deal, the owner has a task, and Next step names the
invoice. Delete the test invoice after.

## Per deal

### 1. The deal is ready

A person says so ("draft the terms for Acme"), or the deal reaches the stage your playbook sets
for terms. The agent does not decide a deal is ready to close.

### 2. Write the deal file

Claude reads the deal, its contact and its company from the CRM and writes
`clients/<slug>/close/deal.json` in the shape of `close/templates/deal.example.json`: legal name,
address, contact, signer, offer (exactly as named in `commercial.md` §1), add-ons with
quantities, term in months, start date, CRM ids. The legal name and address come from the client
or their own paperwork, never a guess; if they are not known, ask.

**No figures go in the deal file.** The script refuses a field named price, amount, fee, cost,
total, discount or rate, and any typed currency figure, because every figure must come from
canon or the custom offer.

**Check:** the dry run (step 4) runs without a `STOP` about the deal file.

### 3. Custom offer, if negotiated

A negotiated deal has `clients/<slug>/custom-offer.md` (copy `clients/_TEMPLATE/`), with a filled
Status, a named approver, and a **Variance from standard** table. For each row whose Line matches
the offer or an add-on, the script uses This deal instead of canon. A row named "Payment terms"
replaces the §4 text.

The script stops if the custom offer is lapsed, has no approver, or states a Standard that is no
longer what `commercial.md` says. That last one means the deal is described against a price you
no longer charge: the approver restates it before anything goes out. A custom offer never edits
`commercial.md`.

**Check:** the dry run prints `custom offer: clients/<slug>/custom-offer.md` and tags the changed
lines `[custom-offer.md]`.

### 4. Build the documents

```
python3 close/make-close-docs.py clients/<slug>/close/deal.json            # dry run: read it
python3 close/make-close-docs.py clients/<slug>/close/deal.json --write \
    --order-form-base close/templates/order-form-base.docx
```

Then run the copy checks on what was built:

```
python3 ops/check-client-copy.py clients/<slug>/close/<date>-<slug>-email.txt
python3 ops/check-corpus.py
```

Open both PDFs and read them, every line. The script checks figures and structure, not sentences.

**Check:** both PDFs exist, read correctly, carry no "DRAFT" and no `{{`, and their totals match
the dry run.

### 5. Draft the email

Claude creates a Gmail draft to the contact with the Gmail connector:

- **to** the contact, **subject** from the first line of `…-email.txt`;
- **body** the rest of `…-email.txt`, **htmlBody** `…-email.html`. Both already end with the
  signature from `seller.json`;
- **the Summary of Terms PDF attached** (and the Order Form PDF when you are sending it). Large
  attachments can fail through the connector; if one does, the draft goes without it and the
  person attaches the PDF from `clients/<slug>/close/` before sending;
- on an existing thread, a reply to that thread's last message.

Keep it short: thanks, the attachment, one ask (who signs, who onboards the vendor). Prices live
in the attachment, never in the body; the script refuses an email template carrying a figure.

To change a draft, **create a new one and delete the old one**. Updating a reply draft through
the connector drops its thread reference, and it then sends as a new email outside the
conversation.

**Check:** the draft is in Gmail Drafts, threaded where it should be, signature at the bottom,
PDF attached. Nothing has been sent.

### 6. A person sends it. Then file, record, tag

Once the person confirms it went:

1. Copy the PDFs exactly as attached to `clients/<slug>/outreach/<date>-SENT-<name>.pdf`, and the
   email text as sent to `clients/<slug>/outreach/<date>-SENT-terms-email.md`.
2. Add a row to the **Artifact record** in `clients/<slug>/record.md` naming each file, the tag,
   the date and the recipient. The generator reads this table and will never overwrite a file
   listed there.
3. Commit, then `git tag client/<slug>-<YYYY-MM-DD>` and push the tag.

A change after this point is a reissue: run the generator with a new `--date`, send again, new
row, new tag. Never edit what they hold (`docs/versioning-client-copies.md`).

**Check:** `git tag -l 'client/<slug>-*'` lists the tag, and record.md has the row.

### 7. Signed

A person moves the deal to Closed Won (agents never move stages). File the countersigned copy
in `clients/<slug>/outreach/` and record it.

### 8. The invoice

If the receiver is on (setup step 6), the draft invoice appears within a minute. Otherwise:

```
python3 close/hubspot-create-invoice.py --lines-file clients/<slug>/close/<date>-<slug>-lines.json \
    --bill first-period --invoice-date <YYYY-MM-DD> --net <days from §4>          # dry run
... --apply
```

`--bill first-period` bills one period of each recurring line plus every one-time line;
`--bill term` bills each line's total over the term. CRM ids come from the lines file, or pass
`--deal`, `--company`, `--contact` (repeatable; the first is the billing contact). For a bill the
generator does not cover, pass `--line "Name|Quantity|Unit price|Description"`, repeatable, and
confirm each typed figure against `commercial.md` or the custom offer.

A second invoice on the same deal (a supplemental bill, not a replacement) needs
`--allow-second`. If a run dies after creating the invoice, `--resume <invoice id>` fills that
empty draft rather than making another.

**Check:** the draft in HubSpot shows the right lines, total, billing contact and due date, and
its status is Draft. A person finalises and sends it from HubSpot.

## Known gotchas (all of these happened)

- **"[DRAFT]" in a header shipped to a client.** The base Word document carried a "[DRAFT]" run
  in its first-page header, top right of page 1, invisible unless you open the header. Every
  order form generated from it inherited the mark, and one went out. A later note claimed it was
  fixed when the fix had never been committed, so the next fresh generation carried it again.
  The script now stops on "DRAFT" anywhere in the output, headers and footers of every section
  included. Fix the base document, not the output, and test a fresh generation rather than
  trusting a note that says it's fixed.
- **Gmail connector drafts have no signature.** Gmail adds the signature only in its own compose
  window; an API-made draft holds exactly the body given. The generator appends the signature
  from `seller.json` to both the text and the HTML body.
- **Updating a reply draft detaches it from its thread.** The connector's update drops the
  reply reference and the draft becomes a new email. Recreate the draft as a reply and delete the
  old one; never update a reply draft.
- **Invoice writes are refused by the HubSpot connector**, even after reauthorising with invoice
  scopes. The private-app token route exists for that.
- **An invoice with no lines.** With invoice scope but no line-item scope, the invoice is created
  and the line item fails, leaving a draft that bills nothing. Add `crm.objects.line_items.write`
  and `e-commerce` to the private app; `--resume` fills the empty draft.
- **A long closing email.** The first terms-send draft ran to paragraphs of explanation; it was
  cut to five lines before it went, because at the close every extra sentence is something to
  react to instead of a document to sign. The template is short on purpose.
- **A supplemental mistaken for a replacement.** A second bill on a deal was first drafted as a
  replacement for the first invoice. The script stops on a deal that already has an invoice
  until you say `--allow-second`.
- **Client deals written into the pricing canon.** Two negotiated deals were once written into
  `commercial.md`, one of them nearly two hundred lines, and the standard offer ended up buried
  beneath them. Custom figures live in `clients/<slug>/custom-offer.md` only; the generator reads
  them from there.
