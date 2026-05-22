# Rewiring Patterns (Phase 5)

The most common transformations `frontend-rewirer` applies. Each pattern shows the before (vibe-coded prototype) and the after (production-shape).

## The cardinal rule

**Change data flow, not visual structure.** The JSX, the Tailwind classes, the shadcn primitive choices — leave them alone. Only the code that fetches, owns, or mutates data changes.

Before any pattern, the contract for the feature exists in `@<scope>/contracts/<feature>` and the dual-mode adapter routes `apiRequest` calls to either the real API or the mock route.

---

## Pattern 1: Replace fixture import with TanStack Query

### Before — page imports JSON directly

```tsx
// apps/web/src/app/companies/page.tsx
import companiesData from '@/data/companies.json';
import { CompaniesList } from '@/modules/companies/components/list';

export default function CompaniesPage() {
  return <CompaniesList companies={companiesData} />;
}
```

```tsx
// apps/web/src/modules/companies/components/list.tsx
'use client';

import { useState, useMemo } from 'react';
import type { Company } from '@/types/company';
// ... shadcn imports

export function CompaniesList({ companies: initial }: { companies: Company[] }) {
  const [companies, setCompanies] = useState(initial);
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'industry'>('name');
  const [page, setPage] = useState(0);

  const visible = useMemo(() => {
    const filtered = companies.filter(c =>
      c.name.toLowerCase().includes(filter.toLowerCase()),
    );
    const sorted = [...filtered].sort((a, b) => a[sortBy].localeCompare(b[sortBy]));
    return sorted.slice(page * 20, page * 20 + 20);
  }, [companies, filter, sortBy, page]);

  return (
    <div>
      <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search..." />
      <Table>...</Table>
    </div>
  );
}
```

### After — TanStack Query + server-side filter/sort/paginate

```tsx
// apps/web/src/modules/companies/api.ts
import { apiRequest } from '@/lib/api-client';
import { companyListResponseSchema, type CompanyFilters } from '@<scope>/contracts/companies';

export function getCompanies(filters: CompanyFilters) {
  const qs = new URLSearchParams();
  if (filters.q) qs.set('q', filters.q);
  if (filters.industry) qs.set('industry', filters.industry);
  if (filters.sort) qs.set('sort', filters.sort);
  qs.set('page', String(filters.page ?? 1));
  qs.set('per_page', String(filters.per_page ?? 20));
  return apiRequest(`/companies?${qs.toString()}`, companyListResponseSchema);
}
```

```tsx
// apps/web/src/modules/companies/query-keys.ts
import type { CompanyFilters } from '@<scope>/contracts/companies';

export const companyKeys = {
  all: ['companies'] as const,
  lists: () => [...companyKeys.all, 'list'] as const,
  list: (filters: CompanyFilters) => [...companyKeys.lists(), filters] as const,
  details: () => [...companyKeys.all, 'detail'] as const,
  detail: (id: string) => [...companyKeys.details(), id] as const,
};
```

```tsx
// apps/web/src/modules/companies/hooks/use-companies.ts
import { useQuery } from '@tanstack/react-query';
import { getCompanies } from '../api';
import { companyKeys } from '../query-keys';
import type { CompanyFilters } from '@<scope>/contracts/companies';

export function useCompanies(filters: CompanyFilters) {
  return useQuery({
    queryKey: companyKeys.list(filters),
    queryFn: () => getCompanies(filters),
  });
}
```

```tsx
// apps/web/src/app/companies/page.tsx
import { CompaniesList } from '@/modules/companies/components/list';

// Now a server component — no data dependency at this level
export default function CompaniesPage() {
  return <CompaniesList />;
}
```

```tsx
// apps/web/src/modules/companies/components/list.tsx
'use client';

import { useState } from 'react';
import { useCompanies } from '../hooks/use-companies';
// ... shadcn imports

export function CompaniesList() {
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'industry'>('name');
  const [page, setPage] = useState(1);

  const { data, isLoading } = useCompanies({
    q: filter,
    sort: sortBy,
    page,
    per_page: 20,
  });

  return (
    <div>
      <Input
        value={filter}
        onChange={(e) => { setFilter(e.target.value); setPage(1); }}
        placeholder="Search..."
      />
      {isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <>
          <Table>{/* render data.items */}</Table>
          <Pagination /* uses data.total, data.per_page */ />
        </>
      )}
    </div>
  );
}
```

