# Database-backed Cache and Sessions

How to configure Laravel's cache and session layers to use the database instead of Redis. Read in Phase 3 (scaffolding) and Phase 5 (per-module caching decisions).

## Why database, not Redis

Lambda functions are stateless and short-lived. Redis requires a persistent TCP connection to a cluster that typically lives **inside a VPC**. A VPC adds:

- NAT Gateway costs for the Lambda-to-internet path
- Elastic Network Interface (ENI) attachment latency on cold starts (~200–400 ms extra)
- Additional infrastructure to manage and secure

CockroachDB is reached over the **public internet** (no VPC). Putting the cache and session tables in the same CockroachDB cluster means:

- Zero extra infra to provision or pay for
- No cold-start ENI penalty
- Single connection target, consistent with the rest of the data layer

The trade-off is throughput: database cache is slower than Redis for very hot keys. For the free-tier / low-traffic target this skill addresses, the simplicity wins. If you outgrow it, the swap is a one-line env change — Redis is a future operational decision, not an architectural prerequisite.

## Required environment variables

Add these to `.env` and `.env.example`. There are **no `REDIS_*` variables** — do not add them.

```ini
# .env.example — cache and session config (no Redis)
CACHE_STORE=database
SESSION_DRIVER=database

# Queue is SQS (not database, not Redis)
QUEUE_CONNECTION=sqs

# DB (CockroachDB serverless — see cockroachdb-eloquent.md for full connection config)
DB_HOST=free-tier.aws-us-east-1.cockroachlabs.cloud
DB_PORT=26257
DB_DATABASE=clustername.defaultdb
DB_USERNAME=app_user
DB_PASSWORD=
DB_SSLMODE=verify-full

# SQS (see sqs-queues.md)
SQS_PREFIX=https://sqs.us-east-1.amazonaws.com/123456789
SQS_QUEUE=default
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

The `CACHE_STORE=database` and `SESSION_DRIVER=database` values match what is already set in `serverless.yml` for production (see `laravel-bref-deploy`). The same env block works locally and on Lambda.

## Create the tables

Run the two artisan commands that scaffold the cache and session migration files, then migrate:

```bash
php artisan make:cache-table
php artisan make:session-table
php artisan migrate
```

This produces two migration files under `database/migrations/`:

- `xxxx_create_cache_table.php` — creates `cache` and `cache_locks` tables
- `xxxx_create_sessions_table.php` — creates `sessions` table

The generated migrations use standard Laravel schema helpers; no changes are needed for CockroachDB because:

- The tables use `VARCHAR`/`TEXT`/`INTEGER` columns — all supported
- There are no `SEQUENCE`-backed auto-increment primary keys on these tables (Laravel uses string keys for cache; sessions use a string `id`)
- `cache_locks` uses an expiration integer column + `SELECT FOR UPDATE` locking — CockroachDB supports `SELECT FOR UPDATE` under serializable isolation

Do not convert these tables to UUID PKs. They are Laravel-owned infrastructure, not domain entities.

## Config file wiring

Laravel's default `config/cache.php` and `config/session.php` read from env; nothing custom is needed beyond setting the env vars. Confirm the `database` store is configured:

```php
// config/cache.php — the 'database' store ships with Laravel, no changes needed
'default' => env('CACHE_STORE', 'database'),

'stores' => [
    'database' => [
        'driver'     => 'database',
        'connection' => env('DB_CACHE_CONNECTION'),   // null → uses default connection
        'table'      => env('DB_CACHE_TABLE', 'cache'),
        'lock_connection' => env('DB_CACHE_LOCK_CONNECTION'),
        'lock_table' => env('DB_CACHE_LOCK_TABLE'),
    ],
    // ...
],
```

```php
// config/session.php — the 'database' driver ships with Laravel, no changes needed
'driver' => env('SESSION_DRIVER', 'database'),
'table'  => env('SESSION_TABLE', 'sessions'),
'connection' => env('SESSION_CONNECTION'),   // null → uses default connection
```

Both configurations point at the same CockroachDB connection (the default `pgsql` connection) unless you explicitly set `DB_CACHE_CONNECTION` or `SESSION_CONNECTION`. Using the default connection is fine for most deployments.

## TTL and locking behavior under CockroachDB serverless

**Cache TTL.** Laravel's database cache store writes an `expiration` unix timestamp column. Expired entries are not automatically pruned — stale rows accumulate until overwritten or explicitly pruned. Run the built-in prune command on a schedule to keep the table lean:

```bash
# routes/console.php — add alongside the audit prune command
Schedule::command('cache:prune-stale-tags')->hourly();
```

For the raw `cache` table (non-tagged entries), stale rows are overwritten on the next write to the same key. The table will not grow unboundedly for active keys. For long-lived apps with many unique keys, add a cleanup cron:

```php
// routes/console.php
Schedule::call(function () {
    DB::table('cache')->where('expiration', '<', now()->timestamp)->delete();
})->daily()->name('prune-expired-cache');
```

**Cache locks.** The `cache_locks` table uses `expiresAt` comparisons; Laravel's `Cache::lock()` uses a `SELECT + INSERT OR UPDATE` pattern that works correctly under CockroachDB's serializable isolation. If two requests race for the same lock, one will get a 40001 serialization error — this is handled transparently by the CockroachDB retry wrapper (see `cockroachdb-eloquent.md`). Do not wrap lock acquisition in `CockroachRetry::transaction()`; that would cause double-retry semantics. Let the lock driver retry natively.

**Sessions.** Session reads are `SELECT … WHERE id = ?` — point lookups on the primary key. Session writes are `INSERT … ON CONFLICT DO UPDATE` (upsert). Both are safe under serializable isolation. Session data is stored serialized in a `TEXT` column; keep session payloads small (auth state, flash messages, CSRF token — nothing else).

## Cache invalidation

The database cache driver supports **tagged caches** and **keyed deletes**. Use one or both depending on the invalidation granularity needed.

**The Nest/Redis pattern that does NOT map:** the Nest caching reference uses `delByPattern()` with Redis `SCAN` to bulk-delete keys matching a glob. There is no SQL equivalent that is both safe and efficient. Do not try to replicate it with `LIKE` queries on the cache table — this is a table scan that locks under serializable isolation.

Use these patterns instead:

### Keyed deletes (exact key invalidation)

The preferred pattern for single-entity and list invalidation. Name keys so you can compute the exact key to delete without scanning.

```php
// Key naming convention — always prefix with workspace ID
// Single entity:   "ws:{workspaceId}:company:{id}"
// List (filtered): "ws:{workspaceId}:company:list:{hash}"
// Aggregate:       "ws:{workspaceId}:agg:company_count"

