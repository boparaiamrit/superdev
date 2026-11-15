# Superdev in Codex

Codex loads superdev's skills. The agents and the rest of the plugin are files the skills read.

## What Codex loads

- `plugins/superdev/.codex-plugin/plugin.json` registers the plugin; its `"skills": "./skills/"` makes every `skills/*/SKILL.md` available.
- `.agents/plugins/marketplace.json` makes the repository a local marketplace, **Superdev Local**; [INSTALL.md](INSTALL.md) describes the install.
- `plugins/superdev/agents/*.md` are not loaded. They are role prompts: the main agent reads the agent file and runs its steps itself, unless the operator asks for delegated work (rule BLD-4 of `superdev-build`).

## Using the skills

```text
Use $superdev-build with the PRD at docs/prd.md and the design in docs/design/.
Use $product-qa in gate mode before the release.
Use $security-review-and-fix on this Navree app.
Use $prototype-to-navree to move this prototype to Navree.
```

## Paths

- Wherever a skill says `${CLAUDE_PLUGIN_ROOT}`, use the path of the `plugins/superdev` folder Codex installed the plugin from, for example `node <that path>/scripts/verify-done.mjs --suites --strict` from the app root.
- Lessons live in `.claude/memory/superdev-learned/` in the app on both hosts.
- `navree skills:install` puts Navree's skills in both `.claude/skills/` and `.agents/skills/` of the app.

## Tests

From the repository root:

```bash
python -m unittest discover -s tests -v
```
