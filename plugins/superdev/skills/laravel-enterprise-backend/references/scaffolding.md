# Scaffolding `apps/api`

Run this in Phase 3, after `references/monorepo-setup.md` has set up the workspace and `packages/contracts`. Goal: a Laravel 13 app booting on CockroachDB via the stock `pgsql` driver, database-backed cache and sessions, SQS queue connection, Sanctum auth, and `/api/v1/health` returning green.

## Step 1 — Create the app

From the monorepo root:

```bash
laravel new apps/api \
  --no-starter-kit \
  --no-interaction \
  --php 8.3
```

`--no-starter-kit` gives a clean API app with no Blade/Livewire. PHP 8.3+ is required for Laravel 13.x and the `#[Authorize]` / `#[Audit]` attribute patterns.

> **Monorepo note:** When this skill runs inside the `prd-design-build-orchestrator`, the `docker-compose.yml` lives at the **monorepo root**. The `monorepo-bootstrapper` agent owns it. `apps/api` is a plain `composer.json` project — it is **not** a pnpm workspace package. See `references/monorepo-setup.md` for the Turbo wiring and the CockroachDB Compose service.

## Step 2 — Install runtime dependencies

```bash
cd apps/api

# Core stack
composer require \
  spatie/laravel-data \
  spatie/laravel-typescript-transformer \
  laravel/sanctum \
  spatie/laravel-permission \
  aws/aws-sdk-php

# Verify versions support Laravel 13 (adjust majors if a newer release is available)
# spatie/laravel-data ^4, spatie/laravel-typescript-transformer ^3.2
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
php artisan vendor:publish --provider="Spatie\LaravelData\LaravelDataServiceProvider"
php artisan vendor:publish --tag=typescript-transformer-config
```

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

# CockroachDB serverless (stock pgsql driver — no third-party package)
# Full DSN carries the cluster routing id and SSL cert path:
#   postgresql://user:pass@<cluster>.cockroachlabs.cloud:26257/<cluster-name>.defaultdb?sslmode=verify-full&sslrootcert=/path/to/ca.crt
DATABASE_URL=CHANGE_ME
DB_HOST=localhost
DB_PORT=26257
DB_DATABASE=defaultdb
DB_USERNAME=root
DB_PASSWORD=
DB_SSLMODE=verify-full
# DB_SSLROOTCERT=/path/to/ca.crt   # path to the CockroachDB CA cert (serverless)

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

## Step 5 — `config/database.php` — CockroachDB connection

Edit the `pgsql` connection block in `config/database.php` to match CockroachDB's defaults. No third-party package:

```php
// config/database.php — 'connections' => [ 'pgsql' => [...] ]
'pgsql' => [
    'driver'         => 'pgsql',
    'url'            => env('DATABASE_URL'),
    'host'           => env('DB_HOST', '127.0.0.1'),
    'port'           => env('DB_PORT', '26257'),           // CockroachDB default
    'database'       => env('DB_DATABASE', 'defaultdb'),
    'username'       => env('DB_USERNAME'),
    'password'       => env('DB_PASSWORD'),
    'charset'        => 'utf8',
    'prefix'         => '',
    'prefix_indexes' => true,
    'search_path'    => 'public',
    'sslmode'        => env('DB_SSLMODE', 'verify-full'),
    'options'        => array_filter([
        \PDO::PGSQL_ATTR_DISABLE_PREPARES => true,        // safer under CockroachDB pooling
    ]),
],
```

The `DATABASE_URL` carries the cluster routing id and `sslrootcert` query param for CockroachDB serverless; no additional driver is required. See `references/cockroachdb-eloquent.md` for UUID primary keys, the 40001 serialization-retry wrapper, and additive-migration discipline.

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

Create the database-backed cache and session tables (they live in CockroachDB alongside your application data):

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

## Step 9 — UUID primary keys base migration

Every tenant-scoped table uses a UUID primary key generated server-side by CockroachDB's `gen_random_uuid()`. No `SEQUENCE`/auto-increment. Create a baseline migration for the `users` table (replace the default Laravel migration):

```php
// database/migrations/0001_01_01_000000_create_users_table.php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('users', function (Blueprint $table) {
            $table->uuid('id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('workspace_id')->index();     // reference column — no FK constraint (D9)
            $table->string('name');
            $table->string('email')->unique();
            $table->string('password');
            $table->rememberToken();
            $table->timestampsTz();
        });

        Schema::create('personal_access_tokens', function (Blueprint $table) {
            $table->uuid('id')->primary()->default(DB::raw('gen_random_uuid()'));
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

The reusable trait for every tenant model:

```php
// app/Concerns/HasUuidPrimaryKey.php
namespace App\Concerns;

trait HasUuidPrimaryKey
{
    public $incrementing = false;
    protected $keyType = 'string';
}
```

Apply it in every model:

```php
// app/Models/User.php (excerpt)
use App\Concerns\HasUuidPrimaryKey;
use App\Concerns\BelongsToWorkspace;

