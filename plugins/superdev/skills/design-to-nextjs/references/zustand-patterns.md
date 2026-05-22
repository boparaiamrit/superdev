# Zustand Store Conventions

When and how to use Zustand in the converted app. Read in Phase 5.

## The single most important rule

**Zustand is for client/UI state. Server state belongs to TanStack Query. Form state belongs to React Hook Form.**

If you find yourself putting an API-fetched list into a Zustand store, stop. That data has a server source of truth, and TanStack Query already owns its cache, invalidation, refetching, and loading states. Duplicating it in Zustand creates two sources of truth and a stale-data nightmare.

### Decision tree

```
Is the data fetched from an API?
├── YES → TanStack Query. Always.
└── NO → Is the data a form's field values?
        ├── YES → React Hook Form.
        └── NO → Is the state shared across multiple components?
                 ├── YES → Is it scoped to one module?
                 │        ├── YES → Module Zustand store (modules/<name>/store.ts)
                 │        └── NO  → Global Zustand store (stores/*.ts)
                 └── NO → Component-local useState
```

## What belongs in Zustand

Real examples from a CRM:

- **UI chrome**: sidebar collapsed/expanded, command palette open, current theme
- **Modal/drawer open state** when multiple components need to open/close it (otherwise `useState`)
- **Selection state** when shared between toolbar and table (e.g., "X rows selected" badge in toolbar that depends on table selection)
- **Multi-step wizard state** when steps live in separate components
- **Optimistic UI flags** like "campaign is sending now, show spinner in nav"
- **Filter state** when filters live in one component and the table lives in another (though URL-driven filters are often better)
- **Current workspace ID** (global, scoped to session)
- **Active user / auth session** (global, scoped to session)

## What does NOT belong in Zustand

- API data (companies, contacts, campaigns, emails, leads, deals — all of these)
- Form field values
- Server-derived computed values (counts, totals — derive from query data)
- Anything that has a server source of truth, ever

## Global stores

Usually one or two. If you reach for a third, ask whether it really transcends modules.

### `src/stores/auth-store.ts`

```ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

type AuthSession = {
  userId: string;
  email: string;
  workspaceId: string;
  roles: Array<'admin' | 'operator' | 'pipeline' | 'viewer'>;
};

type AuthState = {
  session: AuthSession | null;
  setSession: (session: AuthSession | null) => void;
  clearSession: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      session: null,
      setSession: (session) => set({ session }),
      clearSession: () => set({ session: null }),
    }),
    {
      name: '<app>-auth',
      storage: createJSONStorage(() => localStorage),
    },
  ),
);

// Selectors — prefer these over raw store access
export const useCurrentUser = () => useAuthStore((s) => s.session);
export const useIsAuthenticated = () => useAuthStore((s) => Boolean(s.session));
export const useHasRole = (role: AuthSession['roles'][number]) =>
  useAuthStore((s) => s.session?.roles.includes(role) ?? false);
```

### `src/stores/ui-store.ts`

```ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

type Theme = 'light' | 'dark' | 'system';

type UiState = {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;

  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;

  theme: Theme;
  setTheme: (theme: Theme) => void;
};

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      commandPaletteOpen: false,
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),

      theme: 'system',
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: '<app>-ui',
      storage: createJSONStorage(() => localStorage),
      // Persist only durable preferences — not transient state
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        theme: state.theme,
      }),
    },
  ),
);
```

## Module stores

A module store lives in `modules/<name>/store.ts`. Most modules don't need one — only create when state crosses components.

### Example: CSV import wizard state

The CSV import wizard has steps: upload → detect → map → validate → preview → confirm. State flows across these steps and is shared between the step components and a global progress indicator.

```ts
// modules/companies/store.ts
import { create } from 'zustand';
import type { ImportMode, ColumnMapping } from './types';

type ImportWizardState = {
  // Step navigation
  currentStep: 'upload' | 'detect' | 'map' | 'validate' | 'preview' | 'confirm';
  goToStep: (step: ImportWizardState['currentStep']) => void;
  nextStep: () => void;
  prevStep: () => void;

  // Step data
  file: File | null;
  setFile: (file: File | null) => void;

  mode: ImportMode | null;
  setMode: (mode: ImportMode) => void;

  columnMapping: ColumnMapping;
  setColumnMapping: (mapping: ColumnMapping) => void;

  // Reset
  reset: () => void;
};

const STEPS = ['upload', 'detect', 'map', 'validate', 'preview', 'confirm'] as const;

const initialState = {
  currentStep: 'upload' as const,
  file: null,
  mode: null,
  columnMapping: {} as ColumnMapping,
};

export const useImportWizard = create<ImportWizardState>((set, get) => ({
  ...initialState,

  goToStep: (step) => set({ currentStep: step }),
  nextStep: () => {
    const idx = STEPS.indexOf(get().currentStep);
    const next = STEPS[idx + 1];
    if (next) set({ currentStep: next });
  },
  prevStep: () => {
    const idx = STEPS.indexOf(get().currentStep);
    const prev = STEPS[idx - 1];
    if (prev) set({ currentStep: prev });
  },

  setFile: (file) => set({ file }),
  setMode: (mode) => set({ mode }),
  setColumnMapping: (columnMapping) => set({ columnMapping }),

  reset: () => set(initialState),
}));
```

