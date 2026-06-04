---
name: laravel-enterprise-backend
description: Build a production-grade Laravel 13 backend on PostgreSQL + TimescaleDB (stock pgsql driver, UUID keys, self-managed host over the public internet), with database-backed cache + sessions (no Redis), SQS queues plus a Bref worker, Laravel Sanctum token auth with multi-tenant workspace isolation via Eloquent global scopes, spatie/laravel-permission + Policies for fine-grained authorization, Eloquent API Resources (JsonResource) as response presenters with FormRequests for validation, a hand-written TypeScript contract in packages/contracts guarded by a Pest contract test (no codegen), an #[Audit] PHP attribute that writes structured rows to a TimescaleDB audit_logs hypertable (native compression + retention policies) via an SQS job, PHP 8.1 Title Case string-backed enums (DB value = wire value = UI label, zero conversion code), Monolog JSON logs, and Laravel Boost for AI-assisted development. The backend is the upstream half of a monorepo whose downstream is a Next.js app (built by design-to-nextjs); the frontend renders view-ready data without optional-chaining. Use whenever the user wants to build, scaffold, or extend a Laravel backend; mentions Eloquent, PostgreSQL, TimescaleDB, hypertables, Bref or serverless Laravel, Sanctum, spatie permissions, API Resources, JsonResource, Title Case enums, workspace multi-tenancy, or a Laravel alternative to the Nest.js backend.
---

# Laravel Enterprise Backend

A pipeline for building a production-grade Laravel 13 backend, sized for a monorepo whose frontend is built by the `design-to-nextjs` skill. The skill operates in six phases. Walk them in order; skipping phases produces backends that "work" until they hit real load, a real tenant boundary, or a real audit.

This is the Laravel counterpart to `nestjs-enterprise-backend`. It preserves every non-negotiable architectural commitment of that skill and changes only the *mechanism* where the Laravel runtime / serverless infra demands it. Deployment to AWS Lambda is a **separate** skill — `laravel-bref-deploy` — do not deploy from here.

## How to invoke this skill

This is a **recipe skill** — it provides the patterns and references that builder agents follow.

### Pattern 1 — invoked by the orchestrator (most common)

When `prd-design-build-orchestrator` runs and the operator chooses the **Laravel** backend stack, its `laravel-module-builder` subagent reads this skill's references directly. No separate invocation needed; this skill is installed at `~/.claude/skills/laravel-enterprise-backend/`, and the builder loads `SKILL.md` plus the references relevant to the current module (typically `module-structure.md`, `postgres-timescale-eloquent.md`, `api-resources.md`, `view-data-pattern.md`, `auth-sanctum-permissions.md`, `multitenancy-global-scope.md`, `audit-attribute.md`).

### Pattern 2 — invoked by the migration skill

When a migration skill runs, its extractor agent uses this skill's references the same way — building Laravel domain modules that match what the existing frontend expects from the generated TS contracts.

### Pattern 3 — standalone (backend-only build)

For backend-only builds without the orchestrator (e.g., a Laravel API to serve an existing frontend or to be consumed by a mobile app), start a Claude Code session:

```text
Build a Laravel backend with the architecture patterns from this skill.
Domain: a CRM with companies, contacts, deals.
```

The main session reads this skill's SKILL.md and walks the six phases (inventory, planning, scaffolding, auth+tenancy, module generation, async layer). No subagents required for this path; the main session does the work.

## Architectural commitments (non-negotiable)

These are baked into every phase. Push back on the user only if they explicitly want a different stack — otherwise enforce them.

### 1. Monorepo with a hand-written, test-guarded contract

```text
<workspace>/
├── apps/
│   ├── web/                  ← Next.js frontend (design-to-nextjs skill)
│   └── api/                  ← Laravel 13 backend (this skill; composer, NOT a pnpm package)
├── packages/
│   └── contracts/            ← HAND-WRITTEN TS types in src/<feature>.ts (no codegen)
├── docker-compose.yml        ← single-node Postgres + TimescaleDB for local dev parity
├── pnpm-workspace.yaml
├── turbo.json
└── package.json
```

