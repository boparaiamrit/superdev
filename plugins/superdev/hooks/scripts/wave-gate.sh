#!/usr/bin/env bash
# wave-gate.sh  (SubagentStop hook for module builders)
#
# Promotes the wave gate from "typecheck only" to "typecheck/static + lint +
# no-new-suppressions". Runs when a builder stops, scoped to the app it owns,
# and is STACK-AWARE so it covers both the TS stack (Nest/Next) and the Laravel
# stack (laravel-enterprise-backend + design-to-laravel Inertia monolith).
# On any failure it exits 2 so the error is fed back to the orchestrator and the
# wave cannot advance until it is fixed at the ROOT CAUSE (no suppressions).
#
# Usage (from hooks.json): wave-gate.sh <app-subdir> [lane]
#   <app-subdir>  e.g. apps/api | apps/web
#   lane          auto (default) | js | php
#                 js  → only the TS toolchain (package.json: typecheck + lint)
#                 php → only the PHP toolchain (composer+artisan: Pint + PHPStan)
#                 auto→ run whichever toolchains the dir has (Inertia monolith
#                       apps/api has BOTH composer.json and package.json)
#
# JS lane  : <pm> run typecheck (||tsc --noEmit) + <pm> run lint --max-warnings=0
# PHP lane : ./vendor/bin/pint --test (format/lint) + ./vendor/bin/phpstan
#            analyse (static). Each runs only if that binary is installed; the
#            full test suite is NOT run here (that is the integration gate).
#
# Exit: 0 = green (or nothing to check); 2 = red (blocks wave advance).

set -u
. "$(dirname "$0")/_superdev-lib.sh" 2>/dev/null || true
[ ! -t 0 ] && cat >/dev/null 2>&1 || true   # drain stdin

APP="${1:-}"
LANE="${2:-auto}"
PROJ="$(sd_project_dir)"
APPDIR="$PROJ/$APP"
[ -n "$APP" ] && [ -d "$APPDIR" ] || exit 0

HAS_JS=0;  [ -f "$APPDIR/package.json" ] && HAS_JS=1
HAS_PHP=0; { [ -f "$APPDIR/composer.json" ] && [ -f "$APPDIR/artisan" ]; } && HAS_PHP=1
DO_JS=0; DO_PHP=0
case "$LANE" in
  js)   DO_JS=$HAS_JS ;;
  php)  DO_PHP=$HAS_PHP ;;
  *)    DO_JS=$HAS_JS; DO_PHP=$HAS_PHP ;;
esac
[ "$DO_JS" = 0 ] && [ "$DO_PHP" = 0 ] && exit 0

FAILED=""; REPORT=""
run() { ( cd "$APPDIR" && eval "$1" ) 2>&1; }

# ── JS lane: typecheck + lint ────────────────────────────────────────────
if [ "$DO_JS" = 1 ]; then
  PM="$(sd_pm)"
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

  LINT_OUT="$(run "$PM run lint -- --max-warnings=0" 2>/dev/null || true)"
  if printf '%s' "$LINT_OUT" | grep -qiE "missing script|no (such )?script|unknown option|invalid option"; then
    LINT_OUT="$(run "$PM run lint" 2>/dev/null || true)"
  fi
  if printf '%s' "$LINT_OUT" | grep -qE "[1-9][0-9]* error(s)?|✖ [1-9][0-9]* problem|[1-9][0-9]* problems? \([1-9]"; then
    FAILED="${FAILED} lint"
    REPORT="${REPORT}
── lint (${APP}) ──
$(printf '%s' "$LINT_OUT" | grep -E "error|problem|warning" | head -25)"
  fi
fi

# ── PHP lane: Pint (format/lint) + PHPStan/Larastan (static) ─────────────
if [ "$DO_PHP" = 1 ]; then
  if [ -f "$APPDIR/vendor/bin/pint" ]; then
    PINT_OUT="$( cd "$APPDIR" && ./vendor/bin/pint --test 2>&1 )"; PINT_RC=$?
    if [ "$PINT_RC" -ne 0 ]; then
      FAILED="${FAILED} pint"
      REPORT="${REPORT}
── pint --test (${APP}) — code style failures, run ./vendor/bin/pint to fix ──
$(printf '%s' "$PINT_OUT" | grep -iE "✗|FAIL|requires|incorrect" | head -20)"
    fi
  fi
  if [ -f "$APPDIR/vendor/bin/phpstan" ]; then
    PS_OUT="$( cd "$APPDIR" && ./vendor/bin/phpstan analyse --no-progress --no-interaction 2>&1 )"; PS_RC=$?
    if [ "$PS_RC" -ne 0 ]; then
      FAILED="${FAILED} phpstan"
      REPORT="${REPORT}
── phpstan analyse (${APP}) — static analysis errors ──
$(printf '%s' "$PS_OUT" | grep -iE "error|Line|:[0-9]+" | head -25)"
    fi
  fi
fi

# ── No NEW suppressions vs the last commit (JS + PHP patterns) ───────────
# Catches added lines in modified tracked files AND whole new (untracked) files.
SUPP_RE='eslint-disable|@ts-ignore|@ts-expect-error|as any[^A-Za-z]|as unknown as|@phpstan-ignore|@phpcs:ignore|@codingStandardsIgnore|@phan-suppress'
if command -v git >/dev/null 2>&1 && ( cd "$PROJ" && git rev-parse --git-dir >/dev/null 2>&1 ); then
  ADDED="$( cd "$PROJ" && git -c color.ui=never diff HEAD -- "$APP" 2>/dev/null | grep -E '^\+' | grep -vE '^[+][+][+]' || true )"
  DIFF_SUPP="$(printf '%s' "$ADDED" | grep -nE "$SUPP_RE" || true)"
  NEWF="$( cd "$PROJ" && git ls-files --others --exclude-standard -- "$APP" 2>/dev/null || true )"
  NEW_SUPP=""
  [ -n "$NEWF" ] && NEW_SUPP="$( cd "$PROJ" && printf '%s\n' "$NEWF" | while IFS= read -r nf; do [ -f "$nf" ] && grep -HnE "$SUPP_RE" "$nf" 2>/dev/null || true; done )"
  SUPP="$(printf '%s\n%s' "$DIFF_SUPP" "$NEW_SUPP" | grep -E '.' | head -20 || true)"
  if [ -n "$SUPP" ]; then
    FAILED="${FAILED} suppressions"
    REPORT="${REPORT}
── NEW suppressions introduced in this wave (${APP}) — forbidden, fix the root cause ──
$(printf '%s' "$SUPP")"
  fi
fi

if [ -n "$FAILED" ]; then
  {
    echo "[superdev wave-gate] BLOCKED (${APP}) — failing:${FAILED}"
    echo "$REPORT"
    echo ""
    echo "Do NOT advance the wave and do NOT suppress. Dispatch a focused fixer subagent"
    echo "(the matching *-module-builder with a 'fix' prompt) to resolve the ROOT CAUSE;"
    echo "this gate must pass before the next wave."
  } >&2
  exit 2
fi

echo "[superdev wave-gate] ${APP} (lane=${LANE}): checks green — no errors, no new suppressions"
exit 0
