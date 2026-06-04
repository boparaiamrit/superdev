# Laravel Module Structure

Canonical folder layout for a feature domain module. Read in Phase 2 (planning) and Phase 5 (per-module generation).

## `apps/api/` top-level layout

```
apps/api/
├── composer.json
├── artisan
├── serverless.yml              ← added by laravel-bref-deploy skill
├── docker-compose.yml          ← Postgres + TimescaleDB for local dev
├── database/
│   └── migrations/             ← one migration file per domain entity
├── routes/
│   ├── api.php                 ← all v1 API routes; each controller referenced here
│   └── console.php             ← scheduler entries (cron expressions live here)
└── app/
    ├── Audit/                  ← #[Audit] attribute + AuditManager + AuditWrite job
    ├── Concerns/               ← HasUuids, BelongsToWorkspace traits
    ├── Support/                ← helpers
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

The `AuditWrite` job lives in `app/Jobs/AuditWrite.php` (shared, not per-domain). It inserts directly into the `audit_logs` hypertable via `DB::table('audit_logs')->insert([...])`. See `references/audit-attribute.md` for the full implementation.

## `app/Concerns/` — shared model traits

```
app/Concerns/
├── HasUuids.php            ← Laravel's built-in HasUuids trait alias (or extend it); UUID PKs as a preference
└── BelongsToWorkspace.php  ← global scope + creating hook; auto-filters all tenant queries
```

See `references/multitenancy-global-scope.md` for the full trait implementations.

## `app/Domains/<Feature>/` — feature domain modules

Every feature is a self-contained domain module at `app/Domains/<Feature>/` (PSR-4 namespace `App\Domains\<Feature>\`). This mirrors Nest's per-feature `src/modules/<feature>/` folder; a single `laravel-module-builder` agent owns exactly one domain folder and never touches another feature's files.

```
app/Domains/Companies/
├── Models/
│   └── Company.php                     ← Eloquent model; uses HasUuids + BelongsToWorkspace
├── Enums/
│   └── Industry.php                    ← PHP 8.1 string-backed Title Case enum
├── Http/
│   ├── Resources/
│   │   └── CompanyResource.php         ← API Resource presenter (JsonResource); the view-shape contract
│   ├── Requests/
│   │   ├── CreateCompanyRequest.php    ← FormRequest; rules() + authorize()
│   │   └── UpdateCompanyRequest.php    ← FormRequest (partial update)
│   └── Controllers/
│       └── CompanyController.php       ← thin; delegates to Action/Service; #[Authorize] on every method
├── Actions/                            ← (or Services/ — choose one per domain, be consistent)
│   ├── CreateCompany.php               ← single-responsibility action; wraps AuditManager::run()
│   ├── UpdateCompany.php
│   └── DeleteCompany.php
├── Policies/
│   └── CompanyPolicy.php               ← can(), update(), delete() — workspace condition lives here
├── Jobs/
│   └── (feature-specific background jobs, e.g. SendCompanyWelcomeEmail.php)
└── Tests/
    ├── CompanyContractTest.php         ← contract: Resource toArray() matches documented TS shape
    ├── CompanyActionTest.php           ← unit: action happy path
    └── CompanyFeatureTest.php          ← feature: cross-workspace 404, authz-negative, CRUD happy path
```

The hand-written TS contract lives outside the domain:

- **Decoupled Next.js:** `packages/contracts/src/companies.ts`
- **Inertia:** `resources/js/types/companies.ts`

### `Models/Company.php`

```php
// app/Domains/Companies/Models/Company.php
namespace App\Domains\Companies\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use App\Concerns\BelongsToWorkspace;
use App\Domains\Companies\Enums\Industry;

class Company extends Model
{
    use HasFactory, HasUuids, BelongsToWorkspace;

    protected $fillable = ['name', 'domain', 'industry', 'workspace_id'];

    protected function casts(): array
    {
        return [
            'industry' => Industry::class,
        ];
    }

