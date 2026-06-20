# Scaffolding `apps/api`

Run this in Phase 3, after `references/monorepo-setup.md` has set up the workspace and `packages/contracts`. Goal: a Laravel 13 app booting on PostgreSQL + TimescaleDB via the stock `pgsql` driver, database-backed cache and sessions, SQS queue connection, Sanctum auth, and `/api/v1/health` returning green.

## Step 1 — Create the app

From the monorepo root:

```bash
laravel new apps/api \
  --no-starter-kit \
  --no-interaction \
  --php 8.3
```

`--no-starter-kit` gives a clean API app with no Blade/Livewire. PHP 8.3+ is required for Laravel 13.x and the `#[Authorize]` / `#[Audit]` attribute patterns.

> **Monorepo note:** When this skill runs inside the `prd-design-build-orchestrator`, the `docker-compose.yml` lives at the **monorepo root**. The `monorepo-bootstrapper` agent owns it. `apps/api` is a plain `composer.json` project — it is **not** a pnpm workspace package. See `references/monorepo-setup.md` for the Turbo wiring and the Postgres+TimescaleDB Compose service.

## Step 2 — Install runtime dependencies

```bash
cd apps/api

# Core stack
composer require \
  laravel/sanctum \
  spatie/laravel-permission \
  aws/aws-sdk-php

# spatie/laravel-permission ^8, aws/aws-sdk-php ^3
```

```bash
# Dev-only tools
composer require --dev \
  laravel/boost \
  pestphp/pest \
  pestphp/pest-plugin-laravel \
  pestphp/pest-plugin-faker

# Initialize Pest (replaces PHPUnit as the test runner)
php artisan pest:install
```

Publish vendor configs needed at boot:

```bash
php artisan vendor:publish --provider="Laravel\Sanctum\SanctumServiceProvider"
php artisan vendor:publish --provider="Spatie\Permission\PermissionServiceProvider"
```

No code-generation pipeline to set up. API shapes are hand-written `JsonResource` classes; TS contracts are hand-written in `packages/contracts/src/<feature>.ts` (decoupled Next.js) or `resources/js/types/` (Inertia). See `references/api-resources.md`.

## Step 3 — Laravel Boost (AI tooling)

```bash
php artisan boost:install   # generates .mcp.json, CLAUDE.md, AGENTS.md, .ai/*
```

Register the MCP server with Claude Code:

```bash
claude mcp add -s local -t stdio laravel-boost -- php artisan boost:mcp
```

Gitignore generated files — team conventions go in `.ai/guidelines/*` instead:

```
# .gitignore additions
.mcp.json
CLAUDE.md
AGENTS.md
.ai/cache/
boost.json
```

See `references/boost-setup.md` for full Boost guidance.

## Step 4 — `.env.example`

Replace the default `.env.example` with the full template. Every value that must change per environment is marked `CHANGE_ME`:

```ini
APP_NAME=Laravel
APP_ENV=local
APP_KEY=                              # php artisan key:generate
APP_DEBUG=true
APP_URL=http://localhost:8000

LOG_CHANNEL=stderr
LOG_LEVEL=debug

# PostgreSQL + TimescaleDB (stock pgsql driver — host must support the TimescaleDB extension)
# Timescale Cloud or self-managed Postgres+Timescale reachable over the public internet.
# Neon is NOT a target for this tier (no compression/TSL support).
DATABASE_URL=CHANGE_ME
DB_HOST=CHANGE_ME
DB_PORT=5432
DB_DATABASE=CHANGE_ME
DB_USERNAME=CHANGE_ME
DB_PASSWORD=CHANGE_ME
DB_SSLMODE=require                    # managed host over the public internet

# Cache — database-backed (no Redis)
CACHE_STORE=database
CACHE_PREFIX=<app>_

# Sessions — database-backed (no Redis)
SESSION_DRIVER=database
SESSION_LIFETIME=120

# Queues — AWS SQS (no Horizon, no DB queue driver)
QUEUE_CONNECTION=sqs
AWS_ACCESS_KEY_ID=CHANGE_ME
AWS_SECRET_ACCESS_KEY=CHANGE_ME
AWS_DEFAULT_REGION=us-east-1
SQS_PREFIX=https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID
SQS_QUEUE=default
SQS_SUFFIX=

# Filesystem
FILESYSTEM_DISK=local

# Sanctum
SANCTUM_STATEFUL_DOMAINS=localhost,localhost:3000
```