PHP is upstream: the **API Resource** (`JsonResource`) is the presenter, and its `toArray()` shape is the contract. There is **no codegen pipeline** — the matching TS is **authored by hand** in `packages/contracts/src/<feature>.ts` (decoupled Next.js) or `resources/js/types/` (Inertia), and a **Pest contract test** asserts the Resource's `toArray()` matches the documented TS shape. The backend cannot import TS, so there is one author (PHP Resource) and one consumer (TS), kept in lockstep by the contract test rather than a transformer. The Next.js app imports `@<scope>/contracts`. See `references/monorepo-setup.md`.

### 2. View-shape contract — backend returns view-ready data

Backend always returns data in the shape the frontend renders. **Frontend code never uses `?.` or `??` to defend against missing fields.** This is enforced by the contract and by a Pest "no-null" test.

What this means in practice:

- **No optional fields for data that exists.** A company always has a `name`. The Resource key is non-nullable.
- **Counts and aggregates are always returned, defaulted to 0.** Eager-load with `withCount()` so `contacts: int` is always present, never `contacts?: number`.
- **Related entities are populated, not implied by reference columns.** A response includes `mailbox: MailboxView`, not just `mailbox_id`.
- **Computed labels are built server-side, in the Resource.** Growth signal returns as `{ kind: 'Growing', label: '+12% YoY', delta_pct: 12 }`, not raw numbers for the frontend to compute.
- **Variations are discriminated unions, not optional flags.** "Last activity" is `{ kind: 'None' } | { kind: 'Email Sent', at, label } | { kind: 'Email Received', at, label }`. Never `last_activity_at?: string`.
- **Dates are ISO 8601 strings.** Never raw `Carbon` objects — call `->toIso8601String()`.

The mechanism is an **Eloquent API Resource as presenter**: every entity has a `JsonResource` whose `toArray()` builds the view shape. Controllers return `Resource::collection(...)` or `new Resource($model)` after eager-loading + `withCount()`; they never return a model or array directly. `nullable` is acceptable but must be explicit; "optional/missing" is a smell. This is where transformation work happens — not on the frontend. See `references/api-resources.md` and `references/view-data-pattern.md`.

### 3. Eloquent ORM on PostgreSQL + TimescaleDB

Eloquent is the ORM. Schema is defined in Laravel migrations, models declare `casts()` for enums/JSON, factories/seeders drive tests. **UUID primary keys via the `HasUuids` trait** — a *preference*, not a constraint: this is real Postgres, so sequences/auto-increment are available if a feature wants them. The **reference-field model** is kept: tenant/relation columns (`workspace_id`, `company_id`) are plain indexed columns with **no FK constraints/cascades**; Eloquent relations (`belongsTo`/`hasMany`) are still declared so reads can eager-load (`with`, `withCount`) and join — relation integrity is handled in app code. No Doctrine, no raw query builder for feature code. See `references/postgres-timescale-eloquent.md`.

### 4. Fine-grained authorization — Policies + spatie/laravel-permission

Authorization is not just role checks. `spatie/laravel-permission` provides DB-backed roles and permissions; **Policies/Gates** resolve the actual answer, including the workspace-match condition. Roles are an *input* to the policy, not the resolution itself. Enforcement is via the Laravel 13 `#[Authorize(...)]` controller-method attribute. **Authorize every endpoint, including `GET /me`.** See `references/auth-sanctum-permissions.md`. When the frontend is an **Inertia monolith** (Step A.5c), identity is **Laravel Fortify session** (not Sanctum tokens) while `spatie/laravel-permission` + Policies + `#[Authorize]` stay the same — see `references/inertia-variant.md`.

> Laravel equivalent of Nest's CASL: spatie/laravel-permission + Policies. Do not bring CASL into a Laravel build.

### 5. `#[Audit]` attribute → TimescaleDB hypertable

