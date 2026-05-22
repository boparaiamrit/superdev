#!/usr/bin/env bash
# install-superdev.sh
#
# Installs the superdev Claude Code plugin (6 skills + 24 agents + hooks)
# into ~/.claude/plugins/ on Linux, macOS, or WSL.
#
# Usage:
#   bash install-superdev.sh                    # install
#   bash install-superdev.sh --uninstall        # remove
#   bash install-superdev.sh --verify           # verify current install
#   bash install-superdev.sh --enable-teams     # enable agent-teams mode
#   bash install-superdev.sh --help             # show all options
#
# Prerequisites:
#   - Claude Code v2.1.32 or later (check with `claude --version`)
#   - Python 3
#   - bash 4+, unzip
#
# What this script does:
#   1. Verifies prerequisites
#   2. Detects environment (WSL / Linux / macOS)
#   3. Extracts the plugin from the .zip alongside this script
#   4. Installs to ~/.claude/plugins/superdev/
#   5. Registers the plugin in ~/.claude/settings.json so it loads in every session
#   6. (Optional) Enables CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
#   7. Validates installation

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

PLUGIN_NAME="superdev"
PLUGIN_VERSION="1.0.0"
PLUGIN_ZIP="${PLUGIN_ZIP:-superdev.zip}"
CLAUDE_HOME="${HOME}/.claude"
PLUGIN_DIR="${CLAUDE_HOME}/plugins/${PLUGIN_NAME}"
SETTINGS_FILE="${CLAUDE_HOME}/settings.json"

