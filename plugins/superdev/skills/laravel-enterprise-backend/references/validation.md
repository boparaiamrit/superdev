# Validation

How to wire input validation into Laravel 13 so that one class carries input rules, response shape, and the TypeScript contract. Read in Phase 5 when generating feature modules.

## One class, three jobs

In the Nest stack, `nestjs-zod` shares a Zod schema between the DTO (input validation), the response presenter, and the frontend type. The Laravel equivalent is `spatie/laravel-data`:

- **Input rules** — a `rules()` static method on the same Data class gates bad requests at the controller boundary.
- **Response shape** — the controller returns the Data object directly; it serialises to JSON automatically.
- **TypeScript contract** — `php artisan typescript:transform` reads `#[TypeScript]`-annotated Data classes and emits a union type into `packages/contracts/src/generated.ts`.

A single class in `app/Domains/<Feature>/Data/` owns all three. There is no separate DTO file, no hand-written TS, and no schema duplication.

## Input Data classes

Name input classes after the action: `CreateCompanyData`, `UpdateCompanyData`, `ListCompaniesData`. They live alongside view Data classes in the same `Data/` folder. The class is used as a controller parameter — Laravel resolves and validates it automatically when you type-hint it in the method signature.

```php
// app/Domains/Companies/Data/CreateCompanyData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\LaravelData\Attributes\Validation\Max;
use Spatie\LaravelData\Attributes\Validation\Min;
use Spatie\LaravelData\Attributes\Validation\Rule;
use Spatie\TypeScriptTransformer\Attributes\TypeScript;
use App\Domains\Companies\Enums\Industry;

#[TypeScript]
class CreateCompanyData extends Data
{
    public function __construct(
        #[Min(1), Max(120)]
        public string $name,

        #[Rule(['nullable', 'regex:/^[a-z0-9.-]+\.[a-z]{2,}$/i'])]
        public ?string $domain,

        public Industry $industry,         // Title Case enum; enum type-hint validates it automatically
    ) {}
}
```

A few points about this class:

- **The enum is validated for free.** Laravel resolves `Industry $industry` and rejects any value that is not a valid `Industry` case before your controller body runs. No extra `Rule::enum(Industry::class)` needed.
- **`?string $domain` is explicitly nullable.** The client must send `"domain": null` to express absence; the field is never silently missing from the payload.
- **No `$fillable` bypass.** The Data class is constructed from the request; it never calls `Model::fill()` directly. The action/service maps from the Data object to the model.

## The `rules()` method for cross-field rules

For rules that span multiple fields — uniqueness within a workspace, conditional requirements, custom error messages — add a `public static function rules(): array` method to the Data class. spatie/laravel-data merges these with the attribute-level rules automatically before validating the request:

```php
// app/Domains/Companies/Data/CreateCompanyData.php
// Add this import at the top of the file (after namespace declaration):
// use Illuminate\Validation\Rule as LaravelRule;

// Add this method inside the CreateCompanyData class:
public static function rules(): array
{
    // Workspace-scoped uniqueness: domain must be unique within the current workspace.
    $workspaceId = app()->bound('workspace.id') ? app('workspace.id') : null;

    return [
        'domain' => [
            'nullable',
            'regex:/^[a-z0-9.-]+\.[a-z]{2,}$/i',
            LaravelRule::unique('companies', 'domain')
                ->where('workspace_id', $workspaceId)
                ->whereNull('deleted_at'),
        ],
    ];
}
```

Keep `rules()` focused on cross-field and database-level constraints. Attribute-based rules handle the straightforward per-field checks.

## Using the input class in a controller

Type-hint the input Data class as a parameter. Laravel resolves it from the request body, runs validation, and injects the typed object. No manual `$request->validate()` call needed.

```php
// app/Domains/Companies/Http/CompanyController.php
namespace App\Domains\Companies\Http;

use App\Domains\Companies\Actions\CreateCompanyAction;
use App\Domains\Companies\Data\CreateCompanyData;
use App\Domains\Companies\Data\CompanyData;
use Illuminate\Routing\Attributes\Controllers\Authorize;

class CompanyController
{
    #[Authorize('create', \App\Domains\Companies\Models\Company::class)]
    public function store(CreateCompanyData $input, CreateCompanyAction $action): CompanyData
    {
        return $action->handle($input);
    }
}
```

