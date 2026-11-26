# Backend-vs-frontend ownership, SRP layers, input ceilings, stories and UI ladder

Read this at step 3 (`plan-architect`), step 5 (contracts) and step 6 (`navree-module-builder`, `navree-ui-screen-builder`, `nextjs-module-builder`).

## Backend vs frontend ownership boundary (rule GOV-3, hard rule 28)

| Concern | Owner | Rule |
|---|---|---|
| Authentication, sessions, token rotation and revocation | Backend | Enforced on every request per client type (hard rule 21, rules SEC-1 to SEC-6). |
| Authorization, abilities and permission keys | Backend | UI hides denied controls for clarity; the server checks every route and record (rules BE-5, SEC-7). |
| Workspace scoping (`workspace_id`) | Backend | Resolved from `CurrentWorkspace` or verified session; never read from request bodies (rules BE-2, BE-3, BE-4). |
| Business invariants, uniqueness, money math and hierarchy cycles | Backend service | Enforced inside `&Uow` transactions (hard rules 7, 22, 23; rule BE-9). |
| Server-derived fields (actor, resolved manager email, UTC timestamp, totals) | Backend service | Computed on the server from source rows; client inputs are ignored for derived fields. |
| Filtering, sorting, search and pagination over server datasets | Backend query | Indexed queries with `per_page <= 100` or keyset cursors (rules BE-7, BE-16). |
| Payload ceilings and adversarial input rejection | Backend boundary | Enforced before domain logic runs (rule GOV-6, rule BE-20, hard rule 29). |
| Audit log writes | Backend transaction | Recorded inside the writing unit of work or `AuditLog::record` (hard rule 12, rule BE-12). |
| Layout, responsive 390 px adaptation, RTL text isolation and theme tokens | Frontend | Composed from Navree UI or design-system kit components; zero raw inline styles (hard rule 14, rules NUI-7, QA-6). |
| Form drafts, instant format hints, inline server validation errors | Frontend | Display server `field` errors cleanly on 400 or 422 without losing user input (hard rule 8). |
| Optimistic UI feedback and lazy loading | Frontend | Roll back on server 409 conflicts; lazy-load secondary tabs and heavy widgets. |

## Single-responsibility backend module roles (rule GOV-4, rule BE-19)

Keep each file focused on one job rather than combining HTTP parsing, SQL, authorization and domain rules in a single handler.

| Role | Typical file | Responsibility | Forbidden here |
|---|---|---|---|
| Transport adapter | `controller.rs` / `pages.rs` | Extract `Valid<..>`, `CurrentWorkspace` and actor; call one service method; map `DomainError` to HTTP status and `code` (`navree-errors-and-responses`) | Multi-step business math, raw SQL, direct cross-module table queries |
| Policy and input guard | `policy.rs` / `requests.rs` | Ability rules (`src/abilities.rs`), `#[derive(Validate)]` / `#[derive(Form)]` bounds, payload ceiling checks (`navree-validation`, `navree-access-control`) | Database writes, side effects |
| Domain service | `service.rs` | Transport-agnostic business logic taking `&Uow`, enforcing invariants, idempotency, derived fields and post-commit events (hard rules 7, 22, 23, 24) | Reading raw HTTP headers or building HTML |
| Repository or query module | `queries.rs` / `model.rs` | Parameterized workspace-scoped ORM queries, eager loading, keyset cursor paging, indexed filters (`navree-orm`, `navree-database`) | Authorization guesses, cross-module table joins |
| Worker job | `jobs/<name>.rs` | Idempotent async execution opening its own unit of work and scoping every query by payload `workspace_id` (`navree-queues-and-scheduling`, rule BE-17) | Trusting ambient HTTP state or skipping workspace scope |
| Cross-module facade | `facade.rs` | Narrow exported service interface consumed by higher-tier modules (`navree-modules-and-di`, rule BE-18) | Exposing private models or raw table handles |

