# client-facing/ — cleared to send

The only folder holding documents cleared to send to a client, partner or prospect as they are.
Anything not here is not cleared.

Before a send: `python3 ops/check-client-copy.py` (banned terms, retired names) and
`python3 ops/check-corpus.py` (figures only where they're allowed). Match every figure against
`commercial.md` by eye; `close/make-close-docs.py` does this for deal documents. After: tag and record
(`docs/versioning-client-copies.md`).

Deal documents built by `close/make-close-docs.py` live in `clients/<slug>/close/` and are cleared
to send once its guards pass and a person has read the PDF. See `close/CLOSE.md`.
