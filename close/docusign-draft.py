#!/usr/bin/env python3
"""Create a DRAFT DocuSign envelope for a deal's Order Form, with hubspot_deal_id on it.

  python3 close/docusign-draft.py clients/<slug>/close/deal.json --pdf <order form pdf> \\
      --countersigner "Your Name <you@example.com>"            # dry run: prints the envelope
  ... --apply                                                  # creates the draft

Nothing here sends. The envelope lands in DocuSign Drafts; a person places the signature fields,
reads it, and sends it. hubspot_deal_id is what lets ops/receivers/api/sign-*.js close the right
deal without guessing.

The customer signer comes from deal.json: signer.name, and signer.email or else contact.email.
A preview PDF is refused: it is marked not for sending.

Env vars (.env at the repo root works too):
  DOCUSIGN_ACCESS_TOKEN  OAuth access token with the `signature` scope
  DOCUSIGN_ACCOUNT_ID    API Account ID (DocuSign Settings -> Apps and Keys)
  DOCUSIGN_BASE_URI      Account Base URI from the same page, e.g. https://na3.docusign.net
"""
import argparse
import base64
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_env():
    f = ROOT / '.env'
    if f.exists():
        for line in f.read_text().splitlines():
            m = re.match(r'\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)', line)
            if m:
                os.environ.setdefault(m[1], m[2].strip().strip('"\''))


def person(text):
    m = re.fullmatch(r'\s*(.+?)\s*<\s*([^<>\s]+@[^<>\s]+)\s*>\s*', text)
    if not m:
        sys.exit(f'--countersigner must look like "Your Name <you@example.com>", got: {text}')
    return m[1], m[2]


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('deal', type=pathlib.Path)
    ap.add_argument('--pdf', type=pathlib.Path, required=True, help='the Order Form PDF from make-close-docs.py')
    ap.add_argument('--countersigner', required=True, help='"Name <email>": who signs for you, after the customer')
    ap.add_argument('--subject', help='email subject (default: Order Form for <client>)')
    ap.add_argument('--apply', action='store_true', help='create the draft (default is a dry run)')
    a = ap.parse_args()

    deal = json.loads(a.deal.read_text())
    if not a.pdf.exists():
        sys.exit(f'No such PDF: {a.pdf}')
    if 'preview' in a.pdf.parts:
        sys.exit('That PDF is a preview, marked not for sending. Build the real one first.')
    signer, contact = deal.get('signer') or {}, deal.get('contact') or {}
    name, email = signer.get('name') or contact.get('name'), signer.get('email') or contact.get('email')
    deal_id = str((deal.get('crm') or {}).get('deal_id') or '').strip()
    if not name or not email:
        sys.exit('deal.json needs a signer name and an email (signer.email or contact.email).')
    if not deal_id:
        sys.exit('deal.json has no crm.deal_id, so the signature receiver could only match on email. Fill it in.')
    own_name, own_email = person(a.countersigner)
    client = (deal.get('client') or {}).get('display_name') or (deal.get('client') or {}).get('slug') or 'your company'

    body = {
        'status': 'created',   # a draft; 'sent' would email the signers
        'emailSubject': (a.subject or f'Order Form for {client}')[:100],
        'documents': [{'documentId': '1', 'name': a.pdf.name, 'fileExtension': 'pdf',
                       'documentBase64': base64.b64encode(a.pdf.read_bytes()).decode()}],
        'recipients': {'signers': [
            {'recipientId': '1', 'routingOrder': '1', 'name': name, 'email': email},
            {'recipientId': '2', 'routingOrder': '2', 'name': own_name, 'email': own_email}]},
        'customFields': {'textCustomFields': [
            {'name': 'hubspot_deal_id', 'value': deal_id, 'show': 'false', 'required': 'false'}]},
    }
    print(f'Draft envelope: "{body["emailSubject"]}"')
    print(f'  document     {a.pdf.name}')
    print(f'  signs first  {name} <{email}>')
    print(f'  signs second {own_name} <{own_email}>')
    print(f'  hubspot_deal_id {deal_id}')
    if not a.apply:
        print('\nDry run. Re-run with --apply to create the draft.')
        return

    missing = [k for k in ('DOCUSIGN_ACCESS_TOKEN', 'DOCUSIGN_ACCOUNT_ID', 'DOCUSIGN_BASE_URI') if not os.environ.get(k)]
    if missing:
        sys.exit('Not set: ' + ', '.join(missing))
    url = f"{os.environ['DOCUSIGN_BASE_URI'].rstrip('/')}/restapi/v2.1/accounts/{os.environ['DOCUSIGN_ACCOUNT_ID']}/envelopes"
    req = urllib.request.Request(url, method='POST', data=json.dumps(body).encode(), headers={
        'Authorization': 'Bearer ' + os.environ['DOCUSIGN_ACCESS_TOKEN'], 'Content-Type': 'application/json',
        'User-Agent': 'gtm-engine/1.0 (docusign-draft)'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f'DocuSign said {e.code}: {e.read().decode()[:300]}')
    print(f"\nCreated {out.get('envelopeId')}, status {out.get('status')}. Nothing was sent.")
    print('Open it in DocuSign Drafts, place the signature fields, read it, send it.')


if __name__ == '__main__':
    main()
