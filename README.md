<div align="center">

# Superdev — Claude Code + Codex Plugin

**18 production-grade skills + 54 agents for full-stack monorepo builds**

*The main agent builds directly — contracts first, one verified module at a time. No conductor, no parallel builder waves, no self-graded "done".*

<br>

[![Get Started](https://img.shields.io/badge/Get_Started-blue?style=for-the-badge)](#-quick-start)
[![Stars](https://img.shields.io/github/stars/boparaiamrit/superdev?style=for-the-badge&color=gold)](https://github.com/boparaiamrit/superdev)
[![License](https://img.shields.io/github/license/boparaiamrit/superdev?style=for-the-badge)](https://github.com/boparaiamrit/superdev/blob/main/LICENSE)

[![GitHub](https://img.shields.io/badge/GitHub-boparaiamrit-181717?style=flat-square&logo=github)](https://github.com/boparaiamrit)
[![X/Twitter](https://img.shields.io/badge/X-@boparaiamrit-000000?style=flat-square&logo=x)](https://x.com/boparaiamrit)
[![Sponsor](https://img.shields.io/badge/Sponsor-❤️-ea4aaa?style=flat-square)](https://github.com/sponsors/boparaiamrit)

</div>

---

> **v2.0.0 — the conductor is removed.** v1 routed every build through an orchestrator skill that dispatched parallel builder subagents in waves, installed (stale, abridged) agent copies into each project, threaded "lessons" before every dispatch via bash hooks, and let builds mark their own completion ledger `pass`. On the real projects built with it, that produced contract races between parallel agents, production binaries dead on arrival under fully green test suites, 71 audit decorators writing zero audit rows, and done-claims no machine check backed. v2 keeps the recipes, auditors, and conventions that worked — and makes the main agent build directly and sequentially, prove each module at runtime, and finish with a live verification script. Details: [`superdev-build`](plugins/superdev/skills/superdev-build/SKILL.md) and the [`hard rules`](plugins/superdev/skills/superdev-build/references/hard-rules.md) those failures produced.

## 🧬 What's inside — 18 skills

| # | Skill | What it does |
|:---:|:---|:---|
| 1 | 🧭 **superdev-build** 🆕 v2.0.0 | The full-build SOP the main agent executes itself: plan artifacts (`PRD_DIGEST` / `DESIGN_DIGEST` / `AUDIT` / `EXECUTION_PLAN`) → user confirmation → stack choice → bootstrap proven by boot → **all contracts first** → one module at a time (backend → boot + curl + side-effect verify → frontend → browser verify) → audits → `verify-done`. |
| 2 | 🎨 **design-to-nextjs** | Claude Design handoffs → production Next.js (shadcn-everywhere, view-shape contract, dual-mode adapter, Radix-vs-**Base UI** detection before composing). |
| 3 | 🐘 **design-to-laravel** | Claude Design → **Laravel + Inertia 3 + React 19** monolith (typed props, Wayfinder, `useForm`, Fortify + spatie/permission). Default Laravel frontend. |
| 4 | 🖼️ **design-preservation** | Prototype sources are copied **verbatim**, mirrored at `/__design-source/`, pixel-diffed at ≤ 1% drift. The Holy Grail rule: no restyling. |
| 5 | 🏛️ **nestjs-enterprise-backend** | Nest.js + Postgres 17/TimescaleDB + Drizzle + CASL + BullMQ + Redis; `@Audit` on controller handlers; **CommonJS contracts**; no `patchNestJsSwagger` boot crash. |
| 6 | 🐘 **laravel-enterprise-backend** | Laravel 13 + PostgreSQL/TimescaleDB + DB cache/sessions + SQS; Eloquent API Resources + hand-written TS contracts; `#[Audit]` → hypertable; global-scope tenancy; Title-Case enums; Boost. |
| 7 | ☁️ **laravel-bref-deploy** | Serverless Laravel on AWS Lambda via Bref 3.x (web + SQS worker + console, EventBridge scheduler, S3/CloudFront, SSM, no VPC). |
| 8 | 🧱 **frontend-modular-architecture** | Anti-god-file law: page ≤ 100 / component ≤ 200 lines, per-module Zustand stores, wizards split per-step, overlays in `parts/<name>/` via shadcn Portal primitives. |
| 9 | 🔨 **frontend-refactoring** | Atomic one-module conversion of a fat module: deep plan → review → behavior baseline → atomic execute → zero-drift verify. Any drift = full rollback. |
| 10 | 🔄 **prototype-to-saas** | Single-user Next.js prototype (JSON-as-backend) → multi-tenant SaaS, feature-by-feature rewiring without destroying the UI. |
| 11 | 🔒 **security-review-and-fix** | Six-phase audit: inventory → static → dynamic → dependency → triage → fix. |
| 12 | 🧪 **exploratory-qa** | Senior-engineer QA: Playwright happy + edge paths, consistency audit, perf probing with N+1 detection. |
| 13 | 🪲 **systematic-debugging** | Reproduce → root-cause → hypothesis-test → fix → regression-verify. No fix without a verified `ROOT_CAUSE.md`. |
| 14 | ✅ **product-completeness-audit** | Demo-vs-product verdict in production mode: placeholders, stub handlers, mocked data, HYBRID screens. |
| 15 | 🎯 **production-readiness-audit** | Five passes score every module 1–10 (weakest pass wins, tenancy/P0 hard caps); **every score cites its command/browser/DB evidence**; loop fix → re-audit until all ≥ 9. |
| 16 | 🗡️ **brutal-exhaustive-audit** | Every file, route, flow, data path, edge case — mandatory disk-tracked checklists before any "ship" claim. |
| 17 | 🧠 **superdev-self-learning** | Deliberate lesson capture to the target project's `.claude/memory/superdev-learned/`; stack-general lessons graduate into `hard-rules.md` instead of staying siloed. |
| 18 | 🏁 **superdev-done** | Runs `verify-done.mjs`: live Definition-of-Done — per-package typecheck/lint/build, **boots the built API**, contracts-format + swagger-landmine checks, suppression + placeholder sweeps. |

> 🔀 **Stack choice** — `superdev-build` Step 2 asks **Laravel or Nest.js**; Laravel then asks **Inertia monolith** (default) vs **decoupled Next.js**. Persisted in `STACK.md`. Nest.js always pairs with Next.js; QA/security/audit skills are identical either way.

**Every skill works standalone** — "run a security audit" runs exactly that, no pipeline. `superdev-build` only sequences the skills for a full greenfield build.

## ⚔️ The hard rules (learned in production)

v2's center of gravity is [`hard-rules.md`](plugins/superdev/skills/superdev-build/references/hard-rules.md) — twelve failure classes that actually shipped on SuperDev-built projects, now enforced by recipes and checks instead of rediscovered per project:

1. **Boot the built artifact** — 119 green tests once hid a dead-on-arrival production binary. `node dist/main.js` + health curl, every module.
2. **Never `patchNestJsSwagger()`** with @nestjs/swagger 11 — crashes boot (hit two projects; the second *after* the first "learned" it project-locally).
3. **Contracts build as CommonJS** for Nest consumers — ESM-only contracts throw at boot, not at typecheck.
4. **Contracts first, one owner** — parallel frontend/backend work against a same-step contract invents conflicting schemas that only fail in production mode.
5. **Verify side effects, not decorators** — 71 `@Audit` service methods wrote 0 audit rows because interceptors read controller handlers.
6. **No default secrets, no unsanitized filesystem routes, no ungated mocks** in scaffold output.
7. **Confirm Radix vs Base UI** (`components.json`) before writing shadcn code — `asChild` does not exist on Base UI.
8. **drizzle-kit gets its own tsconfig target** — its esbuild rejects `es2023`.
9. **Browser-smoke client-mounted routes** — React-19/r3f crashes pass every static gate.
10. **No raw JSON in operator UI** — structured controls with plain-language labels.
11. **One canonical public origin** for every public URL, identical across apps.
12. **Live provider keys only in gitignored env; tests use stubs.**

## 🚀 Quick start

### Install

**Claude Code:**

```shell
claude plugin marketplace add boparaiamrit/superdev --scope project
claude plugin install superdev@superdev --scope project
```

Run them from the target Git project — Superdev is **project-scoped only** (never user scope). The bundled helper `bash /path/to/superdev/install-superdev.sh` delegates to the same two commands with `--scope project` and refuses to run outside a Git project. For plugin development only: `claude --plugin-dir ~/superdev/plugins/superdev`.

**Codex:** the repo-local marketplace at `.agents/plugins/marketplace.json` exposes the same plugin; see [CODEX.md](CODEX.md).

### Run

Full build — just say it:

```text
I have a PRD at docs/PRD.md and a design handoff at design/. Build the full-stack app.
```

Or invoke any single skill directly, no build pipeline involved:

| 🎯 Want only… | 💬 Say… | 🎬 What happens |
|:---|:---|:---|
| Security audit | *"Run a security audit on this codebase"* | `security-review-and-fix` → `SECURITY_REPORT.md` |
| QA pass | *"Run a production-readiness QA pass"* | `exploratory-qa` Playwright flows + perf probes |
| A stubborn bug fixed properly | *"Help me debug this failure: …"* | `systematic-debugging` root-cause-before-fix |
| Demo-vs-product truth | *"Is this actually wired up or just looks done?"* | `product-completeness-audit` in production mode |
| Score every module | *"Rate each module 1–10 and complete it fully"* | `production-readiness-audit` loop until all ≥ 9 with cited evidence |
| Design → Next.js | *"Convert this Claude Design output to Next.js"* | `design-to-nextjs` |
| Done-check | *"Are we done?"* | `superdev-done` runs `verify-done.mjs` live |

## 🏗️ How a build works now

```text
superdev-build (main agent executes; subagents optional, one at a time)
  Step 0  Read hard-rules + project lessons (once)
  Step 1  Plan: PRD_DIGEST → DESIGN_DIGEST → AUDIT (+DECISIONS) → EXECUTION_PLAN → user confirms
  Step 2  Stack: Nest.js | Laravel  (→ Inertia | Next.js)   → STACK.md
  Step 3  Bootstrap monorepo + Docker infra → prove it boots (health endpoints)
  Step 4  Contracts: ALL view shapes, one owner → build (CJS) → checkpoint
  Step 5  Per module, sequentially:
            backend → typecheck/tests → BOOT dist → curl → side-effect proof
            frontend (canonical contract only) → typecheck → browser-open in prod mode
  Step 6  Cross-cutting audits by risk (integration/tenancy, security, QA, completeness, readiness)
  Step 7  verify-done.mjs green + audits clean = done. Lessons written down.
```

**Agents (54)** are auto-loaded from `plugins/superdev/agents/` — the single source of truth, never copied into projects. Read-only auditors can be dispatched any time; builder agents are checklists the main agent usually executes itself, dispatchable for one bounded module when context demands. No install scripts, no extraction, no stale copies (v1's installer shipped abridged agent versions — e.g. a 774-char `integration-tester` where the real one is ~9k).

**No hooks.** v1's bash hook machinery (auto-typecheck, stack-up checks, frustration detection, done-gate Stop sentinel) was Windows-hostile and silently inert in practice. Verification is explicit and cross-platform: run the checks, read the result.

## 🏗️ Architectural commitments (unchanged, now actually enforced)

| # | Commitment |
|:---:|:---|
| 1 | **Monorepo** — `apps/web` + `apps/api` + `packages/contracts` (Inertia: single Laravel app) |
| 2 | **View-shape contract** — backend returns render-ready data; no `?.`/`??` chains on contract fields |
| 3 | **Title-Case enums** — DB = wire = UI label, zero conversion code |
| 4 | **shadcn/ui everywhere** — every primitive from `@/components/ui/*`; Radix **or Base UI**, detected first |
| 5 | **Docker for all infrastructure** — healthchecks on every service (Laravel serverless: managed Postgres/Timescale) |
| 6 | **Permissions + audit on every mutation** — proven by rows written, not decorators present |
| 7 | **Dual-mode adapter** — demo fixtures vs production API; mock routes sanitized + demo-gated |

## 📦 Tech stack baked in

| Layer | Choices |
|:---|:---|
| Frontend | Next.js App Router · Tailwind · TanStack Query/Table · Zustand · Zod · React Hook Form · shadcn/ui — or Laravel + Inertia 3 + React 19 |
| Backend | Nest.js + PostgreSQL 17/TimescaleDB + Drizzle + Redis/BullMQ + CASL + nestjs-zod — or Laravel 13 + PostgreSQL/TimescaleDB + DB cache/sessions + SQS on Bref |
| Tooling | pnpm workspaces (default) · Turborepo · Docker Compose · PM-agnostic checks (pnpm/npm/yarn/bun by lockfile) |
| QA | Playwright |

## 🗂️ Repository structure

```text
superdev/
├── plugins/superdev/
│   ├── skills/                  18 skills (superdev-build + recipes + audits)
│   ├── agents/                  54 agents — single source, plugin auto-loaded
│   ├── scripts/verify-done.mjs  the live Definition-of-Done check (Node, cross-platform)
│   ├── .claude-plugin/          Claude Code manifest
│   └── .codex-plugin/           Codex manifest
├── tests/                       plugin integrity + project-scope tests
├── CHANGELOG.md                 release history (v2.0.0 notes + migration guide)
├── docs/superpowers/            historical design specs/plans (v1 era, kept for provenance)
├── superdev.zip                 packaged plugin (kept in sync by the integrity tests)
├── install-superdev.sh          project-scoped Claude installer helper
├── CODEX.md                     Codex host notes
└── README.md
```

## ✅ Validating changes

```bash
python -m unittest discover -s tests -v
```

Fails on: missing/mismatched frontmatter, broken skill links, stale counts in README/manifests, any reference to the removed conductor/install/hook machinery, recipes re-teaching the `patchNestJsSwagger` crash, and zip drift.

## ⚙️ Requirements

Claude Code (v2.1.32+) or Codex · Node.js (>= 18, for target projects + `verify-done.mjs`) · a package manager (pnpm default) · Docker for project infrastructure.

## 📜 License

MIT
