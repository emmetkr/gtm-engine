#!/usr/bin/env python3
"""Daily call list: rank outbound leads by real engagement, then write phones and CALL tasks.

Three parts, and only two of them are this script:

  1. rank    python3 outbound/daily-call-list.py rank --out call-list.json
             Reads lemlist activity for your outbound campaigns, drops bot and scanner events,
             scores each lead, checks HubSpot, and writes the top N to a JSON file.
  2. phones  NOT this script. Claude runs your Clay phone-finding function through the Clay
             connector on every row with "needsPhone": true and fills in "phone". The function
             needs the LinkedIn URL; a row without one cannot be looked up. (OUTBOUND.md, step 10)
  3. write   python3 outbound/daily-call-list.py write call-list.json            # dry run
             python3 outbound/daily-call-list.py write call-list.json --apply
             Writes each found number to the HubSpot contact's mobilephone (only when blank) and
             opens one CALL task per person, due today, with the signal and the number in the body.

Scoring (change the weights below if your data says otherwise):
  human click x10 + human open x2.
  A click is human when lemlist does not flag it as a bot AND it came at least SCANNER_SECONDS
  after the latest send to that lead. An open is human on the same test with PREFETCH_SECONDS.
  Corporate email security fetches links and pixels seconds after delivery; those events are
  real lemlist events and fake engagement.
  Anyone who replied is left off: a reply is a conversation, answer it in the inbox.

Env vars:
  LEMLIST_API_KEY           required for rank
  LEMLIST_SOURCE_CAMPAIGNS  the id:rail list the click receiver uses (or pass --campaign, repeatable)
  HUBSPOT_ACCESS_TOKEN      required for write; used by rank to skip people already in a deal
  TASK_OWNER_EMAIL          optional, the HubSpot user who owns the CALL tasks
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

LEM = 'https://api.lemlist.com/api'
HS = 'https://api.hubapi.com'
SCANNER_SECONDS = 45     # clicks sooner than this after the send are a machine
PREFETCH_SECONDS = 90    # opens sooner than this after the send are a machine
W_CLICK, W_OPEN = 10, 2
TASK_CONTACT_ASSOC = 204


def http(method, url, headers, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header('Content-Type', 'application/json')
    # lemlist answers 403 to urllib's default User-Agent (Cloudflare). curl works; so does this.
    req.add_header('User-Agent', 'gtm-engine/1.0 (daily-call-list)')
    for k, v in headers.items():
        req.add_header(k, v)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                t = r.read().decode()
                return r.status, (json.loads(t) if t.startswith(('{', '[')) else t)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(10)
                continue
            t = e.read().decode()
            return e.code, (json.loads(t) if t.startswith(('{', '[')) else t)


def lem(path):
    key = os.environ['LEMLIST_API_KEY']
    return http('GET', LEM + path, {'Authorization': 'Basic ' + base64.b64encode((':' + key).encode()).decode()})


def hs(method, path, body=None):
    s, r = http(method, HS + path, {'Authorization': 'Bearer ' + os.environ['HUBSPOT_ACCESS_TOKEN']}, body)
    if s >= 400:
        raise RuntimeError(f'hubspot {method} {path} {s} {str(r)[:200]}')
    return r


def ts(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        return None


def campaigns(args):
    if args.campaign:
        return args.campaign
    raw = os.environ.get('LEMLIST_SOURCE_CAMPAIGNS', '')
    ids = [p.split(':')[0].strip() for p in raw.split(',') if p.strip()]
    if not ids:
        sys.exit('No campaigns: pass --campaign or set LEMLIST_SOURCE_CAMPAIGNS.')
    return ids


def activities(cid, since):
    out, offset = [], 0
    while True:
        s, page = lem(f'/activities?campaignId={cid}&limit=100&offset={offset}&version=v2')
        if s != 200:
            sys.exit(f'lemlist activities {cid}: {s} {str(page)[:200]}')
        rows = page if isinstance(page, list) else (page.get('activities') or page.get('data') or [])
        out += [a for a in rows if (ts(a.get('createdAt')) or since) >= since]
        if len(rows) < 100:
            return out
        offset += 100
        time.sleep(0.3)


def lead_variables(cid):
    s, rows = lem(f'/v2/campaigns/{cid}/export/leads?state=all&format=json')
    if s != 200:
        print(f'  (lead export for {cid} failed: {s}; falling back to activity fields)')
        return {}
    rows = rows if isinstance(rows, list) else (rows.get('leads') or rows.get('data') or [])
    return {(r.get('email') or '').lower(): r for r in rows if r.get('email')}


def is_bot(a):
    return bool(a.get('bot') or a.get('isBot'))


def rank(args):
    if not os.environ.get('LEMLIST_API_KEY'):
        sys.exit('LEMLIST_API_KEY is not set.')
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    excluded = set()
    if args.exclude_file:
        excluded = {l.strip().lower() for l in open(args.exclude_file) if l.strip() and not l.startswith('#')}

    leads = {}
    for cid in campaigns(args):
        acts = activities(cid, since)
        varmap = lead_variables(cid)
        print(f'{cid}: {len(acts)} activities in the last {args.days} days')
        by_lead = {}
        for a in acts:
            email = (a.get('leadEmail') or a.get('email') or '').lower()
            if email:
                by_lead.setdefault(email, []).append(a)
        for email, evs in by_lead.items():
            sends = sorted(t for t in (ts(a.get('createdAt')) for a in evs if a.get('type') == 'emailsSent') if t)

            def human(a, gap):
                t = ts(a.get('createdAt'))
                if is_bot(a) or not t:
                    return False
                prior = [s for s in sends if s <= t]
                return not prior or (t - prior[-1]).total_seconds() >= gap

            clicks = sum(1 for a in evs if a.get('type') == 'emailsClicked' and human(a, SCANNER_SECONDS))
            opens = sum(1 for a in evs if a.get('type') == 'emailsOpened' and human(a, PREFETCH_SECONDS))
            replied = any(a.get('type') in ('emailsReplied', 'linkedinReplied') for a in evs)
            lr = leads.setdefault(email, {'email': email, 'clicks': 0, 'opens': 0, 'replied': False, 'campaigns': []})
            lr['clicks'] += clicks
            lr['opens'] += opens
            lr['replied'] = lr['replied'] or replied
            lr['campaigns'].append(cid)
            v = varmap.get(email, {})
            first = evs[0]
            for key, alt in (('firstName', 'leadFirstName'), ('lastName', 'leadLastName'),
                             ('companyName', 'leadCompanyName'), ('jobTitle', None),
                             ('linkedinUrl', None), ('phone', None)):
                if not lr.get(key):
                    lr[key] = v.get(key) or (first.get(alt) if alt else '') or first.get(key) or ''

    rows = []
    for lr in leads.values():
        domain = lr['email'].split('@')[-1]
        if lr['replied'] or domain in excluded:
            continue
        lr['score'] = lr['clicks'] * W_CLICK + lr['opens'] * W_OPEN
        if lr['score'] <= 0:
            continue
        rows.append(lr)
    rows.sort(key=lambda r: (-r['score'], -r['clicks']))

    out = []
    use_hs = bool(os.environ.get('HUBSPOT_ACCESS_TOKEN'))
    if not use_hs:
        print('!! HUBSPOT_ACCESS_TOKEN not set: not checking for open deals or existing phone numbers.')
    for r in rows:
        if len(out) >= args.limit:
            break
        r['hubspotId'] = None
        if use_hs:
            found = hs('POST', '/crm/v3/objects/contacts/search', {
                'filterGroups': [{'filters': [{'propertyName': 'email', 'operator': 'EQ', 'value': r['email']}]}],
                'properties': ['mobilephone', 'phone', 'num_associated_deals'], 'limit': 1}).get('results') or []
            if found:
                p = found[0].get('properties') or {}
                if int(p.get('num_associated_deals') or 0) > 0:
                    continue   # someone already owns this conversation
                r['hubspotId'] = found[0]['id']
                r['phone'] = r.get('phone') or p.get('mobilephone') or p.get('phone') or ''
            time.sleep(0.15)
        bits = []
        if r['clicks']:
            bits.append(f"{r['clicks']} click{'s' if r['clicks'] > 1 else ''}")
        if r['opens']:
            bits.append(f"{r['opens']} open{'s' if r['opens'] > 1 else ''}")
        r['signal'] = ', '.join(bits) + f' in the last {args.days} days'
        r['needsPhone'] = not r.get('phone')
        r['canLookUpPhone'] = bool(r.get('linkedinUrl'))
        out.append(r)

    with open(args.out, 'w') as f:
        json.dump(out, f, indent=1)
    need = [r for r in out if r['needsPhone']]
    print(f'\n{len(out)} on the list -> {args.out}')
    print(f'{len(need)} need a phone; {sum(1 for r in need if r["canLookUpPhone"])} have a LinkedIn URL to look one up with.')
    for r in out:
        name = f"{r.get('firstName', '')} {r.get('lastName', '')}".strip() or r['email']
        print(f"  {r['score']:>3}  {name}, {r.get('jobTitle', '')} at {r.get('companyName', '')}  ({r['signal']})"
              f"{'' if r.get('phone') else '  [no phone]'}")


def write(args):
    if not os.environ.get('HUBSPOT_ACCESS_TOKEN'):
        sys.exit('HUBSPOT_ACCESS_TOKEN is not set.')
    rows = json.load(open(args.file))
    owner = None
    if os.environ.get('TASK_OWNER_EMAIL'):
        o = hs('GET', '/crm/v3/owners?email=' + urllib.parse.quote(os.environ['TASK_OWNER_EMAIL']))
        owner = (o.get('results') or [{}])[0].get('id')
    due = datetime.now(timezone.utc).replace(hour=17, minute=0, second=0, microsecond=0).isoformat()
    done = 0
    for r in rows:
        name = f"{r.get('firstName', '')} {r.get('lastName', '')}".strip() or r['email']
        phone = (r.get('phone') or '').strip()
        if not phone:
            print(f'  skip {name}: no phone')
            continue
        cid = r.get('hubspotId')
        if not args.apply:
            print(f"  would {'update' if cid else 'create'} contact {name} mobilephone={phone} and open a CALL task")
            continue
        if cid:
            p = hs('GET', f'/crm/v3/objects/contacts/{cid}?properties=mobilephone').get('properties') or {}
            if not p.get('mobilephone'):
                hs('PATCH', f'/crm/v3/objects/contacts/{cid}', {'properties': {'mobilephone': phone}})
        else:
            props = {'email': r['email'], 'firstname': r.get('firstName', ''), 'lastname': r.get('lastName', ''),
                     'company': r.get('companyName', ''), 'jobtitle': r.get('jobTitle', ''), 'mobilephone': phone}
            cid = hs('POST', '/crm/v3/objects/contacts', {'properties': {k: v for k, v in props.items() if v}})['id']
        props = {
            'hs_task_subject': f"Call {name}{' (' + r['companyName'] + ')' if r.get('companyName') else ''}",
            'hs_task_body': '\n'.join(filter(None, [
                f"Signal: {r.get('signal', '')}", f'Phone: {phone}',
                f"Title: {r['jobTitle']}" if r.get('jobTitle') else None,
                f"LinkedIn: {r['linkedinUrl']}" if r.get('linkedinUrl') else None,
                'From the daily call list (outbound/daily-call-list.py).'])),
            'hs_timestamp': due, 'hs_task_status': 'NOT_STARTED', 'hs_task_priority': 'HIGH', 'hs_task_type': 'CALL',
        }
        if owner:
            props['hubspot_owner_id'] = owner
        hs('POST', '/crm/v3/objects/tasks', {'properties': props, 'associations': [
            {'to': {'id': cid}, 'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': TASK_CONTACT_ASSOC}]}]})
        done += 1
        print(f'  ok  {name}: phone written, CALL task open')
        time.sleep(0.2)
    print(f'\n{done} CALL tasks created.' if args.apply else '\nDry run. Re-run with --apply to write.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('rank')
    r.add_argument('--campaign', action='append', help='lemlist campaign id (repeatable)')
    r.add_argument('--days', type=int, default=14)
    r.add_argument('--limit', type=int, default=30)
    r.add_argument('--exclude-file', help='one excluded domain per line (customers, do-not-call, regions you do not call)')
    r.add_argument('--out', default='call-list.json')
    w = sub.add_parser('write')
    w.add_argument('file')
    w.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    rank(args) if args.cmd == 'rank' else write(args)


if __name__ == '__main__':
    main()
