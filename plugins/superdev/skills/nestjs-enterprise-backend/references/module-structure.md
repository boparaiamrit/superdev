# Nest.js Module Structure

Canonical folder layout. Read in Phase 2 (planning) and Phase 5 (per-module generation).

## `apps/api/` top-level layout

```
apps/api/
├── package.json
├── tsconfig.json
├── nest-cli.json
├── drizzle.config.ts
├── docker-compose.yml          ← Postgres+Timescale, Redis for local dev
├── drizzle/                    ← Generated migrations + custom SQL
│   ├── 0000_init.sql
│   ├── meta/
│   └── custom/                 ← Hand-written Timescale-specific SQL
└── src/
    ├── main.ts                 ← API process entrypoint
    ├── worker.ts               ← Worker process entrypoint (no HTTP)
    ├── app.module.ts           ← Root module — wires infra + feature modules
    ├── db/
    │   ├── client.ts           ← Drizzle db instance
    │   ├── tenant-db.ts        ← Workspace-scoped query wrapper
    │   └── schema/             ← Drizzle table definitions
    ├── infrastructure/         ← Cross-cutting modules (always present)
    ├── common/                 ← Guards, decorators, filters, interceptors, pipes
    └── modules/                ← Feature modules (the bulk of the app)
```

Two entrypoints (`main.ts` and `worker.ts`) is intentional. The API process serves HTTP. The worker process consumes BullMQ jobs. They share modules but boot differently — see `references/scaffolding.md` and `references/bullmq-queues.md`.

## `src/infrastructure/` — cross-cutting modules

Always present, used by every feature module.

```
src/infrastructure/
├── drizzle/
│   ├── drizzle.module.ts       ← Global module, provides DRIZZLE_DB token
│   └── drizzle.constants.ts    ← export const DRIZZLE_DB = Symbol(...)
├── config/
│   ├── config.module.ts
│   ├── config.service.ts       ← Typed access to env
│   └── env.schema.ts           ← Zod schema for env vars
├── logger/
│   ├── logger.module.ts        ← Pino with request/workspace context
│   └── logger.service.ts
├── cache/
│   ├── cache.module.ts         ← cache-manager + Redis
│   ├── cache.service.ts        ← Typed get/set/del helpers
│   └── cache.constants.ts      ← REDIS_CLIENT token for raw ioredis access
├── queue/
│   ├── queue.module.ts         ← BullMQ root config
│   └── queue.constants.ts      ← QUEUE_NAMES constants
├── health/
│   ├── health.module.ts
│   └── health.controller.ts    ← /health, /readiness
└── metrics/
    └── metrics.providers.ts    ← Prometheus counter/histogram providers
```

## `src/common/` — guards, decorators, filters, interceptors

Reusable Nest.js building blocks, not specific to any feature.

```
src/common/
├── guards/
│   ├── jwt-auth.guard.ts
│   └── policies.guard.ts       ← CASL ability enforcement
├── decorators/
│   ├── current-user.decorator.ts
│   ├── current-workspace.decorator.ts
│   ├── current-ability.decorator.ts
│   ├── public.decorator.ts
│   ├── check-ability.decorator.ts   ← CASL rule metadata
│   └── audit.decorator.ts            ← @Audit({ action, subject })
├── filters/
│   └── all-exceptions.filter.ts      ← Normalizes every error to {code, message, details, request_id}
├── interceptors/
│   ├── workspace-context.interceptor.ts  ← Sets req.workspace + AsyncLocalStorage
│   └── audit.interceptor.ts              ← Reads @Audit metadata, enqueues audit-write
├── context/
│   └── workspace-context.ts              ← AsyncLocalStorage<WorkspaceContext>
└── pipes/
    └── (nestjs-zod's ZodValidationPipe is used globally; no custom pipes needed in v1)
```

## `src/modules/<feature>/` — feature modules

Every feature module follows the same shape:

```
src/modules/companies/
├── companies.module.ts          ← Module wiring
├── companies.controller.ts      ← HTTP endpoints (thin)
├── companies.service.ts         ← Business logic, @Audit decorated
├── companies.repository.ts      ← Drizzle queries (incl. enrichment subselects)
├── companies.presenter.ts       ← DB row → view-shape mapper
├── dto/
│   ├── create-company.dto.ts    ← class extends createZodDto(...) from @<scope>/contracts
│   ├── update-company.dto.ts
│   └── company-filters.dto.ts
├── companies.presenter.spec.ts  ← Unit tests for the presenter
├── companies.service.spec.ts    ← Unit tests for the service
└── companies.e2e-spec.ts        ← Integration test (cross-workspace, CASL, audit)
```

### `companies.module.ts`

```ts
import { Module } from '@nestjs/common';
import { CompaniesController } from './companies.controller';
import { CompaniesService } from './companies.service';
import { CompaniesRepository } from './companies.repository';
import { CompaniesPresenter } from './companies.presenter';

@Module({
  controllers: [CompaniesController],
  providers: [CompaniesService, CompaniesRepository, CompaniesPresenter],
  exports: [CompaniesService, CompaniesPresenter],
})
export class CompaniesModule {}
```

