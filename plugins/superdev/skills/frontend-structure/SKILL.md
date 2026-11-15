---
name: frontend-structure
description: Use when laying out or auditing a module of a Next.js front end on a Navree API, or when one oversized Next.js module must be split without changing what it does. Gives the module layout, size limits and the one-module, one-commit refactor checked before and after.
---

# Front-end structure

This skill sets how the modules of a Next.js front end are laid out under `web/`, how large a file
may grow, and how one oversized module is split without changing what it does. It applies only when
`STACK.md` has `front_end: next`; Navree UI screens have no client modules to lay out.
[design-to-nextjs](../design-to-nextjs/SKILL.md) uses it for every new module,
[prototype-to-navree](../prototype-to-navree/SKILL.md) uses it before a prototype module is rewired,
and the operator can ask for it on any module that has grown too large.

## Module layout

Under `web/` (the `web_dir` of `STACK.md`):

```text
web/
  app/(app)/w/[workspace]/invoices/page.tsx   a route file: it composes and does nothing else
  modules/invoices/
    index.ts                the only file other modules and route files import from
    components/
      invoices-page.tsx     the screen the route file renders
      invoices-table/       a component with parts is a folder: index.tsx, columns.tsx, filters.tsx
      invoice-form/         index.tsx coordinates the steps; one file per step (step-1-customer.tsx)
      send-invoice-dialog/  an overlay: its own folder, built from the kit's primitives
    hooks/                  use-invoices.ts, use-send-invoice.ts: data access over the generated client
  components/               shared by two or more modules (page header, empty state)
  components/ui/            the kit's primitives: vendored, not module code
```

- A route file in `app/` is a thin entry: it imports a screen from the module's `index.ts` and
  passes the route parameters. The `app/(app)/w/[workspace]/` tree is the SaaS kit's; `--ui next`
  without the kit has no workspace segment (a product with workspaces takes the kit, rule NX-6).
- Hooks hold data access. Types come from the generated schema (rule NX-2); a module has no file of
  hand-written response shapes.
- Other modules and route files import a module only through its `index.ts`; inside the module,
  imports are relative.
- A module of one screen and one component keeps `components/`, `hooks/` and `index.ts`. Add the
  other folders when it gains a second screen, a form with steps or an overlay.
- Route files and screens stay server components while they only fetch and compose; `'use client'`
  goes on the leaf that needs state or events. Which of the kit's helpers need a client component is
  in `navree-frontend-next`.
- Where state lives is rule NX-7 in `design-to-nextjs`; it has one home there.

## Limits

| What | Limit | Over the limit |
|---|---|---|
| A page file: a route's `page.tsx` or a module's `<screen>-page.tsx` | 100 lines | Split it before more code goes in (FS-2) |
| A component file | 200 lines | Move parts into the component's own folder (FS-2) |
| A form with three or more steps | One file per step | Each step owns its fields and checks (FS-3) |
| An overlay: dialog, sheet, popover or menu | One folder each | Build it from the kit's primitive (FS-4) |

The kit's overlay primitives render in a portal, so a parent's `overflow` or stacking context cannot
clip them; a hand-made fixed or absolutely positioned panel can be.

## Refactoring one module

A refactor changes the structure of one module and nothing it does. Before starting, check that the
working tree is clean, that the current branch is not the default branch and that
`pnpm run typecheck` passes.

1. `refactor-planner` reads the whole module and writes `refactor/<module>/PLAN.md` per
   [refactor-plan](references/refactor-plan.md), with `Status: DRAFT` and the commit it was planned
   on.
2. The operator reads the plan. When they agree, the main agent replaces the status line with
   `Status: AGREED by <name> on <YYYY-MM-DD>` (rule BLD-6). Nothing in the module changes before
   that line exists.
3. `visual-diff-auditor` in `baseline` mode (target `refactor`) captures screenshots, page text,
   requests and console output for every route of the module into `refactor/<module>/baseline/`, on
   data from `navree migrate:fresh --seed` at realistic volume (rule FS-6).
4. The main agent confirms the current commit equals the plan's `Commit:` line (otherwise the plan
   is stale: go back to step 1), creates branch `refactor/<module>`, executes the plan in its order
   without intermediate commits, runs `pnpm run typecheck` (it must pass) and makes one commit (rule
   FS-8).
5. `visual-diff-auditor` in `compare` mode, on the same data, widths and colour mode. On `PASS` it
   writes `refactor/<module>/VERIFIED.md` and the branch is ready to merge. Otherwise copy the
   compare evidence to `refactor/<module>-rejected-<n>/`, reset the branch to the commit recorded in
   the plan and re-plan with the differences as input (rule FS-7).

## Checks

`module-structure-auditor` runs after each module's screens are built (step 6.5 of the build, with
`out_dir: audit`) and after a refactor. It checks rules FS-1 to FS-4, NX-7 and NX-8 and writes
`<out_dir>/module-structure-auditor.md`. It rates findings on the one scale in
[artifact formats](../superdev-build/references/artifacts.md), where a structure finding is
usually `Minor`. Whatever its severity, a structure finding is fixed before the module's commit
(step 6.7): it is cheap to fix then and expensive later.

## Rules

- **FS-1** A route file only composes: no business logic, no inline column definitions, no form
  state, no client-side filtering or sorting.
- **FS-2** A page file is at most 100 lines and a component file at most 200; a longer one is split
  before more code goes in.
- **FS-3** A form with three or more steps has one file per step, each owning its fields and checks.
- **FS-4** Overlays are built from the kit's primitives, one folder each; there is no hand-made
  fixed or absolutely positioned overlay.
- **FS-5** One module per refactor, one commit, no change in behaviour. The plan lists every file
  created, moved or deleted, every state move and every consumer import, ends with the type check,
  and contains no "TBD"; the plan is followed exactly.
- **FS-6** The baseline is taken before any change, on seeded data at realistic volume; timestamps,
  ids and animations are masked.
- **FS-7** A refactor that changes a screen beyond the drift threshold (rule PRE-3 of
  [design-preservation](../design-preservation/SKILL.md), measured as
  [drift-check](../design-preservation/references/drift-check.md) describes), changes page text or requests,
  or adds a console error is reverted whole. The evidence is saved first; there is no partial keep.
- **FS-8** A refactor commit contains nothing else: no other module, no dependency bump, no
  lint-only change, no test rewrite.

State ownership for Next.js is rule NX-7 (one home); this skill links to it.

## Reference files

| File | Read when |
|---|---|
| [references/refactor-plan.md](references/refactor-plan.md) | `refactor-planner` writes a plan, and before the operator is shown one |
