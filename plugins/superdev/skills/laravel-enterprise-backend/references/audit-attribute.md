# Audit Logging — `#[Audit]` Attribute + TimescaleDB Hypertable

Every state-changing service method is wrapped once. `AuditManager` times the action, captures who/what/when, marks `Success`/`Failure`, and dispatches an **SQS `AuditWrite` job** that inserts a structured row into the `audit_logs` **TimescaleDB hypertable**. Free compliance trail, zero per-handler boilerplate, and the write never blocks the response.

> **The rule: every mutation is audited.** Creates, updates, deletes, state transitions, sends — anything that changes data goes through `AuditManager::run()`. Read-only endpoints are not audited (the request logger covers those). `status` values are **Title Case** (`Success` / `Failure`) — same convention as the enums (DB value = wire value = UI label).

This is the Laravel analogue of the Nest `@Audit` decorator + interceptor + hypertable (see `nestjs-enterprise-backend/references/audit-logging.md`). The mechanism diverges (no decorator metadata + RxJS interceptor; SQS instead of BullMQ) but the semantics — and the **TimescaleDB hypertable sink with native compression + retention** — are preserved verbatim.

## What gets logged

Each audit row:

```php
[
    'id'           => '...uuid...',      // gen_random_uuid()
    'action'       => 'company.create',  // <subject_lowercase>.<verb>
    'subject'      => 'Company',          // the entity type
    'status'       => 'Success',          // Title Case: 'Success' | 'Failure'
    'duration_ms'  => 42,
    'workspace_id' => '...uuid...',       // always workspace-scoped
    'user_id'      => '...uuid...|null',  // null for system/cron actions
    'request_id'   => '...|null',
    'ip'           => '...|null',
    'context'      => '{...}',            // JSONB — redacted args, diff, etc.
    'occurred_at'  => '2026-06-03T10:00:00+00:00',
]
```

## The attribute

`app/Audit/Audit.php` — a declarative marker for the action/subject pair. Used by the optional reflection wrapper (below); the explicit `AuditManager::run()` call is the always-works baseline.

```php
// app/Audit/Audit.php — the attribute
namespace App\Audit;

#[\Attribute(\Attribute::TARGET_METHOD)]
final class Audit
{
    public function __construct(public string $action, public string $subject) {}
}
```

## The manager

`app/Audit/AuditManager.php` — wraps an action, times it, records `Success`/`Failure`, and dispatches the write job to the `audit` queue. The `finally` block guarantees a row is written whether the closure returns or throws; the original exception still propagates.

```php
// app/Audit/AuditManager.php — wraps an action, times it, dispatches the write job
namespace App\Audit;

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

The dispatch is fire-and-forget onto the dedicated `audit` queue — the request returns immediately; a Bref SQS worker drains the queue and performs the insert (see `sqs-queues.md` and the deployer's `sqs-worker.md`). `workspace_id` is read from the per-request `workspace.id` binding set by the tenancy middleware (see `multitenancy-global-scope.md`).

## The SQS write job

`app/Jobs/AuditWrite.php` — the queued job that inserts the row into the hypertable. It implements `ShouldQueue`, so dispatching it enqueues to SQS rather than running inline.

```php
// app/Jobs/AuditWrite.php — SQS job that inserts the row into the audit_logs hypertable
namespace App\Jobs;

use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

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

The insert is a single `DB::table()` write into the hypertable — no Eloquent model, no global scope (audit rows carry their own `workspace_id` and must never be tenant-filtered on write). Inserts route into the right Timescale chunk automatically by `occurred_at`. The job is idempotent-safe enough for at-least-once delivery: a duplicate delivery writes a duplicate row with a fresh `id`, which audit queries tolerate (dedupe by `request_id` + `action` if strict de-dup is required).

## The hypertable

`audit_logs` is a **TimescaleDB hypertable** partitioned by `occurred_at` into time chunks, with **native compression** (old chunks columnar-compress) and a **native retention policy** (old chunks are dropped automatically). This mirrors the Nest schema exactly. Create it with raw `DB::statement()` so the Timescale DDL is explicit; the host must support the TimescaleDB extension (Timescale Cloud / self-managed Postgres+Timescale — see `postgres-timescale-eloquent.md`).

