# CockroachDB + Eloquent

How to run Eloquent on the CockroachDB serverless free tier using Laravel's **stock `pgsql` driver** — no third-party CockroachDB package. CockroachDB is Postgres-wire-compatible, so every CRDB quirk is handled at the app layer. Read in Phase 3 (scaffolding / DB connection) and Phase 2/5 (per-entity migrations + write paths).

## Why stock `pgsql` (no special driver)

- CockroachDB speaks the Postgres wire protocol — Laravel's built-in `pgsql` connection connects unchanged.
- A dedicated CockroachDB Laravel package adds a maintenance dependency for behavior we can express in a few lines of app code (UUID defaults, a retry helper).
- Serverless cluster routing and TLS are carried entirely in the DSN — nothing Laravel-specific is required.
- Fewer moving parts survive Bref's packaged Lambda runtime better than a forked grammar/connector.

The CRDB-specific concerns — UUID primary keys, `40001` serialization retries, additive migrations, a partitioned audit table — all live in application code, not a driver.

## Connection (stock pgsql, no third-party driver)

Point the `pgsql` connection at CockroachDB serverless. The only CRDB-flavored values are the default port (`26257`), the default database (`defaultdb`), and `sslmode=verify-full`.

```php
// config/database.php — 'connections' => [ 'pgsql' => [...] ]
'pgsql' => [
    'driver' => 'pgsql',
    'url' => env('DATABASE_URL'),
    'host' => env('DB_HOST', '127.0.0.1'),
    'port' => env('DB_PORT', '26257'),          // CockroachDB default
    'database' => env('DB_DATABASE', 'defaultdb'),
    'username' => env('DB_USERNAME'),
    'password' => env('DB_PASSWORD'),
    'charset' => 'utf8',
    'prefix' => '',
    'prefix_indexes' => true,
    'search_path' => 'public',
    'sslmode' => env('DB_SSLMODE', 'verify-full'),
    'options' => array_filter([
        // CockroachDB Cloud serverless: route to the cluster + pin the CA cert.
        // 'cluster' is passed as a connection option, e.g. via the URL:
        //   postgresql://user:pass@host:26257/cluster-name.defaultdb?sslmode=verify-full&sslrootcert=/path/ca.crt
        \PDO::PGSQL_ATTR_DISABLE_PREPARES => true, // safer with CRDB + pgbouncer-style routing
    ]),
],
```

### Where the serverless `cluster` routing lives

CockroachDB Cloud serverless multiplexes many tenants behind one host, so the **cluster routing id is carried in `DATABASE_URL`**, not in a Laravel option:

- The **database name** is prefixed with the cluster id: `clustername.defaultdb` (not bare `defaultdb`).
- The CA certificate is pinned via the `sslrootcert` query parameter.
- `sslmode=verify-full` forces hostname + chain verification.

```bash
# .env — single DSN carries host, cluster, db, TLS, and CA path
DATABASE_URL="postgresql://user:pass@host.cockroachlabs.cloud:26257/cluster-name.defaultdb?sslmode=verify-full&sslrootcert=/var/task/certs/ca.crt"
```

When `DATABASE_URL` is set, Laravel parses it and the discrete `DB_*` values become fallbacks. No special Laravel package is required — the cluster id rides inside the database name and the TLS material rides inside the query string.

## UUID primary keys (no SEQUENCE)

CockroachDB has no auto-increment `SEQUENCE` worth using for PKs (sequential ints create hotspots). Use `gen_random_uuid()` as the column default so the database generates the id, and tell Eloquent the key is a non-incrementing string.

```php
// migration
Schema::create('companies', function (Blueprint $table) {
    $table->uuid('id')->primary()->default(DB::raw('gen_random_uuid()'));
    $table->uuid('workspace_id')->index();        // reference column, NOT a FK constraint (D9)
    $table->string('name');
    $table->timestampsTz();
});
```

```php
// app/Concerns/HasUuidPrimaryKey.php
trait HasUuidPrimaryKey
{
    public $incrementing = false;
    protected $keyType = 'string';
}
```

Add `use HasUuidPrimaryKey;` to every model. Consequences to design around:

- **IDs are not monotonic.** Never order by `id` to mean "creation order" — order by `created_at`. Tests must not assume sequential ids.
- **Factories generate UUIDs.** Let the DB default fill `id`, or set `'id' => (string) Str::uuid()` in the factory; either works.
- `timestampsTz()` uses `TIMESTAMPTZ`, which CockroachDB stores in UTC.

## 40001 serialization retry

CockroachDB runs `SERIALIZABLE` isolation by default and aborts conflicting transactions with SQLSTATE `40001` ("restart transaction"). This is **expected** under concurrency — the contract is that the client retries. Wrap every write transaction in this helper with exponential backoff.

```php
// app/Support/CockroachRetry.php
namespace App\Support;

use Illuminate\Support\Facades\DB;
use Throwable;

final class CockroachRetry
{
    /** Retry a write closure on CockroachDB 40001 serialization failures. */
    public static function transaction(callable $callback, int $attempts = 5)
    {
        for ($attempt = 1; ; $attempt++) {
            try {
                return DB::transaction($callback);
            } catch (Throwable $e) {
                if ($attempt >= $attempts || ! self::isSerializationFailure($e)) {
                    throw $e;
                }
                usleep((int) (random_int(50, 150) * 1000 * (2 ** ($attempt - 1)))); // backoff
            }
        }
    }

    private static function isSerializationFailure(Throwable $e): bool
    {
        return str_contains($e->getMessage(), '40001')
            || str_contains($e->getMessage(), 'restart transaction');
    }
}
```

