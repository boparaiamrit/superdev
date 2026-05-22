# Environment Checklist (Phase 1)

What `qa-environment` does. The defaults below are tuned for the design-to-nextjs + nestjs-enterprise-backend stack but adapt for project specifics from EXECUTION_PLAN.md / MIGRATION_PLAN.md.

## Stack verification

Before any seeding, confirm every service is up. Anything not green → STOP.

```bash
# Docker services
docker compose ps --format json | jq -r '.[] | "\(.Service)\t\(.Health // .State)"'
# Expected: all services healthy or running

# API
curl -fsS http://localhost:3001/v1/readiness | jq
# Expected: { "status": "ok", "checks": { "db": "ok", "redis": "ok" } }

# Worker (peek at BullMQ keys)
docker compose exec -T redis redis-cli --scan --pattern 'bull:*' | head -5
# Expected: at least some key prefixes (bull:email-send:..., bull:audit-write:...)

# Web
curl -fsSI http://localhost:3000 | head -1
# Expected: HTTP/1.1 200 (or 307 to /login — both fine)
```

If anything's broken, the QA pipeline halts. `qa-environment` doesn't try to fix infra issues; it surfaces them and stops.

## Seed scale targets

These exercise the right code paths for QA observability. Toy scale (5 rows) hides 80% of what we're looking for.

### Default seed (override from MIGRATION_PLAN if present)

| Entity | Per workspace | Total (3 workspaces) | Why this scale |
|---|---|---|---|
| Workspaces | — | 3 | Tests cross-workspace isolation + multi-tenant rendering |
| Users | 5 | 15 | Covers all roles (Admin, Operator, Pipeline, Viewer + spare) |
| Companies | 250 | 750 | Tests list pagination, sort/filter, table rendering at non-trivial scale |
| Contacts | 2000 (8/company avg) | 6000 | Tests joins, eager loading, large-result handling |
| Mailboxes | 5 | 15 | Different warmup states (Not Started, In Progress, Active, Paused, Failed) |
| Campaigns | 30 | 90 | Mix of all statuses; tests filter-by-status, multi-tab views |
| Leads | 80 across stages | 240 | Tests kanban density per column |
| Deals | 30 across stages | 90 | Same for deal pipeline |
| Email sent (HYPERTABLE) | 50,000 | 150,000 | Exercises Timescale chunks + continuous aggregates + analytics views |
| Audit logs (HYPERTABLE) | 5,000 | 15,000 | Tests audit-log viewer at scale |

### Scale-up workspace

In addition to the three "normal" workspaces, create ONE workspace ("Big Co") with 10x scale:
- 2500 companies, 20000 contacts, 500000 email_sent records

This workspace exists ONLY for performance testing. Flow-testers use it for the large-data edge case.

### Distribution within enums (Title Case)

Don't make every record have the same status — distribute realistically:

- Company industries: Technology 35%, Healthcare 20%, Finance 25%, Logistics 10%, Other 10%
- Campaign statuses: Draft 30%, Scheduled 10%, Sending 5%, Paused 5%, Completed 40%, Archived 10%
- Lead stages: New 30%, Qualified 25%, Proposal Sent 20%, Negotiation 15%, Won 7%, Lost 3%
- User roles: 1 Admin, 1 Operator, 1 Pipeline, 2 Viewer

This catches "the filter only works for one value" bugs.

## Edge-case fixtures (plant exactly these)

These specific records become known targets for flow-testers:

| Edge case | Record | Notes |
|---|---|---|
| Long name | Company `Acme Pharmaceutical & Life Sciences Diagnostic Solutions International Holdings Corp Limited Partnership Trust LLC` (180 chars) | Overflow test |
| Unicode + emoji | Contact `José 🌶️ García-O'Brien` | Rendering + persistence test |
| All-nullable-fields-null | One Contact with `phone=null, title=null, last_email_received_at=null` | Tests nullable handling |
| Zero-children | One Company with 0 contacts, 0 leads, 0 deals | Tests count-zero rendering and empty sub-sections |
| Empty-everything workspace | A workspace `Empty Co` with 0 companies and 0 of everything else | Tests full empty states |
| Unusual TLD | Company with domain `acme.museum` | Tests domain validation/display |
| HTML-like content | Contact with notes containing `<script>alert(1)</script>` | XSS check |
| Numeric edge | Deal with amount `0.01` and another with `999999999.99` | Currency formatting edges |
| Date edges | A record from 1970-01-02 and another scheduled for 2099 | Date range UI |

