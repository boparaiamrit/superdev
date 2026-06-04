# PostgreSQL + TimescaleDB + Eloquent

How to run Eloquent on **PostgreSQL with the TimescaleDB extension** using Laravel's **stock `pgsql` driver** — no third-party DB package. TimescaleDB is just a Postgres extension, so the connection is plain Postgres; time-series tables (audit logs) become **hypertables** with native compression + retention. Read in Phase 3 (scaffolding / DB connection) and Phase 2/5 (per-entity migrations + write paths).

> **(Was CockroachDB in ≤v1.5.)** The stack is now self-managed Postgres+Timescale. Standard Postgres semantics apply: real sequences, joins, `SELECT … FOR UPDATE SKIP LOCKED`, and serializable transactions all work — there are no engine quirks to code around.

## Why stock `pgsql` (no special driver)

- Postgres is Laravel's first-class database — the built-in `pgsql` connection connects unchanged.
- TimescaleDB ships as a **Postgres extension** (`CREATE EXTENSION timescaledb`); it adds hypertables, compression, and retention policies without changing the wire protocol or the driver.
- TLS and host routing for a managed Postgres+Timescale instance are carried in the DSN — nothing Laravel-specific is required.
- Fewer moving parts survive Bref's packaged Lambda runtime better than a forked grammar/connector.

**Host requirement:** the database must support the TimescaleDB extension and the TSL features (compression + retention) — **Timescale Cloud** or a **self-managed Postgres+Timescale** server. Plain managed Postgres without the extension (e.g. Neon) is **not a target for this tier** — it cannot create hypertables or run compression/retention policies.

## Connection (stock pgsql, no third-party driver)

Point the `pgsql` connection at the managed Postgres+Timescale host. It is an ordinary Postgres connection — default port `5432`, `sslmode=require` because the host is reached over the public internet from Bref.

```php
// config/database.php — 'connections' => [ 'pgsql' => [...] ]
'pgsql' => [
    'driver' => 'pgsql',
    'url' => env('DATABASE_URL'),
    'host' => env('DB_HOST', '127.0.0.1'),
    'port' => env('DB_PORT', '5432'),
    'database' => env('DB_DATABASE'),
    'username' => env('DB_USERNAME'),
    'password' => env('DB_PASSWORD'),
    'charset' => 'utf8',
    'prefix' => '',
    'prefix_indexes' => true,
    'search_path' => 'public',
    'sslmode' => env('DB_SSLMODE', 'require'),   // managed host over the public internet
],
```

When `DATABASE_URL` is set, Laravel parses it and the discrete `DB_*` values become fallbacks:

```bash
# .env — single DSN carries host, db, and TLS
DATABASE_URL="postgresql://user:pass@host.tsdb.cloud.timescale.com:5432/tsdb?sslmode=require"
```

No `cluster` param, no prepared-statement workaround, no third-party package. See the deployer's `postgres-timescale-connection.md` for the Bref-side connection (bounded reserved concurrency, `sslmode`, no VPC).

## Enable the extension (first migration)

The very first migration enables TimescaleDB so later migrations can create hypertables. It is idempotent (`IF NOT EXISTS`), so re-running migrate is safe.

```php
// database/migrations/0000_00_00_000000_enable_timescaledb.php
use Illuminate\Support\Facades\DB;

return new class extends \Illuminate\Database\Migrations\Migration {
    public function up(): void
    {
        DB::statement('CREATE EXTENSION IF NOT EXISTS timescaledb');
    }

    public function down(): void
    {
        // leave the extension in place — dropping it would tear down every hypertable
    }
};
```

If `CREATE EXTENSION` fails, the host does not ship TimescaleDB — switch to a Timescale Cloud or self-managed Postgres+Timescale instance (see the host requirement above).

## UUID primary keys (a preference, not a constraint)