The action calls `AuditManager::run()` around the write. See `references/audit-attribute.md` for the pattern. The controller never touches `$request` directly — the Data class carries the validated payload.

## Query/filter Data classes

For list endpoints, define a separate filter class. Mark fields as optional with a default so the URL can omit them.

```php
// app/Domains/Companies/Data/ListCompaniesData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\LaravelData\Attributes\Validation\IntegerType;
use Spatie\LaravelData\Attributes\Validation\Min;
use Spatie\LaravelData\Attributes\Validation\Max;
use Spatie\TypeScriptTransformer\Attributes\TypeScript;
use App\Domains\Companies\Enums\Industry;

#[TypeScript]
class ListCompaniesData extends Data
{
    public function __construct(
        public ?string $search = null,
        public ?Industry $industry = null,

        #[IntegerType, Min(1)]
        public int $page = 1,

        #[IntegerType, Min(1), Max(100)]
        public int $per_page = 20,
    ) {}
}
```

Use it as a query-string input in the controller:

```php
use Spatie\LaravelData\WithData;

#[Authorize('viewAny', \App\Domains\Companies\Models\Company::class)]
public function index(ListCompaniesData $filters): \Spatie\LaravelData\PaginatedDataCollection
{
    return CompanyData::collect(
        Company::query()
            ->when($filters->search, fn ($q, $s) => $q->where('name', 'ilike', "%$s%"))
            ->when($filters->industry, fn ($q, $i) => $q->where('industry', $i))
            ->withCount(['contacts', 'openLeads as open_leads_count'])
            ->paginate($filters->per_page, page: $filters->page),
        \Spatie\LaravelData\PaginatedDataCollection::class,
    );
}
```

## FormRequest fallback

Use `FormRequest` when the validation logic is too imperative for a Data class — multi-step wizards, file uploads, or deeply conditional rules that read from multiple DB tables.

```php
// app/Domains/Companies/Http/Requests/BulkImportCompaniesRequest.php
namespace App\Domains\Companies\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class BulkImportCompaniesRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()->can('company.import');
    }

    public function rules(): array
    {
        return [
            'file'          => ['required', 'file', 'mimes:csv', 'max:10240'],
            'dedup_field'   => ['required', 'in:domain,name'],
            'notify_on_end' => ['boolean'],
        ];
    }
}
```

The FormRequest is the controller parameter in place of the Data class. Prefer the Data class for standard create/update inputs — FormRequest is the escape hatch, not the default.

## Mapping validation errors to the error-code contract

When a Data class or FormRequest fails validation, Laravel throws a `ValidationException`. The global exception handler (see `references/error-handling.md`) catches it and returns a 422 response in the shared error envelope:

```json
{
  "code": "VALIDATION_FAILED",
  "message": "Request validation failed",
  "details": {
    "name":     ["The name field is required."],
    "industry": ["The selected industry is invalid."]
  },
  "request_id": "req_01HXYZ"
}
```

The handler normalises this in `bootstrap/app.php` under `->withExceptions(...)`. You do not throw or catch `ValidationException` in your controllers or services — let it propagate.

