# Caching with Redis

How to cache reads and invalidate on writes. Read in Phase 5 (per-module caching decisions).

## The model

- **Cache-aside**: service checks cache first, falls through to DB, writes back to cache.
- **Write-invalidate**: on every mutation, delete the cached key. Next read repopulates.
- **No write-through.** Adds complexity for marginal gain; sticks with the cache-aside pattern.

## CacheService

`apps/api/src/infrastructure/cache/cache.service.ts`:

```ts
import { Injectable, Inject } from '@nestjs/common';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import type { Cache } from 'cache-manager';

@Injectable()
export class CacheService {
  constructor(@Inject(CACHE_MANAGER) private readonly cache: Cache) {}

  async get<T>(key: string): Promise<T | null> {
    const value = await this.cache.get<T>(key);
    return value ?? null;
  }

  async set<T>(key: string, value: T, ttlSeconds: number): Promise<void> {
    await this.cache.set(key, value, ttlSeconds * 1000);
  }

  async del(key: string): Promise<void> {
    await this.cache.del(key);
  }

  /**
   * Delete every key matching a pattern. Use sparingly — KEYS is O(N).
   * Prefer narrowly-prefixed keys + targeted dels.
   */
  async delByPattern(pattern: string): Promise<void> {
    const store = (this.cache.stores as any)[0]; // cache-manager-redis-yet shape
    const client = store?.client;
    if (!client) return;

    const stream = client.scanStream({ match: pattern, count: 200 });
    for await (const keys of stream) {
      if (keys.length) await client.del(...keys);
    }
  }

  /**
   * Read-through helper: returns cached value if present, otherwise runs the
   * loader, caches the result, and returns it.
   */
  async readThrough<T>(key: string, ttlSeconds: number, loader: () => Promise<T>): Promise<T> {
    const cached = await this.get<T>(key);
    if (cached !== null) return cached;

    const fresh = await loader();
    await this.set(key, fresh, ttlSeconds);
    return fresh;
  }
}
```

## Key naming convention

```
<workspace>:<resource>:<id>             ← single-entity reads
<workspace>:<resource>:list:<hash>      ← list queries (hash of filters)
<workspace>:agg:<name>:<args>           ← aggregates
```

Examples:
- `ws_01HXYZ:company:cmp_01ABC`
- `ws_01HXYZ:company:list:filters=hash_a1b2`
- `ws_01HXYZ:agg:send_volume:days=30`

Workspace prefix is the safety net — even if invalidation is buggy, no cross-tenant leak.

## TTL conventions

- **Single-entity reads:** 60 seconds (short, balances freshness vs hit rate)
- **List queries:** 30 seconds (lists change more often)
- **Aggregates / dashboards:** 5 minutes (heavy queries; users tolerate stale)
- **Static reference data (industries, plans):** 24 hours

If freshness matters more than perf, skip the cache. Caching is opt-in per query, not a default.

## Cache-aside in a service

```ts
// modules/companies/companies.service.ts
async get(workspaceId: string, id: string): Promise<CompanyView> {
  return this.cache.readThrough(
    `${workspaceId}:company:${id}`,
    60,
    async () => {
      const result = await this.repo.findOneWithEnrichment(workspaceId, id);
      if (!result) throw new NotFoundException('Company not found');
      return this.presenter.toView(result.company, result.enrichment);
    },
  );
}
```

The cached value is the **view shape**, not the DB row. This means:
- Less computation on cache hits (no presenter call)
- Larger cached value (but still small for single entities)
- Cache invalidation is keyed on the view, so updates to enrichment data (a new contact count) require invalidation too — see below

## Invalidate on writes

```ts
@Audit({ action: 'company.update', subject: 'Company' })
async update(workspaceId: string, id: string, input: UpdateCompanyInput): Promise<CompanyView> {
  const t = tenantDb(this.db, workspaceId);
  const [row] = await this.db
    .update(companies)
    .set(input)
    .where(t.scope('companies', eq(companies.id, id)))
    .returning();

  if (!row) throw new NotFoundException('Company not found');

  // Invalidate this entity's cache and any list cache for this workspace
  await this.cache.del(`${workspaceId}:company:${id}`);
  await this.cache.delByPattern(`${workspaceId}:company:list:*`);

  // Re-read with enrichment, repopulating the cache
  return this.get(workspaceId, id);
}
```

