# Project-Scoped Superdev Installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Superdev installation, runtime path, and learned-memory workflow project-scoped for Claude and Codex.

**Architecture:** Claude installation delegates to the supported CLI with `--scope project`, while Codex discovery stays in the repository marketplace. Bundled resources resolve through relative plugin paths or `${CLAUDE_PLUGIN_ROOT}`, and a standard-library Python suite enforces the project-only contract across scripts, docs, prompts, hooks, and the distribution archive.

**Tech Stack:** Bash, Python 3 `unittest`, JSON, Markdown, Claude Code CLI, Codex plugin manifests

---

### Task 1: Add project-scope regression tests

**Files:**
- Create: `tests/test_project_scope.py`

- [ ] **Step 1: Write the static failing tests**

Create a `unittest.TestCase` that scans `README.md`, `INSTALL.md`, `CODEX.md`, `install-superdev.sh`, `plugins/superdev/README.md`, all plugin Markdown files, and `plugins/superdev/hooks/hooks.json`. Exclude `docs/superpowers/` because the design and plan intentionally document the legacy strings. Assert that active surfaces do not contain:

```python
FORBIDDEN_GLOBAL_PATTERNS = {
    "global skill path": "~/.claude/skills",
    "global plugin target": "~/.claude/plugins/superdev",
    "obsolete plugin root": "CLAUDE_PLUGIN_DIR",
    "global lesson file": "~/.claude/CLAUDE.md",
    "personal Codex marketplace": "~/.agents/plugins/marketplace.json",
    "personal Codex plugin directory": "~/.codex/plugins",
}
```

Add assertions that all documented Claude install, uninstall, marketplace-add, enable, and disable commands which mention Superdev include `--scope project`; that the Codex docs name `.agents/plugins/marketplace.json`; and that inventory contains exactly 16 `SKILL.md` files and 51 agent Markdown files.

- [ ] **Step 2: Write the installer behavior failing tests**

Use `tempfile.TemporaryDirectory`, initialize a temporary Git repository, and prepend a fake `claude` executable to `PATH`. The fake executable records every argument in `FAKE_CLAUDE_LOG`, creates project `.claude/settings.json` for install, returns a JSON plugin list, and removes the project entry for uninstall. Cover these behaviors:

Name the behavior tests `test_install_uses_project_scope`, `test_uninstall_uses_project_scope`, `test_verify_checks_project_install`, `test_enable_teams_preserves_project_settings`, `test_invalid_project_settings_are_not_overwritten`, and `test_installer_refuses_to_run_outside_git_project`.

Set `HOME` to a separate empty temporary directory and assert it remains unchanged after every successful action.

- [ ] **Step 3: Run the tests and verify RED**

Run:

```bash
python3 -m unittest -v tests/test_project_scope.py
```

Expected: failures identify the current global installer, global bundled paths, obsolete hook variable, global lesson instructions, missing project-scope commands, and stale archive.

- [ ] **Step 4: Commit the red tests**

```bash
git add tests/test_project_scope.py
git commit -m "test: enforce project-scoped superdev"
```

### Task 2: Replace the global Claude installer

**Files:**
- Modify: `install-superdev.sh`
- Test: `tests/test_project_scope.py`

- [ ] **Step 1: Replace the installer with a project-scoped CLI wrapper**

Implement these functions with LF line endings:

```bash
resolve_project() {
  command -v git >/dev/null 2>&1 || fail "git is required"
  PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" ||
    fail "Run this command from inside the target Git project."
  [[ -w "$PROJECT_ROOT" ]] || fail "Project root is not writable: $PROJECT_ROOT"
  SETTINGS_FILE="$PROJECT_ROOT/.claude/settings.json"
  cd "$PROJECT_ROOT"
}

install_plugin() {
  require_claude
  claude plugin marketplace add boparaiamrit/superdev --scope project
  claude plugin install superdev@superdev --scope project
  verify_install
}

uninstall_plugin() {
  require_claude
  claude plugin uninstall superdev@superdev --scope project
}
```

`verify_install` must parse `.claude/settings.json`, require `enabledPlugins["superdev@superdev"] is True`, call `claude plugin list --json`, and recursively confirm that the returned JSON contains `superdev@superdev` or `superdev`. `enable_teams` must preserve unrelated JSON keys and write only `$PROJECT_ROOT/.claude/settings.json`. Invalid JSON must terminate without replacing the file.

The help and success output must state project scope, the detected project root, and current inventory. Read the version from `plugins/superdev/.claude-plugin/plugin.json` and count skills and agents dynamically when the source tree is present.

- [ ] **Step 2: Run installer tests and verify GREEN**

```bash
python3 -m unittest -v tests.test_project_scope.ProjectScopeInstallerTests
bash -n install-superdev.sh
```

Expected: all installer tests pass and Bash syntax exits 0.

- [ ] **Step 3: Commit the installer fix**

```bash
git add install-superdev.sh tests/test_project_scope.py
git commit -m "fix: install superdev at project scope"
```

