---
name: superdev-build
description: Build a full-stack monorepo from a PRD + design handoff, directly as the main agent — no conductor, no parallel builder waves. Plan with on-disk artifacts (PRD_DIGEST, DESIGN_DIGEST, AUDIT, EXECUTION_PLAN), choose the stack (Nest.js or Laravel; Next.js or Inertia) and the clients (web, staff admin, Tauri desktop/mobile), lay the security foundation at bootstrap, author ALL shared contracts before any feature code, then build one module at a time (backend → runtime-verify → frontend → browser-verify → device-verify), finishing with the standalone audits, the release QA gate and the verify-done script. Use for greenfield full-stack builds and prototype productionizing; for single-side or single-feature work use the recipe skills directly.
---

# SuperDev Build — direct, sequential, verified

**You build the product yourself, in this session.** Plan the work, author canonical contracts, and build dependent modules sequentially with runtime proof. The conductor, parallel builder waves, hooks, agent-copy installers, and completion ledgers remain removed.

What you have instead:

- **Recipe skills are checklists you read and execute** (`design-to-nextjs`, `nestjs-enterprise-backend`, `laravel-enterprise-backend`, `frontend-modular-architecture`, …). Each works standalone; this skill only sequences them for a full build.
- **`agents/*.md` are optional helpers, auto-loaded by the plugin** — no install step, no copying into the project. Read-only auditors (`ui-auditor`, `static-auditor`, `wiring-auditor`, …) may be dispatched any time for a bounded check. Builder agents (`backend-module-builder`, …) may be dispatched for **one module at a time** only when context demands it — never backend and frontend for the same new contract in parallel.
- **Done is a script, not a claim:** [`../../scripts/verify-done.mjs`](../../scripts/verify-done.mjs) runs typecheck/lint/build, boots the built API, and sweeps for suppressions and placeholder content. Run it; do not narrate around it.

## Before anything: read the hard rules

Read [`references/hard-rules.md`](references/hard-rules.md) once at build start. Each rule states its applicable scope and required verification. Apply stack-specific requirements to the installed configuration, and preserve project-specific evidence in local memory rather than public guidance.

If the target project has `.claude/memory/superdev-learned/`, skim it once now (not before every step) for project-specific constraints.

## Step 1 — Plan on disk, confirm with the user

Produce four artifacts at the project root, in the formats defined in [`references/artifacts-format.md`](references/artifacts-format.md). Write them yourself, or dispatch the matching read-only agent one at a time (`prd-analyst`, `design-inventory`, `gap-auditor`, `plan-architect`) and save its return:

1. `PRD_DIGEST.md` — entities, features, screens, NFRs, open questions. No architecture decisions.
2. `DESIGN_DIGEST.md` — screens, components, implicit data shapes. No implementation detail. (Skip if there is no design; say so in the plan.)
3. `AUDIT.md` — PRD-vs-design gaps (`missing-from-design`, `missing-from-prd`, `type-mismatch`, `naming-drift`, `scope-creep`) with a `## DECISIONS` section.
4. `EXECUTION_PLAN.md` — final module list, entity catalog with view shapes, build order, CASL abilities for resource ownership plus the staff permission-key catalog, queues/crons, and a `## Security` section per [`security-foundation`](../security-foundation/SKILL.md): identities (end users, staff, devices), the permission catalog draft, personal-data fields to mask, balances and money paths, live-update channels and notification categories.

Show the plan summary (modules, build order, resolved gaps) and **wait for explicit user confirmation** before writing code. Revisions edit `AUDIT.md` DECISIONS, then regenerate the plan.

For a prototype source (existing HTML/app, not Claude Design output), first apply [`design-preservation`](../design-preservation/SKILL.md): verbatim copy + mirror + baseline screenshots before any rewiring.

## Step 2 — Stack choice (ask once, persist)

If the plan has backend modules, ask the operator:

- **Nest.js** — Postgres 17 + TimescaleDB + Drizzle + Redis/BullMQ + CASL ([`nestjs-enterprise-backend`](../nestjs-enterprise-backend/SKILL.md)); frontend is always Next.js ([`design-to-nextjs`](../design-to-nextjs/SKILL.md)).
- **Laravel** — Laravel 13 + PostgreSQL/TimescaleDB + DB cache/sessions + SQS + Bref ([`laravel-enterprise-backend`](../laravel-enterprise-backend/SKILL.md), [`laravel-bref-deploy`](../laravel-bref-deploy/SKILL.md)). Then ask the frontend: **Inertia monolith** (default, [`design-to-laravel`](../design-to-laravel/SKILL.md), Fortify session, typed props in `resources/js/types`) or **decoupled Next.js** (Sanctum tokens).

