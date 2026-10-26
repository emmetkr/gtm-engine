#!/bin/bash
# Claude Code hook (SessionStart): injects the handoff into the new session's context —
# open loops first, then the last session's summary, then the tail of the raw record.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
# If the previous session's summarizer is still running (immediate /clear or restart),
# wait for it — up to 30s — so we inject the fresh handoff, not the stale one.
for _ in $(seq 1 30); do
  pgrep -f "summarize.sh --worker" >/dev/null 2>&1 || break
  sleep 1
done
BODY=""
# Standing priority list (hand-maintained; not rewritten by the summarizer).
if [ -f "$DIR/PRIORITIES.md" ] && [ -s "$DIR/PRIORITIES.md" ]; then
  BODY="## Priorities (sessions/PRIORITIES.md — hand-maintained, read first)
$(cat "$DIR/PRIORITIES.md")

"
fi
if [ -f "$DIR/NEXT.md" ] && [ -s "$DIR/NEXT.md" ]; then
  BODY="$BODY## Open loops (sessions/NEXT.md)
$(cat "$DIR/NEXT.md")

"
fi
if [ -f "$DIR/SUMMARY-LATEST.md" ]; then
  BODY="$BODY$(cat "$DIR/SUMMARY-LATEST.md")

"
fi
if [ -f "$DIR/LATEST.md" ]; then
  BODY="$BODY## Raw record tail (sessions/LATEST.md)
$(tail -25 "$DIR/LATEST.md")"
fi
[ -n "$BODY" ] || exit 0
printf '%s' "$BODY" | jq -Rs '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:("Handoff from previous coding sessions (auto-generated; sessions/ holds full history):\n\n"+.)}}'
