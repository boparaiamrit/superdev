# Performance Checklist (Phase 5)

What `qa-performance-prober` measures. Performance phase runs LAST so the system is otherwise idle.

## Pre-flight

```bash
# Verify nothing else is hammering the stack
docker compose ps
# All flow-testers complete
# No background Playwright processes
ps aux | grep -E "playwright|chromium" | grep -v grep
```

## Web Vitals per route

For each route in the app:

```ts
import { chromium } from 'playwright';

const ROUTES = [...]; // from QA_ENVIRONMENT.md
const results: any[] = [];

const browser = await chromium.launch();

for (const route of ROUTES) {
  // Run each route 3 times; report median to reduce variance
  const samples = [];
  for (let i = 0; i < 3; i++) {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    // Inject auth
    await ctx.addCookies([/* refresh cookie if applicable */]);
    const page = await ctx.newPage();

    await page.goto(`http://localhost:3000${route}`, { waitUntil: 'networkidle' });

    const metrics = await page.evaluate(() => new Promise((resolve) => {
      const observer = new PerformanceObserver((list) => {
        const lcp = list.getEntriesByType('largest-contentful-paint').pop() as any;
        const layoutShifts = list.getEntriesByType('layout-shift') as any[];
        const longTasks = list.getEntriesByType('longtask') as any[];

        resolve({
          lcp: lcp?.startTime,
          cls: layoutShifts.reduce((sum, e) => sum + (e.hadRecentInput ? 0 : e.value), 0),
          tbt: longTasks.reduce((sum, t) => sum + Math.max(0, t.duration - 50), 0),
          longTaskCount: longTasks.length,
        });
      });
      observer.observe({ type: 'largest-contentful-paint', buffered: true });
      observer.observe({ type: 'layout-shift', buffered: true });
      observer.observe({ type: 'longtask', buffered: true });
      // Resolve after 5s if not enough activity
      setTimeout(() => resolve({ note: 'timeout' }), 5000);
    }));

    samples.push(metrics);
    await ctx.close();
  }

  results.push({
    route,
    median: median(samples),
  });
}

await browser.close();
```

### Thresholds

| Metric | ✓ | ⚠ | ✗ |
|---|---|---|---|
| LCP | <1.8s | 1.8-2.5s | >2.5s |
| LCP critical | — | — | >4s = Critical finding |
| CLS | <0.1 | 0.1-0.25 | >0.25 |
| TBT | <200ms | 200-600ms | >600ms |
| Bundle First Load JS | <200KB | 200-300KB | >500KB = High |

## Database query counts

### Enable query logging

```bash
docker compose exec postgres psql -U postgres -d <app>_dev <<SQL
  ALTER SYSTEM SET log_statement = 'all';
  ALTER SYSTEM SET log_min_duration_statement = 0;
  ALTER SYSTEM SET log_destination = 'stderr';
  SELECT pg_reload_conf();
SQL

# Clear current log
docker compose exec postgres truncate -s 0 /var/log/postgresql/postgresql.log 2>/dev/null \
  || docker compose restart postgres   # fallback
```

### Per-action query counting

For each user-visible action:

```bash
count_queries_for() {
  local label=$1
  local before=$(docker compose logs --tail=0 -f postgres 2>&1 | wc -l &)
  # Trigger the action via curl or Playwright
  eval "$2"
  sleep 1
  local after_log=$(docker compose logs --tail=200 postgres 2>/dev/null | grep -c "LOG:  statement:")
  echo "$label: $after_log statements"
}

# Examples
count_queries_for "GET /companies (list 20)" \
  "curl -s -H 'Authorization: Bearer $TOKEN' '$API/companies?per_page=20' > /dev/null"

count_queries_for "GET /companies/:id (detail)" \
  "curl -s -H 'Authorization: Bearer $TOKEN' '$API/companies/$ID' > /dev/null"
```

### Flags

| Pattern | Severity | Action |
|---|---|---|
| List endpoint fires N+1 (N = page size, +1 for count) | High | Refactor to use JOIN or batched fetch |
| List endpoint fires >N+5 queries | High | Look for per-row enrichment loops |
| Detail endpoint fires >5 queries | Medium | Add eager loads for related entities |
| Detail endpoint fires >10 queries | High | Likely N+1 on a sub-collection |
| Any query without `LIMIT` on workspace-scoped table | Medium | Unbounded result; add limit |
| Query with `Seq Scan` on >1000-row table (via EXPLAIN) | High | Missing index |

### Running EXPLAIN ANALYZE

For any flagged slow query, capture the plan:

```bash
# Pick a slow query from the log
docker compose exec postgres psql -U postgres -d <app>_dev -c "
  EXPLAIN ANALYZE
  SELECT * FROM companies
  WHERE workspace_id = '...' AND industry = 'Technology'
  ORDER BY created_at DESC
  LIMIT 20;
"
```

Save plan output to `qa/performance/explain-<endpoint>.txt`.

## Frontend data-volume freezes

For each list page with realistic-scale data:

```ts
// Navigate to scale-up workspace with 2500 records
await page.goto(`${WEB}/companies?per_page=1000`);
await page.waitForLoadState('networkidle');

// Measure filter input responsiveness
const start = performance.now();
await page.fill('input[placeholder*="Search"]', 'A');

