# View Presenter Pattern

The pattern that enforces the "no `?.` or `??` on the frontend" contract. Every service method runs DB rows through a presenter that produces the rich, view-ready response shape defined in `packages/contracts`. Read this in Phase 5 — every module needs a presenter.

## The contract

1. Service queries the DB → gets a row or set of rows
2. Service calls `presenter.toView(row, ctx)` → gets a view-shape object
3. Service returns the view object

The frontend renders `view.headcount.growth_signal.label` directly. No optional chains. No nullish coalescing. The presenter has already built every label, every count, every discriminated-union variant.

## Why a presenter, not a service method

Three reasons:

1. **Testability** — `presenter.toView()` is a pure function. Unit tests pass DB-shaped fixtures, assert the view shape.
2. **Composition** — list responses, detail responses, and nested includes (e.g. `campaign.contacts[i]`) all reuse the same presenter.
3. **Discipline** — moving the transformation to a named class makes it impossible to "forget" and accidentally return a raw DB row from a service.

## File layout

```
apps/api/src/modules/companies/
├── companies.module.ts
├── companies.controller.ts
├── companies.service.ts
├── companies.repository.ts       ← (optional) complex queries
├── companies.presenter.ts        ← THIS FILE
├── dto/
│   ├── create-company.dto.ts
│   └── update-company.dto.ts
└── tests/
    ├── companies.presenter.spec.ts   ← Unit tests for the presenter
    └── companies.service.spec.ts
```

## Presenter shape

A presenter is an injectable class with pure methods.

