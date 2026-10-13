# Changelog

All notable changes to Superdev are documented here. Releases are annotated git tags (`vX.Y.Z`) on `main`; from v2.0.0 they are also published as GitHub Releases with the packaged `superdev.zip` attached.

## v2.0.0 — 2026-10-13

**The conductor is removed.** SuperDev v1 routed every build through an orchestrator skill that dispatched parallel builder waves, installed agent copies into each project, threaded lessons via bash hooks, and graded its own completion ledger. Evidence from the production projects built with it (ForgeMyTool, PostMitra, 4Brokr) showed parallel contract races, production binaries dead on arrival under green test suites, stale abridged agent installs, and done-claims no machine check backed. v2 keeps the recipes, auditors, and conventions — the main agent builds directly and proves each step at runtime.

### Added

- **`superdev-build` skill** — the full-build SOP executed by the main agent: plan artifacts (`PRD_DIGEST` / `DESIGN_DIGEST` / `AUDIT` / `EXECUTION_PLAN`) → user confirmation → stack choice (Nest.js/Laravel × Next.js/Inertia) → bootstrap proven by boot → **all contracts first** → one module at a time (backend → boot-the-dist + curl + side-effect verify → frontend → browser verify) → standalone audits → verify-done.
- **`hard-rules.md`** (`superdev-build/references/`) — the 12 production failure lessons promoted out of per-project memory: boot the built artifact, never `patchNestJsSwagger()`, CommonJS contracts, contracts single-owner/upfront, verify side effects not decorators, no default secrets / unsanitized fs routes / ungated mocks, Radix-vs-Base-UI detection, drizzle-kit tsconfig, browser-smoke client-mounted routes, no raw-JSON operator UI, one canonical public origin, secrets hygiene.
- **`scripts/verify-done.mjs`** — cross-platform (Node) live Definition-of-Done: per-package typecheck/lint/build, boots `apps/api/dist` and polls health endpoints, contracts module-format + `patchNestJsSwagger` landmine checks, no-new-suppressions sweep vs git HEAD, demo/placeholder sweep. `superdev-done` now runs it.
- **`tests/test_plugin_integrity.py`** — guards frontmatter, skill links, documented counts (18 skills / 54 agents), zip parity, and regressions (removed machinery, taught boot crashes).

### Changed

- Recipes fixed at the source: NestJS scaffolding/validation no longer call `patchNestJsSwagger()` (boot crash on @nestjs/swagger 11; docs setup is try/catch-guarded), contracts package builds as **CommonJS** with `require` exports, `@Audit` guidance now places the decorator on **controller handlers** with a runtime side-effect proof, env schema warns against secret defaults, the dual-mode mock route sanitizes path segments and is demo-gated, and `design-to-nextjs` requires confirming the shadcn backing library (Radix vs Base UI) before composing components.
- `production-readiness-audit`: every 1–10 score must cite its command/browser/DB evidence (uncited = 0); state lives in `READINESS.md` only.
- `superdev-self-learning`: deliberate, manual lesson capture (no hooks); stack-general lessons are promoted into `hard-rules.md` instead of staying siloed in one project (the failure mode that let the same boot crash ship twice).
- Build order language is dependency **groups** built **sequentially** everywhere (plan format, builders, migration) — no parallel backend+frontend work against a same-step contract.
- All bundled-resource references are plugin-relative; the v1.8.1 project-scoped install contract (installer helper, `--scope project`, tests) is retained and its docs updated to v2.

### Removed (breaking)

- `prd-design-build-orchestrator` skill and its references (execution/audit pipelines, orchestration patterns, embedded agent copies). The artifact formats live on under `superdev-build/references/artifacts-format.md`.
- Agent-extractor installers (`install-core/qa/security/migration-agents.sh`, `extract-agent.py`) and their stale embedded agent copies — `agents/*.md` are the single source and are auto-loaded by the plugin; nothing is copied into target projects.
- The bash hook machinery (`hooks/`): done-gate Stop sentinel + completion ledger, wave-gate, stack-up check, frustration detection, per-dispatch lesson threading. Verification is explicit (`verify-done.mjs`, per-module runtime checks). Existing projects may delete `.claude/.superdev-orchestrating`, `.claude/.superdev-donegate-attempts`, and `COMPLETION_LEDGER.json`.
- "Agent teams" 3-teammate debate sections from skills (the plan-review value is kept as a single-pass three-lens self-review in `frontend-refactoring`). The installer's `--enable-teams` flag remains available as a host setting.

### Migration from v1.x

- Reinstall at project scope: `claude plugin marketplace add boparaiamrit/superdev --scope project` + `claude plugin install superdev@superdev --scope project` (or `bash /path/to/superdev/install-superdev.sh`).
- Prompts that said "use the orchestrator / build the full-stack app" now route to `superdev-build`. Standalone skill invocations are unchanged.
- Projects with copied agents under `.claude/agents/` (from the old installers) can delete the stale copies — the plugin's `agents/` are canonical.
- Replace any `COMPLETION_LEDGER.json` done-checks with `node <plugin>/scripts/verify-done.mjs`.

## v1.8.1 — 2026-07-20

Project-scoped Superdev: installation and activation live in the target repository (Claude `--scope project`, Codex repository marketplace); bundled resources resolve from the plugin root; learning stays project-local; `tests/test_project_scope.py` enforces no global/personal Superdev paths.

## v1.8.0 — 2026-06-20

Production-readiness-audit: scores every module 1–10 across five passes and loops fix → re-audit until every module is 9+. Requires real seed data + an initial owner/admin user, demo-mode OFF, and a multi-tenancy leak test. New agents: module-readiness-rater, tenancy-isolation-tester, seed-data-architect (18 skills / 54 agents).

## v1.7.0 — 2026-06-20

Completion ENFORCED (done-gate) + Laravel/Inertia merge.

## v1.6.0 — 2026-06-04

Laravel backend reworked to PostgreSQL + TimescaleDB + Eloquent API Resources (dropping CockroachDB + spatie/laravel-data); `audit_logs` hypertable; hand-written TS contracts.

## v1.5.0 — 2026-06-04

design-to-laravel (Claude Design → Laravel + Inertia 3 + React 19 monolith), frontend-stack gate (Inertia vs Next.js). 16 skills / 51 agents.

## v1.4.0 — 2026-06-03

Laravel backend option (laravel-enterprise-backend + laravel-bref-deploy), backend-stack selection gate. 15 skills / 50 agents.

## v1.3.1 — 2026-05-26

Earlier release (see git history).
