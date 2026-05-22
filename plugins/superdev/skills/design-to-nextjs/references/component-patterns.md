# Component Translation Patterns

How to translate Claude Design HTML into proper React components — not by transcribing, but by re-implementing against the target stack's primitives.

## The fundamental rule

Claude Design's HTML is a **visual specification**, not the final markup. The job is to re-implement the design intent using shadcn/ui primitives, module components, and shared composites. If you find yourself copy-pasting `<div class="...">` blocks one-for-one into JSX, stop and refactor.

## Translation checklist for every component

Before generating a component:

1. **Identify the closest existing primitive.** Is this a button? Use `<Button>`. A modal? Use `<Dialog>`. A select? Use `<Select>`. Don't roll your own when shadcn already has it.
2. **Identify the closest shared composite.** Is this a data table? Use `<DataTable>`. A page header with title + actions? Use `<PageHeader>`. An empty state? Use `<EmptyState>`.
3. **Replace inline classes with token-based classes.** No `bg-[#1a2b3c]`. Use `bg-brand-500`.
4. **Replace inline event handlers with React events.** `onclick="..."` → `onClick={() => ...}`.
5. **Replace `<img>` with Next.js `<Image>`** for production images. Inline SVGs and `<Image>` with `unoptimized` for decorative ones.
6. **Mark client components explicitly.** `'use client'` only when needed (hooks, events, browser APIs).
7. **Lift state to the right level.** Per-component → `useState`. Cross-component within module → `useReducer` or module Zustand store. Cross-module → global Zustand store. Server data → TanStack Query.

## Pattern catalog

### Pattern 1: Buttons

**Claude Design HTML:**
```html
<button class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium transition-colors">
  Create campaign
</button>
```

**React:**
```tsx
import { Button } from '@/components/ui/button';

<Button onClick={handleCreate}>
  Create campaign
</Button>
```

Variants like `bg-red-600` map to `<Button variant="destructive">`. Outlined → `variant="outline"`. Ghost → `variant="ghost"`. Don't recreate styling.

### Pattern 2: Cards

**Claude Design HTML:**
```html
<div class="bg-white rounded-lg border border-slate-200 p-6 shadow-sm">
  <h3 class="text-lg font-semibold text-slate-900">Total companies</h3>
  <p class="text-3xl font-bold text-slate-900 mt-2">1,247</p>
  <p class="text-sm text-slate-500 mt-1">+12% from last month</p>
</div>
```

**React:**
```tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

<Card>
  <CardHeader>
    <CardTitle>Total companies</CardTitle>
  </CardHeader>
  <CardContent>
    <p className="text-3xl font-bold">1,247</p>
    <p className="text-sm text-text-muted mt-1">+12% from last month</p>
  </CardContent>
</Card>
```

If this exact pattern (stat with label, value, delta) appears 3+ times in the design, factor it into `components/shared/stat-tile.tsx`:

```tsx
type StatTileProps = {
  label: string;
  value: string | number;
  delta?: { value: string; direction: 'up' | 'down' | 'flat' };
};

export function StatTile({ label, value, delta }: StatTileProps) { /* ... */ }
```

### Pattern 3: Forms

**Claude Design HTML:**
```html
<form>
  <label class="block text-sm font-medium mb-1">Company name</label>
  <input type="text" class="w-full border rounded-md px-3 py-2" placeholder="Acme Corp" />
  
  <label class="block text-sm font-medium mb-1 mt-4">Industry</label>
  <select class="w-full border rounded-md px-3 py-2">
    <option>Technology</option>
    <option>Healthcare</option>
  </select>
  
  <button type="submit" class="mt-6 bg-blue-600 text-white px-4 py-2 rounded-md">
    Save
  </button>
</form>
```

**React (React Hook Form + Zod):**
```tsx
'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useCreateCompany } from '../hooks/use-companies';

const formSchema = z.object({
  name: z.string().min(1, 'Name is required').max(120),
  industry: z.enum(['technology', 'healthcare', 'finance']),
});

type FormValues = z.infer<typeof formSchema>;

export function CompanyForm({ onSuccess }: { onSuccess?: () => void }) {
  const createCompany = useCreateCompany();
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
  });

  const onSubmit = handleSubmit(async (values) => {
    await createCompany.mutateAsync(values);
    onSuccess?.();
  });

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <Label htmlFor="name">Company name</Label>
        <Input id="name" placeholder="Acme Corp" {...register('name')} />
        {errors.name && <p className="text-sm text-status-error-fg mt-1">{errors.name.message}</p>}
      </div>

      <div>
        <Label htmlFor="industry">Industry</Label>
        <Select onValueChange={(v) => setValue('industry', v as FormValues['industry'])}>
          <SelectTrigger id="industry">
            <SelectValue placeholder="Select industry" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="technology">Technology</SelectItem>
            <SelectItem value="healthcare">Healthcare</SelectItem>
            <SelectItem value="finance">Finance</SelectItem>
          </SelectContent>
        </Select>
        {errors.industry && <p className="text-sm text-status-error-fg mt-1">{errors.industry.message}</p>}
      </div>

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Saving…' : 'Save'}
      </Button>
    </form>
  );
}
```