Then ask which **clients** the product needs, and persist them as `clients`:

- **Web app** — always, per the frontend choice above.
- **Staff admin** — a separate app (`apps/admin`) with its own staff identity, permission catalog and masked personal data, whenever the PRD has operators, back-office work or approvals (per [`security-foundation`](../security-foundation/references/staff-roles-and-pii.md)).
- **Tauri desktop/mobile** — `apps/mobile` (or `apps/desktop`) per [`design-to-tauri`](../design-to-tauri/SKILL.md), when the PRD asks for an Android, iOS or desktop app. Say plainly that iOS builds need macOS and that push to a closed phone app needs FCM/APNs credentials.

Persist `backend_stack`, `frontend_stack` and `clients` in `STACK.md` and `EXECUTION_PLAN.md` so every later step — and any resumed session — reads the same values.

## Step 3 — Bootstrap, then prove it boots

Scaffold the monorepo (the `monorepo-bootstrapper` agent file is the checklist; execute it yourself): pnpm/Turbo workspace (or the repo's existing PM), `apps/api` + `apps/web` + `packages/contracts` (single Laravel app for Inertia), root `docker-compose.yml` with healthchecks for every infra service, shadcn init + bulk primitives, `.env.example` complete.

Give the root `package.json` two data scripts the rest of the build relies on: `db:seed` (realistic demo data with one account per role — enough for parallel QA agents to each own theirs) and `db:fresh` (drop, migrate, `db:seed`). The committed suites and the release gate start from `db:fresh`.

Apply the hard rules for the selected stack: no `.default()` secrets, CommonJS contracts for the default CommonJS Nest.js consumer, compatible migration-tool configuration and client libraries, and sanitized, demo-gated mock routes.

Lay the **security foundation** in the skeleton, before any feature module ([`security-foundation`](../security-foundation/SKILL.md)): sessions checked on every request, rotating refresh tokens with theft detection, blocking with a reason, rate limits, hardening and the audit log; the staff identity and permission guard when `clients` includes an admin; the idempotency interceptor and per-account lock helper when the plan has balances; the event outbox and stream endpoints when it has live updates. Generate every secret (JWT, encryption key, VAPID keys) into the gitignored env file — no defaults.

Then prove the skeleton: infra up and healthy, API boots, web boots, `/health` + `/health/ready` answer, sign-in works against the real session table, and the first committed suite (`test:security`) runs green. Do not proceed on "it typechecks."

## Step 4 — Contracts first, all of them, one owner

Author **every** module's view shapes in `packages/contracts` before any feature code (Laravel+Next.js: Eloquent API Resources + hand-written TS types guarded by a contract test; Inertia: typed props). One owner — you. Enforce the view-shape contract (backend returns render-ready data; no `.optional()` on data fields) and Title-Case enums (DB value = wire value = UI label).

Build the contracts package and reach a checkpoint the user can commit. This ordering is what makes later steps safe: backend and frontend both consume a contract that already exists, so neither invents a local schema. **A frontend local `z.object` mirroring a server view is a defect** (form-input schemas are fine).

If a later module genuinely needs a new shape, add it to contracts first, rebuild, then build the module against it.

## Step 5 — Build loop: one module, verified, then the next

For each module in `EXECUTION_PLAN.md` order:

1. **Backend** per the stack recipe (module structure, presenter/view, CASL/`#[Authorize]`, audit, tests). Cross-cutting decorators go where the framework actually reads them (hard-rules #5).
2. **Verify backend at runtime:** typecheck + unit/e2e + build the dist + boot it (`node apps/api/dist/main.js`) + `curl` health and one real endpoint of this module + prove one side effect (row written, job enqueued, audit row present).
3. **Frontend** against the canonical contract, per [`frontend-modular-architecture`](../frontend-modular-architecture/SKILL.md) (module folders, stores, Portal primitives, file-size laws) and the design recipe. Before writing components, confirm which shadcn backing library is installed (hard-rules #7) and mirror an existing usage.
4. **Verify frontend in a browser:** typecheck + open the route(s) in production mode against the running API; client-mounted surfaces (canvas/WebGL, charts) must actually mount with zero console errors.
5. **Admin and device clients:** build the module's staff screens (masked personal data, permission-gated actions) and, when `clients` includes Tauri, its app screens per [`design-to-tauri`](../design-to-tauri/SKILL.md) — verified on an emulator or phone with `adb`, not in a browser tab (hard-rules #18).
6. **Extend the committed suites** for what the module added: contract checks for its responses, its permission keys in the role matrix, its money paths in the money suite, its events in the live-update suite ([`security-foundation/references/security-test-suites.md`](../security-foundation/references/security-test-suites.md)).
7. Record anything surprising as a lesson (Step 7) while it is fresh.

No parallel backend+frontend work on a contract created in the same step. Sequential feels slower and is faster: every rework loop in the old wave model came from two agents building against shapes the other had not seen.

Existing fat frontend module (>300-line files) in the way? Run [`frontend-refactoring`](../frontend-refactoring/SKILL.md) on that one module first; never rewire a god-file. A bug surfaces mid-build? Switch to [`systematic-debugging`](../systematic-debugging/SKILL.md) and fix at the verified root cause — no suppressions (`eslint-disable`, `@ts-ignore`, `as any`) as a substitute.

## Step 6 — Cross-cutting audits (pick by risk), then the release gate (always)

Run these as their own skills; each may dispatch its read-only auditors:

- Integration + tenancy: cross-workspace isolation, permission enforcement, audit coverage, view-shape compliance against live responses.
- [`security-review-and-fix`](../security-review-and-fix/SKILL.md) — inventory → static → dynamic → dependency → fix.
- [`exploratory-qa`](../exploratory-qa/SKILL.md) — Playwright flows, consistency, performance (stack must be up first).
- [`product-completeness-audit`](../product-completeness-audit/SKILL.md) — demo-vs-product: placeholders, HYBRID screens, mocked data, in production mode.
- [`production-readiness-audit`](../production-readiness-audit/SKILL.md) / [`brutal-exhaustive-audit`](../brutal-exhaustive-audit/SKILL.md) — whole-product passes before a ship claim. Every score must cite its command/browser/DB evidence; an uncited score counts as not run.

Then, always, the **[`release-qa-gate`](../release-qa-gate/SKILL.md)** on a fresh seed: every committed suite, route × role × viewport × theme, every form and link, accessibility and contrast in every interactive state, security behaviours in the browser, money races, live updates across clients, and the device pass for native clients. Its `QA_COVERAGE.md` must have no `FAIL` and no unaccepted `NOT RUN`.

## Step 7 — Prove done, capture lessons

Run the gate from the target repo root and read its verdict:

```bash
node <superdev-plugin>/scripts/verify-done.mjs --suites --strict
```

The release gate's step-2 run is this proof when it ran on the final commit (`qa/verify-done.txt`); if code changed since, run it again now, before the gate's closing `db:fresh`. `--suites` runs every committed `test:*` script (and `smoke`) against the running stack after the build and boot checks, so start the stack and reset the demo data first; `--strict` turns skipped checks and warnings into failures. Exit 0 is required alongside the Step-6 audits you chose, each clean; a `QA_COVERAGE.md` with no `FAIL` and no unaccepted `NOT RUN`; and recorded verification of every applicable hard rule. The script's default Nest.js boot check does not establish Laravel runtime readiness or replace browser, database, and security evidence. Fix failed checks at their root cause and re-run them.

If a correction or failed check reveals a reusable lesson, record redacted evidence in `.claude/memory/superdev-learned/<topic>.md` using [`superdev-self-learning`](../superdev-self-learning/SKILL.md). Propose only the generic rule, scope, corrective action, and verification check for `hard-rules.md`. Keep project names, domains, incident details, and private metrics out of public documentation and bundles.

## Conventions every step enforces

- **Monorepo + shared contracts** — one source of truth for wire shapes.
- **View-shape contract** — the API returns render-ready data; the UI renders without `?.`/`??` chains on contract fields.
- **Title-Case enums** — DB = wire = UI label; no label maps.
- **shadcn/ui only** for visual primitives (`ui-auditor` enforces); check Radix vs Base UI before composing.
- **Docker for all infrastructure**, workspace-prefixed containers, healthchecks on every service.
- **Permissions + audit on every mutation**, proven by side-effect checks, not decorator presence.
- **Security built in from bootstrap** — sessions checked per request, two-factor/passkeys where accounts matter, masked personal data with audited reveal, idempotent money paths, per-account balance locks, live updates only after commit — each proven by a committed suite.
- **Every client proven where it runs** — browser for web and admin, emulator or phone for Tauri.
- **Dual-mode frontend** (demo fixtures vs production API) where the design recipe calls for it; demo/mock routes never ship ungated.
- **Operator UI is for operators** — structured controls with plain-language labels; never raw JSON editors or magic-number sentinels.
- **One canonical public origin** for every public-facing URL, identical across apps.

## What replaced what (v1 → v2)

The old conductor skill, the agent-extractor install scripts (which installed stale, abridged agent copies), the bash hook machinery (done-gate sentinels, frustration detection, per-dispatch lesson threading), and self-graded completion ledgers were removed. Their durable parts live on here (planning artifacts, stack gates), in `hard-rules.md` (the lessons), in `verify-done.mjs` (the checks, run live), and in the standalone skills (everything else).
