# Setup

Do these in order. Each step ends with something you can check.

## 1. Make it yours (30 min)

Open the repo in Claude Code and say: *"Interview me and fill the canon."* Claude asks
questions and writes:

| File | What goes in it |
|---|---|
| `.claude/skills/company-context/SKILL.md` | ICP, who buys, the sale motion, positioning, proof points |
| `.claude/skills/product-context/SKILL.md` | Each product or module, what it does, and its state (live / beta / planned) |
| `.claude/skills/sales-playbook/references/commercial.md` | Every price, tier, discount rule. The only file that sets a figure |
| `.claude/skills/sales-call-scorer/PLAYBOOK.md` | The plays your best rep runs, numbered |
| `docs/non-negotiables.md` | The rules that cause real damage. Each with who ruled and when |
| `CLAUDE.md` | Company name, plus the derived copy of the non-negotiables |

**Check:** `python3 ops/check-corpus.py` reports no figures outside `commercial.md`.

## 2. Wire the CRM (30 min)

1. Connect the CRM connector in Claude (Settings → Connectors).
2. Create the custom deal properties in `crm-records` §Properties (`last_call_at`,
   `last_call_score`, `last_call_grade`, `last_call_tier`, `last_call_headline`, `blockers`).
3. Copy your real pipeline and stage IDs into the stage table in `crm-records`. It is the one
   home for them; `sales-intake` points at it.
4. Build one CRM workflow: *when `last_call_at` is known or changes → post to the sales Slack
   channel* with deal name, grade, score, tier, headline, next step, blockers, owner, link.

**Check:** set `last_call_at` on a test deal by hand. The card appears in Slack.

## 3. First call, by hand

Paste a real transcript into Claude Code: *"process this call."* `sales-intake` matches the
deal, scores it, proposes each write and asks you to confirm. Read the scorecard against your
own sense of the call. If the score is wrong, fix `RUBRIC.md` or `PLAYBOOK.md`, not the output.

Do five calls this way before automating. The rubric will need tuning; it always does.

## 4. Turn on the post-call routine

Follow `agents/postcall/README.md`. Create the Routine in the console UI with the repo and the
CRM, call recorder and Gmail connectors attached. Its prompt is three lines that point at the
runbook, so the procedure lives in git.

**Check:** after the next real call, a card lands within the hour, and
`agents/postcall/state/heartbeat.md` on branch `claude/postcall` shows the run.

## 5. The rest

- `agents/digest/` — Friday digest to Slack or a doc.
- `agents/keeper/` — daily hygiene: runs the checks, files tasks, keeps `NEEDS.md` honest.
- `.github/workflows/heartbeat-watch.yml` — alerts if a routine goes quiet. Add the
  `SLACK_WEBHOOK_URL` secret.
- `sessions/` hooks are already wired in `.claude/settings.json`: every new session starts with
  a summary of the last one.
- `ops/receivers/` — booking attribution, when you start running paid or outbound traffic.