    // Relationships: plain reference columns — no FK constraints (D5)
    public function contacts()
    {
        return $this->hasMany(\App\Domains\Contacts\Models\Contact::class, 'company_id');
    }
}
```

UUID PKs are a preference (`HasUuids`), not a constraint; real Postgres sequences are available if a feature wants them.

### `Enums/Industry.php`

```php
// app/Domains/Companies/Enums/Industry.php
namespace App\Domains\Companies\Enums;

enum Industry: string
{
    case Technology = 'Technology';
    case Healthcare = 'Healthcare';
    case Finance    = 'Finance';
    case Logistics  = 'Logistics';
    case Other      = 'Other';
}
```

DB column is a plain string (not a native PG enum type). Value = wire value = UI label; zero conversion code. The hand-written TS union mirrors these values exactly. See `references/enums-title-case.md`.

### `Http/Resources/CompanyResource.php`

```php
// app/Domains/Companies/Http/Resources/CompanyResource.php
namespace App\Domains\Companies\Http\Resources;

use Illuminate\Http\Resources\Json\JsonResource;

class CompanyResource extends JsonResource
{
    public function toArray($request): array
    {
        return [
            'id'            => $this->id,
            'name'          => $this->name,
            'domain'        => $this->domain,                      // nullable explicit, never omitted
            'industry'      => $this->industry,                    // Title-Case enum value = label
            'counts'        => [
                'contacts'   => (int) ($this->contacts_count ?? 0),   // withCount(); default 0
                'open_leads' => (int) ($this->open_leads_count ?? 0),
            ],
            'last_activity' => $this->lastActivityPayload(),      // discriminated union { kind, ... }
            'created_at'    => $this->created_at->toIso8601String(),
            'updated_at'    => $this->updated_at->toIso8601String(),
        ];
    }
}
```

Rule (same view-shape discipline as Nest's presenter): exhaustive fields, counts default 0, discriminated unions for variants, ISO dates, nullable explicit — so the frontend never needs `?.`/`??`.

### `Http/Requests/CreateCompanyRequest.php`

```php
// app/Domains/Companies/Http/Requests/CreateCompanyRequest.php
namespace App\Domains\Companies\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use App\Domains\Companies\Enums\Industry;
use Illuminate\Validation\Rules\Enum;

class CreateCompanyRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // #[Authorize] on the controller method handles the policy check
    }

    public function rules(): array
    {
        return [
            'name'     => ['required', 'string', 'max:255'],
            'domain'   => ['nullable', 'string', 'max:255'],
            'industry' => ['required', new Enum(Industry::class)],
        ];
    }
}
```

### `Actions/CreateCompany.php`

```php
// app/Domains/Companies/Actions/CreateCompany.php
namespace App\Domains\Companies\Actions;

use App\Audit\AuditManager;
use App\Domains\Companies\Http\Resources\CompanyResource;
use App\Domains\Companies\Http\Requests\CreateCompanyRequest;
use App\Domains\Companies\Models\Company;

final class CreateCompany
{
    public function __construct(private AuditManager $audit) {}

    public function handle(CreateCompanyRequest $request): CompanyResource
    {
        return $this->audit->run('company.create', 'Company', function () use ($request) {
            $company = Company::create($request->validated());
            return new CompanyResource($company->loadCount(['contacts']));
        });
    }
}
```

Every mutation goes through `AuditManager::run()`. Standard Postgres transactions work normally — no retry wrapper needed. See `references/audit-attribute.md`.

### `Http/Controllers/CompanyController.php`

```php
// app/Domains/Companies/Http/Controllers/CompanyController.php
namespace App\Domains\Companies\Http\Controllers;

use App\Domains\Companies\Actions\CreateCompany;
use App\Domains\Companies\Actions\UpdateCompany;
use App\Domains\Companies\Actions\DeleteCompany;
use App\Domains\Companies\Http\Requests\CreateCompanyRequest;
use App\Domains\Companies\Http\Requests\UpdateCompanyRequest;
use App\Domains\Companies\Http\Resources\CompanyResource;
use App\Domains\Companies\Models\Company;
use Illuminate\Routing\Attributes\Controllers\Authorize;