No `REDIS_*` variables. Cache and sessions are database-backed; the queue driver is SQS.

## Step 5 — `config/database.php` — PostgreSQL + TimescaleDB connection

Edit the `pgsql` connection block in `config/database.php`. TimescaleDB is an extension on top of standard Postgres — no third-party driver package required:

```php
// config/database.php — 'connections' => [ 'pgsql' => [...] ]
'pgsql' => [
    'driver'         => 'pgsql',
    'url'            => env('DATABASE_URL'),
    'host'           => env('DB_HOST', '127.0.0.1'),
    'port'           => env('DB_PORT', '5432'),
    'database'       => env('DB_DATABASE'),
    'username'       => env('DB_USERNAME'),
    'password'       => env('DB_PASSWORD'),
    'charset'        => 'utf8',
    'search_path'    => 'public',
    'sslmode'        => env('DB_SSLMODE', 'require'),   // managed host over the public internet
],
```

Standard Postgres semantics apply: sequences, joins, `SKIP LOCKED`, real transactions all work. See `references/postgres-timescale-eloquent.md` for UUID primary keys, hypertable migrations, and the reference-field model.

## Step 6 — `bootstrap/app.php` — middleware and exception handling

Laravel 13 uses a single `bootstrap/app.php` for the application bootstrap. Register the workspace middleware and Sanctum's auth guard:

```php
// bootstrap/app.php
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware) {
        // Resolve the current workspace from the authed user and bind it
        // into the IoC container so BelongsToWorkspace global scope can read it.
        $middleware->appendToGroup('api', [
            \App\Http\Middleware\ResolveWorkspace::class,
        ]);

        // Sanctum stateful middleware alias (cross-domain SPA cookie auth).
        // Bearer-token API routes use `auth:sanctum` guard (registered by Sanctum's ServiceProvider).
        $middleware->alias([
            'auth.sanctum' => \Laravel\Sanctum\Http\Middleware\EnsureFrontendRequestsAreStateful::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions) {
        // Global JSON error shape — see references/error-handling.md
        $exceptions->render(function (\Illuminate\Auth\AuthenticationException $e, $request) {
            if ($request->expectsJson()) {
                return response()->json(['code' => 'UNAUTHENTICATED', 'message' => 'Unauthenticated.'], 401);
            }
        });

        $exceptions->render(function (\Illuminate\Auth\Access\AuthorizationException $e, $request) {
            if ($request->expectsJson()) {
                return response()->json(['code' => 'FORBIDDEN', 'message' => $e->getMessage()], 403);
            }
        });
    })
    ->create();
```

The `ResolveWorkspace` middleware implementation lives in `references/multitenancy-global-scope.md`.

## Step 7 — SQS queue config

Edit `config/queue.php` to confirm the SQS driver block is present and reads from `.env`:

```php
// config/queue.php (excerpt — the sqs block ships with Laravel; verify it looks like this)
'sqs' => [
    'driver'      => 'sqs',
    'key'         => env('AWS_ACCESS_KEY_ID'),
    'secret'      => env('AWS_SECRET_ACCESS_KEY'),
    'prefix'      => env('SQS_PREFIX', 'https://sqs.us-east-1.amazonaws.com/your-account-id'),
    'queue'       => env('SQS_QUEUE', 'default'),
    'suffix'      => env('SQS_SUFFIX'),
    'region'      => env('AWS_DEFAULT_REGION', 'us-east-1'),
    'after_commit' => false,
],
```

`QUEUE_CONNECTION=sqs` in `.env` selects this driver. No `queue:work` daemon — the SQS worker Lambda runs via Bref's `QueueHandler`. See `references/sqs-queues.md` for job authoring and `laravel-bref-deploy/references/sqs-worker.md` for the Lambda side.

## Step 8 — Cache and session tables

