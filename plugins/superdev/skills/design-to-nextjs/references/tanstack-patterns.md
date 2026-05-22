# TanStack Query & TanStack Table Patterns

How to structure data fetching, mutations, caching, and tables in the converted app. Read in Phase 5 (module generation).

## Part 1 — TanStack Query

### Rule 1: One query-keys file per module

Every module has a `query-keys.ts` that defines all keys for that module's queries. This makes invalidation predictable.

```ts
// modules/companies/query-keys.ts
export const companyKeys = {
  all: ['companies'] as const,
  lists: () => [...companyKeys.all, 'list'] as const,
  list: (filters: CompanyFilters) => [...companyKeys.lists(), filters] as const,
  details: () => [...companyKeys.all, 'detail'] as const,
  detail: (id: string) => [...companyKeys.details(), id] as const,
} as const;
```

This pattern (from the TanStack docs) enables targeted invalidation:
- `invalidate(companyKeys.all)` — refetch everything for companies
- `invalidate(companyKeys.lists())` — refetch all list views
- `invalidate(companyKeys.detail(id))` — refetch one specific company

### Rule 2: Module exposes hooks, not raw queries

External code calls `useCompanies()`, not `useQuery(...)` directly. The module owns the key shape and the schema.

```ts
// modules/companies/hooks/use-companies.ts
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { companiesApi } from '../api';
import { companyKeys } from '../query-keys';
import type { CompanyFilters, CreateCompanyInput, UpdateCompanyInput } from '../types';

export function useCompanies(filters: CompanyFilters = {}) {
  return useQuery({
    queryKey: companyKeys.list(filters),
    queryFn: ({ signal }) => companiesApi.list(filters, signal),
  });
}

export function useCompany(id: string) {
  return useQuery({
    queryKey: companyKeys.detail(id),
    queryFn: ({ signal }) => companiesApi.get(id, signal),
    enabled: Boolean(id),
  });
}

export function useCreateCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateCompanyInput) => companiesApi.create(input),
    onSuccess: (company) => {
      // Invalidate lists so they refetch
      queryClient.invalidateQueries({ queryKey: companyKeys.lists() });
      // Seed the detail cache so navigating to the new company is instant
      queryClient.setQueryData(companyKeys.detail(company.id), company);
      toast.success(`${company.name} created`);
    },
    onError: (error) => {
      toast.error('Failed to create company', { description: error.message });
    },
  });
}

export function useUpdateCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, ...input }: { id: string } & UpdateCompanyInput) =>
      companiesApi.update(id, input),
    // Optimistic update for instant UI feedback
    onMutate: async ({ id, ...input }) => {
      await queryClient.cancelQueries({ queryKey: companyKeys.detail(id) });
      const previous = queryClient.getQueryData(companyKeys.detail(id));
      queryClient.setQueryData(companyKeys.detail(id), (old: any) => ({ ...old, ...input }));
      return { previous };
    },
    onError: (error, { id }, context) => {
      // Roll back on failure
      if (context?.previous) {
        queryClient.setQueryData(companyKeys.detail(id), context.previous);
      }
      toast.error('Failed to update', { description: error.message });
    },
    onSettled: (_, __, { id }) => {
      queryClient.invalidateQueries({ queryKey: companyKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: companyKeys.lists() });
    },
  });
}

export function useDeleteCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => companiesApi.delete(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: companyKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: companyKeys.lists() });
      toast.success('Company deleted');
    },
  });
}
```

### Rule 3: api.ts uses the api-client wrapper, never raw fetch

```ts
// modules/companies/api.ts
import { apiRequest } from '@/lib/api-client';
import { companySchema, companyListSchema } from './schemas';
import type { Company, CompanyFilters, CreateCompanyInput, UpdateCompanyInput } from './types';

export const companiesApi = {
  list: (filters: CompanyFilters, signal?: AbortSignal) => {
    const params = new URLSearchParams(filters as Record<string, string>).toString();
    return apiRequest(`/companies?${params}`, {
      schema: companyListSchema,
      signal,
    });
  },

  get: (id: string, signal?: AbortSignal) =>
    apiRequest(`/companies/${id}`, { schema: companySchema, signal }),

  create: (input: CreateCompanyInput) =>
    apiRequest('/companies', { method: 'POST', body: input, schema: companySchema }),

  update: (id: string, input: UpdateCompanyInput) =>
    apiRequest(`/companies/${id}`, { method: 'PATCH', body: input, schema: companySchema }),

  delete: (id: string) =>
    apiRequest(`/companies/${id}`, { method: 'DELETE', schema: z.void() }),
};
```

### Rule 4: schemas.ts is the runtime contract

