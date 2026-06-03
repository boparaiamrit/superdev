# Design — Laravel backend option for superdev

- **Date:** 2026-06-03
- **Status:** Approved (brainstorming → spec)
- **Author:** Amritpal Singh Boparai (with Claude)
- **Scope:** Add Laravel as a first-class backend alternative to the existing Nest.js backend across the `superdev` plugin, including a build skill, a serverless deploy skill, a parallel module-builder agent, and orchestrator ("container") integration that asks the operator to choose the backend stack.

---

## 1. Goal & motivation

`superdev` currently builds the backend half of every full-stack monorepo with **one** stack: `nestjs-enterprise-backend` (Nest.js + Postgres 17 + TimescaleDB + Drizzle + Redis/BullMQ + CASL). The `prd-design-build-orchestrator` ("the container") hardcodes that choice — its `backend-module-builder` agent and `contracts-author` agent are Nest/Zod-specific.

We want a **second backend option: Laravel** (latest, **13.x**), deployed **serverless via Bref**, on the **CockroachDB free tier**, with **database-backed sessions/cache** (no Redis) and **SQS** queues. When the orchestrator reaches the backend-build step it must **ask the operator: "Laravel or Nest.js?"** and route accordingly.

The Laravel variant **preserves every non-negotiable architectural commitment** of the Nest skill; it only changes the *mechanism* where the new runtime/infra constraints demand it.

---

## 2. Decisions locked during brainstorming

| # | Decision | Choice |
|---|---|---|
| D1 | Integration depth | **Full integration** — 2 skills + 1 agent + orchestrator selection gate + stack-aware contracts/bootstrap + docs |
| D2 | Contract sharing with the Next.js frontend | **`spatie/laravel-data` → `php artisan typescript:transform` → TS into `packages/contracts`** (PHP is upstream source of truth; the Data class is *also* the response presenter) |
| D3 | Audit logging | **Faithful `#[Audit]` PHP attribute** + `AuditManager` → SQS `AuditWrite` job → RANGE-partitioned `audit_logs` table + scheduled prune (mirrors Nest `@Audit` semantics) |
| D4 | DB driver | **Stock framework-native `pgsql` connection only.** No third-party CockroachDB Laravel package (no `ylsideas/cockroachdb-laravel`). CockroachDB is Postgres-wire-compatible; CRDB quirks handled at the app layer. |
| D5 | Laravel version | **Laravel 13.x** (released 2026-03-17, PHP 8.3+). Minimal breaking changes from 12; ships expanded first-party PHP attributes (`#[Authorize]`, `#[Middleware]`, `#[Tries]`, `#[Backoff]`, `#[Timeout]`) that fit our `#[Audit]`/policy approach. |
| D6 | Deploy tool | **OSS Serverless (`osls`)** as default (free, open-source drop-in; the original Serverless Framework is now licensed). **Bref Cloud (`bref deploy`)** documented as the simpler managed alternative. |
| D7 | FE runtime validation | **Types-only** (compile-time TS). No FE Zod runtime parsing — view-shape is enforced server-side by laravel-data + a Pest "no-null" test. Optional Zod-emitter documented as an add-on. |
| D8 | Asset/HTML handling | A **deployer responsibility**: `laravel-bref-deploy` copies `public/` HTML + static assets to **S3 + CloudFront** (Lambda FS is read-only except `/tmp`). The build skill does not own this. |
| D9 | Database design philosophy | **Reference-field model — no hard FKs, no cascade, no delete-through-join.** Relationships are plain reference columns (`workspace_id`, `company_id`) resolved in application code. (Note: current CockroachDB *does* support SELECT joins, `DELETE … USING`, and `UPDATE … FROM`, so this is a stylistic choice, not a constraint workaround.) |

---

## 3. Architectural commitment mapping (Nest → Laravel)

The Nest skill defines six "non-negotiable" commitments plus cross-cutting infra. Each maps as follows:

| Commitment | Nest.js mechanism | **Laravel mechanism** | Divergence |
|---|---|---|---|
| 1. Monorepo + single-source shared contract | Hand-written Zod in `packages/contracts`, imported by both apps | `apps/api` (Laravel, composer) + `apps/web` (Next.js, pnpm) + `packages/contracts` (**generated** TS). laravel-data classes upstream → `typescript:transform` emits TS. | Direction reversed (PHP upstream; backend can't import TS) |
| 2. View-shape contract (no FE `?.`/`??`) | Presenter classes (`toView`) | **`spatie/laravel-data` objects** as presenter; eager-load relations + `withCount()` so counts default to 0; build labels & discriminated-union `kind` payloads in the Data class; dates → ISO strings. No controller returns a model/array directly. | Mechanism swap (same rule) |
| 3. ORM | Drizzle (TS schema, generated migrations) | **Eloquent** + Laravel migrations/factories/seeders; `casts()` for enums/JSON | Stack swap |
| 4. Fine-grained authz (CASL) | CASL abilities + `@CheckAbility` + `PoliciesGuard` | **Policies/Gates + `spatie/laravel-permission` v8** (DB-backed roles/permissions); enforced via Laravel 13 `#[Authorize(...)]` controller attribute; conditions (incl. workspace match) live in policy methods. Authorize **every** endpoint incl. `GET /me`. | Engine swap (same model: roles are an input, policy resolves) |
| 5. Audit decorator → durable sink | `@Audit` + interceptor → BullMQ → Timescale hypertable | **`#[Audit(action, subject)]` attribute** read by reflection in `AuditManager`; times the action, captures workspace/user/request_id/ip + Success/Failure + duration_ms; dispatches **SQS `AuditWrite`** job → **RANGE-partitioned `audit_logs`** table; scheduled **prune** command replaces Timescale retention/compression. | Transport + sink diverge; semantics preserved |
| 6. Title Case enums (DB = wire = UI label) | Drizzle `pgEnum` + `z.enum` | **PHP 8.1 string-backed enums** (`enum CompanyStatus: string { case ProposalSent = 'Proposal Sent'; }`) + Eloquent `casts()`. `->value` is the canonical Title-Case string; emitted TS union is identical. STRING columns (not native PG enum types) to avoid CRDB cross-type-cast friction. | **None — preserved verbatim** |
| 7. Multi-tenant workspace isolation + cross-workspace 404 | `tenantDb()` wrapper injects `workspace_id` | **`BelongsToWorkspace` trait + Eloquent global scope** auto-filters every tenant-scoped query; middleware resolves current workspace from the authed user/token. Cross-workspace read → empty result → `findOrFail()` → **404**. Mandatory cross-workspace 404 Pest test retained. | Improved (Eloquent has the middleware Drizzle lacked) |
| Infra (Docker: PG+Timescale+Redis) | All deps in Docker | **Prod = managed serverless** (CockroachDB Cloud over public internet, SQS, Lambda, S3/CloudFront, SSM; **no VPC**). **Local dev = Docker single-node CockroachDB** for parity; DB-backed cache/sessions; SQS via local emulation or a real dev queue. | Heavily diverged |

---

## 4. Target stack (Laravel variant)

- **Framework:** Laravel **13.x**, PHP **8.3+** (deploy on Bref `php-84-fpm`).
- **AI tooling:** **Laravel Boost** (`composer require laravel/boost --dev` → `php artisan boost:install`) — MCP server (`php artisan boost:mcp`) + version-matched guidelines + skills. Generated `.mcp.json`/`CLAUDE.md`/`AGENTS.md`/`.ai/*` are **gitignored**; team overrides live in `.ai/guidelines/*`.
- **DB:** **CockroachDB serverless free tier** (5 GiB + 50M RUs/mo) via **stock `pgsql`** connection (port 26257, `defaultdb`, `sslmode=verify-full`, serverless `cluster` routing via connection options).
- **ORM:** **Eloquent** + migrations/factories/seeders; UUID PKs via `gen_random_uuid()`.
- **Presenter + contract:** **`spatie/laravel-data` ^4** (verify Laravel 13 support; bump if a newer major is required) → **`spatie/laravel-typescript-transformer` ^3.2**, `php artisan typescript:transform` into `packages/contracts/src`.
- **Validation:** laravel-data `validation()` (one class = input rules + response shape + TS), backed by FormRequests where needed.
- **AuthN:** **Laravel Sanctum** personal-access tokens (cross-domain SPA via `Authorization` header).
- **AuthZ:** Policies/Gates + **`spatie/laravel-permission` ^8** (PHP 8.3+, supports L12/13); `#[Authorize]` attribute on controllers.
- **Audit:** custom `#[Audit]` attribute + `AuditManager` + SQS `AuditWrite` job + partitioned `audit_logs`. (`spatie/laravel-activitylog` explicitly **not** used — D3 chose the faithful attribute path.)
- **Cache + Sessions:** **database-backed** (`CACHE_STORE=database`, `SESSION_DRIVER=database`; `cache` + `sessions` tables in CockroachDB). No Redis.
- **Queues:** **SQS** (`QUEUE_CONNECTION=sqs`, `aws/aws-sdk-php`); Bref SQS-worker Lambda. **No Horizon** (Redis-only), no `queue:work` daemon.
- **Scheduler:** Laravel scheduler invoked by **EventBridge** `rate(1 minute)` → console Lambda `schedule:run`.
- **Logging/metrics:** **Monolog JSON** → stderr → CloudWatch; `Log::withContext(['request_id','workspace_id'])`. Metrics via CloudWatch (EMF) rather than a Prometheus endpoint (awkward on Lambda).
- **Testing:** **Pest** feature/unit tests — mandatory **cross-workspace 404**, **40001 retry**, and **no-null view-shape** tests.

---

## 5. CockroachDB compatibility layer (app-level only — no special driver)

Baked into `references/cockroachdb-eloquent.md` and the scaffolding:

1. **UUID primary keys** via `$table->uuid('id')->primary()->default(DB::raw('gen_random_uuid()'))` — no auto-increment `SEQUENCE`. Factories/seeders generate UUIDs; tests must not assume monotonic IDs.
2. **40001 serialization-retry wrapper** — a `DB::transaction($cb, attempts)` helper / middleware with exponential backoff (3–5 attempts) around all write transactions; a dedicated Pest test forces the retry path.
3. **No DB queue driver** (`SKIP LOCKED` unsupported) — moot, we use SQS.
4. **No TimescaleDB** — `audit_logs` is a plain table, **RANGE-partitioned by `occurred_at`**, with a scheduled prune command for retention (replaces hypertable retention/compression).
5. **Additive migrations** — avoid `ALTER COLUMN TYPE` on indexed/constrained columns and never inside a transaction; prefer add-column + backfill + drop.
6. **No full-text search** — use trigram/JSONB inverted indexes or external search if needed.
7. **JSONB** fully supported (alias for JSON) for laravel-data array casts; keep values < 1 MB.
8. **Reference-field model (D9)** — relationships are plain columns, no FK constraints/cascades; orphan cleanup handled in app code (e.g., on workspace/entity deletion). Current CockroachDB supports joins/`DELETE … USING`/`UPDATE … FROM`, so this is a design preference, not a forced workaround.

---

## 6. Skill 1 — `laravel-enterprise-backend`

Recipe skill; mirrors `nestjs-enterprise-backend`'s six-phase structure and "recipe skill" invocation modes (orchestrator-driven, migration-driven, standalone).

**Phases:**

```
Phase 1 — Domain Inventory     entities (regular vs partitioned), view shapes (Data classes),
                               SQS queues, scheduled jobs, permission matrix (roles→abilities)
Phase 2 — Module Planning      monorepo layout, Data/Resource shapes, permissions. USER-CONFIRMATION GATE.
Phase 3 — Scaffolding          laravel new (13.x) → Boost install → pgsql/CockroachDB conn →
                               db cache/session tables → Sanctum → spatie/permission →
                               laravel-data + typescript-transformer → Pest
Phase 4 — Auth + Tenancy       Sanctum tokens, BelongsToWorkspace global scope + workspace middleware,
                               Policies + #[Authorize], #[Audit] attribute + AuditManager + AuditWrite SQS job
Phase 5 — Module Generation    Data (contract) → migration (Eloquent) → model + enum casts →
                               Data-presenter → action/service → controller (#[Authorize]) → Pest tests
Phase 6 — Async Layer          SQS jobs, scheduled commands, audit prune, 40001 retry wrapper
```

Phase 2 has a mandatory user-confirmation gate (same as Nest).

**Canonical per-module order (Phase 5):**
`Data class (contract+presenter) → migration → model(+enum casts) → action/service (#[Audit] on mutations) → controller (#[Authorize]) → Pest tests (presenter no-null, cross-workspace 404, authz negative)`.

**Reference files (≈15):**

| File | Purpose |
|---|---|
| `monorepo-setup.md` | Laravel `apps/api` inside the pnpm/turbo monorepo; the generated-contracts wiring |
| `scaffolding.md` | `laravel new` 13.x, package installs, env, db cache/session tables, boot order |
| `boost-setup.md` | Laravel Boost install, MCP registration, gitignore hygiene, `.ai/guidelines` overrides |
| `cockroachdb-eloquent.md` | stock `pgsql` connection, UUID PKs, 40001 retry, additive migrations, partitioning |
| `laravel-data-contracts.md` | **(most important)** Data classes as presenter + `typescript:transform` emit + Title-Case enum → TS union |
| `view-data-pattern.md` | The "fully-populated view shape" rules; eager-loading; `withCount`; discriminated unions |
| `enums-title-case.md` | PHP string-backed enums, casts, the DB=wire=label rule, anti-patterns |
| `auth-sanctum-permissions.md` | Sanctum tokens, spatie/permission roles, Policies, `#[Authorize]` |
| `multitenancy-global-scope.md` | `BelongsToWorkspace` trait + global scope + workspace middleware + cross-workspace 404 test |
| `audit-attribute.md` | `#[Audit]` attribute, `AuditManager`, `AuditWrite` SQS job, partitioned `audit_logs`, prune |
| `validation.md` | laravel-data `validation()` + FormRequests |
| `error-handling.md` | global exception handling, typed error responses, error-code contract |
| `sqs-queues.md` | jobs, dispatch, idempotency keys, DLQ, retry (transport companion to the deployer skill) |
| `db-cache-sessions.md` | database cache/session config, table migrations, TTL/locking notes, cache-tag invalidation |
| `module-structure.md` | folder layout for a feature module; what each file owns |

**Validation checklist (skill):** `composer install` clean; `php artisan migrate` clean on CockroachDB; `typescript:transform` emits into `packages/contracts`; Pest green incl. cross-workspace 404 + CASL-equivalent negative + no-null view-shape + 40001 retry; `Log` lines are JSON with `request_id`/`workspace_id`; no `env()` outside `config()`; every mutation has `#[Audit]`; every endpoint has `#[Authorize]`.

---

## 7. Skill 2 — `laravel-bref-deploy`

A phased serverless-deploy recipe producing a working `serverless.yml` and AWS topology. **No Nest equivalent** — new skill.

**Deploy topology (3 Lambda functions):**

```
web      runtime php-84-fpm     httpApi event → FPM → public/index.php
worker   runtime php-84         Bref\LaravelBridge\Queue\QueueHandler ← SQS (serverless-lift queue)
artisan  runtime php-84-console one-off commands + EventBridge rate(1 minute) → schedule:run
```

**Key responsibilities:**
- **Install/config:** `composer require bref/bref bref/laravel-bridge --update-with-dependencies` (bridge ≥ 3.0); `php artisan vendor:publish --tag=serverless-config`; `serverless plugin install -n serverless-lift`.
- **Assets/HTML (D8):** build then **copy `public/` HTML + static assets → S3**, serve via **CloudFront** (`ASSET_URL`, always `asset()`); CloudFront invalidation on deploy; presigned S3 URLs for uploads > 4 MB. Lambda FS read-only except `/tmp`.
- **Database connectivity:** CockroachDB serverless over **public internet → no VPC** (avoids NAT cost + ENI cold starts); bounded reserved concurrency to limit DB connection fan-out.
- **Secrets/env:** **AWS SSM Parameter Store** (free) — `APP_KEY`, DB creds, AWS queue config via `${ssm:/app/...}` or runtime `bref-ssm:` prefix; nothing committed.
- **Migrations:** run **before** deploy (`osls bref:cli --args="migrate --force"` / `bref` equivalent), not during boot.
- **Cache/sessions:** database-backed (no `/tmp`, no Redis).
- **Deploy commands:** default **`osls deploy --stage prod`**; document **`bref deploy`** (Bref Cloud) as the managed alternative.
- **Package hygiene:** keep deploy package < 250 MB (audit `aws/aws-sdk-php`); ARM64 for ~20% savings; ≥ 1024 MB memory for `web`.

**Reference files (≈8):**
`serverless-yml.md`, `runtimes-and-functions.md`, `sqs-worker.md`, `scheduler-eventbridge.md`, `storage-s3-cloudfront.md` (owns the asset/HTML copy), `secrets-ssm.md`, `cockroachdb-serverless-connection.md`, `deploy-checklist.md`.

---

## 8. Agent — `laravel-module-builder`

Parallel to `backend-module-builder.md`; one feature module per invocation, designed for parallel wave dispatch by the orchestrator.

- **Frontmatter:** `tools: Read, Write, Edit, Bash`; `model: inherit`; `permissionMode: acceptEdits`; `skills: [laravel-enterprise-backend]`.
- **Owns:** `apps/api/app/Domains/<Feature>/*` (or `app/Models` + `app/Http/Controllers/<Feature>` per chosen module layout), the feature migration, the feature's laravel-data classes (which feed `packages/contracts` via transform), Pest tests.
- **Critical patterns enforced:** Title-Case enums; Data-class-as-presenter (no raw model/array out); `BelongsToWorkspace` scoping; `#[Audit]` on every mutation; `#[Authorize]` on every endpoint; cross-workspace 404 + authz-negative + no-null Pest tests.
- **After writing:** `php artisan typescript:transform`; `composer test`/`php artisan test --filter=<Feature>`; up to 3 fix attempts then report.
- **Strict rules:** don't touch other features; don't hand-author TS contracts (generate them); don't skip the Data presenter / `#[Audit]` / cross-workspace test.

---

## 9. Orchestrator integration — the "container asks the question"

Edits to `prd-design-build-orchestrator` (SKILL.md + relevant references) plus the two shared Phase-B agents.

**9.1 Backend-stack selection gate (new, at Phase A.5).** Right after the EXECUTION_PLAN confirmation gate and before any backend bootstrap/build, if the plan contains backend modules the orchestrator asks via `AskUserQuestion`:

```
Backend stack?
  ● Nest.js   — Postgres 17 + TimescaleDB + Drizzle + Redis/BullMQ + CASL (nestjs-enterprise-backend)
  ● Laravel   — Laravel 13 + CockroachDB + DB cache/sessions + SQS, deployed via Bref (laravel-enterprise-backend + laravel-bref-deploy)
```

The choice is persisted (e.g., `STACK.md` and/or a `backend_stack` field in `EXECUTION_PLAN.md`) so every later phase and any resume reads the same value.

**9.2 Stack-aware routing.** A new row in the skill-routing table and conditionals in the affected phases:

| Phase / agent | Nest.js path | **Laravel path** |
|---|---|---|
| Skill routing | `nestjs-enterprise-backend` | `laravel-enterprise-backend` (build) + `laravel-bref-deploy` (Phase D ship) |
| `contracts-author` (Phase B.2) | author Zod in `packages/contracts/src` | author **laravel-data classes** in `apps/api`; run `typescript:transform` to populate `packages/contracts` |
| `monorepo-bootstrapper` (Phase B.1) | scaffold Nest `apps/api` + Docker PG/Redis | scaffold **Laravel `apps/api`** (composer, Boost, pgsql/CockroachDB, db cache/session tables) + single-node CockroachDB compose for local |
| Module builder (Phase C) | `backend-module-builder` | **`laravel-module-builder`** |
| Deploy (Phase D) | (existing) | invoke **`laravel-bref-deploy`** |

The **frontend half is unchanged** — `design-to-nextjs`, `frontend-modular-architecture`, QA/security/audit skills all consume the generated TS contracts identically regardless of backend stack.

**9.3 Agent install list.** `laravel-module-builder` is added to the auto-discovered agents; the orchestrator's install/expected-count notes are updated to reflect the stack-conditional builder.

---

## 10. Monorepo layout

```
<workspace>/
├── apps/
│   ├── web/                ← Next.js (pnpm workspace package)   — unchanged
│   └── api/                ← Laravel 13 (composer.json; NOT a pnpm package)
│       ├── app/  routes/  database/  config/  tests/
│       └── serverless.yml  (added by laravel-bref-deploy)
├── packages/
│   └── contracts/          ← TS types GENERATED by `php artisan typescript:transform`
│                             (apps/web imports @<scope>/contracts as before)
├── docker-compose.yml      ← single-node CockroachDB (local dev parity)
├── turbo.json              ← gains a `contracts` task shelling to `php artisan typescript:transform`
└── pnpm-workspace.yaml
```

- `apps/api` stays positionally identical to the Nest layout so sibling skills' `apps/api` path assumptions hold.
- Turbo `contracts` task runs the transform before `web` builds (`web` `dependsOn` `contracts`).
- **Alternative considered & rejected:** Laravel in a top-level `api/` outside the workspace — breaks the `apps/api` convention every sibling skill relies on.

---

## 11. Documentation & registration updates

- `plugins/superdev/.claude-plugin/plugin.json` — bump version; update `description` (13 → **15 skills**; mention Laravel/Bref/CockroachDB); add keywords (`laravel`, `bref`, `serverless`, `cockroachdb`, `eloquent`, `sanctum`).
- `plugins/superdev/.codex-plugin/plugin.json` — mirror.
- Top-level `README.md` and `plugins/superdev/README.md` — "What's Inside" table 13 → 15; add the two skills; note the backend-stack choice; update counts/diagrams where they say "11 skills"/"13 skills".
- `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` — refresh description/skill list if they enumerate skills.

---

## 12. Out of scope (YAGNI)

- No migration tooling to convert an existing Nest backend to Laravel (or vice-versa).
- No Laravel **frontend** (Blade/Inertia/Livewire) — the frontend stays Next.js via the existing skills.
- No FE runtime Zod emitter by default (D7) — documented as an optional add-on only.
- No `spatie/laravel-activitylog`, no `ylsideas/cockroachdb-laravel`, no Horizon, no Redis, no VPC/RDS-Proxy.
- No Laravel Vapor path (Bref only, per request).

---

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `spatie/laravel-data` / `typescript-transformer` major-version lag behind Laravel 13 | Skill pins the version that certifies L13 at build time; transform is a build step, not runtime — low blast radius. |
| CockroachDB serverless connection fan-out under Lambda concurrency (no RDS Proxy without VPC) | Bounded **reserved concurrency** on `web`; rely on CockroachDB serverless connection handling; load-test before launch (documented in deploy-checklist). |
| Cold starts (~250 ms p99) | Document optional provisioned concurrency; acceptable default for the free-tier/low-traffic target. |
| Serverless Framework licensing confusion | Default to **`osls`** (free OSS drop-in); document Bref Cloud as alternative. |
| Audit volume vs CockroachDB free-tier storage (5 GiB) | Partition + scheduled prune; deploy-checklist notes offloading to S3/CloudWatch if volume grows. |
| SQS at-least-once + 15-min Lambda cap | Idempotency keys on jobs; DLQ + CloudWatch alarms (no Horizon dashboard). |

---

## 14. File manifest (what gets created / edited)

**New skill — `plugins/superdev/skills/laravel-enterprise-backend/`:** `SKILL.md` + the ≈15 references in §6.

**New skill — `plugins/superdev/skills/laravel-bref-deploy/`:** `SKILL.md` + the ≈8 references in §7.

**New agent:** `plugins/superdev/agents/laravel-module-builder.md`.

**Edited:**
- `plugins/superdev/skills/prd-design-build-orchestrator/SKILL.md` (+ `references/execution-pipeline.md`, `references/agent-definitions.md` as needed) — selection gate + stack-aware routing + agent list.
- `plugins/superdev/agents/monorepo-bootstrapper.md` — stack-aware Laravel scaffold.
- `plugins/superdev/agents/contracts-author.md` — stack-aware laravel-data + transform path.
- `plugins/superdev/.claude-plugin/plugin.json`, `plugins/superdev/.codex-plugin/plugin.json`.
- `README.md`, `plugins/superdev/README.md`.
- `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json` (if they enumerate skills).

---

## 15. Acceptance criteria

1. Operator running the orchestrator with backend modules is **asked Laravel vs Nest.js**, and the choice routes bootstrap, contracts, module-building, and deploy correctly.
2. `laravel-enterprise-backend` standalone produces a Laravel 13 app that: boots on CockroachDB via stock `pgsql`; has DB cache/sessions; passes Pest cross-workspace 404 + authz-negative + no-null view-shape + 40001 retry tests; emits TS contracts into `packages/contracts`; every mutation `#[Audit]`-ed and every endpoint `#[Authorize]`-d.
3. `laravel-bref-deploy` produces a `serverless.yml` with the 3 functions, SQS worker, EventBridge scheduler, S3/CloudFront asset copy, and SSM secrets; documents both `osls deploy` and `bref deploy`.
4. The six non-negotiable commitments are demonstrably preserved (esp. Title-Case enums verbatim and the view-shape "no FE `?.`" contract).
5. Plugin docs/manifests reflect 15 skills and the new Laravel/Bref/CockroachDB capability.