Rules:
- Every form uses React Hook Form + Zod resolver.
- The Zod schema lives in `modules/<name>/schemas.ts` if it represents API contract, or inline if it's UI-only.
- Submit through a mutation hook (`useCreateCompany`), never directly via `fetch`.
- Error messages render below each field.
- Submit button shows loading state.

### Pattern 4: Tables

**Claude Design HTML:**
```html
<table class="w-full">
  <thead>
    <tr class="border-b">
      <th class="text-left p-3">Company</th>
      <th class="text-left p-3">Industry</th>
      <th class="text-left p-3">Headcount</th>
      <th class="text-right p-3">Actions</th>
    </tr>
  </thead>
  <tbody>
    <tr class="border-b">
      <td class="p-3">Acme Corp</td>
      <td class="p-3">Technology</td>
      <td class="p-3">142</td>
      <td class="p-3 text-right">...</td>
    </tr>
  </tbody>
</table>
```

**React (TanStack Table via `<DataTable>`):**

The table itself uses the shared `<DataTable>` component (see `references/tanstack-patterns.md` for the full implementation). The module supplies column defs:

```tsx
// modules/companies/components/companies-table-columns.tsx
'use client';

import type { ColumnDef } from '@tanstack/react-table';
import { DataTableColumnHeader } from '@/components/shared/data-table/data-table-column-header';
import { DataTableRowActions } from '@/components/shared/data-table/data-table-row-actions';
import type { Company } from '../types';

export const companiesColumns: ColumnDef<Company>[] = [
  {
    accessorKey: 'name',
    header: ({ column }) => <DataTableColumnHeader column={column} title="Company" />,
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: 'industry',
    header: 'Industry',
  },
  {
    accessorKey: 'headcount',
    header: ({ column }) => <DataTableColumnHeader column={column} title="Headcount" />,
    cell: ({ row }) => row.original.headcount.toLocaleString(),
  },
  {
    id: 'actions',
    cell: ({ row }) => <DataTableRowActions row={row} />,
  },
];
```

Then the page composition:

```tsx
// modules/companies/components/companies-table.tsx
'use client';

import { useCompanies } from '../hooks/use-companies';
import { DataTable } from '@/components/shared/data-table/data-table';
import { companiesColumns } from './companies-table-columns';

export function CompaniesTable() {
  const { data, isLoading, error } = useCompanies();

  if (isLoading) return <DataTableSkeleton />;
  if (error) return <ErrorState error={error} />;

  return <DataTable columns={companiesColumns} data={data ?? []} />;
}
```

### Pattern 5: List + detail layout

**Claude Design HTML:** typically two columns — list on the left, detail on the right.

**React:** route this as nested pages with parallel routes or as a query-string-driven detail panel.

Option A (separate routes):
```
app/(dashboard)/contacts/
├── page.tsx           → list view
└── [id]/page.tsx      → detail view
```

Option B (parallel routes for inline detail):
```
app/(dashboard)/inbox/
├── page.tsx
└── @detail/
    └── [threadId]/page.tsx
```

Pick based on the design: if clicking a list item navigates to a new page, use Option A. If clicking opens a panel beside the list (common in inboxes), use Option B.

### Pattern 6: Empty / loading / error states

Claude Design often shows only the populated state. You need to invent these states from the design's visual language.

```tsx
import { EmptyState } from '@/components/shared/empty-state';
import { Building2 } from 'lucide-react';

if (companies.length === 0) {
  return (
    <EmptyState
      icon={Building2}
      title="No companies yet"
      description="Import a CSV or create your first company to get started."
      action={<Button onClick={openImport}>Import CSV</Button>}
    />
  );
}
```

Standard states for every data view:
- **Loading** — skeleton matching the populated layout
- **Error** — error message with retry button
- **Empty (initial)** — onboarding CTA
- **Empty (filtered)** — "no results" with clear-filters CTA

### Pattern 7: Modals and drawers

**Claude Design HTML:** usually shown inline as if always open.

**React (modal):**
```tsx
'use client';

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { CompanyForm } from './company-form';
import { useState } from 'react';

export function CreateCompanyDialog() {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New company</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Create company</DialogTitle></DialogHeader>
        <CompanyForm onSuccess={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
```

### Pattern 8: Navigation (sidebar, topbar) — shadcn's sidebar block

Every sidebar uses shadcn's installed `<Sidebar>` block. No custom `<aside>` layouts. Single source of truth for nav items, typed:

