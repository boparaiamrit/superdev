# Superdev

A Claude Code + Codex plugin bundling **16 skills + 51 specialized role prompts** for full-stack monorepo builds, with a self-improving memory loop, holy-grail design preservation, and atomic frontend refactoring.

## Host support

Superdev is dual-hosted:

- **Codex:** loads the 16 skills through `.codex-plugin/plugin.json`. Use `agents/*.md` as role-prompt references when explicit delegation is useful. Claude hook behavior should be run as explicit verification steps.
- **Claude Code:** loads the original Claude plugin manifest, subagents, and hook events.

See `../../CODEX.md` for the Codex adapter notes.

## What's in this plugin

**Sixteen skills:**

| Skill | Purpose |
|---|---|
| `prd-design-build-orchestrator` | The conductor — multi-agent orchestration across all 16 skills, reads `.claude/memory/superdev-learned/` before every dispatch |
| `design-to-nextjs` | Translate **Claude Design** handoffs into production Next.js (shadcn-everywhere, view-shape contract, dual-mode adapter) |
| `design-preservation` | When source is a **prototype**, copy verbatim into `design-source/`, mirror at `/__design-source/`, pixel-diff every Phase C wave at ≤ 1% drift |
| `frontend-modular-architecture` 🆕 v1.3.0 | Opinionated structure: page ≤ 100 / component ≤ 200 lines, dedicated Zustand stores per module, wizards split per-step, sub-sub-components (drawer/modal/popover) in `parts/<name>/` folders using shadcn Portal primitives |
| `frontend-refactoring` 🆕 v1.3.0 | **Atomic one-module conversion** of a fat existing module — 5 strict phases (plan → review → snapshot → atomic-execute → verify) with hard rollback on any behavior drift. No half-state ever lands. |
| `nestjs-enterprise-backend` | Nest.js + PG17/TimescaleDB + Drizzle + CASL + BullMQ + `@Audit` decorator + view-shape contract |
| `security-review-and-fix` | Six-phase security audit (inventory, static, dynamic, dependency, triage, fix) |
| `prototype-to-saas` | Convert a single-user Next.js prototype with JSON-as-backend into a multi-tenant SaaS. v1.3.0 adds **Phase 4.5** — refactoring runs BEFORE rewiring. |
| `exploratory-qa` | Playwright-driven QA: happy + edge cases, consistency audit, performance probing |
| `systematic-debugging` | 5-phase brutal-debug, refuses fixes without VERIFIED ROOT_CAUSE.md |
| `product-completeness-audit` | "A beautiful UI with hardcoded data is a demo" — distinguishes REAL / MOCKED / HYBRID in production mode |
| `brutal-exhaustive-audit` | Every file / route / flow / data path / edge case — disk-tracked checklists |
| `superdev-self-learning` | The meta-loop — writes `.claude/memory/superdev-learned/` from frustration / verifier signals |
| `laravel-enterprise-backend` 🆕 v1.4.0 · reworked v1.6.0 | **Laravel 13** backend alternative — **PostgreSQL + TimescaleDB** (stock `pgsql`) + DB cache/sessions + SQS, **Eloquent API Resources** presenter + hand-written TS contract, `#[Audit]` → `audit_logs` hypertable, Sanctum + `spatie/laravel-permission`, `BelongsToWorkspace` global-scope tenancy, Title-Case enums, Laravel Boost |
| `laravel-bref-deploy` 🆕 v1.4.0 | **Serverless deploy** of the Laravel backend on AWS Lambda via **Bref 3.x** — web/SQS-worker/console functions, EventBridge scheduler, S3/CloudFront assets, SSM secrets, no VPC; OSS Serverless (`osls`) default |
| `design-to-laravel` 🆕 v1.5.0 | Translate **Claude Design** → **Laravel + Inertia 3 + React 19** monolith (React starter kit: TS, Tailwind 4, shadcn). Typed-props pages via `Inertia::render`, Wayfinder routing, `useForm`, Fortify session + spatie/permission + `#[Authorize]`; reuses design-to-nextjs token-extraction + shadcn; client-only on Bref. Default Laravel frontend |

> 🔀 **Stack choice** — the orchestrator asks **Laravel or Nest.js** at Step A.5b. If Laravel, it then asks the frontend at Step A.5c: **Inertia monolith** (default — `design-to-laravel`, one app, Fortify session) or **decoupled Next.js** (`design-to-nextjs`, Sanctum tokens). Nest.js always pairs with Next.js.

**51 role prompts** bundled with the plugin:

In Claude Code, these are auto-loaded as subagents when the plugin is enabled. In Codex, they remain available as prompt references for explicit delegated or parallel work.

