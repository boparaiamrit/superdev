# Laravel Backend Option — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. When authoring each skill file, also follow `plugin-dev:skill-development` conventions and use `plugin-dev:plugin-validator` for validation gates.

**Goal:** Add Laravel (13.x) as a first-class backend alternative to Nest.js across the `superdev` plugin — a build skill, a Bref serverless deploy skill, a parallel module-builder agent, and orchestrator integration that asks the operator to choose the backend stack.

**Architecture:** Two new recipe skills (`laravel-enterprise-backend`, `laravel-bref-deploy`) mirror `nestjs-enterprise-backend`'s structure and preserve all six non-negotiable commitments, diverging only where CockroachDB / DB-backed cache+sessions / Bref-SQS / Laravel 13 demand it. A new `laravel-module-builder` agent mirrors `backend-module-builder`. The `prd-design-build-orchestrator` gains a Phase A.5 backend-stack selection gate and stack-aware routing for `contracts-author` and `monorepo-bootstrapper`. The frontend half (design-to-nextjs, QA/security/audit) is untouched — it consumes generated TS contracts identically.

**Tech Stack:** Laravel 13.x (PHP 8.3+), stock `pgsql` driver → CockroachDB serverless, `spatie/laravel-data` + `spatie/laravel-typescript-transformer`, Laravel Sanctum, `spatie/laravel-permission`, custom `#[Audit]` attribute, database cache/sessions, AWS SQS, Bref 3.x (`bref/bref` + `bref/laravel-bridge`), OSS Serverless (`osls`) / Bref Cloud, Laravel Boost, Pest. Source spec: `docs/superpowers/specs/2026-06-03-laravel-backend-option-design.md`.

---

## Validation recipes (referenced by tasks; defined once — DRY)

- **VR-1 — SKILL.md frontmatter parses.** From repo root:
  `node -e "const fs=require('fs');const s=fs.readFileSync(process.argv[1],'utf8');const m=s.match(/^---\n([\s\S]*?)\n---/);if(!m)throw new Error('no frontmatter');if(!/\nname:\s*\S/.test('\n'+m[1]))throw 'missing name';if(!/\ndescription:\s*\S/.test('\n'+m[1]))throw 'missing description';console.log('OK frontmatter')" <path-to-SKILL.md>`
  Expected: `OK frontmatter`. Also confirm `name:` equals the skill's directory name.
- **VR-2 — reference links resolve.** For the skill being edited, every `references/<x>.md` named in `SKILL.md`'s reference table exists on disk:
  `for f in $(grep -oE "references/[a-z0-9-]+\.md" plugins/superdev/skills/<skill>/SKILL.md | sort -u); do test -f "plugins/superdev/skills/<skill>/$f" && echo "OK $f" || echo "MISSING $f"; done`
  Expected: every line `OK …`, zero `MISSING`.
- **VR-3 — plugin validates & loads.** Dispatch the `plugin-dev:plugin-validator` agent on `plugins/superdev/`. Expected: no structural errors; new skills/agent discovered. (If the `claude` CLI is available: `claude plugin validate plugins/superdev` as a secondary check.)
- **VR-4 — no broken intra-doc references.** `grep -rEn "nestjs-enterprise-backend|Drizzle|BullMQ|Timescale|Redis" plugins/superdev/skills/laravel-enterprise-backend plugins/superdev/skills/laravel-bref-deploy` should return only intentional comparison mentions (review each hit; there should be no accidental copy-paste of Nest-only tech as if it were the Laravel stack).

Commits use Conventional Commits and end with the trailer:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
Work happens on branch `feat/laravel-backend-option` (already created).

---

## File Structure

**Created — skill 1 `plugins/superdev/skills/laravel-enterprise-backend/`:**
- `SKILL.md` — six-phase pipeline, architectural commitments, reference table (triggering surface)
- `references/scaffolding.md` — `laravel new` 13.x, package installs, env, boot order
- `references/monorepo-setup.md` — Laravel `apps/api` in the pnpm/turbo monorepo + generated-contracts wiring
- `references/boost-setup.md` — Laravel Boost install/MCP/gitignore hygiene
- `references/cockroachdb-eloquent.md` — stock pgsql conn, UUID PKs, 40001 retry, partitioning *(novel)*
- `references/laravel-data-contracts.md` — Data-as-presenter + `typescript:transform` emit *(novel, most important)*
- `references/view-data-pattern.md` — fully-populated view-shape rules
- `references/enums-title-case.md` — PHP string-backed Title Case enums
- `references/auth-sanctum-permissions.md` — Sanctum + spatie/permission + Policies + `#[Authorize]`
- `references/multitenancy-global-scope.md` — `BelongsToWorkspace` trait + global scope + 404 test *(novel)*
- `references/audit-attribute.md` — `#[Audit]` attribute + AuditManager + SQS job + partitioned table *(novel)*
- `references/validation.md` — laravel-data `validation()` + FormRequests
- `references/error-handling.md` — global exception handling + error-code contract
- `references/sqs-queues.md` — jobs, dispatch, idempotency, DLQ
- `references/db-cache-sessions.md` — database cache/session config + tables
- `references/module-structure.md` — `app/Domains/<Feature>/` folder layout

**Created — skill 2 `plugins/superdev/skills/laravel-bref-deploy/`:**
- `SKILL.md` — phased deploy pipeline + reference table
- `references/serverless-yml.md` — full `serverless.yml` blueprint *(novel)*
- `references/runtimes-and-functions.md` — php-84-fpm/php-84/php-84-console functions
- `references/sqs-worker.md` — Bref `QueueHandler` + lift `queue` construct *(novel)*
- `references/scheduler-eventbridge.md` — EventBridge → `schedule:run`
- `references/storage-s3-cloudfront.md` — **HTML/asset copy to S3+CloudFront** (D8) *(novel)*
- `references/secrets-ssm.md` — SSM Parameter Store config
- `references/cockroachdb-serverless-connection.md` — public-internet/no-VPC connection notes
- `references/deploy-checklist.md` — `osls deploy` / `bref deploy`, migrations-before-deploy, package size

**Created — agent:** `plugins/superdev/agents/laravel-module-builder.md`

**Modified:**
- `plugins/superdev/skills/prd-design-build-orchestrator/SKILL.md` — selection gate + routing
- `plugins/superdev/skills/prd-design-build-orchestrator/references/execution-pipeline.md` — stack-aware wave notes (if present)
- `plugins/superdev/agents/monorepo-bootstrapper.md` — stack-aware Laravel scaffold
- `plugins/superdev/agents/contracts-author.md` — stack-aware laravel-data + transform
- `plugins/superdev/.claude-plugin/plugin.json`, `plugins/superdev/.codex-plugin/plugin.json`
- `README.md`, `plugins/superdev/README.md`
- `.claude-plugin/marketplace.json`

---

## PHASE 1 — `laravel-enterprise-backend` skill