class CompanyController
{
    #[Authorize('viewAny', Company::class)]
    public function index()
    {
        return CompanyResource::collection(
            Company::query()
                ->withCount(['contacts', 'leads as open_leads_count'])
                ->paginate()
        );
    }

    #[Authorize('view', 'company')]
    public function show(Company $company)
    {
        return new CompanyResource($company->loadCount(['contacts']));
    }

    #[Authorize('create', Company::class)]
    public function store(CreateCompanyRequest $request, CreateCompany $action)
    {
        return $action->handle($request);
    }

    #[Authorize('update', 'company')]
    public function update(UpdateCompanyRequest $request, Company $company, UpdateCompany $action)
    {
        return $action->handle($request, $company);
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
- Validate (via FormRequest injection — Laravel resolves it before the method runs)
- Delegate to Action/Service
- Return Resource or `noContent()`

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

## Hand-written TS contract + contract test

There is no codegen pipeline. The TS type is authored by hand and kept in lockstep with the Resource; the Pest contract test is the guard.

```ts
// packages/contracts/src/companies.ts  (decoupled Next.js)
// resources/js/types/companies.ts      (Inertia)
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

See `references/api-resources.md` for the full Resource + contract test patterns.

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
└── 2026_06_01_000004_create_audit_logs_table.php   ← TimescaleDB hypertable; see audit-attribute.md
```

UUID PKs use Laravel's `HasUuids` trait (preference, not a constraint — Postgres sequences are also available). No foreign-key constraints — reference columns only (D5). See `references/postgres-timescale-eloquent.md`.

Example migration for a reference-field table:

```php
Schema::create('companies', function (Blueprint $table) {
    $table->uuid('id')->primary();                 // HasUuids fills it; sequences available too
    $table->uuid('workspace_id')->index();         // reference column — NO ->constrained(), NO cascade
    $table->string('name');
    $table->string('domain')->nullable();
    $table->string('industry');                    // plain string column; PHP enum handles casting
    $table->timestampsTz();
});
```

## Canonical per-module build order (Phase 5)

Work through each feature in this exact order. Each step depends on the previous.

```
1. Migration
   → database/migrations/YYYY_MM_DD_HHMMSS_create_companies_table.php
   UUID PK (HasUuids preference); workspace_id reference column (no FK);
   string column for enum fields; timestampsTz().

2. Model + enum casts
   → Models/Company.php (HasUuids, BelongsToWorkspace, casts())
   → Enums/Industry.php (Title Case string-backed enum)
   Wire casts() to the enum. Verify factory generates a UUID (not an int).

3. Http/Resources (presenter) + hand-written TS contract
   → Http/Resources/CompanyResource.php
   Exhaustive toArray(): every field explicit, counts default 0, ISO dates,
   discriminated union for variants. No optional/missing keys.
   → packages/contracts/src/companies.ts  (decoupled)
   → resources/js/types/companies.ts      (Inertia)
   The TS is authored by hand; the contract test (step 7) is the guard.

4. FormRequests (validation)
   → Http/Requests/CreateCompanyRequest.php
   → Http/Requests/UpdateCompanyRequest.php
   rules() for each input shape; authorize() returns true (policy in controller).

5. Action/Service + AuditManager
   → Actions/CreateCompany.php, UpdateCompany.php, DeleteCompany.php
   Every mutation wraps AuditManager::run(). List/show read-paths live in the
   controller (Eloquent with withCount() + withCount()) — no AuditManager for reads.

6. Controller + #[Authorize]
   → Http/Controllers/CompanyController.php
   Thin delegate; #[Authorize] on EVERY method. No conditionals.
   → Policies/CompanyPolicy.php
   Register in AuthServiceProvider (or Laravel 13 auto-discovery).

7. Route entry
   → routes/api.php — append Route::apiResource(...)
   One line. Edit, not rewrite.

8. Pest tests
   → Tests/CompanyContractTest.php  (Resource toArray() matches TS contract shape; no-null)
   → Tests/CompanyActionTest.php    (action happy path)
   → Tests/CompanyFeatureTest.php   (cross-workspace 404, authz-negative, CRUD happy path)
   Run: php artisan test --filter=Company
```

## One agent = one `Domains/<Feature>/` folder

Each `laravel-module-builder` agent invocation owns exactly one `app/Domains/<Feature>/` folder and one entry in `database/migrations/`. It:

- Appends a single `Route::apiResource(...)` line to `routes/api.php`.
- Does **not** touch any other feature's folder, migration, or routes.
- Authors the hand-written TS contract file for its feature only.
- Reports the files created and the route line added.

Multiple features are built in parallel waves: independent domains in the same wave; domains that depend on another domain's model in a subsequent wave.

## Naming conventions

| Concern | Convention | Example |
|---|---|---|
| Domain folder | PascalCase | `Companies`, `EmailCampaigns` |
| PSR-4 namespace | `App\Domains\<Feature>\` | `App\Domains\Companies\Models` |
| Model class | PascalCase singular | `Company` |
| Controller | `<Entity>Controller` | `CompanyController` |
| Action | Verb + Entity | `CreateCompany`, `UpdateCompany` |
| API Resource (presenter) | `<Entity>Resource` | `CompanyResource` |
| FormRequest (create) | `Create<Entity>Request` | `CreateCompanyRequest` |
| FormRequest (update) | `Update<Entity>Request` | `UpdateCompanyRequest` |
| Policy | `<Entity>Policy` | `CompanyPolicy` |
| Enum | PascalCase, Title Case values | `Industry::Technology = 'Technology'` |
| TS contract type | `<Entity>View` | `CompanyView` |
| TS contract file | `<feature>.ts` | `companies.ts` |
| Migration | `YYYY_MM_DD_HHMMSS_create_<table>_table` | standard Laravel |
| Audit action string | `<subject_lowercase>.<verb>` | `'company.create'` |
| Route resource name | kebab-case plural | `companies`, `email-campaigns` |

## Where shared types come from

Always import hand-written TS from `packages/contracts` (decoupled Next.js):

```ts
// apps/web — always import from the contracts package
import type { CompanyView, Industry } from '@<scope>/contracts/companies';
```

For Inertia, consume from `resources/js/types`:

```ts
import type { CompanyView } from '@/types/companies';
```

Never duplicate type definitions across apps. The API Resource's `toArray()` is the server-side source of truth; the hand-written TS contract must mirror it exactly; the contract test enforces the match. See `references/api-resources.md`.

## Anti-patterns

- Returning a raw model or array from a controller or action — always wrap in an API Resource.
- Returning `null` or omitting a required field in a Resource — see `references/view-data-pattern.md`.
- Forgetting `#[Authorize]` on any controller method — every endpoint must be authorized, including `GET /me` and list endpoints.
- Forgetting `AuditManager::run()` wrapping a mutation — compliance gaps appear silently.
- Accessing `app/Domains/OtherFeature/` from within a domain module — inject that domain's Action via the service container; never reach into another domain's folder directly.
- Putting business logic in controllers — delegate to an Action or Service.
- Direct `DB::` calls in controllers — go through an Action/Service.
- Omitting `BelongsToWorkspace` on a tenant-scoped model — every query against that table will leak cross-workspace rows.
- Skipping the contract test — it is the only automated guard keeping the Resource and the hand-written TS in sync.
- Skipping the cross-workspace 404 Pest test — the mandatory isolation check that catches missing global scope or policy gaps.
- Using a native PG enum type for enum columns — use a plain string column and a PHP string-backed enum; avoids type-cast friction and keeps migrations simple.
- Adding `->constrained()` or `->cascadeOnDelete()` to reference columns — integrity is enforced in app code, not by FK constraints (D5).