### Task 3: Make bundled resource paths portable

**Files:**
- Modify: `plugins/superdev/hooks/hooks.json`
- Modify: `plugins/superdev/agents/backend-extractor.md`
- Modify: `plugins/superdev/agents/backend-module-builder.md`
- Modify: `plugins/superdev/agents/bug-reproducer.md`
- Modify: `plugins/superdev/agents/codebase-discoverer.md`
- Modify: `plugins/superdev/agents/contracts-author.md`
- Modify: `plugins/superdev/agents/dependency-auditor.md`
- Modify: `plugins/superdev/agents/design-inventory.md`
- Modify: `plugins/superdev/agents/dynamic-auditor.md`
- Modify: `plugins/superdev/agents/frontend-module-builder.md`
- Modify: `plugins/superdev/agents/frontend-rewirer.md`
- Modify: `plugins/superdev/agents/gap-auditor.md`
- Modify: `plugins/superdev/agents/inertia-module-builder.md`
- Modify: `plugins/superdev/agents/integration-tester.md`
- Modify: `plugins/superdev/agents/laravel-module-builder.md`
- Modify: `plugins/superdev/agents/migration-planner.md`
- Modify: `plugins/superdev/agents/monorepo-bootstrapper.md`
- Modify: `plugins/superdev/agents/plan-architect.md`
- Modify: `plugins/superdev/agents/prd-analyst.md`
- Modify: `plugins/superdev/agents/qa-consistency-checker.md`
- Modify: `plugins/superdev/agents/qa-environment.md`
- Modify: `plugins/superdev/agents/qa-flow-tester.md`
- Modify: `plugins/superdev/agents/qa-performance-prober.md`
- Modify: `plugins/superdev/agents/schema-reverse-engineer.md`
- Modify: `plugins/superdev/agents/security-fixer.md`
- Modify: `plugins/superdev/agents/security-inventory.md`
- Modify: `plugins/superdev/agents/static-auditor.md`
- Modify: `plugins/superdev/skills/design-to-nextjs/SKILL.md`
- Modify: `plugins/superdev/skills/exploratory-qa/SKILL.md`
- Modify: `plugins/superdev/skills/exploratory-qa/references/qa-agents.md`
- Modify: `plugins/superdev/skills/laravel-enterprise-backend/SKILL.md`
- Modify: `plugins/superdev/skills/nestjs-enterprise-backend/SKILL.md`
- Modify: `plugins/superdev/skills/prd-design-build-orchestrator/SKILL.md`
- Modify: `plugins/superdev/skills/prd-design-build-orchestrator/references/agent-definitions.md`
- Modify: `plugins/superdev/skills/prd-design-build-orchestrator/references/execution-pipeline.md`
- Modify: `plugins/superdev/skills/prd-design-build-orchestrator/references/orchestration-patterns.md`
- Modify: `plugins/superdev/skills/prototype-to-saas/SKILL.md`
- Modify: `plugins/superdev/skills/prototype-to-saas/references/migration-agents.md`
- Modify: `plugins/superdev/skills/security-review-and-fix/SKILL.md`
- Modify: `plugins/superdev/skills/security-review-and-fix/references/security-agents.md`
- Test: `tests/test_project_scope.py`

- [ ] **Step 1: Replace prose resource paths**

Use paths relative to the containing Markdown file:

```text
agents/qa-environment.md
  -> ../skills/exploratory-qa/references/environment-checklist.md
skills/exploratory-qa/SKILL.md
  -> ../exploratory-qa/references/environment-checklist.md
skills/exploratory-qa/references/qa-agents.md
  -> ../../exploratory-qa/references/environment-checklist.md
```

Keep references in code spans or Markdown links so the host can resolve them without a home-directory assumption.

- [ ] **Step 2: Replace executable paths and hook roots**

