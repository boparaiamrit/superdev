# State and Data Management

Where data lives and who owns it in an Inertia React monolith. Read during Phase 4 (per-page translation) and whenever you are deciding whether to reach for client state.

## The fundamental rule

**Server data belongs to Inertia props. Client-only UI state belongs to Zustand. Nothing else.**

There is no TanStack Query in this stack. Inertia replaces it entirely: the controller shapes and delivers all server data as typed props on every navigation. There is no client-side cache to manage, no query keys to maintain, and no loading spinners for data that was already serialized on the server.

### Decision tree

```
Is the data fetched from (or owned by) the server?
├── YES → It is an Inertia prop. The controller delivers it; the page receives it.
│         Need a refresh? router.reload({ only: ['propName'] })
└── NO → Is it form field values during an active submission?
          ├── YES → Inertia useForm(). (see forms-useform.md)
          └── NO → Is the state shared across multiple components on the page?
                    ├── YES → Is it scoped to one page/feature?
                    │         ├── YES → Component useState / useReducer (lift to common parent)
                    │         └── NO  → Zustand store (resources/js/stores/)
                    └── NO → Component-local useState
```

## Inertia props — the primary data layer

Every piece of data that originates on the server arrives as a typed prop. The controller eager-loads, shapes, and paginates; the page receives a fully-formed object with no optional chaining needed (see `typed-props.md` for the "no `?.`" discipline).

```tsx
// resources/js/pages/companies/index.tsx
import type { CompanyView, Paginated } from '@/types/companies'

// Props come from the controller — no fetching, no loading state, no error boundary for data
export default function CompaniesIndex({ companies, filters }: {
  companies: Paginated<CompanyView>
  filters: { search: string; industry: string }
}) {
  return (
    <div>
      {companies.data.map((c) => (
        <div key={c.id}>{c.name} — {c.industry}</div>
      ))}
    </div>
  )
}
```

The controller is the query layer:

```php
// app/Domains/Companies/Http/CompanyController.php
#[Authorize('viewAny', Company::class)]
public function index(Request $request): \Inertia\Response
{
    return Inertia::render('companies/index', [
        'companies' => CompanyResource::collection(
            Company::query()
                ->withCount('contacts')
                ->when($request->search, fn($q, $v) => $q->where('name', 'ilike', "%{$v}%"))
                ->paginate(25)
        )->toArray($request),
        'filters' => [
            'search'   => $request->search ?? '',
            'industry' => $request->industry ?? '',
        ],
    ]);
}
```

## Partial reloads — refreshing specific props

When the user changes a filter or a background action updates server data, use `router.reload` with `only` to re-fetch specific props without a full page transition. This avoids re-rendering the entire page and preserves scroll position.

```tsx
import { router } from '@inertiajs/react'
import { Input } from '@/components/ui/input'

function CompanySearchBar({ initialSearch }: { initialSearch: string }) {
  const [search, setSearch] = useState(initialSearch)

  function handleSearch(value: string) {
    setSearch(value)
    router.reload({
      only: ['companies'],           // reload only the 'companies' prop
      data: { search: value },       // send updated query params
      preserveState: true,           // keep other component state
      preserveScroll: true,
    })
  }

  return (
    <Input
      value={search}
      onChange={(e) => handleSearch(e.target.value)}
      placeholder="Search companies…"
    />
  )
}
```

Use `only` to name the exact props to reload. Keep the list tight — listing props not needed wastes a round-trip.

### When to use `router.reload` vs a full visit

| Scenario | Approach |
|---|---|
| Filter / sort / paginate within the same page | `router.reload({ only: [...], data: {...} })` |
| Navigate to a different page | `router.visit()` or `<Link href>` |
| After a mutation that changes displayed data | `router.reload({ only: [...] })` in the `onSuccess` callback of `useForm` |
| After a background action (e.g. polling, websocket) | `router.reload({ only: [...] })` on the event |

## Zustand — genuine client-only UI state only

Zustand is for state that has **no server source of truth**: sidebar collapsed, command palette open, drag-and-drop in-progress state, multi-step wizard step, row selection across a table + toolbar.

The Zustand conventions for this stack are identical to the Next.js path. Read them in full at `design-to-nextjs/references/zustand-patterns.md`. Key points that apply here:

- Store lives in `resources/js/stores/` (global) or `resources/js/pages/<feature>/store.ts` (scoped).
- Use selectors, not whole-store destructuring, to avoid unnecessary re-renders.
- Persist only durable preferences (theme, sidebar state). Do not persist server data shadows.
- Auth session is NOT stored in Zustand — it arrives as `usePage().props.auth` (a shared Inertia prop from `HandleInertiaRequests::share`).

### Example: sidebar + command palette (global)

```ts
// resources/js/stores/ui-store.ts
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

type UiState = {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  commandPaletteOpen: boolean
  setCommandPaletteOpen: (open: boolean) => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      commandPaletteOpen: false,
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
    }),
    {
      name: 'ui',
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed }),
    },
  ),
)

// Named selectors — export and reuse these, never destructure the whole store
export const useSidebarCollapsed = () => useUiStore((s) => s.sidebarCollapsed)
export const useToggleSidebar = () => useUiStore((s) => s.toggleSidebar)
export const useCommandPaletteOpen = () => useUiStore((s) => s.commandPaletteOpen)
export const useSetCommandPaletteOpen = () => useUiStore((s) => s.setCommandPaletteOpen)
```

