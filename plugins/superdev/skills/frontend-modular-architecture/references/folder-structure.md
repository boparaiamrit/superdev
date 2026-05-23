# Canonical folder structure

The reference layout. Every new module follows this. Every existing module audited against it.

```
apps/web/src/modules/<feature>/
├── pages/                                  # NEXT.JS PAGES — thin shells
│   ├── list-page.tsx                       # ≤ 100 lines: layout + data hook
│   ├── detail-page.tsx
│   └── new-page.tsx
│
├── components/                              # COMPOSABLE BUILDING BLOCKS
│   ├── <feature>-table/                    # component with subcomponents → FOLDER
│   │   ├── index.tsx                       # ≤ 200 lines: table layout
│   │   ├── columns.tsx                     # column defs
│   │   ├── row-actions.tsx                 # kebab menu trigger
│   │   ├── filters.tsx
│   │   └── parts/                          # SUB-SUB-COMPONENTS
│   │       ├── delete-confirm-dialog/      # one Portal-primitive per folder
│   │       │   ├── index.tsx
│   │       │   └── confirm-button.tsx
│   │       ├── bulk-edit-drawer/
│   │       │   ├── index.tsx
│   │       │   ├── form.tsx
│   │       │   ├── footer.tsx
│   │       │   └── parts/                  # sub-sub-sub (rare)
│   │       │       └── field-group.tsx
│   │       └── column-customizer-popover/
│   │           └── index.tsx
│   │
│   ├── <feature>-card/
│   │   ├── index.tsx
│   │   ├── header.tsx
│   │   ├── body.tsx
│   │   └── footer.tsx
│   │
│   └── create-wizard/                      # MULTI-STEP — always split
│       ├── index.tsx                       # orchestrator: step nav + validation
│       ├── step-1-basics.tsx
│       ├── step-2-contacts.tsx
│       ├── step-3-billing.tsx
│       ├── step-N-…
│       └── shared/                         # cross-step pieces
│           ├── nav-buttons.tsx
│           ├── progress-indicator.tsx
│           └── validation-summary.tsx
│
├── stores/                                  # DEDICATED STORES per concern
│   ├── <feature>-store.ts                  # entity state (selection, filters, sort)
│   ├── <feature>-ui-store.ts               # which modal/drawer is open
│   └── <feature>-wizard-store.ts           # cross-step wizard values + step
│
├── hooks/                                   # MODULE-SPECIFIC composed hooks
│   ├── use-<feature>.ts                    # TanStack Query wrapper for list
│   ├── use-<feature>-detail.ts             # TanStack Query wrapper for one
│   ├── use-create-<feature>.ts             # mutation + cache invalidation
│   ├── use-update-<feature>.ts
│   ├── use-<feature>-form.ts               # RHF + Zod adapter
│   └── use-<feature>-selection.ts          # bulk-select helpers using ui-store
│
├── api.ts                                   # fetchers ONLY (no UI logic)
└── index.ts                                 # public exports (only what other modules need)
```

## When a single file is OK

Tiny modules don't need every subfolder. Acceptable minimal layout for a 1-page module:

```
modules/<feature>/
├── pages/
│   └── index-page.tsx                       # ≤ 100 lines
├── components/
│   └── <feature>-content.tsx                # ≤ 200 lines
├── hooks/
│   └── use-<feature>.ts
├── api.ts
└── index.ts
```

Skipped: `stores/` (no shared state), no `parts/` (no sub-sub-components).

Threshold to upgrade: when the module grows to ≥ 3 distinct pages OR ≥ 5 distinct components OR ≥ 1 wizard OR ≥ 1 drawer/modal — adopt the full structure.

## Naming conventions

- **Component folders** — kebab-case-feature-name: `companies-table/`, `create-wizard/`
- **Sub-sub-component folders** under `parts/` — describe what they DO + the primitive: `delete-confirm-dialog/`, `bulk-edit-drawer/`, `filter-popover/`
- **Step files** in wizards — `step-N-purpose.tsx`: `step-1-basics.tsx`, `step-2-contacts.tsx`
- **Page files** — `<verb>-page.tsx`: `list-page.tsx`, `new-page.tsx`, `edit-page.tsx`
- **Store files** — `<feature>-<concern>-store.ts`: `companies-store.ts`, `companies-ui-store.ts`, `companies-wizard-store.ts`
- **Hook files** — `use-<verb>-<noun>.ts`: `use-companies.ts`, `use-create-company.ts`

## Why folder-per-subcomponent

A FILE can grow. A FOLDER cannot. By making sub-sub-components folders, you guarantee that when the next iteration adds complexity to `bulk-edit-drawer`, the new pieces land inside `bulk-edit-drawer/` instead of being inlined into its file.

## When a `parts/` folder isn't needed

A component is allowed to have child components in the SAME folder if they're NOT Portal-using and NOT independently extractable:

```
companies-card/
├── index.tsx
├── header.tsx          # plain subcomponent of the card
├── body.tsx
└── footer.tsx
```

The `parts/` convention is RESERVED for sub-sub-components that are:
- Portal-using (drawer/modal/popover/menu), OR
- Independently lifecycle-managed (their own open/close state, their own data needs)

Plain visual subdivisions (header / body / footer) stay flat in the parent folder.
