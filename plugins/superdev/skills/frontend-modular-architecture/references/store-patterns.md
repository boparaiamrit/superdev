# Zustand store patterns per module

Every module that has shared state gets its own stores. The split is by **concern**, not by size — different stores serve different lifecycles:

| Store | Lifecycle | Persistence | Examples |
|---|---|---|---|
| `<feature>-store.ts` | Module session | None (or sessionStorage) | selection, filters, sort, view mode |
| `<feature>-ui-store.ts` | Module session | None | which modal/drawer/popover is open |
| `<feature>-wizard-store.ts` | One wizard instance | None | step index, cross-step form values, navigation history |
| `<feature>-prefs-store.ts` (optional) | App lifetime | localStorage | column visibility, page size, default sort |

## Pattern 1 — Entity store (selection / filters / sort)

```ts
// stores/companies-store.ts
import { create } from 'zustand';

type SortKey = 'name' | 'industry' | 'created_at';

type CompaniesState = {
  // Selection
  selectedIds: string[];
  toggleSelected: (id: string) => void;
  selectAll: (ids: string[]) => void;
  clearSelection: () => void;

  // Filters
  search: string;
  setSearch: (q: string) => void;
  industryFilter: string | null;
  setIndustryFilter: (v: string | null) => void;

  // Sort
  sortBy: SortKey;
  sortDir: 'asc' | 'desc';
  setSort: (by: SortKey, dir: 'asc' | 'desc') => void;
};

export const useCompaniesStore = create<CompaniesState>((set) => ({
  selectedIds: [],
  toggleSelected: (id) => set((s) => ({
    selectedIds: s.selectedIds.includes(id)
      ? s.selectedIds.filter((x) => x !== id)
      : [...s.selectedIds, id],
  })),
  selectAll: (ids) => set({ selectedIds: ids }),
  clearSelection: () => set({ selectedIds: [] }),

  search: '',
  setSearch: (search) => set({ search }),
  industryFilter: null,
  setIndustryFilter: (industryFilter) => set({ industryFilter }),

  sortBy: 'created_at',
  sortDir: 'desc',
  setSort: (sortBy, sortDir) => set({ sortBy, sortDir }),
}));
```

Components subscribe with selectors so they re-render only when their slice changes:

```tsx
// components/companies-table/row-actions.tsx
const toggle = useCompaniesStore((s) => s.toggleSelected);
const isSelected = useCompaniesStore((s) => s.selectedIds.includes(rowId));
```

## Pattern 2 — UI store (which modal/drawer is open)

```ts
// stores/companies-ui-store.ts
import { create } from 'zustand';

type CompaniesUiState = {
  bulkDrawerOpen: boolean;
  openBulkDrawer: () => void;
  closeBulkDrawer: () => void;

  deleteConfirmFor: string | null;
  askDeleteConfirm: (id: string) => void;
  dismissDeleteConfirm: () => void;

  columnCustomizerOpen: boolean;
  toggleColumnCustomizer: () => void;
};

export const useCompaniesUiStore = create<CompaniesUiState>((set, get) => ({
  bulkDrawerOpen: false,
  openBulkDrawer: () => set({ bulkDrawerOpen: true }),
  closeBulkDrawer: () => set({ bulkDrawerOpen: false }),

  deleteConfirmFor: null,
  askDeleteConfirm: (deleteConfirmFor) => set({ deleteConfirmFor }),
  dismissDeleteConfirm: () => set({ deleteConfirmFor: null }),

  columnCustomizerOpen: false,
  toggleColumnCustomizer: () => set({ columnCustomizerOpen: !get().columnCustomizerOpen }),
}));
```

Why separate from `<feature>-store.ts`: UI state has different semantics. Closing the bulk drawer should NOT clear selection. Filters surviving a modal close is correct. Keeping them in different stores makes the boundary explicit.

## Pattern 3 — Wizard store (cross-step values)

```ts
// stores/companies-wizard-store.ts
import { create } from 'zustand';

type CompanyDraft = {
  name?: string;
  industry?: string;
  contacts?: Array<{ email: string; role: string }>;
  billing?: { plan: string; seats: number };
  // ... shape mirrors what the wizard collects across all steps
};

type CompaniesWizardState = {
  step: number;
  draft: CompanyDraft;
  setStep: (step: number) => void;
  next: () => void;
  prev: () => void;
  patch: (p: Partial<CompanyDraft>) => void;
  reset: () => void;
};

const TOTAL_STEPS = 5;

export const useCompaniesWizardStore = create<CompaniesWizardState>((set) => ({
  step: 1,
  draft: {},
  setStep: (step) => set({ step }),
  next: () => set((s) => ({ step: Math.min(s.step + 1, TOTAL_STEPS) })),
  prev: () => set((s) => ({ step: Math.max(s.step - 1, 1) })),
  patch: (p) => set((s) => ({ draft: { ...s.draft, ...p } })),
  reset: () => set({ step: 1, draft: {} }),
}));
```

Each step file `step-N-foo.tsx` reads `draft.<its slice>` and calls `patch({ <its slice>: ... })`. The orchestrator (`create-wizard/index.tsx`) reads `step` to decide which step to render and calls `reset()` on submit success.

## Pattern 4 — Prefs store (persisted to localStorage)

```ts
// stores/companies-prefs-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type CompaniesPrefsState = {
  visibleColumns: string[];
  setVisibleColumns: (cols: string[]) => void;
  pageSize: number;
  setPageSize: (n: number) => void;
};

export const useCompaniesPrefsStore = create<CompaniesPrefsState>()(
  persist(
    (set) => ({
      visibleColumns: ['name', 'industry', 'created_at'],
      setVisibleColumns: (visibleColumns) => set({ visibleColumns }),
      pageSize: 50,
      setPageSize: (pageSize) => set({ pageSize }),
    }),
    { name: '<app>-companies-prefs' }
  )
);
```

Storage key uses the `<app>` placeholder from the project's brand — see plugin's [`README.md` placeholder convention](../../../README.md).

## When NOT to use a store

- ❌ State that's truly local to one component (e.g. "is this card expanded" controlling its own visual state with no consumers elsewhere) → keep `useState`
- ❌ Server data — that lives in TanStack Query, not Zustand. The store holds CLIENT-derived state (selection, filters) and the query holds SERVER state (the actual companies)
- ❌ Form values inside a single form — RHF handles those; use a wizard store only for cross-step values
- ❌ Routing state — use Next.js router

## Selector hygiene

Always select the smallest slice:

```tsx
// ✓ Good
const selectedIds = useCompaniesStore((s) => s.selectedIds);

// ✗ Bad (component re-renders on ANY state change)
const { selectedIds } = useCompaniesStore();
```

For multiple slices, use `shallow`:

```tsx
import { shallow } from 'zustand/shallow';
const [ids, sort] = useCompaniesStore((s) => [s.selectedIds, s.sortBy], shallow);
```

## Anti-patterns

| 🚫 | ✅ |
|---|---|
| Lifting state to the page to share between two siblings | Module store |
| Context provider for "isOpen" of a modal | UI store |
| `useState` chain in the page for filters | Entity store |
| 30 `useState` in a wizard component | Wizard store |
| Passing selected IDs through 4 levels of props | Store + selector at the leaf |
| Putting server data in a store | TanStack Query |
