# gtm-engine

A plug-and-play go-to-market system run by Claude Code agents. Clone it, fill in what your
company sells, connect your CRM and call recorder, and you have:

- **Call prep** before every meeting, built from your playbook and the deal's history.
- **Post-call automation**: the call ends, a transcript is scored 0 to 100 against your
  playbook, the CRM deal is updated, follow-up tasks are created, a follow-up email is drafted,
  and a card lands in your sales Slack channel. Nobody types anything.
- **A weekly pipeline digest** and deal-by-deal risk analysis.
- **A canon that stays true**: one file per fact, checks that catch drift, and an agent that
  keeps it clean.

It was extracted from a working B2B sales system that ran an enterprise motion, then stripped of
everything company-specific. What is left is the structure and the rules that kept it honest.

## The idea in one picture

```
                      KNOWLEDGE LAYER  (.claude/skills/, docs/)
          what is true and what to do: pricing, product, playbook, rubric
                                    │  read by
        ┌───────────────┬───────────┴───────┬──────────────────┐
        ▼               ▼                   ▼                  ▼
   OPERATOR         POSTCALL             DIGEST              KEEPER
   (you + Claude   (hourly routine:     (Friday routine:    (daily routine:
    Code, live)     score + write CRM)   pipeline roll-up)   hygiene, tasks)
        │               │                   │                  │
        └───────────────┴─────── git (the bus) ────────────────┘
                                    │
             CRM ── Slack ── call recorder ── email drafts ── enrichment
```

**Two layers.** Skills hold knowledge; agents do work and read the skills. An agent never
carries its own copy of a fact. When a fact changes you change one file and every agent picks it
up on its next run.

**Git is the bus.** Agents do not message each other. They write files on their own branches,
and the files are the messages. Every change is a commit, so you can always answer "what did we
believe on the 3rd, and who changed it."

## Quickstart (about an hour to first scored call)

1. **Clone and open in Claude Code.** `git clone … && cd gtm-engine && claude`
2. **Say "set me up".** Claude walks you through setup one step at a time. It interviews you,
   fills `company-context`, `product-context` and `commercial.md`, tells you exactly where to
   click for the steps it can't do, and checks each step before moving on. Stop whenever you
   like and say "continue setup" next time; progress is kept in `SETUP-PROGRESS.md`.
3. **Connect the stack.** At minimum: a CRM, a call recorder with a Claude connector, Slack and
   Gmail. See [STACK.md](STACK.md).
4. **Score a call by hand.** Paste a transcript and say *"process this call"*. That runs
   `sales-intake`, which scores, writes the deal, and drafts the follow-up. Confirm each write.
5. **Turn on the routines** once the interactive run is right: `agents/postcall`, then
   `agents/digest`, then `agents/keeper`.

Full walkthrough: [SETUP.md](SETUP.md).

## Where things are

| Path | What |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Instructions every agent loads. Your non-negotiables go here (derived copy) |
| [SETUP.md](SETUP.md) | First-day setup, in order |
| [STACK.md](STACK.md) | Recommended tools per layer, alternatives, and the gotchas we paid for |
| `.claude/skills/` | **Knowledge layer.** One folder per skill. Versioned like code |
| `agents/` | **Agent layer.** One runbook per scheduled agent, plus its state |
| [docs/architecture.md](docs/architecture.md) | How the pieces fit, and the six loops |
| [docs/non-negotiables.md](docs/non-negotiables.md) | The rules that cause real damage when broken. Single home |
| [docs/system-hygiene.md](docs/system-hygiene.md) | One source of truth, retire don't duplicate, worktrees |
| [docs/bus-contract.md](docs/bus-contract.md) | How agents share work through git |
| [docs/design-system.md](docs/design-system.md) | Who reads this, and are we asking them for something? |
| `clients/` | **Client evidence.** One folder per account. Permanent records |
| `client-facing/` | The only folder cleared to send to a client as is |
| `tasks/` | Work queue, one file per task, with an owner and a done-when |
| `NEEDS.md` | Open decisions and gaps. The only open-items list |
| `ops/` | Checks (`check-corpus.py`, `check-client-copy.py`) and webhook receivers |
| [ops/receivers/INBOUND.md](ops/receivers/INBOUND.md) | Book a demo → Clay enrichment → fit score → Slack card → deal |
| `site/attribution.js` | Website snippet: first-touch UTMs, Calendly handoff, hidden form fields |
| `sessions/` | Hooks that give every new Claude session a handoff from the last one |
| `archive/` | Retired documents with tombstones. Never loaded as truth |

## The skills

| Skill | Job |
|---|---|
| `company-context` | ICP, sale motion, buying roles, positioning, proof. Every sales skill reads it |
| `product-context` | What the product does and what state each part is in |
| `sales-playbook` | The stages, the calls, objections, and `commercial.md`, the one home for prices |
| `crm-records` | How contacts, companies and deals are created, and the stage ladder |
| `meeting-prep` | A plan to win the next meeting, per attendee |
| `sales-call-scorer` | Scores a call 0 to 100 against `RUBRIC.md` and `PLAYBOOK.md`. Evaluates only |
| `sales-intake` | The post-call entry point: match, score, write the deal, tier, tasks, follow-up draft |
| `call-debrief` | The leadership readout of one call |
| `pipeline-analysis` | Every open deal: health, the real blocker, one move |
| `weekly-exec-update` | The Friday cross-deal digest |
| `humanize-copy` | Strips AI tells from outgoing prose |

## License

MIT. Use it, fork it, sell with it.
