<div align="center">

# Superdev — Claude Code + Codex Plugin

**21 production-grade skills + 60 agents for full-stack monorepo builds**

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

> **v2.1.0** adds Tauri desktop and mobile clients ([`design-to-tauri`](plugins/superdev/skills/design-to-tauri/SKILL.md)), a security layer built in from bootstrap ([`security-foundation`](plugins/superdev/skills/security-foundation/SKILL.md)), and a release QA gate where every coverage cell cites evidence ([`release-qa-gate`](plugins/superdev/skills/release-qa-gate/SKILL.md)). It keeps direct sequential builds, canonical contracts, and explicit runtime verification. The conductor, hooks, agent-copy installers, and completion ledgers remain removed. Use [`superdev-build`](plugins/superdev/skills/superdev-build/SKILL.md) for the build workflow and the [`hard rules`](plugins/superdev/skills/superdev-build/references/hard-rules.md) for stack-specific requirements and verification.

## 🧬 What's inside — 21 skills

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
| 18 | 🏁 **superdev-done** | Runs `verify-done.mjs`: live Definition-of-Done — per-package typecheck/lint/build, **boots the built API**, contracts-format + swagger-landmine checks, Tauri shell checks, suppression + placeholder sweeps, and with `--suites` every committed runtime suite against the running stack. |
| 19 | 📱 **design-to-tauri** 🆕 v2.1.0 | Tauri 2 desktop + Android + iOS clients on the shared contracts: locked-down shell (CSP, least-privilege capabilities, exact HTTP origins, keystore tokens), mobile token auth with single-flight refresh, SSE live updates and phone alerts, emulator QA with `adb`, store release. |
| 20 | 🛡️ **security-foundation** 🆕 v2.1.0 | The security layer built at bootstrap, not audited later: sessions checked per request, refresh rotation with theft detection, blocking with a reason, TOTP + recovery codes + passkeys + device list + QR sign-in, separate staff identity with permission keys, masked personal data with audited reveal, per-account balance locks, idempotency keys, reconciliation, transactional live updates and notifications — each proven by a committed suite. |
| 21 | 🧾 **release-qa-gate** 🆕 v2.1.0 | The "cover everything" pass on a fresh seed: committed suites, route × role × viewport × theme, every form and link, axe + contrast in every interactive state, security behaviours in the browser, money races, live updates across clients, the phone app on a device — `QA_COVERAGE.md` with evidence in every cell. |

> 🔀 **Stack choice** — `superdev-build` Step 2 asks **Laravel or Nest.js**; Laravel then asks **Inertia monolith** (default) vs **decoupled Next.js**. Persisted in `STACK.md`. Nest.js always pairs with Next.js; QA/security/audit skills are identical either way.

**Every skill works standalone** — "run a security audit" runs exactly that, no pipeline. `superdev-build` only sequences the skills for a full greenfield build.

## ⚔️ The hard rules

[`hard-rules.md`](plugins/superdev/skills/superdev-build/references/hard-rules.md) defines eighteen reusable requirements. Each states where it applies and how to verify it:

1. **Boot the built artifact** after each backend module, using the selected stack's production entry point and health checks.
2. **Use supported validation and documentation integration** — do not scaffold `patchNestJsSwagger()` or private Swagger imports.
3. **Match contract exports to their consumers** — CommonJS contracts for the default CommonJS Nest.js stack.
4. **Contracts first, one owner** — import canonical response shapes and build dependent modules sequentially.
5. **Verify permissions and side effects** through real mutations, audit rows, denied requests, and source-backed aggregates.
6. **No default secrets, no unsanitized filesystem routes, no ungated mocks** in scaffold output.
7. **Confirm Radix vs Base UI** from installed primitives before composing shadcn components.
8. **Keep migration tooling compatible** — isolate its compiler configuration when needed and verify generated SQL.
9. **Browser-test client-mounted routes** with dependency versions compatible with the installed React major.
10. **No raw JSON in operator UI** — structured controls with plain-language labels.
11. **One canonical public origin** for every public URL, identical across apps.
12. **Keep provider keys private** — tests use stubs, saved evidence is redacted, and production never silently substitutes demo data.
13. **Check the session on every request** — revocation, staff disabling and blocking take effect at once, and a blocked person is told why.
14. **Serialize balance changes per account** — a transaction-scoped lock in every spend, grant and expiry path, and a reconciliation that proves the books.
15. **Make money-moving requests idempotent** — `Idempotency-Key` replay, discount re-validation at payment, entitlements that end with the plan.
16. **Publish live updates inside the writing transaction** — delivered only after commit, filtered by permission, replayed on reconnect, ended on revocation.
17. **Do not trust correlated subqueries in single-table ORM selects** — compute counts with grouped queries and assert them against seeded data.
18. **Prove native clients on a device** — locked-down Tauri shell, then every module driven on an emulator or phone.

### Public documentation and saved lessons

