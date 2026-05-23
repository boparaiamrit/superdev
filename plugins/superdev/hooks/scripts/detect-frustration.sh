#!/usr/bin/env bash
# detect-frustration.sh
#
# Reads the user's submitted prompt and tests it against the strong-signal
# frustration patterns from
#   skills/superdev-self-learning/references/frustration-patterns.md
#
# Input resolution order (Claude Code passes hook data as JSON on stdin;
# env vars and $1 are fallbacks for older/non-standard callers):
#   1. stdin JSON  → .prompt    (preferred, parsed via jq or python3)
#   2. $CLAUDE_USER_PROMPT       (legacy env var; may be unset on Windows)
#   3. $1                        (manual invocation)
#
# On match: touch .claude/memory/.frustration-queued so the next SubagentStop
# hook (maybe-learn.sh) knows to dispatch learn-from-frustration.
#
# Exits 0 always — hooks must never block user prompts.

set -u

# --- Resolve PROMPT --------------------------------------------------------
PROMPT=""

# 1. stdin JSON (Claude Code's documented protocol)
if [ ! -t 0 ]; then
  JSON="$(cat 2>/dev/null || true)"
  if [ -n "$JSON" ]; then
    if command -v jq >/dev/null 2>&1; then
      PROMPT="$(printf '%s' "$JSON" | jq -r '.prompt // empty' 2>/dev/null || true)"
    elif command -v python3 >/dev/null 2>&1; then
      PROMPT="$(printf '%s' "$JSON" | python3 -c "import json,sys
try:
  d=json.load(sys.stdin)
  print(d.get('prompt') or d.get('user_prompt') or '')
except Exception:
  pass" 2>/dev/null || true)"
    fi
  fi
fi

# 2. Env var fallback
[ -z "$PROMPT" ] && PROMPT="${CLAUDE_USER_PROMPT:-}"

# 3. Argument fallback (manual / test invocation)
[ -z "$PROMPT" ] && PROMPT="${1:-}"

# Nothing to inspect — silent exit
[ -z "$PROMPT" ] && exit 0

# --- Detection -------------------------------------------------------------
PROMPT_SHORT="${PROMPT:0:500}"
PROMPT_LOWER="$(printf '%s' "$PROMPT_SHORT" | tr '[:upper:]' '[:lower:]')"

queue() {
  mkdir -p .claude/memory 2>/dev/null
  touch .claude/memory/.frustration-queued 2>/dev/null
  echo "[superdev-self-learning] $1 detected" >&2
}

# Strong signal 1: short emphatic correction (whole message ≤ 40 chars)
if [ "${#PROMPT_SHORT}" -le 40 ]; then
  case "$PROMPT_LOWER" in
    no|no.|no!|stop|stop.|stop!|nope|wrong|wrong.|"don't"|"don't do that"|undo|revert|"that's wrong")
      queue "short-emphatic frustration"
      exit 0
      ;;
  esac
fi

# Strong signal 2: "I already told you" markers (any length)
if printf '%s' "$PROMPT_LOWER" | grep -qE 'i (already )?(told|said)|for the (second|third|fourth|fifth) time|stop ignoring|why (are you|do you keep)|i (just )?said (not to|don'\''t)|you broke (it|the)|this is broken|this isn'\''t working'; then
  queue "repeat-correction marker"
  exit 0
fi

# Strong signal 3: revert announcements
if printf '%s' "$PROMPT_LOWER" | grep -qE "i('m| am)? going to revert|rolling? this back|needs to be undone"; then
  queue "revert announcement"
  exit 0
fi

# No match — silent exit
exit 0
