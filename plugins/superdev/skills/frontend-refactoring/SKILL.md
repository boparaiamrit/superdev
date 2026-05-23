---
name: frontend-refactoring
description: Use to refactor ONE existing bloated frontend module into the canonical frontend-modular-architecture layout IN A SINGLE ATOMIC CONVERSION. Refuses partial conversions — half-converted modules are worse than untouched. Five strict phases (deep-plan → review gate → behavior snapshot → atomic-execute on feature branch → diff-verify) where conversion-verifier rolls back the entire commit if any behavior changed. Handles wizards split per-step, sub-sub-components moved into parts/<name>/ folders with own Portal primitives, dedicated Zustand stores extracted from useState soup, drawers/modals/popovers wrapped in shadcn Sheet/Dialog/Popover. Dispatches 4 agents (module-conversion-planner, module-behavior-snapshotter, atomic-module-converter, conversion-verifier).
---

# Frontend Refactoring — atomic one-module conversion

The hardest problem in frontend AI work: converting a fat existing module to a sane structure WITHOUT breaking it. This skill solves it by enforcing one rule above all others:

## The Iron Law

```
ONE MODULE PER DISPATCH.
ONE COMMIT PER CONVERSION.
ZERO BEHAVIOR CHANGE.
IF CONVERSION-VERIFIER FINDS DRIFT, THE WHOLE COMMIT REVERTS.

There is no "we'll finish the rest tomorrow" — a half-converted module
breaks every import, every test, every running dev server. That state
MUST NEVER LAND ON A SHARED BRANCH.
```

## When to use

- ✅ A module's structure was flagged by `module-structure-auditor` and needs decomposition
- ✅ Before running `prototype-to-saas` on a prototype with fat files (Phase B.5)
- ✅ User says "this file is too big" / "this wizard is unmaintainable"
- ✅ A 5+ step wizard lives in one file
- ✅ A page exceeds 100 lines OR a component exceeds 200 lines

## When NOT to use

- ❌ Multiple modules at once (one conversion per dispatch, period)
- ❌ Refactoring that intentionally changes behavior (use `frontend-module-builder` + delete old code)
- ❌ Renames-only / formatting-only changes (run codemods directly)
- ❌ Cross-module changes (each module gets its own conversion dispatch)

## How the orchestrator should use this skill

- After `module-structure-auditor` returns P1 findings on a module → dispatch `frontend-refactoring` for that one module
- In `prototype-to-saas` pipeline → run as **Phase B.5** between discovery and rewiring. The prototype's UI must be decomposed before `frontend-rewirer` touches anything (rewiring a fat file just preserves the antipattern with new data wiring)
- User explicitly asks for a refactor → dispatch directly

## The 5 strict phases

```
┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐
│ PHASE 1 — DEEP PLAN     │───▶│ PHASE 2 — REVIEW GATE   │───▶│ PHASE 3 — SNAPSHOT      │
│ module-conversion-      │    │ User confirms plan      │    │ module-behavior-        │
│ planner                 │    │ Optional 3-teammate     │    │ snapshotter             │
│                         │    │ completeness review     │    │                         │
│ EXHAUSTIVE plan:        │    │                         │    │ Playwright records ALL  │
│ every new file (full    │    │ REJECT if plan has any  │    │ behavior: every route,  │
│ path), every split,     │    │ "we'll figure step N    │    │ every click, every      │
│ every store, every      │    │ out later" — vague      │    │ drawer/modal/popover    │
│ Portal, every import    │    │ plans are forbidden     │    │ open/close, every form  │
│ update                  │    │                         │    │ submit                  │
└────────┬────────────────┘    └────────┬────────────────┘    └────────┬────────────────┘
         ▼                              ▼                              ▼
   CONVERSION_PLAN.md             approved-plan.md            baseline/<feature>/
                                                              (screenshots + DOM +
                                                              HARs + console logs)

                                                                       │
                                                                       ▼
                                              ┌─────────────────────────────────────┐
                                              │ PHASE 4 — ATOMIC EXECUTE            │
                                              │ atomic-module-converter             │
                                              │                                     │
                                              │ Single commit on feature branch.    │
                                              │ ALL moves + splits + imports +      │
                                              │ store extractions + Portal wraps    │
                                              │ in ONE pass. No partial state.      │
                                              │                                     │
                                              │ Branch: refactor/<feature>-decompose│
                                              │ Commit msg: refers to CONVERSION_PLAN│
                                              └────────┬────────────────────────────┘
                                                       ▼
                              ┌─────────────────────────────────────────────────┐
                              │ PHASE 5 — VERIFY (no-rollback gate)              │
                              │ conversion-verifier + portal-correctness-auditor │
                              │                                                  │
                              │ Re-run Playwright snapshot. Diff every captured  │
                              │ behavior against baseline. ZERO drift required.  │
                              │                                                  │
                              │ Also runs portal-correctness-auditor to confirm  │
                              │ extracted drawers/modals use shadcn Portal       │
                              │ primitives.                                      │
                              │                                                  │
                              │ Any drift → git reset --hard, re-plan, restart.  │
                              └──────────────────────────────────────────────────┘
```