# Colors (only if stdout is a TTY)
if [[ -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  BLUE='\033[0;34m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BLUE='' BOLD='' NC=''
fi

# -----------------------------------------------------------------------------
# Logging helpers
# -----------------------------------------------------------------------------

log_info()    { printf "${BLUE}[*]${NC} %s\n" "$*"; }
log_success() { printf "${GREEN}[✓]${NC} %s\n" "$*"; }
log_warn()    { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
log_error()   { printf "${RED}[✗]${NC} %s\n" "$*" >&2; }
log_step()    { printf "\n${BOLD}${BLUE}==>${NC} ${BOLD}%s${NC}\n" "$*"; }

# -----------------------------------------------------------------------------
# Environment detection
# -----------------------------------------------------------------------------

detect_env() {
  if grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
    ENV_TYPE="WSL"
    # Detect Windows username for friendly path hints later
    WIN_USER="$(cmd.exe /C 'echo %USERNAME%' 2>/dev/null | tr -d '\r\n' || echo '')"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    ENV_TYPE="macOS"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    ENV_TYPE="Linux"
  else
    ENV_TYPE="Unknown ($OSTYPE)"
  fi
}

# -----------------------------------------------------------------------------
# Prerequisite checks
# -----------------------------------------------------------------------------

check_prereq() {
  local missing=0

  log_step "Checking prerequisites"

  # Claude Code
  if command -v claude >/dev/null 2>&1; then
    local ver
    ver=$(claude --version 2>/dev/null | head -1 || echo "unknown")
    log_success "Claude Code installed: $ver"
  else
    log_error "Claude Code not found in PATH."
    log_info  "Install from: https://code.claude.com/docs/en/quickstart"
    if [[ "$ENV_TYPE" == "WSL" ]]; then
      log_info  "On WSL, install inside the WSL distro itself, not Windows."
      log_info  "Quick install: curl -fsSL https://claude.ai/install.sh | sh"
    fi
    missing=1
  fi

  # Python 3
  if command -v python3 >/dev/null 2>&1; then
    log_success "Python 3 available: $(python3 --version)"
  else
    log_error "python3 not found."
    missing=1
  fi

  # unzip
  if command -v unzip >/dev/null 2>&1; then
    log_success "unzip available"
  else
    log_error "unzip not found. Install with: sudo apt install unzip  (or brew install unzip)"
    missing=1
  fi

  # jq (optional, for nicer output)
  if command -v jq >/dev/null 2>&1; then
    HAS_JQ=1
  else
    HAS_JQ=0
    log_warn "jq not installed (optional, will use python for JSON)"
  fi

  if [[ $missing -eq 1 ]]; then
    log_error "Missing prerequisites. Install them and re-run."
    exit 1
  fi
}

# -----------------------------------------------------------------------------
# Locate the plugin zip
# -----------------------------------------------------------------------------

locate_zip() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  # Check: alongside the script
  if [[ -f "${script_dir}/${PLUGIN_ZIP}" ]]; then
    PLUGIN_ZIP_PATH="${script_dir}/${PLUGIN_ZIP}"
    log_success "Found plugin: ${PLUGIN_ZIP_PATH}"
    return 0
  fi

  # Check: current directory
  if [[ -f "./${PLUGIN_ZIP}" ]]; then
    PLUGIN_ZIP_PATH="$(pwd)/${PLUGIN_ZIP}"
    log_success "Found plugin: ${PLUGIN_ZIP_PATH}"
    return 0
  fi

  # Check: explicit env var
  if [[ -n "${SUPERDEV_ZIP:-}" && -f "${SUPERDEV_ZIP}" ]]; then
    PLUGIN_ZIP_PATH="${SUPERDEV_ZIP}"
    log_success "Found plugin: ${PLUGIN_ZIP_PATH}"
    return 0
  fi

  # WSL hint: maybe it's on Windows side
  if [[ "$ENV_TYPE" == "WSL" ]]; then
    local possible_paths=(
      "/mnt/c/Users/${WIN_USER}/Downloads/${PLUGIN_ZIP}"
      "/mnt/c/Users/${WIN_USER}/Desktop/${PLUGIN_ZIP}"
    )
    for p in "${possible_paths[@]}"; do
      if [[ -f "$p" ]]; then
        PLUGIN_ZIP_PATH="$p"
        log_success "Found plugin at Windows-side path: ${PLUGIN_ZIP_PATH}"
        log_info "Tip: copy it into WSL with 'cp \"$p\" ~/' for faster installs"
        return 0
      fi
    done
  fi

  log_error "Cannot find ${PLUGIN_ZIP}."
  log_info  "Place it alongside this script, or set SUPERDEV_ZIP=/path/to/${PLUGIN_ZIP}"
  if [[ "$ENV_TYPE" == "WSL" ]]; then
    log_info  ""
    log_info  "WSL users: if you downloaded the .zip on Windows, copy it into WSL first:"
    log_info  "  cp /mnt/c/Users/${WIN_USER:-USERNAME}/Downloads/${PLUGIN_ZIP} ~/"
    log_info  "  bash ~/install-superdev.sh"
  fi
  exit 1
}

# -----------------------------------------------------------------------------
# Install the plugin
# -----------------------------------------------------------------------------

install_plugin() {
  log_step "Installing plugin to ${PLUGIN_DIR}"

  # Backup existing install if present
  if [[ -d "$PLUGIN_DIR" ]]; then
    local backup="${PLUGIN_DIR}.backup.$(date +%Y%m%d-%H%M%S)"
    log_warn "Existing install detected. Backing up to: $backup"
    mv "$PLUGIN_DIR" "$backup"
  fi

  mkdir -p "$(dirname "$PLUGIN_DIR")"

  # Extract into a temp directory first, then move into place
  # This handles the case where the zip has a top-level superdev/ directory
  local tmp_extract
  tmp_extract="$(mktemp -d)"
  trap "rm -rf $tmp_extract" EXIT

  log_info "Extracting ${PLUGIN_ZIP_PATH}..."
  unzip -q "$PLUGIN_ZIP_PATH" -d "$tmp_extract"

  # The zip contains superdev/ at root; move that to the final location
  if [[ -d "${tmp_extract}/${PLUGIN_NAME}" ]]; then
    mv "${tmp_extract}/${PLUGIN_NAME}" "$PLUGIN_DIR"
  else
    # Fallback: contents may have been zipped without the top-level dir
    mkdir -p "$PLUGIN_DIR"
    mv "${tmp_extract}"/* "$PLUGIN_DIR/"
  fi

  log_success "Plugin extracted to ${PLUGIN_DIR}"
}

# -----------------------------------------------------------------------------
# Verify plugin structure
# -----------------------------------------------------------------------------

verify_structure() {
  log_step "Verifying plugin structure"

  local missing=0

  # Manifest
  if [[ -f "${PLUGIN_DIR}/.claude-plugin/plugin.json" ]]; then
    if python3 -c "import json; json.load(open('${PLUGIN_DIR}/.claude-plugin/plugin.json'))" 2>/dev/null; then
      log_success "Manifest is valid JSON"
    else
      log_error "Manifest exists but isn't valid JSON"
      missing=1
    fi
  else
    log_error "Missing .claude-plugin/plugin.json"
    missing=1
  fi

  # Skills directory
  if [[ -d "${PLUGIN_DIR}/skills" ]]; then
    local skill_count
    skill_count=$(find "${PLUGIN_DIR}/skills" -maxdepth 2 -name "SKILL.md" | wc -l)
    if [[ $skill_count -eq 6 ]]; then
      log_success "All 6 skills present"
    else
      log_warn "Expected 6 skills, found $skill_count"
    fi
  else
    log_error "Missing skills/ directory"
    missing=1
  fi

  # Agents directory
  if [[ -d "${PLUGIN_DIR}/agents" ]]; then
    local agent_count
    agent_count=$(find "${PLUGIN_DIR}/agents" -maxdepth 1 -name "*.md" | wc -l)
    if [[ $agent_count -eq 24 ]]; then
      log_success "All 24 agents present"
    else
      log_warn "Expected 24 agents, found $agent_count"
    fi

    # Validate each agent has frontmatter
    local bad_frontmatter=0
    for f in "${PLUGIN_DIR}/agents"/*.md; do
      if ! head -1 "$f" | grep -q '^---$'; then
        log_warn "Missing frontmatter in $(basename $f)"
        bad_frontmatter=$((bad_frontmatter + 1))
      fi
    done
    if [[ $bad_frontmatter -eq 0 ]]; then
      log_success "All agents have valid frontmatter"
    fi
  else
    log_error "Missing agents/ directory"
    missing=1
  fi

  # Hooks
  if [[ -f "${PLUGIN_DIR}/hooks/hooks.json" ]]; then
    if python3 -c "import json; json.load(open('${PLUGIN_DIR}/hooks/hooks.json'))" 2>/dev/null; then
      log_success "Hooks configuration is valid JSON"
    else
      log_warn "Hooks file exists but isn't valid JSON"
    fi
  else
    log_warn "No hooks/hooks.json (plugin will work without it)"
  fi

  if [[ $missing -eq 1 ]]; then
    log_error "Plugin structure has issues. Install may not work correctly."
    return 1
  fi
}

# -----------------------------------------------------------------------------
# Register plugin in settings.json so it loads in every session
# -----------------------------------------------------------------------------

register_in_settings() {
  log_step "Registering plugin in ${SETTINGS_FILE}"

  mkdir -p "$CLAUDE_HOME"

  # Use python for safe JSON manipulation
  python3 - <<EOF
import json
import os
from pathlib import Path

settings_path = Path("${SETTINGS_FILE}")
plugin_dir = "${PLUGIN_DIR}"

if settings_path.exists():
    try:
        with open(settings_path) as f:
            content = f.read().strip()
        settings = json.loads(content) if content else {}
    except json.JSONDecodeError as e:
        print(f"WARNING: existing settings.json is invalid JSON: {e}")
        backup = settings_path.with_suffix(".json.broken-backup")
        settings_path.rename(backup)
        print(f"Moved broken settings to {backup}, starting fresh.")
        settings = {}
else:
    settings = {}

# Add plugin path to the plugins list
plugins = settings.get("plugins", [])
if not isinstance(plugins, list):
    plugins = []

# De-duplicate: remove any existing entry pointing at the same location
plugins = [p for p in plugins if (isinstance(p, str) and p != plugin_dir) or (isinstance(p, dict) and p.get("path") != plugin_dir)]
plugins.append(plugin_dir)
settings["plugins"] = plugins

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"  Registered plugin path: {plugin_dir}")
print(f"  Total plugins in settings: {len(plugins)}")
EOF

  log_success "Plugin registered for all future Claude Code sessions"
}

# -----------------------------------------------------------------------------
# Enable agent teams (optional)
# -----------------------------------------------------------------------------

enable_agent_teams() {
  log_step "Enabling agent teams (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1)"

  python3 - <<EOF
import json
from pathlib import Path

settings_path = Path("${SETTINGS_FILE}")
if settings_path.exists():
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

env = settings.get("env", {})
env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"
settings["env"] = env

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print("  Agent teams enabled in ${SETTINGS_FILE}")
EOF

  log_success "Agent teams mode enabled"
  log_info "Restart any active Claude Code sessions to pick up this change."
}

# -----------------------------------------------------------------------------
# Uninstall
# -----------------------------------------------------------------------------

do_uninstall() {
  log_step "Uninstalling ${PLUGIN_NAME}"

  if [[ -d "$PLUGIN_DIR" ]]; then
    log_info "Removing $PLUGIN_DIR..."
    rm -rf "$PLUGIN_DIR"
    log_success "Plugin directory removed"
  else
    log_warn "Plugin directory not found; nothing to remove"
  fi

  # Remove from settings.json
  if [[ -f "$SETTINGS_FILE" ]]; then
    python3 - <<EOF
import json
from pathlib import Path

settings_path = Path("${SETTINGS_FILE}")
with open(settings_path) as f:
    settings = json.load(f)

plugins = settings.get("plugins", [])
before = len(plugins)
plugin_dir = "${PLUGIN_DIR}"
plugins = [p for p in plugins if (isinstance(p, str) and p != plugin_dir) or (isinstance(p, dict) and p.get("path") != plugin_dir)]
settings["plugins"] = plugins

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"  Removed {before - len(plugins)} plugin entry from settings.json")
EOF
  fi

  log_success "Uninstall complete"
}

# -----------------------------------------------------------------------------
# Verify-only mode
# -----------------------------------------------------------------------------

do_verify() {
  log_step "Verifying ${PLUGIN_NAME} installation"

  if [[ ! -d "$PLUGIN_DIR" ]]; then
    log_error "Plugin not installed at $PLUGIN_DIR"
    log_info "Run without --verify to install."
    exit 1
  fi

  log_success "Plugin directory exists: $PLUGIN_DIR"

  verify_structure

  # Check settings registration
  if [[ -f "$SETTINGS_FILE" ]]; then
    if python3 -c "
import json
settings = json.load(open('${SETTINGS_FILE}'))
plugins = settings.get('plugins', [])
found = False
for p in plugins:
    if (isinstance(p, str) and p == '${PLUGIN_DIR}') or (isinstance(p, dict) and p.get('path') == '${PLUGIN_DIR}'):
        found = True
        break
exit(0 if found else 1)
" 2>/dev/null; then
      log_success "Plugin registered in settings.json"
    else
      log_warn "Plugin directory exists but not registered in settings.json"
      log_info "Run: bash install-superdev.sh (without --verify) to register"
    fi

    # Check agent teams
    if python3 -c "
import json
settings = json.load(open('${SETTINGS_FILE}'))
env = settings.get('env', {})
exit(0 if env.get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS') == '1' else 1)
" 2>/dev/null; then
      log_success "Agent teams mode is enabled"
    else
      log_info "Agent teams mode not enabled (run with --enable-teams to enable)"
    fi
  else
    log_warn "$SETTINGS_FILE doesn't exist yet"
  fi
}

# -----------------------------------------------------------------------------
# Show usage instructions after install
# -----------------------------------------------------------------------------

show_usage() {
  cat <<EOF

${BOLD}${GREEN}════════════════════════════════════════════════════════════════${NC}
${BOLD}${GREEN}  superdev installed successfully${NC}
${BOLD}${GREEN}════════════════════════════════════════════════════════════════${NC}

${BOLD}Plugin location:${NC} ${PLUGIN_DIR}
${BOLD}Environment:${NC}     ${ENV_TYPE}

${BOLD}What's installed:${NC}
  • 6 skills (design-to-nextjs, nestjs-enterprise-backend,
    prd-design-build-orchestrator, security-review-and-fix,
    prototype-to-saas, exploratory-qa)
  • 24 specialized subagents
  • Hooks for auto-typecheck after builder agents

${BOLD}Next steps:${NC}

  1. Start a Claude Code session in any project:

     ${BLUE}cd ~/my-project${NC}
     ${BLUE}claude${NC}

  2. Verify the plugin loaded:

     ${BLUE}/plugin list${NC}     ${YELLOW}# should show superdev${NC}
     ${BLUE}/agents${NC}          ${YELLOW}# should show all 24 namespaced agents${NC}

  3. Kick off a full-stack build:

     ${BLUE}I have a PRD at docs/PRD.md and a design at design/.${NC}
     ${BLUE}Build the full-stack app.${NC}

${BOLD}Other entry points:${NC}

  • Existing Next.js prototype with JSON fixtures:
    "${BLUE}Help me productionize this Next.js prototype${NC}"

  • Standalone security audit:
    "${BLUE}Run a security audit on this codebase${NC}"

  • Standalone QA pass:
    "${BLUE}Run a production-readiness QA pass${NC}"

${BOLD}Optional — enable agent teams (experimental):${NC}

  ${BLUE}bash $(basename "${BASH_SOURCE[0]}") --enable-teams${NC}

  This enables adversarial 3-teammate reviews for security audits,
  QA report synthesis, and gap audits. Costs ~3× tokens; use for
  high-stakes work only.

${BOLD}Commands:${NC}

  ${BLUE}bash $(basename "${BASH_SOURCE[0]}") --verify${NC}        Verify install
  ${BLUE}bash $(basename "${BASH_SOURCE[0]}") --enable-teams${NC}  Enable agent teams
  ${BLUE}bash $(basename "${BASH_SOURCE[0]}") --uninstall${NC}     Remove plugin

EOF

  if [[ "$ENV_TYPE" == "WSL" ]]; then
    cat <<EOF
${BOLD}${YELLOW}WSL note:${NC}
  Claude Code must run inside WSL (not Windows). If 'claude' isn't
  found, install it inside your WSL distro:
    ${BLUE}curl -fsSL https://claude.ai/install.sh | sh${NC}

EOF
  fi
}

show_help() {
  cat <<EOF
${BOLD}install-superdev.sh${NC} — install the superdev Claude Code plugin

${BOLD}USAGE${NC}
  bash install-superdev.sh [options]

${BOLD}OPTIONS${NC}
  (none)            Install the plugin (default action)
  --verify          Verify an existing installation
  --enable-teams    Enable CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 in settings
  --uninstall       Remove the plugin and de-register from settings
  --help            Show this help

${BOLD}ENVIRONMENT VARIABLES${NC}
  SUPERDEV_ZIP   Path to the plugin zip if not alongside this script
  PLUGIN_ZIP          Override the expected zip filename
                      (default: superdev.zip)

${BOLD}WHAT THIS SCRIPT DOES${NC}
  1. Verifies Claude Code, Python 3, and unzip are installed
  2. Detects WSL / Linux / macOS
  3. Extracts the plugin to ~/.claude/plugins/superdev/
  4. Registers the plugin path in ~/.claude/settings.json
  5. Validates the install

${BOLD}EXAMPLES${NC}
  # Standard install
  bash install-superdev.sh

  # Install with agent teams enabled
  bash install-superdev.sh
  bash install-superdev.sh --enable-teams

  # Verify current install
  bash install-superdev.sh --verify

  # Plugin zip in a non-default location
  SUPERDEV_ZIP=~/Downloads/superdev.zip bash install-superdev.sh

EOF
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
  printf "${BOLD}${BLUE}"
  printf "╔════════════════════════════════════════════════════════════╗\n"
  printf "║          superdev installer for Claude Code            ║\n"
  printf "║                       v${PLUGIN_VERSION}                                  ║\n"
  printf "╚════════════════════════════════════════════════════════════╝${NC}\n\n"

  detect_env
  log_info "Detected environment: ${ENV_TYPE}"

  case "${1:-install}" in
    --help|-h|help)
      show_help
      exit 0
      ;;
    --verify|verify)
      do_verify
      exit 0
      ;;
    --uninstall|uninstall)
      do_uninstall
      exit 0
      ;;
    --enable-teams|enable-teams)
      enable_agent_teams
      exit 0
      ;;
    install|"")
      check_prereq
      locate_zip
      install_plugin
      verify_structure
      register_in_settings
      show_usage
      ;;
    *)
      log_error "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
}

main "$@"
