# POSTCALL — setup

1. Run `sales-intake` by hand on five calls until the scores feel right (SETUP.md §3).
2. In the Claude Code console, Routines → New. **Create it in the console UI, not from a
   session**: a session-created Routine can land with no repository and no connectors and fire
   into an empty container for days.
   - Repository: this repo.
   - Connectors: CRM, call recorder, Gmail, plus Slack if `crm-records` says
     `card_route: slack-connector`. Nothing else.
   - Schedule: `7 * * * *` (hourly). Avoid day-of-week filters; cron runs in UTC.
   - Prompt: the `prompt` field in `routine.json`.
3. Check the first run: branch `claude/postcall`, file `state/heartbeat.md`.
4. Add `claude/postcall` to the heartbeat watchdog.
