#!/usr/bin/env bash
# maybe-learn.sh
#
# Runs on SubagentStop for fix-applier | regression-verifier |
# design-fidelity-auditor | audit-synthesizer.
#
# Prints a marker if learn-from-frustration should be dispatched. Three
# triggers:
#   1. .claude/memory/.frustration-queued exists (set by detect-frustration.sh)
#   2. The just-finished agent's output contained a "LESSON:" line
#   3. The agent's output contained a failure verdict (REJECT / FAIL / drift)
#
# Input resolution (Claude Code's documented protocol is JSON on stdin):
#   AGENT_NAME    ← .subagent_name || .subagent_type || $CLAUDE_SUBAGENT_NAME || $1 || "unknown"
#   AGENT_OUTPUT  ← .tool_response.output || .output || (empty)
#
# This script does NOT itself spawn an agent — agent dispatch happens in the
# Claude Code session. The marker tells the session what to do next.
#
# Exits 0 always — hooks must never block subagent transitions.

set -u

# --- Resolve AGENT_NAME and AGENT_OUTPUT ----------------------------------
AGENT_NAME=""
AGENT_OUTPUT=""

if [ ! -t 0 ]; then
  JSON="$(cat 2>/dev/null || true)"
  if [ -n "$JSON" ]; then
    if command -v jq >/dev/null 2>&1; then
      AGENT_NAME="$(printf '%s' "$JSON" | jq -r '.subagent_name // .subagent_type // empty' 2>/dev/null || true)"
      AGENT_OUTPUT="$(printf '%s' "$JSON" | jq -r '.tool_response.output // .output // empty' 2>/dev/null || true)"
    elif command -v python3 >/dev/null 2>&1; then
      AGENT_NAME="$(printf '%s' "$JSON" | python3 -c "import json,sys
try:
  d=json.load(sys.stdin)
  print(d.get('subagent_name') or d.get('subagent_type') or '')
except Exception:
  pass" 2>/dev/null || true)"
      AGENT_OUTPUT="$(printf '%s' "$JSON" | python3 -c "import json,sys
try:
  d=json.load(sys.stdin)
  tr=d.get('tool_response') or {}
  print(tr.get('output') if isinstance(tr,dict) else d.get('output') or '')
except Exception:
  pass" 2>/dev/null || true)"
    fi
  fi
fi

[ -z "$AGENT_NAME" ] && AGENT_NAME="${CLAUDE_SUBAGENT_NAME:-}"
[ -z "$AGENT_NAME" ] && AGENT_NAME="${1:-unknown}"

# --- Decide trigger reason -------------------------------------------------
REASON=""
QUEUE_FILE=".claude/memory/.frustration-queued"

# Reason 1: frustration was queued by UserPromptSubmit hook
if [ -f "$QUEUE_FILE" ]; then
  REASON="user-correction"
  rm -f "$QUEUE_FILE" 2>/dev/null
fi

# Reason 2: LESSON: line in agent output (fix-applier convention)
if [ -z "$REASON" ] && [ -n "$AGENT_OUTPUT" ]; then
  if printf '%s' "$AGENT_OUTPUT" | grep -q "^LESSON:" 2>/dev/null; then
    REASON="fix-pattern"
  fi
fi

# Reason 3: failure verdict in agent output
if [ -z "$REASON" ] && [ -n "$AGENT_OUTPUT" ]; then
  if printf '%s' "$AGENT_OUTPUT" | grep -qE "Verdict: (REJECT|FAIL|DEMO|BROKEN)|drift% > 1|REGRESSION found" 2>/dev/null; then
    case "$AGENT_NAME" in
      regression-verifier)        REASON="regression-rejected" ;;
      design-fidelity-auditor)    REASON="drift-failed" ;;
      audit-synthesizer)          REASON="audit-pattern" ;;
      *)                          REASON="verifier-failed" ;;
    esac
  fi
fi

if [ -n "$REASON" ]; then
  echo "[superdev-self-learning] Queue: dispatch learn-from-frustration with triggered_by=${REASON} after agent ${AGENT_NAME}"
fi

exit 0
