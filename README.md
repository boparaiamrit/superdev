<div align="center">

# Superdev — Claude Code Plugin

**6 production-grade skills + 24 specialized subagents for full-stack monorepo builds**

*Workspace-scope agnostic · package-manager agnostic · marketplaceable*

<br>

[![Get Started](https://img.shields.io/badge/Get_Started-blue?style=for-the-badge)](#-quick-start)
[![Stars](https://img.shields.io/github/stars/boparaiamrit/superdev?style=for-the-badge&color=gold)](https://github.com/boparaiamrit/superdev)
[![License](https://img.shields.io/github/license/boparaiamrit/superdev?style=for-the-badge)](https://github.com/boparaiamrit/superdev/blob/main/LICENSE)

[![GitHub](https://img.shields.io/badge/GitHub-boparaiamrit-181717?style=flat-square&logo=github)](https://github.com/boparaiamrit)
[![X/Twitter](https://img.shields.io/badge/X-@boparaiamrit-000000?style=flat-square&logo=x)](https://x.com/boparaiamrit)
[![Sponsor](https://img.shields.io/badge/Sponsor-❤️-ea4aaa?style=flat-square)](https://github.com/sponsors/boparaiamrit)

</div>

---

## 🧬 What's Inside

| # | Skill | What It Does |
|:---:|:---|:---|
| 1 | 🧠 **prd-design-build-orchestrator** | Multi-agent orchestration: PRD audit → execution plan → parallel feature builds → integration → security → QA. The conductor that drives a full PRD-to-shipping-app pipeline. |
| 2 | 🎨 **design-to-nextjs** | Convert Claude Design handoffs into production Next.js codebases. Shadcn-everywhere enforcement, view-shape contract, dual-mode adapter (demo fixtures vs real API). |
| 3 | 🏛️ **nestjs-enterprise-backend** | Nest.js + PostgreSQL 17 + TimescaleDB + Drizzle ORM + CASL + BullMQ + Redis. Includes the `@Audit` decorator, view-shape contract, and CASL ability enforcement. |
| 4 | 🔒 **security-review-and-fix** | Six-phase security audit: inventory → static → dynamic → dependency → triage → fix. Optional 3-teammate adversarial review of findings. |
| 5 | 🔄 **prototype-to-saas** | Convert a single-user Next.js prototype with JSON-as-backend into a multi-tenant SaaS. Surgical feature-by-feature rewiring without destroying the UI. |
| 6 | 🧪 **exploratory-qa** | Senior-engineer-style QA: Playwright-driven happy paths + edge cases, cross-cutting consistency audit, performance probing with N+1 detection. |

---

## 💎 The Gem: 24 Subagents + Adversarial Teams + PM-Agnostic Runtime

**Superdev** ships every full-stack workflow as a fleet of **24 specialized subagents** that the orchestrator dispatches in parallel waves — each agent gets a fresh context window, focuses on one feature module or one audit concern, and writes its findings to disk before returning.

```
 ╔══════════════════════════════════════════════════════════════════════╗
 ║              ORCHESTRATOR  ·  4 phases  ·  6 skills                  ║
 ║         A) Audit    B) Bootstrap    C) Execute    D) Integrate       ║
 ╚════════════════════════════════╦═════════════════════════════════════╝
                                  ║
                       Subagent waves dispatching
       ┌──────────────┬───────────┴───────────┬──────────────┐
       │              │                       │              │
 ┌─────┴────────┐ ┌───┴───────────┐ ┌─────────┴─────┐ ┌──────┴─────────┐
 │ 10 build     │ │  5 security   │ │  5 migration  │ │  4 QA          │
 │ agents       │ │  agents       │ │  agents       │ │  agents        │
 │              │ │               │ │               │ │                │
 │ prd-analyst  │ │ security-inv  │ │ codebase-disc │ │ qa-environment │
 │ design-inv   │ │ static-audit  │ │ schema-revrse │ │ qa-flow-tester │
 │ gap-auditor  │ │ dynamic-audit │ │ migration-plan│ │ qa-consist…    │
 │ plan-arch    │ │ dep-auditor   │ │ backend-extr  │ │ qa-perf-probe  │
 │ monorepo-boot│ │ security-fix  │ │ frontend-rew  │ │                │
 │ contracts-a  │ │               │ │               │ │                │
 │ backend-mod  │ │               │ │               │ │                │
 │ frontend-mod │ │               │ │               │ │                │
 │ ui-auditor   │ │               │ │               │ │                │
 │ integ-tester │ │               │ │               │ │                │
 └──────────────┘ └───────────────┘ └───────────────┘ └────────────────┘
        │                │                  │                  │
        ▼                ▼                  ▼                  ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │       Markdown artifacts on disk (audited, resumable, reviewable)    │
 │  EXECUTION_PLAN.md  SECURITY_REPORT.md  MIGRATION_PLAN.md  QA_*.md   │
 └──────────────────────────────────────────────────────────────────────┘
```

**What makes it different:**

- ✅ **Workspace-scope agnostic** — no hardcoded `@scope/` anywhere; uses `<scope>` placeholders + path-based pnpm filters
- ✅ **Package-manager agnostic** — hooks auto-detect pnpm / npm / yarn / bun from lockfile
- ✅ **Install anywhere** — works installed globally in `~/.claude/plugins/` or privately checked into a single monorepo
- ✅ **24 subagents auto-loaded** — no install scripts, no manual `agents/` copying
- ✅ **2 runtime hooks** — `SubagentStop` auto-typecheck after every builder; `SubagentStart` verifies stack health before QA agents run
- ✅ **Adversarial teams (optional)** — 3-teammate reviews for security, QA synthesis, and gap audits when stakes are high
- ✅ **Memory-injection ready** — agents that use `memory: project` write their findings to the project's `.claude/` memory so subsequent sessions inherit context
- ✅ **Resumable** — every phase produces a markdown artifact; pick up where you stopped

---

## 🚀 Quick Start

### Install

**Step 1 — Add the marketplace:**
```shell
/plugin marketplace add boparaiamrit/superdev
```

**Step 2 — Install the plugin:**
```shell
/plugin install superdev@superdev
```

> 💡 Or install from the bundled zip:
> ```bash
> bash install-superdev.sh
> ```
> The installer extracts to `~/.claude/plugins/superdev/` and registers the path in `~/.claude/settings.json` so every Claude Code session loads it.

> 🧪 Or test locally during development:
> ```bash
> claude --plugin-dir ~/superdev/plugins/superdev
> ```

### Run

In any Claude Code session, just say what you want:

| 🎯 Situation | 💬 What to say |
|:---|:---|
| Greenfield PRD + design | *"Build the full-stack app from `docs/PRD.md` and `design/`"* |
| Existing Next.js prototype | *"Help me productionize this Next.js prototype"* |
| Standalone security pass | *"Run a security audit on this codebase"* |
| Standalone QA pass | *"Run a production-readiness QA pass"* |
| Frontend only | *"Convert this Claude Design output to a Next.js codebase"* |
| Backend only | *"Build a Nest.js backend with these patterns: …"* |

The right skill activates, the right subagents dispatch — no slash commands to memorize.

---

## 🛠️ Package Manager Support

**Hooks auto-detect your package manager** from the lockfile in your monorepo root:

| 📦 Lockfile found | 🏃 Hook runs |
|:---|:---|
| `pnpm-lock.yaml` | `(cd apps/api && pnpm typecheck)` |
| `yarn.lock` | `(cd apps/api && yarn typecheck)` |
| `bun.lockb` / `bun.lock` | `(cd apps/api && bun run typecheck)` |
| *(none of the above)* | `(cd apps/api && npm run typecheck)` |

> ✅ **No configuration needed.** Drop the plugin into a pnpm, npm, yarn, or bun monorepo and the hooks just work.

The `monorepo-bootstrapper` agent defaults to **pnpm + Turborepo** (it's the cleanest fit for workspace-scope filtering), but it honors your existing setup if there's already a lockfile — and the runtime hooks adapt to whatever PM your repo actually uses.

---

## 🧩 Placeholder Convention

Superdev is **workspace-scope-agnostic** by design. Where docs reference your project, you'll see placeholders — substitute them with your project's actual values:

| 🏷️ Placeholder | 📖 Means | 🔍 Detect from |
|:---|:---|:---|
| `<scope>` | npm scope (e.g. `acme` in `@acme/api`) | Root `package.json` `name` field |
| `<workspace>` | Monorepo root dir name | Directory you ran `<pm> init` in |
| `<app>` | Short name for DB / storage-key prefixes | Lowercase `<workspace>` |
| `<APP_NAME>` | Human-readable brand shown in UI / API title | Your product name |
| `<feature>` | The feature module being built | Current task |
| `<pm>` | Package manager (`pnpm` / `npm` / `yarn` / `bun`) | Lockfile in monorepo root |

Nothing in the plugin is hardcoded to a specific monorepo. **Install once, use everywhere.**

---

## 🏗️ How It Works — The 4-Phase Pipeline

```
┌───────────────┐    ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   A. AUDIT    │───▶│ B. BOOTSTRAP  │───▶│  C. EXECUTE   │───▶│ D. INTEGRATE  │
│  PRD digest,  │    │  Monorepo +   │    │  Per-feature  │    │  Cross-cutting│
│  design       │    │  contracts    │    │  build waves  │    │  tests, sec   │
│  inventory,   │    │  scaffold,    │    │  (be+fe in    │    │  audit, QA,   │
│  gap audit,   │    │  Docker up,   │    │  parallel),   │    │  perf probe   │
│  plan         │    │  health check │    │  ui-audit     │    │               │
└───────────────┘    └───────────────┘    └───────────────┘    └───────────────┘
```

### 📋 Phase A — Audit

- **`prd-analyst`** reads PRD → produces `PRD_DIGEST.md` (entities, features, NFRs)
- **`design-inventory`** reads design handoff → produces `DESIGN_DIGEST.md` (screens, components, implicit shapes)
- **`gap-auditor`** diffs the two → produces `AUDIT.md` (missing-from-design / missing-from-prd / type-mismatch / naming-drift / scope-creep)
- **`plan-architect`** synthesizes everything → `EXECUTION_PLAN.md` (module split, wave structure, CASL abilities, queues, crons)

> 🤝 **Optional adversarial team:** With `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, gap-auditor runs as a 3-teammate review (harshest critic vs pragmatist vs shipping-advocate).

### 🏗️ Phase B — Bootstrap

- **`monorepo-bootstrapper`** scaffolds the pnpm workspace + Turbo + apps/api + apps/web + packages/* per the bundled scaffolding references. Uses your existing PM if a lockfile is already present.
- **`contracts-author`** authors every Zod schema in `packages/contracts/src/*.ts` for every feature at once. Enforces the view-shape contract (no `.optional()` on data fields, Title Case enums).

### 🚀 Phase C — Execute (Parallel Waves)

For each feature in the execution plan, dispatched in parallel:

- **`backend-module-builder`** — Nest.js controller, service, presenter, repository, DTOs, Drizzle schema, tests
- **`frontend-module-builder`** — Next.js api fetchers, TanStack Query hooks, components, fixtures, page route
- **`ui-auditor`** — verifies shadcn-everywhere compliance after each wave

### 🔍 Phase D — Integrate

- **`integration-tester`** — cross-workspace isolation, CASL enforcement, `@Audit` coverage, view-shape compliance, dual-mode boot
- **`security-inventory` → `static-auditor` → `dynamic-auditor` → `dependency-auditor` → `security-fixer`** — 5-stage security pipeline
- **`qa-environment` → `qa-flow-tester` (parallel per feature) → `qa-consistency-checker` → `qa-performance-prober`** — Playwright-driven exploratory QA

---

## 🧠 Architectural Commitments (Enforced Across All Skills)

| # | Commitment | Why it matters |
|:---:|:---|:---|
| 1 | 🏛️ **Monorepo** — `apps/web` + `apps/api` + `packages/contracts` | Shared Zod schemas eliminate frontend/backend drift |
| 2 | 📐 **View-shape contract** — backend returns view-ready data | Frontend renders WITHOUT `?.` or `??` on contract fields — the API does the work, not the UI |
| 3 | 🏷️ **Title Case enums** — DB = wire = UI label | No conversion code anywhere; `company.status` renders directly |
| 4 | 🎨 **shadcn/ui everywhere** — every visual primitive from `@/components/ui/*` | `ui-auditor` enforces this — NO Radix-direct, MUI, Chakra, etc. |
| 5 | 🐳 **Docker for ALL infrastructure** — Postgres + Timescale, Redis, etc. | Container names prefixed with `<workspace>_*` so multiple monorepos run side-by-side |
| 6 | 🔐 **CASL + `@Audit`** — every endpoint protected, every mutation audited | Tenant isolation + compliance baked into the framework |
| 7 | 🔀 **Dual-mode adapter** — `NEXT_PUBLIC_API_MODE=demo` vs `production` | Frontend ships with JSON fixtures for design review; flips to real API at deploy |

---

## 🤝 Agent Teams (Optional, ~3× tokens)

Several phases benefit from **adversarial 3-teammate reviews** when stakes are high. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

| | Phase | Team | What they do |
|:---:|:---|:---|:---|
| 🔎 | Gap audit (Phase A.3) | 3 critics | Adversarial review of PRD-vs-design gaps |
| 🔒 | Security audit (Phase D.2) | 3 auditors | Challenge each other's findings; reduce false positives |
| 🧪 | QA report synthesis (Phase D.3.6) | 3 reviewers | Severity debate — harshest-critic vs pragmatist vs shipping-advocate |
| ⚡ | Performance investigation | 3 hypothesists | Competing-hypotheses for ambiguous slowdowns |
| 🔧 | Per-feature pair-programming (Phase C.2) | be ↔ fe | Backend + frontend teammates negotiate contracts live |

Enable with the installer:
```bash
bash install-superdev.sh --enable-teams
```

---

## 📦 Tech Stack Baked In

| Layer | Choices |
|:---|:---|
| 🎨 **Frontend** | Next.js 14+ App Router · Tailwind · TanStack Query/Table · Zustand · Zod · React Hook Form · shadcn/ui |
| 🏛️ **Backend** | Nest.js 10+ · PostgreSQL 17 + TimescaleDB · Drizzle ORM · Redis 7+ · BullMQ · CASL · nestjs-zod · JWT + argon2 · Pino · Prometheus |
| 🛠️ **Tooling** | pnpm workspaces (default) · Turborepo · Docker Compose |
| 🧪 **QA** | Playwright (via MCP server scoped to QA agents only) |
| 🔁 **PM compat** | pnpm / npm / yarn / bun — hooks auto-detect |

---

## 🪝 Runtime Enforcement Hooks

Event-driven enforcement that catches regressions the moment they happen:

| | Hook | Event | What it does |
|:---:|:---|:---|:---|
| ✅ | **Auto-typecheck (backend)** | `SubagentStop` · backend-module-builder, backend-extractor | Runs `<pm> typecheck` in `apps/api/` and pipes last 20 lines to the orchestrator |
| ✅ | **Auto-typecheck (frontend)** | `SubagentStop` · frontend-module-builder, frontend-rewirer | Runs `<pm> typecheck` in `apps/web/` and pipes last 20 lines |
| ✅ | **Auto-build (contracts)** | `SubagentStop` · contracts-author | Runs `<pm> build` in `packages/contracts/` to catch Zod schema errors early |
| 🚦 | **Stack-up check** | `SubagentStart` · qa-flow-tester, qa-performance-prober | Hits `/v1/readiness` + Next.js root before QA agents waste time on a dead stack |

All hooks **auto-detect your package manager** from the lockfile — no configuration required.

---

## 🗂️ Repository Structure

```
superdev/
├── 📁 .claude-plugin/
│   └── marketplace.json                     Marketplace manifest
├── 📁 plugins/superdev/
│   ├── 📁 .claude-plugin/
│   │   └── plugin.json                      Plugin manifest
│   ├── 📁 agents/                           24 specialized subagents
│   │   ├── prd-analyst.md                   ┐
│   │   ├── design-inventory.md              │
│   │   ├── gap-auditor.md                   │  10 core
│   │   ├── plan-architect.md                │  build agents
│   │   ├── monorepo-bootstrapper.md         │
│   │   ├── contracts-author.md              │
│   │   ├── backend-module-builder.md        │
│   │   ├── frontend-module-builder.md       │
│   │   ├── ui-auditor.md                    │
│   │   ├── integration-tester.md            ┘
│   │   ├── security-inventory.md            ┐
│   │   ├── static-auditor.md                │
│   │   ├── dynamic-auditor.md               │  5 security
│   │   ├── dependency-auditor.md            │  agents
│   │   ├── security-fixer.md                ┘
│   │   ├── codebase-discoverer.md           ┐
│   │   ├── schema-reverse-engineer.md       │
│   │   ├── migration-planner.md             │  5 migration
│   │   ├── backend-extractor.md             │  agents
│   │   ├── frontend-rewirer.md              ┘
│   │   ├── qa-environment.md                ┐
│   │   ├── qa-flow-tester.md                │  4 QA
│   │   ├── qa-consistency-checker.md        │  agents
│   │   └── qa-performance-prober.md         ┘
│   ├── 📁 skills/                           6 skills with references/
│   │   ├── prd-design-build-orchestrator/   The conductor
│   │   ├── design-to-nextjs/                Frontend skill
│   │   ├── nestjs-enterprise-backend/       Backend skill
│   │   ├── security-review-and-fix/         Security skill
│   │   ├── prototype-to-saas/               Migration skill
│   │   └── exploratory-qa/                  QA skill
│   ├── 📁 hooks/
│   │   └── hooks.json                       PM-agnostic runtime hooks
│   └── README.md                            Plugin-level docs
├── 📦 superdev.zip                          Bundled plugin for the installer
├── 🛠️ install-superdev.sh                   Shell installer (bash, ~20KB)
├── 📖 INSTALL.md                            Installer docs
├── 📖 README.md                             This file
├── 📄 LICENSE                               MIT
└── .gitignore
```

---

## 🧑‍🔧 Why a Plugin Instead of Six Separate Skills

| ✅ Benefit | 📖 Why it matters |
|:---|:---|
| **One install** | Six skills + 24 agents + hooks in a single `/plugin install` |
| **Agents auto-loaded** | No `install-*-agents.sh` scripts; nothing manual |
| **Plugin namespacing** | Agent-name collisions with other installed plugins are impossible |
| **Hooks ship with the plugin** | No `settings.json` editing — hooks auto-load when the plugin loads |
| **Versioned releases** | `version` field in `plugin.json`; install pinned versions |
| **Marketplaceable** | Distributable via `/plugin marketplace add boparaiamrit/superdev` |

---

## ⚙️ Requirements

| | Requirement | Notes |
|:---:|:---|:---|
| 🤖 | **Claude Code** | v2.1.32+ recommended. Agent Teams optional (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) for adversarial reviews. |
| 📦 | **Node.js + a package manager** | pnpm (default) / npm / yarn / bun — hooks auto-detect |
| 🐳 | **Docker** | For Postgres + Timescale + Redis. Container names are workspace-prefixed. |
| 🐍 | **Python 3** | Used by the installer (`install-superdev.sh`) for safe JSON manipulation of `settings.json` |

---

## 🐛 Troubleshooting

| ❌ Symptom | ✅ Fix |
|:---|:---|
| Hook says `pnpm: command not found` | Hook is detecting `pnpm-lock.yaml`. If you actually use a different PM, delete the stale lockfile or replace it with your real one. |
| Stack-up hook fails before QA agents | Boot your stack first: `<pm> dev:infra && <pm> dev`. Hook is just a friendly precheck. |
| `ui-auditor` flags Radix-direct imports | The whole skill enforces shadcn-everywhere. Use `@/components/ui/*` instead. |
| Agents reference `@<scope>/contracts` | Substitute `<scope>` with your monorepo's actual npm scope (from root `package.json` `name`). |
| `monorepo-bootstrapper` insists on pnpm | It defaults to pnpm but honors existing lockfiles. Run it in an empty dir for full pnpm scaffold, or in an existing monorepo and it adapts. |

---

## 🤝 Contributing

Contributions welcome! Open issues or PRs at [github.com/boparaiamrit/superdev](https://github.com/boparaiamrit/superdev).

**Areas for contribution:**
- Additional skills (e.g. mobile, GraphQL backend, monolith variant)
- More subagents for specialized workflows
- Additional package manager edge cases in the hook detector
- Reference docs for non-Drizzle ORMs
- Alternative UI library variants (e.g. Mantine-everywhere instead of shadcn-everywhere)

---

## 📄 License

[MIT](LICENSE)

---

## 👤 Author

**Amritpal Singh Boparai** — [@boparaiamrit](https://github.com/boparaiamrit)

Built with [Claude Code](https://claude.com/claude-code) · Companion plugin to [build-second-brain](https://github.com/boparaiamrit/build-second-brain)

---

<p align="center">
  <sub>Made with intensity in India 🇮🇳</sub>
</p>
