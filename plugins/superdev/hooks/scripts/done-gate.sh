#!/usr/bin/env bash
# done-gate.sh — the machine-checkable Definition-of-Done gate.
#
# Two modes:
#   (A) Stop hook (default): reads the Stop-hook JSON on stdin. If a superdev
#       build is in progress (.claude/.superdev-orchestrating present) AND the
#       last assistant turn claimed completion ("done/ready/production/live/…"),
#       it runs the checks and, if any are red, emits
#       {"decision":"block","reason":...} so the model CANNOT end the turn on a
#       false "done". Otherwise it approves (stays silent).
#   (B) --report: prints a human-readable PASS/FAIL summary and exits 0 (green)
#       or 1 (not done). Backs the /superdev-done skill.
#
# It is FAST: the expensive gates (build/typecheck/lint/integration/security/
# qa/brutal) are read from COMPLETION_LEDGER.json (written by the wave gate and
# the Phase D driver). done-gate adds cheap live checks: ledger freshness,
# no-new-suppressions vs the build base, and a high-precision demo/placeholder
# sweep. The ledger survives compaction, so deferred work cannot be silently
# dropped between "done" and a later firefight.
#
# Fail-OPEN: any inability to inspect state approves the stop (never trap a user).

set -u
. "$(dirname "$0")/_superdev-lib.sh" 2>/dev/null || true

MODE="stop"
[ "${1:-}" = "--report" ] && MODE="report"

PROJ="$(sd_project_dir)"
SENTINEL="$PROJ/.claude/.superdev-orchestrating"
OVERRIDE="$PROJ/.claude/.superdev-done-override"
LEDGER="$PROJ/COMPLETION_LEDGER.json"
ATTEMPTS="$PROJ/.claude/.superdev-donegate-attempts"
PY="$(sd_python)"

approve() { [ "$MODE" = report ] && return 0; exit 0; }   # silent allow

# ---- Stop-mode pre-conditions --------------------------------------------
if [ "$MODE" = "stop" ]; then
  JSON=""; [ ! -t 0 ] && JSON="$(cat 2>/dev/null || true)"
  # arm only for superdev builds
  [ -f "$SENTINEL" ] || approve
  [ -f "$OVERRIDE" ] && approve
  # loop bound: never block forever
  N="$(cat "$ATTEMPTS" 2>/dev/null || echo 0)"; case "$N" in ''|*[!0-9]*) N=0;; esac
  if [ "$N" -ge 6 ]; then
    printf '{"decision":"approve","systemMessage":"superdev done-gate: still red after %s attempts — allowing stop. Resolve the failing checks manually or create .claude/.superdev-done-override."}\n' "$N"
    rm -f "$ATTEMPTS" 2>/dev/null || true
    exit 0
  fi
  # only engage when the assistant actually claimed completion
  TPATH="$(sd_json_field "$JSON" '.transcript_path')"
  CLAIM=""
  if [ -n "$TPATH" ] && [ -f "$TPATH" ] && [ -n "$PY" ]; then
    CLAIM="$("$PY" - "$TPATH" <<'PY' 2>/dev/null || true
import json,sys,re
last=""
try:
    for line in open(sys.argv[1],encoding="utf-8"):
        try: d=json.loads(line)
        except: continue
        if d.get("type")=="assistant":
            c=d.get("message",{}).get("content")
            if isinstance(c,list):
                t=" ".join(b.get("text","") for b in c if isinstance(b,dict) and b.get("type")=="text")
                if t.strip(): last=t
except Exception: pass
pat=re.compile(r"\b(done|complete[d]?|finished|ready to ship|production[- ]ready|ready for production|is live|shipped|all set|good to go|ship it|fully (built|functional|working)|everything (works|is working))\b|🎉|🚀", re.I)
print("YES" if pat.search(last) else "")
PY
)"
  fi
  # if we cannot read the transcript, fail OPEN (do not block)
  [ -z "$CLAIM" ] && approve
