#!/usr/bin/env bash
# install-migration-agents.sh
# Extracts the 5 migration agent definitions from migration-agents.md and writes
# each to .claude/agents/<name>.md in the current project.
#
# This skill reuses the orchestrator skill's extract-agent.py — that's the single
# source of truth for extraction logic, so any fixes to it benefit both skills.

set -euo pipefail

MIGRATION_SKILL_DIR="${HOME}/.claude/skills/prototype-to-saas"
MIGRATION_SKILL_REF="${MIGRATION_SKILL_DIR}/references/migration-agents.md"

ORCH_SKILL_DIR="${HOME}/.claude/skills/prd-design-build-orchestrator"
EXTRACTOR="${ORCH_SKILL_DIR}/references/extract-agent.py"

if [[ ! -f "$MIGRATION_SKILL_REF" ]]; then
  echo "❌ Migration agent definitions not found at $MIGRATION_SKILL_REF"
  echo "   Install the prototype-to-saas skill first."
  exit 1
fi

if [[ ! -f "$EXTRACTOR" ]]; then
  echo "❌ Extractor not found at $EXTRACTOR"
  echo "   This script requires the prd-design-build-orchestrator skill to be"
  echo "   installed (it provides the extract-agent.py used here)."
  exit 1
fi

mkdir -p .claude/agents

MIGRATION_AGENTS=(
  codebase-discoverer
  schema-reverse-engineer
  migration-planner
  backend-extractor
  frontend-rewirer
)

INSTALLED=0
FAILED=0

for agent in "${MIGRATION_AGENTS[@]}"; do
  out=".claude/agents/${agent}.md"
  if python3 "$EXTRACTOR" "$MIGRATION_SKILL_REF" "$agent" > "$out" 2>/tmp/extract-err.txt; then
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
echo "Migration agents: ${INSTALLED} installed, ${FAILED} failed"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi

for agent in "${MIGRATION_AGENTS[@]}"; do
  f=".claude/agents/${agent}.md"
  if ! head -1 "$f" | grep -q '^---$'; then
    echo "❌ $f does not start with --- frontmatter"
    exit 1
  fi
done

echo "All migration agents validated (frontmatter present)."
