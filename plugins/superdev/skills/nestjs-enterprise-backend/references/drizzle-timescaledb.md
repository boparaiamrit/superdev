# Drizzle ORM + TimescaleDB

How to use Drizzle alongside TimescaleDB. Replaces Prisma entirely. Read in Phase 3 (init) and Phase 5 (per-entity schemas).

## Why Drizzle over Prisma

- Schema is TypeScript code, not a separate DSL — refactors work with normal TS tooling
- Queries are SQL-shaped — no learning a second query DSL
- No client generation step — types come from the schema definitions directly
- Migration files are SQL — easy to inspect, easy to hand-tune for Timescale features
- Edge/serverless friendly — single-import, no bloated client

## Setup

### Install

```bash
cd apps/api
pnpm add drizzle-orm postgres
pnpm add -D drizzle-kit @types/pg
```

### `apps/api/drizzle.config.ts`

```ts
import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  schema: './src/db/schema/index.ts',
  out: './drizzle',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
  casing: 'snake_case',
  verbose: true,
  strict: true,
});
```

`casing: 'snake_case'` makes Drizzle automatically convert TS camelCase columns to snake_case in SQL (e.g., `headcountCurrent` → `headcount_current`). This aligns with the contract shape.

### `apps/api/src/db/client.ts`

```ts
import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema';

const queryClient = postgres(process.env.DATABASE_URL!, {
  max: 20,
  idle_timeout: 30,
  connect_timeout: 10,
});

export const db = drizzle(queryClient, { schema, casing: 'snake_case' });

export type Db = typeof db;
export type DbTx = Parameters<Parameters<typeof db.transaction>[0]>[0];
```

### The Drizzle module (Nest.js)

`apps/api/src/infrastructure/drizzle/drizzle.module.ts`:

```ts
import { Global, Module } from '@nestjs/common';
import { DRIZZLE_DB } from './drizzle.constants';
import { db } from '@/db/client';

@Global()
@Module({
  providers: [{ provide: DRIZZLE_DB, useValue: db }],
  exports: [DRIZZLE_DB],
})
export class DrizzleModule {}
```

Services inject the db:

```ts
import { Inject, Injectable } from '@nestjs/common';
import { DRIZZLE_DB } from '@/infrastructure/drizzle/drizzle.constants';
import type { Db } from '@/db/client';

@Injectable()
export class CompaniesService {
  constructor(@Inject(DRIZZLE_DB) private readonly db: Db) {}
}
```

## Schema definitions

### `apps/api/src/db/schema/enums.ts`

```ts
import { pgEnum } from 'drizzle-orm/pg-core';

// All enum values are Title Case — they are the wire format AND the UI label.
// Postgres handles spaces and mixed case fine; spaces are legal inside enum values.

export const planEnum = pgEnum('plan', ['Starter', 'Growth', 'Enterprise']);

export const roleEnum = pgEnum('role', ['Admin', 'Operator', 'Pipeline', 'Viewer']);

export const industryEnum = pgEnum('industry', [
  'Technology', 'Healthcare', 'Finance', 'Logistics', 'Other',
]);

// Numeric ranges stay as ranges — render naturally with a unit suffix at the view site.
export const sizeBucketEnum = pgEnum('size_bucket', [
  '1-10', '11-50', '51-200', '201-1000', '1000+',
]);

export const growthSignalEnum = pgEnum('growth_signal', ['Growing', 'Stable', 'Declining']);

export const bounceStatusEnum = pgEnum('bounce_status', ['None', 'Soft', 'Hard', 'Complaint']);

export const warmupStatusEnum = pgEnum('warmup_status', [
  'Not Started', 'In Progress', 'Active', 'Paused', 'Failed',
]);

export const campaignStatusEnum = pgEnum('campaign_status', [
  'Draft', 'Scheduled', 'Sending', 'Paused', 'Completed', 'Archived',
]);

export const leadStageEnum = pgEnum('lead_stage', [
  'New', 'Qualified', 'Proposal Sent', 'Negotiation', 'Won', 'Lost',
]);

export const auditStatusEnum = pgEnum('audit_status', ['Success', 'Failure']);
```

Inserts and queries match the case exactly:

