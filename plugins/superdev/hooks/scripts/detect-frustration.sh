#!/usr/bin/env bash
# detect-frustration.sh  (UserPromptSubmit hook)
#
# Detects user-frustration / correction signals and ACTUALLY closes the
# self-learning loop's trigger half:
#   1. records the signal to .claude/memory/superdev-learned/.pending.log
#   2. injects an instruction into the model's context (via additionalContext)
#      telling it to dispatch learn-from-frustration and write a lesson file.
#
# Before, this script only touched a queue file + echoed to stderr, so the
# instruction never reached the model and no lesson was ever written. The
# detection set is also broadened to catch the real signals the old regex
# missed (profanity, lint-suppression vetoes, "keep it / don't remove",
# fake-data callouts, repeated terse "fix"/"still broken").
#
# Exits 0 always — hooks must never block user prompts.

set -u
. "$(dirname "$0")/_superdev-lib.sh" 2>/dev/null || true

# --- Resolve PROMPT (stdin JSON .prompt preferred; env/arg fallbacks) ------
PROMPT=""
if [ ! -t 0 ]; then
  JSON="$(cat 2>/dev/null || true)"
  [ -n "${JSON:-}" ] && PROMPT="$(sd_json_field "$JSON" '.prompt')"
  [ -z "$PROMPT" ] && [ -n "${JSON:-}" ] && PROMPT="$(sd_json_field "$JSON" '.user_prompt')"
fi
[ -z "$PROMPT" ] && PROMPT="${CLAUDE_USER_PROMPT:-}"
[ -z "$PROMPT" ] && PROMPT="${1:-}"
[ -z "$PROMPT" ] && exit 0

PROMPT_SHORT="${PROMPT:0:500}"
PROMPT_LOWER="$(printf '%s' "$PROMPT_SHORT" | tr '[:upper:]' '[:lower:]')"

TRIGGER=""

# Strong signal 1 — short emphatic correction (whole message ≤ 40 chars)
if [ "${#PROMPT_SHORT}" -le 40 ]; then
  case "$PROMPT_LOWER" in
    no|no.|no!|stop|stop.|stop!|nope|wrong|wrong.|"don't"|"don't do that"|undo|revert|"that's wrong"|fix|"fix it"|"fix this"|"still broken"|"not working"|"same issue"|"same problem")
      TRIGGER="short-emphatic" ;;
  esac
fi

# Strong signal 2 — repeat-correction / "you broke it" markers (any length)
if [ -z "$TRIGGER" ] && printf '%s' "$PROMPT_LOWER" | grep -qE "i (already )?(told|said)|for the (second|third|fourth|fifth) time|stop ignoring|why (are you|do you keep|did you)|i (just )?said (not to|don'\''t)|you broke (it|the)|this is broken|this isn'\''t working|nothing works|again\?|still (not|broken|wrong|the same)|keep (doing|breaking|changing)"; then
  TRIGGER="repeat-correction"
fi

# Strong signal 3 — profanity / sharp dissatisfaction (the real-world signal the old regex missed)
if [ -z "$TRIGGER" ] && printf '%s' "$PROMPT_LOWER" | grep -qE "what the (fuck|hell)|wtf|this sucks|garbage|useless|terrible|awful|that'\''s not what i (asked|wanted|said)"; then
  TRIGGER="sharp-dissatisfaction"
fi

# Strong signal 4 — lint/type SUPPRESSION veto (user forbidding the shortcut)
if [ -z "$TRIGGER" ] && printf '%s' "$PROMPT_LOWER" | grep -qE "do ?n'?t (do |use |add )?.*(disable|suppress|ignore|warn|as any)|no (inline )?(eslint|ts).?(disable|ignore)|fix (it|the|every|its)? ?.*(root cause|properly|professionally)|no suppress|don'\''t (downgrade|disable)"; then
  TRIGGER="suppression-veto"
fi

# Strong signal 5 — fake/mock data callout (demo-vs-product)
if [ -z "$TRIGGER" ] && printf '%s' "$PROMPT_LOWER" | grep -qE "fake data|mock data|don'\''t (show|use) (fake|mock|dummy)|not real|still (mock|fake|dummy|hardcoded)|hardcoded|why (is|are).*(0|zero|empty)|placeholder"; then
  TRIGGER="fake-data-callout"
fi

# Strong signal 6 — "keep it / don't remove / don't change" (preserve-intent correction)
if [ -z "$TRIGGER" ] && printf '%s' "$PROMPT_LOWER" | grep -qE "keep (the|it|them|that).*(don'\''t remove| stay)|don'\''t (remove|delete|change|touch)|i (told|asked) you (to keep|not to)|put (it|them) back|bring (it|them) back"; then
  TRIGGER="preserve-intent"
fi

[ -z "$TRIGGER" ] && exit 0

# --- Record + inject -------------------------------------------------------
PROJ="$(sd_project_dir)"
DIR="$PROJ/.claude/memory/superdev-learned"
mkdir -p "$DIR" 2>/dev/null || true
# one queued line per signal (best-effort; never fail the hook)
{ printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)" "$TRIGGER" "$(printf '%s' "$PROMPT_SHORT" | tr '\t\n' '  ')" >> "$DIR/.pending.log"; } 2>/dev/null || true
# legacy flag (kept so maybe-learn.sh can also consume it on SubagentStop)
touch "$PROJ/.claude/memory/.frustration-queued" 2>/dev/null || true

echo "[superdev-self-learning] ${TRIGGER} detected" >&2

sd_emit_context "UserPromptSubmit" "⚠ superdev-self-learning: a user-frustration signal (\"${TRIGGER}\") was detected in this message. After you address the user's request, DISPATCH the learn-from-frustration agent and write a lesson to .claude/memory/superdev-learned/<topic>.md (frontmatter: type=feedback) capturing the rule + why + how to apply it, so this class of mistake is not repeated. Then remove the corresponding line from .claude/memory/superdev-learned/.pending.log. Do this even if the fix feels obvious — the lesson is what immunizes future dispatches."

exit 0