class User extends Authenticatable
{
    use HasUuidPrimaryKey, BelongsToWorkspace;
    // ...
}
```

See `references/cockroachdb-eloquent.md` for the full UUID-PK pattern and the 40001 serialization-retry wrapper you must apply around writes.

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

## Step 11 — `config/typescript-transformer.php`

Point the TS emit at the shared contracts package so the Next.js frontend gets the generated types:

```php
// config/typescript-transformer.php (published by the package)
return [
    'auto_discover_types' => [
        app_path(),
    ],
    'collectors' => [
        Spatie\LaravelData\Support\TypeScriptTransformer\DataTypeScriptCollector::class,
    ],
    'transformers' => [
        Spatie\LaravelData\Support\TypeScriptTransformer\DataTypeScriptTransformer::class,
    ],
    // Emit into the monorepo shared contracts package consumed by apps/web
    'output_file' => base_path('../../packages/contracts/src/generated.ts'),
    'writer'      => Spatie\TypeScriptTransformer\Writers\TypeDefinitionWriter::class,
];
```

Run the transform whenever a Data class changes:

```bash
php artisan typescript:transform
```

This is wired into the Turbo `contracts` task so it runs automatically before `apps/web` builds. See `references/monorepo-setup.md` for the Turbo task definition and `references/laravel-data-contracts.md` for the Data-as-presenter pattern.

## Step 12 — Boot verify

Copy `.env.example` to `.env` and fill in your CockroachDB DSN and AWS credentials, then:

```bash
php artisan key:generate

# Run migrations (creates cache, session, users, personal_access_tokens tables)
php artisan migrate

# Confirm the transform can find Data classes (empty output is fine at this stage)
php artisan typescript:transform

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
├── .env.example                 ← committed; CockroachDB DSN, db cache/sessions, sqs
├── bootstrap/
│   ├── app.php                  ← ResolveWorkspace middleware, exception renders
│   └── providers.php
├── config/
│   ├── database.php             ← pgsql block tuned for CockroachDB (port 26257, sslmode)
│   ├── cache.php                ← default: database
│   ├── session.php              ← driver: database
│   ├── queue.php                ← sqs block
│   └── typescript-transformer.php   ← output_file → packages/contracts/src/generated.ts
├── database/
│   ├── migrations/
│   │   ├── 0001_01_01_000000_create_users_table.php   ← UUID PK, workspace_id ref col
│   │   ├── <timestamp>_create_cache_table.php
│   │   └── <timestamp>_create_sessions_table.php
│   ├── factories/
│   └── seeders/
├── routes/
│   ├── api.php                  ← v1 prefix, /health, feature routes added in Phase 5
│   └── console.php              ← scheduler entries (audit prune, etc.)
├── app/
│   ├── Models/
│   │   └── User.php             ← HasUuidPrimaryKey + BelongsToWorkspace
│   ├── Http/
│   │   └── Middleware/
│   │       └── ResolveWorkspace.php
│   ├── Concerns/
│   │   ├── HasUuidPrimaryKey.php
│   │   └── BelongsToWorkspace.php     ← added in Phase 4
│   ├── Support/
│   │   └── CockroachRetry.php         ← added in Phase 4 / 6
│   ├── Audit/
│   │   ├── Audit.php                  ← #[Audit] attribute, added in Phase 4
│   │   └── AuditManager.php           ← added in Phase 4
│   └── Domains/                       ← feature modules added in Phase 5
│       └── (Companies/, Contacts/, Deals/, …)
└── tests/
    ├── Pest.php
    ├── Feature/
    │   └── WorkspaceIsolationTest.php  ← added in Phase 4
    └── Unit/
```

## Anti-patterns

| Anti-pattern | Why it breaks the stack |
|---|---|
| `composer require ylsideas/cockroachdb-laravel` | Forbidden (D4). Use the stock `pgsql` driver. CockroachDB is Postgres-wire compatible. |
| `CACHE_STORE=redis` or `SESSION_DRIVER=redis` | No Redis in this stack. Database-backed only; Lambda is stateless and Redis needs a VPC. |
| `QUEUE_CONNECTION=database` | CockroachDB does not support `SKIP LOCKED`; the DB queue driver relies on it. Use SQS. |
| `$table->id()` (auto-increment) | CockroachDB sequences are a hotspot. Use `uuid('id')->primary()->default(DB::raw('gen_random_uuid()'))`. |
| `DB::transaction($cb)` without the retry wrapper | Serialization failures (SQLSTATE 40001) will propagate. Wrap writes with `CockroachRetry::transaction()`. |
| Returning a raw Eloquent model or `->toArray()` from a controller | Always return a `spatie/laravel-data` Data class. The model is never the public shape. |
| Hand-editing `packages/contracts/src/generated.ts` | The file is generated by `php artisan typescript:transform`. Edit the Data class; re-run the transform. |
| Running `php artisan queue:work` on the server | The queue worker is a separate Bref Lambda (runtime `php-84`) consuming SQS. No daemon. |
