#!/usr/bin/env bash
# maybe-learn.sh  (SubagentStop hook)
#
# Runs when one of the real roster agents that produce verdicts/fixes stops.
# Records a learnable signal to .claude/memory/superdev-learned/.pending.log
# (consumed by superdev-session-start.sh and detect-frustration.sh's injection)
# and surfaces a dispatch instruction to the orchestrator via additionalContext.
#
# Triggers:
#   1. .claude/memory/.frustration-queued exists (set by detect-frustration.sh)
#   2. the agent's output contains a "LESSON:" line (fix-applier convention)
#   3. the agent's output contains a failure verdict (REJECT / FAIL / DEMO / drift)
#
# NOTE: the SubagentStop matcher in hooks.json was previously pinned to four
# agent names that are NOT in the roster, so this never fired. It now matches
# the real builders/verifiers (backend-module-builder, frontend-module-builder,
# security-fixer, integration-tester, ui-auditor, qa-flow-tester, …).
#
# Exits 0 always — never block a subagent transition.

set -u
. "$(dirname "$0")/_superdev-lib.sh" 2>/dev/null || true

AGENT_NAME=""; AGENT_OUTPUT=""
if [ ! -t 0 ]; then
  JSON="$(cat 2>/dev/null || true)"
  if [ -n "${JSON:-}" ]; then
    AGENT_NAME="$(sd_json_field "$JSON" '.subagent_name')"
    [ -z "$AGENT_NAME" ] && AGENT_NAME="$(sd_json_field "$JSON" '.subagent_type')"
    AGENT_OUTPUT="$(sd_json_field "$JSON" '.tool_response.output')"
    [ -z "$AGENT_OUTPUT" ] && AGENT_OUTPUT="$(sd_json_field "$JSON" '.output')"
  fi
fi
[ -z "$AGENT_NAME" ] && AGENT_NAME="${CLAUDE_SUBAGENT_NAME:-}"
[ -z "$AGENT_NAME" ] && AGENT_NAME="${1:-unknown}"

PROJ="$(sd_project_dir)"
DIR="$PROJ/.claude/memory/superdev-learned"
QUEUE_FILE="$PROJ/.claude/memory/.frustration-queued"

REASON=""
if [ -f "$QUEUE_FILE" ]; then REASON="user-correction"; rm -f "$QUEUE_FILE" 2>/dev/null || true; fi
if [ -z "$REASON" ] && [ -n "$AGENT_OUTPUT" ] && printf '%s' "$AGENT_OUTPUT" | grep -q "^LESSON:" 2>/dev/null; then
  REASON="fix-pattern"
fi
if [ -z "$REASON" ] && [ -n "$AGENT_OUTPUT" ] && printf '%s' "$AGENT_OUTPUT" | grep -qE "Verdict: (REJECT|FAIL|DEMO|BROKEN)|drift% > 1|drift > 1%|REGRESSION found|[0-9]+ (P0|critical|high) " 2>/dev/null; then
  case "$AGENT_NAME" in
    regression-verifier|conversion-verifier) REASON="regression-rejected" ;;
    design-fidelity-auditor)                 REASON="drift-failed" ;;
    audit-synthesizer|gap-auditor)           REASON="audit-pattern" ;;
    *)                                       REASON="verifier-failed" ;;
  esac
fi

[ -z "$REASON" ] && exit 0

mkdir -p "$DIR" 2>/dev/null || true
{ printf '%s\t%s\t(after %s)\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)" "$REASON" "$AGENT_NAME" >> "$DIR/.pending.log"; } 2>/dev/null || true

sd_emit_context "SubagentStop" "🧠 superdev-self-learning: a learnable signal (triggered_by=${REASON}, after ${AGENT_NAME}) was recorded. Dispatch the learn-from-frustration agent and write .claude/memory/superdev-learned/<topic>.md before declaring this work done, then clear the matching line in .pending.log."
exit 0
