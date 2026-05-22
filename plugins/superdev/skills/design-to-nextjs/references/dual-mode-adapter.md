# Dual-Mode Adapter — Demo (JSON) and Production (Nest.js)

The app supports two modes, switched by a single environment variable. The production code path is unchanged between them — only the base URL differs. This makes demos trivial, parallel frontend/backend development possible, and end-to-end tests deterministic.

## The contract

A single environment variable controls everything:

```bash
NEXT_PUBLIC_API_MODE=demo        # Demo: every call reads from local JSON fixtures
NEXT_PUBLIC_API_MODE=production  # Production: every call hits the Nest.js backend
```

In demo mode, requests go to a Next.js Route Handler at `/api/mock/*` that reads JSON fixtures from `src/mocks/`.

In production mode, requests go to `NEXT_PUBLIC_API_BASE_URL` (the Nest.js backend).

Everything between the React component and the actual `fetch` call is identical in both modes — same hooks, same Zod schemas, same error handling, same loading states.

## The JSON-to-backend contract

**Critical rule:** The JSON fixtures MUST be a byte-perfect mirror of what the Nest.js backend returns. Same field names, same types, same casing, same date format (ISO 8601), same pagination shape, same error envelope.

The Zod schemas in `modules/<name>/schemas.ts` are the single source of truth. Both sides — the JSON fixtures and the Nest.js DTOs — conform to them. To enforce this, run schema validation on fixtures in CI (see "Fixture validation" below).

## Folder layout

```
src/
├── lib/
│   ├── api-client.ts              ← reads NEXT_PUBLIC_API_MODE, sets BASE_URL accordingly
│   └── env.ts                     ← Zod-validates env vars at boot
├── mocks/                         ← JSON fixtures, organized by module
│   ├── companies/
│   │   ├── list.json              ← GET /companies
│   │   ├── detail.json            ← GET /companies/:id (template; :id substituted at lookup)
│   │   ├── create.json            ← POST /companies (canned success response)
│   │   ├── update.json            ← PATCH /companies/:id
│   │   └── delete.json            ← DELETE /companies/:id (usually 204; just an empty object)
│   ├── contacts/
│   ├── campaigns/
│   └── ...
└── app/
    └── api/
        └── mock/
            └── [...path]/
                └── route.ts       ← serves the JSON files
```

## Implementation — three files

### File 1 — `src/lib/env.ts`

```ts
import { z } from 'zod';

const envSchema = z.object({
  NEXT_PUBLIC_API_MODE: z.enum(['demo', 'production']).default('demo'),
  NEXT_PUBLIC_API_BASE_URL: z.string().url().optional(),
  NEXT_PUBLIC_APP_URL: z.string().url().default('http://localhost:3000'),
});

const parsed = envSchema.safeParse({
  NEXT_PUBLIC_API_MODE: process.env.NEXT_PUBLIC_API_MODE,
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
});

if (!parsed.success) {
  console.error('Invalid env:', parsed.error.flatten().fieldErrors);
  throw new Error('Environment validation failed');
}

export const env = parsed.data;

// Single source of truth: derive base URL from mode
export const API_BASE = env.NEXT_PUBLIC_API_MODE === 'demo'
  ? '/api/mock'
  : (env.NEXT_PUBLIC_API_BASE_URL ?? (() => { throw new Error('NEXT_PUBLIC_API_BASE_URL is required in production mode'); })());

export const IS_DEMO = env.NEXT_PUBLIC_API_MODE === 'demo';
```

### File 2 — `src/lib/api-client.ts` (mode-agnostic — reads `API_BASE`)

```ts
import { z } from 'zod';
import { API_BASE } from './env';

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
    this.name = 'ApiError';
  }
}

type RequestOptions<TSchema extends z.ZodTypeAny> = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  schema: TSchema;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  searchParams?: Record<string, string | number | boolean | undefined>;
};

export async function apiRequest<TSchema extends z.ZodTypeAny>(
  path: string,
  options: RequestOptions<TSchema>,
): Promise<z.infer<TSchema>> {
  const { method = 'GET', body, schema, signal, headers = {}, searchParams } = options;

  let url = `${API_BASE}${path}`;
  if (searchParams) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(searchParams)) {
      if (v !== undefined) sp.set(k, String(v));
    }
    const qs = sp.toString();
    if (qs) url += (url.includes('?') ? '&' : '?') + qs;
  }

  const response = await fetch(url, {
    method,
    signal,
    headers: { 'Content-Type': 'application/json', ...headers },
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'include',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorBody.code ?? 'UNKNOWN',
      errorBody.message ?? response.statusText,
      errorBody.details,
    );
  }

  if (response.status === 204) return schema.parse(undefined);

  const data = await response.json();
  const parsed = schema.safeParse(data);

  if (!parsed.success) {
    console.error('API response failed schema validation', parsed.error);
    throw new ApiError(500, 'SCHEMA_MISMATCH', 'Response did not match schema', parsed.error);
  }

  return parsed.data;
}
```