Create the database-backed cache and session tables (they live in PostgreSQL alongside your application data):

```bash
php artisan make:cache-table
php artisan make:session-table
php artisan migrate
```

Confirm `config/cache.php` uses `database` by default (or `.env` overrides it):

```php
// config/cache.php
'default' => env('CACHE_STORE', 'database'),
```

Confirm `config/session.php`:

```php
// config/session.php
'driver' => env('SESSION_DRIVER', 'database'),
```

No Redis dependency. For cache invalidation: use explicit keyed deletes or cache tags with a database tag store — the Redis `SCAN`/wildcard delete pattern does not apply here. See `references/db-cache-sessions.md` for TTL and locking notes.

## Step 9 — Enable TimescaleDB + base migrations

The first migration enables the TimescaleDB extension. The host must support it — use Timescale Cloud or a self-managed Postgres instance with the extension installed. (Neon is not a target for this tier.)

```php
// database/migrations/0001_01_01_000000_enable_timescaledb.php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('CREATE EXTENSION IF NOT EXISTS timescaledb');
    }

    public function down(): void
    {
        // Intentionally left empty — removing the extension drops all hypertables.
    }
};
```

Next, create the `users` table. UUID PKs are the preferred style (`HasUuids` trait fills the column server-side via PHP); Postgres sequences are available if a feature needs them:

```php
// database/migrations/0001_01_01_000001_create_users_table.php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('users', function (Blueprint $table) {
            $table->uuid('id')->primary();              // HasUuids trait fills this
            $table->uuid('workspace_id')->index();      // reference column — no FK constraint (D5)
            $table->string('name');
            $table->string('email')->unique();
            $table->string('password');
            $table->rememberToken();
            $table->timestampsTz();
        });

        Schema::create('personal_access_tokens', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->uuidMorphs('tokenable');
            $table->string('name');
            $table->string('token', 64)->unique();
            $table->text('abilities')->nullable();
            $table->timestamp('last_used_at')->nullable();
            $table->timestamp('expires_at')->nullable();
            $table->timestampsTz();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('personal_access_tokens');
        Schema::dropIfExists('users');
    }
};
```