For deletes: same pattern, just delete keys; no repopulation needed.

## Cross-resource invalidation

When a write to one resource invalidates a cached view of another, the producing service is responsible.

Example: creating a contact updates `company.counts.contacts`. The `ContactsService.create()` invalidates the parent company's cache:

```ts
@Audit({ action: 'contact.create', subject: 'Contact' })
async create(workspaceId: string, input: CreateContactInput) {
  const [row] = await this.db.insert(contacts).values({ ...input, workspaceId }).returning();

  // Parent company's view includes contacts count — invalidate
  if (row.companyId) {
    await this.cache.del(`${workspaceId}:company:${row.companyId}`);
  }

  return this.presenter.toView(row);
}
```

This is awkward but explicit. If invalidation chains get complex, consider event-driven invalidation (the producing service emits an event; subscribers invalidate their own caches). For v1, direct invalidation is simpler.

## What NOT to cache

- **Audit log queries** — must always show fresh data.
- **Anything reflecting auth state** — sessions, permissions, abilities. CASL ability is built per-request from JWT roles; never cache.
- **Counts that change frequently** (e.g., real-time inbox unread count). Show stale → frustrating UX. Skip cache.
- **Mutation responses** — return them fresh.
- **Anything keyed by user (not workspace)** in a workspace-cache. Wrong key scope.

## Cache stampede protection

If a popular key expires and 100 requests hit at once, they all miss and stampede the DB. Two mitigations:

### Soft-expiry with jitter

Add ±10% jitter to TTLs so popular keys don't expire in unison:

```ts
async set<T>(key: string, value: T, ttlSeconds: number) {
  const jittered = ttlSeconds + Math.floor((Math.random() - 0.5) * ttlSeconds * 0.2);
  await this.cache.set(key, value, jittered * 1000);
}
```

### Single-flight (advanced)

For very hot keys, hold a Redis lock while loading:

```ts
async readThroughSingleflight<T>(key: string, ttlSeconds: number, loader: () => Promise<T>) {
  const cached = await this.get<T>(key);
  if (cached !== null) return cached;

  const lockKey = `lock:${key}`;
  const lock = await this.redis.set(lockKey, '1', 'PX', 5000, 'NX');

  if (!lock) {
    // Another request is loading; wait briefly then re-read
    await new Promise((r) => setTimeout(r, 100));
    return this.readThroughSingleflight(key, ttlSeconds, loader);
  }

  try {
    const fresh = await loader();
    await this.set(key, fresh, ttlSeconds);
    return fresh;
  } finally {
    await this.redis.del(lockKey);
  }
}
```

Only reach for this when profiling shows stampedes. Don't pre-optimize.

## Two Redis databases

The scaffolding sets up:
- `REDIS_DB_CACHE=0` for caching
- `REDIS_DB_QUEUE=1` for BullMQ

A `FLUSHDB` on the cache DB doesn't nuke queue state. Useful in dev and after schema changes that obsolete cached shapes.

## Cache warming

Some queries are heavy and predictably accessed (e.g., dashboard aggregates). Pre-warm them in a cron:

```ts
// modules/scheduled-tasks/workers/cache-warmer.worker.ts
@Cron('*/5 * * * *')   // Or registered via SCHEDULED_TASKS queue
async warmDashboards() {
  const workspaces = await this.workspaces.listActive();
  for (const ws of workspaces) {
    await this.analytics.dashboardSummary(ws.id); // cache-side-effect
  }
}
```

Use sparingly — warming many keys synchronously can itself be the load problem.

## Anti-patterns

- ❌ Caching mutation responses. They go to the cache fresh on next read; don't cache the response itself.
- ❌ Caching across tenants. Always prefix with `workspaceId`.
- ❌ Using `del('*')` or `FLUSHDB` from app code. That's an operator action.
- ❌ Long TTLs without invalidation hooks. "It'll fall out of cache eventually" is not a strategy.
- ❌ Caching the DB row instead of the view shape. Cache misses now require re-running the presenter; cache hits do too. Cache the view.
- ❌ Skipping cache and "optimizing later." Add a `@Cacheable` mental model from day one; opt in per query.