### File 3 — `src/app/api/mock/[...path]/route.ts`

The Route Handler that serves fixtures in demo mode.

```ts
import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

// Optional: simulate network latency to surface loading-state bugs in development
const SIMULATE_LATENCY_MS = Number(process.env.MOCK_LATENCY_MS ?? '200');

async function loadFixture(filePath: string): Promise<unknown | null> {
  try {
    const raw = await readFile(filePath, 'utf8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function delay(ms: number) {
  if (ms > 0) await new Promise((r) => setTimeout(r, ms));
}

function notFound(method: string, path: string) {
  return NextResponse.json(
    { code: 'MOCK_NOT_FOUND', message: `No mock for ${method} /${path}` },
    { status: 404 },
  );
}

async function handle(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  await delay(SIMULATE_LATENCY_MS);

  const method = req.method;
  const segments = path; // e.g. ['companies'] or ['companies', '123']

  // Build candidate fixture file paths in priority order
  const mocksRoot = join(process.cwd(), 'src', 'mocks');
  const candidates: string[] = [];

  if (method === 'GET') {
    if (segments.length === 1) {
      // GET /companies → companies/list.json
      candidates.push(join(mocksRoot, segments[0], 'list.json'));
    } else if (segments.length >= 2) {
      // GET /companies/123 → look for companies/detail-123.json then companies/detail.json
      const [resource, id, ...rest] = segments;
      if (rest.length === 0) {
        candidates.push(join(mocksRoot, resource, `detail-${id}.json`));
        candidates.push(join(mocksRoot, resource, 'detail.json'));
      } else {
        // GET /companies/123/contacts → companies/123-contacts.json then companies/contacts.json
        candidates.push(join(mocksRoot, resource, `${id}-${rest.join('-')}.json`));
        candidates.push(join(mocksRoot, resource, `${rest.join('-')}.json`));
      }
    }
  } else if (method === 'POST') {
    // POST /companies → companies/create.json (canned success), merging the body's fields
    const body = await req.json().catch(() => ({}));
    const fixturePath = join(mocksRoot, segments[0], 'create.json');
    const fixture = await loadFixture(fixturePath);
    if (!fixture) return notFound(method, path.join('/'));

    // Merge: take the fixture's response shape, override fields with the submitted body
    const merged = { ...(fixture as Record<string, unknown>), ...body, id: `mock_${Date.now()}` };
    return NextResponse.json(merged);
  } else if (method === 'PATCH' || method === 'PUT') {
    const [resource, id] = segments;
    const body = await req.json().catch(() => ({}));
    const fixturePath = join(mocksRoot, resource, `detail-${id}.json`);
    const fallbackPath = join(mocksRoot, resource, 'detail.json');
    const fixture = (await loadFixture(fixturePath)) ?? (await loadFixture(fallbackPath));
    if (!fixture) return notFound(method, path.join('/'));

    return NextResponse.json({ ...(fixture as Record<string, unknown>), ...body, id });
  } else if (method === 'DELETE') {
    return new NextResponse(null, { status: 204 });
  }

  // For GET: try each candidate
  for (const candidate of candidates) {
    const fixture = await loadFixture(candidate);
    if (fixture) return NextResponse.json(fixture);
  }

  return notFound(method, path.join('/'));
}

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const PUT = handle;
export const DELETE = handle;
```

## Authoring fixtures

A fixture is a JSON file that matches the Zod schema for the endpoint exactly. Use realistic data — not "Lorem ipsum" — because the demo is shown to stakeholders.

### Example — `src/mocks/companies/list.json`

The Zod schema (from `modules/companies/schemas.ts`):

```ts
export const companyListSchema = z.object({
  data: z.array(companySchema),
  total: z.number(),
  page: z.number(),
  per_page: z.number(),
});
```

The fixture mirrors it exactly:

```json
{
  "data": [
    {
      "id": "cmp_01HXYZ",
      "name": "Acme Logistics",
      "domain": "acmelogistics.com",
      "industry": "Logistics",
      "size_bucket": "51-200",
      "headcount_current": 142,
      "headcount_12mo_ago": 98,
      "growth_signal": "Growing",
      "created_at": "2026-02-14T09:23:11.000Z",
      "updated_at": "2026-04-30T15:10:02.000Z"
    },
    {
      "id": "cmp_01HXYA",
      "name": "Beacon Health Systems",
      "domain": "beaconhealth.io",
      "industry": "Healthcare",
      "size_bucket": "201-1000",
      "headcount_current": 487,
      "headcount_12mo_ago": 502,
      "growth_signal": "Declining",
      "created_at": "2026-01-09T14:00:00.000Z",
      "updated_at": "2026-05-01T11:32:18.000Z"
    }
  ],
  "total": 247,
  "page": 1,
  "per_page": 20
}
```

### Example — `src/mocks/companies/detail.json`

