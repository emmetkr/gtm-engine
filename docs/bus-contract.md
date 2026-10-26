# Bus contract — how agents share work

**One bus: the git remote.** Files are the messages. There are no agent-to-agent channels.

1. **Each agent writes on `claude/<name>`.** A person merges to `main`.
2. **Single writer per file.** A file has one owner after creation. Others file a task.
3. **A task is a message.** `tasks/<slug>.md` with `owner`, `blocked-on`, `done-when`.
4. **State is a file.** Cursors and heartbeats under `agents/<name>/state/`.
5. **Identity per commit.** Real per-agent name and email, passed with `git -c`. A prefix in the
   subject (`POSTCALL:`) makes the history greppable.
6. **Merge, never rebase or force.** History is the audit trail.
7. **External systems have one writer each** (see `agents/README.md` roster).