use Illuminate\Support\Facades\Cache;

class CompanyService
{
    private function cacheKey(string $workspaceId, string $id): string
    {
        return "ws:{$workspaceId}:company:{$id}";
    }

    private function listCacheKey(string $workspaceId, array $filters = []): string
    {
        return "ws:{$workspaceId}:company:list:" . md5(serialize($filters));
    }

    public function find(string $workspaceId, string $id): CompanyData
    {
        return Cache::remember(
            $this->cacheKey($workspaceId, $id),
            ttl: 60,
            callback: fn () => CompanyData::fromModel(
                Company::withCount(['contacts', 'openLeads as open_leads_count'])
                       ->findOrFail($id)
            )
        );
    }

    public function update(string $workspaceId, string $id, UpdateCompanyData $input): CompanyData
    {
        $company = \App\Support\CockroachRetry::transaction(function () use ($id, $input) {
            $c = Company::findOrFail($id);
            $c->update($input->toArray());
            return $c;
        });

        // Invalidate the entity key and all list keys for this workspace
        Cache::forget($this->cacheKey($workspaceId, $id));
        Cache::forget($this->listCacheKey($workspaceId));  // forget the no-filter list
        // If you track filter hashes, store them in a side-channel set and delete each

        return CompanyData::fromModel($company->loadCount('contacts'));
    }
}
```

The workspace prefix in every key is the safety net: even if invalidation misses a key, no cross-tenant data leaks because a different workspace's request uses a different prefix.

### Tagged cache invalidation

Laravel's database cache driver supports cache tags. Use them when you want to group-invalidate a family of keys without tracking individual key names.

```php
// Cache with a tag
Cache::tags(["ws:{$workspaceId}:companies"])->remember(
    "ws:{$workspaceId}:company:{$id}",
    ttl: 60,
    callback: fn () => CompanyData::fromModel(Company::findOrFail($id))
);

// Invalidate all keys tagged for this workspace's companies
Cache::tags(["ws:{$workspaceId}:companies"])->flush();
```

Tags are stored with tag-prefixed keys in the `cache` table; the `cache:prune-stale-tags` command removes orphaned tag entries. The `flush()` call issues targeted deletes by tag — no table scan. This is the correct database-cache alternative to Redis `SCAN + DEL`.

Use tagged caches when:
- A single write invalidates many related keys (e.g., updating a company invalidates company detail, company list, and any deal views that embed company data)
- The set of keys is large or their suffixes are dynamic

Do not use tags if you only ever delete one or two known keys — keyed deletes are simpler.

## TTL conventions

Match the Nest caching reference TTLs — they are stack-agnostic:

| Data type | TTL |
|---|---|
| Single-entity reads | 60 s |
| List queries | 30 s |
| Aggregates / dashboards | 5 min |
| Static reference data (enums, plans) | 24 h |

Skip the cache for audit log queries (must be fresh), anything reflecting auth state (Sanctum token validation is per-request — never cache), and mutation responses (return them fresh; next read repopulates).

## Cross-resource invalidation

When a write to one resource invalidates a view of another, the producing service is responsible. Example: creating a contact updates `company.counts.contacts`.

```php
// app/Domains/Contacts/Services/ContactService.php
public function create(string $workspaceId, CreateContactData $input): ContactData
{
    return app(AuditManager::class)->run('contact.create', 'Contact', function () use ($workspaceId, $input) {
        $contact = \App\Support\CockroachRetry::transaction(
            fn () => Contact::create([...$input->toArray(), 'workspace_id' => $workspaceId])
        );

        // Parent company view embeds contacts count — invalidate
        if ($contact->company_id) {
            Cache::forget("ws:{$workspaceId}:company:{$contact->company_id}");
        }

        return ContactData::fromModel($contact);
    });
}
```

## Anti-patterns

- **Do not use `LIKE '%key%'` on the cache table.** This is a full table scan that acquires row-level locks under serializable isolation. Use keyed deletes or tagged caches.
- **Do not add `REDIS_*` variables.** This stack has no Redis. Adding Redis vars implies a Redis connection that does not exist.
- **Do not cache mutation responses.** Return them fresh; the next read repopulates.
- **Do not cache across tenants.** Every key must be prefixed with `workspaceId`.
- **Do not cache the Eloquent model/raw DB row.** Cache the `Data` view shape. Cache hits then skip both the DB query and the presenter computation.
- **Do not rely on stale-entry expiry alone.** CockroachDB serverless has no background job to reap expired cache rows. Prune actively or write-through-overwrite ensures the table stays bounded.
- **Do not use `Cache::flush()` without a tag.** A global flush clears cache for all tenants and workspaces. Always scope flushes to a tag or delete specific keys.