```json
{
  "id": "cmp_01HXYZ",
  "name": "Acme Logistics",
  "domain": "acmelogistics.com",
  "industry": "Logistics",
  "size_bucket": "51-200",
  "headcount_current": 142,
  "headcount_12mo_ago": 98,
  "growth_signal": "Growing",
  "created_at": "2026-02-14T09:23:11.000Z",
  "updated_at": "2026-04-30T15:10:02.000Z"
}
```

### Example — `src/mocks/companies/create.json`

A canned success response. Field names match what the backend would return on POST. The Route Handler overrides `id` and merges the request body, so you only need to supply the "extra" fields the backend would generate (timestamps, defaults).

```json
{
  "id": "REPLACED_BY_HANDLER",
  "name": "REPLACED_BY_BODY",
  "domain": null,
  "industry": "Technology",
  "size_bucket": "1-10",
  "headcount_current": 0,
  "headcount_12mo_ago": null,
  "growth_signal": "Stable",
  "created_at": "2026-05-17T12:00:00.000Z",
  "updated_at": "2026-05-17T12:00:00.000Z"
}
```

## Fixture validation in CI

Schema drift between fixtures and the Zod contract is the failure mode this whole pattern exists to prevent. Catch it with a script.

### `scripts/validate-fixtures.ts`

```ts
import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { companyListSchema, companySchema } from '../src/modules/companies/schemas';
import { contactListSchema, contactSchema } from '../src/modules/contacts/schemas';
// ... import all module schemas

type FixtureMap = Record<string, { schema: any; files: string[] }>;

const map: FixtureMap = {
  companies: {
    schema: companySchema,
    files: ['detail.json', 'create.json'],
  },
  'companies-list': {
    schema: companyListSchema,
    files: ['list.json'],
  },
  // ... extend for each module
};

let hasError = false;

for (const [key, { schema, files }] of Object.entries(map)) {
  const [resource] = key.split('-');
  for (const file of files) {
    const path = join('src/mocks', resource, file);
    const raw = await readFile(path, 'utf8');
    const data = JSON.parse(raw);
    const result = schema.safeParse(data);
    if (!result.success) {
      console.error(`❌ ${path}`);
      console.error(result.error.flatten());
      hasError = true;
    } else {
      console.log(`✅ ${path}`);
    }
  }
}

process.exit(hasError ? 1 : 0);
```

Wire it into `package.json`:

```json
{
  "scripts": {
    "validate:fixtures": "tsx scripts/validate-fixtures.ts"
  }
}
```

Run on every CI build. If a Zod schema changes and a fixture isn't updated to match, CI fails before the demo breaks.

## Switching modes

Local dev (default):

```bash
# .env.local
NEXT_PUBLIC_API_MODE=demo
```

Running against a local Nest.js backend:

```bash
# .env.local
NEXT_PUBLIC_API_MODE=production
NEXT_PUBLIC_API_BASE_URL=http://localhost:3001/v1
```

Production deployment:

```bash
NEXT_PUBLIC_API_MODE=production
NEXT_PUBLIC_API_BASE_URL=https://api.example.com/v1
```

## Optional enhancements

These are not v1 requirements but are worth knowing.

### Latency tuning per endpoint

If certain endpoints should feel slower (a long AI generation, an import), key them in the Route Handler:

```ts
const ENDPOINT_LATENCY: Record<string, number> = {
  'ai/generate': 2500,
  'imports': 5000,
};
```

### Error scenarios

To demo error states, the Route Handler can read a header or query param:

```bash
GET /api/mock/companies?_mock_status=500
```

```ts
const forcedStatus = req.nextUrl.searchParams.get('_mock_status');
if (forcedStatus) {
  return NextResponse.json({ code: 'FORCED', message: 'Mock error' }, { status: Number(forcedStatus) });
}
```

### Mutation persistence

The Route Handler resets on hot reload. For persistent demo state (create a company → see it in the list afterwards), layer client-side state via TanStack Query's `setQueryData` after mutations succeed. This already happens in the standard mutation pattern (see `tanstack-patterns.md`) — no special demo-mode code needed.

### Per-tenant fixtures

If your demo needs multiple workspaces with different data, name fixtures by tenant:

```
src/mocks/
└── companies/
    ├── ws_demo1-list.json
    ├── ws_demo2-list.json
    └── ...
```

Pass the workspace ID as a request header; have the Route Handler resolve it before file lookup.

## Anti-patterns

- ❌ Hand-editing fixtures to match a backend change. Add fixture validation to CI instead.
- ❌ Switching modes per-request. Mode is a build-time/runtime constant; do not make it dynamic.
- ❌ Putting business logic in the mock Route Handler. It's a glorified file reader — keep it dumb.
- ❌ Fixtures with placeholder strings like "TODO" or "Lorem". Use realistic data — the demo is a sales tool.
- ❌ Two sources of truth for response shape. The Zod schema is the contract; fixtures and the Nest.js DTOs both serve it.
