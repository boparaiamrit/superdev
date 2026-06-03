# Audit Logging — `#[Audit]` Attribute + Partitioned Table

Every state-changing service method is wrapped once. `AuditManager` times the action, captures who/what/when, marks `Success`/`Failure`, and dispatches an **SQS `AuditWrite` job** that inserts a structured row into a **RANGE-partitioned `audit_logs`** table. Free compliance trail, zero per-handler boilerplate, and the write never blocks the response.

> **The rule: every mutation is audited.** Creates, updates, deletes, state transitions, sends — anything that changes data goes through `AuditManager::run()`. Read-only endpoints are not audited (the request logger covers those). `status` values are **Title Case** (`Success` / `Failure`) — same convention as the enums (DB value = wire value = UI label).

This is the Laravel analogue of the Nest `@Audit` decorator + interceptor + hypertable. The mechanism diverges (no decorator metadata + RxJS interceptor; no BullMQ; no TimescaleDB) but the semantics are preserved verbatim.

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

`app/Jobs/AuditWrite.php` — the queued job that inserts the row. It implements `ShouldQueue`, so dispatching it enqueues to SQS rather than running inline.

```php
// app/Jobs/AuditWrite.php — SQS job that inserts the row
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

The insert is a single `DB::table()` write — no Eloquent model, no global scope (audit rows carry their own `workspace_id` and must never be tenant-filtered on write). The job is idempotent-safe enough for at-least-once delivery: a duplicate delivery writes a duplicate row with a fresh `id`, which audit queries tolerate (dedupe by `request_id` + `action` if strict de-dup is required).

## Usage in a service (mutations only)

Wrap the mutation closure. Combine `AuditManager` with the `CockroachRetry` 40001 wrapper (see `cockroachdb-eloquent.md`) and return a `CompanyData` presenter via `CompanyData::fromModel` (see `laravel-data-contracts.md`) — never a raw model.

```php
// app/Domains/Companies/Actions/CreateCompany.php
public function create(CreateCompanyData $input): CompanyData
{
    return app(AuditManager::class)->run('company.create', 'Company', function () use ($input) {
        $company = \App\Support\CockroachRetry::transaction(fn () => Company::create($input->toArray()));
        return CompanyData::fromModel($company->loadCount('contacts'));
    });
}
```

Order matters: `AuditManager::run()` is the outermost wrapper so it times the whole operation (including retries) and records `Failure` if every retry exhausts. `CockroachRetry::transaction()` is inside it so each serialization-retry attempt re-runs the write but produces exactly one audit row.

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
public function create(CreateCompanyData $input): CompanyData { /* ... */ }
```

Redact secrets (`password`, `token`, `secret`, `api_key`, `authorization`) before putting args into `context` — the `context` JSONB column must never hold credentials or full request bodies.

## The partitioned table

`audit_logs` is a plain table (no TimescaleDB), **RANGE-partitioned by `occurred_at`** for scan locality and cheap retention. CockroachDB-flavored DDL via raw `DB::statement()` so we control the exact types (`STRING`/`JSONB`/`UUID`, `gen_random_uuid()` default, no FK constraints per the reference-field model).

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

Notes:
- `status` stores the Title-Case string directly (`'Success'`/`'Failure'`) — no enum type, no label map.
- `workspace_id`/`user_id` are plain reference columns (UUID), **not** FK constraints (reference-field model, D9). Audit rows survive the deletion of the entity they reference.
- The `(workspace_id, occurred_at)` index serves the admin read-side query (filter by workspace, order by time).
- RANGE partitioning by `occurred_at` keeps recent partitions hot and makes the prune below a bounded delete. On CockroachDB Enterprise you can declare explicit `PARTITION BY RANGE (occurred_at)`; on the free serverless tier the index + scheduled prune deliver the same retention behavior.

## The prune command

