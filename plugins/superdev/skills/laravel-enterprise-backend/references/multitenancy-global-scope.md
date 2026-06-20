# Multi-tenancy via Eloquent global scope

How to enforce workspace isolation so every tenant-scoped query is filtered automatically, and a cross-workspace read returns a 404 (not a 403, not someone else's row). Read in Phase 4, alongside `auth-sanctum-permissions.md`.

## The model

Every tenant-scoped table carries a plain `workspace_id` reference column (no FK constraint, no cascade — D5). Isolation is enforced in two coordinated places:

1. **`ResolveWorkspace` middleware** — resolves the current workspace from the authenticated user and binds it into the container as `workspace.id`, once per request.
2. **`BelongsToWorkspace` trait** — adds an Eloquent global scope that appends `where workspace_id = <current>` to *every* query on the model, plus a `creating` hook that stamps `workspace_id` on inserts.

Because the global scope filters reads, a row from another workspace is simply *not in the result set*. The controller's `findOrFail()` then throws `ModelNotFoundException`, which Laravel renders as **404**. The caller can't tell whether the ID never existed or merely belongs to someone else — existence is not leaked. This is the Laravel equivalent of the Nest `tenantDb()` wrapper, except Eloquent gives us a middleware + global-scope pair that the Drizzle approach lacked.

## `BelongsToWorkspace` trait

Add this trait to every tenant-scoped model (`Company`, `Contact`, `Lead`, `Deal`, …). The `bootBelongsToWorkspace` method is auto-invoked by Eloquent's trait-booting convention.

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

Two behaviors fall out of this:

- **Reads are auto-filtered.** Every `Company::query()`, `Company::find()`, relationship load, and `withCount()` on a `BelongsToWorkspace` model carries the `workspace_id` predicate. You never write `->where('workspace_id', …)` by hand — and you can't forget to.
- **Writes are auto-stamped.** A `Company::create([...])` without an explicit `workspace_id` inherits the current request's workspace. Tenants cannot insert rows into another workspace, even by passing a forged `workspace_id` you don't bind (the create hook only fills when empty; the read scope still hides cross-tenant rows on the way back out).

The table-qualified column name (`$builder->getModel()->getTable().'.workspace_id'`) keeps the predicate unambiguous when the query joins or eager-loads other tables.

## `ResolveWorkspace` middleware

The scope reads `workspace.id` from the container; this middleware is what puts it there, per request, from the authenticated user.

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

The user's `workspace_id` comes from the authenticated user resolved per request — via a Sanctum token (decoupled Next.js) or a Fortify session cookie (Inertia) — see `auth-sanctum-permissions.md`. Unauthenticated requests never bind `workspace.id`, so the global scope's `if ($wid …)` guard leaves the query unscoped — which is fine because such routes are public (e.g. `/api/v1/health`) and don't touch tenant tables.

## Registering the middleware

Register `ResolveWorkspace` in `bootstrap/app.php` so it runs on the API group **after** authentication has populated `$request->user()`:

```php
// bootstrap/app.php
->withMiddleware(function (Illuminate\Foundation\Configuration\Middleware $middleware) {
    $middleware->api(append: [
        \App\Http\Middleware\ResolveWorkspace::class,
    ]);
})
```

Order matters: Sanctum's `auth:sanctum` resolves the user first; `ResolveWorkspace` then reads `$request->user()`. If you append it to the group, place it after the auth middleware on protected route groups (or apply it as route middleware on the authenticated `v1` group).

## Why this yields 404, not 403

Trace a cross-workspace read:

1. User in workspace B calls `GET /api/v1/companies/{id}` where `{id}` belongs to workspace A.
2. `ResolveWorkspace` binds `workspace.id = B`.
3. The controller calls `Company::findOrFail($id)`. The global scope rewrites this to `… where workspace_id = B and id = {id}`.
4. No row matches (the company's `workspace_id` is A) → empty result → `findOrFail()` throws `ModelNotFoundException` → Laravel renders **404**.

Returning 404 (rather than 403) is deliberate: a 403 would confirm the resource *exists*, leaking information across the tenant boundary. The not-found response is indistinguishable from a genuinely nonexistent ID.

## Mandatory cross-workspace Pest test

Write this before any feature module ships. It proves the global scope is wired and that the 404 (not 200, not 403) contract holds, plus the authorization-negative case for a viewer. Both use `actingAs($user, 'sanctum')` to authenticate against the Sanctum guard.

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

The first test proves tenancy isolation; the second proves the `spatie/laravel-permission` + Policy + `#[Authorize]` layer denies a least-privileged role (see `auth-sanctum-permissions.md`). Together they are the two non-negotiable security tests for any tenant-scoped feature.

### Fixture note: `withoutGlobalScopes()`

The test above creates `$companyA` *before* any request binds `workspace.id`, so the `creating` hook leaves the factory's explicit `workspace_id` (from `->for($wsA)`) intact and the read scope is inert during setup. But once a request has run — or when a test factory or assertion needs to set up / read rows belonging to a workspace **other than** the one currently bound — you must bypass the scope explicitly:

```php
// Set up or assert against another workspace's rows, ignoring the active scope:
$companyA = Company::withoutGlobalScopes()->create([
    'workspace_id' => $wsA->id,
    'name' => 'Acme',
    'industry' => 'Technology',
]);

// Assert the row still exists in the DB even though the request user (workspace B) gets a 404:
expect(Company::withoutGlobalScopes()->whereKey($companyA->id)->exists())->toBeTrue();
```

Without `withoutGlobalScopes()`, a setup helper running under a bound workspace would silently filter out — or refuse to read back — the cross-tenant fixture it is trying to create, making the test pass for the wrong reason. Use it only in test setup and cross-tenant assertions, never in application code.

## Anti-patterns

- ❌ Hand-writing `->where('workspace_id', $ws)` in queries. The whole point of the trait is that you never have to — and never forget to. If you're typing `workspace_id` in a feature query, the model is missing the trait.
- ❌ Forgetting to add `BelongsToWorkspace` to a new tenant-scoped model. Every model with a `workspace_id` column gets the trait. A model without it is a cross-tenant leak waiting to happen.
- ❌ Returning 403 (or 200) for a cross-workspace read. It must be **404** — existence is not leaked. Let the scope + `findOrFail()` produce it; don't special-case it.
- ❌ Trusting a client-supplied `workspace_id` in the request body. The `creating` hook stamps it from the bound workspace; never let the payload set it.
- ❌ Using `withoutGlobalScopes()` in application/controller code to "see across workspaces." It belongs in test setup and admin/console maintenance only.
- ❌ Resolving the workspace before authentication. `ResolveWorkspace` must run after `auth:sanctum` so `$request->user()` is populated.
- ❌ Adding a hard FK constraint or cascade on `workspace_id`. It's a plain reference column (D5); orphan cleanup is handled in application code.
- ❌ Shipping a feature without the cross-workspace 404 test. It is THE test that proves tenancy works.
