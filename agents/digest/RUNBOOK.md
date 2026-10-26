# DIGEST — the Friday run

Schedule: Fridays, once, mid-afternoon in your timezone (write the UTC hour). Connectors: CRM
(read), Google Drive or Slack.

**May:** read the CRM; write the digest doc; write `agents/digest/state/`; push to
`claude/digest`. **May not:** write the CRM, send email.

1. Get current (same block as `agents/postcall/RUNBOOK.md` §1, branch `claude/digest`).
2. Run `.claude/skills/weekly-exec-update`. Then `pipeline-analysis` for the top five deals by
   value × risk.
3. Write the result as one doc in the team's weekly folder. Put the link in `state/heartbeat.md`.
4. Commit as `DIGEST:` and push.
