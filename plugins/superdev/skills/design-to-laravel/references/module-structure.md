# Module Structure — Per-Feature Layout (Inertia React Monolith)

One agent owns one feature end-to-end: its prop types, its controller render methods, its pages, and its components. This document defines the canonical layout and the order in which each piece is authored.

## Directory layout for a feature

```
resources/js/
├── pages/
│   └── <feature>/
│       ├── index.tsx       ← list (GET /feature)
│       ├── create.tsx      ← create form (GET /feature/create)
│       ├── edit.tsx        ← edit form  (GET /feature/:id/edit)
│       └── show.tsx        ← detail view (GET /feature/:id)
├── components/
│   └── <feature>/
│       ├── <feature>-table.tsx
│       ├── <feature>-card.tsx
│       ├── <feature>-form.tsx
│       └── ...
└── types/
    └── <feature>.ts        ← all view types for this feature

app/
└── Domains/
    └── <Feature>/
        └── Http/
            └── <Feature>Controller.php   ← Inertia::render + #[Authorize]
```

The Laravel routes live in `routes/web.php` (the controller writes them there). Backend domain logic — models, actions, Jobs, events, policies — belongs in `app/Domains/<Feature>/` and is the responsibility of the `laravel-module-builder` agent, not this one.

---

## Canonical authoring order

**Types → controller render → page(s) → components → forms**

This order ensures every downstream file has a typed contract to reference. Never write a page or component before its prop types are locked.

---

## Step 1 — Prop types (`resources/js/types/<feature>.ts`)

Write the view-shape types first. Rules (see `typed-props.md` for full detail):

- Every field present and typed; `null` is explicit, never "missing".
- Counts are `number` (default 0 server-side), never optional.
- Enum values are Title-Case string literals — they render directly as labels, no label map needed.
- No `?.` or `??` on any prop field in pages or components. The controller guarantees the shape.

```ts
// resources/js/types/companies.ts
export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'
export type CompanyStatus = 'Active' | 'Inactive' | 'Prospect'

export interface CompanyView {
  id: string
  name: string
  domain: string | null          // explicit null when absent
  industry: Industry             // value IS the label — render directly
  status: CompanyStatus
  counts: {
    contacts: number             // always a number; controller defaults to 0
    open_leads: number
    won_deals: number
  }
  created_at: string             // ISO 8601
}

export interface CompanyEditView extends CompanyView {
  // extra fields needed only for the edit page
}

export interface Paginated<T> {
  data: T[]
  total: number
  page: number
  per_page: number
}
```

---

## Step 2 — Controller render methods (`app/Domains/<Feature>/Http/<Feature>Controller.php`)

Write one `Inertia::render` call per page. Eager-load everything the page needs; compute counts; shape the prop to match the view type exactly. Annotate each action with `#[Authorize]`.

```php
<?php

namespace App\Domains\Companies\Http;

use App\Domains\Companies\Models\Company;
use Illuminate\Http\Request;
use Illuminate\Routing\Attributes\Controllers\Authorize;
use Inertia\Inertia;
use Inertia\Response;

class CompanyController
{
    #[Authorize('viewAny', Company::class)]
    public function index(): Response
    {
        return Inertia::render('companies/index', [
            'companies' => Company::query()
                ->withCount(['contacts', 'open_leads', 'won_deals'])
                ->paginate(20)
                ->through(fn (Company $c) => [
                    'id'         => $c->id,
                    'name'       => $c->name,
                    'domain'     => $c->domain,
                    'industry'   => $c->industry->value,  // Title-Case enum value
                    'status'     => $c->status->value,
                    'counts'     => [
                        'contacts'   => $c->contacts_count   ?? 0,
                        'open_leads' => $c->open_leads_count ?? 0,
                        'won_deals'  => $c->won_deals_count  ?? 0,
                    ],
                    'created_at' => $c->created_at->toIso8601String(),
                ]),
        ]);
    }

    #[Authorize('create', Company::class)]
    public function create(): Response
    {
        return Inertia::render('companies/create', [
            'industries' => \App\Domains\Companies\Enums\Industry::values(),
            'statuses'   => \App\Domains\Companies\Enums\CompanyStatus::values(),
        ]);
    }

    #[Authorize('update', 'company')]
    public function edit(Company $company): Response
    {
        return Inertia::render('companies/edit', [
            'company'    => [
                'id'         => $company->id,
                'name'       => $company->name,
                'domain'     => $company->domain,
                'industry'   => $company->industry->value,
                'status'     => $company->status->value,
                'counts'     => [
                    'contacts'   => $company->contacts()->count(),
                    'open_leads' => $company->openLeads()->count(),
                    'won_deals'  => $company->wonDeals()->count(),
                ],
                'created_at' => $company->created_at->toIso8601String(),
            ],
            'industries' => \App\Domains\Companies\Enums\Industry::values(),
            'statuses'   => \App\Domains\Companies\Enums\CompanyStatus::values(),
        ]);
    }

    #[Authorize('view', 'company')]
    public function show(Company $company): Response
    {
        return Inertia::render('companies/show', [
            'company' => [/* same shape as edit */],
            'contacts' => $company->contacts()->limit(10)->get()->map(/* ... */),
        ]);
    }
}
```

