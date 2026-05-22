#!/usr/bin/env bash
# install-core-agents.sh
# Extracts the 9 core agent definitions from agent-definitions.md and writes
# each to .claude/agents/<name>.md in the current project.
#
# Run from the project root after the prd-design-build-orchestrator skill is
# installed. The orchestrator invokes this in Phase A.1.

set -euo pipefail

SKILL_DIR="${HOME}/.claude/skills/prd-design-build-orchestrator"
SKILL_REF="${SKILL_DIR}/references/agent-definitions.md"
EXTRACTOR="${SKILL_DIR}/references/extract-agent.py"

if [[ ! -f "$SKILL_REF" ]]; then
  echo "❌ Agent definitions not found at $SKILL_REF"
  echo "   Install the prd-design-build-orchestrator skill first."
  exit 1
fi

if [[ ! -f "$EXTRACTOR" ]]; then
  echo "❌ Extractor script not found at $EXTRACTOR"
  exit 1
fi

mkdir -p .claude/agents

CORE_AGENTS=(
  prd-analyst
  design-inventory
  gap-auditor
  plan-architect
  monorepo-bootstrapper
  contracts-author
  backend-module-builder
  frontend-module-builder
  ui-auditor
  integration-tester
)

INSTALLED=0
FAILED=0

for agent in "${CORE_AGENTS[@]}"; do
  out=".claude/agents/${agent}.md"
  if python3 "$EXTRACTOR" "$SKILL_REF" "$agent" > "$out" 2>/tmp/extract-err.txt; then
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
echo "Core agents: ${INSTALLED} installed, ${FAILED} failed"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi

# Validate every installed file starts with frontmatter
for agent in "${CORE_AGENTS[@]}"; do
  f=".claude/agents/${agent}.md"
  if ! head -1 "$f" | grep -q '^---$'; then
    echo "❌ $f does not start with --- frontmatter"
    exit 1
  fi
done

echo "All core agents validated (frontmatter present)."