### `companies.controller.ts`

```ts
import { Body, Controller, Delete, Get, HttpCode, HttpStatus, Param, Patch, Post, Query } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { CompaniesService } from './companies.service';
import { CreateCompanyDto, UpdateCompanyDto, CompanyFiltersDto } from './dto';
import { CheckAbility } from '@/common/decorators/check-ability.decorator';
import { CurrentWorkspace } from '@/common/decorators/current-workspace.decorator';

@ApiTags('companies')
@Controller('companies')
export class CompaniesController {
  constructor(private readonly companies: CompaniesService) {}

  @Get()
  @CheckAbility({ action: 'read', subject: 'Company' })
  list(@CurrentWorkspace() ws: { id: string }, @Query() filters: CompanyFiltersDto) {
    return this.companies.list(ws.id, filters);
  }

  @Get(':id')
  @CheckAbility({ action: 'read', subject: 'Company' })
  get(@CurrentWorkspace() ws: { id: string }, @Param('id') id: string) {
    return this.companies.get(ws.id, id);
  }

  @Post()
  @CheckAbility({ action: 'create', subject: 'Company' })
  @HttpCode(HttpStatus.CREATED)
  create(@CurrentWorkspace() ws: { id: string }, @Body() input: CreateCompanyDto) {
    return this.companies.create(ws.id, input);
  }

  @Patch(':id')
  @CheckAbility({ action: 'update', subject: 'Company' })
  update(@CurrentWorkspace() ws: { id: string }, @Param('id') id: string, @Body() input: UpdateCompanyDto) {
    return this.companies.update(ws.id, id, input);
  }

  @Delete(':id')
  @CheckAbility({ action: 'delete', subject: 'Company' })
  @HttpCode(HttpStatus.NO_CONTENT)
  delete(@CurrentWorkspace() ws: { id: string }, @Param('id') id: string) {
    return this.companies.delete(ws.id, id);
  }
}
```

Controllers stay this thin:
- Authenticate (via global JwtAuthGuard)
- Authorize (via global PoliciesGuard + `@CheckAbility`)
- Validate (via global ZodValidationPipe + DTOs)
- Delegate to service
- Return

No conditionals, no transformations, no DB calls.

### `companies.service.ts`

```ts
import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { eq } from 'drizzle-orm';
import { DRIZZLE_DB } from '@/infrastructure/drizzle/drizzle.constants';
import { CacheService } from '@/infrastructure/cache/cache.service';
import { tenantDb } from '@/db/tenant-db';
import { companies } from '@/db/schema';
import type { Db } from '@/db/client';
import { Audit } from '@/common/decorators/audit.decorator';
import type { CreateCompanyInput, UpdateCompanyInput, CompanyFilters } from '@<scope>/contracts/companies';
import { CompaniesRepository } from './companies.repository';
import { CompaniesPresenter } from './companies.presenter';

@Injectable()
export class CompaniesService {
  constructor(
    @Inject(DRIZZLE_DB) private readonly db: Db,
    private readonly repo: CompaniesRepository,
    private readonly presenter: CompaniesPresenter,
    private readonly cache: CacheService,
  ) {}

  async list(workspaceId: string, filters: CompanyFilters) {
    const { rows, total } = await this.repo.listWithEnrichment(workspaceId, filters);
    return this.presenter.toListResponse(rows, total, filters.page, filters.per_page);
  }

  async get(workspaceId: string, id: string) {
    return this.cache.readThrough(`${workspaceId}:company:${id}`, 60, async () => {
      const result = await this.repo.findOneWithEnrichment(workspaceId, id);
      if (!result) throw new NotFoundException('Company not found');
      return this.presenter.toView(result.company, result.enrichment);
    });
  }

  @Audit({ action: 'company.create', subject: 'Company' })
  async create(workspaceId: string, input: CreateCompanyInput) {
    const [row] = await this.db
      .insert(companies)
      .values({ ...input, workspaceId, sizeBucket: '1-10' })
      .returning();

    await this.cache.delByPattern(`${workspaceId}:company:list:*`);
    return this.presenter.toView(row, { contactsCount: 0, openLeadsCount: 0, wonDealsCount: 0, lastActivity: null });
  }

  @Audit({ action: 'company.update', subject: 'Company' })
  async update(workspaceId: string, id: string, input: UpdateCompanyInput) {
    const t = tenantDb(this.db, workspaceId);
    const [row] = await this.db
      .update(companies)
      .set(input)
      .where(t.scope('companies', eq(companies.id, id)))
      .returning();

    if (!row) throw new NotFoundException('Company not found');

    await this.cache.del(`${workspaceId}:company:${id}`);
    await this.cache.delByPattern(`${workspaceId}:company:list:*`);

    return this.get(workspaceId, id);
  }

  @Audit({ action: 'company.delete', subject: 'Company' })
  async delete(workspaceId: string, id: string) {
    const t = tenantDb(this.db, workspaceId);
    const result = await this.db.delete(companies).where(t.scope('companies', eq(companies.id, id)));
    if (result.count === 0) throw new NotFoundException('Company not found');

    await this.cache.del(`${workspaceId}:company:${id}`);
    await this.cache.delByPattern(`${workspaceId}:company:list:*`);
  }
}
```

