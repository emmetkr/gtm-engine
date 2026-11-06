# GTM system — agent instructions

<!-- Replace the placeholder on the line below with your company name, on that line only. Keep
     this file short: it loads into every session. -->

This repo is COMPANY's go-to-market system: the knowledge layer (skills) and the agent layer
that runs on it.

## First run

If the opening line above still holds the placeholder name, or `SETUP-PROGRESS.md` has an open
`[ ]` box in steps 0 to 3a (a deferred `[~]` box does not count), the engine is not set up yet. At the start of the session, before anything else, tell the user
that in one sentence and offer to walk them through setup. If they agree, run the `setup` skill.
If they ask for something else first, help with that, and mention that answers will be generic
until setup step 1 is done.

## The architecture

**Knowledge layer — `.claude/skills/` and `docs/`.** What is true and what to do. Read whole.
**Agent layer — `agents/`.** One runbook per scheduled agent. Agents read the skills; they never
embed knowledge of their own.

**One source of truth per fact.** A fact lives in one file; everything else points at it. The
same fact written in two places is a defect even when the copies agree, because they will stop
agreeing. Doctrine: `docs/system-hygiene.md`.

**Two authorities, two questions.**

| Question | Authority |
|---|---|
| What we sell, and what it costs | `.claude/skills/sales-playbook/references/commercial.md` |
| What exists, and what state it is in | `.claude/skills/product-context/SKILL.md` |

On a number, `commercial.md` wins.

**Two corpora.** `.claude/skills/` and `docs/` hold company knowledge: stable, corrected in
place. `clients/` holds client evidence: one folder per account, a permanent record, annotated
rather than corrected. A client record cites a price; it never states one.

## Non-negotiables

**Source: `docs/non-negotiables.md`.** The list below is a derived copy, kept here because this
file loads automatically. Change a rule there first, then here.

1. **Never quote a price** without reading `commercial.md`. A new or changed figure lands in
   `commercial.md` first.
2. **Never state a capability** the product reference does not support, and never describe a
   planned feature as live.
3. **Never edit anything already in a client's hands** unless the change cannot alter what they
   believe was offered. A factual change is a reissue.
4. **Never send email, contracts or client messages on a person's behalf.** Agents write drafts.
5. **Never move a deal stage unattended.** Agents propose; a person moves it.
6. **Never guess a fact about a prospect.** It comes from enrichment or their own site, or it
   is cut.
7. **`archive/` is not part of the dataset.** Search it when hunting a past decision; never load
   it as truth.
<!-- Add your own: banned words, names you never say, legal lines. Each gets a ruling and a date. -->

## Working style

- Before writing any document, answer: *who reads this, and are we asking them for something?*
  `docs/design-system.md` routes the answer.
- Read the relevant skill before producing client-facing output. Memory of this domain drifts.
- When a skill turns out to be wrong, fix the skill in the same session and commit with a
  message that says what changed and why. Do not work around it.
- When something is unresolved, say so and add it to `NEEDS.md`. Do not pick a plausible answer.
- Run `python3 ops/check-corpus.py` before merging and `python3 ops/check-client-copy.py`
  before anything goes to a client.

## Git

- Skills are versioned like code. A pricing change must be findable from its commit message.
- Tag whenever something goes to a client: `client/<name>-<YYYY-MM-DD>`.
- Several sessions may run at once. Never commit, rebase or switch branches in a shared
  checkout: `git worktree add`, work there, push, remove. Exception: setup, run alone in a fresh
  clone, commits in place.
- Scheduled agents push only to `claude/<agent>` branches, never to `main`.
