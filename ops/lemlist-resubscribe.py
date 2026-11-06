#!/usr/bin/env python3
"""Undo an accidental lemlist unsubscribe and put the lead back on its email sequence.

  python3 ops/lemlist-resubscribe.py a@example.com b@example.com     # repair these
  python3 ops/lemlist-resubscribe.py --file emails.txt                # one per line
  add --dry-run to only report

Needs LEMLIST_API_KEY in the environment.

Why this exists: `DELETE /campaigns/{id}/leads/{lead}` WITHOUT `?action=remove` does not remove
the lead from that campaign. It UNSUBSCRIBES the email address team-wide, which stops the person
in every campaign, and the response is a 200 with the lead body either way, so nothing looks
wrong. Always pass action=remove to drop a lead from a campaign. (outbound/OUTBOUND.md, gotchas)

For each email: (1) re-subscribe the address (v2 endpoint, then the legacy one); (2) for every
campaign lead still marked unsubscribed, try resume; (3) if it is still unsubscribed, remove the
lead from that campaign (action=remove), re-create it with the same variables, and skip the steps
it had already received, so the sequence carries on where it stopped instead of resending.

Run it on yourself first: add your own address to a test campaign, unsubscribe it, repair it.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.lemlist.com/api'
KEY = os.environ.get('LEMLIST_API_KEY', '').strip()
DRY = '--dry-run' in sys.argv


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'gtm-engine/1.0 (lemlist-resubscribe)')   # Cloudflare refuses urllib's default
    req.add_header('Authorization', 'Basic ' + base64.b64encode((':' + KEY).encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            t = r.read().decode()
            return r.status, (json.loads(t) if t.startswith(('{', '[')) else t)
    except urllib.error.HTTPError as e:
        t = e.read().decode()
        return e.code, (json.loads(t) if t.startswith(('{', '[')) else t)


def sent_steps(campaign_id, lead_id):
    """Step ids of the email steps this lead already received."""
    _, acts = call('GET', f'/activities?campaignId={campaign_id}&leadId={lead_id}&type=emailsSent&limit=50&version=v2')
    acts = acts if isinstance(acts, list) else ((acts or {}).get('activities') or (acts or {}).get('data') or [])
    done = {a.get('sequenceStep') for a in acts if a.get('sequenceStep') is not None}
    _, seqs = call('GET', f'/campaigns/{campaign_id}/sequences')
    steps = next(iter(seqs.values()))['steps'] if isinstance(seqs, dict) and seqs else []
    return [st['_id'] for st in steps if st.get('sequenceStep') in done]


def repair(email):
    q = urllib.parse.quote(email)
    print(f'\n== {email}')
    if DRY:
        print('  dry run: not re-subscribing')
    else:
        s, r = call('DELETE', f'/v2/unsubscribes/variables/{q}')
        if s == 404:
            s, r = call('DELETE', f'/unsubscribes/{q}')
        print('  re-subscribe ->', s, str(r)[:120])
    _, leads = call('GET', f'/leads?email={q}&version=v2')
    for lead in (leads if isinstance(leads, list) else []):
        camp = lead.get('campaign') or {}
        cid, lid = camp.get('id'), lead['_id']
        print(f"  lead {lid} in {camp.get('name')}: state={lead.get('state')} status={lead.get('status')}")
        if lead.get('status') != 'unsubscribed' or DRY:
            continue
        s, r = call('POST', f'/leads/start/{lid}')
        print('  resume ->', s, str(r)[:120])
        _, again = call('GET', f'/leads?id={lid}&version=v2')
        st = (again[0] if isinstance(again, list) and again else {}).get('status')
        if st != 'unsubscribed':
            print('  restored, status', st)
            continue
        done = sent_steps(cid, lid)
        variables = lead.get('variables') or {}
        print(f'  still unsubscribed; re-creating (steps already sent: {done})')
        s, _ = call('DELETE', f'/campaigns/{cid}/leads/{lid}?action=remove')   # action=remove, always
        print('  remove ->', s)
        s, r = call('POST', f'/campaigns/{cid}/leads/?deduplicate=false', variables)
        print('  re-add ->', s, str(r)[:100])
        new_id = r.get('_id') if isinstance(r, dict) else None
        if not new_id:
            print('  re-add failed; fix by hand in lemlist')
            continue
        for step_id in done:
            s2, r2 = call('POST', f'/campaigns/{cid}/leads/{new_id}/steps/{step_id}/skip')
            print(f'  skip {step_id} ->', s2, str(r2)[:100])
        time.sleep(0.3)


def main():
    if not KEY:
        sys.exit('LEMLIST_API_KEY is not set.')
    args = [a for a in sys.argv[1:] if a != '--dry-run']
    if args[:1] == ['--file']:
        emails = [line.strip() for line in open(args[1]) if line.strip()]
    else:
        emails = args
    if not emails:
        print(__doc__)
        sys.exit(1)
    for e in emails:
        repair(e)


if __name__ == '__main__':
    main()