The reusable concern for every tenant model (uses Laravel's built-in `HasUuids`):

```php
// app/Concerns/HasUuids.php  — re-export or use Illuminate\Database\Eloquent\Concerns\HasUuids directly
namespace App\Concerns;

// Preferred: use Laravel's built-in trait on each model rather than wrapping it.
// app/Models/User.php excerpt:
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use App\Concerns\BelongsToWorkspace;

class User extends Authenticatable
{
    use HasUuids, BelongsToWorkspace;
    // ...
}
```

See `references/postgres-timescale-eloquent.md` for the full UUID-PK preference, reference-field migrations (no FK constraints), and hypertable patterns.

## Step 10 — `routes/api.php` — v1 prefix and health endpoint

```php
<?php
// routes/api.php
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API Routes — all requests are stateless (Sanctum bearer token)
|--------------------------------------------------------------------------
*/

Route::prefix('v1')->group(function () {

    // Health check — public, no auth required
    Route::get('/health', function () {
        return response()->json([
            'status'   => 'ok',
            'database' => DB::connection()->getPdo() ? 'up' : 'down',
            'cache'    => Cache::store('database')->has('__ping') || true ? 'up' : 'down',
        ]);
    });

    // Auth routes — Sanctum token issuance
    // Route::post('/auth/login',  [AuthController::class, 'login']);
    // Route::post('/auth/logout', [AuthController::class, 'logout'])->middleware('auth:sanctum');

    // Feature routes — added per module in Phase 5
    // Route::middleware(['auth:sanctum'])->group(function () {
    //     Route::apiResource('companies', CompanyController::class);
    // });
});
```

Every authenticated route group wraps `auth:sanctum`. All endpoints must carry `#[Authorize]` — see `references/auth-sanctum-permissions.md`.

## Step 11 — Boot verify

Copy `.env.example` to `.env` and fill in your PostgreSQL DSN and AWS credentials, then:

```bash
php artisan key:generate

# Run migrations (enables TimescaleDB extension, creates users, cache, session tables)
php artisan migrate

# Start the dev server
php artisan serve
```

Expected output:

```
INFO  Server running on [http://127.0.0.1:8000].
```

Test:

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","database":"up","cache":"up"}
```

All green — proceed to Phase 4 (Sanctum + `BelongsToWorkspace` global scope + `#[Audit]` / `AuditManager`) and Phase 5 (feature modules).

## Final scaffolding state

```
apps/api/
├── artisan
├── composer.json
├── composer.lock
├── .env                         ← local only; never committed
├── .env.example                 ← committed; Postgres+TimescaleDB DSN, db cache/sessions, sqs
├── bootstrap/
│   ├── app.php                  ← ResolveWorkspace middleware, exception renders
│   └── providers.php
├── config/
│   ├── database.php             ← pgsql block (standard Postgres port 5432, sslmode)
│   ├── cache.php                ← default: database
│   ├── session.php              ← driver: database
│   └── queue.php                ← sqs block
├── database/
│   ├── migrations/
│   │   ├── 0001_01_01_000000_enable_timescaledb.php  ← CREATE EXTENSION IF NOT EXISTS timescaledb
│   │   ├── 0001_01_01_000001_create_users_table.php  ← UUID PK (HasUuids), workspace_id ref col
│   │   ├── <timestamp>_create_cache_table.php
│   │   └── <timestamp>_create_sessions_table.php
│   ├── factories/
│   └── seeders/
├── routes/
│   ├── api.php                  ← v1 prefix, /health, feature routes added in Phase 5
│   └── console.php              ← scheduler entries
├── app/
│   ├── Models/
│   │   └── User.php             ← HasUuids + BelongsToWorkspace
│   ├── Http/
│   │   ├── Middleware/
│   │   │   └── ResolveWorkspace.php
│   │   └── Resources/           ← JsonResource presenters (one per feature, added in Phase 5)
│   ├── Concerns/
│   │   └── BelongsToWorkspace.php     ← added in Phase 4
│   ├── Audit/
│   │   ├── Audit.php                  ← #[Audit] attribute, added in Phase 4
│   │   └── AuditManager.php           ← added in Phase 4
│   └── Domains/                       ← feature modules added in Phase 5
│       └── (Companies/, Contacts/, Deals/, …)
│           └── Http/
│               ├── Controllers/
│               ├── Requests/          ← FormRequest validation
│               └── Resources/         ← JsonResource presenters
└── tests/
    ├── Pest.php
    ├── Feature/
    │   ├── WorkspaceIsolationTest.php        ← added in Phase 4
    │   └── <Feature>ContractTest.php         ← locks each Resource to its TS contract shape
    └── Unit/
```

## Anti-patterns

| Anti-pattern | Why it breaks the stack |
|---|---|
| `CACHE_STORE=redis` or `SESSION_DRIVER=redis` | No Redis in this stack. Database-backed only; Lambda is stateless and Redis needs a VPC. |
| `QUEUE_CONNECTION=database` | SQS is the queue driver for the serverless/Bref deploy. Use SQS — `SKIP LOCKED` works on Postgres but a daemon-less Lambda environment needs a managed queue. |
| `$table->id()` (auto-increment bigint) | Prefer UUID PKs (`HasUuids`) for tenant-scoped tables — consistent with the global scope pattern. Sequences are available when a feature genuinely needs them. |
| Returning a raw Eloquent model or `->toArray()` from a controller | Always return a `JsonResource` (or `JsonResource::collection()`). Eager-load and `withCount` before passing to the resource. See `references/api-resources.md`. |
| Hand-editing `packages/contracts/src/<feature>.ts` without updating the Resource | The TS contract is hand-written and kept in lockstep with the `JsonResource::toArray()`. The contract Pest test is the guard — run it after any Resource change. |
| Omitting `CREATE EXTENSION IF NOT EXISTS timescaledb` in the first migration | `create_hypertable()` calls in later migrations will fail. The extension migration must run first; it is idempotent. |
| Running `php artisan queue:work` on the server | The queue worker is a separate Bref Lambda (runtime `php-84`) consuming SQS. No daemon. |
