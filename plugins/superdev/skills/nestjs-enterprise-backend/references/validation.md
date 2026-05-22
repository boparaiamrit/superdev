# Validation with nestjs-zod

How to wire Zod schemas (shared with the frontend) into Nest.js request validation and OpenAPI documentation. Read in Phase 5 when generating DTOs.

## Why nestjs-zod and not class-validator

Nest.js historically uses `class-validator` + `class-transformer`. That works, but it forces the contract to live in TypeScript decorators that don't easily share with a frontend. With `nestjs-zod`, the same Zod schema:

- Validates the incoming request body / query / params (runtime)
- Generates the TypeScript type (compile-time)
- Generates OpenAPI schema (docs)
- **Is the same file the frontend imports** — single source of truth

The schema lives in `packages/contracts/`, the DTO is one line in the module's `dto/` folder.

## Setup

Already installed in scaffolding: `nestjs-zod` and `zod`.

`main.ts` needs the Zod validation pipe set globally (replaces the default `ValidationPipe`):

```ts
import { ZodValidationPipe } from 'nestjs-zod';

app.useGlobalPipes(new ZodValidationPipe());
```

Also wire the OpenAPI patch so Zod schemas surface in `/docs`:

```ts
import { patchNestJsSwagger } from 'nestjs-zod';

patchNestJsSwagger();
// ... then SwaggerModule.setup(...)
```

## Authoring schemas (in `packages/contracts/src/`)

Schemas live in the monorepo's shared package, **not** in `apps/api/src/contracts/`. Both apps import from `@<scope>/contracts/<feature>`. See `references/monorepo-setup.md` for the package layout.

```ts
// packages/contracts/src/companies.ts
import { z } from 'zod';
import { paginatedResponseSchema } from './pagination';

// All enums are Title Case — the value IS the display label; no FE lookup needed.
export const industrySchema = z.enum(['Technology', 'Healthcare', 'Finance', 'Logistics', 'Other']);
export type Industry = z.infer<typeof industrySchema>;

export const sizeBucketSchema = z.enum(['1-10', '11-50', '51-200', '201-1000', '1000+']);
export type SizeBucket = z.infer<typeof sizeBucketSchema>;

export const growthSignalKindSchema = z.enum(['Growing', 'Stable', 'Declining']);
export type GrowthSignalKind = z.infer<typeof growthSignalKindSchema>;

// VIEW shape — what the API returns and the FE renders 1:1
export const companyViewSchema = z.object({
  id: z.string(),
  name: z.string(),
  domain: z.string().nullable(),
  industry: industrySchema,          // Title Case value, render directly
  size_bucket: sizeBucketSchema,     // Numeric range, render as-is (append unit at view site)
  headcount: z.object({
    current: z.number().int().nonnegative(),
    twelve_months_ago: z.number().int().nonnegative(),
    delta_pct: z.number(),
    growth_signal: z.object({
      kind: growthSignalKindSchema,  // Title Case
      label: z.string(),             // Computed contextual label, e.g. "+12% YoY"
    }),
  }),
  counts: z.object({
    contacts: z.number().int().nonnegative(),
    open_leads: z.number().int().nonnegative(),
    won_deals: z.number().int().nonnegative(),
  }),
  last_activity: z.discriminatedUnion('kind', [
    z.object({ kind: z.literal('None') }),
    z.object({ kind: z.literal('Email Sent'),     at: z.string().datetime(), subject: z.string(), label: z.string() }),
    z.object({ kind: z.literal('Email Received'), at: z.string().datetime(), preview: z.string(), label: z.string() }),
    z.object({ kind: z.literal('Deal Won'),       at: z.string().datetime(), amount_label: z.string(), label: z.string() }),
  ]),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export type CompanyView = z.infer<typeof companyViewSchema>;
export const companyListResponseSchema = paginatedResponseSchema(companyViewSchema);
export type CompanyListResponse = z.infer<typeof companyListResponseSchema>;

// REQUEST shapes — what the API accepts
export const createCompanySchema = z.object({
  name: z.string().min(1).max(120),
  domain: z.string().regex(/^[a-z0-9.-]+\.[a-z]{2,}$/i).nullable(),
  industry: industrySchema,
});

export const updateCompanySchema = createCompanySchema.partial();

export const companyFiltersSchema = z.object({
  search: z.string().optional(),
  industry: industrySchema.optional(),
  page: z.coerce.number().int().positive().default(1),
  per_page: z.coerce.number().int().positive().max(100).default(20),
});

export type CreateCompanyInput = z.infer<typeof createCompanySchema>;
export type UpdateCompanyInput = z.infer<typeof updateCompanySchema>;
export type CompanyFilters = z.infer<typeof companyFiltersSchema>;
```

Notice the structure of `companyViewSchema`:
- No `.optional()` on data fields (just on filter inputs)
- Discriminated union for `last_activity` — frontend pattern-matches `kind` instead of checking nulls
- Labels are part of the contract — the presenter builds them server-side, the frontend renders them as-is
- Dates as ISO 8601 strings (never `Date`)

