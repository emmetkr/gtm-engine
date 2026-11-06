# Non-negotiables

The rules that cause real damage when broken. **This is the single home.** `CLAUDE.md` carries
a derived copy; change a rule here first, then there, in the same commit.

Each rule records who ruled and when. Rulings change; when one is reversed, strike it here with
the reversal's date and owner, so the history stays readable.

## How to add one

```
## N. <the rule, as an imperative>
`[RULED by NAME, YYYY-MM-DD]`
Why: <the incident or risk that prompted it>
What it does not touch: <the boundary, so it is not over-applied>
Checked by: <the script, or "by hand">
```

## 1. Never quote a price without reading `commercial.md`
`[RULED by NAME, YYYY-MM-DD]`
Why: one pricing model living in three files that disagreed is how a client gets two quotes.
Figures may be *restated* on the surfaces listed in `ops/checks.json` → `price_ok`; they are
*set* only in `commercial.md`.
Checked by: `ops/check-corpus.py` (figures in the wrong place).

## 2. Never claim a capability the product reference does not list as live
`[RULED by NAME, YYYY-MM-DD]`

## 3. Never edit anything already in a client's hands
`[RULED by NAME, YYYY-MM-DD]`
Unless the change cannot alter what they believe was offered. Otherwise reissue it, tag it
`client/<name>-<date>`, and record both in `clients/<slug>/record.md`.

## 4. Agents never send
`[RULED by NAME, YYYY-MM-DD]`
Email, Slack to clients, contracts. Agents draft; a person sends.

## 5. Never move a deal stage unattended
`[RULED by NAME, YYYY-MM-DD]`
Agents propose a stage change in the recap; a person moves it. One exception: the signature
receiver moves a deal to Closed Won when DocuSign reports every signer has signed. That is the
buyer's signature, not an agent's judgment, and it moves nothing else.

## 6. Never guess a fact about a prospect
`[RULED by NAME, YYYY-MM-DD]`
From enrichment or their own site, or cut.

## 7. `archive/` is not part of the dataset
`[RULED by NAME, YYYY-MM-DD]`
Load versus look: never load it as truth; do search it when hunting a past decision.

<!-- Add your own below. Common ones: a partner or vendor never named; a term never used; a
     claim legal has not cleared; what is never documented in the repo at all. -->
