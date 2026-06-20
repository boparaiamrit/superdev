# Validation

How to wire input validation into Laravel 13 using FormRequests. Read in Phase 5 when generating feature modules.

## One class per action

Validation lives in a dedicated `FormRequest` class named after the action: `CreateCompanyRequest`, `UpdateCompanyRequest`, `ListCompaniesRequest`. Each class lives in `app/Domains/<Feature>/Http/Requests/`. The controller type-hints the request class — Laravel resolves it, runs `authorize()`, validates the rules, and injects the populated request object. The controller body never calls `validate()` manually.

The request is validated **before** the controller body runs. By the time your controller receives the request, all input is clean and typed. The API Resource (`CompanyResource`) is only instantiated after the action/service completes — validation precedes the presenter.

## CreateCompanyRequest

```php
// app/Domains/Companies/Http/Requests/CreateCompanyRequest.php
namespace App\Domains\Companies\Http\Requests;

use App\Domains\Companies\Enums\Industry;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class CreateCompanyRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()->can('create', \App\Domains\Companies\Models\Company::class);
    }

    public function rules(): array
    {
        $workspaceId = $this->user()->workspace_id;

        return [
            'name'     => ['required', 'string', 'min:1', 'max:120'],
            'domain'   => [
                'nullable',
                'string',
                'regex:/^[a-z0-9.-]+\.[a-z]{2,}$/i',
                Rule::unique('companies', 'domain')
                    ->where('workspace_id', $workspaceId)
                    ->whereNull('deleted_at'),
            ],
            'industry' => ['required', Rule::enum(Industry::class)],
        ];
    }
}
```

A few points about this class:

- **`Rule::enum(Industry::class)`** rejects any value that is not a valid `Industry` case (e.g. `'TECHNOLOGY'` fails; `'Technology'` passes). Title-Case enum values are the documented public API — the error message will say `"The selected industry is invalid."`.
- **`'domain' => ['nullable', ...]`** the client must send `"domain": null` to express absence. The field is never silently missing from the payload.
- **`authorize()`** delegates to the Policy. For standard CRUD you can also use the `#[Authorize]` attribute on the controller method (see `references/auth-sanctum-permissions.md`) — pick one approach per endpoint, not both.

## Using the request in the controller

Type-hint the FormRequest as the first parameter. The second parameter injects the action/service. The controller returns the API Resource, never a raw model or array.

```php
// app/Domains/Companies/Http/CompanyController.php
namespace App\Domains\Companies\Http;

use App\Domains\Companies\Actions\CreateCompanyAction;
use App\Domains\Companies\Http\Requests\CreateCompanyRequest;
use App\Domains\Companies\Http\Resources\CompanyResource;
use Illuminate\Routing\Attributes\Controllers\Authorize;

class CompanyController
{
    #[Authorize('create', \App\Domains\Companies\Models\Company::class)]
    public function store(CreateCompanyRequest $request, CreateCompanyAction $action): CompanyResource
    {
        $company = $action->handle($request->validated());

        return new CompanyResource($company->loadCount('contacts'));
    }
}
```

`$request->validated()` returns only the keys declared in `rules()` — no raw user input leaks through. The action wraps the write inside `AuditManager::run()`; see `references/audit-attribute.md`.

## Query/filter requests

For list endpoints, define a separate request class. Mark fields as optional with defaults so the URL can omit them.

```php
// app/Domains/Companies/Http/Requests/ListCompaniesRequest.php
namespace App\Domains\Companies\Http\Requests;

use App\Domains\Companies\Enums\Industry;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class ListCompaniesRequest extends FormRequest
{
    public function authorize(): bool { return true; }  // Policy check is on the controller method

    public function rules(): array
    {
        return [
            'search'   => ['nullable', 'string', 'max:200'],
            'industry' => ['nullable', Rule::enum(Industry::class)],
            'page'     => ['nullable', 'integer', 'min:1'],
            'per_page' => ['nullable', 'integer', 'min:1', 'max:100'],
        ];
    }

    // Coerce defaults after validation so the controller can read them cleanly.
    public function page(): int     { return (int) ($this->input('page', 1)); }
    public function perPage(): int  { return (int) ($this->input('per_page', 20)); }
}
```

