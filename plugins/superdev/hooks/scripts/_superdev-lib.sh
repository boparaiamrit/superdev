#!/usr/bin/env bash
# _superdev-lib.sh — shared helpers for superdev hook scripts.
#
# Source this from a hook script:  . "$(dirname "$0")/_superdev-lib.sh"
# Every function is defensive: a missing tool or path must never abort a hook.
#
# Conventions (paths are relative to the project root):
#   .claude/memory/superdev-learned/        learned lessons (one .md per lesson)
#   .claude/memory/superdev-learned/.pending.log   queued frustration/verifier signals
#   .claude/.superdev-orchestrating          sentinel: a superdev build is in progress
#   COMPLETION_LEDGER.json                   machine-readable done/deferred state
#   .claude/.superdev-done-override          user escape hatch for the done-gate

# Project root: Claude Code sets CLAUDE_PROJECT_DIR; fall back to cwd.
sd_project_dir() { printf '%s' "${CLAUDE_PROJECT_DIR:-$PWD}"; }

# A working Python interpreter, or empty string.
sd_python() { command -v python3 2>/dev/null || command -v python 2>/dev/null || true; }

# Read a field from the hook's stdin JSON (already captured into $1=json, $2=key path).
# Uses python for correctness; returns empty on any failure.
sd_json_field() {
  _json="$1"; _key="$2"; _py="$(sd_python)"
  [ -z "$_json" ] && return 0
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$_json" | jq -r "$_key // empty" 2>/dev/null || true
  elif [ -n "$_py" ]; then
    printf '%s' "$_json" | "$_py" -c "import json,sys
try:
    d=json.load(sys.stdin)
    cur=d
    for p in '''$_key'''.strip('.').split('.'):
        if p=='': continue
        cur=cur.get(p) if isinstance(cur,dict) else None
    print(cur if isinstance(cur,str) else ('' if cur is None else cur))
except Exception:
    pass" 2>/dev/null || true
  fi
}

# Emit additionalContext for the given hook event so the text is injected into
# the model's context (the supported channel — NOT bare stderr). Falls back to
# plain stdout (which SessionStart / UserPromptSubmit also inject) when no python.
# Usage: sd_emit_context <HookEventName> <message>
sd_emit_context() {
  _evt="$1"; shift; _msg="$*"; _py="$(sd_python)"
  [ -z "$_msg" ] && return 0
  if [ -n "$_py" ]; then
    SD_EVT="$_evt" SD_MSG="$_msg" "$_py" -c "import json,os
print(json.dumps({'hookSpecificOutput':{'hookEventName':os.environ['SD_EVT'],'additionalContext':os.environ['SD_MSG']}}))" 2>/dev/null && return 0
  fi
  printf '%s\n' "$_msg"
}

# Detect the workspace package manager from lockfiles at the project root.
sd_pm() {
  _d="$(sd_project_dir)"
  if [ -f "$_d/bun.lockb" ] || [ -f "$_d/bun.lock" ]; then printf 'bun'
  elif [ -f "$_d/pnpm-lock.yaml" ]; then printf 'pnpm'
  elif [ -f "$_d/yarn.lock" ]; then printf 'yarn'
  else printf 'npm'; fi
}