```ts
await db.insert(companies).values({ industry: 'Technology', ... });  // ✅
await db.insert(companies).values({ industry: 'technology', ... });  // ❌ runtime error: invalid input value

const rows = await db.select().from(companies).where(eq(companies.industry, 'Technology'));  // ✅
```

### `apps/api/src/db/schema/workspaces.ts`

```ts
import { pgTable, text, timestamp } from 'drizzle-orm/pg-core';
import { createId } from '@paralleldrive/cuid2';
import { planEnum } from './enums';

export const workspaces = pgTable('workspaces', {
  id: text().primaryKey().$defaultFn(() => createId()),
  name: text().notNull(),
  plan: planEnum().notNull().default('STARTER'),
  createdAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp({ withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});

export type Workspace = typeof workspaces.$inferSelect;
export type WorkspaceInsert = typeof workspaces.$inferInsert;
```

Install the CUID helper:

```bash
pnpm add @paralleldrive/cuid2
```

### `apps/api/src/db/schema/companies.ts`

```ts
import { pgTable, text, integer, jsonb, timestamp, index, uniqueIndex } from 'drizzle-orm/pg-core';
import { createId } from '@paralleldrive/cuid2';
import { workspaces } from './workspaces';
import { industryEnum, sizeBucketEnum, growthSignalEnum } from './enums';

export const companies = pgTable(
  'companies',
  {
    id: text().primaryKey().$defaultFn(() => createId()),
    workspaceId: text().notNull().references(() => workspaces.id, { onDelete: 'cascade' }),
    name: text().notNull(),
    domain: text(),
    industry: industryEnum().notNull(),
    sizeBucket: sizeBucketEnum().notNull(),
    headcountCurrent: integer().notNull().default(0),
    headcount12moAgo: integer(),
    growthSignal: growthSignalEnum().notNull().default('Stable'),
    customFields: jsonb().notNull().default({}),
    createdAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp({ withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
  },
  (t) => ({
    workspaceDomainUnique: uniqueIndex('companies_workspace_domain_uq').on(t.workspaceId, t.domain),
    workspaceCreated: index('companies_workspace_created_idx').on(t.workspaceId, t.createdAt),
    workspaceIndustry: index('companies_workspace_industry_idx').on(t.workspaceId, t.industry),
  }),
);

export type Company = typeof companies.$inferSelect;
export type CompanyInsert = typeof companies.$inferInsert;
```

### `apps/api/src/db/schema/email-sent.ts` (hypertable)

```ts
import { pgTable, text, timestamp, index, primaryKey } from 'drizzle-orm/pg-core';
import { createId } from '@paralleldrive/cuid2';
import { bounceStatusEnum } from './enums';

export const emailSent = pgTable(
  'email_sent',
  {
    id: text().notNull().$defaultFn(() => createId()),
    workspaceId: text().notNull(),
    mailboxId: text().notNull(),
    draftId: text().notNull(),
    campaignId: text(),
    contactId: text().notNull(),
    messageId: text().notNull(),
    threadId: text(),
    subject: text().notNull(),
    sentAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
    bounceStatus: bounceStatusEnum().notNull().default('None'),
  },
  (t) => ({
    // PK must include the time column for hypertable partitioning
    pk: primaryKey({ columns: [t.sentAt, t.id] }),
    workspaceSent: index('email_sent_workspace_sent_idx').on(t.workspaceId, t.sentAt),
    mailboxSent: index('email_sent_mailbox_sent_idx').on(t.mailboxId, t.sentAt),
    campaignSent: index('email_sent_campaign_sent_idx').on(t.campaignId, t.sentAt),
    contactSent: index('email_sent_contact_sent_idx').on(t.contactId, t.sentAt),
    messageIdLookup: index('email_sent_message_id_idx').on(t.messageId),
  }),
);

export type EmailSent = typeof emailSent.$inferSelect;
export type EmailSentInsert = typeof emailSent.$inferInsert;
```

**Critical:** the primary key includes the time column (`sentAt`). Timescale requires this for partitioning.

### `apps/api/src/db/schema/audit-logs.ts` (hypertable)