Controller usage:

```php
#[Authorize('viewAny', \App\Domains\Companies\Models\Company::class)]
public function index(ListCompaniesRequest $request): \Illuminate\Http\Resources\Json\AnonymousResourceCollection
{
    $companies = Company::query()
        ->when($request->input('search'), fn ($q, $s) => $q->where('name', 'ilike', "%$s%"))
        ->when($request->input('industry'), fn ($q, $i) => $q->where('industry', $i))
        ->withCount(['contacts', 'leads as open_leads_count'])
        ->paginate($request->perPage(), page: $request->page());

    return CompanyResource::collection($companies);
}
```

## Custom error messages and attribute names

Override `messages()` and `attributes()` in the request to control the user-visible validation text:

```php
public function messages(): array
{
    return [
        'industry.Illuminate\Validation\Rules\Enum' => 'Industry must be one of: Technology, Healthcare, Finance, Logistics, Other.',
    ];
}

public function attributes(): array
{
    return [
        'per_page' => 'page size',
    ];
}
```

## Mapping validation errors to the error-code contract

When a FormRequest fails validation, Laravel throws a `ValidationException`. The global exception handler (see `references/error-handling.md`) catches it and returns a 422 response in the shared error envelope:

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

The handler normalises this in `bootstrap/app.php` under `->withExceptions(...)`. You do not throw or catch `ValidationException` in your controllers or services — let it propagate. The `VALIDATION_FAILED` code string is defined in `App\Support\ErrorCode::ValidationFailed` (PHP) and in `packages/contracts/src/errors.ts` (TS); the frontend switches on the stable `code`, never on `message`.

For domain-specific violations that are not field-level (for example, attempting to exceed a workspace's company limit), throw a `DomainException` with the correct error code from the service/action:

```php
use App\Exceptions\DomainException;
use App\Support\ErrorCode;

// In an action/service:
if ($workspace->companies()->count() >= $workspace->company_limit) {
    throw new DomainException(
        errorCode:  ErrorCode::Conflict,
        message:    'Workspace company limit reached',
        details:    ['limit' => $workspace->company_limit],
        httpStatus: 422,
    );
}
```

## Pest tests for validation

Write at least one feature test per request that asserts the happy path returns 201/200, and one per validation rule that asserts 422 with the correct field in `details`.

```php
// tests/Feature/Companies/CreateCompanyTest.php
use App\Domains\Companies\Models\Company;

it('creates a company with valid input', function () {
    $user = loginAsOperator();   // helper: actingAs + sets workspace scope

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
    loginAsOperator();

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

it('requires name and industry', function () {
    loginAsOperator();

    $this->postJson('/api/v1/companies', [])
        ->assertStatus(422)
        ->assertJsonPath('code', 'VALIDATION_FAILED')
        ->assertJsonStructure(['details' => ['name', 'industry']]);
});
```

## Anti-patterns

- **Calling `$request->validate()` or `request()->validate()` inside a controller body.** Type-hint the FormRequest as the controller parameter instead. Validation runs before the controller body — never duplicate it inside the method.
- **Returning a raw model or array from the controller.** The controller always returns a `CompanyResource` (or collection); `$request->validated()` feeds the action, and the action returns a model that is then wrapped by the Resource.
- **Accessing `$request->all()` or `$request->input()` without going through `validated()` first.** Use `$request->validated()` to get only the declared, clean keys. Raw access bypasses the declared rules.
- **Skipping `authorize()`.** The method must return `true` or delegate to a Policy. An empty `return true;` is acceptable only when authorization is handled exclusively by `#[Authorize]` on the controller method — document which approach is in use.
- **Duplicating rules between a FormRequest and an inline `validate()` call for the same endpoint.** There must be exactly one place where an endpoint's rules are declared.
- **Catching `ValidationException` in the controller.** Let it propagate to the global handler in `references/error-handling.md`, which normalises it into the error envelope.
- **Using `Form::old()` / session flashing for API validation errors.** This is a JSON API — validation errors go in the response body as `details`, not in the session.
- **Putting domain-limit logic inside `rules()`.** Business-rule violations (quota exceeded, duplicate slug within a tenant) belong in the action/service as a `DomainException`, not as a Closure rule in the FormRequest.
