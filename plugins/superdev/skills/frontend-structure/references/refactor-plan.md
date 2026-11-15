# Refactor plan

`refactor-planner` writes `refactor/<module>/PLAN.md` for one oversized Next.js module, from the
template below, and checks it against the list at the end before the operator sees it. The main
agent executes it exactly; anything the plan does not list does not happen (rule FS-5). Paths start
from `web/`.

## Template

```markdown
# Refactor plan: invoices

Status: DRAFT

## Source

Commit: <id of the commit the plan and the baseline are made on>

- modules/invoices/invoices.tsx (<n> lines; <n> state hooks; contains <what>)
- modules/invoices/invoice-detail.tsx (<n> lines)
- modules/invoices/api.ts (<n> lines)

## Files

Create:
- modules/invoices/components/invoices-page.tsx
- modules/invoices/components/invoices-table/index.tsx
- modules/invoices/components/invoices-table/columns.tsx
- modules/invoices/components/send-invoice-dialog/index.tsx
- modules/invoices/components/invoice-form/index.tsx
- modules/invoices/components/invoice-form/step-1-customer.tsx
- modules/invoices/hooks/use-invoices.ts

Move (path changes, content does not):
- <old path> to <new path>

Delete (after its content has moved):
- modules/invoices/invoices.tsx

## State moves

| Source (file:line) | State | Goes to |
|---|---|---|
| invoices.tsx:14 | selected row ids | module store, `selectedIds` |
| invoices.tsx:48 | send dialog open | stays in `send-invoice-dialog/index.tsx` (only it reads it) |

## Consumer imports

| Consumer (file:line) | Old import | New import |
|---|---|---|
| app/(app)/w/[workspace]/invoices/page.tsx:1 | `@/modules/invoices/invoices` | `@/modules/invoices` |

## Behaviour to keep

- Widths, delays and animations the source hard-codes (for example the send dialog's 480 px width)
- Keyboard shortcuts (Escape closes the dialog and the drawer)
- URL parameters of the list (`?status=sent&customer=<id>`)
- Side effects on submit (calls, events, redirects)

## Order

1. <module store, if the plan creates one>
2. hooks
3. overlay folders, then component folders
4. step files, then the step coordinator
5. screens (`<screen>-page.tsx`), then `index.ts`
6. consumer imports in route files and other modules
7. delete the old files
8. `pnpm run typecheck`

## Risks

- <file:line>: <what could change behaviour when this code moves, and how the plan keeps it>
```

Sample names are a neutral invoicing product; replace them with the module's. The order puts each
piece after what it imports, so the type check passes at the end; the last line is always
`pnpm run typecheck`.

## Status line

`Status: DRAFT` until the operator agrees. Then the main agent replaces the whole line with
`Status: AGREED by <name> on <YYYY-MM-DD>` (for example
`Status: AGREED by Meera Sharma on 2026-11-20`). The line carries nothing else, so a check can match
it exactly.

## Checks before the operator sees it

The planner revises the plan, and does not show it to the operator, while any of these holds:

- A section is missing, or a table is empty although the source has that kind of thing.
- The text contains `TBD`, "approximately" or "later".
- A piece of state in the source (state hook, context, ref, effect with no dependency list) has no
  row under `## State moves`, including the ones that stay where they are.
- A file that imports from the module is not under `## Consumer imports`; the list comes from a
  search of `web/`, not from memory.
- An overlay in the source (a fixed or absolutely positioned panel, a modal) has no folder under
  `## Files`.
- A page file would exceed 100 lines or a component file 200 (rule FS-2).
- `## Behaviour to keep` is empty, or `## Order` does not end with `pnpm run typecheck`.