```ts
import { pgTable, text, jsonb, timestamp, index, primaryKey } from 'drizzle-orm/pg-core';
import { createId } from '@paralleldrive/cuid2';

export const auditLogs = pgTable(
  'audit_logs',
  {
    id: text().notNull().$defaultFn(() => createId()),
    workspaceId: text().notNull(),
    userId: text(),
    action: text().notNull(),         // e.g. 'campaign.send', 'company.delete'
    subjectType: text().notNull(),     // e.g. 'Campaign', 'Company'
    subjectId: text(),
    requestId: text(),
    ip: text(),
    userAgent: text(),
    status: text().notNull(),          // 'Success' | 'Failure'
    durationMs: text(),
    metadata: jsonb().notNull().default({}),
    occurredAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.occurredAt, t.id] }),
    workspaceTime: index('audit_workspace_time_idx').on(t.workspaceId, t.occurredAt),
    userTime: index('audit_user_time_idx').on(t.userId, t.occurredAt),
    subjectTime: index('audit_subject_time_idx').on(t.subjectType, t.subjectId, t.occurredAt),
    actionTime: index('audit_action_time_idx').on(t.action, t.occurredAt),
  }),
);

export type AuditLog = typeof auditLogs.$inferSelect;
export type AuditLogInsert = typeof auditLogs.$inferInsert;
```

### `apps/api/src/db/schema/index.ts`

```ts
export * from './enums';
export * from './workspaces';
export * from './users';
export * from './companies';
export * from './contacts';
export * from './campaigns';
export * from './mailboxes';
export * from './email-sent';
export * from './email-received';
export * from './audit-logs';
// ...
```

## Migrations

### Generate

```bash
pnpm drizzle-kit generate --name init
```

Produces `drizzle/0000_init.sql`. Inspect before applying.

### Apply

```bash
pnpm drizzle-kit migrate
```

Or programmatically (recommended for prod deploys):

```ts
// apps/api/src/db/migrate.ts
import { drizzle } from 'drizzle-orm/postgres-js';
import { migrate } from 'drizzle-orm/postgres-js/migrator';
import postgres from 'postgres';

const sql = postgres(process.env.DATABASE_URL!, { max: 1 });
const db = drizzle(sql);

await migrate(db, { migrationsFolder: './drizzle' });
await sql.end();
```

Run via `pnpm tsx src/db/migrate.ts` in CI.

### TimescaleDB initialization migration

Drizzle won't create the extension or convert tables to hypertables. Add a manual SQL migration after the initial schema migration.

```bash
# Create a custom migration file
mkdir -p drizzle/custom
```

`drizzle/custom/01-timescale-init.sql`:

```sql
-- One-time extension setup
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Convert email_sent to hypertable
SELECT create_hypertable(
  'email_sent',
  'sent_at',
  chunk_time_interval => INTERVAL '7 days',
  if_not_exists => TRUE,
  migrate_data => TRUE
);

ALTER TABLE email_sent SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'workspace_id, mailbox_id',
  timescaledb.compress_orderby = 'sent_at DESC'
);

SELECT add_compression_policy('email_sent', INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('email_sent', INTERVAL '730 days', if_not_exists => TRUE);

-- Convert audit_logs to hypertable
SELECT create_hypertable(
  'audit_logs',
  'occurred_at',
  chunk_time_interval => INTERVAL '7 days',
  if_not_exists => TRUE,
  migrate_data => TRUE
);

ALTER TABLE audit_logs SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'workspace_id',
  timescaledb.compress_orderby = 'occurred_at DESC'
);

SELECT add_compression_policy('audit_logs', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('audit_logs', INTERVAL '365 days', if_not_exists => TRUE);

-- Continuous aggregate: daily send metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_send_metrics
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 day', sent_at) AS day,
  workspace_id,
  mailbox_id,
  COUNT(*)                                              AS sent_count,
  COUNT(*) FILTER (WHERE bounce_status = 'Hard')        AS hard_bounces,
  COUNT(*) FILTER (WHERE bounce_status = 'Soft')        AS soft_bounces,
  COUNT(*) FILTER (WHERE bounce_status = 'Complaint')   AS complaints
FROM email_sent
GROUP BY day, workspace_id, mailbox_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('daily_send_metrics',
  start_offset => INTERVAL '2 days',
  end_offset   => INTERVAL '1 hour',
  schedule_interval => INTERVAL '30 minutes',
  if_not_exists => TRUE
);
```

Apply via a helper script:

