# Versioning and client copies

**Anything delivered to a client is permanent.**

1. Before sending, run `python3 ops/check-client-copy.py` and, if it carries a number,
   `python3 ops/check-corpus.py`.
2. Send from `client-facing/` only.
3. Tag the commit: `git tag client/<name>-<YYYY-MM-DD>` and push the tag. That tag answers
   "what did we tell them in August."
4. Record the send in `clients/<slug>/record.md` → Artifact record.
5. A later factual change is a **reissue**: new file, new tag, new record row. Never a silent
   edit to the old one. A typo fix that cannot change what they believe was offered is allowed.