```ts
// apps/api/src/modules/companies/companies.presenter.ts
import { Injectable } from '@nestjs/common';
import type { Company } from '@/db/schema/companies';
import type {
  CompanyView,
  CompanyListResponse,
  Industry,
  SizeBucket,
  GrowthSignalKind,
} from '@<scope>/contracts/companies';

// What the presenter needs alongside the row to build the view
type CompanyEnrichment = {
  contactsCount: number;
  openLeadsCount: number;
  wonDealsCount: number;
  lastActivity: LastActivityRow | null;
};

type LastActivityRow =
  | { kind: 'Email Sent';     occurredAt: Date; subject: string }
  | { kind: 'Email Received'; occurredAt: Date; preview: string }
  | { kind: 'Deal Won';       occurredAt: Date; amountCents: number; currency: string };

type LastActivityRow =
  | { kind: 'Email Sent';     occurredAt: Date; subject: string }
  | { kind: 'Email Received'; occurredAt: Date; preview: string }
  | { kind: 'Deal Won';       occurredAt: Date; amountCents: number; currency: string };

@Injectable()
export class CompaniesPresenter {
  toView(row: Company, enrichment: CompanyEnrichment): CompanyView {
    const headcount = this.buildHeadcount(row.headcountCurrent, row.headcount12moAgo);

    return {
      id: row.id,
      name: row.name,
      domain: row.domain,
      // industry is already Title Case in the DB — pass through, no transformation
      industry: row.industry,
      // numeric ranges render naturally — append unit at the view site if desired
      size_bucket: row.sizeBucket,
      headcount,
      counts: {
        contacts:   enrichment.contactsCount,
        open_leads: enrichment.openLeadsCount,
        won_deals:  enrichment.wonDealsCount,
      },
      last_activity: this.buildLastActivity(enrichment.lastActivity),
      created_at: row.createdAt.toISOString(),
      updated_at: row.updatedAt.toISOString(),
    };
  }

  toListResponse(
    rows: Array<{ company: Company; enrichment: CompanyEnrichment }>,
    total: number,
    page: number,
    perPage: number,
  ): CompanyListResponse {
    return {
      data: rows.map(({ company, enrichment }) => this.toView(company, enrichment)),
      total,
      page,
      per_page: perPage,
    };
  }

  // ────────────────────────────────────────────────────────────────────────
  // Private builders — each returns a value-typed sub-shape
  // ────────────────────────────────────────────────────────────────────────

  private buildHeadcount(current: number, twelveMonthsAgo: number | null): CompanyView['headcount'] {
    const prior = twelveMonthsAgo ?? current;     // Use current as fallback for delta math
    const delta = prior === 0 ? 0 : ((current - prior) / prior) * 100;
    const signal = this.classifyGrowth(delta);
    return {
      current,
      twelve_months_ago: prior,
      delta_pct: Math.round(delta * 10) / 10,
      growth_signal: signal,
    };
  }

  private classifyGrowth(deltaPct: number): CompanyView['headcount']['growth_signal'] {
    if (deltaPct >= 10) {
      return { kind: 'Growing', label: `+${deltaPct.toFixed(1)}% YoY` };
    }
    if (deltaPct <= -10) {
      return { kind: 'Declining', label: `${deltaPct.toFixed(1)}% YoY` };
    }
    return { kind: 'Stable', label: 'Stable headcount' };
  }

  private buildLastActivity(row: LastActivityRow | null): CompanyView['last_activity'] {
    if (!row) return { kind: 'None' };
    const at = row.occurredAt.toISOString();
    const relative = this.relativeTime(row.occurredAt);

    switch (row.kind) {
      case 'Email Sent':
        return { kind: 'Email Sent', at, subject: row.subject, label: `Sent “${row.subject}” ${relative}` };
      case 'Email Received':
        return { kind: 'Email Received', at, preview: row.preview, label: `Replied ${relative}` };
      case 'Deal Won':
        return {
          kind: 'Deal Won',
          at,
          amount_label: this.formatMoney(row.amountCents, row.currency),
          label: `Won deal — ${this.formatMoney(row.amountCents, row.currency)} ${relative}`,
        };
    }
  }

  private formatMoney(cents: number, currency: string): string {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100);
  }

  private relativeTime(d: Date): string {
    const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
    if (seconds < 60)       return 'just now';
    if (seconds < 3600)     return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86_400)   return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604_800)  return `${Math.floor(seconds / 86_400)}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
}
```

Notice what's there:

- Every field in `CompanyView` is built explicitly. No spread of the raw row.
- Counts default to numbers, never undefined.
- The `last_activity` discriminated union has a branch for every variation, including `none`.
- Labels are constructed server-side. Frontend renders `view.last_activity.label` and is done.
- Date objects are converted to ISO strings at the boundary.

## Service using the presenter

```ts
// apps/api/src/modules/companies/companies.service.ts
import { Injectable, Inject, NotFoundException } from '@nestjs/common';
import { eq } from 'drizzle-orm';
import { DRIZZLE_DB } from '@/infrastructure/drizzle/drizzle.constants';
import { tenantDb } from '@/db/tenant-db';
import { companies } from '@/db/schema';
import type { Db } from '@/db/client';
import type { CreateCompanyInput, UpdateCompanyInput, CompanyFilters } from '@<scope>/contracts/companies';
import { CompaniesPresenter } from './companies.presenter';
import { Audit } from '@/common/decorators/audit.decorator';

@Injectable()
export class CompaniesService {
  constructor(
    @Inject(DRIZZLE_DB) private readonly db: Db,
    private readonly presenter: CompaniesPresenter,
    private readonly repo: CompaniesRepository,
  ) {}

  async list(workspaceId: string, filters: CompanyFilters) {
    const { rows, total } = await this.repo.listWithEnrichment(workspaceId, filters);
    return this.presenter.toListResponse(rows, total, filters.page, filters.per_page);
  }

  async get(workspaceId: string, id: string) {
    const result = await this.repo.findOneWithEnrichment(workspaceId, id);
    if (!result) throw new NotFoundException('Company not found');
    return this.presenter.toView(result.company, result.enrichment);
  }

  @Audit({ action: 'company.create', subject: 'Company' })
  async create(workspaceId: string, input: CreateCompanyInput) {
    const [row] = await this.db
      .insert(companies)
      .values({ ...input, workspaceId, sizeBucket: '1-10' })
      .returning();
    const enrichment = { contactsCount: 0, openLeadsCount: 0, wonDealsCount: 0, lastActivity: null };
    return this.presenter.toView(row, enrichment);
  }