```tsx
// modules/workspace/components/app-sidebar.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Building2, Users, Send, Inbox, GitBranch, BarChart3, Settings } from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';

const navItems = [
  { href: '/companies', label: 'Companies', icon: Building2 },
  { href: '/contacts',  label: 'Contacts',  icon: Users },
  { href: '/campaigns', label: 'Campaigns', icon: Send },
  { href: '/inbox',     label: 'Inbox',     icon: Inbox },
  { href: '/pipeline',  label: 'Pipeline',  icon: GitBranch },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
] as const;

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link href="/" className="flex items-center gap-2 px-2 py-1.5 font-semibold">
          {/* logo */}
          <APP_NAME>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const active = pathname.startsWith(item.href);
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton asChild isActive={active} tooltip={item.label}>
                      <Link href={item.href}>
                        <item.icon className="size-4" />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Settings">
              <Link href="/settings">
                <Settings className="size-4" />
                <span>Settings</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
```

The wrapping layout uses shadcn's `<SidebarProvider>`:

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
          {/* topbar content */}
        </header>
        <main className="flex-1 p-4">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
```

Variants the block supports (no need to re-implement):
- `collapsible="icon"` — collapses to icon-only rail
- `collapsible="offcanvas"` — slides off-screen on mobile
- `variant="floating"` — floats with margins instead of edge-to-edge
- `variant="inset"` — content area is inset card

If the design shows none of these and just wants a fixed full-height sidebar, use defaults — no override needed.

### Pattern 9: Charts and visualizations

If the design has charts, use shadcn's installed `chart` primitive (a thin wrapper around `recharts`):

```tsx
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { Bar, BarChart, CartesianGrid, XAxis } from 'recharts';

const chartConfig = {
  sends: { label: 'Sends', color: 'hsl(var(--chart-1))' },
  replies: { label: 'Replies', color: 'hsl(var(--chart-2))' },
} satisfies ChartConfig;

export function SendsChart({ data }: { data: SendsRow[] }) {
  return (
    <ChartContainer config={chartConfig}>
      <BarChart data={data}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="day" />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="sends" fill="var(--color-sends)" />
        <Bar dataKey="replies" fill="var(--color-replies)" />
      </BarChart>
    </ChartContainer>
  );
}
```

`recharts` is already a transitive dep via shadcn's `chart`. Don't install `tremor` or `@tremor/react` — they are forbidden alongside shadcn. Chart components live in module folders (`modules/analytics/components/sends-chart.tsx`).

### Pattern 10: Animations

Claude Design HTML may use `@keyframes` and CSS transitions. Two options:

1. **Simple transitions** — keep as Tailwind utilities (`transition-all duration-200`).
2. **Complex animations** — use Framer Motion:

```bash
pnpm add framer-motion
```

```tsx
'use client';

import { motion, AnimatePresence } from 'framer-motion';

<AnimatePresence>
  {isOpen && (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      {content}
    </motion.div>
  )}
</AnimatePresence>
```

Don't add Framer Motion if the design has no animations beyond basic hovers.

## Server vs. client components — when to add `'use client'`

Add `'use client'` only when the component needs:
- React hooks (`useState`, `useEffect`, custom hooks)
- Event handlers (`onClick`, `onChange`, `onSubmit`)
- Browser-only APIs (`window`, `document`, `localStorage`)
- Third-party libraries that use the above (TanStack Query, Framer Motion, etc.)

**Server components by default** include:
- Static layouts
- Data display from server-side fetched data
- Markdown rendering
- Lists where individual items don't need interactivity

**Push `'use client'` to leaves.** A page shell can be a server component even if it contains a client component (an interactive table) — Next.js renders the server shell with the client island inside it.

```tsx
// modules/companies/components/companies-page.tsx
// NO 'use client' — this is a server component

import { PageHeader } from '@/components/shared/page-header';
import { CompaniesTable } from './companies-table'; // ← client component (TanStack Table needs hooks)
import { CreateCompanyDialog } from './create-company-dialog'; // ← client component

export function CompaniesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Companies"
        description="All companies in your workspace."
        action={<CreateCompanyDialog />}
      />
      <CompaniesTable />
    </div>
  );
}
```

## Final sanity checks for each component

- [ ] Component is in the right module folder (or `components/shared/` if cross-module)
- [ ] No hex codes in className (all token-based)
- [ ] `'use client'` is present iff needed
- [ ] Loading state, error state, empty state all handled
- [ ] Forms use React Hook Form + Zod
- [ ] Tables use `<DataTable>` shared component
- [ ] Mutations show loading + toast feedback
- [ ] No `useEffect` for data fetching (use TanStack Query)
- [ ] Accessible: labels on inputs, alt text on images, focus-visible rings on interactive elements