### Task 1.1: Skill scaffold + SKILL.md

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/SKILL.md`

- [ ] **Step 1: Create the directory and SKILL.md with this exact frontmatter** (the triggering surface — use verbatim):

```yaml
---
name: laravel-enterprise-backend
description: Build a production-grade Laravel 13 backend on the CockroachDB free tier (stock pgsql driver, UUID keys, 40001 serialization-retry), with database-backed cache + sessions (no Redis), SQS queues plus a Bref worker, Laravel Sanctum token auth with multi-tenant workspace isolation via Eloquent global scopes, spatie/laravel-permission + Policies for fine-grained authorization, spatie/laravel-data classes that act as BOTH response presenters and the single contract source (php artisan typescript:transform emits TS types into packages/contracts for the Next.js frontend), an #[Audit] PHP attribute that writes structured rows to a RANGE-partitioned audit_logs table via an SQS job, PHP 8.1 Title Case string-backed enums (DB value = wire value = UI label, zero conversion code), Monolog JSON logs, and Laravel Boost for AI-assisted development. The backend is the upstream half of a monorepo whose downstream is a Next.js app (built by design-to-nextjs); the frontend renders view-ready data without optional-chaining. Use whenever the user wants to build, scaffold, or extend a Laravel backend; mentions Eloquent, CockroachDB, Bref or serverless Laravel, Sanctum, spatie permissions, laravel-data, API resources, Title Case enums, workspace multi-tenancy, or a Laravel alternative to the Nest.js backend.
---
```

- [ ] **Step 2: Write the SKILL.md body** covering these sections (mirror the structure of `plugins/superdev/skills/nestjs-enterprise-backend/SKILL.md`, translating each to Laravel):
  1. **Intro** — recipe skill; six phases; walk in order.
  2. **How to invoke** — three patterns: (a) orchestrator's `laravel-module-builder` reads references; (b) migration skill; (c) standalone main-session build.
  3. **Architectural commitments (non-negotiable)** — the 8 from spec §3, Laravel-phrased: monorepo+generated-contracts; view-shape via laravel-data; Eloquent; spatie/permission+Policies; `#[Audit]`→partitioned table; **Title Case enums** (copy the Good/Bad examples from the Nest SKILL.md verbatim — they are stack-agnostic); workspace global-scope tenancy; serverless infra (CockroachDB+SQS+DB cache/sessions, no Redis/Timescale).
  4. **Target stack** — the bullet list from spec §4.
  5. **Six-phase pipeline** — the block from spec §6.
  6. **Module layout** — `apps/api/app/Domains/<Feature>/` (spec §6 "Module layout" paragraph, verbatim).
  7. **Per-phase sections** (Phase 1–6) — one short section each, each pointing to the reference file(s) it uses.
  8. **CockroachDB compatibility** — the 8 points from spec §5, with a pointer to `references/cockroachdb-eloquent.md`.
  9. **Validation checklist** — the skill checklist from spec §6.
  10. **Reference files table** — all 15 files with "when to read".
  11. **Common pitfalls** — P1–P9 translated (raw model returned instead of Data; optional fields; workspace leak via missing global scope; authorize skipped; `#[Audit]` forgotten; audit table unpartitioned; hand-rolled RBAC instead of spatie; one Lambda for web+worker; skipping cross-workspace test).

- [ ] **Step 3: Validate** — run **VR-1** on the new SKILL.md. Expected: `OK frontmatter`, `name` == `laravel-enterprise-backend`.

- [ ] **Step 4: Commit**

```bash
git add plugins/superdev/skills/laravel-enterprise-backend/SKILL.md
git commit -m "feat(laravel): add laravel-enterprise-backend SKILL.md

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.2: `references/cockroachdb-eloquent.md` (novel — do early; later refs cite it)

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/cockroachdb-eloquent.md`

- [ ] **Step 1: Author the file** with these sections and the exact code blocks below.

  Section "Connection (stock pgsql, no third-party driver)" — `config/database.php` `pgsql` connection pointed at CockroachDB serverless:

```php
// config/database.php — 'connections' => [ 'pgsql' => [...] ]
'pgsql' => [
    'driver' => 'pgsql',
    'url' => env('DATABASE_URL'),
    'host' => env('DB_HOST', '127.0.0.1'),
    'port' => env('DB_PORT', '26257'),          // CockroachDB default
    'database' => env('DB_DATABASE', 'defaultdb'),
    'username' => env('DB_USERNAME'),
    'password' => env('DB_PASSWORD'),
    'charset' => 'utf8',
    'prefix' => '',
    'prefix_indexes' => true,
    'search_path' => 'public',
    'sslmode' => env('DB_SSLMODE', 'verify-full'),
    'options' => array_filter([
        // CockroachDB Cloud serverless: route to the cluster + pin the CA cert.
        // 'cluster' is passed as a connection option, e.g. via the URL:
        //   postgresql://user:pass@host:26257/cluster-name.defaultdb?sslmode=verify-full&sslrootcert=/path/ca.crt
        \PDO::PGSQL_ATTR_DISABLE_PREPARES => true, // safer with CRDB + pgbouncer-style routing
    ]),
],
```

  Note: document that the serverless `cluster` routing id is carried in `DATABASE_URL` (database name `clustername.defaultdb`) and `sslrootcert` query param; no special Laravel package required.

  Section "UUID primary keys (no SEQUENCE)" — migration + model trait:

```php
// migration
Schema::create('companies', function (Blueprint $table) {
    $table->uuid('id')->primary()->default(DB::raw('gen_random_uuid()'));
    $table->uuid('workspace_id')->index();        // reference column, NOT a FK constraint (D9)
    $table->string('name');
    $table->timestampsTz();
});
```

```php
// app/Concerns/HasUuidPrimaryKey.php
trait HasUuidPrimaryKey
{
    public $incrementing = false;
    protected $keyType = 'string';
}
```

  Section "40001 serialization retry" — a helper used around writes:

```php
// app/Support/CockroachRetry.php
namespace App\Support;

use Illuminate\Support\Facades\DB;
use Throwable;

final class CockroachRetry
{
    /** Retry a write closure on CockroachDB 40001 serialization failures. */
    public static function transaction(callable $callback, int $attempts = 5)
    {
        for ($attempt = 1; ; $attempt++) {
            try {
                return DB::transaction($callback);
            } catch (Throwable $e) {
                if ($attempt >= $attempts || ! self::isSerializationFailure($e)) {
                    throw $e;
                }
                usleep((int) (random_int(50, 150) * 1000 * (2 ** ($attempt - 1)))); // backoff
            }
        }
    }

    private static function isSerializationFailure(Throwable $e): bool
    {
        return str_contains($e->getMessage(), '40001')
            || str_contains($e->getMessage(), 'restart transaction');
    }
}
```

  Section "Additive migrations only" — never `ALTER COLUMN TYPE` on indexed/constrained columns or inside a transaction; prefer add-column + backfill + drop. Reference-field model (D9): no FK constraints/cascades; orphan cleanup in app code.

  Section "Partitioned audit table" — pointer to `audit-attribute.md` for the RANGE-partition DDL.

  Section "What we do NOT use" — explicitly: no `ylsideas/cockroachdb-laravel`, no Redis, no TimescaleDB, no DB queue driver (SKIP LOCKED unsupported — we use SQS).