// Race: does the visible list change? did a network request fire?
const result = await Promise.race([
  page.waitForResponse(r => r.url().includes('/v1/companies'), { timeout: 5000 })
    .then(() => ({ kind: 'server' as const })),
  page.waitForFunction(() => {
    const rows = document.querySelectorAll('tbody tr');
    return rows.length < 1000;
  }, { timeout: 5000 })
    .then(() => ({ kind: 'client' as const })),
  new Promise(r => setTimeout(() => r({ kind: 'timeout' as const }), 5000)),
]);
const elapsed = performance.now() - start;
```

Findings:
- `kind: 'client'` AND elapsed > 200ms → Medium ("filter blocks main thread")
- `kind: 'client'` AND elapsed > 1000ms → High ("UX broken at scale")
- `kind: 'server'` AND no debounce in source (every keystroke fires) → Medium ("hammering API")
- `kind: 'timeout'` → Critical ("filter doesn't work at all at this scale")

Cross-reference with source:

```bash
# Find the list component for the feature
grep -rln "useCompanies\|useContacts\|useCampaigns" apps/web/src/modules --include="*.tsx"

# Check for client-side filter/sort patterns
grep -rn '\.filter(\|\.sort(\|useMemo' apps/web/src/modules/companies/components --include="*.tsx"
```

If client-side `.filter()` exists on a list with >100 rows, flag as "should be server-side filter".

## Bundle size per route

```bash
cd apps/web
pnpm build 2>&1 | tee /tmp/build-output.txt

# Next.js prints a route table; extract it
awk '/^\s*┌|^\s*├|^\s*└|^Route \(app\)/' /tmp/build-output.txt
```

Parse the table; flag any First Load JS:
- >500KB → High (large bundle hurts mobile)
- >300KB → Medium
- 1 route is >50% above the median → Medium (suspicious; investigate imports)

## Worker / queue performance

For features that produce BullMQ jobs:

```bash
# Watch queue lengths
docker compose exec redis redis-cli LLEN bull:email-send:wait
docker compose exec redis redis-cli LLEN bull:email-send:active

# Trigger N jobs, observe drain rate
for i in $(seq 1 50); do
  curl -X POST $API/campaigns/$CAMPAIGN_ID/send -H "Authorization: Bearer $TOKEN"
done

sleep 10
docker compose exec redis redis-cli LLEN bull:email-send:wait
# Should be dropping toward zero
```

Findings:
- Queue depth stays high while worker is "running" → worker stuck or starved
- Job pickup latency >1s (time from enqueue to active) → bottleneck for any real volume

## Memory growth (long session)

```ts
// Snapshot heap at intervals during a 5-minute scripted session
const heapSamples: number[] = [];
async function snap() {
  const m = await page.evaluate(() => (performance as any).memory?.usedJSHeapSize || 0);
  heapSamples.push(m);
}

await page.goto(`${WEB}/`);
await snap();

// 5 minutes of clicking around
const end = Date.now() + 5 * 60 * 1000;
while (Date.now() < end) {
  await page.goto(`${WEB}/companies`); await snap();
  await page.goto(`${WEB}/contacts`); await snap();
  await page.goto(`${WEB}/campaigns`); await snap();
  await page.goto(`${WEB}/pipeline`); await snap();
}

// Force GC if possible, then final sample
await page.evaluate(() => (window as any).gc?.());  // requires --js-flags="--expose-gc"
await snap();

const growth = heapSamples[heapSamples.length - 1] - heapSamples[0];
const growthMB = growth / 1024 / 1024;
```

Flags:
- Growth > 50MB over 5 min → potential leak (Medium)
- Linear growth across samples (every sample bigger than the last) → real leak (High)

Common culprits to mention in the finding:
- Subscriptions not cleaned up in `useEffect` returns
- WebSocket / SSE connections not closed on unmount
- Chart instances not disposed
- Large objects retained in Zustand store

## QA_PERFORMANCE.md output

```markdown
# QA Performance Report

> Generated: <ISO 8601>
> Stack: <versions>
> Seed counts: see QA_ENVIRONMENT.md (scale-up workspace: 2500 companies)

## Web Vitals (median of 3 samples)

| Route | LCP | CLS | TBT | Bundle | Verdict |
|---|---|---|---|---|---|
| / | 0.8s | 0.02 | 60ms | 124KB | ✓ |
| /companies | 1.2s | 0.04 | 120ms | 142KB | ✓ |
| /campaigns | 3.1s | 0.18 | 780ms | 248KB | ✗ Multiple |
| /pipeline | 2.4s | 0.08 | 340ms | 196KB | ⚠ TBT |
| ... | | | | | |

## Database query counts

(table per endpoint)

## Findings

### P-1 [High] — Companies list fires 21 queries (N+1)

(...)

### P-2 [Critical] — Companies filter freezes at 1000 rows

- Route: /companies?per_page=1000
- Filter response: 2.1s per keystroke (client-side filter blocks main thread)
- Source: apps/web/src/modules/companies/components/list.tsx:42 — `.filter().sort()` in useMemo
- Recommendation: Move to server (`?q=&sort=&page=`); backend already supports per EXECUTION_PLAN.md
- Evidence: qa/performance/companies-filter-trace.zip

## Bundle sizes

(table)

## Worker / queue

(observations)

## Memory

(samples + verdict)
```

## Reset after measurement

```bash
# Disable query logging (it slows the DB)
docker compose exec postgres psql -U postgres -c "
  ALTER SYSTEM SET log_statement = 'none';
  ALTER SYSTEM SET log_min_duration_statement = -1;
  SELECT pg_reload_conf();
"
```