Record IDs in QA_ENVIRONMENT.md so flow-testers can deep-link to them.

## Seed script invocation

If the project has its own seed (e.g. `apps/api/src/db/seeds/*.seed.ts`), run those first:

```bash
pnpm --filter @<scope>/api seed:dev
```

Verify counts match expectations. If they're below target, supplement with a synthetic generator:

```bash
# Inline TS script the agent writes
cat > /tmp/qa-seed.ts <<'EOF'
import { faker } from '@faker-js/faker';
// ... synthesize records up to the target counts
EOF
pnpm tsx /tmp/qa-seed.ts
```

After seeding, verify:

```bash
docker compose exec -T postgres psql -U postgres -d <app>_dev -c "
  SELECT 'companies' AS table, count(*) FROM companies
  UNION ALL SELECT 'contacts', count(*) FROM contacts
  UNION ALL SELECT 'email_sent', count(*) FROM email_sent
  UNION ALL SELECT 'audit_logs', count(*) FROM audit_logs;
"
```

Counts go into QA_ENVIRONMENT.md's Actual column.

## Test credentials capture

After seed users exist, log in via API and capture the access tokens:

```bash
for email in qa-admin@example.com qa-operator@example.com qa-pipeline@example.com qa-viewer@example.com; do
  TOKEN=$(curl -s -X POST http://localhost:3001/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$email\",\"password\":\"password123\"}" \
    | jq -r '.accessToken')
  echo "$email: $TOKEN" >> qa/credentials.txt
done
```

`qa/credentials.txt` is gitignored. Flow-testers read it for their auth bootstrap.

## Baseline capture

Playwright headless, three viewports, every authed route. Save as PNGs:

```bash
mkdir -p qa/baselines/{desktop,tablet,mobile}

cat > /tmp/qa-baseline.ts <<'EOF'
import { chromium } from 'playwright';

const ROUTES = [
  '/login',
  '/companies',
  '/companies/<seeded-id>',
  '/companies/new',
  '/contacts',
  // ... extract from QA_ENVIRONMENT.md route list
];

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet',  width: 768,  height: 1024 },
  { name: 'mobile',  width: 375,  height: 667 },
];

const ADMIN_TOKEN = process.env.QA_ADMIN_TOKEN!;

const browser = await chromium.launch();
for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    extraHTTPHeaders: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  // Also set the access token in localStorage / cookie as the app expects
  for (const route of ROUTES) {
    const page = await ctx.newPage();
    await page.goto(`http://localhost:3000${route}`);
    await page.waitForLoadState('networkidle');
    const slug = route.replace(/\//g, '-').replace(/^-/, '') || 'root';
    await page.screenshot({
      path: `qa/baselines/${vp.name}/${slug}.png`,
      fullPage: true,
    });
    await page.close();
  }
  await ctx.close();
}
await browser.close();
EOF

QA_ADMIN_TOKEN=$(grep qa-admin qa/credentials.txt | cut -d' ' -f2) \
  pnpm tsx /tmp/qa-baseline.ts
```

Note: how the app expects auth (cookie vs Bearer) determines whether the script sets a cookie or just an Authorization header. Read `apps/web/src/lib/api-client.ts` or `auth-context.tsx` to determine. The agent figures this out from source.

## Anti-patterns

- ❌ Seeding 5 records and calling it done. Find a project that has 5 customers using it; you'll find none of the issues this skill exists for.
- ❌ Distributing every enum 100% to one value. Real data has variety.
- ❌ Forgetting the scale-up workspace. Performance findings need a real-size dataset to surface.
- ❌ Skipping mobile baselines. Most issues are at 375px.
- ❌ Using real-looking credentials. `password123` and `@example.com` only.
- ❌ Running baselines before the page is settled (`networkidle`) — produces flaky screenshots.