## Adversarial input ceilings (rule GOV-6, rule BE-20, hard rule 29)

Every route accepting untrusted input enforces these bounds before business logic executes:

| Input class | Default ceiling or rule | Expected refusal |
|---|---|---|
| JSON request body | At most 64 KB unless the contract explicitly raises it | `413` payload too large |
| Multipart file upload | Per contract (default 10 MB) plus MIME and extension check (`navree-storage`) | `413` or `400` / `422` |
| JSON nesting depth | At most 16 levels | `400` `validation_failed` |
| Plain-text string fields | Explicit max character length per field; refuse `<script>`, `javascript:`, `on*=` HTML event handlers and null bytes (`\0`) | `400` `validation_failed` (JSON) or `422` (Navree UI form) |
| Stored rich text | Sanitized strictly by Navree's HTML sanitizer and wrapped per hard rule 14 | Unsanitized raw markup never stored or rendered |
| Prototype-pollution keys (Next.js / BFF) | Reject `__proto__`, `prototype` and `constructor` keys in parsed JSON payloads | `400` `validation_failed` |
| Pagination and cursors | `1 <= per_page <= 100` (rule BE-7); strict cursor format check on keyset endpoints | `400` `validation_failed` |
| Parent or manager links | Reject self-reference (`id == parent_id`) and cycle chains (`A -> B -> A`) inside `&Uow` | `400` or `409` with contract error `code` |

## Executable user stories with pass and reject coverage (rule GOV-7, hard rule 30)

Every `contracts/<module>.md` includes a `## Stories` table before code starts. Each story covers both the user's goal (`Must pass`) and real-world hostile or boundary failures (`Must reject`) for every route of `## Routes`:

```markdown
## Stories
| Story | Actor | Routes | Must pass | Must reject |
|---|---|---|---|---|
| US-1 | Workspace owner | `GET !/invoices`, `POST !/invoices` | Valid invoice saves in active workspace, updates totals and writes `invoice.created` audit entry | Member without create ability gets 403; empty or negative `amount_paise` gets 422; `<script>` in memo gets 422; `per_page=101` gets 400 |
| US-2 | Workspace owner | `POST !/invoices/{id}/send` | Draft invoice marks sent once, queues `invoices.mail` and records `invoices.sent` | Second send gets 409 `invoice_already_sent`; another workspace's id gets 404 with unchanged row; oversized body gets 413 |
```

`verify-done.mjs` check `contract stories` fails if any module contract lacks `## Stories`, lacks `Must pass` or `Must reject` columns, or leaves either cell empty.

## Four-rung UI escalation ladder (rule GOV-8)

When a screen needs a new interaction or visual block, climb in order and stop at the lowest rung that solves the problem cleanly:

1. **Rung 1 — Reuse built-in components:** use existing `navree-ui` components (or the Next.js kit's `@/components/ui/*` primitives) and design tokens.
2. **Rung 2 — Declarative composition:** combine existing components into a shared app helper function (Navree UI) or shared module component (Next.js) with zero hand-written HTML, inline styles or custom scripts. For mobile or native views backed by server data, use `navree-native` when enabled.
3. **Rung 3 — Focused composable behavior:** when a Next.js or Tauri client needs an interaction the kit lacks (keyboard roving focus, focus trap and return, viewport-clamped floating overlay, drag-and-drop), build one small accessible headless behavior primitive tested independently before wrapping it in styled markup. Never add a second UI component library (rule NX-8).
4. **Rung 4 — Gap proposal or lazy domain widget:** for Navree UI, follow hard rule 14 (record an `N-n` row in `EXECUTION_PLAN.md` `## Navree UI gaps`, ship the agreed nearest component and file an upstream proposal). For Next.js, wrap heavy widgets in an error boundary with a matching loading skeleton, lazy-load secondary tabs and verify at 1440 px and 390 px in light and dark modes.
