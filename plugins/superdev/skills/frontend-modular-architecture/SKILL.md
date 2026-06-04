---
name: frontend-modular-architecture
description: Use whenever building or auditing a Next.js frontend module. Enforces an opinionated modular structure (pages/, components/<comp>/parts/, stores/, hooks/) with strict file-size limits (page ≤ 100 lines, component ≤ 200 lines), dedicated Zustand stores per module (entity / UI / wizard), wizards split into per-step files, and sub-sub-components (drawers / modals / popovers) as their own folders rendering through React Portals via shadcn Dialog/Sheet/Popover. Prevents the AI antipatterns of god-files, state soup (50 useState piled up), useMemo/useCallback theater, and Portal-less drawers that fight stacking context.
---

# Frontend Modular Architecture

The opinionated structure-enforcer that prevents the AI-frontend antipatterns: god-files, state soup, callback theater, flat component folders, raw absolute-positioned drawers.

## The Iron Laws

```
1. PAGE FILES ≤ 100 LINES
2. COMPONENT FILES ≤ 200 LINES
3. SHARED STATE → MODULE STORE, NEVER PROP-DRILLED OR LIFTED
4. WIZARDS WITH ≥ 3 STEPS → PER-STEP FILES UNDER create-wizard/
5. DRAWERS / MODALS / POPOVERS → OWN FOLDER UNDER parts/, RENDERED VIA PORTAL
6. PAGES DELEGATE — they call hooks and render module components, no business logic
7. useMemo / useCallback ONLY when measurably needed, not by default
```

If any rule is violated, the module is unmaintainable at scale. AI agents reading the file later will pile more on, not refactor. The structure rules exist precisely because future-AI is bad at refactoring fat files.

## When to use

- ✅ Any greenfield frontend module being built (`frontend-module-builder` defers to this skill for layout)
- ✅ Auditing an existing module before declaring "done"
- ✅ As a wave-gate after any frontend agent writes new files
- ✅ When the user complains "my page got too big" / "I can't find anything in companies.tsx"

## When NOT to use

