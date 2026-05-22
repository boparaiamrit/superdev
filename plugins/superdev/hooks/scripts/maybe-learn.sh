#!/usr/bin/env bash
# maybe-learn.sh
# Runs on SubagentStop for specific agents. If the .frustration-queued flag is
# set OR the just-finished agent emitted a "LESSON:" line in its output OR the
# agent's verdict was a failure (REJECT / FAIL / drift > 1%), prints a marker
# telling the main session to dispatch learn-from-frustration.
#
# This script does NOT itself spawn an agent — agent spawning happens in the
# Claude Code session, not in shell hooks. The marker tells the session what
# to do next.

set -u
AGENT_NAME="${1:-unknown}"

REASON=""
QUEUE_FILE=".claude/memory/.frustration-queued"
LAST_OUTPUT_FILE=".claude/.last-subagent-output"

# Reason 1: frustration was queued by UserPromptSubmit hook
if [ -f "$QUEUE_FILE" ]; then
  REASON="user-correction"
  rm -f "$QUEUE_FILE"
fi

# Reason 2: the agent's output contained "LESSON:" (fix-applier convention)
if [ -z "$REASON" ] && [ -f "$LAST_OUTPUT_FILE" ]; then
  if grep -q "^LESSON:" "$LAST_OUTPUT_FILE" 2>/dev/null; then
    REASON="fix-pattern"
  fi
fi

# Reason 3: the agent reported a failure verdict
if [ -z "$REASON" ] && [ -f "$LAST_OUTPUT_FILE" ]; then
  if grep -qE "Verdict: (REJECT|FAIL|DEMO|BROKEN)|drift% > 1|REGRESSION found" "$LAST_OUTPUT_FILE" 2>/dev/null; then
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
