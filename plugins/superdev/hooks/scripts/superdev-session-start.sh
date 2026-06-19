#!/usr/bin/env bash
# superdev-session-start.sh  (SessionStart hook)
#
# Enforces the READ half of the self-learning loop that SKILL.md only described
# in prose: at session start, surface every learned lesson in
# .claude/memory/superdev-learned/ (plus any un-captured pending signals) into
# the model's context via additionalContext, so the orchestrator threads them
# into dispatches WITHOUT relying on it remembering to `ls` the directory.
#
# Exits 0 always; emits nothing when there are no lessons.

set -u
. "$(dirname "$0")/_superdev-lib.sh" 2>/dev/null || true

# consume (and discard) stdin if present
[ ! -t 0 ] && cat >/dev/null 2>&1 || true

PROJ="$(sd_project_dir)"
DIR="$PROJ/.claude/memory/superdev-learned"
[ -d "$DIR" ] || exit 0

PY="$(sd_python)"
LESSONS=""
PENDING=""

# Collect "name: description" for each lesson .md (skip dotfiles like .pending.log)
for f in "$DIR"/*.md; do
  [ -e "$f" ] || continue
  case "$(basename "$f")" in .*) continue;; esac
  name=""; desc=""
  if [ -n "$PY" ]; then
    read -r name desc <<EOF2
$("$PY" - "$f" <<'PY'
import sys,re
name=desc=""
try:
    t=open(sys.argv[1],encoding="utf-8").read()
    m=re.search(r'^name:\s*(.+)$', t, re.M);  name=(m.group(1).strip() if m else "")
    m=re.search(r'^description:\s*(.+)$', t, re.M); desc=(m.group(1).strip() if m else "")
except Exception: pass
print((name or "").replace("\n"," "), (desc or "").replace("\n"," "))
PY
)
EOF2
  fi
  [ -z "$name" ] && name="$(basename "$f" .md)"
  LESSONS="${LESSONS}
- ${name}: ${desc}"
done

# Pending (un-captured) signals
if [ -f "$DIR/.pending.log" ]; then
  cnt="$(grep -c . "$DIR/.pending.log" 2>/dev/null || echo 0)"
  if [ "${cnt:-0}" -gt 0 ] 2>/dev/null; then
    PENDING="${cnt} un-captured frustration signal(s) are queued in .claude/memory/superdev-learned/.pending.log — review them and write the missing lesson files, then clear the log."
  fi
fi

[ -z "$LESSONS" ] && [ -z "$PENDING" ] && exit 0

MSG="🧠 superdev learned lessons for THIS project — apply these before/within every dispatch:${LESSONS}"
[ -n "$PENDING" ] && MSG="${MSG}

${PENDING}"

sd_emit_context "SessionStart" "$MSG"
exit 0
