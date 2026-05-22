# Enterprise Folder Structure & Module Conventions

This is the canonical layout for the converted Next.js application. Follow it exactly unless the user explicitly opts out of a piece.

## Top-level layout

```
my-app/
├── .env.example
├── .eslintrc.json
├── .prettierrc
├── next.config.mjs
├── package.json
├── postcss.config.js
├── tailwind.config.ts
├── tsconfig.json
├── components.json            ← shadcn/ui config
├── public/
└── src/
    ├── app/                   ← Next.js App Router pages
    ├── components/
    │   ├── ui/                ← shadcn primitives (Button, Input, Dialog, ...)
    │   └── shared/            ← cross-module composites
    ├── modules/               ← feature modules (the bulk of the app)
    ├── lib/                   ← framework-level utilities
    ├── hooks/                 ← global hooks (useDebounce, useMediaQuery, ...)
    ├── stores/                ← global Zustand stores ONLY
    ├── styles/                ← globals.css, tokens.ts
    └── types/                 ← global TypeScript types (User, AuthSession, ...)
```

## `src/app/` — routing

Use route groups for organization without affecting the URL:

```
src/app/
├── (auth)/                    ← public routes
│   ├── login/page.tsx
│   ├── signup/page.tsx
│   └── layout.tsx             ← centered card layout
├── (dashboard)/               ← authenticated routes
│   ├── layout.tsx             ← sidebar + topbar
│   ├── page.tsx               ← / (dashboard home)
│   ├── companies/
│   │   ├── page.tsx           ← /companies
│   │   ├── [id]/page.tsx      ← /companies/:id
│   │   └── import/page.tsx    ← /companies/import
│   ├── contacts/
│   ├── campaigns/
│   ├── inbox/
│   └── pipeline/
├── api/                       ← Route handlers if needed
├── providers.tsx              ← QueryClientProvider, ThemeProvider, etc.
├── layout.tsx                 ← root layout (imports providers, fonts)
├── error.tsx                  ← root error boundary
├── not-found.tsx
└── globals.css                ← Tailwind directives + base styles
```

**Page files stay thin.** A page imports the relevant module's exports and composes them. Never put business logic in `page.tsx`.

```tsx
// src/app/(dashboard)/companies/page.tsx
import { CompaniesPage } from '@/modules/companies';

export default function Page() {
  return <CompaniesPage />;
}
```

## `src/modules/<feature>/` — feature modules

Every module follows the same shape:

```
src/modules/companies/
├── index.ts                   ← public API (re-exports types, hooks, components)
├── types.ts                   ← Company, CompanySize, GrowthSignal, ...
├── schemas.ts                 ← Zod schemas (companySchema, createCompanySchema)
├── api.ts                     ← getCompanies(), createCompany(), updateCompany()
├── query-keys.ts              ← centralized query keys for invalidation
├── hooks/
│   ├── use-companies.ts       ← useCompanies, useCompany, useCreateCompany, useUpdateCompany, useDeleteCompany
│   └── use-companies-table.ts ← table-specific state hook
├── store.ts                   ← Zustand store (ONLY if cross-component UI state exists)
├── components/
│   ├── companies-page.tsx     ← top-level page composition
│   ├── companies-table.tsx    ← TanStack Table
│   ├── companies-table-columns.tsx  ← column defs (separate file is intentional)
│   ├── companies-filter-bar.tsx
│   ├── company-detail.tsx
│   ├── company-detail-header.tsx
│   ├── company-form.tsx
│   └── company-form-fields/   ← sub-components if the form is big
└── lib/                       ← module-internal utilities (rare)
```

### Module public API

The `index.ts` is the public surface. Outside the module, only import from `@/modules/<name>` — never deep paths.

```ts
// src/modules/companies/index.ts
export type { Company, CompanySize, GrowthSignal } from './types';
export { companySchema, createCompanySchema } from './schemas';
export { useCompanies, useCompany, useCreateCompany } from './hooks/use-companies';
export { CompaniesPage } from './components/companies-page';
export { CompanyDetail } from './components/company-detail';
// DO NOT export api functions — they should only be called via hooks
// DO NOT export the store directly — expose specific selectors via hooks
```

### Within a module, deep imports are fine

```tsx
// inside src/modules/companies/components/companies-page.tsx
import { useCompanies } from '../hooks/use-companies';
import { CompaniesTable } from './companies-table';
```

### Cross-module imports go through the public API

```tsx
// src/modules/contacts/components/contact-detail.tsx
import { useCompany } from '@/modules/companies';
//                                  ^^^^^^^^^^^^ public surface only
```