**What changed:**
- Fixture import gone. Data comes from `useCompanies(filters)`.
- Local list cache (`useState`) gone. TanStack Query owns it.
- Filter/sort/paginate moved from `useMemo` into query params.
- Page is now a server component (no `'use client'`, no data dependency).
- Loading state from `isLoading` instead of fixture-instant-render.

**What didn't change:**
- `<Input>` for filter — same shadcn primitive, same prop shape (the local `useState` for `filter` is KEEP_AS_IS — it's UI state)
- `<Table>` — same shadcn primitive
- The page layout and component composition

---

## Pattern 2: Replace setState mutation with useMutation

### Before — append to in-memory array

```tsx
// apps/web/src/modules/companies/components/add-button.tsx
'use client';

import { useState } from 'react';
import { v4 as uuid } from 'uuid';
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { CompanyForm } from './form';

export function AddCompanyButton({
  onAdd,
}: {
  onAdd: (c: Company) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Add Company</Button>
      </DialogTrigger>
      <DialogContent>
        <CompanyForm
          onSubmit={(input) => {
            onAdd({
              ...input,
              id: uuid(),
              createdAt: new Date().toISOString(),
            });
            setOpen(false);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
```

### After — mutation hook + invalidation

```tsx
// apps/web/src/modules/companies/hooks/use-companies-mutations.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { companyViewSchema, type CreateCompanyInput } from '@<scope>/contracts/companies';
import { companyKeys } from '../query-keys';

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateCompanyInput) =>
      apiRequest('/companies', companyViewSchema, {
        method: 'POST',
        body: input,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: companyKeys.lists() });
    },
  });
}
```

```tsx
// apps/web/src/modules/companies/components/add-button.tsx
'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { CompanyForm } from './form';
import { useCreateCompany } from '../hooks/use-companies-mutations';

export function AddCompanyButton() {
  const [open, setOpen] = useState(false);
  const { mutate, isPending } = useCreateCompany();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Add Company</Button>
      </DialogTrigger>
      <DialogContent>
        <CompanyForm
          submitting={isPending}
          onSubmit={(input) => {
            mutate(input, {
              onSuccess: () => {
                toast.success('Company created');
                setOpen(false);
              },
              onError: (err) => {
                toast.error(err.message);
              },
            });
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
```

**What changed:**
- `onAdd` prop gone. Component owns the mutation internally.
- `uuid()` gone. Backend issues the ID.
- `createdAt` gone from FE. Backend sets it.
- Loading state from `isPending` for the submit button.
- Error toast via `sonner` (shadcn's toast).
- Cache invalidation triggers the list to refetch automatically.

**What didn't change:**
- The `<Dialog>` + `<DialogTrigger>` + `<DialogContent>` structure
- The `<CompanyForm>` component (its `onSubmit` signature is the same — it always took an `input` and called back)
- The `<Button>` label, variant, etc.

---

## Pattern 3: Replace mock auth context with real auth hook

### Before — hardcoded user

```tsx
// apps/web/src/lib/auth-context.tsx
'use client';

import { createContext, useContext } from 'react';

const FAKE_USER = {
  id: 'demo-user-1',
  name: 'Demo User',
  email: 'demo@example.com',
  role: 'admin',
};

const AuthContext = createContext(FAKE_USER);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return <AuthContext.Provider value={FAKE_USER}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
```

### After — JWT-backed hook with the same signature

```tsx
// apps/web/src/modules/auth/hooks/use-auth.ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { userMeSchema } from '@<scope>/contracts/auth';

export function useAuth() {
  const { data } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => apiRequest('/auth/me', userMeSchema),
    staleTime: 5 * 60_000,
  });
  // Hook signature stays the same so the 23 callers don't all need editing.
  // Returns null while loading or if unauthenticated.
  return data ?? null;
}
```

```tsx
// apps/web/src/modules/auth/components/auth-provider.tsx
'use client';

// No longer a context provider — the hook IS the contract.
// This component just handles redirect on 401 from API responses.
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../hooks/use-auth';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const user = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (user === null) {
      // The query loaded and returned null (401) — redirect to login
      router.push('/login');
    }
  }, [user, router]);
  if (user === null) return null;
  return <>{children}</>;
}
```

```tsx
// app/(authed)/layout.tsx — wrap with the guard
import { AuthGuard } from '@/modules/auth/components/auth-provider';
// ...
export default function AuthedLayout({ children }) {
  return <AuthGuard><AppShell>{children}</AppShell></AuthGuard>;
}
```

**Existing callers of `useAuth()` need no edits** because the hook returns the same shape (`{ id, name, email, role }`) — that's why the schema-reverse-engineer included a `userMeSchema` matching the fake user's fields. The fake context provider is deleted.

The login form in M-1 is wired separately: a `useLogin()` mutation hook calls `POST /auth/login`, sets the refresh cookie (httpOnly, sameSite, secure per the backend), and `useAuth()` picks up the now-valid session on next refetch.

---

## Pattern 4: Drag-and-drop with optimistic updates

### Before — local reorder

```tsx
// apps/web/src/modules/pipeline/components/kanban.tsx
'use client';

import { DndContext, type DragEndEvent } from '@dnd-kit/core';
import leadsData from '@/data/leads.json';
import { useState } from 'react';

export function KanbanBoard() {
  const [leads, setLeads] = useState(leadsData);

  const handleDragEnd = (e: DragEndEvent) => {
    if (!e.over) return;
    setLeads((prev) =>
      prev.map((lead) =>
        lead.id === e.active.id
          ? { ...lead, stage: e.over.id as string }
          : lead,
      ),
    );
  };

  return (
    <DndContext onDragEnd={handleDragEnd}>
      {/* columns + lead cards */}
    </DndContext>
  );
}
```

### After — optimistic mutation

```tsx
// apps/web/src/modules/pipeline/hooks/use-leads.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { leadListResponseSchema, leadViewSchema, type LeadStage } from '@<scope>/contracts/pipeline';

const leadKeys = { all: ['leads'] as const };

export function useLeads() {
  return useQuery({
    queryKey: leadKeys.all,
    queryFn: () => apiRequest('/leads?per_page=500', leadListResponseSchema),
  });
}

export function useUpdateLeadStage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, stage }: { id: string; stage: LeadStage }) =>
      apiRequest(`/leads/${id}`, leadViewSchema, {
        method: 'PATCH',
        body: { stage },
      }),
    onMutate: async ({ id, stage }) => {
      // Cancel in-flight refetch so it doesn't overwrite our optimistic update
      await qc.cancelQueries({ queryKey: leadKeys.all });
      const previous = qc.getQueryData(leadKeys.all);
      // Optimistically update
      qc.setQueryData(leadKeys.all, (old: any) => ({
        ...old,
        items: old.items.map((l: any) =>
          l.id === id ? { ...l, stage } : l,
        ),
      }));
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      // Roll back on error
      if (ctx?.previous) qc.setQueryData(leadKeys.all, ctx.previous);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: leadKeys.all });
    },
  });
}
```

```tsx
// apps/web/src/modules/pipeline/components/kanban.tsx
'use client';

import { DndContext, type DragEndEvent } from '@dnd-kit/core';
import { useLeads, useUpdateLeadStage } from '../hooks/use-leads';
import type { LeadStage } from '@<scope>/contracts/pipeline';

const STAGES: LeadStage[] = ['New', 'Qualified', 'Proposal Sent', 'Negotiation', 'Won', 'Lost'];

export function KanbanBoard() {
  const { data } = useLeads();
  const { mutate: updateStage } = useUpdateLeadStage();

  const handleDragEnd = (e: DragEndEvent) => {
    if (!e.over) return;
    const newStage = e.over.id as LeadStage;
    updateStage({ id: e.active.id as string, stage: newStage });
  };

  return (
    <DndContext onDragEnd={handleDragEnd}>
      {STAGES.map((stage) => (
        <Column
          key={stage}
          stage={stage}
          leads={data?.items.filter((l) => l.stage === stage) ?? []}
        />
      ))}
    </DndContext>
  );
}
```

**What changed:**
- Fixture import gone.
- `setLeads` gone. Mutation handles the server write.
- Optimistic update via `onMutate` makes the drop feel instant (UI updates before the network call).
- Rollback via `onError` reverts the card on failure.
- Title Case stages used directly (`'New' | 'Qualified' | 'Proposal Sent'` from the contract).

**What didn't change:**
- `@dnd-kit/core` setup
- Column rendering, drag handles, drop zones
- Visual feedback during drag

---

## Pattern 5: Move client-side computation to view shape

### Before — math in JSX

```tsx
// apps/web/src/modules/companies/components/detail-card.tsx
export function CompanyDetailCard({ company }: { company: Company }) {
  const growthPct = ((company.headcount - company.headcount_12mo_ago) /
                     company.headcount_12mo_ago) * 100;
  const signal = growthPct > 10 ? 'growing' : growthPct < -10 ? 'declining' : 'stable';
  const label = `${growthPct > 0 ? '+' : ''}${growthPct.toFixed(1)}% YoY`;

  return (
    <Card>
      <CardContent>
        <div>{company.headcount}</div>
        <Badge variant={signal === 'growing' ? 'default' : 'secondary'}>
          {label}
        </Badge>
      </CardContent>
    </Card>
  );
}
```

### After — render the contract directly

```tsx
// apps/web/src/modules/companies/components/detail-card.tsx
import type { CompanyView } from '@<scope>/contracts/companies';

export function CompanyDetailCard({ company }: { company: CompanyView }) {
  return (
    <Card>
      <CardContent>
        <div>{company.headcount.current}</div>
        <Badge variant={company.headcount.growth_signal.kind === 'Growing' ? 'default' : 'secondary'}>
          {company.headcount.growth_signal.label}
        </Badge>
      </CardContent>
    </Card>
  );
}
```

**What changed:**
- Computation moved to the backend's `CompaniesPresenter.buildHeadcount()`.
- `signal` discriminator is Title Case (`'Growing' | 'Stable' | 'Declining'`).
- `label` is pre-formatted server-side; FE just renders the string.
- No `?.`, no `??`, no math in JSX.

**What didn't change:**
- `<Card>`, `<CardContent>`, `<Badge>` — same shadcn primitives.
- Visual structure.

---

## Pattern 6: Hand-rolled sidebar → shadcn block

If migration-planner scheduled shadcn sidebar migration for the workspaces module:

### Before — custom aside

```tsx
// app/(authed)/layout.tsx
export default function AuthedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      <aside className="w-64 border-r flex flex-col">
        <div className="p-4 font-semibold"><APP_NAME></div>
        <nav className="flex-1 overflow-y-auto p-2">
          <Link href="/companies" className="block px-3 py-2 hover:bg-muted">Companies</Link>
          <Link href="/contacts" className="block px-3 py-2 hover:bg-muted">Contacts</Link>
          {/* ... */}
        </nav>
        <div className="border-t p-4">
          <Link href="/settings">Settings</Link>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
```

### After — shadcn sidebar block

```tsx
// app/(authed)/layout.tsx
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/modules/workspace/components/app-sidebar';

export default function AuthedLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-12 items-center gap-2 border-b px-3">
          <SidebarTrigger />
        </header>
        <main className="flex-1 p-4">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
```

```tsx
// apps/web/src/modules/workspace/components/app-sidebar.tsx
// (Full example in design-to-nextjs/references/component-patterns.md Pattern 8)
```

**What changed:**
- Custom `<aside>` replaced with `<Sidebar>` block — proper a11y, collapsible, mobile-friendly out of the box.
- Nav items now `<SidebarMenuItem>` + `<SidebarMenuButton asChild>` for active-state styling.

**What didn't change:**
- The nav items themselves (Companies, Contacts, etc.)
- The routes
- The semantic of "sidebar with main content"

---

## Anti-patterns during rewiring

- ❌ Rewriting JSX while rewiring data flow — produces unreviewable diffs
- ❌ Introducing new visual components mid-rewire — schedule as separate work
- ❌ Adding `?.` / `??` to defend against the FE's old fixture-shape assumptions — those gaps are now filled by the contract. If you find yourself adding `?.`, the contract is wrong.
- ❌ Keeping fixture imports as a "fallback" — the dual-mode adapter handles demo/prod cleanly; don't shadow it.
- ❌ Bypassing the contract — every API call goes through `apiRequest(url, schema, options)` with a Zod schema from `@<scope>/contracts`.
- ❌ Moving the kanban drag-and-drop logic before optimistic update is wired — the UX regression is immediate and obvious.