- [ ] **Step 2: Validate** — confirm PHP fences are balanced and the file is referenced nowhere-broken: `grep -c '```' plugins/superdev/skills/laravel-enterprise-backend/references/cockroachdb-eloquent.md` returns an even number.

- [ ] **Step 3: Commit**

```bash
git add plugins/superdev/skills/laravel-enterprise-backend/references/cockroachdb-eloquent.md
git commit -m "feat(laravel): add cockroachdb-eloquent reference (stock pgsql, UUID, 40001 retry)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.3: `references/laravel-data-contracts.md` (novel — most important)

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/laravel-data-contracts.md`

- [ ] **Step 1: Author the file.** This is the analogue of Nest's `view-presenter.md` + `monorepo-setup.md` contracts section. Sections + exact code:

  "The contract" — laravel-data `Data` class is BOTH the response presenter AND the upstream contract; `php artisan typescript:transform` emits TS into `packages/contracts/src`; the Next.js app imports the generated types. Frontend renders directly — no `?.`/`??`.

  Install/config:

```bash
composer require spatie/laravel-data spatie/laravel-typescript-transformer
php artisan vendor:publish --provider="Spatie\LaravelData\LaravelDataServiceProvider"
php artisan vendor:publish --tag=typescript-transformer-config
```

```php
// config/typescript-transformer.php — key settings
'auto_discover_types' => [ app_path() ],
'collectors' => [ Spatie\LaravelData\Support\TypeScriptTransformer\DataTypeScriptCollector::class ],
'transformers' => [ Spatie\LaravelData\Support\TypeScriptTransformer\DataTypeScriptTransformer::class ],
// Emit into the monorepo shared contracts package consumed by apps/web:
'output_file' => base_path('../../packages/contracts/src/generated.ts'),
```

  A view Data class (the presenter) — fully-populated, Title-Case enum, discriminated union, ISO dates:

```php
// app/Domains/Companies/Data/CompanyData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\TypeScriptTransformer\Attributes\TypeScript;
use App\Domains\Companies\Enums\Industry;

#[TypeScript]
class CompanyData extends Data
{
    public function __construct(
        public string $id,
        public string $name,
        public ?string $domain,            // nullable is explicit; never "optional/missing"
        public Industry $industry,         // Title Case PHP enum -> TS union, value = label
        public CompanyCountsData $counts,  // always present, defaulted to 0 server-side
        public LastActivityData $last_activity, // discriminated union, kind is Title Case
        public string $created_at,         // ISO 8601 string, not Carbon
        public string $updated_at,
    ) {}

    public static function fromModel(\App\Domains\Companies\Models\Company $c): self
    {
        return new self(
            id: $c->id,
            name: $c->name,
            domain: $c->domain,
            industry: $c->industry,
            counts: new CompanyCountsData(
                contacts: (int) ($c->contacts_count ?? 0),
                open_leads: (int) ($c->open_leads_count ?? 0),
                won_deals: (int) ($c->won_deals_count ?? 0),
            ),
            last_activity: LastActivityData::fromModel($c),
            created_at: $c->created_at->toIso8601String(),
            updated_at: $c->updated_at->toIso8601String(),
        );
    }
}
```

  Controller returns the Data class (never the model):

```php
return CompanyData::collect(
    Company::query()->withCount(['contacts','openLeads as open_leads_count'])->paginate(),
    \Spatie\LaravelData\PaginatedDataCollection::class,
);
```

  The Turbo wiring (so the transform runs before web builds) — pointer to `monorepo-setup.md`.

  Title-Case enum → TS: show `Industry` PHP enum (pointer to `enums-title-case.md`) and the emitted TS union `export type Industry = 'Technology' | 'Healthcare' | ...`.

  Anti-patterns: returning a model/array; `.optional()`-style nullable-by-omission; hand-editing `packages/contracts` generated files; computing labels on the frontend.

