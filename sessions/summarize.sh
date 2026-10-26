#!/bin/bash
# Claude Code hook (SessionEnd): writes a Claude-authored handoff summary of the session
# and refreshes sessions/NEXT.md (open loops). Detaches so it survives the session closing.
# Manual run: sessions/summarize.sh --now <transcript.jsonl>
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_BIN="$(command -v claude || echo "$HOME/.local/bin/claude")"

if [ "${1:-}" = "--worker" ] || [ "${1:-}" = "--now" ]; then
  TP="${2:-}"
  [ -f "$TP" ] || exit 0
  SID=$(basename "$TP" .jsonl); SHORT=${SID:0:8}; DATE=$(date +%Y-%m-%d)
  COND=$(mktemp)
  jq -r '
    if .type=="user" and .isMeta != true then
      (.message.content | if type=="string" then "USER: "+.
       else "USER: "+([.[] | select(.type=="text") | .text] | join(" ")) end)
    elif .type=="assistant" then
      (.message.content | if type=="array" then ([.[] | select(.type=="text") | .text] | join(" ")) else "" end
       | if length>0 then "ASSISTANT: "+. else empty end)
    else empty end' "$TP" 2>/dev/null \
    | grep -v '^USER: *$' | grep -v 'system-reminder' | grep -vE '^USER:[[:space:]]*<' \
    | cut -c1-500 > "$COND"
  [ -s "$COND" ] || { rm -f "$COND"; exit 0; }
  PREV_NEXT=""
  [ -f "$DIR/NEXT.md" ] && PREV_NEXT=$(cat "$DIR/NEXT.md")
  OUT=$(cd /tmp && cat "$COND" | "$CLAUDE_BIN" -p --model haiku "Above is a condensed transcript of a coding session in a GTM system repo (USER/ASSISTANT lines, tool output omitted). You are a summarizer, not an agent: do NOT use any tools, do NOT write files, do NOT ask questions — reply with markdown text only. The reply is exactly two sections and nothing else:

## SUMMARY
Concrete decisions made, things built/deployed/configured (with real paths, URLs, ids), and anything the next session must know. Dense bullets, most important first, max 25 bullets.

## NEXT
Open loops only: promised or unfinished work, each one bullet with who owes it. Carry forward still-open items from the previous NEXT list below; drop anything the transcript shows completed.

Previous NEXT list:
$PREV_NEXT" 2>/dev/null)
  rm -f "$COND"
  [ -n "$OUT" ] || exit 0
  OUT=$(printf '%s\n' "$OUT" | awk '/^## SUMMARY/{f=1} f')
  [ -n "$OUT" ] || exit 0
  printf '%s\n\n_Session %s, summarized %s_\n' "$OUT" "$SHORT" "$(date '+%Y-%m-%d %H:%M')" > "$DIR/$DATE-$SHORT-summary.md"
  cp "$DIR/$DATE-$SHORT-summary.md" "$DIR/SUMMARY-LATEST.md"
  printf '%s\n' "$OUT" | awk '/^## NEXT/{f=1;next} f' > "$DIR/NEXT.md.tmp" && mv "$DIR/NEXT.md.tmp" "$DIR/NEXT.md"
  exit 0
fi

IN=$(cat)
TP=$(printf '%s' "$IN" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -n "$TP" ] || exit 0
nohup "$DIR/summarize.sh" --worker "$TP" >/dev/null 2>&1 &
exit 0