```ts
// modules/companies/schemas.ts
import { z } from 'zod';

export const companySchema = z.object({
  id: z.string(),
  name: z.string(),
  domain: z.string().nullable(),
  industry: z.enum(['technology', 'healthcare', 'finance', 'other']),
  size_bucket: z.enum(['1-10', '11-50', '51-200', '201-1000', '1000+']),
  headcount_current: z.number().int().nonnegative(),
  headcount_12mo_ago: z.number().int().nonnegative().nullable(),
  growth_signal: z.enum(['growing', 'stable', 'declining']),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const companyListSchema = z.object({
  data: z.array(companySchema),
  total: z.number(),
  page: z.number(),
  per_page: z.number(),
});

export const createCompanySchema = companySchema.pick({
  name: true,
  domain: true,
  industry: true,
});

export const updateCompanySchema = createCompanySchema.partial();
```

### Rule 5: Types are inferred from schemas

```ts
// modules/companies/types.ts
import type { z } from 'zod';
import type {
  companySchema,
  companyListSchema,
  createCompanySchema,
  updateCompanySchema,
} from './schemas';

export type Company = z.infer<typeof companySchema>;
export type CompanyList = z.infer<typeof companyListSchema>;
export type CreateCompanyInput = z.infer<typeof createCompanySchema>;
export type UpdateCompanyInput = z.infer<typeof updateCompanySchema>;

// Hand-written types that don't have a schema (e.g., filter shapes for the UI)
export type CompanyFilters = {
  search?: string;
  industry?: Company['industry'];
  size_bucket?: Company['size_bucket'];
  growth_signal?: Company['growth_signal'];
  page?: number;
  per_page?: number;
};
```

This pattern means the schema is the single source of truth: change the schema, types update automatically.

### Rule 6: Loading + error + empty states always

```tsx
'use client';

import { useCompanies } from '../hooks/use-companies';
import { DataTable } from '@/components/shared/data-table/data-table';
import { ErrorState } from '@/components/shared/error-state';
import { EmptyState } from '@/components/shared/empty-state';
import { DataTableSkeleton } from '@/components/shared/data-table/data-table-skeleton';
import { companiesColumns } from './companies-table-columns';
import { Building2 } from 'lucide-react';

export function CompaniesTable() {
  const { data, isLoading, error, refetch } = useCompanies();

  if (isLoading) return <DataTableSkeleton columns={companiesColumns.length} rows={10} />;
  if (error)     return <ErrorState message={error.message} onRetry={() => refetch()} />;
  if (!data || data.data.length === 0) {
    return <EmptyState icon={Building2} title="No companies yet" description="Import a CSV to get started." />;
  }

  return <DataTable columns={companiesColumns} data={data.data} />;
}
```

### Rule 7: Infinite scroll and pagination

For pagination, the filters include `page` — TanStack Query treats different filters as different queries automatically.

For infinite scroll:

```ts
export function useInfiniteCompanies(filters: Omit<CompanyFilters, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: [...companyKeys.lists(), 'infinite', filters],
    queryFn: ({ pageParam = 1, signal }) =>
      companiesApi.list({ ...filters, page: pageParam }, signal),
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((acc, p) => acc + p.data.length, 0);
      return loaded < lastPage.total ? allPages.length + 1 : undefined;
    },
  });
}
```

### Rule 8: Prefetching on the server

For pages that always need data, prefetch on the server and hydrate on the client:

```tsx
// app/(dashboard)/companies/page.tsx
import { dehydrate, HydrationBoundary } from '@tanstack/react-query';
import { makeQueryClient } from '@/lib/query-client';
import { companyKeys } from '@/modules/companies/query-keys';
import { companiesApi } from '@/modules/companies/api'; // server-safe API
import { CompaniesPage } from '@/modules/companies';

export default async function Page() {
  const queryClient = makeQueryClient();

  await queryClient.prefetchQuery({
    queryKey: companyKeys.list({}),
    queryFn: () => companiesApi.list({}),
  });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <CompaniesPage />
    </HydrationBoundary>
  );
}
```

---

## Part 2 — TanStack Table via shared `<DataTable>`

Every table in the app uses one shared `<DataTable>` component. Modules supply column defs and options.

### The shared `<DataTable>` component

```tsx
// components/shared/data-table/data-table.tsx
'use client';

import {
  type ColumnDef,
  type SortingState,
  type ColumnFiltersState,
  type VisibilityState,
  type RowSelectionState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table';
import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { DataTablePagination } from './data-table-pagination';
import { DataTableToolbar, type DataTableToolbarConfig } from './data-table-toolbar';

type DataTableProps<TData, TValue> = {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  toolbar?: DataTableToolbarConfig<TData>;
  pageSize?: number;
  enableRowSelection?: boolean;
  onRowClick?: (row: TData) => void;
};

export function DataTable<TData, TValue>({
  columns,
  data,
  toolbar,
  pageSize = 20,
  enableRowSelection = false,
  onRowClick,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnFilters, columnVisibility, rowSelection },
    enableRowSelection,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  });

  return (
    <div className="space-y-4">
      {toolbar && <DataTableToolbar table={table} config={toolbar} />}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() ? 'selected' : undefined}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  className={onRowClick ? 'cursor-pointer hover:bg-surface-muted' : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-text-muted">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <DataTablePagination table={table} />
    </div>
  );
}
```