UUID PKs are the **default preference** for entity tables (opaque ids that don't leak row counts and are safe to mint client-side). This is a choice, not a workaround — real Postgres `SEQUENCE`s and `bigIncrements` are available if a particular feature wants monotonic ints.

Use Laravel's `HasUuids` trait: it fills the `id` on create and tells Eloquent the key is a non-incrementing string. No DB-level default is needed.

```php
// migration
Schema::create('companies', function (Blueprint $table) {
    $table->uuid('id')->primary();                 // HasUuids fills it; a Postgres SEQUENCE is available if a feature prefers ints
    $table->uuid('workspace_id')->index();         // reference column — NO ->constrained(), NO cascade
    $table->string('name');
    $table->timestampsTz();
});
```

```php
// app/Domains/Companies/Models/Company.php
use Illuminate\Database\Eloquent\Concerns\HasUuids;

class Company extends Model
{
    use HasUuids;   // sets $incrementing = false, $keyType = 'string', and a UUID on create
}
```

Consequences to design around (true of any UUID PK):

- **IDs are not monotonic.** Order by `created_at` to mean "creation order," never by `id`. Tests must not assume sequential ids.
- **Factories** can let `HasUuids` fill `id`, or set `'id' => (string) Str::uuid()` explicitly — either works.
- `timestampsTz()` uses `TIMESTAMPTZ`, stored in UTC.

## Reference-field data model (no hard FKs — kept)

Relationships are **plain reference columns** (`workspace_id`, `company_id`) — **no FK constraints, no `ON DELETE CASCADE`**. This is a deliberate design preference. Postgres fully supports `JOIN`, `DELETE … USING`, and `UPDATE … FROM`; we simply choose to enforce relation integrity in application code rather than in DB constraints.

- Define reference columns as `$table->uuid('company_id')->index();` — index for lookup, but **no `->constrained()` / `->foreign()`**.
- Declare normal Eloquent relations (`belongsTo`/`hasMany`) over the reference columns for read enrichment.
- **Eager-loading and joins are encouraged for reads:** `with(...)`, `withCount(...)`, and `join(...)` all work on real Postgres and are the way you build presenter payloads (see `api-resources.md`).
- **Orphan cleanup is the app's job.** When a workspace or parent entity is deleted, the deleting service (or a queued job) removes dependent rows explicitly — there is no cascade to lean on.

```php
// model — relation over a reference column, NOT an enforced FK
class Contact extends Model
{
    use HasUuids, BelongsToWorkspace;

    public function company(): BelongsTo
    {
        return $this->belongsTo(Company::class); // resolves contacts.company_id -> companies.id
    }
}
```

```php
// reads — eager-load + withCount; joins are fine (real Postgres)
$companies = Company::query()
    ->withCount(['contacts', 'leads as open_leads_count'])  // SQL aggregates, no FK needed
    ->with('owner')                                         // belongsTo over a reference column
    ->paginate();
```

## Time-series uses hypertables

Any high-volume, time-ordered table (audit logs is the canonical one) is a **TimescaleDB hypertable**, not a plain table. A hypertable looks like a normal table to Eloquent and SQL but is transparently chunked by a time column, which makes recent data fast and retention/compression cheap. The hypertable-creation pattern looks like this:

```php
// migration — create a hypertable: plain CREATE TABLE, then promote it
DB::statement("CREATE TABLE audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    action text NOT NULL, subject text NOT NULL, status text NOT NULL,
    duration_ms int, workspace_id uuid, user_id uuid, request_id text, ip text,
    context jsonb, occurred_at timestamptz NOT NULL DEFAULT now()
)");
DB::statement("SELECT create_hypertable('audit_logs', 'occurred_at')");
DB::statement("CREATE INDEX ON audit_logs (workspace_id, occurred_at DESC)");

// Native compression (TSL): compress old chunks, segmented by the common filter column
DB::statement("ALTER TABLE audit_logs SET (timescaledb.compress, timescaledb.compress_segmentby = 'workspace_id')");
DB::statement("SELECT add_compression_policy('audit_logs', INTERVAL '7 days')");

// Native retention (TSL): drop chunks older than the window — no scheduled prune command needed
DB::statement("SELECT add_retention_policy('audit_logs', INTERVAL '180 days')");
```

Note what the native policies replace: there is **no RANGE-partitioned table to maintain and no `audit:prune` console command** — `add_retention_policy` drops old chunks for you, and `add_compression_policy` shrinks the warm tail automatically.

> **This file shows only the hypertable *creation* pattern.** The full audit mechanics — the `#[Audit]` attribute, `AuditManager`, the SQS `AuditWrite` job, and the admin read-side query — live in **`audit-attribute.md`**. Read that reference for the complete setup; the hypertable above is its storage target.

## What we do NOT use

- **No third-party / forked database driver or grammar.** The stock `pgsql` connection is the supported path.
- **No Redis.** Cache and sessions are database-backed (see `db-cache-sessions.md`) so the stateless Lambda runtime needs no VPC-bound cache. The Postgres `database` queue driver is *technically* available now (Postgres supports `SKIP LOCKED`), but queues still run on **AWS SQS** for the serverless/Bref deploy (see `sqs-queues.md`).
- **No FK constraints / cascades.** Reference columns only; relation integrity in app code.
- **No serialization-retry wrapper or "additive-migrations-only" rule.** Postgres DDL and serializable transactions behave normally; wrap writes in a plain `DB::transaction()` when you need atomicity.

## Anti-patterns

- ❌ Adding FK constraints / `ON DELETE CASCADE`. Use reference columns and clean up orphans in app code (this is the kept design preference).
- ❌ Installing a third-party / forked database package "to be safe." The stock `pgsql` connection plus the TimescaleDB extension cover everything; a forked grammar is a liability under Bref.
- ❌ Assuming engine limitations that don't exist here. Sequences, joins, `SKIP LOCKED`, `DELETE … USING`, and real serializable transactions all work — don't code around quirks from a different database.
- ❌ A plain (non-hyper) table for audit/time-series data. It balloons to hundreds of millions of rows — make it a hypertable and let compression + retention policies manage it.
- ❌ Hand-rolling a scheduled prune command for retention. `add_retention_policy` drops old chunks natively — no `audit:prune` command, no scheduler entry.
- ❌ Ordering by `id` to mean creation order. UUID PKs are not monotonic — order by `created_at`.
- ❌ Targeting a Postgres host without the TimescaleDB extension (e.g. Neon for this tier). Hypertables, compression, and retention all require the extension.
