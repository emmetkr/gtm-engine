# Setup

Do these in order. Each step ends with something you can check.

**This is a conversation, not a form.** You do not open files and type into them. You talk,
Claude writes. That works the same whether you're in the Claude Code CLI with this repo open,
or just talking to Claude in chat and asking it to work on the repo — the only requirement is
that Claude has write access to these files, because the canon only works if it is version
controlled. Say the things in quotes below and let Claude ask follow-ups; do not pre-fill
anything yourself.

## 0. Make it your own private repo (5 min)

This repo is about to hold your prices and client records, so it can't stay a clone of the public
one, and it must never be a public fork. Say *"make this my private repo"*. Claude runs:

```
git remote rename origin upstream
gh repo create <you>/<name> --private --source=. --remote=origin --push
```

No `gh`? Create an empty private repo on github.com, then `git remote set-url origin <url>` and
`git push -u origin main`. Claude also writes your repo's URL into
`agents/postcall/routine.json`.

**Check:** `git remote -v` shows `origin` as your repo, and it shows as Private on GitHub.

## 1. Make it yours (30–45 min)

Open the repo in Claude Code and say: *"Interview me and fill the canon."* This single
conversation covers three things, not just company facts — Claude should ask about all three
before it starts writing:

**a. Who you are and what you sell.** ICP, who buys, the sale motion, positioning, proof
points, every price and discount rule, the plays your best rep runs, the rules that would cause
real damage if broken.

**b. Who outbound should be aimed at.** Not the same question as who buys — this is who gets
prospected, what signal makes someone worth reaching now, which channel, and who is explicitly
off-limits (competitors, existing customers, do-not-contact). This becomes the "Outbound
targeting" section of `company-context`.

**c. What tools you already use or want to use.** Read `STACK.md` together with Claude first —
it's a comparison, not a mandate. For each layer (CRM, call recorder, enrichment, outbound
sequencing, scheduler), say what you have or what you want. Claude should not assume HubSpot,
Clay, or lemlist just because those are this file's defaults.

Claude then writes:

| File | What goes in it |
|---|---|
| `.claude/skills/company-context/SKILL.md` | ICP, outbound targeting, the sale motion, positioning, proof points |
| `.claude/skills/product-context/SKILL.md` | Each product or module, what it does, and its state (live / beta / planned) |
| `.claude/skills/sales-playbook/references/commercial.md` | Every price, tier, discount rule. The only file that sets a figure |
| `.claude/skills/sales-call-scorer/PLAYBOOK.md` | The plays your best rep runs, numbered, and the buying signals that make a call same-day |
| `.claude/skills/sales-playbook/SKILL.md` and `.claude/skills/sales-playbook/references/objections.md` | One block per call in your motion (rename or add blocks to match it); each objection with its scripted answer |
| `docs/non-negotiables.md` | The rules that cause real damage. Each with who ruled and when |
| `CLAUDE.md` | Company name, plus the derived copy of the non-negotiables |
| `STACK.md` § Our picks | Which tools you picked, so later steps wire the right ones instead of the defaults |
| `ops/checks.json` → `banned_terms` | Your "words we never use", so the checks catch them |

**Check:** `python3 ops/check-corpus.py --only placeholders` and `python3 ops/check-corpus.py` both
end with `0 finding(s)`. The first one fails on an untouched clone, so a pass means the canon is
really filled.

## 2. Wire the CRM (30 min)

1. Connect the CRM connector in Claude (Settings → Connectors).
2. Create the custom deal properties in `crm-records` §Properties (`last_call_at`,
   `last_call_score`, `last_call_grade`, `last_call_tier`, `last_call_headline`, `blockers`).
3. Make the CRM's pipeline stages match the ladder in `crm-records` (rename or add stages in the
   CRM, or edit the ladder to match yours), then copy the pipeline and stage IDs into that table.
   It is the one home for them; `sales-intake` points at it.
4. Tell Claude your sales channel and who owns tasks on an unowned deal. It records them as
   `sales_channel` and `default_owner` in `crm-records` § Card route and owners.
5. Install HubSpot's Slack app (HubSpot → Marketplace → Slack), then build one CRM workflow: *when `last_call_at` is known or changes → post to the sales Slack
   channel* with deal name, grade, score, tier, headline, next step, blockers, owner, link.

   **No workflows on your plan?** HubSpot free and Starter can't post to Slack from a workflow
   (that needs Professional). Connect the Slack connector in Claude instead and record
   `card_route: slack-connector` and your sales channel in `crm-records` § Card route. `sales-intake` then posts the same card
   itself, right after the CRM write. Upgrade later and switch the route back.

**Check:** set `last_call_at` on a test deal by hand and the card appears in Slack. On the
connector route, ask Claude to post a test card for that deal instead.

## 3. First call, by hand

Paste a real transcript into Claude Code: *"process this call."* `sales-intake` matches the
deal, scores it, proposes each write and asks you to confirm. Read the scorecard against your
own sense of the call. If the score is wrong, fix `RUBRIC.md` or `PLAYBOOK.md`, not the output.

Do five calls this way before automating. The rubric will need tuning; it always does.

**No CRM connected yet?** Say *"score this call"* instead. `sales-call-scorer` runs on its own,
writes nothing, and you still learn whether the rubric fits your calls. Tick 3a on that.

## 4. Turn on the post-call routine

Follow `agents/postcall/README.md`. Create the Routine in the console UI with the repo and the
CRM, call recorder and Gmail connectors attached (plus Slack on the connector card route). Its prompt is three lines that point at the
runbook, so the procedure lives in git.

**Check:** after the next real call, a card lands within the hour, and
`agents/postcall/state/heartbeat.md` on branch `claude/postcall` shows the run.

## 5. The rest

- `agents/digest/` — Friday digest to Slack or a doc.
- `agents/keeper/` — daily hygiene: runs the checks, files tasks, keeps `NEEDS.md` honest.
- `.github/workflows/heartbeat-watch.yml` — alerts if a routine goes quiet. Add the
  `SLACK_WEBHOOK_URL` secret, and list only the routines you've turned on in its `AGENTS` line, or
  it alerts daily about the ones you haven't.
- `sessions/` hooks are already wired in `.claude/settings.json`: every new session starts with
  a summary of the last one.
- `ops/receivers/INBOUND.md` — book a demo → Clay-enriched lead → fit score → Slack card →
  deal. Includes the site snippet (`site/attribution.js`). Do it when you start running paid or
  outbound traffic; each sub-step ends with a check.
- `outbound/OUTBOUND.md` — target list in Clay → lemlist, warm vs cold rail, UTM tags the
  inbound card can read, click → LinkedIn connect (`ops/receivers/api/lemlist-click-CHANGE-ME.js`),
  and the daily call list. Do it after the inbound flow; a new sending domain needs two weeks of
  warm-up before the first campaign, so start that early.
- `close/CLOSE.md` — the close: Summary of Terms and Order Form generated from the deal and
  `commercial.md` (or a custom offer), a Gmail draft for you to send, the copy filed and tagged,
  then a draft HubSpot invoice on Closed Won. Needs `commercial.md` priced, your lawyer's Order
  Form, and a HubSpot private-app token (the connector refuses invoice writes).
- `TRICKS.md` — read once before you wire anything. Every gotcha there cost real time.
