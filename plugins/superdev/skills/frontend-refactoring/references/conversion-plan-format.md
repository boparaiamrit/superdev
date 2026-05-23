# CONVERSION_PLAN.md format

Mandatory format. The atomic-module-converter parses this — missing sections or vague entries cause the converter to refuse.

```markdown
# Conversion plan — <feature> — <pre-conversion commit hash>

STATUS: DRAFT  (changes to APPROVED after Phase 2 review gate)

## Source inventory
- <path> (<N> lines, <M> useState, <K> useMemo, <L> useCallback, contains <description>)
- (... every existing module file ...)

## Target structure — every new file listed

### Files to CREATE
- apps/web/src/modules/<feature>/pages/list-page.tsx
- apps/web/src/modules/<feature>/pages/detail-page.tsx
- apps/web/src/modules/<feature>/components/<feature>-table/index.tsx
- apps/web/src/modules/<feature>/components/<feature>-table/columns.tsx
- apps/web/src/modules/<feature>/components/<feature>-table/parts/delete-confirm-dialog/index.tsx
- apps/web/src/modules/<feature>/stores/<feature>-store.ts
- apps/web/src/modules/<feature>/stores/<feature>-ui-store.ts
- apps/web/src/modules/<feature>/stores/<feature>-wizard-store.ts
- apps/web/src/modules/<feature>/hooks/use-<feature>.ts
- (... every new file with full path ...)

### Files to DELETE
- apps/web/src/modules/<feature>/<old-fat-file-1>.tsx
- apps/web/src/modules/<feature>/<old-fat-file-2>.tsx

### Files to MOVE (rename, no content change)
- apps/web/src/modules/<feature>/api.ts (no change — clean already)
- apps/web/src/modules/<feature>/types.ts → apps/web/src/modules/<feature>/types.ts (kept in place)

## State migrations — every useState in source

| Source file:line | Source state | Target store | Target property | Notes |
|---|---|---|---|---|
| <fat-file>.tsx:14 | useState([]) for selectedIds | stores/<feature>-store.ts | selectedIds + toggleSelected + clearSelection | |
| <fat-file>.tsx:15 | useState('') for searchQuery | stores/<feature>-store.ts | search + setSearch | |
| <fat-file>.tsx:48 | useState(false) for bulkDrawerOpen | stores/<feature>-ui-store.ts | bulkDrawerOpen + openBulkDrawer + closeBulkDrawer | |
| <fat-file>.tsx:124 | useState(1) for wizardStep | stores/<feature>-wizard-store.ts | step + next + prev + setStep | |
| <fat-file>.tsx:200 | useState(false) for cardExpanded | KEEP as useState in card/index.tsx | (truly local; only this card consumes) |
| ... (every useState must appear) |

## Portal extractions — every drawer/modal/popover

| Source file:line | Current pattern | Target file | Target primitive |
|---|---|---|---|
| <fat-file>.tsx:540 | `<div className="fixed right-0 top-0 z-50">` | components/<feature>-table/parts/bulk-edit-drawer/index.tsx | `<Sheet>` from @/components/ui/sheet |
| <fat-file>.tsx:720 | `<div className="fixed inset-0 z-50 flex">` (delete confirm) | components/<feature>-table/parts/delete-confirm-dialog/index.tsx | `<AlertDialog>` from @/components/ui/alert-dialog |
| <fat-file>.tsx:880 | `<div className="absolute top-full z-50">` (column picker) | components/<feature>-table/parts/column-customizer-popover/index.tsx | `<Popover>` from @/components/ui/popover |

## Wizard split — per-step files

(Skip section if no wizard)

| Step # | Step file | Form fields collected | Validation source |
|---|---|---|---|
| 1 | components/create-wizard/step-1-basics.tsx | name, industry, website | Zod from @<scope>/contracts/<feature> companyCreateBasicsSchema |
| 2 | components/create-wizard/step-2-contacts.tsx | primaryContact{name,email}, billingContact{name,email} | companyCreateContactsSchema |
| 3 | components/create-wizard/step-3-billing.tsx | plan, seats, billingCycle | companyCreateBillingSchema |
| ... |

Plus:
- components/create-wizard/index.tsx (orchestrator: reads step from store, renders step component, handles "Next/Prev" + final submit)
- components/create-wizard/shared/nav-buttons.tsx (Next / Back / Submit buttons)
- components/create-wizard/shared/progress-indicator.tsx (1/8 etc.)

## Hook extractions

| Source file:line | New hook | What it wraps |
|---|---|---|
| <fat-file>.tsx:36-44 | hooks/use-<feature>.ts | TanStack useQuery({ queryKey: ['<feature>'], queryFn: get<Feature>List }) |
| <fat-file>.tsx:78-94 | hooks/use-create-<feature>.ts | useMutation + invalidate ['<feature>'] |
| <fat-file>.tsx:96-112 | hooks/use-update-<feature>.ts | useMutation + optimistic update |
| <fat-file>.tsx:200-232 | hooks/use-<feature>-form.ts | useForm + zodResolver(companyEditSchema) |

## Import updates — every external consumer

| Consumer file:line | Current import | New import |
|---|---|---|
| apps/web/src/app/<feature>/page.tsx:1 | `import { CompaniesPage } from '@/modules/companies/companies'` | `import { CompaniesListPage } from '@/modules/companies/pages/list-page'` |
| apps/web/src/app/<feature>/[id]/page.tsx:1 | `from '@/modules/companies/companies-detail'` | `from '@/modules/companies/pages/detail-page'` |
| apps/web/src/app/<feature>/new/page.tsx:1 | (uses old wizard export) | `from '@/modules/companies/pages/new-page'` |
| (... every external consumer that imports from the module ...) |

## Behavior preservation contract

Things the conversion MUST NOT change. The verifier diffs against baseline; these are the items most likely to drift if the converter is sloppy:

- Bulk drawer width: 480px (hardcoded in source — Sheet's default 384px would be wrong)
- Delete dialog: 300ms artificial delay before mutation fires (preserve via setTimeout in handler)
- Wizard step 6: side-effect call to 3rd-party SDK (preserve in use-create-company.ts onSuccess)
- Column popover: width 256px, aligned to right of trigger
- Keyboard: Escape closes drawer + modal + popover (Sheet/Dialog/Popover do this natively, verify)
- URL filter params: ?industry=X&status=Y preserved across the conversion

## Risk areas

- <fat-file>.tsx:412 uses a custom `useClickOutside` hook locally — Sheet handles click-outside natively. Verify behavior identical (no double-close, no stale-listener issues).
- <fat-file>.tsx:622 has an effect that fires on EVERY render (no dep array) — investigate whether it's intentional before the move; if intentional, preserve carefully in new location.
- Form values in step 4 are stored in a ref (`useRef`), not state — likely a performance dodge. Decide if the wizard store should hold these, or keep ref pattern.

## Atomic-execute order

The converter executes in this order (dependency-aware so typecheck passes at the end):

1. Stores (no dependencies)
2. Hooks (depend on stores + existing api.ts)
3. Leaf components (parts/<name>/index.tsx) — depend on stores + UI primitives
4. Mid-level components (<feature>-table/index.tsx, etc.) — depend on parts/
5. Wizard step files — depend on stores
6. Wizard orchestrator (create-wizard/index.tsx) — depends on steps
7. Pages — depend on everything above
8. Update external consumer imports
9. Delete old fat files
10. Typecheck — MUST pass before commit

## Estimated stats

- Source: <N> files, <total> lines
- Target: <M> files, <total> lines
- Net change: +<delta> files, ~equal lines (decomposition shouldn't add functionality)
- useState eliminated from components: <N> (all migrated to stores)
- Portal violations fixed: <N>
- Files now under size limit (page ≤ 100 / component ≤ 200): <N>/<N>
```

## Gates on the plan itself

The planner refuses to produce / the converter refuses to execute if:

- Any section is missing
- Any table is empty (when the corresponding source pattern exists)
- Any entry contains "TBD" / "approximately" / "we'll figure out later"
- "State migrations" table has fewer rows than the source's useState count
- "Import updates" table is missing any consumer found via grep
- "Atomic-execute order" doesn't end with typecheck