Use it instead of `DB::transaction()` directly for any write that can race:

```php
use App\Support\CockroachRetry;

$company = CockroachRetry::transaction(fn () => Company::create($input->toArray()));
```

A dedicated Pest test must force the retry path (e.g. by throwing a fake `40001` on the first attempt and asserting the second succeeds) so the backoff stays exercised. Read transactions do not need the wrapper.

## Additive migrations only

CockroachDB performs schema changes online and asynchronously. A `ALTER COLUMN ... TYPE` on an indexed or constrained column can be slow, blocking, or unsupported, and schema changes **cannot run inside an explicit transaction**. Keep migrations additive and never destructive in place.

- **Never** `ALTER COLUMN TYPE` on an indexed/constrained column. Prefer **add-column → backfill → swap reads → drop old column** across separate migrations.
- **Never** run a schema change inside `DB::transaction()` — CRDB rejects DDL in an explicit txn.
- Add nullable columns (or columns with a default) so existing rows stay valid; backfill in a follow-up migration or a queued job.
- Drop the old column only after a deploy proves nothing reads it.

```php
// 1) add the new column (nullable, non-destructive)
Schema::table('companies', function (Blueprint $table) {
    $table->string('region')->nullable();
});

// 2) backfill in a separate migration or queued command, then in a later release drop the old one
```

### Reference-field data model (D9)

Relationships are **plain reference columns** (`workspace_id`, `company_id`) — **no hard FK constraints, no `ON DELETE CASCADE`, no delete-through-join**. CockroachDB *does* support `JOIN`, `DELETE … USING`, and `UPDATE … FROM`; this is a deliberate design preference, not a workaround.

- Define columns as `$table->uuid('company_id')->index();` — index for lookup, but **no `->constrained()` / `->foreign()`**.
- Resolve relationships in application code with normal Eloquent relations (`belongsTo`/`hasMany`) over the reference columns.
- **Orphan cleanup is the app's job.** When a workspace or parent entity is deleted, the deleting service (or a queued job) removes dependent rows explicitly — there is no cascade to lean on.
- This keeps schema changes additive and avoids cross-table constraint locks during CRDB's online schema changes.

```php
// model — relation over a reference column, NOT an enforced FK
class Contact extends Model
{
    use HasUuidPrimaryKey, BelongsToWorkspace;

    public function company(): BelongsTo
    {
        return $this->belongsTo(Company::class); // resolves contacts.company_id -> companies.id
    }
}
```

## Partitioned audit table

The `audit_logs` table is a plain table **RANGE-partitioned by `occurred_at`**, with a scheduled prune command for retention (CockroachDB has no TimescaleDB hypertables, compression, or retention policies). The partitioning DDL, the `#[Audit]` attribute, the `AuditManager`, the SQS `AuditWrite` job, and the prune command all live in **`audit-attribute.md`** — see that reference for the full setup.

## What we do NOT use

- **No `ylsideas/cockroachdb-laravel`** (or any third-party CockroachDB driver/grammar). The stock `pgsql` connection plus this file's app-level helpers cover every CRDB quirk.
- **No Redis.** Cache and sessions are database-backed (see `db-cache-sessions.md`) so the stateless Lambda runtime needs no VPC-bound cache.
- **No TimescaleDB** (no hypertables, continuous aggregates, compression, or retention policies). Time-series/audit data uses a RANGE-partitioned table + scheduled prune (see `audit-attribute.md`).
- **No database queue driver.** CockroachDB does not support `SELECT … FOR UPDATE SKIP LOCKED`, which Laravel's `database` queue connection relies on — so it is unusable here regardless. Queues run on **AWS SQS** (see `sqs-queues.md`).
- **No FK constraints / cascades** (D9) — reference columns only.
- **No native PG enum types.** Title-Case enums map to plain `STRING` columns to dodge CRDB cross-type-cast friction (see `enums-title-case.md`).

## Anti-patterns

- ❌ Installing a third-party CockroachDB driver "to be safe." The stock `pgsql` connection is the supported path; a forked grammar is a liability under Bref.
- ❌ Auto-increment / `SEQUENCE` primary keys. They hotspot in CRDB. Use `gen_random_uuid()` UUID PKs.
- ❌ Ordering by `id` to mean creation order. UUIDs are not monotonic — order by `created_at`.
- ❌ Bare `DB::transaction()` around writes. Wrap concurrent writes in `CockroachRetry::transaction()` so `40001` aborts retry instead of surfacing as 500s.
- ❌ `ALTER COLUMN ... TYPE` on a live indexed column, or any DDL inside a transaction. Use additive add-column + backfill + drop steps.
- ❌ Hard FK constraints / `ON DELETE CASCADE`. Use reference columns (D9) and clean up orphans in app code.
- ❌ Reaching for the `database` queue driver. `SKIP LOCKED` is unsupported on CRDB — use SQS.
- ❌ Adding Redis or TimescaleDB to the stack. Cache/sessions are DB-backed; audit/time-series uses a partitioned table + prune.