- **12 core build agents:** `prd-analyst`, `design-inventory`, `gap-auditor`, `plan-architect`, `monorepo-bootstrapper`, `contracts-author`, `backend-module-builder`, `laravel-module-builder`, `frontend-module-builder`, `inertia-module-builder` 🆕, `ui-auditor`, `integration-tester`
- **5 security agents:** `security-inventory`, `static-auditor`, `dynamic-auditor`, `dependency-auditor`, `security-fixer`
- **5 migration agents:** `codebase-discoverer`, `schema-reverse-engineer`, `migration-planner`, `backend-extractor`, `frontend-rewirer`
- **4 QA agents:** `qa-environment`, `qa-flow-tester`, `qa-consistency-checker`, `qa-performance-prober`
- **5 debug agents:** `bug-reproducer`, `root-cause-investigator`, `hypothesis-tester`, `fix-applier`, `regression-verifier`
- **6 brutal-audit agents:** `repo-cartographer`, `route-walker`, `flow-walker`, `data-flow-tracer`, `edge-case-prober`, `audit-synthesizer`
- **5 product-completeness agents:** `placeholder-hunter`, `route-completeness-checker`, `wiring-auditor`, `data-flow-real-vs-mock`, `journey-walker`
- **2 design-preservation agents:** `design-source-mirror`, `design-fidelity-auditor`
- **1 self-learning agent:** `learn-from-frustration`
- **2 modular-architecture agents 🆕:** `module-structure-auditor`, `portal-correctness-auditor`
- **4 frontend-refactoring agents 🆕:** `module-conversion-planner`, `module-behavior-snapshotter`, `atomic-module-converter`, `conversion-verifier`

**Hooks:**
- `SubagentStop` on every builder agent runs `<pm> typecheck` automatically (PM auto-detected from lockfile)
- `SubagentStart` on all Playwright-using agents verifies the stack is up before they run
- `UserPromptSubmit` runs `detect-frustration.sh` — conservative scan for "no/stop/wrong/I told you/revert"; on match queues a `learn-from-frustration` dispatch
- `SubagentStop` on `fix-applier|regression-verifier|design-fidelity-auditor|audit-synthesizer` runs `maybe-learn.sh` — captures verifier rejections and `LESSON:` lines into project memory
- 🆕 `SubagentStop` on `frontend-module-builder|frontend-rewirer|atomic-module-converter` scans newly-written .tsx files for >300 lines and emits a `LESSON:` to dispatch `frontend-refactoring` if any are found

## Placeholder convention

This plugin is **workspace-scope agnostic** — nothing about your monorepo is hardcoded. Where docs reference your project, you'll see placeholders; substitute them with your project's actual values:

| Placeholder | Means | Detect from |
|---|---|---|
| `<scope>` | npm scope (e.g. `acme` in `@acme/api`) | Root `package.json` `name` field |
| `<workspace>` | Monorepo root dir / pnpm workspace name | Directory you ran `pnpm init` in |
| `<app>` | Short name for DB / storage-key prefixes (e.g. `acme_dev`) | Lowercase `<workspace>` |
| `<APP_NAME>` | Human-readable brand name shown in UI / API title | Your product name |
| `<feature>` | The feature module being built | Current task |
| `<pm>` | The package manager (`pnpm` / `npm` / `yarn` / `bun`) | Lockfile in monorepo root |

## Package manager support