- ❌ Tiny one-off pages (a login page that's truly 60 lines and one form does not need pages/ + components/ + stores/ structure)
- ❌ Storybook stories / test files (these have their own layout)
- ❌ The shadcn `components/ui/*` primitives themselves (those are vendored, not module code)

## The canonical structure

```
apps/web/src/modules/<feature>/
├── pages/                              # Next.js page-level shells (≤ 100 lines each)
│   ├── list-page.tsx                   # data fetching + layout, delegates rendering
│   ├── detail-page.tsx
│   └── new-page.tsx
├── components/                          # All composable building blocks (≤ 200 lines each)
│   ├── <feature>-table/                # Each component-with-subcomponents is a FOLDER
│   │   ├── index.tsx                   # the table
│   │   ├── columns.tsx
│   │   ├── row-actions.tsx             # button that opens a menu (Portal)
│   │   ├── filters.tsx
│   │   └── parts/                      # SUB-SUB-COMPONENTS — own folders here
│   │       ├── delete-confirm-dialog/  # modal — own folder, own Portal
│   │       │   ├── index.tsx
│   │       │   └── confirm-button.tsx
│   │       ├── bulk-edit-drawer/       # drawer — own folder, own Portal
│   │       │   ├── index.tsx
│   │       │   ├── form.tsx
│   │       │   └── footer.tsx
│   │       └── column-customizer-popover/
│   │           └── index.tsx
│   ├── <feature>-card/
│   │   ├── index.tsx
│   │   ├── header.tsx
│   │   ├── body.tsx
│   │   └── footer.tsx
│   └── create-wizard/                  # Multi-step wizard — ALWAYS split
│       ├── index.tsx                   # orchestrator: nav + validation only
│       ├── step-1-basics.tsx
│       ├── step-2-contacts.tsx
│       ├── step-3-billing.tsx
│       ├── step-N-…
│       └── shared/                     # cross-step pieces
│           ├── nav-buttons.tsx
│           └── progress-indicator.tsx
├── stores/                              # Dedicated Zustand stores per concern
│   ├── <feature>-store.ts              # entity state (selection, filters, sort)
│   ├── <feature>-ui-store.ts           # which modal/drawer is open
│   └── <feature>-wizard-store.ts       # cross-step wizard values + step index
├── hooks/                               # Module-specific composed hooks
│   ├── use-<feature>.ts                # TanStack Query wrapper
│   ├── use-create-<feature>.ts         # mutation + cache invalidation
│   └── use-<feature>-form.ts           # RHF + Zod adapter
├── api.ts                               # fetchers ONLY (no UI logic)
└── index.ts                             # public exports
```

## The 7 rules in detail

### Rule 1 — Page files ≤ 100 lines

A page is a thin shell. It calls module hooks, picks a layout, renders module components. That's it.

```tsx
// pages/list-page.tsx — 30 lines, not 1500
export function CompaniesListPage() {
  const { data, isLoading } = useCompanies();
  if (isLoading) return <ListSkeleton />;
  return (
    <PageLayout title="Companies" actions={<CompaniesHeaderActions />}>
      <CompaniesTable rows={data} />
      <CreateCompanyDrawer />
    </PageLayout>
  );
}
```

If your page is > 100 lines, you're holding business logic that belongs in a hook or a component.

### Rule 2 — Component files ≤ 200 lines

When a component grows past 200 lines, it's doing too many things. Extract subcomponents into the folder.

**Before (god file):**
```
companies-table.tsx  (1,200 lines: table + columns + row menu + delete dialog + bulk drawer + filters)
```

**After:**
```
companies-table/
├── index.tsx            (160 lines: table layout, virtualization, pagination)
├── columns.tsx          (90 lines: column definitions)
├── row-actions.tsx      (50 lines: kebab menu opening parts/)
├── filters.tsx          (80 lines)
└── parts/
    ├── delete-confirm-dialog/ …
    └── bulk-edit-drawer/ …
```

### Rule 3 — Shared state → module store

If two sibling components both need a value, it does NOT get lifted to the parent and prop-drilled. It goes in the module store.

```ts
// stores/companies-ui-store.ts
import { create } from 'zustand';

type CompaniesUiState = {
  selectedIds: string[];
  toggleSelected: (id: string) => void;
  bulkDrawerOpen: boolean;
  openBulkDrawer: () => void;
  closeBulkDrawer: () => void;
  deleteConfirmFor: string | null;
  askDeleteConfirm: (id: string) => void;
  dismissDeleteConfirm: () => void;
};

export const useCompaniesUiStore = create<CompaniesUiState>((set) => ({
  selectedIds: [],
  toggleSelected: (id) => set((s) => ({
    selectedIds: s.selectedIds.includes(id)
      ? s.selectedIds.filter((x) => x !== id)
      : [...s.selectedIds, id],
  })),
  bulkDrawerOpen: false,
  openBulkDrawer: () => set({ bulkDrawerOpen: true }),
  closeBulkDrawer: () => set({ bulkDrawerOpen: false }),
  deleteConfirmFor: null,
  askDeleteConfirm: (id) => set({ deleteConfirmFor: id }),
  dismissDeleteConfirm: () => set({ deleteConfirmFor: null }),
}));
```

Now `companies-table/row-actions.tsx` calls `useCompaniesUiStore((s) => s.askDeleteConfirm)` and `parts/delete-confirm-dialog/index.tsx` reads `deleteConfirmFor`. No props between them. No god-state in the parent.

**Trigger heuristic:** if a component has ≥ 5 `useState` hooks, you're past the threshold — extract a store.

### Rule 4 — Wizards always split per-step

A 10-step Create flow is **10 files**, not one. The orchestrator file holds step navigation + cross-step validation. Each step is its own file. Cross-step values live in `<feature>-wizard-store.ts`.

```tsx
// components/create-wizard/index.tsx — orchestrator only
export function CreateCompanyWizard() {
  const step = useCompaniesWizardStore((s) => s.step);
  return (
    <Sheet open onOpenChange={...}>
      <SheetContent>
        <ProgressIndicator />
        {step === 1 && <Step1Basics />}
        {step === 2 && <Step2Contacts />}
        {step === 3 && <Step3Billing />}
        {/* … */}
        <NavButtons />
      </SheetContent>
    </Sheet>
  );
}
```

Each step file owns its form, its validation, its submit. Adding step 11 is `step-11-xyz.tsx` + one line in `index.tsx`. Reviewing the diff is trivial.

### Rule 5 — Drawers / modals / popovers use Portals

ALL drawers, modals, popovers, menus, tooltips MUST use shadcn primitives that wrap Radix Portals:

| Use case | Use | NEVER |
|---|---|---|
| Modal dialog | `<Dialog>` from `@/components/ui/dialog` | Raw `<dialog>` element, absolute-positioned div |
| Drawer / side sheet | `<Sheet>` from `@/components/ui/sheet` | Fixed/absolute div in component tree |
| Popover (rich content) | `<Popover>` from `@/components/ui/popover` | Conditional render in flow |
| Menu (right-click, kebab) | `<DropdownMenu>` / `<ContextMenu>` | Custom menu div |
| Tooltip | `<Tooltip>` from `@/components/ui/tooltip` | title attribute, custom tooltip div |
| Select / Combobox | `<Select>` / `<Combobox>` | Custom dropdown |

Why: Radix portals these to `document.body`, escaping the parent's `overflow: hidden`, `transform`, stacking context, z-index. A drawer rendered inside the table will get clipped by the table's overflow; the same drawer via `<Sheet>` won't.

Each drawer/modal/popover lives in its **own folder** under `parts/`:

```
companies-table/parts/
├── delete-confirm-dialog/    # one Portal-using component, own folder
├── bulk-edit-drawer/         # another, own folder
└── column-customizer-popover/  # another
```

This makes the Portal-correctness audit trivial — every folder under `parts/` should contain exactly one shadcn-Portal-primitive at its root.

### Rule 6 — Pages delegate

Pages are **layout + data hook + render module components**. They don't:

- ❌ Define columns inline (those live in `<feature>-table/columns.tsx`)
- ❌ Hold form state (forms live in component files with `use-<feature>-form.ts` hooks)
- ❌ Manage modal open/close (lives in `<feature>-ui-store.ts`)
- ❌ Do client-side filtering/sorting (lives in TanStack Query queryKey or backend)
- ❌ Have business validation logic (lives in Zod schemas in `packages/contracts`)

### Rule 7 — No useMemo/useCallback theater

`useMemo` and `useCallback` are NOT defensive defaults. Add them only when:
- A measurable render cost exists (profiled, not assumed)
- A referential-stable dependency is genuinely required for a downstream `useEffect` / `useMemo` / `useCallback` / memoized component

If you have ≥ 3 `useMemo` or `useCallback` in a component, the actual problem is usually that state should have been in a store (Zustand's selectors give you stable references for free), or the component is doing too much (split it).

## Sub-sub-component pattern

Critical: sub-sub-components get their **own folder** under `parts/`, not just a file.

✅ Correct:
```
companies-table/
├── index.tsx
└── parts/
    ├── delete-confirm-dialog/
    │   ├── index.tsx
    │   ├── confirm-button.tsx
    │   └── store.ts                  # local UI store if needed
    └── bulk-edit-drawer/
        ├── index.tsx
        ├── form.tsx
        ├── footer.tsx
        └── parts/                    # sub-sub-sub-component (rare but allowed)
            └── field-group.tsx
```

❌ Wrong (flat):
```
companies-table/
├── index.tsx
├── delete-confirm-dialog.tsx
├── bulk-edit-drawer.tsx
├── bulk-edit-drawer-form.tsx
└── bulk-edit-drawer-footer.tsx
```

Why folders: lets the dialog/drawer have its own state, its own subcomponents, its own tests, without polluting the parent component's directory listing. Future-AI can grep "where does the bulk-edit-drawer live" and get one folder, not 4 files.

## How the orchestrator should use this skill

For every frontend agent dispatch:

1. **Greenfield (`frontend-module-builder`)** — agent prompt is augmented with "you MUST follow [`frontend-modular-architecture`] — no god files, dedicated Zustand stores per module, sub-sub-components in `parts/<name>/`, Portals via shadcn primitives"
2. **Wave gate** — after the agent finishes, dispatch `module-structure-auditor` + `portal-correctness-auditor` on the just-built module. Any violations → block the wave, surface to the user
3. **Existing module needing decomposition** — orchestrator dispatches `frontend-refactoring` skill (separate atomic-conversion pipeline)

## Agent teams (optional — for store-architecture debates)

When a module is complex enough that store design is non-obvious (3+ candidate boundaries between entity store / UI store / wizard store / cache store):

```
Dispatch 3-teammate store-design debate.
Teammate A — minimalist: "everything in one store unless proven otherwise"
Teammate B — separator: "default to splitting by concern (entity / UI / wizard)"
Teammate C — futurist: "where will state live in 6 months?"

Majority verdict. Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```

## Reference files

- [`references/folder-structure.md`](references/folder-structure.md) — canonical layout reference
- [`references/store-patterns.md`](references/store-patterns.md) — Zustand patterns per store type
- [`references/portal-rules.md`](references/portal-rules.md) — which shadcn primitive for which use case
- [`references/agent-definitions.md`](references/agent-definitions.md) — dispatch prompts
- [`references/inertia-addendum.md`](references/inertia-addendum.md) — applying these rules to a Laravel + Inertia React frontend (`resources/js/`); the deltas vs Next.js
