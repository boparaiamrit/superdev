# Laravel Module Structure

Canonical folder layout for a feature domain module. Read in Phase 2 (planning) and Phase 5 (per-module generation).

## `apps/api/` top-level layout

```
apps/api/
├── composer.json
├── artisan
├── serverless.yml              ← added by laravel-bref-deploy skill
├── docker-compose.yml          ← single-node CockroachDB for local dev
├── database/
│   └── migrations/             ← one migration file per domain entity
├── routes/
│   ├── api.php                 ← all v1 API routes; each controller referenced here
│   └── console.php             ← scheduler entries (cron expressions live here)
└── app/
    ├── Audit/                  ← #[Audit] attribute + AuditManager + AuditWrite job
    ├── Concerns/               ← HasUuidPrimaryKey, BelongsToWorkspace traits
    ├── Support/                ← CockroachRetry, helpers
    ├── Http/
    │   └── Middleware/
    │       └── ResolveWorkspace.php
    └── Domains/                ← feature domain modules (the bulk of the app)
```

There is no separate worker entrypoint file in `app/`. The SQS worker Lambda runs the same app bootstrapped by Bref's `QueueHandler` — see `references/sqs-queues.md`. The scheduler fires via EventBridge → `artisan schedule:run` — see `laravel-bref-deploy/references/scheduler-eventbridge.md`.

## `app/Audit/` — cross-cutting audit infrastructure

Always present; used by every domain that performs mutations.

```
app/Audit/
├── Audit.php               ← #[Audit(action, subject)] PHP 8.1 attribute
└── AuditManager.php        ← wraps an action, times it, dispatches AuditWrite to SQS
```

The `AuditWrite` job lives in `app/Jobs/AuditWrite.php` (shared, not per-domain). See `references/audit-attribute.md` for the full implementation.

## `app/Concerns/` — shared model traits

```
app/Concerns/
├── HasUuidPrimaryKey.php   ← $incrementing = false; $keyType = 'string'
└── BelongsToWorkspace.php  ← global scope + creating hook; auto-filters all tenant queries
```

See `references/multitenancy-global-scope.md` for the full trait implementations.

## `app/Domains/<Feature>/` — feature domain modules

