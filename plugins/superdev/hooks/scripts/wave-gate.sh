#!/usr/bin/env bash
# wave-gate.sh  (SubagentStop hook for module builders)
#
# Promotes the wave gate from "typecheck only" to "typecheck + lint-at-error +
# no-new-suppressions". Runs when a backend/frontend builder stops, scoped to
# the app it owns. On any failure it exits 2 so the error is fed back to the
# orchestrator and the wave cannot advance until it is fixed at the ROOT CAUSE.
#
# Why: in a real build 446 (api) + 25 (web) ESLint errors shipped under
# "all waves green" because the gate only ran typecheck, and the first fix
# instinct was to SUPPRESS (downgrade rules / `as any`). This blocks both.
#
# Usage (from hooks.json): wave-gate.sh <app-subdir>   e.g. apps/api | apps/web
#
# Exit: 0 = gate green (or nothing to check); 2 = gate red (blocks advance).

set -u
. "$(dirname "$0")/_superdev-lib.sh" 2>/dev/null || true
[ ! -t 0 ] && cat >/dev/null 2>&1 || true   # drain stdin

APP="${1:-}"
PROJ="$(sd_project_dir)"
APPDIR="$PROJ/$APP"
[ -n "$APP" ] && [ -f "$APPDIR/package.json" ] || exit 0   # nothing to gate

PM="$(sd_pm)"
FAILED=""
REPORT=""

run() { ( cd "$APPDIR" && eval "$1" ) 2>&1; }

# 1) Typecheck ---------------------------------------------------------------
TC_OUT="$(run "$PM run typecheck" 2>/dev/null || true)"
if printf '%s' "$TC_OUT" | grep -qiE "missing script|command not found|no (such )?script"; then
  TC_OUT="$(run "$PM run type-check" 2>/dev/null || run "$PM run check-types" 2>/dev/null || run "npx -y tsc --noEmit")"
fi
if printf '%s' "$TC_OUT" | grep -qE "error TS[0-9]+|Type error|Found [1-9][0-9]* error"; then
  FAILED="${FAILED} typecheck"
  REPORT="${REPORT}
── typecheck (${APP}) ──
$(printf '%s' "$TC_OUT" | grep -E "error TS|Found [0-9]+ error" | head -25)"
fi

# 2) Lint at ERROR severity (zero warnings) ----------------------------------
LINT_OUT="$(run "$PM run lint -- --max-warnings=0" 2>/dev/null || true)"
if printf '%s' "$LINT_OUT" | grep -qiE "missing script|no (such )?script|unknown option|invalid option"; then
  LINT_OUT="$(run "$PM run lint" 2>/dev/null || true)"
fi
# eslint prints "✖ N problems (E errors, W warnings)"; fail on any error, or any warning when max-warnings honored
if printf '%s' "$LINT_OUT" | grep -qE "[1-9][0-9]* error(s)?|✖ [1-9][0-9]* problem|[1-9][0-9]* problems? \([1-9]"; then
  FAILED="${FAILED} lint"
  REPORT="${REPORT}
── lint (${APP}) ──
$(printf '%s' "$LINT_OUT" | grep -E "error|problem|warning" | head -25)"
fi

# 3) No NEW suppressions vs the last commit ----------------------------------
# Catches BOTH added lines in modified tracked files AND whole new (untracked)
# files — a builder's new files are untracked, which `git diff HEAD` omits.
SUPP_RE='eslint-disable|@ts-ignore|@ts-expect-error|as any[^A-Za-z]|as unknown as'
if command -v git >/dev/null 2>&1 && ( cd "$PROJ" && git rev-parse --git-dir >/dev/null 2>&1 ); then
  ADDED="$( cd "$PROJ" && git -c color.ui=never diff HEAD -- "$APP" 2>/dev/null | grep -E '^\+' | grep -vE '^[+][+][+]' || true )"
  SUPP="$(printf '%s' "$ADDED" | grep -nE "$SUPP_RE" || true)"
  # untracked (new) files under the app — grep their full content
  NEWFILES="$( cd "$PROJ" && git ls-files --others --exclude-standard -- "$APP" 2>/dev/null || true )"
  NEW_SUPP=""
  if [ -n "$NEWFILES" ]; then
    NEW_SUPP="$( cd "$PROJ" && printf '%s\n' "$NEWFILES" | while IFS= read -r nf; do
      [ -f "$nf" ] || continue
      grep -HnE "$SUPP_RE" "$nf" 2>/dev/null || true
    done )"
  fi
  ALLSUPP="$(printf '%s\n%s' "$SUPP" "$NEW_SUPP" | grep -E '.' || true)"
  if [ -n "$ALLSUPP" ]; then
    FAILED="${FAILED} suppressions"
    REPORT="${REPORT}
── NEW suppressions introduced in this wave (${APP}) — forbidden, fix the root cause ──
$(printf '%s' "$ALLSUPP" | head -20)"
  fi
fi

if [ -n "$FAILED" ]; then
  {
    echo "[superdev wave-gate] BLOCKED (${APP}) — failing:${FAILED}"
    echo "$REPORT"
    echo ""
    echo "Do NOT advance the wave and do NOT suppress. Dispatch a focused fixer subagent"
    echo "(backend-module-builder / frontend-module-builder with a 'fix' prompt) to resolve"
    echo "the ROOT CAUSE, then this gate must pass before the next wave."
  } >&2
  exit 2
fi

echo "[superdev wave-gate] ${APP}: typecheck + lint(0 warnings) + no-new-suppressions — green"
exit 0