fi

# ---- The checks ----------------------------------------------------------
FAILS=""; NOTES=""; ACCEPTED=""
add_fail(){ FAILS="${FAILS}
  ✗ $1"; }
add_note(){ NOTES="${NOTES}
  • $1"; }
add_ok(){ NOTES="${NOTES}
  ✓ $1"; }

# 1) Ledger present + all gates pass + fresh
REQUIRED_GATES="typecheck lint build integration completeness security qa brutal"
if [ ! -f "$LEDGER" ]; then
  add_fail "COMPLETION_LEDGER.json is missing — run the Phase D driver (integration → product-completeness → security-review → exploratory-qa → brutal-exhaustive-audit) and record verdicts in the ledger before declaring done."
elif [ -n "$PY" ]; then
  LRES="$(LEDGER_REQ="$REQUIRED_GATES" "$PY" - "$LEDGER" "$PROJ" <<'PY' 2>/dev/null || true
import json,os,sys,subprocess
led=sys.argv[1]; proj=sys.argv[2]
req=os.environ.get("LEDGER_REQ","").split()
out=[]
try: d=json.load(open(led,encoding="utf-8"))
except Exception as e:
    print("FAIL\tledger is not valid JSON ("+str(e)+")"); sys.exit(0)
gates=d.get("gates",{}) if isinstance(d,dict) else {}
for g in req:
    v=gates.get(g)
    if v=="pass": continue
    if v=="deferred": out.append("ACCEPT\tgate '%s' is DEFERRED (accepted risk)"%g); continue
    out.append("FAIL\tgate '%s' is '%s' (must be pass)"%(g, v if v else "missing"))
# per-feature flags
feats=d.get("features",{}) if isinstance(d,dict) else {}
for name,info in (feats.items() if isinstance(feats,dict) else []):
    if not isinstance(info,dict): continue
    for k,val in info.items():
        if k in ("deferred",): continue
        if val is False:
            out.append("FAIL\tfeature '%s' gate '%s' is incomplete"%(name,k))
    dfr=info.get("deferred")
    if dfr: out.append("ACCEPT\tfeature '%s' deferred: %s"%(name, dfr if isinstance(dfr,str) else ",".join(dfr) if isinstance(dfr,list) else "yes"))
# freshness: ledger head_sha vs current HEAD
head=""
try:
    head=subprocess.check_output(["git","-C",proj,"rev-parse","HEAD"],stderr=subprocess.DEVNULL).decode().strip()
except Exception: head=""
lsha=d.get("head_sha") or d.get("base_sha") or ""
if head and lsha and head!=lsha:
    out.append("FAIL\tledger is STALE (recorded %s, HEAD is %s) — re-run the gates after the latest changes"%(lsha[:8],head[:8]))
for line in out: print(line)
PY
)"
  while IFS=$'\t' read -r kind msg; do
    [ -z "$kind" ] && continue
    case "$kind" in
      FAIL) add_fail "$msg" ;;
      ACCEPT) ACCEPTED="${ACCEPTED}
  ⚠ $msg" ;;
    esac
  done <<EOF
$LRES
EOF
  [ -z "$LRES" ] && add_ok "ledger gates all pass"
else
  add_note "no python available — ledger not parsed (install python to enforce ledger gates)"
fi

# 2) No suppressions sneaked in since the build base (precise; needs git+base)
if command -v git >/dev/null 2>&1 && ( cd "$PROJ" && git rev-parse --git-dir >/dev/null 2>&1 ); then
  BASE=""
  [ -f "$LEDGER" ] && [ -n "$PY" ] && BASE="$("$PY" -c "import json,sys
