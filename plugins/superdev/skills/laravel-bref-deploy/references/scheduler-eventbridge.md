# Scheduler — EventBridge → `schedule:run`

Laravel's task scheduler runs on the **console Lambda** (`php-84-console`). An **EventBridge rule at `rate(1 minute)`** invokes the function with `"schedule:run"` as the input every minute — exactly what a traditional cron tab does on a dedicated server, but fully serverless and zero-cost at low tick rates.

> **Cross-reference:** cron command definitions belong in `routes/console.php`. The scheduler is the _execution engine_; the commands themselves are defined there. The `audit:prune` command that deletes old audit rows is a canonical example — see `laravel-enterprise-backend/references/audit-attribute.md` for the full implementation.

---

## How it works

```
EventBridge rule
  rate(1 minute)
      │
      ▼
artisan Lambda   (php-84-console, timeout 720 s)
  php artisan schedule:run
      │
      ├── due? Schedule::command('audit:prune')->dailyAt('03:00')  → runs
      ├── due? Schedule::command('metrics:rollup')->dailyAt('02:00') → skipped
      └── due? Schedule::command('leads:warn-stale')->hourly()     → runs
```

Laravel evaluates every registered command against the current UTC time. Commands that are due run; the rest are skipped. This is standard Laravel scheduler behaviour — the only serverless-specific part is _who ticks the clock_ (EventBridge, not OS cron).

---

## `serverless.yml` wiring

The artisan function and its EventBridge event are declared in `serverless.yml`. The `input` field is the string that the console Lambda handler passes to `php artisan` as arguments — `schedule:run` tells it to run the scheduler for this tick.

```yaml
functions:
  artisan:
    handler: artisan
    runtime: php-84-console
    timeout: 720                 # 12 minutes; each individual command should be < 12 min
    events:
      - schedule:
          rate: rate(1 minute)
          input: '"schedule:run"'   # EventBridge passes this string to the Lambda handler
```

Notes:
- `runtime: php-84-console` is the Bref 3.x shorthand for the composite layer (php-84 + console). The console layer reads the Lambda input as an artisan command string and delegates to `php artisan`.
- `timeout: 720` gives `schedule:run` enough headroom; individual commands should stay under 12 minutes (720 s). Commands that are expected to take longer should dispatch SQS jobs instead of doing the work inline.
- The same `artisan` function is also used for one-off admin commands (see `deploy-checklist.md` — migrations run via `osls bref:cli --args="migrate --force"`).

---

## Cron definitions in `routes/console.php`

All scheduled commands live in `routes/console.php` (Laravel 11+ style — no `Kernel.php` schedule method). Use `->withoutOverlapping()` on every entry: EventBridge ticks every minute and a command that takes > 1 minute will otherwise have multiple concurrent invocations, each on its own Lambda.

```php
// routes/console.php
use Illuminate\Support\Facades\Schedule;

// Audit log retention — delete rows older than 180 days (see audit-attribute.md)
// Runs daily at 03:00 UTC. withoutOverlapping() prevents concurrent prune runs.
Schedule::command('audit:prune')->dailyAt('03:00')->withoutOverlapping();

// Daily metric rollups (e.g. campaign stats summary)
Schedule::command('metrics:rollup')->dailyAt('02:00')->withoutOverlapping();

// Hourly stale-lead warnings
Schedule::command('leads:warn-stale')->hourly()->withoutOverlapping();

// Every 30 minutes — DNS / domain health checks
Schedule::command('domains:check-dns')->everyThirtyMinutes()->withoutOverlapping();

// Weekly report dispatch — Sunday 06:00 UTC
Schedule::command('reports:weekly')->weeklyOn(0, '06:00')->withoutOverlapping();
```

### Frequency reference

| Method | Tick interval |
|---|---|
| `->everyMinute()` | Every tick (each EventBridge fire) |
| `->everyFiveMinutes()` | Every 5 ticks |
| `->everyThirtyMinutes()` | Every 30 ticks |
| `->hourly()` | Once per hour |
| `->dailyAt('HH:MM')` | Once per day at the given UTC time |
| `->weeklyOn(day, 'HH:MM')` | Once per week |

Laravel evaluates the schedule in UTC. All times in `routes/console.php` are UTC.

---

## Idempotency for at-least-once invocation

EventBridge delivers at-least-once. In practice, duplicate fires within the same minute are rare, but they happen. Two defences:

### 1. `->withoutOverlapping()` (primary)

This is mandatory on every scheduled command. Laravel stores an overlap-prevention key in the cache (`CACHE_STORE=database`) so a second invocation of the same command bails immediately if the previous run is still in progress.

```php
Schedule::command('reports:weekly')->weeklyOn(0, '06:00')->withoutOverlapping();
// If EventBridge fires twice in the same minute, the second Lambda finds the overlap
// key in the database cache and exits without running the command again.
```

Because cache is **database-backed** (`CACHE_STORE=database`) and CockroachDB is accessible from Lambda over the public internet (no VPC needed), this overlap key is durable across Lambda instances — it actually works, unlike an in-memory cache on an ephemeral container.

### 2. Business-level idempotency in the command itself

Commands that mutate data should guard against re-execution at the business level — not just via `withoutOverlapping()`. If two ticks both check "is it time to run the weekly report?", only one should proceed.