```php
// migration — audit_logs as a TimescaleDB hypertable (extension enabled in the first migration)
DB::statement("CREATE TABLE audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    action text NOT NULL, subject text NOT NULL, status text NOT NULL,
    duration_ms int, workspace_id uuid, user_id uuid, request_id text, ip text,
    context jsonb, occurred_at timestamptz NOT NULL DEFAULT now()
)");
DB::statement("SELECT create_hypertable('audit_logs', 'occurred_at')");
DB::statement("CREATE INDEX ON audit_logs (workspace_id, occurred_at DESC)");

// Compression (TSL): segment by workspace, compress chunks older than 7 days
DB::statement("ALTER TABLE audit_logs SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'workspace_id'
)");
DB::statement("SELECT add_compression_policy('audit_logs', INTERVAL '7 days')");

// Retention (TSL): drop chunks older than the 180-day window — native, no scheduled command
DB::statement("SELECT add_retention_policy('audit_logs', INTERVAL '180 days')");
```

Notes:
- `status` stores the Title-Case string directly (`'Success'`/`'Failure'`) — no enum type, no label map.
- `workspace_id`/`user_id` are plain reference columns (`uuid`), **not** FK constraints (reference-field model — see `multitenancy-global-scope.md`). Audit rows survive the deletion of the entity they reference.
- The `(workspace_id, occurred_at DESC)` index serves the admin read-side query (filter by workspace, order by time newest-first).
- `create_hypertable` does the time partitioning; you never declare partitions by hand. Inserts and queries target the logical table — Timescale routes to chunks transparently.
- `add_compression_policy` runs as a background job inside the database: chunks older than 7 days compress columnar (cheap storage, fast scans), segmented by `workspace_id` so per-workspace reads stay efficient.
- `add_retention_policy` is the **native replacement for the old scheduled prune** (was a `PruneAuditLogs` delete command in ≤v1.5): Timescale drops whole chunks past 180 days — an `O(1)` metadata operation, not a row-by-row `DELETE`. No EventBridge schedule, no app code.

## Usage in a service (mutations only)

Wrap the mutation closure inside a transaction and return an API Resource presenter (see `api-resources.md`) — never a raw model.

```php
// app/Domains/Companies/Actions/CreateCompany.php
use App\Audit\AuditManager;
use App\Domains\Companies\Http\Resources\CompanyResource;
use App\Models\Company;
use Illuminate\Support\Facades\DB;

public function create(CreateCompanyRequest $request): CompanyResource
{
    return app(AuditManager::class)->run('company.create', 'Company', function () use ($request) {
        $company = DB::transaction(fn () => Company::create($request->validated()));
        return new CompanyResource($company->loadCount('contacts'));
    });
}
```

Order matters: `AuditManager::run()` is the outermost wrapper so it times the whole operation and records `Failure` if the transaction throws. The `DB::transaction()` is inside it — one operation, one audit row.

### Action naming convention

Use `<subject>.<verb>`, lowercase, for `action`; the `subject` argument is the PascalCase entity type.

Good:
- `company.create`, `company.update`, `company.delete`
- `campaign.send`, `campaign.pause`, `campaign.resume`
- `auth.login`, `auth.logout`, `auth.password_reset_request`

Bad:
- `CompanyCreated` (mixed case, event-shaped)
- `created_company` (verb-first)
- `did_thing` (unspecific)

## Optional: `#[Audit]` via reflection (declarative form)

The explicit `AuditManager::run()` call above is the baseline and always works. If you prefer a declarative form, bind a small service decorator (or a route/controller middleware) that reads the `#[Audit]` attribute off the target method via reflection and wraps the call in `AuditManager::run()` automatically:

