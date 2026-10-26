# sessions/ — memory between Claude Code sessions

Three hooks, wired in `.claude/settings.json`:

| Hook | Script | Does |
|---|---|---|
| Stop | `save.sh` | Writes `YYYY-MM-DD-<id>.md`: branch, working tree, recent commits, what was asked |
| SessionEnd | `summarize.sh` | Has a small model write a SUMMARY and a NEXT (open loops) list |
| SessionStart | `context.sh` | Injects `PRIORITIES.md`, `NEXT.md` and the last summary into the new session |

`PRIORITIES.md` is yours: a hand-written ordered list that every session reads first. Records
are gitignored; the scripts are tracked. Needs `jq`.
