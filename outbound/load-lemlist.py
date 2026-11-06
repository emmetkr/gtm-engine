#!/usr/bin/env python3
"""Load a target list (CSV) into a lemlist campaign, after the checks that keep a list clean.

  python3 outbound/load-lemlist.py leads.csv --campaign cam_xxx --rail cold --name outbound-<vertical>
  python3 outbound/load-lemlist.py leads.csv --campaign cam_xxx --rail cold --name outbound-<vertical> --apply
  python3 outbound/load-lemlist.py leads.csv ... --apply --create-contacts   # also create cold leads in HubSpot

Dry run by default: it prints what it would load and why each skipped row was skipped.
--apply writes. Nothing here sends an email; the campaign sends when a person starts it.

CSV columns (header row, any order; extra columns ride along as lemlist variables):
  email, firstName, lastName, companyName, companyDomain, jobTitle, linkedinUrl, vertical

Checks, in order, for each row:
  1. has an email, and it is not free-mail
  2. its domain is not in --exclude-file (one domain per line: customers, partners,
     competitors, do-not-contact; build it from company-context's Outbound targeting exclusions)
  3. its title has none of the excluded words (assistant, intern, ...)
  4. no more than --max-per-domain people per company
  5. HubSpot (if HUBSPOT_ACCESS_TOKEN is set):
       - the company's domain has no associated deal (someone is already talking to them)
       - cold rail: the person is NOT already a contact. Someone already in your CRM is a warm
         lead and belongs on the warm rail (outbound/OUTBOUND.md, step 4)
       - warm rail: the person IS a contact and has no associated deal
Without a HubSpot token the HubSpot checks are skipped and the run says so loudly.

Env vars: LEMLIST_API_KEY (needed for --apply), HUBSPOT_ACCESS_TOKEN (strongly recommended).
--create-contacts needs the outbound_rail and outbound_campaign contact properties (step 3).
"""
import argparse
import base64
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

LEM = 'https://api.lemlist.com/api'
HS = 'https://api.hubapi.com'
FREE_MAIL = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com', 'aol.com', 'me.com',
             'live.com', 'msn.com', 'protonmail.com', 'proton.me', 'ymail.com', 'googlemail.com', 'mail.com'}
EXCLUDED_TITLE_WORDS = ['assistant', 'intern', 'student', 'pa to']   # CHANGE ME if your buyers differ


def http(method, url, headers, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'gtm-engine/1.0 (load-lemlist)')   # Cloudflare refuses urllib's default
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            t = r.read().decode()
            return r.status, (json.loads(t) if t.startswith(('{', '[')) else t)
    except urllib.error.HTTPError as e:
        t = e.read().decode()
        return e.code, (json.loads(t) if t.startswith(('{', '[')) else t)


def lem(method, path, body=None):
    key = os.environ.get('LEMLIST_API_KEY', '')
    return http(method, LEM + path, {'Authorization': 'Basic ' + base64.b64encode((':' + key).encode()).decode()}, body)


def hs(method, path, body=None):
    s, r = http(method, HS + path, {'Authorization': 'Bearer ' + os.environ['HUBSPOT_ACCESS_TOKEN']}, body)
    if s == 429:
        time.sleep(10)
        s, r = http(method, HS + path, {'Authorization': 'Bearer ' + os.environ['HUBSPOT_ACCESS_TOKEN']}, body)
    if s >= 400:
        raise RuntimeError(f'hubspot {method} {path} {s} {str(r)[:200]}')
    return r


def hs_contact(email):
    r = hs('POST', '/crm/v3/objects/contacts/search', {
        'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': email}]}],
        'properties': ['email', 'num_associated_deals'], 'limit': 1})
    rows = r.get('results') or []
    return rows[0] if rows else None


