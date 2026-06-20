# Change spec (v1.6.0) — Laravel backend: drop laravel-data + CockroachDB → API Resources + TimescaleDB

- **Date:** 2026-06-04
- **Status:** Approved (decisions locked)
- **Amends:** `2026-06-03-laravel-backend-option-design.md` (v1.4.0) and `2026-06-04-design-to-laravel-inertia-design.md` (v1.5.0).
- **Scope:** Re-architect the **Laravel backend** stack along two axes the user requested: (1) remove `spatie/laravel-data`; (2) replace CockroachDB with **PostgreSQL + TimescaleDB** (self-managed host). Rewrite the affected skills/agents/docs to v1.6.0.

This is the authoritative brief the rewrite agents read. Where it shows code, reproduce it faithfully (it is illustrative markdown inside skill docs — there is no app in this repo; do not run anything, do not git).

---

## Locked decisions

| # | Decision |
|---|---|
| **D1** | **Drop `spatie/laravel-data`.** Presenter = **Eloquent API Resources** (`Illuminate\Http\Resources\Json\JsonResource`). Validation = **FormRequests**. |
| **D2** | **Drop CockroachDB.** DB = **PostgreSQL + TimescaleDB extension**, via the **stock `pgsql` driver** (no third-party DB package). Host is **self-managed** (Timescale Cloud or self-hosted Postgres+Timescale) reached over the public internet from Bref. **Neon is NOT a target** for this tier (no compression/TSL) — state this in the docs. |
| **D3** | **Contract = hand-written TS, zero new deps.** No `typescript-transformer`, no Scramble. Decoupled Next.js: hand-written TS in `packages/contracts/src/<feature>.ts`. Inertia: hand-written types in `resources/js/types/`. A **contract test** (Pest) asserts the API Resource's `toArray()` matches the documented shape. |
| **D4** | **`audit_logs` = TimescaleDB hypertable** with **native retention + compression policies** (full Nest parity), replacing the CockroachDB RANGE-partitioned table. The bespoke `PruneAuditLogs` command is removed (native `add_retention_policy` replaces it). |
| **D5** | **Reference-field model kept** (user preference): plain reference columns (`workspace_id`, `company_id`), **no FK constraints/cascades**. Eloquent relations + eager-loading (`with`, `withCount`) and joins are allowed for read enrichment; relation integrity is handled in app code. |
| **D6** | **Remove CockroachDB compatibility**: the 40001 serialization-retry wrapper (`CockroachRetry`), "additive-migrations-only," "no `SKIP LOCKED`," and the "UUID-because-no-`SEQUENCE`" rationale. UUID PKs stay as a **preference** (Laravel `HasUuids`), not a constraint — real Postgres sequences are available if a feature wants them. |
| **—** | **Unchanged:** SQS queues, database-backed cache/sessions, Bref serverless deploy, Sanctum (decoupled) / Fortify (Inertia) auth, `spatie/laravel-permission` + Policies + `#[Authorize]`, Title-Case PHP enums, `BelongsToWorkspace` global-scope tenancy + cross-workspace 404, Laravel Boost. |

---

## Canonical patterns (reproduce in the rewritten refs)

### A. Connection — stock pgsql + TimescaleDB (replaces CockroachDB)

```php
// config/database.php — 'connections.pgsql' (standard Postgres; TimescaleDB is just an extension)
'pgsql' => [
    'driver' => 'pgsql',
    'url' => env('DATABASE_URL'),
    'host' => env('DB_HOST', '127.0.0.1'),
    'port' => env('DB_PORT', '5432'),
    'database' => env('DB_DATABASE'),
    'username' => env('DB_USERNAME'),
    'password' => env('DB_PASSWORD'),
    'charset' => 'utf8',
    'search_path' => 'public',
    'sslmode' => env('DB_SSLMODE', 'require'),   // managed host over the public internet
],
```

```php
// first migration: enable the extension (host must support TimescaleDB — Timescale Cloud / self-managed)
DB::statement('CREATE EXTENSION IF NOT EXISTS timescaledb');
```

No `cluster` param, no `ylsideas` package, no `PDO::PGSQL_ATTR_DISABLE_PREPARES` CRDB workaround. Standard Postgres semantics: sequences, joins, `SKIP LOCKED`, real transactions all work.

### B. audit_logs hypertable (replaces partitioned table) — full Timescale, mirrors Nest

