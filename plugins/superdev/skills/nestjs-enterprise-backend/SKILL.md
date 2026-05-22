---
name: nestjs-enterprise-backend
description: Build a production-grade Nest.js backend with PostgreSQL 17 + TimescaleDB, Drizzle ORM, Redis (cache + BullMQ queues), workers and crons via BullMQ, JWT auth with multi-tenant workspace isolation, CASL for authorization, Zod validation, an @Audit method decorator that writes to a TimescaleDB hypertable, structured Pino logs, and Prometheus metrics. The backend is the upstream half of a monorepo whose downstream is a Next.js app (built by the design-to-nextjs skill); both apps share Zod schemas from packages/contracts. Backend always returns view-ready data (counts, labels, discriminated unions) so frontend renders without optional-chaining gymnastics. Use whenever the user wants to build, scaffold, or extend a Nest.js backend; mentions Drizzle, Postgres, TimescaleDB, BullMQ queues, workers, crons, CASL abilities, audit logging, view-shape contracts, hypertables, continuous aggregates, or multi-tenant SaaS patterns.
---

# Nest.js Enterprise Backend

A pipeline for building a production-grade Nest.js backend, sized for a monorepo whose frontend is built by the `design-to-nextjs` skill. The skill operates in six phases. Walk them in order; skipping phases produces backends that "work" until they hit real load, a real tenant boundary, or a real audit.

## How to invoke this skill

This is a **recipe skill** — it provides the patterns and references that builder agents follow.

### Pattern 1 — invoked by the orchestrator (most common)

When `prd-design-build-orchestrator` runs, its `backend-module-builder` subagent reads this skill's references directly. No separate invocation needed; this skill is installed at `~/.claude/skills/nestjs-enterprise-backend/`, and the builder loads `SKILL.md` plus the references relevant to the current module (typically `module-structure.md`, `drizzle-timescaledb.md`, `view-presenter.md`, `auth-casl.md`, `audit-logging.md`).

### Pattern 2 — invoked by the migration skill

When `prototype-to-saas` runs, its `backend-extractor` agent uses this skill's references the same way — building Nest.js modules that match what the existing frontend expects.

### Pattern 3 — standalone (backend-only build)

For backend-only builds without the orchestrator (e.g., a Nest.js API to serve an existing frontend or to be consumed by a mobile app), start a Claude Code session:

```
Build a Nest.js backend with the architecture patterns from this skill.
Domain: a CRM with companies, contacts, deals.
```

The main session reads this skill's SKILL.md and walks the six phases (inventory, planning, scaffolding, auth+tenancy, module generation, integration). No subagents required for this path; the main session does the work.

## Architectural commitments (non-negotiable)

These are baked into every phase. Push back on the user only if they explicitly want a different stack — otherwise enforce them.

### 1. Monorepo with shared contracts

```
<workspace>/
├── apps/
│   ├── web/                  ← Next.js frontend (design-to-nextjs skill)
│   └── api/                  ← Nest.js backend (this skill)
├── packages/
│   ├── contracts/            ← Zod schemas, view types, error codes — SINGLE SOURCE OF TRUTH
│   ├── tsconfig/             ← shared tsconfig presets
│   └── eslint-config/        ← shared lint config
├── pnpm-workspace.yaml
├── turbo.json
└── package.json
```

Backend imports schemas from `@<scope>/contracts`. Frontend imports the same schemas. No duplication, no sync scripts, one source.

### 2. View-shape contract — backend returns view-ready data

Backend always returns data in the shape the frontend renders. **Frontend code never uses `?.` or `??` to defend against missing fields.** This is enforced by the contract.

What this means in practice:

- **No optional fields for data that exists.** A company always has a `name`. Field is non-nullable.
- **Counts and aggregates are always returned, defaulted to 0.** Not `contacts_count?: number` — always `contacts_count: number`.
- **Related entities are populated, not implied by foreign keys.** A campaign response includes `mailbox: MailboxSummary`, not just `mailbox_id`.
- **Computed labels are built server-side.** Growth signal returns as `{ kind: 'growing', label: '+12% YoY', delta_pct: 12 }`, not `headcount_current` + `headcount_12mo_ago` for the frontend to compute.
- **Variations are discriminated unions, not optional flags.** "Last activity" is `{ kind: 'None' } | { kind: 'Email Sent', at, label } | { kind: 'Email Received', at, label }`. Never `last_activity_at?: string`.
- **Dates are ISO 8601 strings.** Never `Date` objects.

