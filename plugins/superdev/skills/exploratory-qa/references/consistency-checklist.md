# Consistency Checklist (Phase 4)

What `qa-consistency-checker` audits across modules. Each section has a grep recipe and severity guidance.

## Visual consistency

### Button sizing on equivalent actions

```bash
# Inventory every <Button> across modules
grep -rEn '<Button[^>]*size="([^"]+)"' apps/web/src/modules --include="*.tsx" \
  | sed -E 's/.*size="([^"]+)".*/\1/' | sort | uniq -c

# Per-module breakdown
for dir in apps/web/src/modules/*/; do
  feature=$(basename "$dir")
  echo "=== $feature ==="
  grep -rEhn '<Button[^>]*' "$dir" --include="*.tsx" \
    | grep -oE 'size="[^"]*"|<Button>' | sort | uniq -c
done
```

Compare primary form-submit buttons across modules. If 3 modules use `default` and 1 uses `lg`, the outlier is a finding.

Severity guidance:
- Different sizes for the same semantic action → Medium
- Destructive actions using different variants → Medium

### Heading hierarchy

```bash
# h1 / h2 patterns across module pages
grep -rEn '<h[12]' apps/web/src/modules apps/web/src/app --include="*.tsx" \
  | grep -oE 'className="[^"]*"' \
  | sort | uniq -c | sort -rn
```

Severity:
- Page titles use different size classes (`text-2xl` vs `text-3xl` for h1) → Medium
- Some pages have no h1 → High (a11y + SEO)
- Section headings inconsistent (`<h2>` vs `<h3>` vs styled `<div>`) → Medium

Refactor flag: extract `<PageHeader title actions>` shared component.

### Card / panel padding

```bash
grep -rEn 'CardContent\|className="[^"]*p-\d' apps/web/src/modules --include="*.tsx" \
  | grep -oE 'p-\d+|px-\d+ py-\d+' | sort | uniq -c
```

Severity:
- Multiple padding patterns on Card content → Low (consistency polish)
- Page-level padding differs (`p-4` vs `p-6` vs `p-8`) → Medium

## Structural consistency

### Data table implementations

Find every list-view component:

```bash
grep -rln "useReactTable\|<Table>" apps/web/src/modules --include="*.tsx"
```

For each candidate, count lines and compare structure. The pattern to find:

```bash
# Lines in each module's "list table" / "data table"
find apps/web/src/modules -name "*.tsx" -path "*list*" -o -name "*table*" \
  | xargs wc -l | sort -n | tail -20
```

If 3+ modules each have ~150-line list-table files, that's a refactor candidate.

Refactor recommendation template:
- **Title:** DataTable duplicated across N modules
- **Estimated savings:** ~total_lines × 0.7 (after extracting generic, leaving per-feature column defs)
- **Suggested location:** `apps/web/src/components/shared/data-table/`
- **Migration risk:** Low (similar structure) / Medium (custom row-action menus) / High (very different implementations)

### Empty states

```bash
# Module-level empty state implementations
grep -rln "EmptyState\|empty.*state\|no .* yet" apps/web/src/modules --include="*.tsx"

# Components named EmptyState
grep -rln "function EmptyState\|export.*EmptyState" apps/web/src --include="*.tsx"
```

Findings:
- Some modules have empty states, others don't → High (missing) per module
- Each module has its own `<EmptyState>` component → Refactor (extract to `shared/`)

### Loading skeletons

```bash
grep -rln "Skeleton\|animate-pulse" apps/web/src/modules --include="*.tsx"
```

For each list page identified in Phase 2, confirm a skeleton renders during `isLoading`. Modules that show a spinner or nothing → Medium finding per module.

### Confirm-delete dialogs

```bash
grep -rln -E "confirm.*delete|are you sure|cannot be undone" apps/web/src/modules --include="*.tsx" -i
```

For each, capture:
- Wording of the question
- Button labels (Delete / Confirm / Yes)
- Whether it requires type-the-name to confirm

If 3+ variations exist → Refactor recommendation: `<ConfirmDestructiveAction>` shared component.

### Form patterns