CockroachDB has no Timescale `drop_chunks`, so retention is a scheduled delete. Register the command and a daily scheduler entry (run by EventBridge → console Lambda — see the deployer's `scheduler-eventbridge.md`).

```php
// app/Console/Commands/PruneAuditLogs.php (scheduled daily) — retention via delete (CRDB has no Timescale drop-chunk)
namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class PruneAuditLogs extends Command
{
    protected $signature = 'audit:prune';
    protected $description = 'Delete audit_logs rows older than the retention window';

    public function handle(): int
    {
        DB::statement('DELETE FROM audit_logs WHERE occurred_at < now() - INTERVAL ?', ['180 days']);

        return self::SUCCESS;
    }
}
```

```php
// routes/console.php — daily prune (EventBridge -> schedule:run drives this on Lambda)
use Illuminate\Support\Facades\Schedule;

Schedule::command('audit:prune')->dailyAt('03:00');
```

Batch the delete (`LIMIT` + loop) if a single prune would touch more rows than the free-tier RU budget comfortably allows; if audit volume outgrows the 5 GiB storage cap, offload older partitions to S3/CloudWatch (noted in the deployer's `deploy-checklist.md`).

## Querying audit logs

Read-side is admin-only and `#[Authorize]`-d like every endpoint (see `auth-sanctum-permissions.md`). Filter by the per-request workspace, order by `occurred_at`. Because audit rows come from a raw `DB::table()` query (no Eloquent model exists for `audit_logs`), map each row to an `AuditLogData` presenter before returning rather than passing raw `stdClass` objects to the frontend.

There is no `AuditLog` Eloquent model, so authorize via a spatie permission string rather than a Policy class. Grant the `view audit logs` permission to the `Admin` role in your permission seeder.

```php
// app/Domains/Audit/Http/AuditController.php
use Illuminate\Routing\Attributes\Controllers\Authorize;
use Illuminate\Support\Facades\DB;

#[Authorize('view audit logs')]
public function index(\App\Domains\Audit\Http\Requests\AuditFilters $filters): \Illuminate\Pagination\LengthAwarePaginator
{
    // DB::table() — no Eloquent model; map each row to an AuditLogData presenter
    return DB::table('audit_logs')
        ->where('workspace_id', app('workspace.id'))
        ->when($filters->action, fn ($q) => $q->where('action', $filters->action))
        ->when($filters->user_id, fn ($q) => $q->where('user_id', $filters->user_id))
        ->orderByDesc('occurred_at')
        ->paginate($filters->per_page)
        ->through(fn ($row) => \App\Domains\Audit\Data\AuditLogData::fromRow((array) $row));
}
```

## Anti-patterns

- ❌ Forgetting `#[Audit]` / `AuditManager::run()` on a mutation. **Every** state change is audited. A create/update/delete with no audit row is a bug.
- ❌ Synchronous audit writes in the request path. Always dispatch the `AuditWrite` job onto the `audit` SQS queue.
- ❌ Audit rows in a plain, unpartitioned table. They balloon to hundreds of millions of rows — RANGE-partition by `occurred_at` and prune on a schedule.
- ❌ Writing audit rows without `workspace_id`. Every row is workspace-scoped; `null` only for genuine system/cron actions.
- ❌ Storing passwords or full request bodies in `context`. Redact secrets before they reach the JSONB column.
- ❌ Auditing read-only endpoints. Skips the overhead on hot paths; reads are covered by the request logger.
- ❌ Lower-casing or screaming the status (`success`, `SUCCESS`, `FAILED`). It is Title Case: `Success` / `Failure` — the wire value is the label.
- ❌ Inconsistent action names (`createCompany` vs `company.create`). Pick `<subject>.<verb>` lowercase and stick to it.
- ❌ Adding FK constraints from `audit_logs` to `users`/`workspaces`. Reference-field model — audit rows outlive the entities they reference.
- ❌ Forgetting the SQS worker (or the `audit` queue mapping). Jobs pile up in SQS with no consumer and the trail goes silent.