```ts
// apps/api/src/db/apply-custom.ts
import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import postgres from 'postgres';

const sql = postgres(process.env.DATABASE_URL!, { max: 1 });
const dir = join(process.cwd(), 'drizzle/custom');
const files = (await readdir(dir)).filter((f) => f.endsWith('.sql')).sort();

for (const file of files) {
  console.log(`Applying ${file}`);
  const content = await readFile(join(dir, file), 'utf8');
  await sql.unsafe(content);
}

await sql.end();
console.log('Custom migrations applied');
```

Run after `drizzle-kit migrate`: `pnpm tsx src/db/apply-custom.ts`.

For a more robust solution, track which custom migrations have been applied in a `custom_migrations` table. For v1 the idempotent `IF NOT EXISTS` guards make re-running safe.

## Workspace-scoped queries

Drizzle has no Prisma-style middleware. Build a tenant-scoped wrapper instead.

`apps/api/src/db/tenant-db.ts`:

```ts
import { eq, and, type SQL } from 'drizzle-orm';
import type { Db } from './client';
import * as schema from './schema';

const WORKSPACE_SCOPED_TABLES = {
  companies: schema.companies,
  contacts: schema.contacts,
  campaigns: schema.campaigns,
  mailboxes: schema.mailboxes,
  emailSent: schema.emailSent,
  emailReceived: schema.emailReceived,
  auditLogs: schema.auditLogs,
} as const;

type ScopedTable = keyof typeof WORKSPACE_SCOPED_TABLES;

export function tenantDb(db: Db, workspaceId: string) {
  return {
    raw: db,
    workspaceId,

    /**
     * Returns a where clause that combines the workspace filter with any
     * additional filter. Use this in every query against workspace-scoped tables.
     */
    scope<T extends ScopedTable>(table: T, where?: SQL): SQL {
      const tbl = WORKSPACE_SCOPED_TABLES[table];
      const workspaceFilter = eq(tbl.workspaceId, workspaceId);
      return where ? and(workspaceFilter, where)! : workspaceFilter;
    },
  };
}

export type TenantDb = ReturnType<typeof tenantDb>;
```

In services:

```ts
@Injectable()
export class CompaniesService {
  constructor(@Inject(DRIZZLE_DB) private readonly db: Db) {}

  async list(workspaceId: string, filters: CompanyFilters): Promise<CompanyListResponse> {
    const t = tenantDb(this.db, workspaceId);
    const where = t.scope('companies', filters.industry ? eq(companies.industry, filters.industry) : undefined);

    const rows = await t.raw.query.companies.findMany({ where, /* ... */ });
    const total = await t.raw.$count(companies, where);

    return this.presenter.toListResponse(rows, total, filters);
  }
}
```

Workspace ID is passed explicitly. The `scope()` helper guarantees the filter is applied. Tests verify it.

## Querying hypertables

### Time-range query (the main read pattern)

```ts
import { sql, and, eq, gte } from 'drizzle-orm';
import { dailySendMetrics } from '@/db/schema/views'; // Defined as a Drizzle view

async getSendVolume(workspaceId: string, days: number) {
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  return this.db
    .select({
      day: dailySendMetrics.day,
      sentCount: sql<number>`SUM(${dailySendMetrics.sentCount})::int`,
    })
    .from(dailySendMetrics)
    .where(and(eq(dailySendMetrics.workspaceId, workspaceId), gte(dailySendMetrics.day, since)))
    .groupBy(dailySendMetrics.day)
    .orderBy(dailySendMetrics.day);
}
```

The continuous aggregate is queried like any other table.

### Inserting events

```ts
async recordSent(input: EmailSentInsert): Promise<void> {
  await this.db.insert(emailSent).values(input);
}
```

Hypertables accept normal Drizzle inserts.

## Anti-patterns

- ❌ Frequently-mutated rows in a hypertable. Hypertables are append-only. Mutate the `Lead` row in a regular table; log changes to `lead_events` hypertable.
- ❌ Omitting the time column from the primary key. `create_hypertable` fails.
- ❌ Querying hypertables without a time range. Full scan across all chunks.
- ❌ Using `db` (raw client) in feature services. Use `tenantDb(db, workspaceId).scope(...)` so the workspace filter is unmissable.
- ❌ Editing migration files after they've shipped. Make a new one.
- ❌ Forgetting `casing: 'snake_case'`. Causes the contract (snake_case) to drift from the DB (camelCase).
