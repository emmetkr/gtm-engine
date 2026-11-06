# Commercial canon — what we sell and what it costs

**The only file that sets a figure.** Every price, rate, discount, seat cost and allowance is
authored here and nowhere else. Other files may restate a figure only where
`ops/checks.json` → `price_ok` allows it, and every restatement must match this file.

A new or changed figure lands here first, in the same commit as any surface that shows it.
The commit message names the change: `commercial: Pro tier $X → $Y (ruled by NAME)`.

**Last ruled:** YYYY-MM-DD by NAME

**Machine-read.** `close/make-close-docs.py` reads the §1 and §2 tables by their column names, so
keep the columns as they are. A billing variant (annual, quarterly) is its own row with its own
price. Everything written in §4 is printed as the payment terms on order forms, so leave §4
empty until it is ruled.

## §1 Offers

| Offer | Price | Billing | Includes |
|---|---|---|---|
| Trial | | | |
| Tier 1 | | | |
| Tier 2 | | | |

## §2 Add-ons

| Item | Price | Unit |
|---|---|---|

## §3 Discount rules

Who may approve what. A discount outside these rules is a custom offer and needs a named
approver.

## §4 Terms

<!-- Payment terms, contract length, cancellation. Printed on order forms as written. -->

## §5 Not yet decided

List anything a buyer might ask about that has no ruling. Each line also goes in `NEEDS.md`.
