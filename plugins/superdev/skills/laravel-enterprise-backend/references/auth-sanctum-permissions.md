# Auth + Sanctum + spatie/laravel-permission

How to implement Sanctum token authentication, workspace-scoped tenancy, and policy-based authorization with spatie/laravel-permission. Read in Phase 4.

## The model

Every authenticated request carries:

1. **User identity** — resolved from the Bearer token by Sanctum's `auth:sanctum` middleware
2. **Workspace context** — resolved from `$user->workspace_id` into the service container by `ResolveWorkspace` middleware so Eloquent global scopes can use it
3. **Roles + permissions** — spatie/laravel-permission DB-backed roles are seeded; **Policies** are the resolution point

Authorization happens in three layers:

- **`auth:sanctum`** — verifies the Bearer token, sets `$request->user()`
- **`ResolveWorkspace`** — binds `workspace.id` into the container so `BelongsToWorkspace` global scope auto-filters every query (see `multitenancy-global-scope.md`)
- **`#[Authorize]` attribute** (or `$this->authorize()`) — checks the Policy before the handler runs

Below all of that, the `BelongsToWorkspace` global scope enforces `workspace_id` on every Eloquent query as defense-in-depth.

---

## Install

```bash
composer require laravel/sanctum spatie/laravel-permission
php artisan vendor:publish --provider="Laravel\Sanctum\SanctumServiceProvider"
php artisan vendor:publish --provider="Spatie\Permission\PermissionServiceProvider"
php artisan migrate
```

Sanctum ships a `personal_access_tokens` table. spatie/laravel-permission ships `roles`, `permissions`, `model_has_roles`, `model_has_permissions`, and `role_has_permissions` tables.

---

## Sanctum: personal-access tokens for the cross-domain Next.js SPA

The Next.js app runs on a different domain, so Sanctum's cookie/SPA guard is unsuitable. Use **personal-access tokens** with `Authorization: Bearer <token>`.

### Middleware

Register in `bootstrap/app.php`:

```php
// bootstrap/app.php
->withMiddleware(function (\Illuminate\Foundation\Configuration\Middleware $middleware) {
    $middleware->api(append: [
        \App\Http\Middleware\ResolveWorkspace::class,
    ]);
    // auth:sanctum is registered automatically by Sanctum's service provider via the 'sanctum' guard.
    // Do NOT alias EnsureFrontendRequestsAreStateful here — that is the cookie/SPA middleware for
    // same-domain SPAs and is unsuitable for cross-domain Bearer token auth.
})
```

Apply to the API route group in `routes/api.php`:

```php
// routes/api.php
Route::middleware(['auth:sanctum'])->prefix('v1')->group(function () {
    // all protected endpoints live here
    Route::get('/me', [\App\Http\Controllers\Auth\MeController::class, 'show']);
    Route::apiResource('companies', \App\Domains\Companies\Http\CompanyController::class);
    // ...
});
```

### Token issuance on login

```php
// app/Domains/Auth/Http/AuthController.php
namespace App\Domains\Auth\Http;

use App\Domains\Auth\Http\Requests\LoginRequest;
use App\Domains\Auth\Http\Resources\TokenResource;
use App\Domains\Users\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Validation\ValidationException;

class AuthController
{
    // Login and logout are on a separate non-protected route group — no #[Authorize] here
    public function login(LoginRequest $request): TokenResource
    {
        $user = User::where('email', $request->validated('email'))->first();

        if (! $user || ! Hash::check($request->validated('password'), $user->password)) {
            throw ValidationException::withMessages([
                'email' => ['The provided credentials are incorrect.'],
            ]);
        }

        // Revoke any existing tokens for this device
        $user->tokens()->where('name', $request->validated('device_name'))->delete();

        $token = $user->createToken($request->validated('device_name'))->plainTextToken;

        return new TokenResource(['token' => $token, 'token_type' => 'Bearer']);
    }

    public function logout(Request $request): \Illuminate\Http\Response
    {
        // Revoke the token that was used to authenticate the request
        $request->user()->currentAccessToken()->delete();

        return response()->noContent();
    }
}
```

```php
// app/Domains/Auth/Http/Requests/LoginRequest.php
namespace App\Domains\Auth\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class LoginRequest extends FormRequest
{
    public function authorize(): bool { return true; }

    public function rules(): array
    {
        return [
            'email'       => ['required', 'email'],
            'password'    => ['required', 'string'],
            'device_name' => ['required', 'string', 'max:255'],
        ];
    }
}
```

