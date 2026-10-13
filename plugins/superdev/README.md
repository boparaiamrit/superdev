# Superdev

A Claude Code + Codex plugin bundling **18 skills + 54 agents** for full-stack monorepo builds: direct sequential building by the main agent, recipe skills for each stack layer, read-only auditor agents, design preservation, atomic frontend refactoring, and live runtime verification.

> **v2.0.0 — the conductor is gone.** SuperDev v1 routed everything through a conductor skill that dispatched parallel builder waves, installed agent copies into each project, and graded its own completion ledger. Across the production projects built with it (ForgeMyTool, PostMitra, 4Brokr), that model caused parallel contract races, green static gates over dead runtimes, stale abridged agent installs, and "done" claims nothing machine-checkable backed. v2 keeps everything that proved valuable — the recipes, the auditors, the conventions — and replaces the conductor with [`superdev-build`](skills/superdev-build/SKILL.md): the main agent builds directly, one verified module at a time, and [`scripts/verify-done.mjs`](scripts/verify-done.mjs) runs the done checks live (including booting the built API). The failure lessons are codified in [`hard-rules.md`](skills/superdev-build/references/hard-rules.md).

## Host support

- **Claude Code:** loads `.claude-plugin/plugin.json`; skills and all 54 agents are auto-discovered from `skills/` and `agents/`. There are no hooks — verification is explicit (`verify-done.mjs`, per-module runtime checks).
- **Codex:** loads the 18 skills through `.codex-plugin/plugin.json`. Treat `agents/*.md` as role-prompt references/checklists unless the user explicitly asks for delegated work. See [`../../CODEX.md`](../../CODEX.md).

## The 18 skills

| Skill | Purpose |
|---|---|
| `superdev-build` 🆕 v2.0.0 | Full-stack build SOP for the main agent: plan artifacts → stack choice → bootstrap → **contracts first** → one module at a time (backend → boot-verify → frontend → browser-verify) → audits → verify-done |
| `design-to-nextjs` | Translate **Claude Design** handoffs into production Next.js (shadcn-everywhere, view-shape contract, dual-mode adapter; checks Radix vs **Base UI** before composing) |
| `design-to-laravel` | Translate **Claude Design** → **Laravel + Inertia 3 + React 19** monolith (typed props, Wayfinder, `useForm`, Fortify + spatie/permission). Default Laravel frontend |
| `design-preservation` | When source is a **prototype**, copy verbatim into `design-source/`, mirror at `/__design-source/`, pixel-diff at ≤ 1% drift. Holy-grail rule: no restyling |
| `nestjs-enterprise-backend` | Nest.js + PG17/TimescaleDB + Drizzle + CASL + BullMQ + `@Audit` (on controller handlers, side-effect-proven) + view-shape contract |
| `laravel-enterprise-backend` | **Laravel 13** alternative — PostgreSQL + TimescaleDB, DB cache/sessions, SQS, Eloquent API Resources + hand-written TS contract, `#[Audit]` → hypertable, global-scope tenancy, Title-Case enums, Boost |
| `laravel-bref-deploy` | Serverless deploy of the Laravel backend on AWS Lambda via **Bref 3.x** (web/SQS-worker/console, EventBridge scheduler, S3/CloudFront, SSM, no VPC) |
| `frontend-modular-architecture` | Structure law: page ≤ 100 / component ≤ 200 lines, dedicated Zustand stores per module, wizards split per-step, overlays in `parts/<name>/` with shadcn Portal primitives |
| `frontend-refactoring` | **Atomic one-module conversion** of a fat module — plan → review → behavior baseline → atomic execute → zero-drift verify, hard rollback on drift |
| `prototype-to-saas` | Convert a single-user Next.js prototype (JSON-as-backend) into a multi-tenant SaaS without breaking the working UI |
| `security-review-and-fix` | Six-phase security audit (inventory, static, dynamic, dependency, triage, fix) |
| `exploratory-qa` | Playwright-driven QA: happy + edge cases, consistency audit, performance probing |
| `systematic-debugging` | 5-phase root-cause debugging; refuses fixes without a verified `ROOT_CAUSE.md` |
| `product-completeness-audit` | "A beautiful UI with hardcoded data is a demo" — REAL / MOCKED / HYBRID detection in production mode |
| `production-readiness-audit` | Five passes score every module 1–10 (min wins, hard caps), **each score cited with command/browser/DB evidence**; fix → re-audit until all ≥ 9 |
| `brutal-exhaustive-audit` | Every file / route / flow / data path / edge case — disk-tracked checklists, final ship gate |
| `superdev-self-learning` | Deliberate lesson capture into the target project's `.claude/memory/superdev-learned/`; stack-general lessons are promoted into `hard-rules.md` |
| `superdev-done` | Runs `scripts/verify-done.mjs` — live Definition-of-Done (typecheck/lint/build per package, dist boot + health, contracts format, suppression + placeholder sweeps) |

> 🔀 **Stack choice** — `superdev-build` Step 2 asks **Laravel or Nest.js**. Laravel then asks the frontend: **Inertia monolith** (default) or **decoupled Next.js**. Nest.js always pairs with Next.js. The choice persists in `STACK.md`.

