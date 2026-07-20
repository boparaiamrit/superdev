# Superdev project installer

Superdev is installed for one project at a time. It must not be enabled at user or personal scope.

## Claude Code

Run the supported Claude CLI commands from the target Git project:

```bash
claude plugin marketplace add boparaiamrit/superdev --scope project
claude plugin install superdev@superdev --scope project
```

The interactive `/plugin` browser is also supported, but you must choose **Project scope** when installing.

### Project-only helper

From the target project, run the helper by its path:

```bash
cd /path/to/target-project
bash /path/to/superdev/install-superdev.sh
```

The helper:

- requires Claude Code, Git, and Python 3;
- refuses to run outside a Git project;
- delegates marketplace and plugin installation to Claude with `--scope project`;
- verifies the project configuration and Claude plugin list; and
- never writes Superdev configuration to user or personal settings.

Optional project-scoped commands:

```bash
bash /path/to/superdev/install-superdev.sh --verify
bash /path/to/superdev/install-superdev.sh --enable-teams
bash /path/to/superdev/install-superdev.sh --uninstall
```

### Migrate an older user-scoped install

Removal from user scope is intentionally explicit because it changes configuration outside the current project:

```bash
claude plugin uninstall superdev@superdev --scope user
claude plugin marketplace add boparaiamrit/superdev --scope project
claude plugin install superdev@superdev --scope project
```

## Codex

Keep the repository marketplace and plugin source inside the target project:

```text
.agents/plugins/marketplace.json
plugins/superdev/
```

Start Codex from that project, open `/plugins`, choose **Superdev Local**, install Superdev, and start a new session. Do not place Superdev in a personal marketplace.

## Bundle contents

- `install-superdev.sh` — project-scoped Claude CLI helper
- `superdev.zip` — optional archive of the current plugin source
- `plugins/superdev/` — 18 skills, 54 agent prompts, and hooks
- `.agents/plugins/marketplace.json` — Codex repository marketplace
- `.claude-plugin/marketplace.json` — Claude marketplace catalog