```php
// app/Domains/Auth/Http/Resources/TokenResource.php
namespace App\Domains\Auth\Http\Resources;

use Illuminate\Http\Resources\Json\JsonResource;

class TokenResource extends JsonResource
{
    public function toArray($request): array
    {
        return [
            'token'      => $this->resource['token'],
            'token_type' => $this->resource['token_type'],
        ];
    }
}
```

`LoginRequest` is a FormRequest; `TokenResource` is an Eloquent API Resource. The hand-written TS contract lives in `packages/contracts/src/auth.ts` (decoupled Next.js) or `resources/js/types/auth.ts` (Inertia) — see `api-resources.md`.

### Token abilities (scopes)

For most applications a single token covers the user's full set of permitted actions — abilities are resolved at the Policy layer, not the token layer. If coarser-grained API key scoping is needed later, issue tokens with explicit abilities:

```php
// Issue a read-only API key
$token = $user->createToken('api-key', ['read'])->plainTextToken;
```

```php
// Check in a policy (rare)
if (! $request->user()->tokenCan('write')) {
    abort(403);
}
```

---

## Roles and permissions (spatie/laravel-permission)

### Permission matrix

Define permissions in a seeder. **Roles are an input; Policies resolve the answer.**

```php
// database/seeders/RolesAndPermissionsSeeder.php
namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Spatie\Permission\Models\Permission;
use Spatie\Permission\Models\Role;

class RolesAndPermissionsSeeder extends Seeder
{
    public function run(): void
    {
        // Reset cached roles and permissions
        app()[\Spatie\Permission\PermissionRegistrar::class]->forgetCachedPermissions();

        // Permission matrix — actions per subject
        $permissions = [
            'company.read', 'company.create', 'company.update', 'company.delete',
            'contact.read', 'contact.create', 'contact.update', 'contact.delete',
            'lead.read',    'lead.create',    'lead.update',    'lead.delete',
            'deal.read',    'deal.create',    'deal.update',    'deal.delete',
            'campaign.read','campaign.create','campaign.update','campaign.send',
            'mailbox.read', 'mailbox.create',
            'audit_log.read',
        ];

        foreach ($permissions as $name) {
            Permission::firstOrCreate(['name' => $name]);
        }

        // Roles and their granted permissions
        Role::firstOrCreate(['name' => 'Admin'])
            ->syncPermissions(Permission::all());

        Role::firstOrCreate(['name' => 'Operator'])
            ->syncPermissions([
                'company.read', 'company.create', 'company.update',
                'contact.read', 'contact.create', 'contact.update',
                'lead.read',    'lead.create',    'lead.update',
                'deal.read',    'deal.create',    'deal.update',
                'campaign.read','campaign.create','campaign.update','campaign.send',
                'mailbox.read',
            ]);

        Role::firstOrCreate(['name' => 'Pipeline'])
            ->syncPermissions([
                'company.read', 'contact.read',
                'lead.read',    'lead.update',
                'deal.read',    'deal.update',
            ]);

        Role::firstOrCreate(['name' => 'Viewer'])
            ->syncPermissions([
                'company.read', 'contact.read',
                'lead.read',    'deal.read', 'campaign.read',
            ]);
    }
}
```

### User model setup

```php
// app/Domains/Users/Models/User.php
namespace App\Domains\Users\Models;

use App\Concerns\BelongsToWorkspace;
use App\Concerns\HasUuidPrimaryKey;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Laravel\Sanctum\HasApiTokens;
use Spatie\Permission\Traits\HasRoles;

class User extends Authenticatable
{
    use HasApiTokens, HasRoles, BelongsToWorkspace, HasUuidPrimaryKey;

    protected $fillable = ['workspace_id', 'name', 'email', 'password'];

    protected $hidden = ['password', 'remember_token'];

    protected function casts(): array
    {
        return ['email_verified_at' => 'datetime', 'password' => 'hashed'];
    }
}
```

Roles must not be assigned by the user themselves. Role assignment is admin-only and goes through a dedicated service method, never a raw `assignRole()` call in a controller.

---

## Policies

Policies are the **resolution point**: a Policy method receives the authenticated user and the model instance, checks the spatie permission, and enforces any row-level conditions such as the workspace match.

### CompanyPolicy