  @Audit({ action: 'company.update', subject: 'Company', subjectIdParam: 'id' })
  async update(workspaceId: string, id: string, input: UpdateCompanyInput) {
    const t = tenantDb(this.db, workspaceId);
    const [row] = await this.db
      .update(companies)
      .set(input)
      .where(t.scope('companies', eq(companies.id, id)))
      .returning();
    if (!row) throw new NotFoundException('Company not found');
    return this.get(workspaceId, id); // Re-read with enrichment
  }

  @Audit({ action: 'company.delete', subject: 'Company', subjectIdParam: 'id' })
  async delete(workspaceId: string, id: string) {
    const t = tenantDb(this.db, workspaceId);
    const result = await this.db.delete(companies).where(t.scope('companies', eq(companies.id, id)));
    if (result.count === 0) throw new NotFoundException('Company not found');
  }
}
```

Every method that returns data calls the presenter. No exceptions.

## Repository for enrichment queries

The presenter needs enrichment data (counts, last activity). The repository builds it efficiently with a single query when possible.

```ts
// apps/api/src/modules/companies/companies.repository.ts
import { Injectable, Inject } from '@nestjs/common';
import { sql, eq, and, count } from 'drizzle-orm';
import { DRIZZLE_DB } from '@/infrastructure/drizzle/drizzle.constants';
import { tenantDb } from '@/db/tenant-db';
import { companies, contacts, leads, deals, emailSent } from '@/db/schema';
import type { Db } from '@/db/client';

@Injectable()
export class CompaniesRepository {
  constructor(@Inject(DRIZZLE_DB) private readonly db: Db) {}

  async findOneWithEnrichment(workspaceId: string, id: string) {
    const t = tenantDb(this.db, workspaceId);

    const [row] = await this.db
      .select({
        company: companies,
        contactsCount: sql<number>`(SELECT COUNT(*)::int FROM contacts c WHERE c.company_id = ${companies.id})`,
        openLeadsCount: sql<number>`(SELECT COUNT(*)::int FROM leads l WHERE l.company_id = ${companies.id} AND l.status = 'Open')`,
        wonDealsCount: sql<number>`(SELECT COUNT(*)::int FROM deals d WHERE d.company_id = ${companies.id} AND d.status = 'Won')`,
      })
      .from(companies)
      .where(t.scope('companies', eq(companies.id, id)))
      .limit(1);

    if (!row) return null;

    const lastActivity = await this.findLastActivity(workspaceId, id);

    return {
      company: row.company,
      enrichment: {
        contactsCount: row.contactsCount,
        openLeadsCount: row.openLeadsCount,
        wonDealsCount: row.wonDealsCount,
        lastActivity,
      },
    };
  }

  // ... listWithEnrichment, findLastActivity, etc.
}
```

The point: even when the data comes from multiple tables, the **service** sees one combined object, calls **one** presenter method, and returns the view shape. The frontend never sees the intermediate join.

## Testing the presenter

```ts
// apps/api/src/modules/companies/tests/companies.presenter.spec.ts
import { CompaniesPresenter } from '../companies.presenter';

