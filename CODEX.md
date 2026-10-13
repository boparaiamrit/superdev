# Superdev for Codex

This repository ships a Codex plugin manifest alongside the Claude Code plugin (v2.0.1; see the root README for the current workflow).

## What Codex loads

- `plugins/superdev/.codex-plugin/plugin.json` registers the plugin with Codex.
- `plugins/superdev/skills/*/SKILL.md` exposes the 18 Superdev skills.
- `.agents/plugins/marketplace.json` lets this repo act as a local Codex marketplace.

## What stays Claude-specific

- `plugins/superdev/.claude-plugin/plugin.json` is the Claude Code manifest (same skills/agents tree).
- `plugins/superdev/agents/*.md` are Claude subagent definitions. In Codex, treat them as role-prompt references/checklists the main agent executes directly, unless the user explicitly asks for parallel or delegated agent work.
- `install-superdev.sh` is a Claude Code helper that delegates to `claude plugin ... --scope project` inside the target Git project. Superdev is project-scoped only on both hosts.

There are no hooks in v2 on either host. Verification is explicit everywhere:

- after each backend module: typecheck + tests, then **boot the built dist** and curl its health endpoints
- after each frontend module: typecheck, then open the route in a browser against the running API
- before any "done" claim: `node <superdev-plugin>/scripts/verify-done.mjs` from the target repo root, plus the applicable stack-specific runtime and audit evidence
- after corrections/verifier rejections: record the lesson in the target project's `.claude/memory/superdev-learned/` (see `superdev-self-learning`)

## Codex workflow guidance

Use the named Superdev skills directly:

```text
Use $superdev-build with docs/PRD.md and design/.
Use $security-review-and-fix to audit this codebase.
Use $prototype-to-saas to productionize this Next.js prototype.
Use $superdev-done — are we done?
```

When a skill mentions `.claude/memory/superdev-learned/`, use that same project-local path (it is where the built projects already keep lessons) unless the repo uses a different memory convention you want to preserve.

## Validation

From the repo root:

```bash
python -m unittest discover -s tests -v
node --check plugins/superdev/scripts/verify-done.mjs
```

On Windows, run the full Python suite inside WSL so installer tests use Bash-compatible paths. The Node syntax check may run on the Windows host if WSL has no Node installation.