### Column header with sort

```tsx
// components/shared/data-table/data-table-column-header.tsx
'use client';

import type { Column } from '@tanstack/react-table';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type Props<TData, TValue> = {
  column: Column<TData, TValue>;
  title: string;
  className?: string;
};

export function DataTableColumnHeader<TData, TValue>({ column, title, className }: Props<TData, TValue>) {
  if (!column.getCanSort()) {
    return <div className={className}>{title}</div>;
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
      className={cn('-ml-3 h-8', className)}
    >
      {title}
      {column.getIsSorted() === 'desc' ? (
        <ArrowDown className="ml-2 size-4" />
      ) : column.getIsSorted() === 'asc' ? (
        <ArrowUp className="ml-2 size-4" />
      ) : (
        <ArrowUpDown className="ml-2 size-4 opacity-50" />
      )}
    </Button>
  );
}
```

### Row actions menu

```tsx
// components/shared/data-table/data-table-row-actions.tsx
'use client';

import type { Row } from '@tanstack/react-table';
import { MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

type Props<TData> = {
  row: Row<TData>;
  actions: { label: string; onClick: (row: TData) => void; destructive?: boolean }[];
};

export function DataTableRowActions<TData>({ row, actions }: Props<TData>) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="size-8">
          <MoreHorizontal className="size-4" />
          <span className="sr-only">Open menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {actions.map((action) => (
          <DropdownMenuItem
            key={action.label}
            onClick={() => action.onClick(row.original)}
            className={action.destructive ? 'text-status-error-fg' : undefined}
          >
            {action.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

### Toolbar with search + filters

```tsx
// components/shared/data-table/data-table-toolbar.tsx
'use client';

import type { Table } from '@tanstack/react-table';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export type DataTableToolbarConfig<TData> = {
  searchColumn?: keyof TData & string;
  searchPlaceholder?: string;
  filters?: Array<{ column: keyof TData & string; title: string; options: { label: string; value: string }[] }>;
};

export function DataTableToolbar<TData>({
  table,
  config,
}: {
  table: Table<TData>;
  config: DataTableToolbarConfig<TData>;
}) {
  const isFiltered = table.getState().columnFilters.length > 0;

  return (
    <div className="flex items-center gap-2">
      {config.searchColumn && (
        <Input
          placeholder={config.searchPlaceholder ?? 'Search…'}
          value={(table.getColumn(config.searchColumn)?.getFilterValue() as string) ?? ''}
          onChange={(e) => table.getColumn(config.searchColumn!)?.setFilterValue(e.target.value)}
          className="h-9 w-[280px]"
        />
      )}
      {/* Render faceted filters from config.filters */}
      {isFiltered && (
        <Button variant="ghost" size="sm" onClick={() => table.resetColumnFilters()}>
          Reset <X className="ml-2 size-4" />
        </Button>
      )}
    </div>
  );
}
```

### Putting it together — companies table example

```tsx
// modules/companies/components/companies-table.tsx
'use client';

import { useCompanies } from '../hooks/use-companies';
import { DataTable } from '@/components/shared/data-table/data-table';
import { companiesColumns } from './companies-table-columns';

export function CompaniesTable() {
  const { data } = useCompanies();

  return (
    <DataTable
      columns={companiesColumns}
      data={data?.data ?? []}
      toolbar={{
        searchColumn: 'name',
        searchPlaceholder: 'Search companies…',
        filters: [
          {
            column: 'industry',
            title: 'Industry',
            options: [
              { label: 'Technology', value: 'technology' },
              { label: 'Healthcare', value: 'healthcare' },
            ],
          },
        ],
      }}
      pageSize={25}
      enableRowSelection
    />
  );
}
```

## Anti-patterns

- ❌ Calling `apiRequest` from a component directly. Use a hook.
- ❌ Using `useState` to mirror server data. Use TanStack Query.
- ❌ Multiple `<DataTable>` implementations. One shared component, many column defs.
- ❌ Hard-coded query keys. Use the keys factory from `query-keys.ts`.
- ❌ Skipping schema validation. Every response goes through Zod.
- ❌ Showing toasts from the component. Toast in the mutation's `onSuccess`/`onError`.