```php
// migration (raw SQL via DB::statement)
DB::statement("CREATE TABLE audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    action text NOT NULL, subject text NOT NULL, status text NOT NULL,
    duration_ms int, workspace_id uuid, user_id uuid, request_id text, ip text,
    context jsonb, occurred_at timestamptz NOT NULL DEFAULT now()
)");
DB::statement("SELECT create_hypertable('audit_logs', 'occurred_at')");
DB::statement("CREATE INDEX ON audit_logs (workspace_id, occurred_at DESC)");
// Compression (TSL): compress old chunks
DB::statement("ALTER TABLE audit_logs SET (timescaledb.compress, timescaledb.compress_segmentby = 'workspace_id')");
DB::statement("SELECT add_compression_policy('audit_logs', INTERVAL '7 days')");
// Retention (TSL): drop chunks older than the window (replaces the bespoke prune command)
DB::statement("SELECT add_retention_policy('audit_logs', INTERVAL '180 days')");
```

The `#[Audit]` attribute + `AuditManager` + SQS `AuditWrite` job are unchanged in shape; the job inserts into the hypertable (`DB::table('audit_logs')->insert([...])`). Status values stay Title Case (`Success`/`Failure`). Remove `PruneAuditLogs`.

### C. API Resource presenter (replaces laravel-data Data class)

```php
// app/Domains/Companies/Http/Resources/CompanyResource.php
use Illuminate\Http\Resources\Json\JsonResource;

class CompanyResource extends JsonResource
{
    public function toArray($request): array
    {
        return [
            'id' => $this->id,
            'name' => $this->name,
            'domain' => $this->domain,                 // nullable explicit, never omitted
            'industry' => $this->industry,             // Title-Case enum value = label
            'counts' => [
                'contacts'   => (int) ($this->contacts_count ?? 0),   // withCount(); default 0
                'open_leads' => (int) ($this->open_leads_count ?? 0),
            ],
            'last_activity' => $this->lastActivityPayload(),  // discriminated union { kind, ... }
            'created_at' => $this->created_at->toIso8601String(),
            'updated_at' => $this->updated_at->toIso8601String(),
        ];
    }
}
```

```php
// controller — NEVER returns a model/array directly; eager-load + withCount first
public function index()
{
    return CompanyResource::collection(
        Company::query()->withCount(['contacts', 'leads as open_leads_count'])->paginate()
    );
}
```

Rule (same view-shape discipline as before): exhaustive fields, counts default 0, discriminated unions for variants, ISO dates, nullable explicit — so the frontend never needs `?.`/`??`.

### D. Hand-written TS contract + contract test (replaces typescript:transform)

```ts
// packages/contracts/src/companies.ts  (decoupled Next.js)   |   resources/js/types/companies.ts (Inertia)
export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'
export interface CompanyView {
  id: string
  name: string
  domain: string | null
  industry: Industry
  counts: { contacts: number; open_leads: number }
  last_activity: { kind: 'None' } | { kind: 'Email Sent'; at: string; label: string }
  created_at: string
  updated_at: string
}
```

```php
// tests/Feature/CompanyContractTest.php (Pest) — locks the Resource to the documented contract
it('CompanyResource matches the published contract shape', function () {
    $company = Company::factory()->create();
    $array = (new CompanyResource($company->loadCount('contacts')))->toArray(request());

    expect($array)->toHaveKeys(['id','name','domain','industry','counts','last_activity','created_at','updated_at'])
        ->and($array['counts']['contacts'])->toBeInt()
        ->and($array['last_activity']['kind'])->toBeString();
    expect(json_encode($array))->not->toContain('null,'); // spot-check required fields aren't null
});
```

No codegen pipeline: the TS is authored by hand and kept in lockstep with the Resource; the contract test is the guard.

### E. Reference-field migrations (no hard FKs — kept)

```php
Schema::create('companies', function (Blueprint $table) {
    $table->uuid('id')->primary();                 // HasUuids trait fills it; sequences also available now
    $table->uuid('workspace_id')->index();         // reference column — NO ->constrained(), NO cascade
    $table->string('name');
    $table->timestampsTz();
});
```

Eloquent relations (`belongsTo`/`hasMany`) are still declared for eager-loading reads; there is just no DB-level FK constraint. Joins/`withCount` are fine (real Postgres).

---

## File-by-file changes