Then register the routes in `routes/web.php`:

```php
// routes/web.php
Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('/companies',              [CompanyController::class, 'index'])->name('companies.index');
    Route::get('/companies/create',       [CompanyController::class, 'create'])->name('companies.create');
    Route::post('/companies',             [CompanyController::class, 'store'])->name('companies.store');
    Route::get('/companies/{company}',    [CompanyController::class, 'show'])->name('companies.show');
    Route::get('/companies/{company}/edit', [CompanyController::class, 'edit'])->name('companies.edit');
    Route::put('/companies/{company}',    [CompanyController::class, 'update'])->name('companies.update');
    Route::delete('/companies/{company}', [CompanyController::class, 'destroy'])->name('companies.destroy');
});
```

---

## Step 3 — Pages (`resources/js/pages/<feature>/`)

Pages are thin: import the prop type, receive typed props, compose components. Keep each page under 100 lines. The starter kit uses `<AppLayout>` (or `<AuthLayout>`) as a wrapper — wrap the return to apply the persistent layout.

### index.tsx — list page

```tsx
// resources/js/pages/companies/index.tsx
import { Link, usePage } from '@inertiajs/react'
import AppLayout from '@/layouts/app-layout'
import { Button } from '@/components/ui/button'
import { CompaniesTable } from '@/components/companies/companies-table'
import type { CompanyView, Paginated } from '@/types/companies'
import type { InertiaPageProps } from '@/types/globals'

interface Props {
  companies: Paginated<CompanyView>
}

export default function CompaniesIndex({ companies }: Props) {
  const { auth } = usePage<InertiaPageProps>().props
  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Companies</h1>
        {auth.permissions.includes('company.create') && (
          <Button asChild>
            <Link href="/companies/create">New company</Link>
          </Button>
        )}
      </div>
      <CompaniesTable companies={companies} />
    </AppLayout>
  )
}
```

### create.tsx — create form page

```tsx
// resources/js/pages/companies/create.tsx
import AppLayout from '@/layouts/app-layout'
import { CompanyForm } from '@/components/companies/company-form'
import type { Industry, CompanyStatus } from '@/types/companies'

interface Props {
  industries: Industry[]
  statuses: CompanyStatus[]
}

export default function CompaniesCreate({ industries, statuses }: Props) {
  return (
    <AppLayout>
      <h1 className="text-2xl font-semibold mb-6">New Company</h1>
      <CompanyForm industries={industries} statuses={statuses} submitUrl="/companies" method="post" />
    </AppLayout>
  )
}
```

### edit.tsx — edit form page

```tsx
// resources/js/pages/companies/edit.tsx
import AppLayout from '@/layouts/app-layout'
import { CompanyForm } from '@/components/companies/company-form'
import type { CompanyEditView, Industry, CompanyStatus } from '@/types/companies'

interface Props {
  company: CompanyEditView
  industries: Industry[]
  statuses: CompanyStatus[]
}

export default function CompaniesEdit({ company, industries, statuses }: Props) {
  return (
    <AppLayout>
      <h1 className="text-2xl font-semibold mb-6">Edit {company.name}</h1>
      <CompanyForm
        initialValues={company}
        industries={industries}
        statuses={statuses}
        submitUrl={`/companies/${company.id}`}
        method="put"
      />
    </AppLayout>
  )
}
```

### show.tsx — detail page

```tsx
// resources/js/pages/companies/show.tsx
import { Link } from '@inertiajs/react'
import AppLayout from '@/layouts/app-layout'
import { Button } from '@/components/ui/button'
import { CompanyDetail } from '@/components/companies/company-detail'
import type { CompanyView } from '@/types/companies'

interface Props {
  company: CompanyView
}

export default function CompaniesShow({ company }: Props) {
  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">{company.name}</h1>
        <Button asChild variant="outline">
          <Link href={`/companies/${company.id}/edit`}>Edit</Link>
        </Button>
      </div>
      <CompanyDetail company={company} />
    </AppLayout>
  )
}
```

