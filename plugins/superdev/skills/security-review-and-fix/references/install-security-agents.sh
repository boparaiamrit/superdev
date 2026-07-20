#!/usr/bin/env bash
# install-security-agents.sh
# Extracts the 5 security agent definitions from security-agents.md and writes
# each to .claude/agents/<name>.md in the current project.
#
# Typically invoked by the prd-design-build-orchestrator's Phase A.1 after it
# detects this skill. Can also be run standalone for ad-hoc audits.
#
# Reuses the orchestrator skill's extract-agent.py (single source of truth for
# the extraction logic).

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SKILLS_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly SECURITY_SKILL_REF="${SCRIPT_DIR}/security-agents.md"
readonly EXTRACTOR="${SKILLS_DIR}/prd-design-build-orchestrator/references/extract-agent.py"

if [[ ! -f "$SECURITY_SKILL_REF" ]]; then
  echo "❌ Security agent definitions not found at $SECURITY_SKILL_REF"
  echo "   Reinstall the project-scoped Superdev plugin."
  exit 1
fi

if [[ ! -f "$EXTRACTOR" ]]; then
  echo "❌ Extractor not found at $EXTRACTOR"
  echo "   Reinstall the project-scoped Superdev plugin."
  exit 1
fi

mkdir -p .claude/agents

SECURITY_AGENTS=(
  security-inventory
  static-auditor
  dynamic-auditor
  dependency-auditor
  security-fixer
)

INSTALLED=0
FAILED=0

for agent in "${SECURITY_AGENTS[@]}"; do
  out=".claude/agents/${agent}.md"
  if python3 "$EXTRACTOR" "$SECURITY_SKILL_REF" "$agent" > "$out" 2>/tmp/extract-err.txt; then
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
echo "Security agents: ${INSTALLED} installed, ${FAILED} failed"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi

for agent in "${SECURITY_AGENTS[@]}"; do
  f=".claude/agents/${agent}.md"
  if ! head -1 "$f" | grep -q '^---$'; then
    echo "❌ $f does not start with --- frontmatter"
    exit 1
  fi
done

echo "All security agents validated (frontmatter present)."
