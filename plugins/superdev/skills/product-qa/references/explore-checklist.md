# Explore checklist

Read this in explore mode: the edge categories for `qa-flow-tester`, the consistency checks for `qa-consistency-checker`, the performance table for `qa-performance-prober` and the `QA_REPORT.md` format. Explore mode looks for what the committed suites and the gate's matrix do not, so it does not re-test what a suite already proves (rule QA-8). `product-audit` uses the same edge categories in its inventory and score modes.

## Edge categories

A route or form is tested on the categories that apply to it, and the report lists only those cells.

| Category | What to do | Expect | Applies to |
|---|---|---|---|
| Empty | a workspace with no rows in the module | an empty state with the next action, never headers alone | lists |
| One item | exactly one row | the list and the detail page lay out correctly | lists, details |
| Large data | 1,000 rows or more, from a seeder written for QA that uses the module's factory (`navree make:factory`), or through the app's own routes, where the per-IP limit of 600 requests a minute applies: wait for `Retry-After` (rule QA-3), or use a seeder | one page of rows at a time (Navree UI tables show 25 by default); filters answer without a freeze | lists |
| Slow network | emulate a slow connection through the browser's network conditions; a fixed delay on every request is not a throttle | a visible loading state and no double actions | every page |
| Server error | answer the page's request with a 500 in the Navree error shape (`code` `internal_error`) | a message and a way to retry, never an endless spinner | every page |
| Validation errors | submit each form empty and with invalid values | errors beside the fields: 422 from a Navree UI form, 400 `validation_failed` from the API | forms |
| Double submit | click submit several times quickly | one record and one request | forms, actions |
| Stale data | change a record in one tab, then act on it in a second tab | live regions update; otherwise a stale write is refused with a reason or applies to current data, and never reports success while storing nothing | details, edits |
| Long text | 500 characters in each text field | no overflow and no broken row; the full value is reachable | lists, details |
| Special characters | emoji, Gurmukhi and Devanagari text (ਗੁਰਪ੍ਰੀਤ ਕੌਰ, मीरा शर्मा), quotes, `<script>alert(1)</script>` | stored and shown as typed; the script shows as text | forms, lists |
| Boundary numbers | 0, a negative number, ₹ 99,99,99,999 | refused, or shown in full as ₹ 99,99,99,999; never rounded or shown as `NaN` | money and quantity fields |
| Back and forward | move through three pages and back with the browser buttons | Navree UI tables return to their sort, filter and page, because that state lives in the URL; no stale page | every page |
| Keyboard only | Tab through the page; press Escape in dialogs | logical order, visible focus, focus kept inside an open dialog | every page |
| 390 px | the checks of rule QA-6 | as in QA-6 | every page |

## Consistency checks

`qa-consistency-checker` reads the screenshots and the source. On Navree UI, screens are made of components (rule NUI-1), so look for one concept built in different ways; on Next.js, look for components duplicated across modules.

1. One component per concept: a table, a page header, an empty state, a confirmation dialog.
2. One dialog width scale.
3. One validation timing: errors appear on submit or on blur, not on both.
4. One feedback pattern after a write: a toast, an inline message or a redirect with a message.
5. Search inputs are debounced and filter on the server.
6. One wording for confirming a destructive action.
7. One heading style per level, and one main heading per page.
8. Every list has an empty state and a loading state.

A pattern repeated across modules is one `Note` finding that lists the places, not one finding per module.

## Performance

`qa-performance-prober` runs alone on an idle app and takes the median of three samples per route. For counting queries per request, check `navree-database` and `navree-performance`. A main route is one used by an acceptance criterion of `EXECUTION_PLAN.md`.

| Measure | Limit | If over |
|---|---|---|
| Largest contentful paint | at most 2.5 s | `Major` on a main route, otherwise `Minor` |
| Cumulative layout shift | at most 0.1 | `Minor` |
| Queries for a list request | the same count for 1 row and for 50 rows | `Major` on a main route, otherwise `Minor` |
| A query without a limit on a workspace table | none | `Major` on a main route, otherwise `Minor` |
| A list filtered or sorted in the browser | none over 500 rows | `Major` on a main route, otherwise `Minor` |
| Script a Next.js route loads on a cold visit (bytes transferred, from the browser) | at most 200 KB | `Major` on a main route over 500 KB, otherwise `Minor` |

## QA_REPORT.md

The main agent writes it from the agents' reports. Findings take ids `Q-n`; the severity scale and the finding fields are in [artifacts.md](../../superdev-build/references/artifacts.md). The fix order puts exposure first: a `Major` finding on a page everyone opens comes before a `Major` finding on a screen few people open.

```markdown
# QA Report

Commit: a1b2c3d
Date: 2026-11-24

## Findings

| ID | Severity | Module | Where | What | Expected | Evidence | Owner |
|---|---|---|---|---|---|---|---|
| Q-1 | Major | invoices | `/invoices` with 1,000 invoices | the list filters in the browser and typing in the search box blocks the page for 2 s | filtering on the server through `search` and `filter[..]` | qa/qa-flow-tester/invoices/large-data.trace.zip | nextjs-module-builder |
| Q-2 | Minor | customers | `/customers` with no rows | the empty state shows the column headers and no next action | an empty state with a "New customer" button | qa/qa-flow-tester/customers/empty.png | navree-ui-screen-builder |

## Fix order

1. Q-1: the filter blocks the main list of the product.
2. Q-2: a wording and layout fix on one screen.
```