Zod schemas in `packages/contracts` enforce this — `.optional()` is a smell; `.nullable()` is acceptable but explicit; defaults (`.default(0)`) on number fields are common.

Backend services use **presenters** to convert DB rows → view shape. Every entity has a `toView(row): View` mapper. Services call it before returning. This is where transformation work happens — not on the frontend.

### 3. Drizzle ORM

Drizzle is the ORM. Schema is defined in TypeScript, migrations are generated from schema changes, queries are SQL-shaped with full type inference. No Prisma.

### 4. CASL for authorization

Authorization is not just role checks. CASL defines abilities — "a user with role X can perform action Y on subject Z when condition W" — and guards check those abilities. Roles are an input to ability resolution, not the resolution itself.

### 5. `@Audit` decorator → TimescaleDB hypertable

Every mutating service method is decorated with `@Audit({ action, subject })`. An interceptor reads the metadata, executes the method, and writes a structured audit log entry to the `audit_logs` hypertable. Every meaningful action becomes searchable in compliance-grade detail with zero per-handler boilerplate.

### 6. Title Case for every enum value — no conversion code anywhere

Every enum, status, stage, role, tag, or discriminator stored or transmitted as a string is in **Title Case**. The DB value equals the wire value equals the UI label. There is no `.toUpperCase()`, no label lookup map, no snake_case-to-display conversion anywhere in the codebase.

**Good:**

```ts
status:        'Active' | 'Inactive' | 'Pending' | 'Suspended'
plan:          'Starter' | 'Growth' | 'Enterprise'
role:          'Admin' | 'Operator' | 'Pipeline' | 'Viewer'
industry:      'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'
stage:         'New' | 'Qualified' | 'Proposal Sent' | 'Negotiation' | 'Won' | 'Lost'
bounce_status: 'None' | 'Soft' | 'Hard' | 'Complaint'
warmup_status: 'Not Started' | 'In Progress' | 'Active' | 'Paused' | 'Failed'
campaign:      'Draft' | 'Scheduled' | 'Sending' | 'Paused' | 'Completed' | 'Archived'
audit_status:  'Success' | 'Failure'
activity_kind: 'None' | 'Email Sent' | 'Email Received' | 'Deal Won' | 'Deal Lost'
growth_signal_kind: 'Growing' | 'Stable' | 'Declining'
```

**Bad — do not do this:**

```ts
status: 'active' | 'inactive'                    // snake/lower; FE needs to capitalize
role:   'ADMIN' | 'OPERATOR'                     // SCREAMING_SNAKE; FE needs to title-case
stage:  'proposal_sent'                          // underscores; FE needs to humanize
industry: { value: 'tech', label: 'Technology' } // dual-field hack; the value IS the label
```

**What this changes:**

- **Drizzle pgEnum values are Title Case strings.** `pgEnum('industry', ['Technology', 'Healthcare', 'Finance', 'Logistics', 'Other'])`. Postgres handles spaces and mixed case fine.
- **Zod enums in `packages/contracts` are Title Case.** `z.enum(['Active', 'Inactive', 'Pending'])`. The inferred type IS the display label.
- **Spaces are legal.** `"In Progress"`, `"Proposal Sent"`, `"Email Sent"`. TypeScript string literal types, Postgres enums, and JSON all preserve them.
- **Numeric ranges stay as ranges.** `"1-10"`, `"51-200"`, `"1000+"` — not word-based, render naturally; no conversion needed.
- **Discriminator `kind` fields in discriminated unions are Title Case too.** `last_activity: { kind: 'Email Sent', at, label }` — `kind` is on the wire, so it follows the rule. Switch statements still work: `switch (activity.kind) { case 'Email Sent': ... }`.
- **The label-map pattern collapses for simple enums.** Where you'd have `INDUSTRY_LABELS = { tech: 'Technology', ... }` and `industry: { value, label }`, you now just have `industry: 'Technology'`. One string, no map.
- **Complex enums keep `{ kind, label }`** — when the label needs computed context (`growth_signal.label = "+12% YoY"`), the structure stays, but `kind` is Title Case.