Shell commands that invoke bundled scripts must use quoted plugin-root paths:

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/<skill>/references/<script>.sh"
```

Replace each hook command with a direct `${CLAUDE_PLUGIN_ROOT}/hooks/scripts/maybe-learn.sh` or `${CLAUDE_PLUGIN_ROOT}/hooks/scripts/detect-frustration.sh` reference. Remove cache scans and the legacy `~/.claude/plugins/superdev` fallback.

- [ ] **Step 3: Run path tests and validate JSON**

```bash
python3 -m unittest -v tests.test_project_scope.ProjectScopeStaticTests.test_no_global_superdev_paths
python3 -m json.tool plugins/superdev/hooks/hooks.json >/dev/null
```

Expected: both commands exit 0.

- [ ] **Step 4: Commit portable paths**

```bash
git add plugins/superdev/agents plugins/superdev/skills plugins/superdev/hooks/hooks.json
git commit -m "fix: resolve bundled resources from plugin root"
```

### Task 4: Remove global learning behavior

**Files:**
- Modify: `plugins/superdev/agents/learn-from-frustration.md`
- Modify: `plugins/superdev/skills/superdev-self-learning/SKILL.md`
- Modify: `README.md`
- Test: `tests/test_project_scope.py`

- [ ] **Step 1: Restrict lesson persistence to the project**

Remove the optional global branch, global command example, global `CLAUDE.md` section, and promotion wording. Preserve the existing project memory behavior:

```text
Claude: .claude/memory/superdev-learned/ and ./CLAUDE.md
Codex:  .superdev/memory/superdev-learned/
```

State explicitly that Superdev never writes to a global instruction file.

- [ ] **Step 2: Run the memory scope tests**

```bash
python3 -m unittest -v tests.test_project_scope.ProjectScopeStaticTests.test_no_global_superdev_paths
```

Expected: pass.

- [ ] **Step 3: Commit project-only memory**

```bash
git add README.md plugins/superdev/agents/learn-from-frustration.md plugins/superdev/skills/superdev-self-learning/SKILL.md
git commit -m "fix: keep superdev learning project-local"
```

### Task 5: Align Claude and Codex installation documentation

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `CODEX.md`
- Modify: `plugins/superdev/README.md`
- Test: `tests/test_project_scope.py`

- [ ] **Step 1: Update Claude guidance**

Use the exact project-scoped commands everywhere:

```bash
claude plugin marketplace add boparaiamrit/superdev --scope project
claude plugin install superdev@superdev --scope project
```

Document migration from legacy user scope with this explicit command:

```bash
claude plugin uninstall superdev@superdev --scope user
```

Explain that users of the interactive `/plugin` browser must select Project scope.

- [ ] **Step 2: Update Codex guidance**

Document only the repository marketplace and project-owned plugin source:

```text
<project>/.agents/plugins/marketplace.json
<project>/plugins/superdev/
```

Describe opening `/plugins` from the target repository, choosing `Superdev Local`, installing, and starting a new session. Explicitly state that Superdev must not be placed in a personal marketplace.

- [ ] **Step 3: Correct stale installation copy**

Replace “install anywhere,” global-install claims, 6-skill/24-agent bundle counts, and global-session wording with project-only language and the current 16-skill/51-agent inventory.

- [ ] **Step 4: Run documentation tests**

```bash
python3 -m unittest -v tests.test_project_scope.ProjectScopeStaticTests
```

Expected: all static tests pass.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md INSTALL.md CODEX.md plugins/superdev/README.md tests/test_project_scope.py
git commit -m "docs: require project-scoped superdev installs"
```

### Task 6: Refresh the distributable plugin and validate both hosts

**Files:**
- Modify: `plugins/superdev/.codex-plugin/plugin.json`
- Modify: `superdev.zip`
- Test: `tests/test_project_scope.py`

- [ ] **Step 1: Apply the Codex development cachebuster**

Run the plugin-creator helper against the existing local plugin:

```bash
python3 /home/boparaiamrit/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py plugins/superdev
```

Expected: preserve the `1.6.0` base version and set one `+codex.local-<UTC timestamp>` suffix. Do not reinstall into a personal marketplace because Superdev is project-only.

- [ ] **Step 2: Rebuild the archive from the corrected plugin tree**

Remove the old archive entry-by-entry through the zip tool and create a fresh archive whose top-level directory is `superdev/`:

```bash
(cd plugins && zip -qr -FS ../superdev.zip superdev)
```

- [ ] **Step 3: Validate manifests and archive contents**

```bash
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
python3 -m json.tool plugins/superdev/.claude-plugin/plugin.json >/dev/null
python3 -m json.tool plugins/superdev/.codex-plugin/plugin.json >/dev/null
python3 /home/boparaiamrit/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/superdev
python3 -m unittest -v tests/test_project_scope.py
```

Expected: all commands exit 0 and the archive test finds no forbidden global path.

- [ ] **Step 4: Commit packaging changes**

```bash
git add plugins/superdev/.codex-plugin/plugin.json superdev.zip tests/test_project_scope.py
git commit -m "chore: refresh project-scoped superdev package"
```

### Task 7: Final verification and review

**Files:**
- Verify all modified files

- [ ] **Step 1: Run the full verification suite**

```bash
python3 -m unittest -v tests/test_project_scope.py
bash -n install-superdev.sh
python3 /home/boparaiamrit/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/superdev
git diff --check main...HEAD
```

Expected: tests pass with zero failures, Bash exits 0, plugin validation succeeds, and diff check is clean.

- [ ] **Step 2: Audit requirements directly**

```bash
rg -n --hidden --glob '!.git/**' --glob '!docs/superpowers/**' --glob '!tests/**' '~/.claude/skills|~/.claude/plugins/superdev|~/.claude/CLAUDE.md|CLAUDE_PLUGIN_DIR|~/.agents/plugins/marketplace.json|~/.codex/plugins' .
```

Expected: no matches in active Superdev surfaces.

- [ ] **Step 3: Review branch diff and status**

```bash
git status --short
git diff --stat main...HEAD
git log --oneline main..HEAD
```

Expected: clean worktree and focused commits for tests, installer, paths, memory, docs, and package validation.