```php
// app/Domains/Companies/Policies/CompanyPolicy.php
namespace App\Domains\Companies\Policies;

use App\Domains\Companies\Models\Company;
use App\Domains\Users\Models\User;
use Illuminate\Auth\Access\HandlesAuthorization;

class CompanyPolicy
{
    use HandlesAuthorization;

    public function viewAny(User $user): bool
    {
        return $user->can('company.read');
    }

    public function view(User $user, Company $company): bool
    {
        // The BelongsToWorkspace global scope will have already filtered the query;
        // this workspace check is defense-in-depth for direct Policy calls.
        return $user->can('company.read')
            && $user->workspace_id === $company->workspace_id;
    }

    public function create(User $user): bool
    {
        return $user->can('company.create');
    }

    public function update(User $user, Company $company): bool
    {
        return $user->can('company.update')
            && $user->workspace_id === $company->workspace_id;
    }

    public function delete(User $user, Company $company): bool
    {
        return $user->can('company.delete')
            && $user->workspace_id === $company->workspace_id;
    }
}
```

Register in `app/Providers/AppServiceProvider.php`:

```php
use Illuminate\Support\Facades\Gate;
use App\Domains\Companies\Models\Company;
use App\Domains\Companies\Policies\CompanyPolicy;

Gate::policy(Company::class, CompanyPolicy::class);
```

Or use automatic policy discovery (Laravel 13 default) — Laravel resolves `CompanyPolicy` from `Company` by convention when both live in expected namespaces.

---

## Enforcement via `#[Authorize]`

Laravel 13 ships a first-party `#[Authorize]` PHP attribute for controllers. This is the **preferred** enforcement mechanism — it keeps authorization declarative and colocated with the route handler.

```php
// app/Domains/Companies/Http/CompanyController.php
namespace App\Domains\Companies\Http;

use App\Domains\Companies\Actions\CreateCompany;
use App\Domains\Companies\Actions\UpdateCompany;
use App\Domains\Companies\Http\Requests\StoreCompanyRequest;
use App\Domains\Companies\Http\Requests\UpdateCompanyRequest;
use App\Domains\Companies\Http\Resources\CompanyResource;
use App\Domains\Companies\Models\Company;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Routing\Attributes\Controllers\Authorize;

class CompanyController
{
    #[Authorize('viewAny', Company::class)]
    public function index(): AnonymousResourceCollection
    {
        return CompanyResource::collection(
            Company::query()
                ->withCount(['contacts', 'openLeads as open_leads_count'])
                ->paginate(),
        );
    }

    #[Authorize('view', 'company')]   // 'company' is the route parameter name
    public function show(Company $company): CompanyResource
    {
        return new CompanyResource($company->loadCount('contacts'));
    }

    #[Authorize('create', Company::class)]
    public function store(
        StoreCompanyRequest $request,
        CreateCompany $action,
    ): CompanyResource {
        return new CompanyResource($action->execute($request->validated()));
    }

    #[Authorize('update', 'company')]
    public function update(
        UpdateCompanyRequest $request,
        Company $company,
        UpdateCompany $action,
    ): CompanyResource {
        return new CompanyResource($action->execute($request->validated(), $company));
    }

    #[Authorize('delete', 'company')]
    public function destroy(Company $company): \Illuminate\Http\Response
    {
        $company->delete();
        return response()->noContent();
    }
}
```

When a policy check fails, Laravel throws `AuthorizationException` and the global handler (configured in `bootstrap/app.php`) converts it to a `403` with the standard error shape (see `error-handling.md`).

### `$this->authorize()` alternative

Use `$this->authorize()` when the authorization decision depends on data that is only available inside the handler body — for instance, checking a loaded sub-resource. This requires the controller to use the `AuthorizesRequests` trait (or extend `App\Http\Controllers\Controller` which includes it):

```php
public function addContact(Company $company, \App\Domains\Contacts\Models\Contact $contact): \App\Domains\Companies\Http\Resources\CompanyResource
{
    $this->authorize('update', $company);   // explicit call instead of attribute

    // ... add the contact
    return new \App\Domains\Companies\Http\Resources\CompanyResource(
        $company->fresh()->loadCount('contacts')
    );
}
```

Both forms call the same Policy method; the attribute is preferred for standard CRUD because it is evaluated before the handler body runs.

---

## `GET /me`: authorize every endpoint

The rule is explicit: **every endpoint — including `GET /me` — must have authorization applied.** There is no such thing as a "safe" endpoint that can skip the check.

