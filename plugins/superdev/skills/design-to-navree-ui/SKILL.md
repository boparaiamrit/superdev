---
name: design-to-navree-ui
description: Use when a design (HTML or CSS mock-up, design-tool export, screenshots, or a design digest) must become Navree UI screens, or when a Navree UI screen is built or changed at step 6 of a superdev build. Maps the design onto Navree UI components, puts its tokens into a theme, applies the gap rule when something is missing, and proves each screen in a browser.
---

# Design to Navree UI

This skill turns a design into Navree UI screens and proves them. Navree UI draws every page on
the server from Rust components; page state lives on the server and in the URL. Navree's own
`navree-design-to-ui` skill is the procedure for carrying a design into components. This skill
fits that procedure into the steps of a superdev build, adds the contract, the gap rule and the
browser proof, and owns the rules NUI-1 to NUI-13. Without a design, skip `navree-design-to-ui`
and build from `navree-ui`; every rule here still applies. A Next.js front end uses
[design-to-nextjs](../design-to-nextjs/SKILL.md) instead.

## Navree skills to read

Step 1 installed them into the app (`.claude/skills/`, and `.agents/skills/` for Codex). Read the
installed copies: they match the app's Navree version.

- `navree-design-to-ui`: the procedure for a design, in phases 0 Intake, 1 Inventory, 2 Tokens,
  3 Mapping, 4 Reconcile, 5 Build and 6 Verify, with three owner stop points and its work in a
  `design/` folder. Read it first when there is a design.
- `navree-ui`: the shell, page routes, forms, `DataTable`, regions, themes and page tests. Read it
  before the first screen, and again for every gap.
- `navree-helm`: the staff panel at `/admin` (rule NUI-9).
- `navree-i18n`: the words of a page in the reader's language.
- `navree-browser-testing`: browser tests with the navree-browser crate (Chrome over CDP).
- `navree-native`: only when the operator asks for Navree Native, a preview behind
  `ui-native-preview` that may change in a minor release.

## How superdev runs navree-design-to-ui

Each phase runs at one superdev step, and its result is recorded where the last column says.

| Phase | Superdev step | What superdev adds | Recorded in |
|---|---|---|---|
| 0 Intake | step 2 | `DESIGN_DIGEST.md`, written by `design-inventory`, is the intake; the design files stay in `docs/brief/` | `DESIGN_DIGEST.md` |
| 1 Inventory | step 3 | every `D-n` screen belongs to one module of the plan | `EXECUTION_PLAN.md` `## Modules` |
| 2 Tokens | step 3 | a role for every token; one theme (rule NUI-7) | `navree-design-to-ui`'s work in `design/`; the theme, at the first module's step 6.4 |
| 3 Mapping | step 3 | every region of every screen is a component or a gap | `EXECUTION_PLAN.md` `## Navree UI gaps` |
| 4 Reconcile | step 3 | its decisions are shown to the operator with the plan | the plan's status line |
| 5 Build | step 6.4 | one module at a time, from its agreed contract (rule BLD-1): the page and form handlers over the module's services, and their route tests | page code, page and route tests |
| 6 Verify | step 6.5 | its checks, then `## Proof of a screen` | `EXECUTION_PLAN.md` `## Build order` (rule BLD-5) |

The three owner stop points of `navree-design-to-ui` are answered at superdev's own stops: the
plan confirmation at step 3 (inventory, tokens, mapping and gaps, shown with the plan) and each
contract's agreement at step 5 (that module's screens). Record each answer there, with the
operator's name and the date (rule BLD-6), and do not ask the same question twice.

At step 5 each `D-n` screen becomes one row of its module's contract under `## Screens`.
`Built from` names the components of the mapping, `States` the states the page draws (rule
NUI-6), `Design` the `D-n` (or, for a preserved prototype, the page under `design/source/`):

| Screen | Route | Built from | States | Design |
|---|---|---|---|---|
| Invoices | `!/invoices` | `Desk` page; `DataTable` of `InvoiceRow`; `Button` "New invoice" | populated, empty, filtered-empty, error | D-4 |

What the mapping records, for each screen:

- Read the design's notes before its screens; they hold what the markup does not show (a list
  paged on the server, rows that can be selected together).
- A pattern that appears on more than two screens (a figure with its label, a toolbar) becomes
  one app function made of components, used everywhere the pattern appears.
