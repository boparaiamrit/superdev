# Portal rules

The single rule: **every drawer / modal / popover / menu / tooltip MUST render through a Portal — and the only sanctioned way is to use the shadcn primitive that wraps Radix.**

## The primitives map

| Use case | shadcn primitive | Import |
|---|---|---|
| Modal dialog | `<Dialog>` | `@/components/ui/dialog` |
| Destructive confirm | `<AlertDialog>` | `@/components/ui/alert-dialog` |
| Side drawer / sheet | `<Sheet>` | `@/components/ui/sheet` |
| Popover (rich content) | `<Popover>` | `@/components/ui/popover` |
| Hover card | `<HoverCard>` | `@/components/ui/hover-card` |
| Right-click menu | `<ContextMenu>` | `@/components/ui/context-menu` |
| Kebab / overflow menu | `<DropdownMenu>` | `@/components/ui/dropdown-menu` |
| Menubar (top-level) | `<Menubar>` | `@/components/ui/menubar` |
| Tooltip | `<Tooltip>` | `@/components/ui/tooltip` |
| Select | `<Select>` | `@/components/ui/select` |
| Combobox | `<Command>` + `<Popover>` (shadcn combobox pattern) | both |
| Toast | `<Toaster>` (Sonner) | `@/components/ui/sonner` |
| Date picker | `<Popover>` + `<Calendar>` | both |

## Why Portals matter

Without a Portal, the rendered DOM lives wherever it was declared in the React tree. That means it inherits:

| Inherited from parent | Bug it creates |
|---|---|
| `overflow: hidden` | Drawer / popover gets clipped at parent's edge |
| `transform` (any value, even `translateZ(0)`) | Popover positioned relative to transformed ancestor instead of viewport |
| Stacking context (any z-index'd ancestor) | Modal sits BEHIND sibling elements that have higher z-index |
| `position: relative` ancestors | `position: fixed` calculates wrong |
| Focus traps in parent | Tab cycling doesn't reach modal contents |
| Click-outside handlers in parent | Closing the modal triggers the parent's onClick |

With a Portal, the DOM renders to `document.body`, escaping ALL of the above. The component still gets React events / context / state from its declared location — just the DOM is elsewhere.

Radix (which shadcn wraps) gets this exactly right: Portal + focus trap + scroll lock + `aria-*` attributes + escape handling + click-outside semantics.

## Pattern — drawer in its own folder

```tsx
// components/companies-table/parts/bulk-edit-drawer/index.tsx
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useCompaniesUiStore } from '../../../../stores/companies-ui-store';
import { BulkEditForm } from './form';
import { BulkEditFooter } from './footer';

export function BulkEditDrawer() {
  const open = useCompaniesUiStore((s) => s.bulkDrawerOpen);
  const close = useCompaniesUiStore((s) => s.closeBulkDrawer);

  return (
    <Sheet open={open} onOpenChange={(v) => !v && close()}>
      <SheetContent side="right" className="w-[480px] sm:max-w-full">
        <SheetHeader>
          <SheetTitle>Bulk edit companies</SheetTitle>
        </SheetHeader>
        <BulkEditForm />
        <BulkEditFooter />
      </SheetContent>
    </Sheet>
  );
}
```

Then in the table:

```tsx
// components/companies-table/index.tsx
import { BulkEditDrawer } from './parts/bulk-edit-drawer';

export function CompaniesTable({ rows }: Props) {
  return (
    <>
      {/* table markup */}
      <BulkEditDrawer />
    </>
  );
}
```

The drawer is rendered as a sibling of the table content. React tree-wise it's nested; DOM-wise it's portaled to `document.body`. Stacking context inherited from `document.body` only.

## Pattern — modal confirm

```tsx
// components/companies-table/parts/delete-confirm-dialog/index.tsx
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from '@/components/ui/alert-dialog';
import { useCompaniesUiStore } from '../../../../stores/companies-ui-store';
import { useDeleteCompany } from '../../../../hooks/use-delete-company';

export function DeleteConfirmDialog() {
  const targetId = useCompaniesUiStore((s) => s.deleteConfirmFor);
  const dismiss = useCompaniesUiStore((s) => s.dismissDeleteConfirm);
  const del = useDeleteCompany();

  return (
    <AlertDialog open={!!targetId} onOpenChange={(v) => !v && dismiss()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this company?</AlertDialogTitle>
          <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={dismiss}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={() => targetId && del.mutate(targetId, { onSuccess: dismiss })}>
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
```

## Pattern — popover trigger + rich content

```tsx
// components/companies-table/parts/column-customizer-popover/index.tsx
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { ColumnsCheckboxList } from './columns-checkbox-list';

export function ColumnCustomizerPopover() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline">Columns</Button>
      </PopoverTrigger>
      <PopoverContent className="w-64" align="end">
        <ColumnsCheckboxList />
      </PopoverContent>
    </Popover>
  );
}
```

## Anti-patterns (will be flagged by portal-correctness-auditor)

| 🚫 | Why it's wrong |
|---|---|
| `<div className="fixed inset-0 z-50">…</div>` | Not portaled — z-index war + parent transforms break positioning |
| `{isOpen && <div className="absolute ...">…</div>}` | Same |
| Native `<dialog>` element | Doesn't theme cleanly, accessibility is partial, no focus trap |
| `import * as Dialog from '@radix-ui/react-dialog'` (inside module code) | Bypasses shadcn's wrapped styles; loses Tailwind theming consistency |
| Custom hook `useModal()` that renders inline | Not portaled |
| Toast solutions other than the project's `<Toaster>` | Two toast systems = stacking conflicts |
| `title="…"` for tooltips on non-trivial content | Native tooltip can't style; replace with `<Tooltip>` |

## Edge cases

### A custom floating UI is genuinely needed (e.g., a connected-line annotation)

OK, but use `createPortal` from `react-dom` directly + a portal root in `app/layout.tsx`:

```tsx
import { createPortal } from 'react-dom';

export function Annotation({ children }) {
  if (typeof window === 'undefined') return null;
  return createPortal(children, document.body);
}
```

Document why (one comment line) so portal-correctness-auditor's manual review marks it as P3 informational rather than P1 violation.

### Nested portals (modal that opens another modal)

Fine — each `<Dialog>` instance creates its own Portal. Radix handles z-index ordering correctly (later = on top).

### SSR

Shadcn primitives are SSR-safe (they no-op rendering on the server and hydrate on the client). Don't add your own `typeof window !== 'undefined'` guards around `<Dialog>` etc.