## Phase 1 — Deep plan (`module-conversion-planner`)

The planner reads the entire module top to bottom and produces `CONVERSION_PLAN.md`. The plan is EXHAUSTIVE — every file the converter will create, move, edit, or delete, with absolute paths.

### Plan format (mandatory)

```markdown
# Conversion plan — companies module — <commit hash>

## Source inventory
- apps/web/src/modules/companies/companies.tsx (1,247 lines, 38 useState, 12 useMemo, contains 8-step create wizard inline)
- apps/web/src/modules/companies/companies-detail.tsx (612 lines)
- apps/web/src/modules/companies/api.ts (clean)
- (no stores/, no hooks/, no parts/ — full restructure required)

## Target structure (every file listed)

### New files to create
- apps/web/src/modules/companies/pages/list-page.tsx (≤ 100 lines)
- apps/web/src/modules/companies/pages/detail-page.tsx
- apps/web/src/modules/companies/pages/new-page.tsx
- apps/web/src/modules/companies/components/companies-table/index.tsx (≤ 200 lines)
- apps/web/src/modules/companies/components/companies-table/columns.tsx
- apps/web/src/modules/companies/components/companies-table/row-actions.tsx
- apps/web/src/modules/companies/components/companies-table/filters.tsx
- apps/web/src/modules/companies/components/companies-table/parts/delete-confirm-dialog/index.tsx
- apps/web/src/modules/companies/components/companies-table/parts/bulk-edit-drawer/index.tsx
- apps/web/src/modules/companies/components/companies-table/parts/bulk-edit-drawer/form.tsx
- apps/web/src/modules/companies/components/companies-table/parts/bulk-edit-drawer/footer.tsx
- apps/web/src/modules/companies/components/create-wizard/index.tsx (orchestrator)
- apps/web/src/modules/companies/components/create-wizard/step-1-basics.tsx
- apps/web/src/modules/companies/components/create-wizard/step-2-contacts.tsx
- apps/web/src/modules/companies/components/create-wizard/step-3-billing.tsx
- apps/web/src/modules/companies/components/create-wizard/step-4-team.tsx
- apps/web/src/modules/companies/components/create-wizard/step-5-integrations.tsx
- apps/web/src/modules/companies/components/create-wizard/step-6-onboarding.tsx
- apps/web/src/modules/companies/components/create-wizard/step-7-billing-method.tsx
- apps/web/src/modules/companies/components/create-wizard/step-8-confirm.tsx
- apps/web/src/modules/companies/components/create-wizard/shared/nav-buttons.tsx
- apps/web/src/modules/companies/components/create-wizard/shared/progress-indicator.tsx
- apps/web/src/modules/companies/stores/companies-store.ts
- apps/web/src/modules/companies/stores/companies-ui-store.ts
- apps/web/src/modules/companies/stores/companies-wizard-store.ts
- apps/web/src/modules/companies/hooks/use-companies.ts
- apps/web/src/modules/companies/hooks/use-create-company.ts
- apps/web/src/modules/companies/hooks/use-update-company.ts
- apps/web/src/modules/companies/hooks/use-delete-company.ts
- apps/web/src/modules/companies/hooks/use-company-form.ts

### Files to DELETE (after content has been migrated)
- apps/web/src/modules/companies/companies.tsx
- apps/web/src/modules/companies/companies-detail.tsx

### State migrations (useState → store)
| Source line | Source state | Target store + property |
|---|---|---|
| companies.tsx:14 | useState([]) for selectedIds | companies-store.ts → selectedIds + toggleSelected + clearSelection |
| companies.tsx:15 | useState('') for searchQuery | companies-store.ts → search + setSearch |
| companies.tsx:23 | useState({}) for filters | companies-store.ts → industryFilter + statusFilter + setFilters |
| companies.tsx:48 | useState(false) for bulkDrawerOpen | companies-ui-store.ts → bulkDrawerOpen + openBulkDrawer + closeBulkDrawer |
| companies.tsx:67 | useState(null) for deleteConfirmFor | companies-ui-store.ts → deleteConfirmFor + askDeleteConfirm + dismissDeleteConfirm |
| companies.tsx:124 | useState(1) for wizardStep | companies-wizard-store.ts → step + next + prev |
| companies.tsx:125-162 | useState(...) × 18 for wizard draft fields | companies-wizard-store.ts → draft + patch
| (full list — every useState accounted for) |

### Portal extractions (raw div → shadcn primitive)
| Source location | Current pattern | Target |
|---|---|---|
| companies.tsx:540 | `<div className="fixed right-0 top-0 z-50">…</div>` (bulk drawer) | components/companies-table/parts/bulk-edit-drawer/index.tsx using `<Sheet>` |
| companies.tsx:720 | `<div className="fixed inset-0 z-50 flex items-center">…</div>` (delete modal) | components/companies-table/parts/delete-confirm-dialog/index.tsx using `<AlertDialog>` |
| companies.tsx:880 | `<div className="absolute top-full z-50">…</div>` (column picker) | components/companies-table/parts/column-customizer-popover/index.tsx using `<Popover>` |

### Import updates required
| File | Current import | New import |
|---|---|---|
| apps/web/src/app/companies/page.tsx:1 | `from '@/modules/companies/companies'` | `from '@/modules/companies/pages/list-page'` |
| apps/web/src/app/companies/[id]/page.tsx:1 | `from '@/modules/companies/companies-detail'` | `from '@/modules/companies/pages/detail-page'` |
| apps/web/src/app/companies/new/page.tsx:1 | `from '@/modules/companies/companies'` (used the wizard inline export) | `from '@/modules/companies/pages/new-page'` |

### Hook extractions
| Source lines | New hook | Notes |
|---|---|---|
| companies.tsx:36-44 (TanStack Query useQuery for list) | hooks/use-companies.ts | Wraps the existing fetcher |
| companies.tsx:78-94 (useMutation for create) | hooks/use-create-company.ts | Includes invalidate ['companies'] |
| companies.tsx:200-232 (useForm + zodResolver) | hooks/use-company-form.ts | Re-export schema from contracts |

### Behavior preservation contract
- All 8 wizard steps preserve their current form fields, validation rules, submit behavior
- Bulk drawer's multi-select count display unchanged
- Delete dialog's destructive-action button color unchanged
- Column customizer's checkbox interactions unchanged
- Keyboard shortcuts (escape closes drawers) unchanged
- URL params for filters unchanged

## Risk areas
- Wizard step 6 (onboarding) has a side-effect that calls 3rd-party SDK on submit — must preserve via use-create-company hook
- Bulk drawer uses a custom `useClickOutside` hook locally — Sheet handles click-outside natively, so we drop the custom hook. Verify behavior unchanged.
- Delete dialog has a 300ms delay before destruction — preserve via mutation's onSuccess setTimeout

## Atomic-execute order (within one commit)
1. Create stores/ (3 files)
2. Create hooks/ (5 files)
3. Create pages/ (3 files) — referencing components that don't exist yet (TS will fail; that's expected mid-commit)
4. Create components/companies-table/ (4 files + parts/)
5. Create components/create-wizard/ (orchestrator + 8 steps + shared)
6. Update apps/web/src/app/companies/*/page.tsx imports
7. Delete companies.tsx + companies-detail.tsx
8. Run typecheck — MUST pass
9. Commit

If typecheck fails at step 8, git reset --hard and redo from a new plan.
```