If you find yourself wanting a deep import across modules, that's a signal the thing you want belongs in `components/shared/` or `lib/`.

## `src/components/ui/` — primitive components

This is where shadcn/ui drops its files. Don't put anything else here.

```
src/components/ui/
├── button.tsx
├── input.tsx
├── select.tsx
├── dialog.tsx
├── dropdown-menu.tsx
├── badge.tsx
├── avatar.tsx
├── toast.tsx
├── tooltip.tsx
├── skeleton.tsx
└── ...
```

## `src/components/shared/` — cross-module composites

Components that compose multiple primitives and are used by more than one module:

```
src/components/shared/
├── data-table/                ← generic TanStack Table wrapper
│   ├── data-table.tsx
│   ├── data-table-pagination.tsx
│   ├── data-table-column-header.tsx
│   ├── data-table-toolbar.tsx
│   └── data-table-row-actions.tsx
├── page-header.tsx
├── empty-state.tsx
├── loading-state.tsx
├── error-state.tsx
├── filter-bar.tsx
└── stat-tile.tsx
```

The `<DataTable>` component takes column defs + data + options and renders a fully-featured table. This is critical: every module's table uses this one component. Variation goes through column defs and options, not through new table implementations.

## `src/lib/` — framework utilities

```
src/lib/
├── api-client.ts              ← fetch wrapper, error handling, Zod parsing
├── query-client.ts            ← QueryClient singleton + default options
├── utils.ts                   ← cn() helper from shadcn, misc utilities
├── env.ts                     ← Zod-validated env vars (do NOT use process.env directly)
└── format.ts                  ← formatDate, formatCurrency, formatNumber
```

## `src/hooks/` — global hooks

Generic hooks unrelated to any specific module:

```
src/hooks/
├── use-debounce.ts
├── use-media-query.ts
├── use-on-click-outside.ts
├── use-local-storage.ts
└── use-mounted.ts
```

Module-specific hooks live in `src/modules/<name>/hooks/`, NOT here.

## `src/stores/` — global Zustand stores

These are stores that genuinely transcend any single module. Most apps have zero or one of these. Examples:

```
src/stores/
├── auth-store.ts              ← current user, session — usually the only one
└── ui-store.ts                ← sidebar collapsed, command palette open, theme
```

If you find yourself adding a third or fourth global store, stop. It probably belongs in a module.

## `src/styles/` — design system files

```
src/styles/
├── globals.css                ← @tailwind directives, CSS custom properties, base resets
└── tokens.ts                  ← TS-typed token exports for use in JS contexts
```

## `src/types/` — global types

Types used across modules. Keep this folder small — most types belong to a specific module.

```
src/types/
├── api.ts                     ← ApiError, ApiResponse<T>, Pagination
└── globals.d.ts               ← global type augmentations
```

## File naming conventions

- **kebab-case for files**: `companies-table.tsx`, `use-companies.ts`
- **PascalCase for React components**: `export function CompaniesTable() { ... }`
- **camelCase for everything else**: `useCompanies`, `getCompanies`, `companyKeys`
- **One default export per page file**: Next.js requires this
- **Named exports everywhere else**: easier to find references, easier to refactor

## Why this structure

- **Modules are bounded**: each feature lives in one folder. New devs can find everything for a feature in one place.
- **Public APIs prevent leaks**: the `index.ts` discipline keeps internal refactors internal.
- **Shared vs. ui split is clear**: `components/ui/` is "atoms" (shadcn), `components/shared/` is "molecules built from atoms used by multiple modules".
- **Tests live next to source**: `companies-table.tsx` + `companies-table.test.tsx` in the same folder. Don't create a parallel `__tests__/` tree.
- **Hooks are colocated with the data they expose**: if `useCompanies` belongs to the `companies` module, keep it there. The `src/hooks/` folder is genuinely-generic only.

## Anti-patterns to avoid

- ❌ A `pages/` folder. Use `app/`. (App Router is the supported default since Next 13.)
- ❌ A `components/` folder at module level that mixes UI primitives with feature components. Split into `ui/` (shadcn) and `shared/` (cross-module composites) at the root.
- ❌ A `services/` folder. Module-specific API code goes in `modules/<name>/api.ts`.
- ❌ A `utils/` god-folder. Specific utilities go in their module; truly-generic ones go in `src/lib/utils.ts`.
- ❌ Index files at every directory level. `index.ts` is for module public APIs only.
- ❌ Type files separated from their domain. `Company` type belongs in `modules/companies/types.ts`, not `src/types/company.ts`.
