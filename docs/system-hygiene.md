# System hygiene

Sales moves fast and offers change. When something changes, **update the canon and retire the
old.** Never leave a stale version standing where an agent can read it.

## Rules

1. **One source of truth per fact.** Two copies that agree today will disagree next month.
2. **Update in place; git is the archive.** No `v2-final-FINAL` files.
3. **Retire whole documents to `archive/`** with a tombstone: retired date, why, superseded by.
4. **Delivered artifacts are never retired.** What went to a client is a permanent record of
   what was represented.
5. **Reach-back.** A material change to the offer makes every unconverted prospect who saw the
   old one a re-engagement candidate. KEEPER files the tasks.
6. **One session per checkout.** Several Claude sessions share a working tree and one HEAD. A
   session that commits without checking the branch commits onto someone else's. Use
   `git worktree add` for any write; read with `git show <ref>:<path>`.
7. **Checks over prose.** A rule that can be checked mechanically gets a check in `ops/`. Prose
   rules do not survive a sweep.

## Staleness signals

- A file with a "last updated" header older than the thing it describes.
- A pointer to a moved or archived file.
- A figure outside `commercial.md` that no longer matches it.
- A task with no owner, or blocked on something already resolved.
- A rendering (PDF, HTML) older than its source.
