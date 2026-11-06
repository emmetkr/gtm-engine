# POSTCALL — the unattended run

What the flow is for: `docs/architecture.md` §Loop 3. What it does per call:
`.claude/skills/sales-intake/SKILL.md`. This file is the plumbing between them.

**May:** read meetings and transcripts from the call recorder; read and write CRM deals,
contacts and tasks in the sales pipeline as `sales-intake` specifies; create an email **draft**;
write `agents/postcall/state/`; file `tasks/`; commit and push to `claude/postcall`.

**May not:** create a deal · move a stage · send email · post to Slack (the CRM workflow posts
the card; only when `crm-records` says `card_route: slack-connector` may this run post, and only
the card) · edit `.claude/skills/` · write `clients/` · delete anything in the recorder ·
force-push · touch another pipeline.

## 1. Get current

```bash
git fetch origin main claude/postcall 2>/dev/null || git fetch origin main
if git rev-parse -q --verify origin/claude/postcall >/dev/null &&
   [ "$(git rev-list --count origin/main..origin/claude/postcall)" -gt 0 ]; then
  git checkout -B claude/postcall origin/claude/postcall
  git merge --no-rebase origin/main
else
  git checkout -B claude/postcall origin/main
fi
```

## 2. Check the heartbeat

Read `state/heartbeat.md`. Last run more than 3 hours ago during working hours means the
automation was down. Say so first, with the gap.

## 3. Find new calls

Find the recorder's tools with `ToolSearch`. List meetings that ended in the last 24 hours;
diff their ids against `state/meetings-seen-ids`. Nothing new → stamp, commit, end. No recorder
tool → write `recorder: unavailable` in the heartbeat and end.

**Transcripts render late. Do not score a stub.**
- Skip any meeting that ended under 30 minutes ago. Leave it unseen; the next run gets it.
- Take the duration from the meeting detail, not the listing. If the transcript ends well short
  of it, or the call is under ~10 minutes against a 30–45 minute invite, skip it this run and
  note it. Process a short call only after two runs agree on its length.
- A stub plus a second meeting with the same attendees within the hour is one call in two
  pieces. Process both together or neither.
- Record the duration on every `# processed:` line. If a processed call's duration later grows
  by more than 50%, rescore from the full transcript and **append** a dated CORRECTION entry.
  Never edit the old one.

## 4. Process each call

Run `sales-intake` in unattended mode, Steps 0–7. Before any write, check the deal's
description log for an entry dated to this call; if one exists, mark the id
`# skipped: already logged` and move on. The cursor file alone is not a dedup.

- No deal match → `tasks/postcall-unmatched-<date>-<slug>.md` for the default owner. Stop for
  that call.
- Something a person must decide → a CRM task on the deal for its owner, due next business day.

## 5. Stamp and push

Append ids to `state/meetings-seen-ids` (`<id> # processed: <duration>s` or `# skipped: <why>`).
Overwrite `state/heartbeat.md` with: run time, branch started from, calls found, processed,
skipped and why, any tool missing.

```bash
git add agents/postcall/state tasks
git -c user.name=POSTCALL -c user.email=postcall@example.com commit -m "POSTCALL: <n> processed, <n> skipped"
git push origin claude/postcall
```