try: print(json.load(open(sys.argv[1])).get('base_sha') or '')
except: print('')" "$LEDGER" 2>/dev/null || true)"
  RANGE="HEAD"; [ -n "$BASE" ] && RANGE="$BASE"
  SUPP_RE='eslint-disable|@ts-ignore|@ts-expect-error|as any[^A-Za-z]|as unknown as'
  DIFF_SUPP="$( cd "$PROJ" && git -c color.ui=never diff "$RANGE" -- apps packages 2>/dev/null | grep -E '^\+' | grep -vE '^[+][+][+]' | grep -nE "$SUPP_RE" || true )"
  NEWF="$( cd "$PROJ" && git ls-files --others --exclude-standard -- apps packages 2>/dev/null || true )"
  NEW_SUPP=""
  [ -n "$NEWF" ] && NEW_SUPP="$( cd "$PROJ" && printf '%s\n' "$NEWF" | while IFS= read -r nf; do [ -f "$nf" ] && grep -HnE "$SUPP_RE" "$nf" 2>/dev/null || true; done )"
  SUPP="$(printf '%s\n%s' "$DIFF_SUPP" "$NEW_SUPP" | grep -E '.' | head -15 || true)"
  if [ -n "$SUPP" ]; then
    add_fail "suppressions introduced since the build base (forbidden — fix the root cause):
$(printf '%s' "$SUPP" | sed 's/^/      /')"
  else
    add_ok "no eslint-disable / @ts-ignore / as-any suppressions vs base"
  fi
fi

# 3) High-precision demo / placeholder sweep (web app)
WEB="$PROJ/apps/web/src"
if [ -d "$WEB" ]; then
  DEMO="$(grep -rInE "lorem ipsum|coming soon|not implemented|\bTODO: ?implement|['\"]4242 ?4242|mockData|fakeUsers|placeholder data" "$WEB" 2>/dev/null \
            | grep -vE "\.(test|spec)\.|/__tests__/|/mocks?/|\.stories\." | head -12 || true)"
  if [ -n "$DEMO" ]; then
    add_fail "demo/placeholder content still present in apps/web/src (a beautiful UI with fake data is a demo, not a product):
$(printf '%s' "$DEMO" | sed 's/^/      /')"
  else
    add_ok "no obvious demo/placeholder content in apps/web/src"
  fi
fi

# ---- Verdict --------------------------------------------------------------
if [ "$MODE" = "report" ]; then
  echo "════════════════════════════════════════════"
  echo " superdev — Definition of Done report"
  echo "════════════════════════════════════════════"
  [ -n "$NOTES" ] && printf '%s\n' "$NOTES"
  [ -n "$ACCEPTED" ] && { echo ""; echo " Accepted risks / deferred:"; printf '%s\n' "$ACCEPTED"; }
  if [ -n "$FAILS" ]; then
    echo ""; echo " NOT DONE — failing checks:"; printf '%s\n' "$FAILS"
    echo ""; echo " Resolve these (no suppressions, fix root causes) before declaring done."
    exit 1
  fi
  echo ""; echo " ✅ DONE — all gates green."
  exit 0
fi

# Stop mode
if [ -n "$FAILS" ]; then
  N=$((N + 1)); echo "$N" > "$ATTEMPTS" 2>/dev/null || true
  REASON="superdev done-gate BLOCKED this 'done' — the build is not actually complete:${FAILS}"
  [ -n "$ACCEPTED" ] && REASON="${REASON}
Accepted/deferred (ok):${ACCEPTED}"
  REASON="${REASON}
Fix the failing checks at the ROOT CAUSE (no suppressions). To override intentionally, create .claude/.superdev-done-override. Re-check anytime with the /superdev-done skill."
  if [ -n "$PY" ]; then
    SD_R="$REASON" "$PY" -c "import json,os;print(json.dumps({'decision':'block','reason':os.environ['SD_R']}))"
  else
    printf '{"decision":"block","reason":"superdev done-gate: build not complete (failing checks present). See /superdev-done."}\n'
  fi
  exit 0
fi

rm -f "$ATTEMPTS" 2>/dev/null || true
exit 0