READMEs, release notes, and bundled guidance use generic technical requirements without real project names, customer domains, incident anecdotes, or private metrics. Keep source evidence in project-local memory. Promote only the failure mechanism, applicable conditions, corrective action, and verification check.

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
| Done-check | *"Are we done?"* | `superdev-done` runs `verify-done.mjs` live (add `--suites --strict` for the committed runtime suites and a release claim) |
| A phone or desktop app | *"Build the Android and iOS app on the same API"* | `design-to-tauri` + emulator QA |
| Security built in | *"Add 2FA, passkeys, roles and masked phone numbers"* | `security-foundation` with committed proof suites |
| Test everything before release | *"Have you done QA? Check every page, every role, contrast, dead links, the app"* | `release-qa-gate` → `QA_COVERAGE.md` |

## 🏗️ How a build works now

```text
superdev-build (main agent executes; subagents optional, one at a time)
  Step 0  Read hard-rules + project lessons (once)
  Step 1  Plan: PRD_DIGEST → DESIGN_DIGEST → AUDIT (+DECISIONS) → EXECUTION_PLAN → user confirms
  Step 2  Stack: Nest.js | Laravel  (→ Inertia | Next.js)   → STACK.md
  Step 3  Bootstrap monorepo + Docker infra → prove it boots (health endpoints)
  Step 4  Contracts: ALL view shapes, one owner → build for consumers → checkpoint
  Step 5  Per module, sequentially:
            backend → typecheck/tests → BOOT dist → curl → side-effect proof
            frontend (canonical contract only) → typecheck → browser-open in prod mode
  Step 6  Cross-cutting audits by risk (integration/tenancy, security, QA, completeness, readiness)
  Step 7  verify-done.mjs green + audits clean = done. Lessons written down.
```

**Agents (54)** are auto-loaded from `plugins/superdev/agents/`, the single source of truth. Read-only auditors can check bounded scopes; builder agents provide checklists for one module at a time. Agent-copy installers and extraction scripts remain removed.

**Verification is explicit:** run the checks and read their results. Browser, database, and stack-specific runtime evidence supplement the automated gate.

## 🏗️ Architectural commitments

| # | Commitment |
|:---:|:---|
| 1 | **Monorepo** — `apps/web` + `apps/api` + `packages/contracts` (Inertia: single Laravel app) |
| 2 | **View-shape contract** — backend returns render-ready data; no `?.`/`??` chains on contract fields |
| 3 | **Title-Case enums** — DB = wire = UI label, zero conversion code |
| 4 | **shadcn/ui everywhere** — every primitive from `@/components/ui/*`; Radix **or Base UI**, detected first |
| 5 | **Docker for all infrastructure** — healthchecks on every service (Laravel serverless: managed Postgres/Timescale) |
| 6 | **Permissions + audit on every mutation** — proven by rows written, not decorators present |
| 7 | **Dual-mode adapter** — demo fixtures vs production API; mock routes sanitized + demo-gated |
| 8 | **Security built in** — sessions, two-factor, staff permissions, masking, money safety and live updates laid at bootstrap and proven by committed suites |
| 9 | **Every client proven where it runs** — browser for web and admin, emulator or phone for Tauri, with cited evidence in `QA_COVERAGE.md` |

## 📦 Tech stack baked in

| Layer | Choices |
|:---|:---|
| Frontend | Next.js App Router · Tailwind · TanStack Query/Table · Zustand · Zod · React Hook Form · shadcn/ui — or Laravel + Inertia 3 + React 19 |
| Backend | Nest.js + PostgreSQL 17/TimescaleDB + Drizzle + Redis/BullMQ + CASL + nestjs-zod — or Laravel 13 + PostgreSQL/TimescaleDB + DB cache/sessions + SQS on Bref |
| Tooling | pnpm workspaces (default) · Turborepo · Docker Compose · PM-agnostic checks (pnpm/npm/yarn/bun by lockfile) |
| Clients | Next.js web + staff admin · Tauri 2 desktop/Android/iOS |
| QA | Playwright · axe-core · adb/emulator · committed runtime suites (`test:*`) |

## 🗂️ Repository structure

```text
superdev/
├── plugins/superdev/
│   ├── skills/                  21 skills (superdev-build + recipes + audits)
│   ├── agents/                  60 agents — single source, plugin auto-loaded
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

On Windows, run the full Python suite inside WSL so installer tests use Bash-compatible paths. Run `node --check plugins/superdev/scripts/verify-done.mjs` separately if Node is available only on the Windows host.

Checks cover frontmatter, links, inventory, removed machinery, unsafe Swagger scaffolding, archive parity, public-guidance attribution, and hard-rule scope/verification fields.

## ⚙️ Requirements

Claude Code (v2.1.32+) or Codex · Node.js (>= 18, for target projects + `verify-done.mjs`) · a package manager (pnpm default) · Docker for project infrastructure.

## 📜 License

MIT