- [ ] **Step 2: Validate** — even number of code fences (`grep -c '```' …`).
- [ ] **Step 3: Commit** `feat(laravel): add laravel-data-contracts reference (Data-as-presenter + TS emit)`.

---

### Task 1.4: `references/multitenancy-global-scope.md` (novel)

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/multitenancy-global-scope.md`

- [ ] **Step 1: Author** with exact code:

```php
// app/Concerns/BelongsToWorkspace.php
namespace App\Concerns;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;

trait BelongsToWorkspace
{
    protected static function bootBelongsToWorkspace(): void
    {
        static::addGlobalScope('workspace', function (Builder $builder) {
            if ($wid = app()->bound('workspace.id') ? app('workspace.id') : null) {
                $builder->where($builder->getModel()->getTable().'.workspace_id', $wid);
            }
        });

        static::creating(function (Model $model) {
            if (! $model->workspace_id && app()->bound('workspace.id')) {
                $model->workspace_id = app('workspace.id');
            }
        });
    }
}
```

```php
// app/Http/Middleware/ResolveWorkspace.php — binds workspace.id per request from the authed user
public function handle($request, \Closure $next)
{
    if ($user = $request->user()) {
        app()->instance('workspace.id', $user->workspace_id);
    }
    return $next($request);
}
```

  Document: register the middleware in `bootstrap/app.php` (`->withMiddleware(...)`); the global scope auto-filters every query → cross-workspace read returns nothing → controller `findOrFail()` → **404** (existence not leaked).

  Mandatory Pest test (verbatim):

```php
// tests/Feature/WorkspaceIsolationTest.php
it('returns 404 when reading another workspace resource', function () {
    $wsA = Workspace::factory()->create();
    $wsB = Workspace::factory()->create();
    $userB = User::factory()->for($wsB)->create();
    $companyA = Company::factory()->for($wsA)->create();

    $response = $this->actingAs($userB, 'sanctum')->getJson("/api/v1/companies/{$companyA->id}");

    expect($response->status())->toBe(404);
});

it('viewer cannot create a company', function () {
    $ws = Workspace::factory()->create();
    $viewer = User::factory()->for($ws)->create();
    $viewer->assignRole('Viewer');

    $response = $this->actingAs($viewer, 'sanctum')
        ->postJson('/api/v1/companies', ['name' => 'X', 'industry' => 'Technology']);

    expect($response->status())->toBe(403);
});
```

  Note the cross-tenant assertion must query with `withoutGlobalScopes()` when setting up fixtures for the *other* workspace.

- [ ] **Step 2: Validate** — even fences.
- [ ] **Step 3: Commit** `feat(laravel): add multitenancy-global-scope reference (+cross-workspace 404 test)`.

---

### Task 1.5: `references/audit-attribute.md` (novel)

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/audit-attribute.md`

- [ ] **Step 1: Author** with exact code:

```php
// app/Audit/Audit.php — the attribute
#[\Attribute(\Attribute::TARGET_METHOD)]
final class Audit
{
    public function __construct(public string $action, public string $subject) {}
}
```

```php
// app/Audit/AuditManager.php — wraps an action, times it, dispatches the write job
final class AuditManager
{
    public function run(string $action, string $subject, \Closure $fn, array $context = [])
    {
        $start = microtime(true);
        $status = 'Success';
        try {
            return $fn();
        } catch (\Throwable $e) {
            $status = 'Failure';
            throw $e;
        } finally {
            \App\Jobs\AuditWrite::dispatch([
                'action' => $action,
                'subject' => $subject,
                'status' => $status,                          // Title Case
                'duration_ms' => (int) ((microtime(true) - $start) * 1000),
                'workspace_id' => app()->bound('workspace.id') ? app('workspace.id') : null,
                'user_id' => optional(auth()->user())->id,
                'request_id' => request()->header('X-Request-Id'),
                'ip' => request()->ip(),
                'context' => $context,                        // redacted args
                'occurred_at' => now()->toIso8601String(),
            ])->onQueue('audit');
        }
    }
}
```

```php
// app/Jobs/AuditWrite.php — SQS job that inserts the row
class AuditWrite implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable;
    public function __construct(public array $row) {}
    public function handle(): void
    {
        DB::table('audit_logs')->insert([
            'id' => (string) Str::uuid(),
            ...$this->row,
            'context' => json_encode($this->row['context'] ?? []),
        ]);
    }
}
```

  Usage in a service (mutations only):

```php
public function create(CreateCompanyData $input): CompanyData
{
    return app(AuditManager::class)->run('company.create', 'Company', function () use ($input) {
        $company = \App\Support\CockroachRetry::transaction(fn () => Company::create($input->toArray()));
        return CompanyData::fromModel($company->loadCount('contacts'));
    });
}
```

  Document the optional `#[Audit]`-attribute-via-reflection wrapper (a service decorator/middleware reading the attribute) as the declarative form, with the explicit `AuditManager::run()` shown above as the always-works baseline.

  Partitioned `audit_logs` migration (RANGE by `occurred_at`), CockroachDB-flavored, plus a scheduled prune command:

```php
// migration — partitioned audit table (no TimescaleDB)
DB::statement("CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action STRING NOT NULL, subject STRING NOT NULL, status STRING NOT NULL,
    duration_ms INT, workspace_id UUID, user_id UUID, request_id STRING, ip STRING,
    context JSONB, occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    INDEX (workspace_id, occurred_at)
)");
```

```php
// app/Console/Commands/PruneAuditLogs.php (scheduled daily) — retention via delete (CRDB has no Timescale drop-chunk)
DB::statement('DELETE FROM audit_logs WHERE occurred_at < now() - INTERVAL ?', ['180 days']);
```

- [ ] **Step 2: Validate** — even fences.
- [ ] **Step 3: Commit** `feat(laravel): add audit-attribute reference (#[Audit] + AuditManager + SQS + partitioned table)`.

---

### Task 1.6: `references/enums-title-case.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/enums-title-case.md`

- [ ] **Step 1: Author.** PHP 8.1 string-backed enums, Title-Case values, Eloquent casts. Exact example:

```php
enum Industry: string {
    case Technology = 'Technology';
    case Healthcare = 'Healthcare';
    case Finance    = 'Finance';
    case Logistics  = 'Logistics';
    case Other      = 'Other';
}

enum Stage: string {
    case New          = 'New';
    case Qualified    = 'Qualified';
    case ProposalSent = 'Proposal Sent';   // case name PascalCase, value Title Case w/ spaces
    case Won          = 'Won';
    case Lost         = 'Lost';
}
```

```php
// model casts() — value IS the wire/UI label; no label maps, no toUpperCase
protected function casts(): array {
    return ['industry' => Industry::class, 'stage' => Stage::class];
}
```

  Reuse the Good/Bad table and the "what this changes" bullets from the Nest SKILL.md (stack-agnostic content). Note: emitted TS union from `typescript:transform` is `'Technology' | 'Healthcare' | …` — identical to the old Zod output. STRING columns (not native PG enum types) to dodge CRDB cross-type-cast friction. Forbidden: `_LABELS` maps, `Str::title()`/`strtoupper()` on enum data, snake/SCREAMING values.

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add enums-title-case reference`.

---

### Task 1.7: `references/auth-sanctum-permissions.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/auth-sanctum-permissions.md`

- [ ] **Step 1: Author** (mirror Nest `auth-casl.md`, translate). Sections + code:
  - Install: `composer require laravel/sanctum spatie/laravel-permission`; publish + migrate.
  - Sanctum personal-access tokens for the cross-domain Next.js SPA (`Authorization: Bearer`); token issuance on login; `auth:sanctum` middleware.
  - spatie roles/permissions seeded (the permission matrix). Roles are an input; Policies resolve the answer.
  - A Policy with the workspace condition:

```php
class CompanyPolicy {
    public function update(User $user, Company $company): bool {
        return $user->can('company.update') && $user->workspace_id === $company->workspace_id;
    }
}
```

  - Enforcement via Laravel 13 `#[Authorize]` attribute on the controller method (preferred), or `$this->authorize('update', $company)`:

```php
use Illuminate\Routing\Attributes\Controllers\Authorize;

class CompanyController {
    #[Authorize('create', Company::class)]
    public function store(CreateCompanyData $data) { /* ... */ }
}
```

  - Rule: authorize EVERY endpoint incl. `GET /me`. Cross-workspace + viewer-negative tests live in `multitenancy-global-scope.md`.

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add auth-sanctum-permissions reference`.

---

### Task 1.8: `references/db-cache-sessions.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/db-cache-sessions.md`

- [ ] **Step 1: Author.** `CACHE_STORE=database`, `SESSION_DRIVER=database`; create tables:

```bash
php artisan make:cache-table
php artisan make:session-table
php artisan migrate
```

  Env block (`.env.example`): `CACHE_STORE=database`, `SESSION_DRIVER=database`, `QUEUE_CONNECTION=sqs`, no `REDIS_*`. Note: these tables live in CockroachDB; verify TTL/locking under serverless. Cache invalidation: use cache **tags**/explicit keyed deletes (the Redis SCAN/`delByPattern` pattern does not map). Why DB not Redis: Lambda is stateless and Redis needs a VPC.

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add db-cache-sessions reference`.

---

### Task 1.9: `references/sqs-queues.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/sqs-queues.md`

- [ ] **Step 1: Author** (the app-side companion to the deployer's `sqs-worker.md`). `composer require aws/aws-sdk-php`; `QUEUE_CONNECTION=sqs`; `config/queue.php` sqs block; jobs implement `ShouldQueue`; dispatch with `->onQueue(...)`; idempotency keys (at-least-once delivery); keep jobs < 60 s (15-min Lambda cap); DLQ + CloudWatch alarms (no Horizon). The `audit` queue is one such queue. Crons are Laravel scheduler entries in `routes/console.php` (run by EventBridge → console Lambda — see deployer skill).

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add sqs-queues reference`.

---

### Task 1.10: `references/scaffolding.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/scaffolding.md`

- [ ] **Step 1: Author** (mirror Nest `scaffolding.md`). Steps: `laravel new apps/api` (13.x, no starter kit — API only); `composer require` the runtime stack (laravel-data, typescript-transformer, sanctum, spatie/permission, aws-sdk-php) + `--dev` Boost + Pest; `.env.example` (CockroachDB DSN, `CACHE_STORE=database`, `SESSION_DRIVER=database`, `QUEUE_CONNECTION=sqs`); `bootstrap/app.php` middleware registration (ResolveWorkspace, sanctum); make cache/session tables; UUID-PK base migration habit; `routes/api.php` `v1` prefix; boot verify (`php artisan serve` + a `/api/v1/health` route). Final scaffolding tree (`app/Domains/`, `app/Audit/`, `app/Support/`, `app/Concerns/`).

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add scaffolding reference`.

---

### Task 1.11: `references/monorepo-setup.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/monorepo-setup.md`

- [ ] **Step 1: Author** (mirror Nest `monorepo-setup.md`, but the Laravel app is NOT a pnpm package). Sections: the layout from spec §10; `packages/contracts` stays a pnpm/TS package but its `src/generated.ts` is produced by `php artisan typescript:transform` (output_file points there); a Turbo `contracts` task that shells to artisan, with `apps/web` `dependsOn: ["contracts"]`:

```json
// turbo.json (excerpt)
"tasks": {
  "contracts": { "cache": false },
  "build": { "dependsOn": ["^build", "contracts"] }
}
```

```json
// package.json at root — a script Turbo's contracts task runs
"scripts": { "contracts": "cd apps/api && php artisan typescript:transform" }
```

  Local infra: `docker-compose.yml` with a single-node CockroachDB for dev parity (cite the deployer skill for prod). `.gitignore`: Boost-generated files (`.mcp.json`, `CLAUDE.md`, `AGENTS.md`, `.ai/*`), `packages/contracts/src/generated.ts` may be committed or generated — document choice (commit the generated file so `apps/web` builds without PHP).

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add monorepo-setup reference`.

---

### Task 1.12: `references/view-data-pattern.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/view-data-pattern.md`

- [ ] **Step 1: Author.** The "fully-populated view shape" discipline (mirror Nest `view-presenter.md` rules section): eager-load relations + `withCount()` so counts default to 0; build computed labels + discriminated-union `kind` payloads in the Data class; dates → ISO strings; nullable is explicit, never "missing". The presenter no-null Pest test (verbatim):

```php
it('company data contains no nulls for required fields and matches the contract', function () {
    $company = Company::factory()->create();
    $data = CompanyData::fromModel($company->loadCount('contacts'))->toArray();
    expect($data)->not->toContain(null)             // spot-check required keys
        ->and($data['counts']['contacts'])->toBeInt()
        ->and($data['last_activity']['kind'])->toBeString();
});
```

  Cross-module data: compose via the other domain's Data class (service-level), or eager-load + map.

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add view-data-pattern reference`.

---

### Task 1.13: `references/validation.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/validation.md`

- [ ] **Step 1: Author.** laravel-data input classes drive validation via `validation()` so input rules + response shape + TS come from one place; FormRequest fallback where complex. Example `CreateCompanyData` with rules and a Title-Case enum input. Map error responses to the error-code contract (pointer to `error-handling.md`).

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add validation reference`.

---

### Task 1.14: `references/error-handling.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/error-handling.md`

- [ ] **Step 1: Author.** Global exception handling in `bootstrap/app.php` `->withExceptions(...)`; a typed JSON error shape `{ code, message, details, request_id }` matching the frontend error contract; the ERROR_CODES enum (reuse the Nest `errors.ts` codes as a PHP enum / const); 404 for cross-workspace (existence not leaked), 403 for authz, 422 for validation.

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add error-handling reference`.

---

### Task 1.15: `references/boost-setup.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/boost-setup.md`

- [ ] **Step 1: Author.** `composer require laravel/boost --dev` → `php artisan boost:install` (enable Guidelines + Skills + MCP); MCP server `php artisan boost:mcp`; register with Claude Code (`claude mcp add -s local -t stdio laravel-boost php artisan boost:mcp`); gitignore generated `.mcp.json`/`CLAUDE.md`/`AGENTS.md`/`.ai/*`/`boost.json`; team conventions live in `.ai/guidelines/*` (not the generated files); run `boost:update --discover` after adding packages. Note Boost is dev-only, never affects production.

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add boost-setup reference`.

---

### Task 1.16: `references/module-structure.md`

**Files:**
- Create: `plugins/superdev/skills/laravel-enterprise-backend/references/module-structure.md`

- [ ] **Step 1: Author.** The `app/Domains/<Feature>/` layout (PSR-4 `App\Domains\<Feature>\`): subfolders `Models/`, `Enums/`, `Data/` (inputs + view), `Actions/` (or `Services/`), `Http/` (Controller, requests), `Policies/`, `Jobs/`, `Tests/`. The canonical build order (spec §6). `routes/api.php` references the controller; migration in `database/migrations/`. One agent owns one `Domains/<Feature>/` folder.

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add module-structure reference`.

---

### Task 1.17: Validate skill 1 end-to-end

- [ ] **Step 1:** Run **VR-1** on `SKILL.md`; **VR-2** for `laravel-enterprise-backend` (all 15 references resolve); **VR-4** (no accidental Nest-stack leakage).
- [ ] **Step 2:** Run **VR-3** (`plugin-dev:plugin-validator` on `plugins/superdev/`). Expected: `laravel-enterprise-backend` discovered, no errors.
- [ ] **Step 3:** Fix any gaps inline, then commit `chore(laravel): validate laravel-enterprise-backend skill` (only if fixes were needed).

---

## PHASE 2 — `laravel-bref-deploy` skill

### Task 2.1: Skill scaffold + SKILL.md

**Files:**
- Create: `plugins/superdev/skills/laravel-bref-deploy/SKILL.md`

- [ ] **Step 1: Create dir + SKILL.md frontmatter** (verbatim):

```yaml
---
name: laravel-bref-deploy
description: Deploy a Laravel backend to AWS Lambda serverless with Bref 3.x. Produces a serverless.yml with three functions — a php-84-fpm web function (httpApi), a php-84 SQS queue worker using Bref's QueueHandler, and a php-84-console Artisan function — plus an EventBridge schedule running schedule:run every minute, public HTML and static assets copied to S3 and served via CloudFront, secrets in AWS SSM Parameter Store, database-backed cache and sessions, and CockroachDB serverless reached over the public internet with no VPC. Defaults to the free OSS Serverless CLI (osls deploy) with Bref Cloud (bref deploy) documented as the simpler managed alternative. Use whenever the user wants to deploy, ship, or configure serverless hosting for a Laravel app; mentions Bref, AWS Lambda, serverless.yml, SQS workers, EventBridge scheduling, S3/CloudFront assets, SSM secrets, or serverless Laravel.
---
```

- [ ] **Step 2: Write the body** — phased deploy pipeline: (1) Install Bref (`composer require bref/bref bref/laravel-bridge --update-with-dependencies`, `php artisan vendor:publish --tag=serverless-config`, `serverless plugin install -n serverless-lift`); (2) Configure functions (web/worker/artisan); (3) SQS + scheduler; (4) Assets to S3/CloudFront (D8); (5) Secrets via SSM; (6) Migrate-then-deploy; (7) Verify. The 3-function topology block (spec §7). "Deploy tool" section: default `osls` (`npm i -g osls`), Bref Cloud `bref deploy` alternative; note original Serverless Framework is no longer OSS. Reference table (8 files). Validation checklist (spec §15 item 3).

- [ ] **Step 3: Validate** — **VR-1**. **Step 4: Commit** `feat(laravel): add laravel-bref-deploy SKILL.md`.

---

### Task 2.2: `references/serverless-yml.md` (novel — full blueprint)

**Files:**
- Create: `plugins/superdev/skills/laravel-bref-deploy/references/serverless-yml.md`

- [ ] **Step 1: Author** with the complete blueprint:

```yaml
service: app-api
provider:
  name: aws
  region: ${env:AWS_REGION, 'us-east-1'}
  runtime: provided.al2
  architecture: arm64
  environment:
    APP_ENV: production
    APP_KEY: ${ssm:/app/APP_KEY}
    DATABASE_URL: ${ssm:/app/DATABASE_URL}      # CockroachDB serverless DSN
    CACHE_STORE: database
    SESSION_DRIVER: database
    QUEUE_CONNECTION: sqs
    SQS_QUEUE: ${construct:jobs.queueUrl}
    FILESYSTEM_DISK: s3
    ASSET_URL: ${env:ASSET_URL}                 # CloudFront domain

plugins:
  - ./vendor/bref/bref
  - serverless-lift

functions:
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28
    memorySize: 1024
    events:
      - httpApi: '*'
  artisan:
    handler: artisan
    runtime: php-84-console
    timeout: 720
    events:
      - schedule:
          rate: rate(1 minute)
          input: '"schedule:run"'              # EventBridge -> scheduler

constructs:
  jobs:
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 60

resources:
  # S3 bucket + CloudFront for public assets are managed in storage-s3-cloudfront.md
```

  Document each block; note `runtime:` keys are Bref 3.x shorthand for the layers. Reserved concurrency note for the `web` function (DB fan-out).

- [ ] **Step 2: Validate** — even fences; the YAML block is internally consistent (function/construct names referenced in env exist). **Step 3: Commit** `feat(laravel): add serverless-yml reference`.

---

### Task 2.3: `references/sqs-worker.md` (novel)

**Files:**
- Create: `plugins/superdev/skills/laravel-bref-deploy/references/sqs-worker.md`

- [ ] **Step 1: Author.** The lift `queue` construct creates the SQS queue + DLQ; worker uses `Bref\LaravelBridge\Queue\QueueHandler` (runtime `php-84`); `QUEUE_CONNECTION=sqs`, `SQS_QUEUE=${construct:jobs.queueUrl}`; no `queue:work` daemon. Jobs < 60 s; idempotency; DLQ + CloudWatch alarms (no Horizon dashboard). Multiple queues (e.g. `audit`, `default`) via additional constructs or a single queue with job-class routing (Laravel 13 `Queue::route`).

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add sqs-worker reference`.

---

### Task 2.4: `references/storage-s3-cloudfront.md` (novel — D8, the asset/HTML copy)

**Files:**
- Create: `plugins/superdev/skills/laravel-bref-deploy/references/storage-s3-cloudfront.md`

- [ ] **Step 1: Author.** This file OWNS the public HTML/static-asset handling (D8): Lambda FS is read-only except `/tmp`. Steps: build assets; **copy `public/` HTML + static assets to S3** on deploy; serve via CloudFront; set `ASSET_URL` to the CloudFront domain and always use `asset()`; CloudFront invalidation on deploy; presigned S3 URLs for uploads > 4 MB (API Gateway payload cap); user uploads on an S3 disk (`allowAcl: true` for Flysystem ACL). Include the S3 bucket + CloudFront `resources:` snippet for `serverless.yml`, and the deploy-time sync command (`aws s3 sync public/ s3://<bucket>/ --exclude index.php`).

- [ ] **Step 2: Validate** — even fences. **Step 3: Commit** `feat(laravel): add storage-s3-cloudfront reference (public HTML/asset copy)`.

---

### Task 2.5: `references/runtimes-and-functions.md`

- [ ] **Step 1: Author** `plugins/superdev/skills/laravel-bref-deploy/references/runtimes-and-functions.md`: the three Bref 3.x runtimes (`php-84-fpm` web, `php-84` event/worker, `php-84-console` = php-84 + console layers), what each function does, memory/timeout guidance, ARM64 cost note, cold-start budget (~250 ms p99) + optional provisioned concurrency. **Step 2: Validate** even fences. **Step 3: Commit** `feat(laravel): add runtimes-and-functions reference`.

### Task 2.6: `references/scheduler-eventbridge.md`

- [ ] **Step 1: Author**: EventBridge `rate(1 minute)` → `artisan schedule:run`; cron definitions in `routes/console.php`; idempotency for at-least-once; the audit-prune command runs here. **Step 2: Validate**. **Step 3: Commit** `feat(laravel): add scheduler-eventbridge reference`.

### Task 2.7: `references/secrets-ssm.md`

- [ ] **Step 1: Author**: AWS SSM Parameter Store (free); `${ssm:/app/...}` at deploy time or `bref-ssm:` runtime via `bref/secrets-loader`; what lives in SSM (APP_KEY, DATABASE_URL, AWS keys); never commit secrets; `php artisan key:generate` → store in SSM. **Step 2: Validate**. **Step 3: Commit** `feat(laravel): add secrets-ssm reference`.

### Task 2.8: `references/cockroachdb-serverless-connection.md`

- [ ] **Step 1: Author**: CockroachDB serverless reached over public internet → **no VPC** (avoids NAT cost + ENI cold starts); DSN/SSL (`sslmode=verify-full`, cluster routing in DB name); connection fan-out under Lambda concurrency → bounded reserved concurrency (no RDS Proxy without VPC); cross-reference the backend skill's `cockroachdb-eloquent.md`. **Step 2: Validate**. **Step 3: Commit** `feat(laravel): add cockroachdb-serverless-connection reference`.

### Task 2.9: `references/deploy-checklist.md`

- [ ] **Step 1: Author**: ordered pre-deploy checklist — `vendor:publish --tag=serverless-config`; `php artisan config:clear`; **run migrations BEFORE deploy** (`osls bref:cli --args="migrate --force"` or Bref Cloud equivalent); audit package size < 250 MB (watch `aws/aws-sdk-php`); `osls deploy --stage prod` (default) / `bref deploy` (alternative); post-deploy: CloudFront invalidation, smoke-test `/api/v1/health`, verify SQS worker + scheduler fire, check CloudWatch logs are JSON. **Step 2: Validate**. **Step 3: Commit** `feat(laravel): add deploy-checklist reference`.

### Task 2.10: Validate skill 2 end-to-end

- [ ] **Step 1:** **VR-1** on `SKILL.md`; **VR-2** for `laravel-bref-deploy` (all 8 references resolve); **VR-4**.
- [ ] **Step 2:** **VR-3** (`plugin-dev:plugin-validator`). Expected: `laravel-bref-deploy` discovered, no errors.
- [ ] **Step 3:** Fix inline; commit `chore(laravel): validate laravel-bref-deploy skill` if needed.

---

## PHASE 3 — `laravel-module-builder` agent

### Task 3.1: Create the agent

**Files:**
- Create: `plugins/superdev/agents/laravel-module-builder.md`

- [ ] **Step 1: Author** with this frontmatter:

```yaml
---
name: laravel-module-builder
description: Builds one Laravel feature module under apps/api/app/Domains/<Feature>/ — model, enums, laravel-data classes (presenter + contract), action/service, controller, policy, jobs, migration, Pest tests. Decorates mutations with #[Audit]. Uses spatie/laravel-permission + Policies + #[Authorize]. Scopes every query via the BelongsToWorkspace global scope. One agent per feature, designed for parallel dispatch.
tools: Read, Write, Edit, Bash
model: inherit
permissionMode: acceptEdits
skills:
  - laravel-enterprise-backend
---
```

- [ ] **Step 2: Author the body** (mirror `agents/backend-module-builder.md`, translate to Laravel): inputs (feature name, EXECUTION_PLAN, the feature's Data classes already authored by contracts-author, the skill + key references); outputs (files under `app/Domains/<Feature>/`, migration, route entry); critical patterns (Title-Case enums; Data-as-presenter — never return a model/array; `BelongsToWorkspace` scoping; `#[Audit]` on every mutation; `#[Authorize]` on every endpoint; Pest tests: no-null view-shape, cross-workspace 404, authz-negative); after-writing (`php artisan typescript:transform`; `php artisan test --filter=<Feature>`; ≤ 3 fix attempts then report); strict rules (don't touch other features; don't hand-author TS — generate it; don't skip Data presenter / `#[Audit]` / cross-workspace test; use Edit for `routes/api.php` append). Return format: files created, typecheck/test status, deviations, route line added (yes/no).

- [ ] **Step 3: Validate** — **VR-1** on the agent file (`name` == `laravel-module-builder`). **Step 4: Commit** `feat(laravel): add laravel-module-builder agent`.

---

## PHASE 4 — Orchestrator integration (the "container asks the question")

### Task 4.1: Selection gate + routing in the orchestrator SKILL.md

**Files:**
- Modify: `plugins/superdev/skills/prd-design-build-orchestrator/SKILL.md`

- [ ] **Step 1:** In the "Skill routing" table (around line 34-49), add a row:
  `| User chose **Laravel** backend | laravel-enterprise-backend (build) + laravel-bref-deploy (Phase D ship) | Eloquent/CockroachDB/Bref serverless stack |`
  and keep the existing `nestjs-enterprise-backend` row (relabel its condition "User chose **Nest.js** backend").

- [ ] **Step 2:** Add a new subsection **"Step A.5 — Backend-stack selection gate"** immediately after "Step A.5 — User-confirmation gate" (renumber the existing A.5 to A.5a if needed, or insert as A.6). Exact content:

````markdown
### Step A.5b — Backend-stack selection gate

If `EXECUTION_PLAN.md` contains backend modules, the orchestrator asks the operator BEFORE Phase B which backend stack to build, using `AskUserQuestion`:

> **Backend stack?**
> - **Nest.js** — Postgres 17 + TimescaleDB + Drizzle + Redis/BullMQ + CASL (`nestjs-enterprise-backend`)
> - **Laravel** — Laravel 13 + CockroachDB + DB cache/sessions + SQS, deployed via Bref (`laravel-enterprise-backend` + `laravel-bref-deploy`)

Persist the answer to `STACK.md` (and a `backend_stack:` field in `EXECUTION_PLAN.md`) so every later phase — and any resume — reads the same value. All Phase B/C/D backend routing below is conditioned on this value. The frontend half is unaffected.
````

- [ ] **Step 3:** In Phase B.1 (monorepo-bootstrapper), B.2 (contracts-author), and Phase C (module builder), add a one-line stack conditional pointing at the table (e.g., "If `backend_stack == Laravel`, dispatch `laravel-module-builder` instead of `backend-module-builder`, and read `laravel-enterprise-backend` references.").

- [ ] **Step 4:** Update the agent install/expected-count notes (Step A.1) to mention `laravel-module-builder` is auto-discovered and used when the Laravel stack is chosen.

- [ ] **Step 5: Validate** — **VR-1** (frontmatter still parses); re-read the edited sections to confirm no broken markdown. **Step 6: Commit** `feat(orchestrator): add backend-stack selection gate + Laravel routing`.

---

### Task 4.2: Stack-aware `monorepo-bootstrapper`

**Files:**
- Modify: `plugins/superdev/agents/monorepo-bootstrapper.md`

- [ ] **Step 1:** Add a "Backend stack" section: if `STACK.md`/plan says Laravel, scaffold `apps/api` per `laravel-enterprise-backend/references/scaffolding.md` + `monorepo-setup.md` (Laravel app, composer, Boost, stock pgsql/CockroachDB, db cache/session tables, single-node CockroachDB compose for local) instead of the Nest scaffold; `packages/contracts` is populated by `php artisan typescript:transform`. Keep the Nest path as the default/else branch.
- [ ] **Step 2: Validate** — **VR-1**. **Step 3: Commit** `feat(orchestrator): make monorepo-bootstrapper stack-aware (Laravel)`.

---

### Task 4.3: Stack-aware `contracts-author`

**Files:**
- Modify: `plugins/superdev/agents/contracts-author.md`

- [ ] **Step 1:** Add a "Backend stack" section: if Laravel, author **laravel-data classes** in `apps/api/app/Domains/<Feature>/Data/` (per `laravel-data-contracts.md`) and run `php artisan typescript:transform` to populate `packages/contracts/src/generated.ts` — do NOT hand-author Zod. Keep the Zod path as the default/else branch.
- [ ] **Step 2: Validate** — **VR-1**. **Step 3: Commit** `feat(orchestrator): make contracts-author stack-aware (laravel-data → TS)`.

---

### Task 4.4: Stack notes in `execution-pipeline.md` (if the file references backend builders)

**Files:**
- Modify: `plugins/superdev/skills/prd-design-build-orchestrator/references/execution-pipeline.md`

- [ ] **Step 1:** `grep -n "backend-module-builder" plugins/superdev/skills/prd-design-build-orchestrator/references/execution-pipeline.md`. If hits, add a note next to each: "(Laravel stack → `laravel-module-builder`)". If no hits, skip this task.
- [ ] **Step 2: Commit** (only if edited) `docs(orchestrator): note Laravel module builder in execution pipeline`.

---

## PHASE 5 — Docs & manifests

### Task 5.1: plugin.json (both manifests)

**Files:**
- Modify: `plugins/superdev/.claude-plugin/plugin.json`
- Modify: `plugins/superdev/.codex-plugin/plugin.json`

- [ ] **Step 1:** Bump `version` (1.3.1 → **1.4.0**). Update `description` in both: "13-skill" → "15-skill"; append a sentence: "v1.4.0 adds a Laravel backend option — `laravel-enterprise-backend` (Laravel 13 + CockroachDB + database cache/sessions + SQS, spatie/laravel-data contracts, #[Audit] attribute, Title-Case enums) and `laravel-bref-deploy` (AWS Lambda serverless via Bref 3.x), plus a backend-stack selection gate in the orchestrator." Add keywords to both: `laravel`, `bref`, `serverless`, `cockroachdb`, `eloquent`, `sanctum`, `aws-lambda`.
- [ ] **Step 2: Validate** — both files parse: `node -e "require('./plugins/superdev/.claude-plugin/plugin.json');require('./plugins/superdev/.codex-plugin/plugin.json');console.log('OK json')"`. Expected `OK json`.
- [ ] **Step 3: Commit** `chore: bump to v1.4.0; document Laravel backend in plugin manifests`.

---

### Task 5.2: READMEs

**Files:**
- Modify: `README.md`
- Modify: `plugins/superdev/README.md`

- [ ] **Step 1:** In `README.md` "## 🧬 What's Inside — 13 Skills": change to **15 Skills**; add rows 14 (`laravel-enterprise-backend`) and 15 (`laravel-bref-deploy`) with one-line descriptions; in the stack/tooling tables add Laravel/CockroachDB/Bref; update the orchestrator diagram caption if it hardcodes a skill count ("11 skills"/"13 skills"). Add a short "Backend stack choice" note explaining the orchestrator asks Laravel vs Nest.js.
- [ ] **Step 2:** Mirror the relevant updates in `plugins/superdev/README.md`.
- [ ] **Step 3: Validate** — `grep -rn "13 Skills\|13-skill\|11 skills" README.md plugins/superdev/README.md` returns no stale counts (or only intentional historical references).
- [ ] **Step 4: Commit** `docs: add Laravel skills to READMEs; update skill count to 15`.

---

### Task 5.3: marketplace.json

**Files:**
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1:** Update the two `description` strings (lines ~4 and ~13) that say "13 skills"/"13 production-grade skills" → 15, and append the two new skills to the enumerated skill list. (`.agents/plugins/marketplace.json` does not enumerate skills — confirm with `grep -c nestjs-enterprise-backend .agents/plugins/marketplace.json` returning 0; if non-zero, update it too.)
- [ ] **Step 2: Validate** — `node -e "require('./.claude-plugin/marketplace.json');console.log('OK')"`.
- [ ] **Step 3: Commit** `docs: update marketplace description to 15 skills`.

---

## PHASE 6 — Final verification

### Task 6.1: Whole-plugin validation + spec acceptance check

- [ ] **Step 1:** Run **VR-3** (`plugin-dev:plugin-validator` on `plugins/superdev/`). Expected: 15 skills + the new agent discovered; zero errors.
- [ ] **Step 2:** Run **VR-2** for BOTH new skills and **VR-4** across both skill dirs.
- [ ] **Step 3:** Skill-count sanity: `ls -d plugins/superdev/skills/*/ | wc -l` returns the expected total (was 13 → now **15**). `test -f plugins/superdev/agents/laravel-module-builder.md`.
- [ ] **Step 4:** Walk spec §15 acceptance criteria 1–5 against the repo; confirm each is satisfied (selection gate present + routes; both skills complete; commitments preserved; docs updated). Note any gaps as follow-up tasks.
- [ ] **Step 5:** Optionally use `skill-creator` to score the two new SKILL.md descriptions for triggering quality; tighten if weak.
- [ ] **Step 6: Commit** `chore(laravel): final validation of Laravel backend option` (if any fixes), then summarize the branch diff for review / PR.

---

## Self-Review (run after the plan is written)

**1. Spec coverage** — every spec section maps to a task:
- §3 commitments 1–8 → Tasks 1.1 (SKILL commitments), 1.3 (contracts), 1.4 (tenancy), 1.5 (audit), 1.6 (enums), 1.7 (authz), 1.8 (cache/sessions), 1.9 (queues), 1.12 (view-shape). ✓
- §4 target stack → Task 1.1 (stack section) + 1.10 scaffolding. ✓
- §5 CockroachDB layer → Task 1.2. ✓
- §6 build skill → Tasks 1.1–1.17. ✓
- §7 deploy skill → Tasks 2.1–2.10. ✓
- §8 agent → Task 3.1. ✓
- §9 orchestrator → Tasks 4.1–4.4. ✓
- §10 monorepo → Task 1.11 + 4.2. ✓
- §11 docs/manifests → Tasks 5.1–5.3. ✓
- D8 asset/HTML copy → Task 2.4. ✓ · D4 stock pgsql → Task 1.2. ✓ · D3 #[Audit] → Task 1.5. ✓ · D2/D7 laravel-data→TS, types-only → Tasks 1.3, 1.6, 4.3. ✓
- §15 acceptance → Task 6.1. ✓

**2. Placeholder scan** — novel technical files (1.2–1.5, 2.2–2.4, 3.1, 4.1) carry complete code/text; mirror files cite a concrete in-repo Nest source file to translate (not a placeholder). No "TBD/TODO".

**3. Type/name consistency** — names used consistently across tasks: `BelongsToWorkspace`, `CockroachRetry::transaction`, `AuditManager::run`, `AuditWrite`, `CompanyData::fromModel`, `app('workspace.id')`, `php artisan typescript:transform`, `packages/contracts/src/generated.ts`, `app/Domains/<Feature>/`, runtimes `php-84-fpm`/`php-84`/`php-84-console`, queue construct `jobs`. ✓