Every mutating service method is audited. The custom `#[Audit(action, subject)]` PHP attribute (read by reflection in `AuditManager`, or invoked explicitly via `AuditManager::run()`) times the action, captures workspace/user/request_id/ip + a Title-Case `Success`/`Failure` status + `duration_ms`, then dispatches an **SQS `AuditWrite` job** that inserts a row into the **`audit_logs` TimescaleDB hypertable** (`create_hypertable('audit_logs', 'occurred_at')`). Retention and compression are **native Timescale policies** (`add_retention_policy` + `add_compression_policy`) — no bespoke prune command. Every meaningful action becomes searchable with zero per-handler boilerplate. See `references/audit-attribute.md`.

> Laravel equivalent of Nest's `@Audit` → TimescaleDB hypertable, with full parity: same hypertable + compression + retention policies. Do not use `spatie/laravel-activitylog`.

### 6. Title Case for every enum value — no conversion code anywhere

Every enum, status, stage, role, tag, or discriminator stored or transmitted as a string is in **Title Case**. The DB value equals the wire value equals the UI label. There is no `strtoupper()`, no `Str::title()` on enum data, no label lookup map, no snake_case-to-display conversion anywhere in the codebase.

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

- **PHP string-backed enum values are Title Case.** `enum Industry: string { case Technology = 'Technology'; ... }`. The `case Stage::ProposalSent = 'Proposal Sent';` — case name PascalCase, value Title Case with spaces.
- **Eloquent `casts()` use the enum class.** `'industry' => Industry::class`. The `->value` is the canonical Title-Case string; no label maps.
- **The hand-written TS union mirrors the PHP enum.** `packages/contracts/src/<feature>.ts` declares `export type Industry = 'Technology' | 'Healthcare' | ...`, kept in lockstep with the PHP enum and locked by the contract test. The literal type IS the display label.
- **Spaces are legal.** `"In Progress"`, `"Proposal Sent"`, `"Email Sent"` — PHP enum values, STRING columns, and JSON all preserve them.
- **Numeric ranges stay as ranges.** `"1-10"`, `"51-200"`, `"1000+"` — render naturally; no conversion needed.
- **Discriminator `kind` fields in discriminated unions are Title Case too.** `last_activity: { kind: 'Email Sent', at, label }` — `kind` is on the wire, so it follows the rule. `match ($activity->kind) { ActivityKind::EmailSent => ... }` still works.
- **The label-map pattern collapses for simple enums.** Where you'd have `INDUSTRY_LABELS = [...]` plus `{ value, label }`, you now just have `industry: 'Technology'`. One string, no map.
- **Complex enums keep `{ kind, label }`** — when the label needs computed context (`growth_signal.label = "+12% YoY"`), the structure stays, but `kind` is Title Case.

**Storage caveat — values are case-sensitive.** Use plain **`string`/`text` columns** (not native Postgres `ENUM` types) so adding an enum case is a code change, not a migration. Inserts and `where('status', 'Active')` filters match exactly; `where('status', 'active')` does not. The contract IS the canonical value; everything else conforms. See `references/enums-title-case.md`.

### 7. Multi-tenant workspace isolation — global scope + cross-workspace 404

Tenancy is enforced by a `BelongsToWorkspace` trait that adds an **Eloquent global scope** auto-filtering every tenant-scoped query by the current `workspace_id`, plus a middleware that resolves the current workspace from the authed Sanctum user. A cross-workspace read returns an empty result → `findOrFail()` → **404** (existence is never leaked as a 403). A mandatory cross-workspace 404 Pest test proves it. See `references/multitenancy-global-scope.md`.

> Eloquent has the request-scoped middleware Drizzle lacked, so this is *better* than the Nest `tenantDb()` wrapper, not just equivalent.

### 8. Serverless infra — Postgres + TimescaleDB + SQS + DB cache/sessions (no Redis)

Production is a managed Lambda deploy reaching a **self-managed** database over the public internet with **no VPC**:

- **Database:** **PostgreSQL + TimescaleDB** via the **stock `pgsql`** driver — no third-party DB package. The host (Timescale Cloud or self-hosted Postgres+Timescale) must support the TimescaleDB extension; reach it with `sslmode=require`. **Neon is not a target for this tier** — it does not offer Timescale compression/TSL. See `references/postgres-timescale-eloquent.md`.
- **Cache + sessions:** **database-backed** (`CACHE_STORE=database`, `SESSION_DRIVER=database`; `cache` + `sessions` tables in Postgres). Lambda is stateless and Redis needs a VPC, so **no Redis**. See `references/db-cache-sessions.md`.
- **Queues:** **AWS SQS** (`QUEUE_CONNECTION=sqs`). **No Horizon** (Redis-only). A DB queue driver is technically possible on Postgres (real `SKIP LOCKED`), but SQS remains the choice for the serverless/Bref deploy. See `references/sqs-queues.md`.
- **Scheduler:** Laravel scheduler invoked by EventBridge → console Lambda (owned by `laravel-bref-deploy`).
- **TimescaleDB.** `audit_logs` is a **hypertable** with native compression + retention policies — no scheduled prune.

Local dev uses a single-node Postgres + TimescaleDB via `docker-compose.yml` for parity.

## Target stack

- **Laravel 13.x**, PHP **8.3+** (deploys on Bref `php-84-fpm`)
- **PostgreSQL + TimescaleDB** (self-managed host: Timescale Cloud or self-hosted) via the **stock `pgsql`** connection (`sslmode=require` over the public internet) — no third-party DB driver. Enable the extension in the first migration: `CREATE EXTENSION IF NOT EXISTS timescaledb`
- **Eloquent** + migrations/factories/seeders; UUID PKs via the `HasUuids` trait (a preference — real sequences are available); reference-field columns with no FK constraints
- **Presenter + contract:** **Eloquent API Resources** (`JsonResource`) build the view shape; the **contract is hand-written TS** in `packages/contracts/src/<feature>.ts` (decoupled) / `resources/js/types/` (Inertia), with a **Pest contract test** locking `toArray()` to the documented shape — no codegen
- **Validation:** **FormRequests** (`authorize()` + `rules()`)
- **AuthN:** **Laravel Sanctum** personal-access tokens (cross-domain SPA via the `Authorization: Bearer` header)
- **AuthZ:** Policies/Gates + **`spatie/laravel-permission`** (DB-backed roles/permissions); enforced via the Laravel 13 `#[Authorize]` attribute
- **Audit:** custom `#[Audit]` attribute + `AuditManager` + SQS `AuditWrite` job + `audit_logs` **TimescaleDB hypertable** with native compression + retention policies (no `spatie/laravel-activitylog`)
- **Cache + Sessions:** **database-backed** (`CACHE_STORE=database`, `SESSION_DRIVER=database`). No Redis.
- **Queues:** **SQS** (`QUEUE_CONNECTION=sqs`, `aws/aws-sdk-php`); Bref SQS-worker Lambda. No Horizon, no `queue:work` daemon.
- **Logging/metrics:** **Monolog JSON** → stderr → CloudWatch; `Log::withContext(['request_id', 'workspace_id'])`. Metrics via CloudWatch EMF (a Prometheus endpoint is awkward on Lambda).
- **AI tooling:** **Laravel Boost** (`composer require laravel/boost --dev` → `php artisan boost:install`) — dev-only MCP server + version-matched guidelines
- **Testing:** **Pest** feature/unit tests — mandatory **cross-workspace 404**, **contract**, and **no-null view-shape** tests

## The six-phase pipeline

```text
Phase 1: Domain Inventory     → Entities (regular vs hypertable), view shapes (Resource shapes), SQS queues, scheduled jobs, permission matrix (roles→abilities).
Phase 2: Module Planning      → Monorepo layout, Resource shapes + TS contract, permissions. User-confirmation gate.
Phase 3: Scaffolding          → laravel new (13.x) → Boost → pgsql + TimescaleDB conn (enable extension) → db cache/session tables → Sanctum → spatie/permission → Pest.
Phase 4: Auth + Tenancy       → Sanctum tokens, BelongsToWorkspace global scope + workspace middleware, Policies + #[Authorize], #[Audit] + AuditManager + AuditWrite SQS job.
Phase 5: Module Generation    → contract (hand-written TS) → migration (Eloquent) → model + enum casts → API Resource presenter → FormRequest → action/service → controller (#[Authorize]) → Pest tests (incl. contract test).
Phase 6: Async Layer          → SQS jobs, scheduled commands (native hypertable retention/compression handle audit aging).
```