For domain-specific validation failures that are not field-level (for example, attempting to exceed a workspace's company limit), throw a typed exception with the correct error code:

```php
use Illuminate\Http\Exceptions\HttpResponseException;
use Illuminate\Http\JsonResponse;

// In an action/service:
if ($workspace->companies()->count() >= $workspace->company_limit) {
    throw new \App\Exceptions\WorkspaceLimitExceededException('companies');
}
```

```php
// app/Exceptions/WorkspaceLimitExceededException.php
namespace App\Exceptions;

use Symfony\Component\HttpKernel\Exception\HttpException;

class WorkspaceLimitExceededException extends HttpException
{
    public function __construct(string $resource)
    {
        parent::__construct(
            422,
            "Workspace limit reached for: $resource",
            context: ['code' => 'WORKSPACE_LIMIT_EXCEEDED', 'resource' => $resource],
        );
    }
}
```

The global handler maps this to `{ code: "WORKSPACE_LIMIT_EXCEEDED", ... }`. The frontend imports the stable `code` string from `packages/contracts/src/errors.ts` and switches on it for context-aware UI — never pattern-match on `message`.

## TypeScript emission

Both input and view Data classes annotated with `#[TypeScript]` are picked up by `typescript:transform`. The emitted TS for `CreateCompanyData` is a plain interface — no Zod, no runtime parsing. The frontend uses it only for compile-time type safety:

```ts
// packages/contracts/src/generated.ts (emitted — do not hand-edit)
export interface CreateCompanyData {
    name: string;
    domain: string | null;
    industry: Industry;
}

export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other';
```

The Next.js app imports `CreateCompanyData` as a type for its form state and fetch calls. There is no Zod `.parse()` call on the frontend — view-shape correctness is enforced server-side by the Data class and the no-null Pest test (see `references/view-data-pattern.md`).

## Pest tests for validation

Write at least one feature test per input class that asserts the happy path returns 201/200, and one per validation rule that asserts 422 with the correct field in `details`.

```php
// tests/Feature/Companies/CreateCompanyTest.php
use App\Domains\Companies\Models\Company;

it('creates a company with valid input', function () {
    $user = loginAsOperator();   // helper that actingAs + sets workspace scope

    $response = $this->postJson('/api/v1/companies', [
        'name'     => 'Acme Corp',
        'domain'   => 'acme.io',
        'industry' => 'Technology',
    ]);

    $response->assertStatus(201);
    expect($response->json('name'))->toBe('Acme Corp')
        ->and($response->json('industry'))->toBe('Technology');
});

it('rejects an invalid industry value', function () {
    $user = loginAsOperator();

    $response = $this->postJson('/api/v1/companies', [
        'name'     => 'Acme Corp',
        'industry' => 'TECHNOLOGY',   // wrong case — not a valid enum value
    ]);

    $response->assertStatus(422)
        ->assertJsonPath('code', 'VALIDATION_FAILED')
        ->assertJsonStructure(['details' => ['industry']]);
});

it('rejects a duplicate domain within the same workspace', function () {
    $user = loginAsOperator();
    Company::factory()->create(['domain' => 'taken.io', 'workspace_id' => $user->workspace_id]);

    $response = $this->postJson('/api/v1/companies', [
        'name'     => 'Another Co',
        'domain'   => 'taken.io',
        'industry' => 'Finance',
    ]);

    $response->assertStatus(422)
        ->assertJsonPath('code', 'VALIDATION_FAILED')
        ->assertJsonStructure(['details' => ['domain']]);
});
```

## Anti-patterns

- **Returning a model from the controller instead of a Data object.** The validation class and the presenter are one class — call `CompanyData::fromModel($company)` before returning. Never return an Eloquent model or a plain array.
- **Using `request()->validate()` or `$request->validate()` inside a controller.** Type-hint the Data class parameter instead. The controller body never calls `validate()`.
- **Hand-editing `packages/contracts/src/generated.ts`.** The file is generated by `php artisan typescript:transform`. Any manual edit is overwritten on the next run. If the emitted type is wrong, fix the PHP Data class.
- **Skipping `#[TypeScript]` on input Data classes.** The frontend needs the input type for typed form submissions. Add the attribute to every public-facing input class.
- **Using `Form::old()` / session flashing for API validation errors.** This is a JSON API — validation errors go in the response body as `details`, not in the session.
- **Duplicating rules between an input Data class and a FormRequest for the same endpoint.** Pick one. Use the Data class by default; use FormRequest only when the input can't be expressed as a constructor-parameter Data class (file uploads, deeply imperative logic).
- **Catching `ValidationException` in the controller.** Let it propagate to the global handler in `references/error-handling.md`, which normalises it into the error envelope.
