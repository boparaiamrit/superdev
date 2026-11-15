# Superdev plugin

Superdev's 15 skills, 41 agents and 25 hard rules take a product from a PRD and a design to a released, verified Navree app. The skills hold the order of work, the files written to disk, the rules and the proofs; Navree's own skills, installed into every app with `navree skills:install`, hold the framework facts. The build itself is [superdev-build](skills/superdev-build/SKILL.md); its [hard rules](skills/superdev-build/references/hard-rules.md) say where each applies and how it is checked.

## Skills

By the step of a build that uses them; each also runs on its own when a request matches its description.

| Step | Skills |
|---|---|
| Steps 1 to 10, in order | [superdev-build](skills/superdev-build/SKILL.md) |
| Step 3, when the source is a prototype or an older product | [prototype-to-navree](skills/prototype-to-navree/SKILL.md), [design-preservation](skills/design-preservation/SKILL.md) |
| Step 4. Foundation | [security-foundation](skills/security-foundation/SKILL.md); the demo seed in [backend-on-navree](skills/backend-on-navree/SKILL.md) |
| Step 6. Modules | [backend-on-navree](skills/backend-on-navree/SKILL.md); [design-to-navree-ui](skills/design-to-navree-ui/SKILL.md), or [design-to-nextjs](skills/design-to-nextjs/SKILL.md) with [frontend-structure](skills/frontend-structure/SKILL.md); [design-to-tauri](skills/design-to-tauri/SKILL.md) for Tauri clients; [design-preservation](skills/design-preservation/SKILL.md) for a preserved prototype |
| Step 7. Audits | [security-review-and-fix](skills/security-review-and-fix/SKILL.md), then [product-audit](skills/product-audit/SKILL.md) |
| Step 8. QA gate | [product-qa](skills/product-qa/SKILL.md) |
| Step 10. Done | [superdev-done](skills/superdev-done/SKILL.md), [superdev-self-learning](skills/superdev-self-learning/SKILL.md) |
| Any step, when something fails | [systematic-debugging](skills/systematic-debugging/SKILL.md) |

## Agents

The skills dispatch these agents, one module or one task per dispatch. Each agent file says what it reads, what it writes and what it returns.

- **Planning:** `prd-analyst`, `design-inventory`, `gap-auditor`, `plan-architect`.
- **Building:** `navree-app-bootstrapper`, `navree-module-builder`, `navree-ui-screen-builder`, `nextjs-module-builder`, `seed-data-architect`.
- **Prototypes and refactors:** `codebase-discoverer`, `schema-reverse-engineer`, `migration-planner`, `refactor-planner`, `visual-diff-auditor`.
- **Security review:** `repo-cartographer`, `static-auditor`, `dynamic-auditor`, `dependency-auditor`.
- **Audit:** `placeholder-hunter`, `data-source-auditor`, `journey-walker`, `tenancy-isolation-tester`, `module-readiness-rater`, `module-structure-auditor`, `ui-auditor`.
- **QA:** `qa-environment`, `qa-flow-tester`, `qa-consistency-checker`, `qa-performance-prober`, `link-crawler`, `a11y-contrast-auditor`, `role-matrix-tester`, `money-integrity-prober`, `realtime-prober`, `mobile-qa-tester`.
- **Debugging:** `bug-reproducer`, `root-cause-investigator`, `hypothesis-tester`, `regression-verifier`.
- **Fixing:** `fix-applier`.
- **Lessons:** `lesson-writer`.

## Hosts

- **Claude Code** reads `.claude-plugin/plugin.json` and finds the skills in `skills/` and the agents in `agents/` by folder.
- **Codex** reads `.codex-plugin/plugin.json`, which registers `skills/`. It does not load the agent files: the main agent reads an agent file and runs its steps itself, unless the operator asks for delegated work (rule BLD-4 of `superdev-build`).
- Skills reach the plugin's own files, such as `scripts/verify-done.mjs`, through `${CLAUDE_PLUGIN_ROOT}` in Claude Code, and through the path of the installed `plugins/superdev` folder in Codex.

## Development

From the repository root, `python -m unittest discover -s tests -v` runs the tests, and `python tools/build_zip.py` rebuilds `superdev.zip` from this folder (`--check` compares it with the committed archive). Rebuild the archive after any change here.