### `skills/laravel-enterprise-backend/`
- **Rename** `references/cockroachdb-eloquent.md` → `references/postgres-timescale-eloquent.md`; rewrite to pattern A + B + E (stock pgsql, TimescaleDB extension + hypertables, reference-field migrations, UUID-as-preference). Remove CockroachRetry / 40001 / additive-only / no-SKIP-LOCKED.
- **Rename** `references/laravel-data-contracts.md` → `references/api-resources.md`; rewrite to pattern C + D (JsonResource presenter + hand-written TS contract + contract test). Remove laravel-data + typescript-transformer.
- **Rewrite** `references/view-data-pattern.md` → API Resources (eager-load + withCount; the no-`?.` discipline; presenter test).
- **Rewrite** `references/audit-attribute.md` → hypertable sink (pattern B); keep `#[Audit]`/`AuditManager`/SQS job; drop `PruneAuditLogs` (native retention).
- **Rewrite** `references/validation.md` → FormRequests (drop laravel-data `validation()`).
- **Rewrite** `references/module-structure.md` → `Http/Resources/` (not `Data/`); per-feature layout.
- **Update** `references/scaffolding.md` → composer deps remove `spatie/laravel-data` + `spatie/laravel-typescript-transformer` (+ any cockroach); DB = Postgres+Timescale; enable extension; keep Sanctum/spatie-permission/Boost/Pest.
- **Update** `references/monorepo-setup.md` → contract is hand-written TS in `packages/contracts` (no `typescript:transform` task / no Turbo `contracts` task that shells to artisan); both apps still consume `@<scope>/contracts`.
- **Update** `references/enums-title-case.md` → remove typescript-transformer; enums appear as hand-written TS unions; PHP string-backed enums + Eloquent `casts()` unchanged.
- **Update** `references/inertia-variant.md` → remove the "laravel-data may still be used server-side" line; presenter is API Resources for JSON paths (Inertia still passes props directly).
- **Update** `references/db-cache-sessions.md` → wording CockroachDB → Postgres+TimescaleDB; database-backed cache/sessions unchanged.
- **Update** `references/multitenancy-global-scope.md` → remove any CockroachDB note; reaffirm reference-field model; global scope + 404 test unchanged.
- **Update** `references/sqs-queues.md` → note DB queue driver is technically possible on Postgres now, but SQS remains the choice for the serverless/Bref deploy.
- **Rewrite** `SKILL.md` → frontmatter description (Postgres+TimescaleDB, API Resources, hand-written contract; drop CockroachDB/laravel-data); commitments (ORM/DB/presenter/contract/audit); target stack; **delete** the "CockroachDB compatibility" section; reference-table renames (postgres-timescale-eloquent, api-resources); pitfalls updated.

### `skills/laravel-bref-deploy/`
- **Rename** `references/cockroachdb-serverless-connection.md` → `references/postgres-timescale-connection.md`; rewrite (managed Postgres+Timescale over public internet, `sslmode`, no VPC, bounded reserved concurrency). Note the host must support the TimescaleDB extension.
- **Update** `SKILL.md`, `references/serverless-yml.md` (env `DATABASE_URL` → Postgres+Timescale), `references/deploy-checklist.md` (migrate enables the extension; smoke-test hypertable) — scrub CockroachDB.

### `skills/design-to-laravel/`
- Scrub any `spatie/laravel-data` mention (the Inertia path already hand-writes `resources/js/types`); confirm no CockroachDB references. Likely tiny.

### Agents
- `agents/contracts-author.md` (Laravel branch) → author **API Resources + hand-written TS** in `packages/contracts` (decoupled) / `resources/js/types` (Inertia); drop laravel-data + `typescript:transform`.
- `agents/laravel-module-builder.md` → API Resources presenter; Postgres+Timescale; audit hypertable; reference-field migrations; remove `CockroachRetry`/`gen_random_uuid`-as-workaround/laravel-data.
- `agents/inertia-module-builder.md` → already hand-written types; scrub any laravel-data mention (likely none).

### Docs / manifests → v1.6.0
- `plugin.json` ×2: version 1.5.0 → **1.6.0**; description (CockroachDB → Postgres+TimescaleDB; laravel-data → API Resources; "hand-written contracts"); keywords add `postgresql`, `timescaledb`, drop reliance on `cockroachdb` (keep or remove `cockroachdb` keyword — remove, since no longer used).
- `marketplace.json`, `README.md`, `plugins/superdev/README.md`: update the laravel-enterprise-backend descriptions (Postgres+TimescaleDB, API Resources, hypertable audit); bump version mentions.

---

## Acceptance criteria

1. No occurrence of `spatie/laravel-data`, `typescript-transformer`, `CockroachRetry`, `40001`, `ylsideas`, or "CockroachDB" remains in `skills/laravel-enterprise-backend/`, `skills/laravel-bref-deploy/`, `skills/design-to-laravel/`, or the two Laravel agents — except, at most, a one-line "(was CockroachDB in ≤v1.5)" migration note.
2. `laravel-enterprise-backend` documents: stock `pgsql` + TimescaleDB extension; `audit_logs` hypertable with compression + retention policies; API Resources presenter; hand-written TS contract + contract test; reference-field (no-FK) migrations; UUID PKs as preference.
3. Renamed files exist (`postgres-timescale-eloquent.md`, `api-resources.md`, `postgres-timescale-connection.md`); old files deleted; all SKILL.md reference tables + cross-references point to the new names (no broken links).
4. `plugin-validator` PASS; counts unchanged (16 skills / 51 agents); manifests v1.6.0 valid JSON.
5. Title-Case enums, `BelongsToWorkspace` 404, `#[Audit]`, `#[Authorize]`, SQS, DB cache/sessions, Bref deploy commitments still present and consistent.
