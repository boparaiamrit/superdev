<div align="center">

# Superdev — Claude Code + Codex Plugin

**13 production-grade skills + 49 specialized role prompts for full-stack monorepo builds**

*Workspace-scope agnostic · package-manager agnostic · self-improving · marketplaceable*

<br>

[![Get Started](https://img.shields.io/badge/Get_Started-blue?style=for-the-badge)](#-quick-start)
[![Stars](https://img.shields.io/github/stars/boparaiamrit/superdev?style=for-the-badge&color=gold)](https://github.com/boparaiamrit/superdev)
[![License](https://img.shields.io/github/license/boparaiamrit/superdev?style=for-the-badge)](https://github.com/boparaiamrit/superdev/blob/main/LICENSE)

[![GitHub](https://img.shields.io/badge/GitHub-boparaiamrit-181717?style=flat-square&logo=github)](https://github.com/boparaiamrit)
[![X/Twitter](https://img.shields.io/badge/X-@boparaiamrit-000000?style=flat-square&logo=x)](https://x.com/boparaiamrit)
[![Sponsor](https://img.shields.io/badge/Sponsor-❤️-ea4aaa?style=flat-square)](https://github.com/sponsors/boparaiamrit)

</div>

---

## Codex Support

Superdev now includes a Codex manifest at `plugins/superdev/.codex-plugin/plugin.json` and a repo-local marketplace at `.agents/plugins/marketplace.json`.

In Codex, the 13 Superdev skills load natively. The Claude Code subagent files and hook events are preserved for Claude users; Codex treats the `agents/*.md` files as role-prompt references and runs hook-equivalent checks explicitly from the skills. See [CODEX.md](CODEX.md) for the host adapter notes.

## 🧬 What's Inside — 13 Skills

| # | Skill | What It Does |
|:---:|:---|:---|
| 1 | 🧠 **prd-design-build-orchestrator** | Multi-agent orchestration. The conductor — coordinates all 11 skills, reads `.claude/memory/superdev-learned/` before every dispatch, threads project lessons into agent prompts. |
| 2 | 🎨 **design-to-nextjs** | Translate **Claude Design** handoffs into production Next.js (shadcn-everywhere, view-shape contract, dual-mode adapter). |
| 3 | 🖼️ **design-preservation** 🆕 | When source is a **prototype** (HTML/Figma/existing app), copy verbatim into `apps/web/src/design-source/`, mirror at `/__design-source/`, pixel-diff every Phase C wave at ≤ 1% drift via `design-fidelity-auditor`. The Holy Grail rule: no restyling. |
| 4 | 🏛️ **nestjs-enterprise-backend** | Nest.js + PostgreSQL 17 + TimescaleDB + Drizzle + CASL + BullMQ + Redis. `@Audit` decorator, view-shape contract, CASL ability enforcement. |
| 5 | 🔒 **security-review-and-fix** | Six-phase security audit: inventory → static → dynamic → dependency → triage → fix. Optional 3-teammate adversarial review. |
| 6 | 🔄 **prototype-to-saas** | Convert a single-user Next.js prototype with JSON-as-backend into a multi-tenant SaaS. Surgical feature-by-feature rewiring without destroying the UI. |
| 7 | 🧪 **exploratory-qa** | Senior-engineer-style QA: Playwright-driven happy paths + edge cases, consistency audit, perf probing with N+1 detection. |
| 8 | 🪲 **systematic-debugging** 🆕 | 5-phase brutal-debug pipeline (reproduce → root-cause → hypothesis-test → fix → regression-verify). Refuses to apply fixes without a `VERIFIED:true` ROOT_CAUSE.md. Optional 3-teammate competing-hypotheses team. |
| 9 | ✅ **product-completeness-audit** 🆕 | "A beautiful UI with hardcoded data is a demo, not a product." 5 agents detect placeholders, stub handlers, mocked data, and HYBRID screens (real data + hardcoded fields). Runs in production mode against real backend. |
| 10 | 🗡️ **brutal-exhaustive-audit** 🆕 | Every file, every route, every flow, every data path, every edge case — no shortcuts, mandatory checklists tracked on disk. The final gate before "ship". 6 agents + optional severity-debate team. |
| 11 | 🧠 **superdev-self-learning** | The meta-loop. `UserPromptSubmit` hook detects frustration; `SubagentStop` captures verifier failures; both dispatch `learn-from-frustration` to write a structured feedback memory entry. The orchestrator reads these before every future dispatch. The system gets smarter every session. |
| 12 | 🧱 **frontend-modular-architecture** 🆕 v1.3.0 | The structure-enforcer that prevents AI-frontend god-files. Page ≤ 100 lines. Component ≤ 200 lines. Dedicated **Zustand** stores per module (entity / UI / wizard). Wizards split per-step under `create-wizard/`. Drawers/modals/popovers in own folders under `parts/<name>/` using shadcn **Portal** primitives (Sheet / Dialog / Popover / DropdownMenu). Audited by `module-structure-auditor` + `portal-correctness-auditor` at every wave gate. |
| 13 | 🔨 **frontend-refactoring** 🆕 v1.3.0 | **Atomic one-module conversion** of an existing fat module into the canonical layout. Five strict phases: deep plan (every file enumerated) → review gate → behavior baseline (Playwright) → atomic-execute (one commit on feature branch) → zero-drift verify. **Any behavior change = full rollback.** No half-converted state ever lands. |


---

## 💎 The Gem: 43 Subagents + Self-Improving Memory + Adversarial Teams

**Superdev** ships every full-stack workflow as a fleet of **43 specialized subagents** that the orchestrator dispatches in parallel waves — each agent gets a fresh context window, focuses on one feature module or one audit concern, and writes its findings to disk before returning. The orchestrator reads `.claude/memory/superdev-learned/` BEFORE every dispatch and threads relevant lessons into agent prompts, so the system learns from every past failure and stops repeating mistakes.

```
 ╔══════════════════════════════════════════════════════════════════════╗
 ║          ORCHESTRATOR  ·  4 phases  ·  11 skills  ·  43 agents       ║
 ║      A) Audit  B) Bootstrap  C) Execute  D) Integrate + Audits       ║
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
- ✅ **43 subagents auto-loaded** — no install scripts, no manual `agents/` copying
- ✅ **6 runtime hooks** — auto-typecheck after every builder, stack-health check before Playwright agents, frustration-detection on every user prompt, lesson-capture after every verifier
- ✅ **Self-improving** — orchestrator reads `.claude/memory/superdev-learned/` before every dispatch; `learn-from-frustration` writes new lessons from user corrections / code reverts / verifier rejections / design drift
- ✅ **Adversarial teams (optional)** — 3-teammate reviews on 9+ phases (security, QA, gap, severity, drift, completeness, competing-hypotheses) when stakes are high
- ✅ **Resumable** — every phase produces a markdown artifact; pick up where you stopped

---

## 🚀 Quick Start

### Install

**Codex local marketplace:**
```shell
# Use this repository's marketplace file:
# .agents/plugins/marketplace.json
```

Then invoke the skills directly in Codex, for example:
```text
Use $security-review-and-fix to audit this codebase.
Use $prototype-to-saas to productionize this prototype.
Use $prd-design-build-orchestrator with docs/PRD.md and design/.
```

**Claude Code marketplace:**

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

In any Claude Code session, just say what you want — **the right skill activates standalone**, no need to drive the whole orchestrator pipeline.

#### Use a single skill (no orchestrator overhead)

| 🎯 Want only… | 💬 Say… | 🎬 What happens |
|:---|:---|:---|
| Security audit | *"Run a security audit on this codebase"* | `security-review-and-fix` activates → dispatches its 5 agents → produces `SECURITY_REPORT.md`. No orchestrator. |
| QA pass | *"Run a production-readiness QA pass"* | `exploratory-qa` activates → its 4 agents run Playwright flows + perf probes |
| Debug a bug | *"Help me debug this test failure: …"* | `systematic-debugging` activates → reproduce → root-cause → fix → regression-verify |
| Brutal final audit | *"Audit this brutally before we ship"* | `brutal-exhaustive-audit` activates → all 6 phases on disk-tracked checklists |
| Demo-vs-product check | *"Is this actually wired up or just looks done?"* | `product-completeness-audit` activates → 5 agents detect placeholder/mock/HYBRID |
| Preserve prototype UI | *"Migrate this prototype to a SaaS but DO NOT change the UI"* | `design-preservation` + `prototype-to-saas` activate together → byte-for-byte mirror + frontend-rewirer with fidelity gate |
| Convert design to Next.js | *"Convert this Claude Design output to a Next.js codebase"* | `design-to-nextjs` activates → shadcn translation, view-shape contract |
| Build backend only | *"Build a Nest.js backend with these patterns: …"* | `nestjs-enterprise-backend` activates → modules with CASL + @Audit + Drizzle |

#### Use the orchestrator (full pipeline)

| 🎯 Situation | 💬 What to say |
|:---|:---|
| Greenfield PRD + Claude Design | *"Build the full-stack app from `docs/PRD.md` and `design/`"* |
| Greenfield PRD + prototype | *"Build the full-stack app — PRD at `docs/PRD.md`, preserve the prototype in `design/`"* |
| Existing Next.js prototype | *"Help me productionize this Next.js prototype — don't change the UI"* |

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

## 🖼️ Design-Preservation — the Holy Grail Rule

When you hand superdev a **prototype** (your own HTML, a Figma export, an existing app's frontend), the `design-preservation` skill treats it as sacred:

```
THE ORIGINAL DESIGN IS A HOLY GRAIL.
WE DO NOT IMPROVE IT, RESTYLE IT, OR REINTERPRET IT.
WE COPY VERBATIM, RENDER AS A MIRROR, AND ONLY THEN WIRE DATA.
Pixel drift > 1% in any region against the source = build fails.
```

How it works:

1. 🗄️ **Phase 0a — Verbatim copy.** `design-source-mirror` copies every HTML / CSS / JS / image / font byte-for-byte into `apps/web/src/design-source/`. Verified with `diff -r`.
2. 🪞 **Phase 0b — Mirror route.** A dev-only `/__design-source/[...path]` route serves the copied files. Source becomes browseable side-by-side with the built app.
3. 📐 **Phase 0c — Baseline capture.** `design-fidelity-auditor` screenshots every page at desktop / tablet / mobile → `design-baseline/`.
4. 🚦 **Phase C wave gates.** After every frontend agent finishes, `design-fidelity-auditor` re-screenshots and pixel-diffs. Drift > 1% on any region → wave fails, agent re-dispatches with the diff.

When NOT to use it:

- ❌ Claude Design output (those are *blueprints meant to be translated* into shadcn — preserving them defeats the whole `design-to-nextjs` skill)
- ❌ Mood-boards or screenshots without HTML/CSS (nothing to preserve verbatim)

The orchestrator auto-routes: prototype → preservation, Claude Design → translation. You don't have to remember the difference.

## 🧠 Self-Learning Loop — the Meta-Skill

Every time the system fails *and you correct it*, it learns. Permanently. For this project.

```
   User dispatches superdev
        │
        ▼
   Orchestrator reads .claude/memory/superdev-learned/  ← ALL past lessons
        │
        ▼
   Threads relevant lessons into agent prompts
        │
        ▼
   Agents do work informed by past mistakes
        │
        ▼
   ⚠️ Something goes wrong? (you said "no/stop/wrong",
      you reverted Claude's code, regression-verifier
      REJECTed, design-fidelity-auditor flagged > 1% drift,
      product-completeness-audit found mocked data)
        │
        ▼
   Frustration hook fires → learn-from-frustration agent
        │
        ▼
   New feedback memory entry written
   (.claude/memory/superdev-learned/<topic>.md)
        │
        ▼
   NEXT dispatch reads the new entry too
        │
        └─ The same mistake is never made twice in this project.
```

What gets captured:

| 🚨 Triggering event | 📝 Example lesson saved |
|:---|:---|
| User reverted 3 `frontend-module-builder` commits with "I told you not to change the buttons" | `no-restyle-source-buttons` — wrap source `<button>` markup, never replace with shadcn `<Button>` |
| `product-completeness-audit` found 3 hardcoded `*_count` fields | `aggregate-counts-always-real` — presenters must SELECT COUNT, never hardcode |
| User said "stop adding error boundaries to list pages" | `do-not-add-error-boundaries-to-list-pages` — rely on TanStack `isError` instead |

Scope (v1.2): **project-only** — lessons live in `.claude/memory/superdev-learned/` in the current repo and are appended to that repo's `CLAUDE.md` so EVERY Claude session in the repo sees them. The user can promote any lesson to global with *"remember this for all my projects"*.

Detection is **conservative** — only strong signals trigger learning ("no/stop/wrong" as a short message, repeat-correction markers like "I already told you", explicit code reverts, verifier rejections). Normal iteration ("actually change the color to blue") doesn't.

## 🤝 Agent Teams (Optional, ~3× tokens)

Several phases benefit from **adversarial 3-teammate reviews** when stakes are high. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

| | Phase | Team | What they do |
|:---:|:---|:---|:---|
| 🔎 | Gap audit (Phase A.3) | 3 critics | Adversarial review of PRD-vs-design gaps |
| 🔒 | Security audit (Phase D.2) | 3 auditors | Challenge each other's findings; reduce false positives |
| 🧪 | QA report synthesis (Phase D.3.6) | 3 reviewers | Severity debate — harshest-critic vs pragmatist vs shipping-advocate |
| ⚡ | Performance investigation | 3 hypothesists | Competing-hypotheses for ambiguous slowdowns |
| 🔧 | Per-feature pair-programming (Phase C.2) | be ↔ fe | Backend + frontend teammates negotiate contracts live |
| 🪲 | Systematic debugging — competing hypotheses 🆕 | 3 detectives | Each champions one root-cause candidate, designs an experiment to falsify the others' |
| 🗡️ | Brutal audit — severity debate 🆕 | 3 reviewers | Harshest-critic vs pragmatist vs shipping-advocate for ambiguous P0/P2 findings |
| ✅ | Product completeness — demo-vs-product 🆕 | 3 verdicts | strict / pragmatic / user-POV decide if HYBRID screens count as DEMO or ship-able |
| 🖼️ | Design drift severity 🆕 | 3 reviewers | designer / pixel-strict / pragmatist for drifts between 1% and 5% |

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

Event-driven enforcement that catches regressions the moment they happen and powers the self-learning loop:

| | Hook | Event | What it does |
|:---:|:---|:---|:---|
| ✅ | **Auto-typecheck (backend)** | `SubagentStop` · backend-module-builder, backend-extractor | Runs `<pm> typecheck` in `apps/api/` |
| ✅ | **Auto-typecheck (frontend)** | `SubagentStop` · frontend-module-builder, frontend-rewirer | Runs `<pm> typecheck` in `apps/web/` |
| ✅ | **Auto-build (contracts)** | `SubagentStop` · contracts-author | Runs `<pm> build` in `packages/contracts/` |
| 🚦 | **Stack-up check** | `SubagentStart` · all Playwright-using agents (qa-flow-tester, qa-performance-prober, journey-walker, route-walker, edge-case-prober, route-completeness-checker) | Hits `/v1/readiness` + Next.js root before runtime agents waste time on a dead stack |
| 🧠 | **Frustration detector** 🆕 | `UserPromptSubmit` · every prompt | Conservative regex scan for "no/stop/wrong/I told you/revert" → queues a learn-from-frustration dispatch |
| 🧠 | **Lesson capturer** 🆕 | `SubagentStop` · fix-applier, regression-verifier, design-fidelity-auditor, audit-synthesizer | If verifier verdict is REJECT/FAIL/drift > 1% OR a `LESSON:` line is in the agent's output, queues a learn-from-frustration dispatch |

All package-manager-aware hooks **auto-detect your PM** from the lockfile — no configuration required.

---

## 🗂️ Repository Structure

```
superdev/
├── 📁 .claude-plugin/
│   └── marketplace.json                     Marketplace manifest
├── 📁 plugins/superdev/
│   ├── 📁 .claude-plugin/
│   │   └── plugin.json                      Plugin manifest (v1.2.0)
│   ├── 📁 agents/                           43 specialized subagents
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
│   │   ├── qa-performance-prober.md         ┘
│   │   ├── bug-reproducer.md                ┐
│   │   ├── root-cause-investigator.md       │  5 systematic-
│   │   ├── hypothesis-tester.md             │  debugging
│   │   ├── fix-applier.md                   │  agents 🆕
│   │   ├── regression-verifier.md           ┘
│   │   ├── repo-cartographer.md             ┐
│   │   ├── route-walker.md                  │
│   │   ├── flow-walker.md                   │  6 brutal-
│   │   ├── data-flow-tracer.md              │  audit
│   │   ├── edge-case-prober.md              │  agents 🆕
│   │   ├── audit-synthesizer.md             ┘
│   │   ├── placeholder-hunter.md            ┐
│   │   ├── route-completeness-checker.md    │
│   │   ├── wiring-auditor.md                │  5 product-
│   │   ├── data-flow-real-vs-mock.md        │  completeness
│   │   ├── journey-walker.md                ┘  agents 🆕
│   │   ├── design-source-mirror.md          ┐  2 design-
│   │   ├── design-fidelity-auditor.md       ┘  preservation 🆕
│   │   └── learn-from-frustration.md           1 self-learning 🆕
│   ├── 📁 skills/                           11 skills with references/
│   │   ├── prd-design-build-orchestrator/   The conductor (routes to all)
│   │   ├── design-to-nextjs/                Claude Design → shadcn translation
│   │   ├── design-preservation/             🆕 Prototype → verbatim mirror + fidelity gate
│   │   ├── nestjs-enterprise-backend/       Backend skill
│   │   ├── security-review-and-fix/         Security skill
│   │   ├── prototype-to-saas/               Migration skill
│   │   ├── exploratory-qa/                  QA skill
│   │   ├── systematic-debugging/            🆕 5-phase root-cause-before-fix
│   │   ├── product-completeness-audit/      🆕 Demo-vs-product verdict
│   │   ├── brutal-exhaustive-audit/         🆕 Every file/route/flow/edge
│   │   └── superdev-self-learning/          🆕 Meta-loop — writes .claude/memory/superdev-learned/
│   ├── 📁 hooks/
│   │   ├── hooks.json                       PM-agnostic runtime + frustration hooks
│   │   └── scripts/
│   │       ├── detect-frustration.sh        UserPromptSubmit hook
│   │       └── maybe-learn.sh               SubagentStop hook
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