```php
// sketch — a decorator that reads #[Audit] and delegates to AuditManager
$method = new \ReflectionMethod($service, $name);
$attr = $method->getAttributes(\App\Audit\Audit::class)[0] ?? null;

if ($attr === null) {
    return $service->{$name}(...$args);               // not audited
}

$audit = $attr->newInstance();                         // App\Audit\Audit
return app(\App\Audit\AuditManager::class)->run(
    $audit->action,
    $audit->subject,
    fn () => $service->{$name}(...$args),
    context: ['args' => /* redact secrets here */ []],
);
```

The decorated method then just carries the attribute:

```php
#[\App\Audit\Audit(action: 'company.create', subject: 'Company')]
public function create(CreateCompanyRequest $request): CompanyResource { /* ... */ }
```

Redact secrets (`password`, `token`, `secret`, `api_key`, `authorization`) before putting args into `context` — the `context` JSONB column must never hold credentials or full request bodies.

## Querying audit logs

Read-side is admin-only and `#[Authorize]`-d like every endpoint (see `auth-sanctum-permissions.md`). Filter by the per-request workspace, order by `occurred_at` (the `(workspace_id, occurred_at DESC)` index keeps this cheap even across compressed chunks). Because audit rows come from a raw `DB::table()` query (no Eloquent model exists for `audit_logs`), map each row through an `AuditLogResource` before returning rather than passing raw `stdClass` objects to the frontend.

There is no `AuditLog` Eloquent model, so authorize via a spatie permission string rather than a Policy class. Grant the `view audit logs` permission to the `Admin` role in your permission seeder.

```php
// app/Domains/Audit/Http/AuditController.php
use App\Domains\Audit\Http\Requests\AuditFilters;
use App\Domains\Audit\Http\Resources\AuditLogResource;
use Illuminate\Routing\Attributes\Controllers\Authorize;
use Illuminate\Support\Facades\DB;

#[Authorize('view audit logs')]
public function index(AuditFilters $filters): \Illuminate\Http\Resources\Json\AnonymousResourceCollection
{
    // DB::table() — no Eloquent model; map each row through an AuditLogResource
    $page = DB::table('audit_logs')
        ->where('workspace_id', app('workspace.id'))
        ->when($filters->action, fn ($q) => $q->where('action', $filters->action))
        ->when($filters->user_id, fn ($q) => $q->where('user_id', $filters->user_id))
        ->orderByDesc('occurred_at')
        ->paginate($filters->per_page);

    return AuditLogResource::collection($page);
}
```

`AuditFilters` is a FormRequest (see `validation.md`); `AuditLogResource` is a `JsonResource` that shapes each row — including `json_decode($row->context)` — into the published contract (see `api-resources.md`).

## Anti-patterns

- ❌ Forgetting `#[Audit]` / `AuditManager::run()` on a mutation. **Every** state change is audited. A create/update/delete with no audit row is a bug.
- ❌ Synchronous audit writes in the request path. Always dispatch the `AuditWrite` job onto the `audit` SQS queue.
- ❌ Audit rows in a plain, unpartitioned (non-hypertable) table. They balloon to hundreds of millions of rows — `audit_logs` must be a TimescaleDB hypertable so chunks compress and retention drops them.
- ❌ A scheduled `DELETE`/prune command for retention when a native policy exists. `add_retention_policy` drops whole chunks for free; a hand-rolled prune command is redundant (and a slow row-by-row delete). Don't reintroduce it.
- ❌ Writing audit rows without `workspace_id`. Every row is workspace-scoped; `null` only for genuine system/cron actions.
- ❌ Storing passwords or full request bodies in `context`. Redact secrets before they reach the JSONB column.
- ❌ Auditing read-only endpoints. Skips the overhead on hot paths; reads are covered by the request logger.
- ❌ Lower-casing or screaming the status (`success`, `SUCCESS`, `FAILED`). It is Title Case: `Success` / `Failure` — the wire value is the label.
- ❌ Inconsistent action names (`createCompany` vs `company.create`). Pick `<subject>.<verb>` lowercase and stick to it.
- ❌ Adding FK constraints from `audit_logs` to `users`/`workspaces`. Reference-field model — audit rows outlive the entities they reference.
- ❌ Forgetting the SQS worker (or the `audit` queue mapping). Jobs pile up in SQS with no consumer and the trail goes silent.