Notice:
- **Every query goes through `tenantDb(db, workspaceId).scope(...)`** — workspace filter is unmissable.
- **Every method that returns data calls the presenter** — no raw rows escape the service.
- **Every mutation is `@Audit`-decorated** — audit log gets a row automatically.
- **`workspaceId` is passed explicitly** — defense in depth alongside `tenantDb()`.

### `companies.repository.ts`

```ts
import { Inject, Injectable } from '@nestjs/common';
import { sql, eq, and, desc, ilike } from 'drizzle-orm';
import { DRIZZLE_DB } from '@/infrastructure/drizzle/drizzle.constants';
import { tenantDb } from '@/db/tenant-db';
import { companies } from '@/db/schema';
import type { Db } from '@/db/client';
import type { CompanyFilters } from '@<scope>/contracts/companies';

@Injectable()
export class CompaniesRepository {
  constructor(@Inject(DRIZZLE_DB) private readonly db: Db) {}

  async listWithEnrichment(workspaceId: string, filters: CompanyFilters) {
    const t = tenantDb(this.db, workspaceId);

    const where = t.scope(
      'companies',
      and(
        filters.search ? ilike(companies.name, `%${filters.search}%`) : undefined,
        filters.industry ? eq(companies.industry, filters.industry) : undefined,
      ),
    );

    const offset = (filters.page - 1) * filters.per_page;

    const rows = await this.db
      .select({
        company: companies,
        contactsCount: sql<number>`(SELECT COUNT(*)::int FROM contacts c WHERE c.company_id = ${companies.id})`,
        openLeadsCount: sql<number>`(SELECT COUNT(*)::int FROM leads l WHERE l.company_id = ${companies.id} AND l.status = 'Open')`,
        wonDealsCount: sql<number>`(SELECT COUNT(*)::int FROM deals d WHERE d.company_id = ${companies.id} AND d.status = 'Won')`,
      })
      .from(companies)
      .where(where)
      .orderBy(desc(companies.createdAt))
      .limit(filters.per_page)
      .offset(offset);

    const [{ count }] = await this.db
      .select({ count: sql<number>`COUNT(*)::int` })
      .from(companies)
      .where(where);

    return {
      rows: rows.map((r) => ({
        company: r.company,
        enrichment: {
          contactsCount: r.contactsCount,
          openLeadsCount: r.openLeadsCount,
          wonDealsCount: r.wonDealsCount,
          lastActivity: null, // load separately for detail views; lists skip for perf
        },
      })),
      total: count,
    };
  }

  // ... findOneWithEnrichment (with last_activity loading)
}
```

The repository builds the enrichment payload the presenter needs. Counts come from subselects (one query, not N+1). For complex aggregations, this is the place — never put SQL in the service.

## `src/db/schema/` — Drizzle definitions

```
src/db/schema/
├── index.ts              ← Re-exports everything
├── enums.ts              ← All pgEnum() declarations
├── workspaces.ts
├── users.ts
├── companies.ts
├── contacts.ts
├── campaigns.ts
├── mailboxes.ts
├── leads.ts
├── deals.ts
├── email-sent.ts         ← HYPERTABLE
├── email-received.ts     ← HYPERTABLE
├── audit-logs.ts         ← HYPERTABLE
└── send-metrics.ts       ← (view onto a continuous aggregate)
```

See `references/drizzle-timescaledb.md` for the schema-authoring patterns and hypertable conversion migrations.

## Naming conventions

- **Folders:** kebab-case (`companies`, `email-send`)
- **Files:** kebab-case with concern suffix (`companies.controller.ts`, `companies.presenter.ts`)
- **Classes:** PascalCase (`CompaniesController`, `CompaniesPresenter`)
- **DTOs:** `<Action><Entity>Dto`
- **Queue names:** kebab-case string constants (`email-send`)
- **Audit actions:** `<subject_lowercase>.<verb>` (`company.create`)
- **Drizzle table variables:** camelCase (`emailSent`); SQL names: snake_case (Drizzle's `casing: 'snake_case'` handles the conversion)

## Where shared types come from

Always:

```ts
import type { CompanyView, CreateCompanyInput } from '@<scope>/contracts/companies';
```

Never:

```ts
import type { CompanyView } from '@/contracts/companies';  // ❌ This file should not exist in apps/api
```

The contracts package lives in `packages/contracts`; the api app imports from it as `@<scope>/contracts`. There is no local copy.

## Anti-patterns

- ❌ Putting business logic in controllers
- ❌ Direct `db` access in controllers — go through a service
- ❌ Skipping `tenantDb().scope()` — every query that touches a workspace-scoped table needs it
- ❌ Returning DB rows from services — always pass through a presenter
- ❌ Local copies of schemas in `apps/api/src/contracts/`. Import from `@<scope>/contracts`.
- ❌ Two modules importing each other's services. Use events or refactor the dependency.
- ❌ One mega-controller with 30 endpoints. Split modules earlier.
- ❌ Forgetting `@Audit` on a mutation. Compliance gaps appear silently.