---

## Step 4 — Components (`resources/js/components/<feature>/`)

Components receive typed props and render using shadcn primitives only. Keep each component under 200 lines; split into sub-components if larger.

### companies-table.tsx

```tsx
// resources/js/components/companies/companies-table.tsx
import { Link } from '@inertiajs/react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import type { CompanyView, Paginated } from '@/types/companies'

interface Props {
  companies: Paginated<CompanyView>
}

export function CompaniesTable({ companies }: Props) {
  if (companies.data.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No companies found.
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Industry</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Contacts</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {companies.data.map((company) => (
          <TableRow key={company.id}>
            <TableCell className="font-medium">{company.name}</TableCell>
            <TableCell>{company.industry}</TableCell>{/* enum value IS the label */}
            <TableCell>
              <Badge variant={company.status === 'Active' ? 'default' : 'secondary'}>
                {company.status}
              </Badge>
            </TableCell>
            <TableCell className="text-right">{company.counts.contacts}</TableCell>
            <TableCell className="text-right">
              <Button asChild size="sm" variant="ghost">
                <Link href={`/companies/${company.id}`}>View</Link>
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

### company-detail.tsx

```tsx
// resources/js/components/companies/company-detail.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { CompanyView } from '@/types/companies'

interface Props {
  company: CompanyView
}

export function CompanyDetail({ company }: Props) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-muted-foreground">Industry</dt>
            <dd>{company.industry}</dd>
            <dt className="text-muted-foreground">Status</dt>
            <dd>{company.status}</dd>
            <dt className="text-muted-foreground">Domain</dt>
            <dd>{company.domain !== null ? company.domain : '—'}</dd>
          </dl>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold">{company.counts.contacts}</div>
              <div className="text-xs text-muted-foreground">Contacts</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{company.counts.open_leads}</div>
              <div className="text-xs text-muted-foreground">Open Leads</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{company.counts.won_deals}</div>
              <div className="text-xs text-muted-foreground">Won Deals</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## Step 5 — Forms (`resources/js/components/<feature>/<feature>-form.tsx`)

Forms use Inertia `useForm`. Errors arrive in `form.errors` from Laravel validation; no client-side Zod needed for field validation (the server owns validation). Use shadcn `Input`, `Select`, `Label`, and `Button` — never bare `<input>` or `<button>`.

```tsx
// resources/js/components/companies/company-form.tsx
import { useForm } from '@inertiajs/react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import type { CompanyView, Industry, CompanyStatus } from '@/types/companies'

interface Props {
  initialValues?: Pick<CompanyView, 'name' | 'domain' | 'industry' | 'status'>
  industries: Industry[]
  statuses: CompanyStatus[]
  submitUrl: string
  method: 'post' | 'put'
}

export function CompanyForm({ initialValues, industries, statuses, submitUrl, method }: Props) {
  const form = useForm({
    name:     initialValues ? initialValues.name             : '',
    domain:   initialValues ? (initialValues.domain ?? '')   : '',  // normalize null → '' for the input
    industry: initialValues ? initialValues.industry         : industries[0],
    status:   initialValues ? initialValues.status           : statuses[0],
  })

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (method === 'put') {
      form.put(submitUrl)
    } else {
      form.post(submitUrl)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4 max-w-lg">
      <div className="space-y-1">
        <Label htmlFor="name">Company name</Label>
        <Input
          id="name"
          value={form.data.name}
          onChange={(e) => form.setData('name', e.target.value)}
        />
        {form.errors.name && (
          <p className="text-sm text-destructive">{form.errors.name}</p>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="domain">Domain</Label>
        <Input
          id="domain"
          value={form.data.domain}
          onChange={(e) => form.setData('domain', e.target.value)}
          placeholder="acme.com"
        />
        {form.errors.domain && (
          <p className="text-sm text-destructive">{form.errors.domain}</p>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="industry">Industry</Label>
        <Select
          value={form.data.industry}
          onValueChange={(v) => form.setData('industry', v as Industry)}
        >
          <SelectTrigger id="industry">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {industries.map((i) => (
              <SelectItem key={i} value={i}>{i}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {form.errors.industry && (
          <p className="text-sm text-destructive">{form.errors.industry}</p>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="status">Status</Label>
        <Select
          value={form.data.status}
          onValueChange={(v) => form.setData('status', v as CompanyStatus)}
        >
          <SelectTrigger id="status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {statuses.map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {form.errors.status && (
          <p className="text-sm text-destructive">{form.errors.status}</p>
        )}
      </div>

      <Button type="submit" disabled={form.processing}>
        {form.processing ? 'Saving…' : 'Save'}
      </Button>
    </form>
  )
}
```

