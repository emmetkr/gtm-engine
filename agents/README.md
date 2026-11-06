# Agents

Each agent is a **runbook in git plus a schedule**. The schedule's prompt is three lines: "you
are X; read `agents/<name>/RUNBOOK.md` and do exactly what it says; then stop." The procedure is
reviewed in a diff and changed by editing a file, not a cron job nobody can see.

## Roster

| Agent | Kind | Runs | Owns (sole writer) | Never touches |
|---|---|---|---|---|
| **OPERATOR** | You in Claude Code | when you open it | whatever you ask | — |
| **POSTCALL** | Cloud Routine | hourly | CRM deals/tasks in the sales pipeline, `agents/postcall/state/` | `clients/`, stages, email send, Slack (except the card on the `slack-connector` route) |
| **DIGEST** | Cloud Routine | Fridays | `agents/digest/state/`, the Friday doc | the CRM (read only) |
| **KEEPER** | Cloud Routine | daily | `clients/`, `tasks/`, `NEEDS.md`, `archive/` moves | the CRM, `client-facing/` sends |

**One writer per surface.** Two agents writing the same object is how duplicates and silent
overwrites happen. When an agent finds something outside its surface, it files a `tasks/` item
for the owner.

## Rules every scheduled agent follows

1. **Fresh container, state in the repo.** Nothing lives in `~`. Cursors and heartbeats are files
   under `agents/<name>/state/`.
2. **Get current first.** Start from `claude/<name>` if it is ahead of `main`, merge `main` in,
   never rebase, never force-push.
3. **Identity per commit**, never in repo config:
   `git -c user.name=POSTCALL -c user.email=postcall@example.com commit`. Subject prefix
   `POSTCALL:`. `git log --grep='^POSTCALL:'` is its history.
4. **Push to `claude/<name>` only.** A person merges to `main`.
5. **Heartbeat every run,** even when there was nothing to do. The watchdog
   (`.github/workflows/heartbeat-watch.yml`) reads it from somewhere the agent is not.
6. **A flag for a human is a task where they work** (a CRM task, a Slack mention), not a line in
   a heartbeat file nobody opens.
7. **Missing tool → record it and stop.** Do not improvise another route to the data.
8. **Agents propose; people decide.** Stage moves, sends, merges, deletes and anything with
   `--apply` are human.

## Adding an agent

Copy `agents/digest/` (the simplest), write its may / may-not list first, give it one surface,
add its heartbeat to the watchdog, create the Routine in the console with the repo and only the
connectors it needs.