```php
// app/Http/Controllers/Auth/MeController.php
namespace App\Http\Controllers\Auth;

use App\Domains\Users\Http\Resources\UserResource;
use Illuminate\Http\Request;
use Illuminate\Routing\Attributes\Controllers\Authorize;

class MeController
{
    #[Authorize('view', 'user')]   // UserPolicy::view — at minimum checks auth()->check()
    public function show(Request $request): UserResource
    {
        return new UserResource($request->user());
    }
}
```

`UserPolicy::view` is the minimal gate: the user is authenticated (Sanctum already ensured that via `auth:sanctum`), so the policy confirms the token's owner matches the resource. This prevents a valid token for user A being used to fetch user B by changing the route parameter.

---

## Authorize every endpoint — checklist

Before any controller ships, verify:

1. Every public method in the controller has either `#[Authorize(...)]` or an explicit `$this->authorize(...)` call.
2. The login and logout endpoints are on a **separate, non-protected route group** — they must NOT be inside the `auth:sanctum` middleware group.
3. Every Policy class is registered (or discovered) and has methods for every action the controller exposes.
4. The cross-workspace 404 test and the viewer-negative (403) test from `multitenancy-global-scope.md` pass.

---

## Cross-workspace and viewer tests

Cross-workspace isolation tests and the viewer-cannot-create test are defined in `multitenancy-global-scope.md`. They must pass before any feature module ships. This file owns only the auth layer tests shown below.

### Auth layer Pest tests

```php
// tests/Feature/Auth/AuthControllerTest.php
use App\Domains\Users\Models\User;

it('issues a Bearer token on valid credentials', function () {
    $user = User::factory()->create(['password' => bcrypt('secret')]);

    $response = $this->postJson('/api/v1/auth/login', [
        'email'       => $user->email,
        'password'    => 'secret',
        'device_name' => 'test',
    ]);

    $response->assertOk()
        ->assertJsonStructure(['token', 'token_type'])
        ->assertJsonPath('token_type', 'Bearer');
});

it('rejects invalid credentials with 422', function () {
    $user = User::factory()->create();

    $this->postJson('/api/v1/auth/login', [
        'email'    => $user->email,
        'password' => 'wrong',
        'device_name' => 'test',
    ])->assertStatus(422);
});

it('returns 401 for unauthenticated request to a protected endpoint', function () {
    $this->getJson('/api/v1/me')->assertUnauthorized();
});

it('GET /me returns the authenticated user', function () {
    $user = User::factory()->create();

    $this->actingAs($user, 'sanctum')
        ->getJson('/api/v1/me')
        ->assertOk()
        ->assertJsonPath('id', $user->id);
});

it('logout revokes the current token', function () {
    $user = User::factory()->create();

    $token = $user->createToken('test')->plainTextToken;

    $this->withToken($token)
        ->postJson('/api/v1/auth/logout')
        ->assertNoContent();

    $this->withToken($token)
        ->getJson('/api/v1/me')
        ->assertUnauthorized();
});
```

---

## Anti-patterns

- **Hand-rolling role checks in controllers or services.** `if ($user->hasRole('Admin'))` in business logic is a Policy bypass. Put every condition in the Policy method.
- **Skipping `#[Authorize]` on "obviously safe" endpoints.** `GET /me`, list endpoints, and read-only routes must all be authorized. Explicit is always safer than implicit.
- **Returning the User model or a raw array from `GET /me`.** Return a `UserResource` (Eloquent API Resource); the TS type is hand-written in the contract (no codegen).
- **Storing tokens in `localStorage` on the frontend.** Use `Authorization: Bearer` in memory (React state / a secure store) for the access token. Never expose tokens to localStorage or cookies without `HttpOnly`.
- **Issuing tokens with unlimited lifetime.** Set an expiry on personal-access tokens: `$user->createToken('name', ['*'], now()->addDays(30))`.
- **Assigning roles from user-controlled input.** Role assignment is admin-only via a protected endpoint. Never expose `assignRole()` to an unauthenticated or unprivileged path.
- **Using spatie's `gate`-level permission checks alone without workspace conditions.** `$user->can('company.update')` passes for any Admin regardless of workspace. Always pair with the workspace condition inside the Policy method, as shown in `CompanyPolicy::update` above.
- **Forgetting the cross-workspace test.** The mandatory 404 isolation test in `multitenancy-global-scope.md` must be the first test written for any new feature, before any other module work begins.