describe('CompaniesPresenter', () => {
  const presenter = new CompaniesPresenter();

  const baseCompany = {
    id: 'cmp_1',
    workspaceId: 'ws_1',
    name: 'Acme',
    domain: 'acme.com',
    industry: 'technology' as const,
    sizeBucket: '51-200' as const,
    headcountCurrent: 120,
    headcount12moAgo: 100,
    growthSignal: 'Growing' as const,
    customFields: {},
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: new Date('2026-05-01T00:00:00Z'),
  };

  const baseEnrichment = {
    contactsCount: 12,
    openLeadsCount: 3,
    wonDealsCount: 1,
    lastActivity: null,
  };

  it('returns counts as numbers, never undefined', () => {
    const view = presenter.toView(baseCompany, baseEnrichment);
    expect(view.counts.contacts).toBe(12);
    expect(view.counts.open_leads).toBe(3);
    expect(view.counts.won_deals).toBe(1);
  });

  it('builds growth_signal as discriminated union with label', () => {
    const view = presenter.toView(baseCompany, baseEnrichment);
    expect(view.headcount.growth_signal.kind).toBe('Growing');
    expect(view.headcount.growth_signal.label).toMatch(/\+\d+\.\d+% YoY/);
  });

  it('handles missing 12-month-ago headcount without throwing', () => {
    const view = presenter.toView(
      { ...baseCompany, headcount12moAgo: null },
      baseEnrichment,
    );
    expect(view.headcount.growth_signal.kind).toBe('Stable');
  });

  it('returns last_activity.kind = "none" when no activity', () => {
    const view = presenter.toView(baseCompany, baseEnrichment);
    expect(view.last_activity).toEqual({ kind: 'None' });
  });

  it('builds last_activity for email_sent with label', () => {
    const view = presenter.toView(baseCompany, {
      ...baseEnrichment,
      lastActivity: {
        kind: 'Email Sent',
        occurredAt: new Date(Date.now() - 1000 * 60 * 30),
        subject: 'Quick question',
      },
    });
    expect(view.last_activity.kind).toBe('Email Sent');
    if (view.last_activity.kind === 'Email Sent') {
      expect(view.last_activity.label).toContain('Quick question');
      expect(view.last_activity.label).toContain('m ago');
    }
  });

  it('serializes dates as ISO strings', () => {
    const view = presenter.toView(baseCompany, baseEnrichment);
    expect(view.created_at).toBe('2026-01-01T00:00:00.000Z');
    expect(view.updated_at).toBe('2026-05-01T00:00:00.000Z');
  });

  it('view contains no undefined values', () => {
    const view = presenter.toView(baseCompany, baseEnrichment);
    expect(JSON.stringify(view)).not.toContain('undefined');
    // Verify against contract schema
    expect(() => companyViewSchema.parse(view)).not.toThrow();
  });
});
```

That last test is the most important — `companyViewSchema.parse(view)` from `@<scope>/contracts/companies` must not throw. That's the proof the presenter satisfies the contract.

## Module wiring

```ts
// apps/api/src/modules/companies/companies.module.ts
import { Module } from '@nestjs/common';
import { CompaniesController } from './companies.controller';
import { CompaniesService } from './companies.service';
import { CompaniesPresenter } from './companies.presenter';
import { CompaniesRepository } from './companies.repository';

@Module({
  controllers: [CompaniesController],
  providers: [CompaniesService, CompaniesRepository, CompaniesPresenter],
  exports: [CompaniesService, CompaniesPresenter],
})
export class CompaniesModule {}
```

The presenter is `@Injectable()` so Nest's DI works. It's also pure — no DB calls, no state — so you can `new CompaniesPresenter()` directly in tests.

## When presenters need cross-module data

A campaign view might include `mailbox: MailboxSummary` (data owned by the mailboxes module). Two options:

1. **Service-level composition** — the campaigns service injects `MailboxesPresenter` (or `MailboxesService.getSummary()`) and passes the result into its own presenter as part of enrichment.
2. **Repository joins** — the repository joins mailboxes into the campaign query and returns the joined row; the campaigns presenter then calls `mailboxesPresenter.toSummary(row.mailbox)`.

Both are fine. Default to (1) for clarity; switch to (2) when N+1 queries become a bottleneck.

## Anti-patterns

- ❌ Returning raw Drizzle rows. The whole skill is about not doing this.
- ❌ Spreading the row into the view (`return { ...row, ... }`). Field-by-field is intentional — it surfaces missed transformations.
- ❌ Building view labels in the controller. Controllers don't transform data; presenters do.
- ❌ Skipping the schema-parse test. That's how you catch contract drift.
- ❌ Letting the frontend compute things the backend can compute. If both sides need to know "growing vs declining", the backend computes once; the frontend renders the label.