The plan is the contract. The converter executes EXACTLY what the plan says, in order. Anything the plan doesn't list MUST NOT happen.

### Refuse-to-run conditions for the planner

- ❌ Plan contains "TBD" / "we'll figure out later" / "approximately"
- ❌ Plan has fewer files listed than source useState count requires (e.g., 38 useState mapped to a single store of 4 properties is wrong)
- ❌ Plan doesn't enumerate every Portal extraction
- ❌ Plan doesn't list import updates for every consumer of the old files
- ❌ Plan's atomic-execute order doesn't end with a typecheck step

## Phase 2 — Review gate

The user reads the plan. If high-stakes, dispatch a 3-teammate review:

```
Dispatch 3-teammate plan-completeness review.
Teammate A — pessimist: hunts for what the plan FORGOT (any missing file? any orphan import?)
Teammate B — pragmatist: questions whether each split is actually needed
Teammate C — surgeon: validates the atomic-execute order — would this typecheck mid-commit?

Majority verdict. Plan only proceeds if all three approve.
```

User then types "approve" or "revise" with specific feedback for the planner to incorporate.

## Phase 3 — Behavior snapshot (`module-behavior-snapshotter`)

Before the converter touches a single file, snapshot CURRENT behavior with Playwright. Every route, every interaction, every drawer/modal/popover open/close, every form submit, every keyboard shortcut.