```php
// app/Console/Commands/WeeklyReport.php
class WeeklyReport extends Command
{
    protected $signature = 'reports:weekly';
    protected $description = 'Dispatch weekly summary reports to workspace admins';

    public function handle(): int
    {
        $windowKey = 'weekly-report:' . now()->startOfWeek()->toDateString();

        // Idempotency guard: only run once per calendar week
        if (\Cache::has($windowKey)) {
            $this->info('Already ran this week — skipping.');
            return self::SUCCESS;
        }

        \Cache::put($windowKey, true, now()->addDays(8)); // TTL > 1 week

        \App\Domains\Reports\Jobs\DispatchWeeklyReports::dispatch()
            ->onQueue(\App\Queue\QueueNames::DEFAULT);

        return self::SUCCESS;
    }
}
```

A cache key that expires after the command's natural re-run window is sufficient. Combine this with `->withoutOverlapping()` for defence in depth.

### 3. Commands that only dispatch jobs

If a scheduled command's sole job is to fan out SQS jobs, idempotency of the heavy work belongs in those jobs (see `laravel-enterprise-backend/references/sqs-queues.md`). The command itself needs only `->withoutOverlapping()` since dispatching the same job twice is handled at the job layer.

---

## The `audit:prune` command

`audit:prune` is the canonical example of a scheduled command in this stack. It deletes `audit_logs` rows beyond the 180-day retention window. Full implementation is in `laravel-enterprise-backend/references/audit-attribute.md`; the schedule entry is:

```php
// routes/console.php
Schedule::command('audit:prune')->dailyAt('03:00')->withoutOverlapping();
```

The command itself:

```php
// app/Console/Commands/PruneAuditLogs.php
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

Notes:
- `audit:prune` runs as a system action — there is no authenticated user. `AuditManager::run()` is not needed here (read-only endpoints and maintenance commands are not themselves audited; see `audit-attribute.md` for the anti-pattern list).
- If the free-tier CockroachDB RU budget is a concern, batch the delete using a subquery loop. CockroachDB (PostgreSQL wire) does not support `DELETE ... LIMIT` — use a `WHERE id IN (SELECT id ... LIMIT n)` pattern instead:

```php
public function handle(): int
{
    do {
        // CockroachDB/PostgreSQL: no DELETE…LIMIT; use a subquery to batch.
        $deleted = DB::affectingStatement(
            "DELETE FROM audit_logs
             WHERE id IN (
                 SELECT id FROM audit_logs
                 WHERE occurred_at < now() - '180 days'::interval
                 LIMIT 1000
             )"
        );
    } while ($deleted > 0);

    return self::SUCCESS;
}
```

---

## Time budget for scheduled commands

The artisan Lambda timeout is `720 s` (12 minutes). Individual commands should stay well under that ceiling:

| Command type | Guideline |
|---|---|
| Fan-out (dispatches SQS jobs) | < 30 s — the command is just a dispatcher |
| Light data transforms or aggregations | < 5 min |
| Batch deletes (e.g., `audit:prune`) | < 10 min; batch via subquery `LIMIT` (not `DELETE … LIMIT`) |
| Anything longer | Redesign as a chain of SQS jobs |

If a scheduled command genuinely needs > 12 minutes, give it a dedicated EventBridge rule with a longer Lambda timeout rather than stretching the shared `artisan` function.

---

## Registering commands

Commands must be auto-discovered or explicitly registered before they appear in the schedule. Laravel 11+ auto-discovers commands in `app/Console/Commands/`. Confirm with:

```bash
php artisan list | grep audit:prune
# Expected: audit:prune   Delete audit_logs rows older than the retention window
```

No `app/Console/Kernel.php` `$commands` array is needed in Laravel 11+.

---

## Anti-patterns

- **Omitting `->withoutOverlapping()`** on any scheduled command. EventBridge delivers at-least-once; without this guard a 2-minute command will be running in two Lambda instances simultaneously after the second tick.
- **In-memory caches for overlap keys.** `/tmp` is not shared between Lambda instances. Overlap prevention only works because `CACHE_STORE=database` is durable. Never switch to `array` or `file` cache drivers on Lambda.
- **Scheduled commands that do heavy work inline.** Long-running inline logic consumes Lambda time and blocks the schedule tick. Dispatch SQS jobs; keep commands fast.
- **Hard-coded `sleep()` or polling loops in commands.** Lambda charges per 100 ms; a polling loop inflates cost and blocks the tick. Fan out to SQS instead.
- **Using `->runInBackground()` on Lambda.** This spawns a child process on the host OS — it does not work inside a Lambda container. Async work goes to SQS jobs.
- **Registering crons as SQS-style repeatable jobs.** Laravel crons belong in `routes/console.php`. The EventBridge tick drives them; there is no BullMQ-style job scheduler in this stack.
- **Assuming local-timezone scheduling.** Lambda runs in UTC. All `dailyAt()`/`weeklyOn()` times in `routes/console.php` are UTC. Document the offset if operators expect a local business time.
- **Running `audit:prune` without batching on high-volume tables.** A single unbounded `DELETE` against millions of rows can exhaust CockroachDB free-tier RUs in one shot. Batch in chunks of 1 000–5 000 rows using the subquery pattern (`DELETE WHERE id IN (SELECT id ... LIMIT n)`) — CockroachDB does not support `DELETE ... LIMIT` directly.
