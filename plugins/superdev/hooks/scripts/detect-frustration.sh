#!/usr/bin/env bash
# detect-frustration.sh
# Reads the user's submitted prompt from $1 and tests it against the
# strong-signal frustration patterns from
# skills/superdev-self-learning/references/frustration-patterns.md.
#
# On match: touch .claude/memory/.frustration-queued so the next SubagentStop
# hook knows to dispatch learn-from-frustration.
#
# Exits 0 always (hooks should not block user prompts).

set -u
PROMPT="${1:-}"

# Cap to first 500 chars — long prompts are rarely pure frustration markers
PROMPT_SHORT="${PROMPT:0:500}"
PROMPT_LOWER="$(printf '%s' "$PROMPT_SHORT" | tr '[:upper:]' '[:lower:]')"

# Strong signal 1: short emphatic correction (whole message ≤ 40 chars)
if [ "${#PROMPT_SHORT}" -le 40 ]; then
  case "$PROMPT_LOWER" in
    no|no.|no!|stop|stop.|stop!|nope|wrong|wrong.|"don't"|"don't do that"|undo|revert|"that's wrong")
      mkdir -p .claude/memory
      touch .claude/memory/.frustration-queued
      echo "[superdev-self-learning] short-emphatic frustration detected" >&2
      exit 0
      ;;
  esac
fi

# Strong signal 2: "I already told you" markers (any length)
if printf '%s' "$PROMPT_LOWER" | grep -qE 'i (already )?(told|said)|for the (second|third|fourth|fifth) time|stop ignoring|why (are you|do you keep)|i (just )?said (not to|don'\''t)|you broke (it|the)|this is broken|this isn'\''t working'; then
  mkdir -p .claude/memory
  touch .claude/memory/.frustration-queued
  echo "[superdev-self-learning] repeat-correction marker detected" >&2
  exit 0
fi

# Strong signal 3: revert announcements
if printf '%s' "$PROMPT_LOWER" | grep -qE "i('m| am)? going to revert|rolling? this back|needs to be undone"; then
  mkdir -p .claude/memory
  touch .claude/memory/.frustration-queued
  echo "[superdev-self-learning] revert announcement detected" >&2
  exit 0
fi

# No match — silent exit. False negatives are fine; false positives create noise.
exit 0