Output: `baseline/<feature>/` directory with:
- Screenshots per route × viewport
- DOM snapshots per route (HTML structure)
- Network HARs per user flow
- Console logs per route
- Interaction trace (sequence of clicks + resulting state)

This baseline IS the source of truth for Phase 5's diff.

## Phase 4 — Atomic execute (`atomic-module-converter`)

Creates a feature branch `refactor/<feature>-decompose` and executes the plan EXACTLY in order. One commit containing ALL file moves, splits, imports, deletions.

**The commit must:**
- Be a single git commit (no intermediate "wip" commits)
- Pass typecheck before being created
- Reference `CONVERSION_PLAN.md` in the commit body
- Touch ONLY files listed in the plan

**The commit must NOT:**
- Land on `main` (always on a feature branch)
- Include unrelated changes ("while I'm here let me fix this lint warning")
- Touch other modules' files (cross-module changes are out of scope)

## Phase 5 — Verify (`conversion-verifier`)

Re-runs the same Playwright snapshot from Phase 3, this time against the converted module. Diffs everything against baseline.

| Check | Pass criteria |
|---|---|
| Per-route screenshot pixel-diff | ≤ 0.5% drift (tighter than design-fidelity-auditor's 1% because this is supposed to be byte-identical) |
| DOM structure | Identical text content; tag names may differ ONLY where a Portal was introduced (raw div → portaled Sheet) |
| Network HAR | Identical request URLs, methods, request bodies (response handling unchanged) |
| Console logs | No new errors / warnings introduced |
| Interaction trace | Same click → same state transition |

Plus, `portal-correctness-auditor` runs on the converted module — every drawer/modal/popover must now be Portal-correct.

### Rollback

If verifier returns REJECT:

```bash
git reset --hard <pre-conversion-sha>
git branch -D refactor/<feature>-decompose
```

The plan re-opens. Phase 1 re-runs with the verifier's findings as input ("on attempt 1, drift was X — adjust plan to preserve Y behavior"). Phase 4 re-executes.

There's no incremental "fix the drift, keep some changes" path. Half-state is the antipattern this skill exists to prevent.

## Agent teams (optional — plan-completeness review)

For complex modules (1000+ line source, 5+ wizard steps, 3+ drawer/modal/popover extractions), the 3-teammate review in Phase 2 dramatically improves outcomes. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

## Reference files

- [`references/conversion-plan-format.md`](references/conversion-plan-format.md) — the exact CONVERSION_PLAN.md template
- [`references/baseline-snapshot-recipes.md`](references/baseline-snapshot-recipes.md) — Playwright patterns for capturing baseline
- [`references/atomic-commit-protocol.md`](references/atomic-commit-protocol.md) — how the converter ensures one atomic commit
- [`references/agent-definitions.md`](references/agent-definitions.md) — dispatch prompts