Hooks **auto-detect** your package manager from the lockfile (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lockb` → bun, otherwise → npm) and run the workspace's typecheck/build script using the right command. You don't have to configure anything.

Skill examples use `pnpm` (the default the monorepo-bootstrapper sets up, because pnpm + Turbo handles workspace-scope filtering best), but if you've already installed in an existing monorepo using a different PM, the hooks adapt automatically. The agent docs include a `<pm>` placeholder — substitute your manager wherever you see it.

| Lockfile detected | Hook runs |
|---|---|
| `pnpm-lock.yaml` | `(cd apps/api && pnpm typecheck)` |
| `yarn.lock` | `(cd apps/api && yarn typecheck)` |
| `bun.lockb` / `bun.lock` | `(cd apps/api && bun run typecheck)` |
| (none of the above) | `(cd apps/api && npm run typecheck)` |

Whether the plugin is installed globally in `~/.claude/plugins/` or privately in a single monorepo, it adapts to that repo's naming and tooling.

## Installation

### Codex — local marketplace

This repo includes a Codex marketplace file:

```text
.agents/plugins/marketplace.json
```

After installing from that local marketplace, invoke the skills directly:

```text
Use $security-review-and-fix to audit this codebase.
Use $prototype-to-saas to productionize this prototype.
Use $prd-design-build-orchestrator with docs/PRD.md and design/.
```

### Claude Code

### Option 1 — install via marketplace (recommended)

```bash
/plugin marketplace add boparaiamrit/superdev
/plugin install superdev
```

### Option 2 — local development

```bash
git clone https://github.com/boparaiamrit/superdev ~/superdev
claude --plugin-dir ~/superdev/plugins/superdev
```

### Option 3 — install from zip

```bash
bash install-superdev.sh
```

## Quick start

After installation, in any Claude Code session:

```
I have a PRD at docs/PRD.md and a design at design/index.html.
Build the full-stack app.
```

The main session reads the orchestrator skill, dispatches subagents through the four phases (audit → bootstrap → execute → integrate), and produces a shipping monorepo.

For other entry points:

| Situation | What to say |
|---|---|
| Greenfield PRD + design | "Build the full-stack app from PRD.md and design/" |
| Existing Next.js prototype with JSON fixtures | "Help me productionize this Next.js prototype" |
| Standalone security audit | "Run a security audit on this codebase" |
| Standalone QA pass | "Run a production-readiness QA pass" |
| Frontend-only from design | "Convert this Claude Design output to a Next.js codebase" |
| Backend-only build (Nest.js) | "Build a Nest.js backend with these patterns: ..." |
| Backend-only build (Laravel) | "Build a Laravel backend with these patterns: ..." (PostgreSQL + TimescaleDB + SQS, deploy via Bref) |

## Agent teams (optional)

Several phases benefit from **agent teams** when stakes are high. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`:

- **Gap audit** (orchestrator Phase A.3) — 3-teammate adversarial review of PRD-vs-design gaps
- **Security audit** (Phase D.2) — 3-teammate team where auditors challenge each other's findings
- **QA report synthesis** (Phase D.3.6) — 3-teammate severity debate (harshest-critic vs pragmatist vs shipping-advocate)
- **Hard performance investigation** — on-demand competing-hypotheses team
- **Per-feature pair-programming** (Phase C.2) — backend↔frontend teammates that can negotiate contracts live

See each skill's "Agent teams (optional)" section for the exact invocation prompts.

## Architectural commitments enforced across all skills

1. **Monorepo** — `apps/web` (Next.js) + `apps/api` (Nest.js) + `packages/contracts` (shared Zod schemas)
2. **View-shape contract** — backend returns view-ready data; frontend renders WITHOUT `?.` or `??` on contract fields
3. **Title Case enums** — DB = wire = UI label, no conversion code anywhere
4. **shadcn/ui everywhere** — every visual primitive from `@/components/ui/*`, sidebar uses shadcn block, NO competing UI libraries
5. **Docker for ALL infrastructure** — Postgres+Timescale, Redis, etc.; nothing local
6. **CASL authorization + `@Audit` decorator** — every endpoint protected, every mutation audited
7. **Dual-mode adapter** — `NEXT_PUBLIC_API_MODE=demo` reads JSON fixtures; `production` hits backend

> 🐘 **Laravel backend variant (v1.4.0, reworked v1.6.0)** preserves all seven commitments with Laravel mechanisms: hand-written TS contract in `packages/contracts` kept in lockstep with **Eloquent API Resources** (1); API Resource presenters (2); PHP Title-Case enums (3); `spatie/laravel-permission` + Policies + `#[Audit]` → `audit_logs` hypertable (6). It diverges where the serverless target requires it: managed **PostgreSQL + TimescaleDB** + database cache/sessions + SQS instead of Docker Postgres/Redis (5), and Bref/AWS Lambda for production instead of Docker. See `laravel-enterprise-backend` / `laravel-bref-deploy`.

## Tech stack baked in

- **Frontend:** Next.js 14+ App Router, Tailwind, TanStack Query/Table, Zustand, Zod, RHF, shadcn/ui
- **Backend (default):** Nest.js 10+, PG17 + TimescaleDB, Drizzle ORM, Redis 7+, BullMQ, CASL, nestjs-zod, JWT+argon2, Pino, Prometheus
- **Backend (alternative) 🆕 v1.4.0 · reworked v1.6.0:** Laravel 13 (PHP 8.3+), managed **PostgreSQL + TimescaleDB** (stock `pgsql`, self-managed), database cache/sessions, SQS queues, Eloquent + **API Resources** (presenter) + hand-written TS contracts, Sanctum, `spatie/laravel-permission`, `#[Audit]` → `audit_logs` hypertable, Laravel Boost — deployed serverless on AWS Lambda via **Bref 3.x** (`laravel-enterprise-backend` + `laravel-bref-deploy`)
- **Tooling:** pnpm workspaces, Turborepo
- **QA:** Playwright (via MCP server scoped to QA agents only)

## Why a plugin instead of six separate skills

- One install instead of six
- Agents auto-loaded; no `install-*-agents.sh` scripts to run
- Plugin namespacing prevents agent-name collisions with other installed plugins
- Hooks ship with the plugin (no manual `settings.json` editing)
- Versioned releases with `version` field
- Marketplaceable

## Development

To modify the plugin:

```bash
# Make changes to skills/, agents/, or hooks/
# Then in your Claude Code session:
/reload-plugins
```

To validate before committing:

```bash
# Each agent file should start with frontmatter
for f in agents/*.md; do
  head -1 "$f" | grep -q '^---$' || echo "MISSING FRONTMATTER: $f"
done

# Plugin manifest is valid JSON
jq empty .claude-plugin/plugin.json
```

## License

MIT — see [LICENSE](../../LICENSE).
