#!/usr/bin/env python3
"""lemlist webhook for the click -> LinkedIn receiver: list / create / delete / replay / status.

  python3 ops/receivers/register-lemlist.py list
  python3 ops/receivers/register-lemlist.py create        # one team-wide emailsClicked hook
  python3 ops/receivers/register-lemlist.py delete <hookId>
  python3 ops/receivers/register-lemlist.py replay        # push every lead already in state
                                                          # emailsClicked through the receiver
                                                          # (backfill; the receiver dedups)
  python3 ops/receivers/register-lemlist.py status        # is the LinkedIn campaign running?

Env vars (never commit them; export them in your shell or keep them in an untracked .env):
  LEMLIST_API_KEY               lemlist API key
  LEMLIST_HOOK_URL              https://<project>.vercel.app/api/lemlist-click-<suffix>
  LEMLIST_SOURCE_CAMPAIGNS      the same id:rail list the receiver reads, e.g. "cam_x:cold,cam_y:warm"
  LEMLIST_LINKEDIN_CAMPAIGN_ID  for `status`

The hook secret is sha256('lemlist-click:' + key), the same derivation the receiver makes, so
nothing extra is stored. One hook, no campaignId: lemlist accepts a given targetUrl once, so the
receiver filters on its own allow-list of source campaigns instead of one hook per campaign.

Setup and the reasons: outbound/OUTBOUND.md, step 9.
"""
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = 'https://api.lemlist.com/api'


def env(name, required=True):
    v = os.environ.get(name, '').strip()
    if required and not v:
        sys.exit(f'{name} is not set. See the docstring at the top of this file.')
    return v


KEY = env('LEMLIST_API_KEY')
SECRET = hashlib.sha256(('lemlist-click:' + KEY).encode()).hexdigest()


def call(method, url, body=None, auth=True):
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header('Content-Type', 'application/json')
    # lemlist sits behind Cloudflare, which refuses urllib's default User-Agent (error 1010).
    req.add_header('User-Agent', 'gtm-engine/1.0 (register-lemlist)')
    if auth:
        req.add_header('Authorization', 'Basic ' + base64.b64encode((':' + KEY).encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sources():
    out = {}
    for pair in env('LEMLIST_SOURCE_CAMPAIGNS').split(','):
        pair = pair.strip()
        if pair:
            cid, _, rail = pair.partition(':')
            out[cid.strip()] = rail.strip() or 'cold'
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'list':
        s, t = call('GET', f'{API}/hooks')
        print(s)
        print(json.dumps(json.loads(t), indent=1) if t.startswith('[') else t)
    elif cmd == 'create':
        target = env('LEMLIST_HOOK_URL')
        s, t = call('POST', f'{API}/hooks', {'targetUrl': target, 'type': 'emailsClicked', 'secret': SECRET})
        print(s, t[:600])
    elif cmd == 'delete':
        if len(sys.argv) < 3:
            sys.exit('usage: register-lemlist.py delete <hookId>')
        s, t = call('DELETE', f'{API}/hooks/{sys.argv[2]}')
        print(s, t[:300])
    elif cmd == 'replay':
        # Reads current lead state, so a lead whose state has moved past emailsClicked (replied,
        # for example) is not replayed. Replayed events carry no click time, so the receiver's
        # scanner guard cannot judge them: review the HubSpot tasks a replay creates.
        target = env('LEMLIST_HOOK_URL')
        for cid, rail in sources().items():
            s, t = call('GET', f'{API}/v2/campaigns/{cid}/export/leads?state=emailsClicked&format=json')
            if s != 200:
                print(f'{cid}: export failed {s} {t[:200]}')
                continue
            leads = json.loads(t)
            leads = leads if isinstance(leads, list) else leads.get('leads', leads.get('data', []))
            print(f'{cid} ({rail}): {len(leads)} clicked')
            for lead in leads:
                ev = {'type': 'emailsClicked', 'campaignId': cid, 'campaignName': cid,
                      'leadId': lead.get('_id') or lead.get('leadId'), 'leadEmail': lead.get('email'),
                      'subject': '(replayed from campaign state)', 'secret': SECRET}
                s, t = call('POST', target, ev, auth=False)
                print(' ', lead.get('email'), '->', s, t[:220])
                time.sleep(0.4)
    elif cmd == 'status':
        cid = env('LEMLIST_LINKEDIN_CAMPAIGN_ID')
        s, t = call('GET', f'{API}/campaigns/{cid}')
        try:
            print(s, 'status:', json.loads(t).get('status'))
        except ValueError:
            print(s, t[:300])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