_company_cache = {}
def hs_company_has_deal(domain):
    if domain not in _company_cache:
        r = hs('POST', '/crm/v3/objects/companies/search', {
            'filterGroups': [{'filters': [{'propertyName': 'domain', 'operator': 'EQ', 'value': domain}]}],
            'properties': ['domain', 'num_associated_deals'], 'limit': 5})
        _company_cache[domain] = any(int((c.get('properties') or {}).get('num_associated_deals') or 0) > 0
                                     for c in (r.get('results') or []))
    return _company_cache[domain]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv')
    ap.add_argument('--campaign', required=True, help='lemlist campaign id')
    ap.add_argument('--rail', required=True, choices=['cold', 'warm'])
    ap.add_argument('--name', required=True, help='utm_campaign value for this campaign, e.g. outbound-<vertical>')
    ap.add_argument('--exclude-file', help='one excluded domain per line')
    ap.add_argument('--max-per-domain', type=int, default=2)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--create-contacts', action='store_true', help='cold rail only: create each loaded lead in HubSpot')
    a = ap.parse_args()

    if a.apply and not os.environ.get('LEMLIST_API_KEY'):
        sys.exit('LEMLIST_API_KEY is not set.')
    use_hs = bool(os.environ.get('HUBSPOT_ACCESS_TOKEN'))
    if not use_hs:
        print('!! HUBSPOT_ACCESS_TOKEN not set: skipping the CRM checks. You may load people who are '
              'already customers or already in a deal.\n')
    if a.create_contacts and (not use_hs or a.rail != 'cold'):
        sys.exit('--create-contacts needs HUBSPOT_ACCESS_TOKEN and --rail cold.')

    excluded = set()
    if a.exclude_file:
        excluded = {line.strip().lower().lstrip('@') for line in open(a.exclude_file)
                    if line.strip() and not line.startswith('#')}

    per_domain, keep, skipped = {}, [], []
    with open(a.csv, newline='') as f:
        for row in csv.DictReader(f):
            row = {k.strip(): (v or '').strip() for k, v in row.items() if k}
            email = row.get('email', '').lower()
            domain = email.split('@')[-1] if '@' in email else ''
            title = row.get('jobTitle', '').lower()
            why = None
            if not domain:
                why = 'no email'
            elif domain in FREE_MAIL:
                why = 'free-mail address'
            elif domain in excluded or row.get('companyDomain', '').lower() in excluded:
                why = 'excluded domain'
            elif any(w in title for w in EXCLUDED_TITLE_WORDS):
                why = f'excluded title ({row.get("jobTitle")})'
            elif per_domain.get(domain, 0) >= a.max_per_domain:
                why = f'already {a.max_per_domain} at {domain}'
            elif use_hs:
                if hs_company_has_deal(domain):
                    why = 'company has a deal in HubSpot'
                else:
                    c = hs_contact(email)
                    if a.rail == 'cold' and c:
                        why = 'already a HubSpot contact: warm rail, not cold'
                    elif a.rail == 'warm' and not c:
                        why = 'not a HubSpot contact: cold rail, not warm'
                    elif c and int((c.get('properties') or {}).get('num_associated_deals') or 0) > 0:
                        why = 'contact has a deal'
                time.sleep(0.15)
            if why:
                skipped.append((email or '(blank)', why))
                continue
            per_domain[domain] = per_domain.get(domain, 0) + 1
            keep.append(row)

    print(f'{len(keep)} to load into {a.campaign} ({a.rail} rail, {a.name}); {len(skipped)} skipped')
    for email, why in skipped:
        print(f'  skip {email}: {why}')
    if not a.apply:
        for row in keep:
            print(f'  load {row.get("email")}  {row.get("jobTitle", "")} at {row.get("companyName", "")}')
        print('\nDry run. Re-run with --apply to load.')
        return

    loaded = 0
    for row in keep:
        email = row.pop('email').lower()
        variables = {k: v for k, v in row.items() if v}
        variables.update({'outboundRail': a.rail, 'outboundCampaign': a.name})
        # deduplicate=true: lemlist refuses a lead already in another campaign of the team, which
        # stops one person getting two sequences at once.
        s, r = lem('POST', f'/campaigns/{a.campaign}/leads/{urllib.parse.quote(email)}?deduplicate=true', variables)
        ok = s < 300
        print(f'  {"ok  " if ok else "FAIL"} {email} -> {s} {"" if ok else str(r)[:160]}')
        loaded += ok
        if ok and a.create_contacts:
            props = {'email': email, 'firstname': row.get('firstName', ''), 'lastname': row.get('lastName', ''),
                     'company': row.get('companyName', ''), 'jobtitle': row.get('jobTitle', ''),
                     'outbound_rail': a.rail, 'outbound_campaign': a.name}
            try:
                hs('POST', '/crm/v3/objects/contacts', {'properties': {k: v for k, v in props.items() if v}})
            except RuntimeError as e:
                print(f'       HubSpot create failed: {str(e)[:160]}')
        time.sleep(0.3)
    print(f'\n{loaded} of {len(keep)} loaded.')


if __name__ == '__main__':
    main()
