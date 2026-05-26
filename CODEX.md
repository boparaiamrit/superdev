# Superdev for Codex

This repository now ships a Codex plugin manifest alongside the original Claude Code plugin.

## What Codex loads

- `plugins/superdev/.codex-plugin/plugin.json` registers the plugin with Codex.
- `plugins/superdev/skills/*/SKILL.md` exposes the 13 Superdev skills.
- `.agents/plugins/marketplace.json` lets this repo act as a local Codex marketplace.

## What stays Claude-specific

- `plugins/superdev/.claude-plugin/plugin.json` is still the Claude Code manifest.
- `plugins/superdev/hooks/hooks.json` uses Claude hook events such as `SubagentStart`, `SubagentStop`, and `UserPromptSubmit`.
- `plugins/superdev/agents/*.md` are Claude subagent definitions. In Codex, treat them as role-prompt references unless the user explicitly asks for parallel or delegated agent work.
- `install-superdev.sh` installs to `~/.claude/plugins/`; it is intentionally left for Claude users.

## Codex workflow guidance

Use the named Superdev skills directly:

```text
Use $security-review-and-fix to audit this codebase.
Use $prototype-to-saas to productionize this Next.js prototype.
Use $prd-design-build-orchestrator with docs/PRD.md and design/.
```

When a skill mentions Claude auto-hooks, run the same checks explicitly in Codex:

- after backend work: run the API typecheck
- after frontend work: run the web typecheck
- before Playwright QA: verify the API and web app are running
- after verifier failures: record the lesson under project memory before retrying

When a skill mentions `.claude/memory/superdev-learned/`, use `.superdev/memory/superdev-learned/` for Codex-hosted projects unless the repo already has a Claude memory directory you want to preserve.

## Validation

Run this from the repo root:

```bash
python ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/superdev
```