---

## Feature ownership boundaries

One invocation of `inertia-module-builder` owns exactly one feature's:

- `resources/js/types/<feature>.ts`
- `resources/js/pages/<feature>/{index,create,edit,show}.tsx`
- `resources/js/components/<feature>/*`
- `app/Domains/<Feature>/Http/<Feature>Controller.php` — render methods only
- Route entries for the feature in `routes/web.php`

It does NOT touch:

- Other features' pages, components, or types
- Backend domain logic: models, actions, events, jobs, migrations (`laravel-module-builder` owns those)
- `HandleInertiaRequests` shared props (auth is global — see `auth-fortify-permissions.md`)
- The sidebar nav (`resources/js/components/app-sidebar.tsx`) — the orchestrator adds nav items after all features are built, or coordinates a separate sidebar-update pass

---

## Cross-feature sharing

When a component is used by two or more features, promote it to `resources/js/components/shared/`. Never import from another feature's component folder.

```
resources/js/components/shared/
├── stat-tile.tsx         ← reusable metric card
├── empty-state.tsx       ← generic empty state
├── page-header.tsx       ← title + action slot
└── paginator.tsx         ← Inertia-aware pagination controls
```

---

## Global type stubs (`resources/js/types/globals.ts`)

Shared types that every feature references. Write once during scaffolding; do not duplicate per feature.

```ts
// resources/js/types/globals.ts
export interface AuthUser {
  id: string
  name: string
  email: string
}

export interface InertiaPageProps {
  auth: {
    user: AuthUser | null
    permissions: string[]
  }
  flash: {
    success: string | null
    error: string | null
  }
}
```

---

## Checklist before declaring a feature done

- [ ] `resources/js/types/<feature>.ts` — all view types present; no `?` on fields that the controller always provides
- [ ] Controller — every page method has `#[Authorize]`; every prop matches the type shape; counts default to `0` not `null`
- [ ] Pages — each page under 100 lines; no business logic in the page file; layout applied
- [ ] Components — each under 200 lines; only shadcn primitives; no bare `<button>` / `<input>` / `<select>`
- [ ] Form — uses Inertia `useForm`; errors displayed per field; submit button reflects `form.processing`
- [ ] Routes — named routes registered in `routes/web.php`; Wayfinder regenerated after route changes
- [ ] No `?.` or `??` used on Inertia prop fields in pages or components
- [ ] No Next.js imports (`next/*`, `'use client'`, `@tanstack/react-query`) anywhere in `resources/js/`

---

## Anti-patterns

**Returning untyped / partially-shaped props.**
Every `Inertia::render` call must produce the exact shape declared in `resources/js/types/<feature>.ts`. Missing fields or silent `null`s will surface as runtime errors in the page because there are no `?.` guards to hide them — which is intentional. Fix the controller, not the page.

**Writing `?.` / `??` on prop fields in pages.**
The "no `?.`" discipline is enforced here. `company.counts?.contacts` means the controller might not always return `counts`. Make the controller always return it (defaulting to `0`).

**Fetching data in components instead of via props.**
There is no `useEffect` + `fetch`, no TanStack Query, no `axios.get` inside a component. All server data arrives as Inertia props. If a component needs data that was not passed as a prop, go back to the controller and add it to `Inertia::render`.

**Rolling your own inputs.**
Every `<input>`, `<button>`, `<select>`, and `<textarea>` must be a shadcn primitive (`Input`, `Button`, `Select`, `Textarea`). Bare HTML form elements are not permitted.

**Letting pages grow beyond 100 lines.**
A page file that reaches 100 lines is almost always mixing composition with implementation. Extract the implementation into a component (`resources/js/components/<feature>/`) and keep the page to layout + prop wiring.

**Importing across feature component folders.**
`resources/js/components/companies/companies-table.tsx` must not import from `resources/js/components/contacts/`. Promote shared code to `resources/js/components/shared/`.

**Mixing backend domain logic into the controller render method.**
The controller method shapes props for the view; it does not contain business rules. Business rules live in domain actions or services. Keep render methods to: authorize → query → shape → render.