```bash
# Every <Form> usage
grep -rln "useForm(\|<Form\b" apps/web/src/modules --include="*.tsx"
```

For each form file, inspect:
- **Validation timing:** `mode: 'onBlur' | 'onChange' | 'onSubmit'` in `useForm({...})`
- **Error display location:** `<FormMessage>` under each field? Or `<Alert>` at top? Or both?
- **Submit button placement** in JSX (last child vs first)
- **Submit button label:** "Save" vs "Create" vs "Submit" vs "Done"
- **Cancel pattern:** "Cancel" ghost / "Close" link / no cancel

Findings:
- Validation mode varies → Medium
- Submit button label inconsistent → Low (style)

## Layout consistency

### Z-index audit

```bash
grep -rEn 'z-(\d+|\[\d+\])|zIndex' apps/web/src --include="*.tsx" --include="*.ts"
```

Build a table:

| Value | File:line | Element |
|---|---|---|
| z-10 | sidebar.tsx:42 | sticky header |
| z-50 | dropdown-menu.tsx:18 | dropdown content |
| z-[100] | toast.tsx:8 | toast |
| z-[999] | dialog.tsx:34 | dialog backdrop |

Severity:
- Random values (`z-[999]`, `z-50`, `z-10`) without a defined scale → Medium
- Specific overlap bugs from Phase 2/3 observations → High (the bug) + Refactor (introduce scale)

Refactor: define semantic z-scale in `tailwind.config.ts`:
```ts
zIndex: {
  dropdown: 30,
  sticky: 40,
  modal: 50,
  popover: 60,
  toast: 70,
}
```

### Sidebar / navigation consistency

```bash
# Sidebar implementation count
grep -rln '<Sidebar\b\|<aside\b' apps/web/src --include="*.tsx"
```

Expected: exactly 1 file with `<Sidebar>` from `@/components/ui/sidebar` (the AppSidebar component). Any other file with `<aside>` is a leftover hand-rolled sidebar.

Severity:
- Hand-rolled sidebar still present → High (violates shadcn-everywhere commitment; ui-auditor should also catch)

### Modal / dialog widths

```bash
grep -rEn '<DialogContent[^>]*className' apps/web/src/modules --include="*.tsx" \
  | grep -oE 'max-w-\S+|w-\[\S+\]' | sort | uniq -c
```

Severity:
- More than ~3 distinct width classes → Medium (introduce dialog-size scale)

## Behavioral consistency

### Toast positions

```bash
grep -rn "Toaster\|<Sonner" apps/web/src --include="*.tsx"
```

If multiple toast libraries exist (sonner + react-hot-toast) → High (duplicates).

### Mutation success patterns

For each mutation file:

```bash
grep -rA15 "onSuccess:" apps/web/src/modules --include="*.tsx" \
  | grep -A1 "onSuccess\|toast"
```

Check:
- Every successful mutation shows a toast?
- Wording style (verb past tense vs present tense)?
- Cache invalidation pattern consistent?

Severity:
- Some mutations silently succeed (no user feedback) → Medium
- Wording wildly inconsistent → Low

### Filter input debouncing

```bash
grep -rn "debounce\|useDebounce\|onChange={(e) => set" apps/web/src/modules --include="*.tsx" \
  | head -30
```

For every list-page filter input, check whether it debounces. If not, and the filter triggers a network request, that's a finding (every keystroke fires API).

## Output: QA_CONSISTENCY.md structure

```markdown
# QA Consistency Report

## Summary

(counts)

## Visual

- V-1, V-2, ...

## Structural / Refactor

- R-1, R-2, ...

## Layout

- L-1, L-2, ...

## Behavioral

- B-1, B-2, ...

## Z-index audit

- Z-1: scale violations
- Z-2: observed conflicts

## Top refactor candidates by impact

1. DataTable (saves ~400 lines, low risk)
2. ConfirmDeleteDialog (saves ~150 lines, low risk)
3. PageHeader (saves ~120 lines, very low risk)
4. EmptyState (saves ~200 lines, low risk)
5. useListQuery hook (saves ~250 lines, medium risk)
```