### Example: Pipeline kanban drag-and-drop

```ts
// modules/pipeline/store.ts
import { create } from 'zustand';

type PipelineUiState = {
  draggingLeadId: string | null;
  hoveredStageId: string | null;
  setDragging: (leadId: string | null) => void;
  setHoveredStage: (stageId: string | null) => void;

  selectedLeadIds: Set<string>;
  toggleLeadSelection: (id: string) => void;
  clearSelection: () => void;
};

export const usePipelineUi = create<PipelineUiState>((set, get) => ({
  draggingLeadId: null,
  hoveredStageId: null,
  setDragging: (leadId) => set({ draggingLeadId: leadId }),
  setHoveredStage: (stageId) => set({ hoveredStageId: stageId }),

  selectedLeadIds: new Set(),
  toggleLeadSelection: (id) =>
    set((s) => {
      const next = new Set(s.selectedLeadIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { selectedLeadIds: next };
    }),
  clearSelection: () => set({ selectedLeadIds: new Set() }),
}));
```

Note what is NOT in this store: the leads themselves, the stages, the pipeline config. Those all come from TanStack Query hooks (`usePipeline`, `useLeads`). The store holds only UI state.

## Selector pattern

Always prefer selectors over destructuring the whole store. Selectors prevent unnecessary re-renders.

```tsx
// ❌ Re-renders on ANY store change
const { sidebarCollapsed, toggleSidebar } = useUiStore();

// ✅ Re-renders only when sidebarCollapsed changes
const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
const toggleSidebar = useUiStore((s) => s.toggleSidebar);

// ✅ Even better — export selectors as named hooks for reuse
export const useSidebarCollapsed = () => useUiStore((s) => s.sidebarCollapsed);
```

For derived/composed state, use `useShallow`:

```ts
import { useShallow } from 'zustand/shallow';

const { user, isAdmin } = useAuthStore(
  useShallow((s) => ({ user: s.session, isAdmin: s.session?.roles.includes('admin') ?? false })),
);
```

## Persistence rules

- Persist durable preferences: theme, sidebar state, language.
- DO NOT persist auth tokens to localStorage — use httpOnly cookies via the server.
- DO NOT persist server data shadows in Zustand — TanStack Query has its own persistence story (`persistQueryClient`).
- Use `partialize` to control what gets persisted, so transient state doesn't survive reloads.

## Devtools

In development, enable Redux DevTools support:

```ts
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

export const useUiStore = create<UiState>()(
  devtools(
    persist(
      (set) => ({ /* ... */ }),
      { name: '<app>-ui' },
    ),
    { name: 'UiStore', enabled: process.env.NODE_ENV === 'development' },
  ),
);
```

## Anti-patterns to avoid

- ❌ Putting `companies: Company[]` in a Zustand store. That's server state — use TanStack Query.
- ❌ Putting `formValues: { name: string; ... }` in a store. That's form state — use React Hook Form.
- ❌ One mega-store for the whole app. Split by concern.
- ❌ Subscribing to the whole store: `const store = useUiStore()`. Use selectors.
- ❌ Mutating state outside `set()`. Always use the setter.
- ❌ Persisting transient state like "modal open". Use `partialize`.
- ❌ Storing functions/instances/refs in persisted state — they don't serialize.

## When to NOT introduce a Zustand store

Three components need to share state:

```tsx
// Component A
const [filter, setFilter] = useState('');
// Component B (sibling)
const [filter, setFilter] = useState('');
// Component C (sibling) — same filter
```

Before reaching for Zustand, consider:

1. **Lift to common parent + pass props** — simplest, works for shallow trees
2. **React Context** — when prop drilling becomes painful but state is local to a subtree
3. **URL state** — for filters, search, pagination, this is often the right answer (use `nuqs` or `useSearchParams`)
4. **Zustand** — when none of the above fit and the state is genuinely cross-cutting

URL state is especially underrated. If a user wants to share a filtered view with a colleague, URL state lets them — Zustand doesn't.