**Every skill works standalone.** `superdev-build` is only the sequencing for a full greenfield build; asking for "a security audit" runs `security-review-and-fix` alone, with no pipeline overhead.

## The 54 agents

Auto-loaded by the plugin (single source in `agents/`; nothing is copied into target projects). Roles:

- **Planning/extraction (read-mostly):** `prd-analyst`, `design-inventory`, `gap-auditor`, `plan-architect`, `codebase-discoverer`, `schema-reverse-engineer`, `repo-cartographer`
- **Builders (optional, one module at a time):** `monorepo-bootstrapper`, `contracts-author`, `backend-module-builder`, `laravel-module-builder`, `frontend-module-builder`, `inertia-module-builder`, `backend-extractor`, `frontend-rewirer`, `atomic-module-converter`, `seed-data-architect`, `design-source-mirror`, fixers (`security-fixer`, `fix-applier`)
- **Auditors/testers (read-only):** `ui-auditor`, `module-structure-auditor`, `portal-correctness-auditor`, `integration-tester`, `tenancy-isolation-tester`, security five (`security-inventory`, `static-auditor`, `dynamic-auditor`, `dependency-auditor`, + `security-fixer`), QA four (`qa-environment`, `qa-flow-tester`, `qa-consistency-checker`, `qa-performance-prober`), completeness/brutal walkers and hunters (`placeholder-hunter`, `wiring-auditor`, `route-completeness-checker`, `data-flow-real-vs-mock`, `journey-walker`, `route-walker`, `flow-walker`, `data-flow-tracer`, `edge-case-prober`, `audit-synthesizer`, `design-fidelity-auditor`, `module-readiness-rater`), debugging (`bug-reproducer`, `root-cause-investigator`, `hypothesis-tester`, `regression-verifier`), migration/conversion (`migration-planner`, `module-conversion-planner`, `module-behavior-snapshotter`, `conversion-verifier`), and `learn-from-frustration`

The default build path executes builder checklists in the main session; dispatch a builder subagent only for a single bounded module, never backend+frontend against a same-step contract in parallel (hard-rules #4).

## Verification model (no hooks, no ledger)

| Check | When | How |
|---|---|---|
| Typecheck + tests + **boot the dist + curl health** + one real endpoint + one side effect | After every backend module | `superdev-build` Step 5 (hard-rules #1, #5) |
| Typecheck + browser-open the route in production mode | After every frontend module | Step 5 (hard-rules #9) |
| Full live gate: per-package typecheck/lint/build, boot, contracts format, swagger landmine, suppression + placeholder sweeps | Before any "done" claim | `node scripts/verify-done.mjs` (see `superdev-done`) |
| Security / QA / completeness / readiness | Step 6, by risk | Standalone audit skills above |

## Placeholder convention

Workspace-scope agnostic — substitute placeholders with your project's values: `<scope>` (npm scope from root `package.json`), `<workspace>` (monorepo dir), `<app>` (lowercase prefix), `<APP_NAME>` (brand), `<feature>`, `<pm>` (package manager from lockfile: `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lock*` → bun, else npm). Examples default to pnpm + Turborepo; existing lockfiles are honored.

## Installation

**Claude Code:**

```bash
/plugin marketplace add boparaiamrit/superdev
/plugin install superdev
# local development:
claude --plugin-dir ~/superdev/plugins/superdev
# or from the bundled zip:
bash install-superdev.sh
```

**Codex:** use the repo-local marketplace `.agents/plugins/marketplace.json`, then invoke skills directly:

```text
Use $superdev-build with docs/PRD.md and design/.
Use $security-review-and-fix to audit this codebase.
Use $prototype-to-saas to productionize this prototype.
```

## Quick start

```text
I have a PRD at docs/PRD.md and a design at design/. Build the full-stack app.
```

`superdev-build` produces the plan artifacts, confirms with you, asks the stack question, then builds module by module with runtime proof at each step.

## Architectural commitments (all skills)

1. **Monorepo + shared contracts** — one source of truth for wire shapes (CommonJS contracts build, hard-rules #3)
2. **View-shape contract** — API returns render-ready data; UI renders without `?.`/`??` on contract fields
3. **Title-Case enums** — DB = wire = UI label
4. **shadcn/ui only** — every visual primitive from `@/components/ui/*`; confirm Radix vs Base UI first
5. **Docker for all infrastructure** (Laravel serverless target: managed Postgres/Timescale instead)
6. **Permissions + audit on every mutation** — proven by side-effect checks, not decorator presence
7. **Dual-mode adapter** — demo fixtures vs production API; mock routes sanitized and demo-gated
8. **No default secrets, no raw-JSON operator UI, one canonical public origin** — the operator-facing hard rules

## Development

```bash
python -m unittest discover -s tests -v   # plugin integrity: frontmatter, links, counts, no stale machinery, zip parity
```

After changing `skills/`, `agents/`, or `scripts/`, refresh `superdev.zip` (zip the `plugins/superdev/` tree under a `superdev/` prefix) and run the tests — they fail on zip drift. In Claude Code, `/reload-plugins` picks up changes.

## License

MIT — see [LICENSE](../../LICENSE).
