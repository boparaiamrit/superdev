#!/usr/bin/env bash
# Install Superdev for the current Claude Code project only.

set -euo pipefail

readonly PLUGIN_ID="superdev@superdev"
readonly MARKETPLACE_SOURCE="boparaiamrit/superdev"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SOURCE_PLUGIN_DIR="${SCRIPT_DIR}/plugins/superdev"

PROJECT_ROOT=""
SETTINGS_FILE=""

log_info() { printf '[*] %s\n' "$*"; }
log_success() { printf '[✓] %s\n' "$*"; }
log_error() { printf '[✗] %s\n' "$*" >&2; }

fail() {
  log_error "$*"
  exit 1
}

require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required."
}

resolve_project() {
  require_command git
  PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" ||
    fail "Run this command from inside the target Git project."
  [[ -w "$PROJECT_ROOT" ]] || fail "Project root is not writable: $PROJECT_ROOT"
  SETTINGS_FILE="${PROJECT_ROOT}/.claude/settings.json"
  cd "$PROJECT_ROOT"
}

require_python() {
  require_command python3
}

require_claude() {
  require_command claude
}

validate_existing_settings() {
  [[ -f "$SETTINGS_FILE" ]] || return 0

  python3 - "$SETTINGS_FILE" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
try:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as error:
    print(f"Invalid project settings at {settings_path}: {error}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(settings, dict):
    print(f"Project settings must contain a JSON object: {settings_path}", file=sys.stderr)
    raise SystemExit(1)
PY
}

verify_project_settings() {
  python3 - "$SETTINGS_FILE" "$PLUGIN_ID" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
plugin_id = sys.argv[2]

if not settings_path.is_file():
    print(f"Project settings were not created: {settings_path}", file=sys.stderr)
    raise SystemExit(1)

settings = json.loads(settings_path.read_text(encoding="utf-8"))
enabled = settings.get("enabledPlugins", {})
if not isinstance(enabled, dict) or enabled.get(plugin_id) is not True:
    print(f"{plugin_id} is not enabled in {settings_path}", file=sys.stderr)
    raise SystemExit(1)
PY
}

verify_claude_list() {
  local plugin_list
  plugin_list="$(claude plugin list --json)" || fail "Claude could not list installed plugins."

  python3 - "$PLUGIN_ID" "$plugin_list" <<'PY'
import json
import sys

plugin_id = sys.argv[1]
try:
    payload = json.loads(sys.argv[2])
except json.JSONDecodeError as error:
    print(f"Claude returned invalid plugin JSON: {error}", file=sys.stderr)
    raise SystemExit(1)

serialized = json.dumps(payload)
if plugin_id not in serialized and "superdev" not in serialized:
    print("Claude did not report Superdev in the project plugin list.", file=sys.stderr)
    raise SystemExit(1)
PY
}

verify_install() {
  require_python
  require_claude
  validate_existing_settings
  verify_project_settings
  verify_claude_list
  log_success "Superdev is enabled for project: $PROJECT_ROOT"
}

install_plugin() {
  require_python
  require_claude
  validate_existing_settings

  log_info "Adding the Superdev marketplace at project scope"
  claude plugin marketplace add "$MARKETPLACE_SOURCE" --scope project

  log_info "Installing Superdev at project scope"
  claude plugin install "$PLUGIN_ID" --scope project

  verify_install
}

uninstall_plugin() {
  require_python
  require_claude
  validate_existing_settings

  claude plugin uninstall "$PLUGIN_ID" --scope project
  log_success "Superdev was removed from project scope: $PROJECT_ROOT"
}

enable_agent_teams() {
  require_python
  validate_existing_settings
  mkdir -p "$(dirname "$SETTINGS_FILE")"

  python3 - "$SETTINGS_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
if settings_path.exists():
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
else:
    settings = {}

env = settings.get("env", {})
if not isinstance(env, dict):
    print("Project settings key 'env' must be a JSON object.", file=sys.stderr)
    raise SystemExit(1)

env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"
settings["env"] = env

temporary_path = settings_path.with_suffix(".json.tmp")
temporary_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
os.replace(temporary_path, settings_path)
PY

  log_success "Agent teams were enabled in project settings: $SETTINGS_FILE"
}

inventory() {
  local version="source unavailable"
  local skill_count="source unavailable"
  local agent_count="source unavailable"

  if [[ -f "${SOURCE_PLUGIN_DIR}/.claude-plugin/plugin.json" ]]; then
    version="$(python3 - "${SOURCE_PLUGIN_DIR}/.claude-plugin/plugin.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as manifest:
    print(json.load(manifest)["version"])
PY
)"
  fi
  if [[ -d "${SOURCE_PLUGIN_DIR}/skills" ]]; then
    skill_count="$(find "${SOURCE_PLUGIN_DIR}/skills" -mindepth 2 -maxdepth 2 -name SKILL.md -type f | wc -l | tr -d ' ')"
  fi
  if [[ -d "${SOURCE_PLUGIN_DIR}/agents" ]]; then
    agent_count="$(find "${SOURCE_PLUGIN_DIR}/agents" -mindepth 1 -maxdepth 1 -name '*.md' -type f | wc -l | tr -d ' ')"
  fi

  printf 'Version: %s\nSkills: %s\nAgents: %s\n' "$version" "$skill_count" "$agent_count"
}

show_usage() {
  cat <<EOF

Superdev is installed for this project only.

Project:  ${PROJECT_ROOT}
Settings: ${SETTINGS_FILE}

$(inventory)

Start Claude Code from this project and run /plugin list to inspect Superdev.
Use --enable-teams to store the optional agent-teams flag in project settings.
EOF
}

show_help() {
  cat <<'EOF'
install-superdev.sh — manage Superdev for the current Claude Code project

USAGE
  bash install-superdev.sh [option]

OPTIONS
  (none)          Add the marketplace and install at project scope
  --verify        Verify the project-scoped installation
  --enable-teams  Enable agent teams in .claude/settings.json
  --uninstall     Uninstall from project scope
  --help          Show this help

The command must run from inside the target Git project. It never writes
Superdev configuration to user or personal settings.

Equivalent install commands:
  claude plugin marketplace add boparaiamrit/superdev --scope project
  claude plugin install superdev@superdev --scope project
EOF
}

main() {
  local action="${1:-install}"

  case "$action" in
    --help|-h|help)
      show_help
      return 0
      ;;
  esac

  resolve_project

  case "$action" in
    install|"")
      install_plugin
      show_usage
      ;;
    --verify|verify)
      verify_install
      ;;
    --enable-teams|enable-teams)
      enable_agent_teams
      ;;
    --uninstall|uninstall)
      uninstall_plugin
      ;;
    *)
      log_error "Unknown option: $action"
      show_help
      return 1
      ;;
  esac
}

main "$@"
