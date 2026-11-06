# Setup progress

Claude ticks these as each step's check passes (see `SETUP.md`). Say "continue setup" to pick
up at the first open box. `[~]` means deferred on purpose, with a row in `NEEDS.md`.

- [ ] 0. Your own private repo (`git remote -v` shows it)
- [ ] 1a. What you sell (company-context, product-context, commercial.md, playbook)
- [ ] 1b. Who outbound targets (company-context, Outbound targeting)
- [ ] 1c. Which tools you use (`STACK.md` § Our picks)
- [ ] 1. Check: `python3 ops/check-corpus.py --only placeholders` and the default run both end with `0 finding(s)`
- [ ] 2. CRM connected, properties created, stage IDs recorded, Slack card fires on a test deal
- [ ] 3a. First call scored by hand (the engine is usable from here)
- [ ] 3b. Five calls processed by hand, rubric tuned
- [ ] 4. Post-call routine on, first automatic card landed
- [ ] 5a. Friday digest routine on
- [ ] 5b. Daily keeper routine on
- [ ] 5c. Heartbeat watch alerting (SLACK_WEBHOOK_URL secret added)
- [ ] 5d. Inbound flow live: site snippet, booking receiver, Clay key, Slack app, inbound receiver, CRM workflows (`ops/receivers/INBOUND.md`)
- [ ] 5e. Outbound sending live: separate domain warmed, tracking domain verified, CRM properties, first list loaded and approved (`outbound/OUTBOUND.md` steps 1-8)
- [ ] 5f. Click → LinkedIn receiver deployed and hook registered; test click queued or tasked (`outbound/OUTBOUND.md` step 9)
- [ ] 5g. First daily call list written to the CRM (`outbound/OUTBOUND.md` step 10)
- [ ] 5h. Close flow live: commercial.md priced, seller.json filled, lawyer's Order Form wired, Gmail draft check, invoice token probe passes, Closed Won receiver optional (`close/CLOSE.md`)

## Notes

<!-- Claude records open items and tool choices here as setup goes. -->