Phase 2 has a mandatory user-confirmation gate (same as Nest).

## Module layout

Each feature is a self-contained domain module at **`apps/api/app/Domains/<Feature>/`** (PSR-4 `App\Domains\<Feature>\`) holding the model, enum(s), `Http/Resources/` (API Resources), `Http/Requests/` (FormRequests), action/service, controller, policy, jobs, and tests. This mirrors Nest's per-feature `modules/<feature>/` folder so a single `laravel-module-builder` agent owns exactly one folder and never touches another feature's files. `routes/api.php` references the feature's controller; the migration lives in `database/migrations/`; the hand-written TS contract lives in `packages/contracts/src/<feature>.ts`. `references/module-structure.md` is the source of truth for the exact file list.

**Canonical per-module order (Phase 5):**
`TS contract (hand-written) → migration → model (+enum casts) → API Resource (presenter) → FormRequest → action/service (#[Audit] on mutations) → controller (#[Authorize]) → Pest tests (contract, presenter no-null, cross-workspace 404, authz negative)`.

---

## Phase 1 — Domain inventory

**Goal:** Catalog every entity, view shape, SQS queue, scheduled job, and permission the backend needs.

For each entity, decide regular table vs hypertable (only `audit_logs` is a hypertable by default). For each entity, write the **view shape** the frontend will receive (not the DB row — the rich, denormalized, computed-fields-included API Resource shape). For each queue: name, producer, idempotency requirement, DLQ. For each scheduled job: name, schedule, idempotency. For the permission matrix: roles → abilities, and the policy conditions (including workspace match).

Output: `INVENTORY.md`.

## Phase 2 — Module planning (user-confirmation gate)

Show the user the monorepo layout, modules, API Resource shapes (and the matching TS contract), SQS queues, scheduled jobs, and the permission matrix. Wait for sign-off before any code generation.

## Phase 3 — Scaffolding

See `references/scaffolding.md`, `references/monorepo-setup.md`, and `references/boost-setup.md`. Two-step: monorepo first, then the Laravel `apps/api` (composer install, Boost, stock `pgsql` + TimescaleDB connection, db cache/session tables, Sanctum, spatie/permission, Pest). PostgreSQL + TimescaleDB specifics — enabling the extension, UUID PKs via `HasUuids`, reference-field (no-FK) migrations, the `audit_logs` hypertable — come from `references/postgres-timescale-eloquent.md`.

## Phase 4 — Auth + tenancy + audit

See `references/auth-sanctum-permissions.md`, `references/multitenancy-global-scope.md`, and `references/audit-attribute.md`.

Pieces:
- Sanctum personal-access token issuance; `auth:sanctum` middleware
- `ResolveWorkspace` middleware (binds `workspace.id` per request from the authed user)
- `BelongsToWorkspace` trait + Eloquent global scope (auto-filters every tenant-scoped query)
- `spatie/laravel-permission` roles/permissions seeded; Policies resolve the answer (incl. workspace match)
- `#[Authorize]` enforcement on every controller method
- `#[Audit]` attribute + `AuditManager` + `AuditWrite` SQS job

**Critical test:** cross-workspace isolation. A request from workspace A must return **404** (not 403, not 200) when reading workspace B's resources.

## Phase 5 — Module-by-module generation

See `references/module-structure.md`, `references/api-resources.md`, `references/view-data-pattern.md`, and `references/validation.md`.

Canonical order within a module:

```text
1. contract    — hand-written TS view types in packages/contracts/src/<feature>.ts (decoupled) / resources/js/types/ (Inertia)
2. migration   — Eloquent migration in database/migrations/ (UUID PK via HasUuids, reference columns/no FK, string enum cols)
3. model       — app/Domains/<Feature>/Models/ with casts() for enums/JSON; BelongsToWorkspace trait
4. resource    — JsonResource presenter in app/Domains/<Feature>/Http/Resources/ (builds the view shape)
5. request     — FormRequest in app/Domains/<Feature>/Http/Requests/ (authorize() + rules())
6. action      — Business logic in Actions/ (or Services/). Mutations carry #[Audit].
7. controller  — Thin HTTP layer in Http/. #[Authorize] on every method. Returns a Resource, never a model.
8. tests       — Pest: contract (toArray() matches the TS shape), presenter no-null, cross-workspace 404, authz-negative
```

**No controller or service method returns an Eloquent model or array directly. Every response goes through an API Resource.** This is what enforces the view-shape contract. The hand-written TS contract is kept in lockstep with the Resource and locked by a Pest contract test — there is no codegen step.

## Phase 6 — Async layer

See `references/sqs-queues.md`.

Per queue: a job implementing `ShouldQueue`, dispatched with `->onQueue(...)`, with an idempotency key (SQS is at-least-once). Jobs stay < 60 s (well under the 15-min Lambda cap). The `audit` queue is one such queue; its `AuditWrite` job inserts into the `audit_logs` hypertable, and **Timescale's native retention + compression policies handle aging — no prune command**. Other scheduled commands are Laravel scheduler entries in `routes/console.php`, run by EventBridge → console Lambda (owned by `laravel-bref-deploy`). No `queue:work` daemon, no Horizon.

---

## PostgreSQL + TimescaleDB notes

This is **standard PostgreSQL** reached through the **stock `pgsql` driver** — no third-party DB package. TimescaleDB is just an extension. The app-level rules below live in `references/postgres-timescale-eloquent.md`:

1. **Enable the extension** in the first migration: `DB::statement('CREATE EXTENSION IF NOT EXISTS timescaledb')`. The host (Timescale Cloud or self-hosted Postgres+Timescale) must support it; Neon is not a target for this tier.
2. **UUID primary keys via the `HasUuids` trait** — a *preference*, not a constraint. This is real Postgres, so sequences/auto-increment are available if a feature wants them; tests must not assume monotonic IDs when `HasUuids` is in use.
3. **Hypertables for time-series.** `audit_logs` is a hypertable (`SELECT create_hypertable('audit_logs', 'occurred_at')`) with native `add_compression_policy` + `add_retention_policy` — no partitioned table, no prune command.
4. **Reference-field model (preference, kept).** Tenant/relation columns (`workspace_id`, `company_id`) are plain indexed columns with **no FK constraints/cascades/delete-through-join**; orphan cleanup is handled in app code. Eloquent relations are still declared, and joins / `with` / `withCount` are fine for read enrichment (real Postgres) — this is a design preference, not a workaround.
5. **Standard Postgres semantics apply.** Real transactions, sequences, `SKIP LOCKED`, full-text search (`tsvector`/GIN) and trigram indexes, and `JSONB` (used for the audit `context` and array casts; keep values < 1 MB) all work normally — no compatibility shims.

## Validation checklist

- [ ] `composer install` clean
- [ ] `php artisan migrate` runs cleanly on Postgres + TimescaleDB (stock `pgsql`, extension enabled, UUID PKs)
- [ ] `audit_logs` hypertable created (`SELECT * FROM timescaledb_information.hypertables`) with compression + retention policies
- [ ] Pest green, including:
  - [ ] **Contract test passes** (each Resource's `toArray()` matches the hand-written TS shape in `packages/contracts`)
  - [ ] **Cross-workspace isolation test passes** (workspace A reading workspace B → 404)
  - [ ] **Authz-negative test passes** (a Viewer cannot perform manage actions → 403)
  - [ ] **No-null view-shape test passes** (responses contain no nulls for required fields; every count is an int; every variation is a tagged union)
- [ ] `Log` lines are JSON and include `request_id` + `workspace_id`
- [ ] No `env()` calls outside `config()`
- [ ] **Every mutation is `#[Audit]`-ed** (produces an `audit_logs` row)
- [ ] **Every endpoint is `#[Authorize]`-d** (incl. `GET /me`)
- [ ] Cache + sessions are database-backed (`cache` + `sessions` tables exist); no Redis
- [ ] `apps/web` imports the hand-written types from `packages/contracts` (no local copies)

---

## Reference files

| File | When to read |
|---|---|
| `references/scaffolding.md` | Phase 3 (`laravel new` 13.x, package installs, env, db cache/session tables, boot order) |
| `references/monorepo-setup.md` | Phase 3 (Laravel `apps/api` in the pnpm/turbo monorepo + generated-contracts wiring) |
| `references/boost-setup.md` | Phase 3 (Laravel Boost install, MCP registration, gitignore hygiene) |
| `references/postgres-timescale-eloquent.md` | Phase 3 (stock pgsql + TimescaleDB connection, enable extension), Phase 5 (UUID PKs via HasUuids, reference-field/no-FK migrations, hypertables) |
| `references/api-resources.md` | Phase 5 (JsonResource-as-presenter + hand-written TS contract + Pest contract test + Title-Case enum → TS union) — most important |
| `references/view-data-pattern.md` | Phase 5 (the fully-populated view-shape rules; eager-loading; `withCount`; discriminated unions) |
| `references/enums-title-case.md` | Phase 5 (PHP string-backed enums, `casts()`, the DB=wire=label rule, anti-patterns) |
| `references/auth-sanctum-permissions.md` | Phase 4 (Sanctum tokens + spatie/permission roles + Policies + `#[Authorize]`) |
| `references/multitenancy-global-scope.md` | Phase 4 (`BelongsToWorkspace` trait + global scope + workspace middleware + cross-workspace 404 test) |
| `references/audit-attribute.md` | Phase 4 (`#[Audit]` attribute + `AuditManager` + `AuditWrite` SQS job + `audit_logs` hypertable + compression/retention policies) |
| `references/validation.md` | Phase 5 (FormRequests — `authorize()` + `rules()`) |
| `references/error-handling.md` | Phase 3 (global exception handling), Phase 5 (typed error responses + error-code contract) |
| `references/sqs-queues.md` | Phase 6 (jobs, dispatch, idempotency keys, DLQ, retry) |
| `references/db-cache-sessions.md` | Phase 3 (database cache/session config + table migrations + cache-tag invalidation) |
| `references/module-structure.md` | Phase 2 (planning), Phase 5 (per-module folder layout — what each file owns) |
| `references/inertia-variant.md` | When the frontend is Inertia (Step A.5c) — Fortify session instead of Sanctum tokens, Inertia props instead of a JSON API, single-app layout |

---

## Common pitfalls

**P1 — Returning an Eloquent model or array directly.** Every response goes through an API Resource. If a controller or service returns the model (or `->toArray()`), that's a bug — it should be `new CompanyResource($model)` / `CompanyResource::collection(...)` after eager-loading + `withCount()`.

**P2 — Optional/missing fields in the view shape.** Frontend will need `?.` to defend. Fix the Resource — make the key nullable + explicit, default counts to 0 via `withCount()`, or use a discriminated union.

**P3 — Workspace leak via a missing global scope.** A model that forgets the `BelongsToWorkspace` trait queries across tenants. Apply the trait to every tenant-scoped model; the global scope auto-filters by `workspace.id`. Never query a tenant model without it.

**P4 — `#[Authorize]` skipped for "obviously authorized" endpoints.** Apply it everywhere — even `GET /me`. Cheap attribute, free audit trail; the Policy also enforces the workspace match.

**P5 — Forgetting `#[Audit]` / `AuditManager::run()` on mutations.** Every state-changing method needs it. If missing, compliance breaks silently.

**P6 — `audit_logs` as a plain table.** It balloons to hundreds of millions of rows. Make it a **TimescaleDB hypertable** (`create_hypertable` on `occurred_at`) with native compression + retention policies — they handle aging automatically, so no prune command is needed.

**P7 — Hand-rolling RBAC instead of spatie/laravel-permission.** Six months later you'll be re-implementing it badly. Use spatie roles/permissions + Policies from day one. (And do not reach for CASL — that's the Nest stack.)

**P8 — One Lambda for web + worker.** A slow SQS job would block HTTP requests. The web FPM function and the SQS worker function are separate Lambdas (see `laravel-bref-deploy`); locally, run the queue worker as a separate process.

**P9 — Skipping the cross-workspace test.** This is THE test that proves tenancy works. Write the cross-workspace 404 Pest test before any feature module; when seeding the *other* workspace's fixtures, set them up with `withoutGlobalScopes()`.