**Storage caveat — values are case-sensitive.** Postgres enum values, Drizzle table inserts, query filters, all match exactly. `where: eq(companies.status, 'Active')` works; `where: eq(companies.status, 'active')` doesn't. The contract IS the canonical value; everything else conforms.

## Target stack

- **Nest.js 10+**, TypeScript strict, Node 20+
- **PostgreSQL 17** + **TimescaleDB** extension
- **Drizzle ORM** + `drizzle-kit` for migrations
- **Redis 7+** for caching (`cache-manager`) and queues (`BullMQ`)
- **BullMQ** for queues, workers, and crons
- **CASL** (`@casl/ability`) for authorization
- **`nestjs-zod`** — DTOs and OpenAPI from `packages/contracts` schemas
- **JWT** with refresh-token rotation, `argon2` for password hashing
- **Pino** (`nestjs-pino`) for structured logging
- **Prometheus** via `@willsoto/nestjs-prometheus`
- **`@nestjs/config`** with Zod-validated env

## The six-phase pipeline

```
Phase 1: Domain Inventory     → Entities (regular vs hypertable), view shapes, queues, crons, abilities.
Phase 2: Module Planning      → Monorepo layout, modules, presenter shapes. User-confirmation gate.
Phase 3: Scaffolding          → pnpm workspace, Turbo, apps/api scaffold, infra modules, Drizzle init.
Phase 4: Auth + Tenancy       → JWT, refresh, workspace context, CASL abilities, @Audit decorator.
Phase 5: Module Generation    → contracts → schema (Drizzle) → presenter → service → controller → tests.
Phase 6: Async Layer          → Queues, workers, crons, rate limiters, @Audit on jobs.
```

Phase 2 has a mandatory user-confirmation gate.

---

## Phase 1 — Domain inventory

**Goal:** Catalog every entity, view shape, queue, cron, and ability the backend needs.

For each entity, decide regular table vs hypertable. For each entity, write the **view shape** the frontend will receive (not the DB row — the rich, denormalized, computed-fields-included shape). For each queue: name, producer, concurrency, rate limits, retries. For each cron: name, schedule, idempotency requirement. For each ability: subject, actions, conditions.

Output: `INVENTORY.md`.

---

## Phase 2 — Module planning (user-confirmation gate)

Show the user the monorepo layout, modules, hypertables, queues, crons, CASL abilities. Wait for sign-off before any code generation.

---

## Phase 3 — Scaffolding

See `references/monorepo-setup.md` and `references/scaffolding.md`. Two-step: monorepo first, then `apps/api`.

---

## Phase 4 — Auth + tenancy + CASL + audit

See `references/auth-casl.md` and `references/audit-logging.md`.

Pieces:
- JWT issuance/refresh, argon2 hashing
- `JwtAuthGuard` (verifies token, sets `req.user`)
- `WorkspaceContextInterceptor` (sets `req.workspace` + AsyncLocalStorage workspace context)
- `AbilityFactory` (builds CASL abilities from user roles + workspace)
- `@CheckAbility(action, subject)` decorator + `PoliciesGuard`
- `@Audit({ action, subject })` decorator + `AuditInterceptor` + audit-write queue

**Critical test:** cross-workspace isolation. A request from workspace A must return **404** (not 403, not 200) when reading workspace B's resources.

---

## Phase 5 — Module-by-module generation

See `references/module-structure.md` and `references/view-presenter.md`.

Canonical order within a module:

```
1. contract  — Zod schemas + view types in packages/contracts/<feature>.ts
2. schema    — Drizzle table definitions in apps/api/src/db/schema/<feature>.ts
3. presenter — toView() mapper (DB row → view shape) in modules/<feature>/<feature>.presenter.ts
4. service   — Business logic. Calls presenter before returning. Decorated with @Audit.
5. controller — Thin HTTP layer. Guards: JWT, Policies, Throttle. Decorated with @CheckAbility.
6. tests     — Unit (service) + integration (controller) + cross-workspace isolation test
```

