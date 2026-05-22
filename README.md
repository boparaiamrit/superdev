# Superdev

A Claude Code plugin marketplace bundling **6 skills** and **24 specialized subagents** for full-stack monorepo builds.

**Workspace-scope agnostic** — hooks use path-based `pnpm` filters and agent docs use `<scope>` / `<workspace>` / `<app>` / `<APP_NAME>` placeholders, so the plugin works in any pnpm monorepo regardless of the `@scope` you use. Install it globally in `~/.claude/plugins/` to use across every project, or check it into a single monorepo for private use — same behavior either way.

## Install

### Via marketplace (recommended)

```bash
/plugin marketplace add boparaiamrit/superdev
/plugin install superdev
```

### Via installer script (bundled zip)

```bash
bash install-superdev.sh
```

The installer extracts the plugin to `~/.claude/plugins/superdev/` and registers it in `~/.claude/settings.json` so every Claude Code session loads it.

### For local development

```bash
git clone https://github.com/boparaiamrit/superdev
claude --plugin-dir superdev/plugins/superdev
```

## What's inside

- **6 skills:** `design-to-nextjs`, `nestjs-enterprise-backend`, `prd-design-build-orchestrator`, `security-review-and-fix`, `prototype-to-saas`, `exploratory-qa`
- **24 subagents** across build, security, migration, and QA workstreams (auto-loaded — no install scripts)
- **Hooks:** auto-typecheck on every builder-agent finish; stack-up verification before QA agents run

Full plugin details: [`plugins/superdev/README.md`](./plugins/superdev/README.md).

## Repository layout

```
superdev/
├── .claude-plugin/marketplace.json     # marketplace manifest
├── plugins/superdev/                   # the plugin itself
│   ├── .claude-plugin/plugin.json
│   ├── agents/                         # 24 subagent definitions
│   ├── skills/                         # 6 skills with references/
│   ├── hooks/hooks.json
│   └── README.md
├── install-superdev.sh                 # bundled installer (extracts zip)
├── superdev.zip                        # plugin bundle for the installer
├── INSTALL.md                          # installer instructions
└── LICENSE
```

## License

MIT — see [LICENSE](./LICENSE).
