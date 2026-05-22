#!/usr/bin/env bash
# install-qa-agents.sh
# Extracts the 4 QA agent definitions from qa-agents.md and writes each to
# .claude/agents/<name>.md in the current project.
#
# Reuses the orchestrator skill's extract-agent.py — same parsing logic as
# install-core-agents.sh and install-security-agents.sh.

set -euo pipefail

QA_SKILL_DIR="${HOME}/.claude/skills/exploratory-qa"
QA_SKILL_REF="${QA_SKILL_DIR}/references/qa-agents.md"

ORCH_SKILL_DIR="${HOME}/.claude/skills/prd-design-build-orchestrator"
EXTRACTOR="${ORCH_SKILL_DIR}/references/extract-agent.py"

if [[ ! -f "$QA_SKILL_REF" ]]; then
  echo "❌ QA agent definitions not found at $QA_SKILL_REF"
  echo "   Install the exploratory-qa skill first."
  exit 1
fi

if [[ ! -f "$EXTRACTOR" ]]; then
  echo "❌ Extractor not found at $EXTRACTOR"
  echo "   This script requires the prd-design-build-orchestrator skill to be"
  echo "   installed (it provides the extract-agent.py used here)."
  exit 1
fi

mkdir -p .claude/agents

QA_AGENTS=(
  qa-environment
  qa-flow-tester
  qa-consistency-checker
  qa-performance-prober
)

INSTALLED=0
FAILED=0

for agent in "${QA_AGENTS[@]}"; do
  out=".claude/agents/${agent}.md"
  if python3 "$EXTRACTOR" "$QA_SKILL_REF" "$agent" > "$out" 2>/tmp/extract-err.txt; then
    if [[ -s "$out" ]]; then
      echo "✓ Installed: $out"
      INSTALLED=$((INSTALLED + 1))
    else
      echo "❌ Empty output for $agent"
      cat /tmp/extract-err.txt
      rm -f "$out"
      FAILED=$((FAILED + 1))
    fi
  else
    echo "❌ Extraction failed for $agent"
    cat /tmp/extract-err.txt
    rm -f "$out"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "QA agents: ${INSTALLED} installed, ${FAILED} failed"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi

for agent in "${QA_AGENTS[@]}"; do
  f=".claude/agents/${agent}.md"
  if ! head -1 "$f" | grep -q '^---$'; then
    echo "❌ $f does not start with --- frontmatter"
    exit 1
  fi
done

echo "All QA agents validated (frontmatter present)."