**No service method returns a DB row directly. Every response goes through a presenter.** This is what enforces the view-shape contract.

---

## Phase 6 — Async layer

See `references/bullmq-queues.md`.

Per queue: producer service + worker class + rate limiter + event listeners. Workers run in a separate process (`apps/api/src/worker.ts`). Crons are BullMQ repeatable jobs registered at bootstrap.

---

## Validation checklist

- [ ] Monorepo builds — `pnpm turbo build` succeeds
- [ ] `pnpm typecheck` passes everywhere
- [ ] `pnpm lint` passes (zero warnings)
- [ ] `drizzle-kit migrate` runs cleanly
- [ ] TimescaleDB hypertables created (`SELECT * FROM timescaledb_information.hypertables`)
- [ ] `/health` returns 200 with DB + Redis + Queue checks green
- [ ] **Cross-workspace isolation test passes** (workspace A reading workspace B → 404)
- [ ] **CASL ability test passes** (a viewer cannot perform manage actions)
- [ ] **Audit decorator test passes** (every mutation produces an audit_logs row)
- [ ] **View-shape contract test passes** (responses contain no `undefined`; every count is a number; every variation is a tagged union)
- [ ] No `process.env.X` outside the config module
- [ ] Logs are JSON, include `requestId` and `workspaceId`
- [ ] OpenAPI docs (`/docs`) render every endpoint
- [ ] `apps/web` imports schemas from `@<scope>/contracts` (no local copies)

---

## Reference files

| File | When to read |
|---|---|
| `references/monorepo-setup.md` | Phase 3 (workspace + Turbo + shared packages) |
| `references/scaffolding.md` | Phase 3 (apps/api setup, infra modules, Drizzle init) |
| `references/module-structure.md` | Phase 2 (planning), Phase 5 (per-module layout) |
| `references/drizzle-timescaledb.md` | Phase 3 (Drizzle + Timescale init), Phase 5 (schemas), hypertable work |
| `references/view-presenter.md` | Phase 5 (every module's presenter — enforces the view-shape contract) |
| `references/auth-casl.md` | Phase 4 (JWT + CASL abilities) |
| `references/audit-logging.md` | Phase 4 (@Audit decorator + interceptor + hypertable) |
| `references/validation.md` | Phase 5 (DTOs from shared contracts) |
| `references/error-handling.md` | Phase 3 (global filter), Phase 5 (typed errors) |
| `references/bullmq-queues.md` | Phase 6 (queues, workers, crons) |
| `references/caching.md` | Phase 5 (per-module caching) |
| `references/observability.md` | Phase 3 (logger + metrics + Prometheus), production review |

---

## Common pitfalls

**P1 — Returning DB rows directly.** Every response goes through a presenter. If a service method returns the Drizzle query result, that's a bug — it should be the view shape after `toView(row)`.

**P2 — Optional fields in view types.** Frontend will need `?.` to defend. Fix the contract — make it nullable + explicit, default it, or use a discriminated union.

**P3 — Workspace leak via Drizzle.** Drizzle has no Prisma-style middleware. Use the `tenantDb()` wrapper that injects `workspace_id` filters; never use the raw `db` client in feature services.

**P4 — CASL skipped for "obviously authorized" endpoints.** Apply `@CheckAbility` everywhere — even `GET /me`. Easy guard, free audit trail.

**P5 — Forgetting `@Audit` on mutations.** Every state-changing method needs it. If missing, compliance breaks silently.

**P6 — Audit logs as a regular table.** They balloon to hundreds of millions of rows. Hypertable with retention + compression policies.

**P7 — Hand-rolling RBAC instead of CASL.** Six months later you'll be re-implementing CASL badly. Use it from day one.

**P8 — One process for API and workers.** A slow AI job blocks HTTP requests. Separate `apps/api/src/main.ts` (HTTP) and `apps/api/src/worker.ts` (BullMQ consumer).

**P9 — Skipping the cross-workspace test.** This is THE test that proves tenancy works. Write it before any feature module.
