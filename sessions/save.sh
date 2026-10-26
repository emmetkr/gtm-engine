#!/bin/bash
# Claude Code hook: writes a record of the current coding session into sessions/.
# Fired on Stop (async), so the record stays current even if a session dies abruptly.
# Reads the hook's JSON on stdin; safe to run manually: echo '{}' | sessions/save.sh
set -u
IN=$(cat)
SID=$(printf '%s' "$IN" | jq -r '.session_id // "manual"' 2>/dev/null || echo manual)
TP=$(printf '%s' "$IN" | jq -r '.transcript_path // empty' 2>/dev/null)
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$DIR/.."
DATE=$(date +%Y-%m-%d)
SHORT=${SID:0:8}
F="$DIR/$DATE-$SHORT.md"
{
  echo "# Session $DATE · $SHORT"
  echo
  echo "- Last saved: $(date '+%Y-%m-%d %H:%M')"
  echo "- Session id: $SID"
  echo "- Branch: $(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo n/a)"
  echo
  echo "## Working tree at last save"
  echo '```'
  git -C "$REPO" status --porcelain 2>/dev/null | head -20
  echo '```'
  echo
  echo "## Recent commits"
  echo '```'
  git -C "$REPO" log --oneline -5 2>/dev/null
  echo '```'
  if [ -n "$TP" ] && [ -f "$TP" ]; then
    echo
    echo "## What was asked this session (user messages, oldest first)"
    jq -r 'select(.type=="user" and .isMeta != true) | .message.content
           | if type=="string" then .
             else ([.[] | select(.type=="text") | .text] | join(" ")) end' "$TP" 2>/dev/null \
      | grep -v '^[[:space:]]*$' | grep -v 'system-reminder' | grep -v '^\[Image' \
      | grep -vE '^[[:space:]]*<' | grep -v 'task-notification' \
      | tail -40 | cut -c1-240 | sed 's/^/- /'
  fi
} > "$F.tmp" && mv "$F.tmp" "$F"
cp "$F" "$DIR/LATEST.md"
exit 0