## Generating DTOs (in `apps/api/src/modules/<feature>/dto/`)

DTOs are one-liners that derive from the shared Zod schema:

```ts
// apps/api/src/modules/companies/dto/create-company.dto.ts
import { createZodDto } from 'nestjs-zod';
import { createCompanySchema } from '@<scope>/contracts/companies';

export class CreateCompanyDto extends createZodDto(createCompanySchema) {}
```

```ts
// apps/api/src/modules/companies/dto/update-company.dto.ts
import { createZodDto } from 'nestjs-zod';
import { updateCompanySchema } from '@<scope>/contracts/companies';

export class UpdateCompanyDto extends createZodDto(updateCompanySchema) {}
```

```ts
// apps/api/src/modules/companies/dto/company-filters.dto.ts
import { createZodDto } from 'nestjs-zod';
import { companyFiltersSchema } from '@<scope>/contracts/companies';

export class CompanyFiltersDto extends createZodDto(companyFiltersSchema) {}
```

Re-export from a barrel file:

```ts
// apps/api/src/modules/companies/dto/index.ts
export * from './create-company.dto';
export * from './update-company.dto';
export * from './company-filters.dto';
```

## Using DTOs in controllers

```ts
@Post()
@Roles('ADMIN', 'OPERATOR')
create(@Body() input: CreateCompanyDto, @CurrentWorkspace() workspace) {
  // input is already validated and typed — no manual parsing
  return this.companies.create(workspace.id, input);
}

@Get()
list(@Query() filters: CompanyFiltersDto, @CurrentWorkspace() workspace) {
  return this.companies.list(workspace.id, filters);
}
```

Validation errors are thrown as `ZodValidationException`, which the global exception filter maps to a 400 response with field-level details. No manual try/catch needed.

## Validating responses too (optional but recommended)

For maximum safety, validate outgoing responses too:

```ts
// modules/companies/companies.service.ts
import { companySchema, type Company } from '@<scope>/contracts/companies';

async get(workspaceId: string, id: string): Promise<Company> {
  const row = await this.prisma.company.findFirst({ where: { id, workspaceId } });
  if (!row) throw new NotFoundException();

  // Validate the response matches the contract
  return companySchema.parse(this.toDto(row));
}

private toDto(row: any): unknown {
  return {
    id: row.id,
    workspace_id: row.workspaceId,
    name: row.name,
    domain: row.domain,
    industry: row.industry.toLowerCase(),
    size_bucket: row.sizeBucket.toLowerCase().replace('s_', '').replace('_', '-'),
    headcount_current: row.headcountCurrent,
    headcount_12mo_ago: row.headcount12moAgo,
    growth_signal: row.growthSignal.toLowerCase(),
    created_at: row.createdAt.toISOString(),
    updated_at: row.updatedAt.toISOString(),
  };
}
```

The `toDto` step is where Prisma's internal shape (camelCase, enum casing) gets converted to the contract shape (snake_case, lowercase). This is mechanical but explicit — never let Prisma's internal types leak into responses.

## Snake_case vs camelCase

The contract uses `snake_case` because that's the convention most JS clients (and the frontend's Zod schemas) consume. Prisma uses camelCase internally. The `toDto` mapper is where conversion happens.

Alternative: configure Prisma to use snake_case names via `@map` and `@@map` everywhere. Cleaner but a lot of boilerplate. Stick with the explicit mapper unless the team prefers otherwise.

## Sharing schemas with the frontend

Schemas live in `packages/contracts`. Both `apps/api` and `apps/web` declare `"@<scope>/contracts": "workspace:*"` and import from it. There is no local copy in either app. CI's `pnpm typecheck` will fail if schemas drift, because consumers compile against the same source. See `references/monorepo-setup.md` for the package config.

## OpenAPI annotations

`nestjs-zod` auto-generates the OpenAPI schema from Zod, but you may want to add metadata:

```ts
@Post()
@ApiOperation({ summary: 'Create a company' })
@ApiResponse({ status: 201, description: 'Company created', type: CompanyResponseDto })
@ApiResponse({ status: 409, description: 'Domain already exists in this workspace' })
@Roles('ADMIN', 'OPERATOR')
create(@Body() input: CreateCompanyDto) { /* ... */ }
```

The frontend can generate a typed client from `/docs/json` (openapi-typescript, orval, etc.) if you want extra-typed API access beyond shared Zod.

## Anti-patterns

- ❌ Duplicating schemas between contracts and DTOs. The DTO is a one-line `createZodDto(schema)`.
- ❌ Using `any` in service signatures. Use the inferred types from `z.infer<...>`.
- ❌ Hand-writing OpenAPI schemas. Let `nestjs-zod` + `patchNestJsSwagger()` generate them.
- ❌ Skipping the response mapper. Prisma's internal shape will leak (camelCase, enum casing, internal fields).
- ❌ Letting the frontend define the contract and pushing it to backend. Either it's truly shared (monorepo / sync script), or the backend owns it.