- A table: its columns, default sort, filters, search, row actions, bulk actions and paging.
- A form: its fields, the rule of each (they become the contract's `## Validation` rows), its
  steps and what a submit does.
- Dialogs, drawers, charts and live figures, each with the component that draws it.
- The states the design does not show (rule NUI-6).

Tokens: give every colour in `## Tokens` of `DESIGN_DIGEST.md` a role (brand, accent, surface,
foreground, border, or a status as a foreground and background pair) and name it by role, never
by value. A value seen once is noise or a missed token: ask the operator. Type, spacing and radius
follow the same way. Check in `navree-ui` which tokens a custom theme can set; a design value no
token can carry is shown to the operator with the plan, next to the nearest value the theme
allows.

The theme and the shell are built at step 6.4 of the first module, before its first page; later
modules add their navigation items. At step 6.4 `superdev-build` dispatches
`navree-ui-screen-builder` with the agreed contract, the `DESIGN_DIGEST.md` rows of its screens,
the design files, the theme, the module's `## Navree UI gaps` rows, and the plugin root, from which
it builds the paths of the files it reads. In a Navree UI module the routes are pages
and form posts, so the screen builder writes their handlers over the services that
`navree-module-builder` built at 6.2, with the route tests (an allowed and a refused account per
`## Routes` row, 422 per invalid field, each `## Refusals` row, one test per `## Side effects` row
through the form) and the module's route-level suites; it then runs the runtime proof (6.3) and
returns its gap rows.

Superdev's own files in `design/` are `source/`, `baseline/`, `DRIFT.md` and `DEVIATIONS.md`
([design-preservation](../design-preservation/SKILL.md), which also runs when the design is a
prototype the operator built). Check at build time which names `navree-design-to-ui` uses in
`design/`, and never overwrite them.

## Needs and what Navree UI provides

Unless a row names another skill, the detail is in `navree-ui`.

| Need | What Navree UI provides | What the app still does | Proof |
|---|---|---|---|
| Shell and navigation | `Shell`, `NavGroup`, `NavItem`, `UserMenu`; sidebar 16 rem open, a sheet below 768 px; items can require an ability (`ability.only`, `.requires(..)`) | NUI-8 | gate route sweep per role |
| Pages | handlers return components; `Desk` and `AppShell` pages with crumbs and actions; `navree make:page` writes a page and its test | NUI-2, NUI-13 | page test |
| Tables | `DataTable`, `TableRow` row types, state in the URL, 25 rows a page by default, bulk actions, CSV export capped at 100,000 rows, `LazyList` by cursor | NUI-3; throttle the export route | page test |
| Forms | `#[derive(Form)]`, `Submit` and `Rejected`, rejected forms answer 422 with errors under the fields, `AsyncRules`, file fields, `Money` fields; a second identical submit while the first is on its way is ignored | NUI-4; a money or record-creating form follows hard rule 23 | a test: a rejected form answers 422 |
| Dialogs and drawers | `Dialog`, `Sheet`, `Drawer`, opened by the server through `Reply` ops | nothing | browser |
| Instant interactions | `Cmd` commands that act without a request; fetching ahead of a click | nothing | browser |
| Charts and reports | server-drawn SVG charts with a table of the same numbers; `Report::from_query`; PNG only with the `ui-image` feature | NUI-10 | page test |
| Lazy and live regions | `Region` (lazy, live), `LiveStream`, a server nudge after the commit, `RealtimeModule` | NUI-5; hard rule 24 | a test with `send_stream()` |
| Theme and tokens | one token table, built-in themes, `Theme::custom` (refuses text that fails WCAG AA), dark by default, precedence app, workspace, user, URL | NUI-7 | the theme builds; gate contrast |
| The app's own CSS, fonts, images | `AppSheet`, `AppFont`, `AppImage`; no `style` attribute and no `<style>` element on a page | NUI-1; an `AppSheet` sets only token values or fonts and is named in a gap row (hard rule 14) | `verify-done.mjs` checks `Navree UI raw markup` and `Navree UI gap rows` |
| Stored rich text | `Markdown`; text from the database shown inside an element marked `data-ui-stored` | the wrapping `navree-ui` shows, in a file a gap row names (hard rule 14) | page test |
| Sign-in pages | `AuthPages` in every minimal app | NUI-9 | gate |
| Staff panel | Helm at `/admin` (`navree-helm`) | NUI-9; the controls table of [security-foundation](../security-foundation/SKILL.md) | gate role sweep |
| Labels | `I18nModule`, registered with `--ui navree` (`navree-i18n`) | rule BE-8 | review |
| Rich text editing | not there yet ("Later" in the docs) | the gap rule | — |
| Islands | shipped in the docs, forbidden by the `navree-ui` skill | do not use them unless the installed `navree-ui` skill allows it | — |
| Browser tests in Rust | the navree-browser crate (Chrome over CDP); the docs show only a Next.js example (`navree-browser-testing`) | check `navree-browser-testing` for a Navree UI example at build time; otherwise the browser proof follows `product-qa`'s sweeps | — |

Where the `navree-ui` skill and the Navree docs disagree (the `TableQuery` parameter names, the
per-request user menu, the counts of tokens and icons), read the installed skill and the docs page
(`docs/ui/` in the Navree repository, or Navigator's `read_doc` when it is connected), follow the
code the generator writes, and record the choice in the contract.

## The gap rule

Hard rule 14 is the rule, with its list of what is never the answer and the three uses of Navree
UI's raw building blocks. A missing element is never drawn with those building blocks.
A gap is one element of the design that no single Navree UI component draws. A composition of
two or more components standing for that element is a gap, with the resolution
`composed from ...`; a component used under another name is not a gap, and neither is a pattern
made of components that each stand for themselves (a page header, a toolbar of buttons).

Gaps are collected at step 3, from the mapping, and the operator agrees them once, with the plan.
A gap found later, when `navree-ui-screen-builder` returns a row at step 6.4, is recorded by the
main agent, and the module goes on with the composition or the nearest component, unless that
defeats the screen's purpose; then the module waits for the operator. The operator agrees the
later rows at the next stop (the next contract agreement, or the start of step 7), and every row
is agreed by step 7, because the audits read the rows.

1. Look again. Read the installed `navree-ui` skill, `navree-design-to-ui` and the Navree UI docs
   under other names (a "stat tile" may be a `Card` with a figure; a "status chip" a badge column
   of a `DataTable`), and ask Navigator's `list_components` when it is connected. If a component
   exists, use it: that is not a gap.
2. Compose. Write an app function that returns existing Navree UI components, with no raw
   building block. It is escaped, themed and tested like the built-ins because it is made of
   them, and it gets a page test (rule NUI-13). If the installed Navree version documents an
   extension point for new components, use that instead, and only that, and name the docs section
   in the row.
3. Propose. Otherwise write the issue or pull request for Navree (`NavreeHQ/navree`): what the
   design needs, the screen, a screenshot of the region, what step 1 read, and the nearest existing
   component. Open it when the operator agrees. Record the gap row with the nearest existing
   component the operator agrees to, and go on; the row stays open until an installed Navree
   version has the component.

Every gap is one row of `EXECUTION_PLAN.md` `## Navree UI gaps`, whatever its resolution. The same
table also holds a row for each use of a raw building block that hard rule 14 allows (stored rich
text, the app's own fixed image or icon, a token-only stylesheet), so it lists every place the app
touches raw markup at all. A drawing that shows the app's data (a ring, a gauge, a chart) is an
element, never an image: it is a gap. `Files` names, as paths from the app root, every file with such a use; it is filled
when the code exists, and is `none` for a gap that needed none.

| N-n | Screen | What is missing | Checked (skill and docs sections read) | Resolution (composed / extension point / issue or pull request link / an allowed use) | Files | Agreed by, date |
|---|---|---|---|---|---|---|
| N-2 | Invoices (D-4) | a ring showing how much of ₹ 1,00,000 is collected | `navree-ui` components and charts; docs: charts, themes | issue link; shipped as a bar chart of one series | none | Meera Sharma, 2026-11-20 |
| N-3 | Customers (D-1) | a balance badge with a coloured edge | `navree-ui` badges and cards | composed from `Badge` and `Card` in `balance_badge()` with the theme's status colour; the coloured edge: issue link | none | Meera Sharma, 2026-11-20 |
| N-4 | Customer (D-2) | notes stored as rich text | `navree-ui` Markdown; docs: ui/overview, stored content | stored rich text, cleaned, wrapped as `navree-ui` shows | `src/modules/customers/notes.rs` | Meera Sharma, 2026-11-20 |

How a build proves that no gap was worked around:

- `node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs` prints `[PASS] Navree UI raw markup` (none
  of what hard rule 14 forbids in what the build added or changed since `base_commit`, so an
  existing app is judged only on its new code) and `[PASS] Navree UI gap rows` (every Rust file of
  the app with a line added since `base_commit` that uses a raw building block, and every
  stylesheet added or changed since `base_commit`, is named in the `Files` of a table row; it
  prints each file that is not).
- `ui-auditor` in `navree` mode checks that each named use is one of the three that hard rule 14
  allows (the script cannot tell them apart) and reports no `Blocker` or `Major` finding.
- The QA gate's render check (rule QA-10) passes on every Navree UI page.
- By step 7, every `N-n` row has a resolution and the operator's name and date.

## Rules

- **NUI-1** Every screen is made of Navree UI components, with nothing hard rule 14 forbids and
  its raw building blocks only for the three uses it allows, in files a gap row names; the app's
  own stylesheet, fonts and images only through `AppSheet`, `AppFont` and `AppImage`. Proof: the `Navree UI raw markup`
  and `Navree UI gap rows` checks and the render check of rule QA-10.
- **NUI-2** Page routes start with `!` (a route without it sits under `/api` and answers JSON
  errors) and declare their access as JSON routes do, on the `RouteDef`: `.can(action, subject,
  from)` or `.permissions(..)` beyond sign-in (rule BE-5), `.authenticated()` or `.public()`
  (check `navree-ui`). Proof: `navree routes --json` lists every page route of the contract with
  the contract's access.
- **NUI-3** One `DataTable` per page; tables are paged; long lists use `LazyList`; a column a role
  may not see is removed with `TableQuery::without_columns` (rule SEC-10). Proof: a page test as
  a role without the permission finds no such column.
- **NUI-4** Every form is a `#[derive(Form)]` type posted to its handler. Its rules equal the
  contract's validation table; a posted option is checked with `all_pickable`; a file field's
  upload answers with a keyed response; a money field is Navree UI's `Money` (rule BE-9). Proof: a test posts each invalid value of the validation
  table and gets 422 with the field's error (hard rule 8), and a test posts an option outside the
  list and is refused.
- **NUI-5** Page data comes from the handler's query, never from a fetch in the browser; a
  region's source is a path of the site and answers with a `View` or `pages::region_answer`.
  Proof: the page test finds the seeded records in the response.
- **NUI-6** Every list has an empty state with the next action, a filtered-empty state with
  "clear filters", and an error state; build them when the design shows only the populated
  state. Proof: the contract's `States` column lists them and a page test draws each.
- **NUI-7** The design's colours, type, spacing and radius become a theme (`Theme::custom`); no
  colour value in page code, and an app stylesheet sets only token values or fonts, never a
  missing element (hard rule 14); both modes are checked at the gate. Proof: the theme builds; a
  search of `src/` finds colour values only in the theme's file; the gate's contrast cells pass
  in light and dark.
- **NUI-8** Navigation shows each role only what its abilities allow; the server still checks
  every route (rule SEC-7). Proof: the gate's route sweep per role.
- **NUI-9** Sign-in, sign-up and account pages are Navree's `AuthPages`; staff tables and edits
  are Helm resources (`navree make:resource`) unless the PRD needs a staff screen Helm cannot
  draw. Proof: no app handler draws a sign-in form; the plan names each staff screen built outside
  Helm and why.
- **NUI-10** Charts: at most 8 series, an `.id(..)` each, `en-IN` number format with ₹. Proof:
  the page test of every page with a chart.
- **NUI-11** Operator settings screens use structured controls (hard rule 19).
- **NUI-12** No pills, no letter tiles, no glow (rule 6 of `navree-design-to-ui`). Proof:
  `ui-auditor` in `navree` mode.
- **NUI-13** Every page has a test (`TestView` without the app, `TestApp` over HTTP,
  `send_stream()` for live regions). Proof: `cargo test`; every page route of the contract is
  requested by a test.

## Proof of a screen

At step 6.5, for every page of the module, in this order, after the runtime proof of 6.3 (item 6 of
`## Proof of a module` in [backend-on-navree](../backend-on-navree/SKILL.md): each page opened and
each form posted once on the release binary, one side effect observed):

1. `cargo test` passes, the page's and the route tests among them; quote the `test result:` lines.
2. The page is opened in a real browser (Chrome through the navree-browser crate when
   `navree-browser-testing` shows a Navree UI page test in the installed version, otherwise the
   recipes of [ui-sweeps](../product-qa/references/ui-sweeps.md)) at 1440 and 390 px wide, in
   light and dark, signed in as a role the contract allows and, where the contract refuses some,
   as one it refuses: the allowed role sees the content, the refused one the refusal, and the
   console shows zero errors (hard rule 18).
3. `ui-auditor` in `navree` mode reports no `Blocker` or `Major` finding.
4. For a preserved prototype, `visual-diff-auditor` compares the page with its baseline
   ([design-preservation](../design-preservation/SKILL.md), step 4).
5. The result lines go into `EXECUTION_PLAN.md` `## Build order` (rule BLD-5), for example
   `cargo test: 18 passed; 0 failed`,
   `browser: 4 pages x 2 widths x 2 modes x 2 roles, 0 console errors`,
   `ui-auditor: 0 Blocker, 0 Major`.