### Example: kanban drag state (feature-scoped)

```ts
// resources/js/pages/pipeline/store.ts
import { create } from 'zustand'

type PipelineUiState = {
  draggingLeadId: string | null
  hoveredStageId: string | null
  setDragging: (leadId: string | null) => void
  setHoveredStage: (stageId: string | null) => void
  selectedLeadIds: Set<string>
  toggleLeadSelection: (id: string) => void
  clearSelection: () => void
}

export const usePipelineUi = create<PipelineUiState>((set, get) => ({
  draggingLeadId: null,
  hoveredStageId: null,
  setDragging: (leadId) => set({ draggingLeadId: leadId }),
  setHoveredStage: (stageId) => set({ hoveredStageId: stageId }),
  selectedLeadIds: new Set(),
  toggleLeadSelection: (id) =>
    set((s) => {
      const next = new Set(s.selectedLeadIds)
      next.has(id) ? next.delete(id) : next.add(id)
      return { selectedLeadIds: next }
    }),
  clearSelection: () => set({ selectedLeadIds: new Set() }),
}))
```

Note what is NOT in this store: the leads themselves and the pipeline stages. Those arrive as Inertia props from the controller.

## Auth state — always from Inertia shared props

Auth is NOT a Zustand store. It is a shared Inertia prop injected by `HandleInertiaRequests::share` on every request (see `auth-fortify-permissions.md`). Read it with `usePage()`:

```tsx
import { usePage } from '@inertiajs/react'

function CompanyActions() {
  const { auth } = usePage().props
  // auth.user is always present on authenticated pages (no ?. needed — controller guarantees it)
  // auth.permissions is a string[] of resolved permission names
  return auth.permissions.includes('company.create') ? <CreateButton /> : null
}
```

Do not copy auth data into a Zustand store. If auth changes (logout, permission update), a full Inertia navigation re-delivers the updated shared props automatically.

## No TanStack Query

TanStack Query does not exist in this stack. Do not install `@tanstack/react-query`. The problem it solves (server state caching and refetching) is handled differently here:

| TanStack Query pattern | Inertia equivalent |
|---|---|
| `useQuery` to fetch a list | Controller delivers list as a prop; page receives it |
| `useMutation` + `invalidateQueries` | `useForm().post/put/delete` + `router.reload({ only: [...] })` |
| Background refetch / polling | `router.reload({ only: [...] })` on a timer or event |
| Prefetch on server | Data is already in props — no prefetch step needed |
| Optimistic updates | Manage in local `useState` + confirm on prop reload |
| Loading / error states for data | Data is always present at render; no loading state for initial data (handle only `form.processing` for submissions) |

## Anti-patterns

### Fetching server data on the client

```tsx
// WRONG — do not fetch server data in a component
function CompanyList() {
  const [companies, setCompanies] = useState([])
  useEffect(() => {
    fetch('/api/companies').then(r => r.json()).then(setCompanies)
  }, [])
  return companies.map(...)
}

// RIGHT — data arrives as a typed prop; no fetching needed
function CompanyList({ companies }: { companies: Paginated<CompanyView> }) {
  return companies.data.map(...)
}
```

### Mirroring server state in Zustand

```ts
// WRONG — server data does not belong in a Zustand store
const useCompanyStore = create((set) => ({
  companies: [],
  fetchCompanies: async () => {
    const data = await fetch('/api/companies').then(r => r.json())
    set({ companies: data })
  },
}))

// RIGHT — companies come from the controller as props
// Zustand only holds UI state (selection, drag, open panels)
```

### Using optional chaining on Inertia prop fields

```tsx
// WRONG — ?. implies the controller might not deliver the field
const name = company?.name ?? 'Unknown'

// RIGHT — the controller guarantees the shape; no ?. on prop fields
const name = company.name   // typed as string in resources/js/types/companies.ts
```

See `typed-props.md` for the full "no `?.`" discipline.

### Installing TanStack Query

TanStack Query is the data layer for the decoupled Next.js path where the frontend fetches from a JSON API. Installing it in an Inertia monolith creates a parallel data layer that conflicts with Inertia's prop delivery model. It is explicitly forbidden in this stack.

### Global store for page-scoped state

If state is only needed within one page, keep it in `useState` (or lifted to the page component). Only introduce a Zustand store when state genuinely crosses pages or persists across navigations.

## Summary

| Data / state | Owner |
|---|---|
| Server records (lists, details, counts) | Inertia props from controller |
| Filtering / sorting / pagination | `router.reload({ only: [...], data: {...} })` |
| Auth user + permissions | `usePage().props.auth` (shared Inertia prop) |
| Form field values + validation errors | Inertia `useForm()` |
| UI chrome (sidebar, theme, palette) | Zustand global store (`resources/js/stores/`) |
| Feature-scoped UI (drag, selection, wizard) | Zustand page store (`resources/js/pages/<feature>/store.ts`) |
| Transient component state | `useState` |
| TanStack Query | Not present — do not install |