Every feature is a self-contained domain module at `app/Domains/<Feature>/` (PSR-4 namespace `App\Domains\<Feature>\`). This mirrors Nest's per-feature `src/modules/<feature>/` folder; a single `laravel-module-builder` agent owns exactly one domain folder and never touches another feature's files.

```
app/Domains/Companies/
├── Models/
│   └── Company.php             ← Eloquent model; uses HasUuidPrimaryKey + BelongsToWorkspace
├── Enums/
│   └── Industry.php            ← PHP 8.1 string-backed Title Case enum
├── Data/
│   ├── CompanyData.php         ← view-shape presenter (spatie/laravel-data); also the TS contract
│   ├── CompanyCountsData.php   ← nested data object (counts always present, never null)
│   ├── CreateCompanyData.php   ← input data class with validation() rules
│   └── UpdateCompanyData.php   ← input data class (partial update)
├── Actions/                    ← (or Services/ — choose one per domain, be consistent)
│   ├── CreateCompany.php       ← single-responsibility action; wraps AuditManager::run()
│   ├── UpdateCompany.php
│   └── DeleteCompany.php
├── Http/
│   ├── Controllers/
│   │   └── CompanyController.php   ← thin; delegates to Action/Service; #[Authorize] on every method
│   └── Requests/
│       └── (FormRequest subclasses if validation() on Data classes is insufficient)
├── Policies/
│   └── CompanyPolicy.php       ← can(), update(), delete() — workspace condition lives here
├── Jobs/
│   └── (feature-specific background jobs, e.g. SendCompanyWelcomeEmail.php)
└── Tests/
    ├── CompanyDataTest.php     ← unit: no-null view-shape, correct counts, ISO dates
    ├── CompanyActionTest.php   ← unit: action happy path + 40001 retry trigger
    └── CompanyFeatureTest.php  ← feature: cross-workspace 404, authz-negative, CRUD happy path
```

### `Models/Company.php`

```php
// app/Domains/Companies/Models/Company.php
namespace App\Domains\Companies\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use App\Concerns\HasUuidPrimaryKey;
use App\Concerns\BelongsToWorkspace;
use App\Domains\Companies\Enums\Industry;

class Company extends Model
{
    use HasFactory, HasUuidPrimaryKey, BelongsToWorkspace;

    protected $fillable = ['name', 'domain', 'industry', 'workspace_id'];

    protected function casts(): array
    {
        return [
            'industry' => Industry::class,
        ];
    }

    // Relationships: plain reference columns — no FK constraints (D9)
    public function contacts()
    {
        return $this->hasMany(\App\Domains\Contacts\Models\Contact::class, 'company_id');
    }
}
```

### `Enums/Industry.php`

```php
// app/Domains/Companies/Enums/Industry.php
namespace App\Domains\Companies\Enums;

use Spatie\TypeScriptTransformer\Attributes\TypeScript;

#[TypeScript]
enum Industry: string
{
    case Technology = 'Technology';
    case Healthcare = 'Healthcare';
    case Finance    = 'Finance';
    case Logistics  = 'Logistics';
    case Other      = 'Other';
}
```

DB column is STRING (not a native PG enum type). Value = wire value = UI label; zero conversion code. See `references/enums-title-case.md`.

### `Data/CompanyData.php`

```php
// app/Domains/Companies/Data/CompanyData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\TypeScriptTransformer\Attributes\TypeScript;
use App\Domains\Companies\Enums\Industry;
use App\Domains\Companies\Models\Company;

#[TypeScript]
class CompanyData extends Data
{
    public function __construct(
        public string  $id,
        public string  $name,
        public ?string $domain,              // nullable is explicit; never "missing"
        public Industry $industry,
        public CompanyCountsData $counts,    // always present — defaults to 0 server-side
        public string  $created_at,          // ISO 8601 string, never Carbon object
        public string  $updated_at,
    ) {}

    public static function fromModel(Company $company): self
    {
        return new self(
            id:         $company->id,
            name:       $company->name,
            domain:     $company->domain,
            industry:   $company->industry,
            counts: new CompanyCountsData(
                contacts:    (int) ($company->contacts_count ?? 0),
                open_leads:  (int) ($company->open_leads_count ?? 0),
                won_deals:   (int) ($company->won_deals_count ?? 0),
            ),
            created_at: $company->created_at->toIso8601String(),
            updated_at: $company->updated_at->toIso8601String(),
        );
    }
}
```

`php artisan typescript:transform` emits this class into `packages/contracts/src/generated.ts` as a TypeScript interface. See `references/laravel-data-contracts.md`.

### `Data/CreateCompanyData.php`

```php
// app/Domains/Companies/Data/CreateCompanyData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\LaravelData\Attributes\Validation\Required;
use Spatie\LaravelData\Attributes\Validation\StringType;
use Spatie\LaravelData\Attributes\Validation\MaxLength;
use App\Domains\Companies\Enums\Industry;

class CreateCompanyData extends Data
{
    public function __construct(
        #[Required, StringType, MaxLength(255)]
        public string   $name,

        #[StringType, MaxLength(255)]
        public ?string  $domain,

        #[Required]
        public Industry $industry,
    ) {}
}
```

One class is the input shape, the validation rules, and the TypeScript type. See `references/validation.md`.

### `Actions/CreateCompany.php`

```php
// app/Domains/Companies/Actions/CreateCompany.php
namespace App\Domains\Companies\Actions;

use App\Audit\AuditManager;
use App\Domains\Companies\Data\CompanyData;
use App\Domains\Companies\Data\CreateCompanyData;
use App\Domains\Companies\Models\Company;
use App\Support\CockroachRetry;

final class CreateCompany
{
    public function __construct(private AuditManager $audit) {}

    public function handle(CreateCompanyData $input): CompanyData
    {
        return $this->audit->run('company.create', 'Company', function () use ($input) {
            $company = CockroachRetry::transaction(
                fn () => Company::create($input->toArray())
            );
            return CompanyData::fromModel($company->loadCount(['contacts']));
        });
    }
}
```

Every mutation goes through `AuditManager::run()`. Every write inside a transaction goes through `CockroachRetry::transaction()`. See `references/audit-attribute.md` and `references/cockroachdb-eloquent.md`.

### `Http/Controllers/CompanyController.php`

```php
// app/Domains/Companies/Http/Controllers/CompanyController.php
namespace App\Domains\Companies\Http\Controllers;

use App\Domains\Companies\Actions\CreateCompany;
use App\Domains\Companies\Actions\UpdateCompany;
use App\Domains\Companies\Actions\DeleteCompany;
use App\Domains\Companies\Data\CompanyData;
use App\Domains\Companies\Data\CreateCompanyData;
use App\Domains\Companies\Data\UpdateCompanyData;
use App\Domains\Companies\Models\Company;
use Illuminate\Http\Request;
use Illuminate\Routing\Attributes\Controllers\Authorize;
use Spatie\LaravelData\PaginatedDataCollection;

class CompanyController
{
    #[Authorize('viewAny', Company::class)]
    public function index(Request $request)
    {
        return CompanyData::collect(
            Company::query()
                ->withCount(['contacts', 'openLeads as open_leads_count', 'wonDeals as won_deals_count'])
                ->paginate(),
            PaginatedDataCollection::class,
        );
    }

    #[Authorize('view', 'company')]
    public function show(Company $company)
    {
        return CompanyData::fromModel($company->loadCount(['contacts']));
    }

    #[Authorize('create', Company::class)]
    public function store(CreateCompanyData $input, CreateCompany $action)
    {
        return $action->handle($input);
    }

    #[Authorize('update', 'company')]
    public function update(UpdateCompanyData $input, Company $company, UpdateCompany $action)
    {
        return $action->handle($input, $company);
    }

    #[Authorize('delete', 'company')]
    public function destroy(Company $company, DeleteCompany $action)
    {
        $action->handle($company);
        return response()->noContent();
    }
}
```

Controllers stay thin:
- Authenticate (via `auth:sanctum` middleware in `routes/api.php`)
- Authorize (via `#[Authorize]` on every method — no exceptions)
- Validate (via laravel-data input class injection)
- Delegate to Action/Service
- Return Data class or `noContent()`

No conditionals, no transformations, no direct DB calls.

### `Policies/CompanyPolicy.php`

```php
// app/Domains/Companies/Policies/CompanyPolicy.php
namespace App\Domains\Companies\Policies;

use App\Models\User;
use App\Domains\Companies\Models\Company;

class CompanyPolicy
{
    public function viewAny(User $user): bool
    {
        return $user->can('company.view');
    }

    public function view(User $user, Company $company): bool
    {
        // BelongsToWorkspace global scope already filters to workspace; this is a belt-and-suspenders check
        return $user->can('company.view') && $user->workspace_id === $company->workspace_id;
    }

    public function create(User $user): bool
    {
        return $user->can('company.create');
    }

    public function update(User $user, Company $company): bool
    {
        return $user->can('company.update') && $user->workspace_id === $company->workspace_id;
    }

    public function delete(User $user, Company $company): bool
    {
        return $user->can('company.delete') && $user->workspace_id === $company->workspace_id;
    }
}
```

Roles are an input; the Policy resolves the answer. `spatie/laravel-permission` provides the role→permission mapping in the DB. See `references/auth-sanctum-permissions.md`.

## `routes/api.php` — wiring the controller

```php
// routes/api.php
use App\Domains\Companies\Http\Controllers\CompanyController;
use App\Domains\Contacts\Http\Controllers\ContactController;

Route::prefix('v1')->middleware(['auth:sanctum'])->group(function () {

    Route::apiResource('companies', CompanyController::class);

    Route::apiResource('contacts', ContactController::class);

    // ... further domain resources
});
```

The `BelongsToWorkspace` global scope and `ResolveWorkspace` middleware fire automatically on every authenticated request — no per-route tenant plumbing needed.

## `database/migrations/` — one file per entity

```
database/migrations/
├── 0001_01_01_000000_create_users_table.php        ← ships with Laravel
├── 0001_01_01_000001_create_cache_table.php        ← php artisan make:cache-table
├── 0001_01_01_000002_create_sessions_table.php     ← php artisan make:session-table
├── 2026_06_01_000001_create_workspaces_table.php
├── 2026_06_01_000002_create_companies_table.php
├── 2026_06_01_000003_create_contacts_table.php
└── 2026_06_01_000004_create_audit_logs_table.php   ← RANGE-partitioned; see audit-attribute.md
```

All migrations are additive only. Never `ALTER COLUMN TYPE` on a column with an index or constraint. UUID PKs use `gen_random_uuid()` default. No foreign-key constraints — reference columns only (D9). See `references/cockroachdb-eloquent.md`.

## Canonical per-module build order (Phase 5)

Work through each feature in this exact order. Each step depends on the previous.

```
1. Data class (contract + presenter)
   → CompanyData.php, CompanyCountsData.php
   → CreateCompanyData.php, UpdateCompanyData.php
   These are written first because they define the contract shape that migrations
   and the frontend will consume. Run php artisan typescript:transform after each
   Data class to catch transformer errors early.

2. Migration
   → database/migrations/YYYY_MM_DD_HHMMSS_create_companies_table.php
   UUID PK with gen_random_uuid() default; workspace_id reference column (no FK);
   STRING column for enum fields; timestampsTz().

3. Model + enum casts
   → Models/Company.php (HasUuidPrimaryKey, BelongsToWorkspace, casts())
   → Enums/Industry.php (Title Case string-backed enum)
   Wire casts() to the enum. Verify factory generates a UUID (not an int).

4. Action/Service + AuditManager
   → Actions/CreateCompany.php, UpdateCompany.php, DeleteCompany.php
   Every write wraps CockroachRetry::transaction(); every action wraps AuditManager::run().
   List/show read-paths live in the controller (delegate to Eloquent directly or a
   dedicated query class) — no AuditManager needed for reads.

5. Controller + #[Authorize]
   → Http/Controllers/CompanyController.php
   Thin delegate; #[Authorize] on EVERY method. No conditionals.
   → Policies/CompanyPolicy.php
   Register the policy in AuthServiceProvider (or Laravel 13 auto-discovery).

6. Route entry
   → routes/api.php — append Route::apiResource(...)
   One line. Edit, not rewrite.

7. Pest tests
   → Tests/CompanyDataTest.php   (no-null view-shape + correct type assertions)
   → Tests/CompanyActionTest.php (action happy path + 40001 retry)
   → Tests/CompanyFeatureTest.php (cross-workspace 404, authz-negative, CRUD)
   Run: php artisan test --filter=Company
```

The contracts (`packages/contracts/src/generated.ts`) are regenerated by running `php artisan typescript:transform` after step 1 (and again after any Data class change). Never hand-edit the generated file.

## One agent = one `Domains/<Feature>/` folder

Each `laravel-module-builder` agent invocation owns exactly one `app/Domains/<Feature>/` folder and one entry in `database/migrations/`. It:

- Appends a single `Route::apiResource(...)` line to `routes/api.php`.
- Does **not** touch any other feature's folder, migration, or routes.
- Does **not** hand-author TypeScript — it runs `php artisan typescript:transform`.
- Reports the files created and the route line added.

Multiple features are built in parallel waves: independent domains in the same wave; domains that depend on another domain's Data class in a subsequent wave.

## Naming conventions

| Concern | Convention | Example |
|---|---|---|
| Domain folder | PascalCase | `Companies`, `EmailCampaigns` |
| PSR-4 namespace | `App\Domains\<Feature>\` | `App\Domains\Companies\Models` |
| Model class | PascalCase singular | `Company` |
| Controller | `<Entity>Controller` | `CompanyController` |
| Action | Verb + Entity | `CreateCompany`, `UpdateCompany` |
| Data class (view) | `<Entity>Data` | `CompanyData` |
| Data class (input) | `<Verb><Entity>Data` | `CreateCompanyData` |
| Policy | `<Entity>Policy` | `CompanyPolicy` |
| Enum | PascalCase, Title Case values | `Industry::Technology = 'Technology'` |
| Migration | `YYYY_MM_DD_HHMMSS_create_<table>_table` | standard Laravel |
| Audit action string | `<subject_lowercase>.<verb>` | `'company.create'` |
| Route resource name | kebab-case plural | `companies`, `email-campaigns` |

## Where shared types come from

Always import generated TS from `packages/contracts`:

```ts
// apps/web — always import from the generated package
import type { CompanyData, CreateCompanyData } from '@<scope>/contracts';
```

Never hand-author or copy-paste types in `apps/web`. The backend PHP Data class is the single source of truth; `php artisan typescript:transform` keeps the generated file in sync. See `references/laravel-data-contracts.md`.

## Anti-patterns

- Returning a raw model or array from a controller or action — always wrap in a Data class.
- Returning `null` / omitting a required field in a view Data class — see `references/view-data-pattern.md`.
- Forgetting `#[Authorize]` on any controller method — every endpoint must be authorized, including `GET /me` and list endpoints.
- Forgetting `AuditManager::run()` wrapping a mutation — compliance gaps appear silently.
- Accessing `app/Domains/OtherFeature/` from within a domain module — use that domain's Data class or inject its Action via the service container; never reach into another domain's folder directly.
- Putting business logic in controllers — delegate to an Action or Service.
- Direct `DB::` calls in controllers — go through an Action/Service.
- Omitting `BelongsToWorkspace` on a tenant-scoped model — every query against that table will leak cross-workspace rows.
- Hand-editing `packages/contracts/src/generated.ts` — regenerate with `php artisan typescript:transform`.
- Using a native PG enum type for enum columns — use STRING and a PHP string-backed enum to avoid CockroachDB cross-type-cast friction.
- Skipping the cross-workspace 404 Pest test — the mandatory isolation check that catches missing global scope or policy gaps.
