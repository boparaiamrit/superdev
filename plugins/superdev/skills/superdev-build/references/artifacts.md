# Artifact formats

The files a build writes at steps 1 to 5, and the words every skill and agent uses for severity, ids, status and output folders. Paths are relative to the app root, the directory `navree new` created. The samples come from Ledgerly, a small invoicing app with two models, customers and invoices, and two demo workspaces, Sandhu Traders (Ludhiana) and Sharma Textiles (Pune). A section with nothing in it keeps its heading and the line `None.`

## STACK.md

Written by the main agent at step 1; `clients` is completed at step 3, and a line is added under `## Suites` when a suite is created (steps 4 and 6).

```markdown
# Stack

navree_version: 1.2.2
new_command: navree new ledgerly --database timescaledb
front_end: navree
kit: none
database: timescaledb
binary: ledgerly
clients: web, admin
base_commit: 3f2a9c1
test_database_url: postgres://navree:navree@127.0.0.1:5432/ledgerly_test
web_dir:
openapi:
api_types:

## Suites

- cargo test --test security
- cargo test --test access
- cargo test --test isolation
```

Keys, all required, in this order:

| Key | Values |
|---|---|
| `navree_version` | what `navree --version` printed, without the word `navree` |
| `new_command` | the exact command run, copied from the terminal; empty for an app that existed before the build |
| `front_end` | `navree`, `next` or `none` |
| `kit` | `none`, `saas`, `api` (the `micro` kit is not used) |
| `database` | `timescaledb`, `postgres`, `mysql`, `sqlite` |
| `binary` | the Cargo package name of the app (the release binary is `target/release/<binary>`, with `.exe` on Windows) |
| `clients` | comma list of `web`, `admin`, `tauri-android`, `tauri-ios`, `tauri-desktop` (`web` always; `admin` when the PRD has staff work) |
| `base_commit` | the id of the first commit (the generated app), or, for an app that existed before the build, of the commit the build starts from; the suppression and raw-markup sweeps diff against it |
| `test_database_url` | empty for SQLite; otherwise required (`verify-done.mjs` fails on an empty value), a database URL for real-database tests (`verify-done.mjs --suites` exports it as `NAVREE_TEST_POSTGRES_URL` or `NAVREE_TEST_MYSQL_URL`) |
| `web_dir` | `web` when `front_end: next`, else empty |
| `openapi` | path of the committed OpenAPI document when `front_end: next` (found at step 1 by running `navree openapi:export` once), else empty |
| `api_types` | path of the generated `schema.d.ts` when `front_end: next` (the SaaS kit's is `web/lib/api/schema.d.ts`; for `--ui next` without a kit, run `navree openapi:client --input <openapi> --out web/lib/api` once and record the result), else empty |

`## Suites`: the exact commands of the committed runtime suites, in run order, one per `- ` line, added when the suite is created. Every command runs as written from the app root on Linux, macOS and Windows: plain words only: no quotes, no shell syntax, no inline environment assignments; each starts with `cargo test`, and the done check refuses any other line. When the CLI was installed from a clone, add the line `# navree from a local checkout: <path>` under the keys; when superdev is not installed in the app (a host with neither `claude` nor `codex`), add `# superdev is not installed in this app: CLAUDE_PLUGIN_ROOT=<path of plugins/superdev>`; lines starting with `#`, other than the title, are not keys.

## PRD_DIGEST.md

Written by `prd-analyst` at step 2. It records what the PRD says, with the PRD section for each line, and makes no decisions. A `Source:` line under the title names the file or folder read. Features are `F-n`, entities `E-n`; an entity says whether it is per workspace. When the PRD labels its features or entities, the digest keeps the PRD's labels and the `Source:` line says so; a section is cited by its number or, when the PRD has none, by its heading.

```markdown
# PRD Digest
Source: docs/brief/ledgerly-prd.md (the labels F-1 and F-2 are the PRD's own; sections are cited by number)
## Product
Ledgerly lets a trader keep customers, send invoices in rupees and see who has paid (PRD 1).
## Roles
- Workspace owner and accountant (PRD 1.2); support staff who help traders (PRD 5.1).
## Features
- F-1 Customers: add, edit, search and list customers (PRD 2.1).
- F-2 Invoices: draft, send by mail, mark paid, totals per customer (PRD 2.2).
## Entities
- E-1 Customer, per workspace: name, phone, email, GSTIN (PRD 2.1).
- E-2 Invoice, per workspace: number, customer, amount, status (draft, sent, paid), due date (PRD 2.2).
## Screens
- Customers list and detail, invoices list and detail, a home page with amounts due (PRD 3).
## Integrations
- Mail for sent invoices (PRD 2.2).
## Non-functional requirements
- Times in IST; amounts shown as ₹ 1,00,000 (PRD 6).
## Questions
- May an accountant delete a sent invoice? PRD 2.2 does not say.
```

## DESIGN_DIGEST.md

Written by `design-inventory` at step 2. It records what the design shows and invents nothing; screens are `D-n`.

```markdown
# Design Digest
## Source
- docs/brief/design/: six HTML screens and PNG exports at 1440 and 390 px.
## Screens
- D-1 Customers list (customers.html): route guess /customers; customers with the amount due; states shown: populated, empty.
- D-2 Invoice detail (invoice.html): route guess /invoices/{id}; one invoice and its lines; states shown: populated.
## Components seen
- Sidebar with groups, data table with filters, dialog, toast, status badge.
## Forms
- New customer (D-3): name (required), phone (+91 98140 12345 as the placeholder), email, GSTIN; button "Add customer".
## Tables
- Customers (D-1): name (sortable), phone, amount due in ₹ (sortable), last invoice date; 25 rows a page.
## Navigation
- Sidebar: Home, Customers, Invoices, Settings; user menu at the top right.
## Tokens
- Colours: brand #1F6F5C, surface #FFFFFF, text #1A1A1A, border #E3E3E3. Type: one sans-serif, body 14/20 px. Spacing: 4 px steps. Radius: 4 px on controls, 6 px on cards.
## Computed displays
- Amount due (D-1): needs the sum of `amount_paise` of each customer's unpaid invoices, shown as ₹ 1,00,000; "Sent 2 h ago" needs the time of sending, in IST.
## States not shown
- Loading and error states of every list; the empty invoices list.
## Questions
- D-2 has a "Download PDF" button; the PRD does not mention a PDF.
```

## GAPS.md

`gap-auditor` writes `## Findings` at step 3 and leaves `## Decisions` empty. Each finding is `G-n` with a severity (`Blocker`, `Major` or `Minor`) and one type: `missing-from-design`, `missing-from-prd`, `type-mismatch`, `naming-drift`, `scope-creep`. The main agent writes `## Decisions`: one line per `G-n`, the operator's words quoted with their name and the date (rule BLD-6). Every finding has a decision before the plan is confirmed.

```markdown
# Gaps
## Findings
### G-1 [Major] [missing-from-design]
- Evidence: F-2 asks for "mark paid" (PRD 2.2); no screen in DESIGN_DIGEST.md has the control (D-2).
- Proposed resolution: a "Mark paid" action on the invoice detail page.
### G-2 [Minor] [naming-drift]
- Evidence: the PRD says "client" (PRD 2.1); the design says "customer" (D-1).
- Proposed resolution: "customer" everywhere.
## Decisions
- G-1: "Add Mark paid to the invoice page." (Meera Sharma, 2026-11-18)
- G-2: "Customer." (Meera Sharma, 2026-11-18)
```

## EXECUTION_PLAN.md

`plan-architect` writes it at step 3 with `Status: DRAFT`. The main agent replaces that line with `Status: CONFIRMED by <name> on <YYYY-MM-DD>` only after the operator says so, adds `## Demo accounts` at step 4, and fills a `## Build order` row after each module (rule BLD-5). A revision follows rule BLD-3.

```markdown
# Execution Plan
Status: CONFIRMED by Meera Sharma on 2026-11-18
## Modules
| Id | Module | Purpose | Depends on |
|---|---|---|---|
| M-1 | customers | the trader's customers | (none) |
| M-2 | invoices | invoices, sending and payment | M-1 |
## Models
| Model | Module | Table | Scope | Fields | Indexes |
|---|---|---|---|---|---|
| Customer | customers | customers | workspace | name, phone, email, gstin | (workspace_id, phone) unique |
| Invoice | invoices | invoices | workspace | number, customer_id, amount_paise, status, due_on | (workspace_id, number) unique |
## Build order
| Module | Status | Commit | Proof |
|---|---|---|---|
| M-1 customers | PASS | 4be21d0 | cargo test: 41 passed; 0 failed; routes match the contract; GET /health/ready 200; audit entry customers.created; /customers at 1440 and 390 px, 0 console errors |
| M-2 invoices | PASS (6.5 NOT RUN, ACC-1) | 9c41e07 | cargo test: 58 passed; 0 failed; routes match the contract; one invoice row and its audit entry observed; browser proof NOT RUN, accepted in ACC-1 |
| M-3 reports | NOT RUN | | |
## Access
- Global roles: `admin`, `support`. Workspace roles: `owner`, `admin`, `member`, `viewer`.
- Permission keys: `customers.read`, `customers.reveal_contact`, `invoices.send`.
- Public routes, copied from `<target>/release/<binary> routes --json` at step 4 and after each module: the release binary, which ships, and not `navree routes --json`, which runs the debug build and also lists Logbook's routes. Each route is method and path in backticks; the done check compares this bullet with the release binary both ways (prose does not count). A Navree app has about thirty public routes of the framework's own: the sign-in pages, health, the toolkit's files, the token and realtime routes. `GET /health/live`, `GET /health/ready`, `GET /sign-in`, `POST /sign-in`, `GET /_navree/ui/{file}`, `POST /api/auth/login`, `GET /metrics`, `GET /api/openapi.json`, `GET /api/docs` and the rest of the binary's list. Decided at deploy, and settled in `DEPLOY.md`: `/metrics`, `/api/openapi.json` and `/api/docs`. No module route is public.
- First address: `GET /` sends a signed-in person to `/customers` and a guest to `/sign-in` (route `GET !/`, access `.authenticated()`); the done check asks for it on the booted release binary.
## Jobs and schedules
- `invoices.remind`: daily at 09:00 IST, mails a reminder for each invoice due tomorrow.
## Integrations
- Mail: the `log` transport in development, a real transport in production.
## Security
- Controls that apply: password sign-in, browser sessions, rate limits, second factor (staff), route access, roles and permission keys, masked personal data, audit log, workspace isolation.
- Masked fields: `customers.phone`, `customers.email`. Balances: none. Live topics: `invoices` per workspace.
## Navree UI gaps
None.
## Open items
- O-1 PDF download of an invoice: the operator decides after M-2.
## Acceptance criteria
- F-1: an owner adds a customer with phone +91 98140 12345 and finds it by name; a member of Sharma Textiles cannot open it.
- F-2: an accountant sends an invoice of ₹ 1,00,000; the customer gets the mail; marking it paid moves it out of the amount due.
## Demo accounts
| Email | Role | Workspace |
|---|---|---|
| harpreet.sandhu@example.com | owner | Sandhu Traders, Ludhiana |
| gurpreet.kaur@example.com | member | Sandhu Traders, Ludhiana |
| meera.sharma@example.com | owner | Sharma Textiles, Pune |
| arjun.mehta@example.com | support (staff) | (none) |
```

`## Navree UI gaps` has one row per `N-n`, in the columns defined in [design-to-navree-ui](../../design-to-navree-ui/SKILL.md), section "The gap rule"; every gap has a row, composed ones included, and so has each use of a raw building block for one of the three uses hard rule 14 allows; a missing element is never drawn with those building blocks. The `Files` column names every file with such a use, and only rows of this table count as naming it. `## Build order` lists the modules in the order they are built; `Status` is `PASS`, `FAIL` or `NOT RUN`. A module whose browser proof (6.5) cannot run on this host reads `PASS (6.5 NOT RUN, ACC-n)`, with `ACC-n` an entry of `ACCEPTANCES.md`; every other proof is quoted in `Proof` and the unproved one is named there. A parenthesis with no `ACC-n` is not a pass (rule BLD-5). With `front_end: next`, `## Modules` also holds, below its table, the module plan of [design-to-nextjs](../../design-to-nextjs/SKILL.md) (its step 3): one line per module with its folder and routes, such as `- M-2 invoices: web/modules/invoices; /w/[workspace]/invoices, /w/[workspace]/invoices/[id]`, and one line such as `Shared: web/components (page header, empty state); the tokens layer on @navree/theme`.

## `contracts/<module>.md`

The contract of a module is two things, in this order:

1. **The written contract**, `contracts/<module>.md` (format below), agreed by the operator at step 5: the module's models with their scope (global or workspace), its routes with the access declaration of each, its request types with the validation rule of every field, its list queries (filters, sorts, search, paging), its abilities and permission keys, its refusals (status and `code`), its side effects (audit actions, jobs, mails, live topics) and its screens.
2. **The contract in code**, the module's first commit at step 6, made before any handler body or screen code: the model structs and migrations, the request types with `#[derive(Validate)]` (a rule or `skip` on every field, else no compile), the list specs (`ListResource` for JSON routes; `TableRow` and `#[derive(Form)]` types for Navree UI), every route with its access declaration (a route without one does not compile; rule BE-5 of [backend-on-navree](../../backend-on-navree/SKILL.md) says which declarations a superdev build uses) and handlers that return a refusal until they are filled (JSON handlers at step 6.2; a Navree UI module's page and form handlers at step 6.4, hard rule 3), the ability rules in `src/abilities.rs`, the permission keys in `config/app.toml`.
   - **Navree UI app** (`front_end: navree`): that is the whole contract. Its routes are pages and form posts, answering with a page or a `Reply`; the screens are drawn on the server from these types, and there is no wire format between screen and server.
   - **Next.js front end** (`front_end: next`): every JSON route also carries `#[api(..)]` with its request, response, status and responses, a named page type for lists (`Page<T>` has no schema), and the commit includes the regenerated `openapi.json` (`navree openapi:export`) and TypeScript types (`navree openapi:client`). Screens import only those generated types; no hand-written response type.

The Navree skills for these parts are `navree-validation`, `navree-controllers-and-routing`, `navree-access-control`, `navree-orm`, `navree-ui` and, for Next.js, `navree-openapi`. Proof that the contract in code matches the written contract: `cargo build` passes; among the routes whose `module` is this module's, `navree routes --json` lists exactly the routes of the contract's route table with the same access (a page route's `path` shows without `!`, with `"page": true`; `access` reads like `can:send Invoice from id`); for Next.js, the drift check of `verify-done.mjs` (regenerate both files, `git diff` shows nothing) passes. A shape needed later is added to `contracts/<module>.md` first, then to the code.

```markdown
# Contract: invoices (M-2)
Status: AGREED by Meera Sharma on 2026-11-20
Front end: navree
## Models
| Model | Table | Scope | Fields | Indexes and unique keys |
|---|---|---|---|---|
| Invoice | invoices | workspace | id: Uuid; workspace_id: Uuid; customer_id: Uuid; number: String; amount_paise: i64; status: String (`draft`, `sent`, `paid`); due_on: NaiveDate; created_at; updated_at | (workspace_id, number) unique |
## Routes
| Method | Path | Name | Access | Request | Response | Statuses | Audit action |
|---|---|---|---|---|---|---|---|
| GET | `!/invoices` | invoices.index | `.can("read", "Invoice", None)` | `TableQuery<InvoiceRow>` | page | 200, 403 | (none) |
| POST | `!/invoices/{id}/send` | invoices.send | `.can("send", "Invoice", Some("id"))` | (none) | `Reply` | 200, 403, 404, 409 | invoices.sent |
## Validation
| Request type | Field | Rule | Message |
|---|---|---|---|
## Lists
| Route | Filters | Sorts (default) | Search | Paging |
|---|---|---|---|---|
## Abilities and permissions
## Refusals
| Situation | Status | code |
|---|---|---|
| Invoice already sent | 409 | `invoice_already_sent` |
## Side effects
| Trigger | Effect | Proof |
|---|---|---|
## Screens
| Screen | Route | Built from | States | Design |
|---|---|---|---|---|
## Open questions
```

The sample shows the headings and columns; in a real contract every table has its rows, and a section with nothing in it holds `None.` A Navree UI module's routes are pages and form posts, as above; a Next.js module's are JSON routes, such as `POST /api/v1/invoices/{id}/send` with `#[can(Send, Invoice, from = "id")]`, answering `InvoiceResource`.

Rules for the format: page routes start with `!`; API paths are `/api/v<version>/<prefix>/<path>`; the `Name` column is optional documentation, because a route declared with the route macros shows `"name": null` in `navree routes --json`, so the proof compares method, path and access only; the Access column holds exactly one declaration per route; `Scope` is `global` or `workspace`; amounts are integers in paise with the field name ending `_paise` (shown on screens as ₹ 1,00,000); dates are `NaiveDate` or `DateTime<Utc>`; the `## Screens` section is left out when `front_end: none`. `schema-reverse-engineer` drafts contracts for a prototype with `Status: DRAFT`; only the main agent sets `Status: AGREED` (rule BLD-2).

## Severity

| Severity | Meaning | Release |
|---|---|---|
| `Blocker` | Data reaches someone it must not (another workspace, a role without the permission, the public); wrong money; a security control not working; a secret exposed; data loss; a crash or 500 on a main path | Blocks. Fix before anything else. |
| `Major` | A main task cannot be completed; a dead link or inert button on a main path; text contrast below WCAG AA; a planned control missing but not exploitable alone; a write without its audit entry; a native client unusable on a supported screen | Blocks. |
| `Minor` | Cosmetic, wording, a non-main path, hygiene with no exposure | Does not block; listed with an owner. |
| `Note` | Not a defect: positive evidence, a refactor candidate, an observation | Does not block. |

Every finding has an id, a severity, where (file:line, route or screen), the evidence (the command and its result line, a screenshot path, a response excerpt) and an owner. A finding without evidence is not reported. Severity is not priority: the fix order puts exposure first.

## Ids

Finding ids: `G-` gaps (`GAPS.md`), `A-` audit, `Q-` QA, `S-` security, `B-` debugging candidates. Other ids: `F-` PRD features, `E-` PRD entities, `D-` design screens, `M-` modules, `O-` open items, `N-` Navree UI gaps, `ACC-` the operator's acceptances (`ACCEPTANCES.md`). Numbers start at 1 and are never reused in a file.

## ACCEPTANCES.md

The operator's own file, at the app root: the only place where something that blocks a release is accepted. The operator writes it, one entry per acceptance, and commits each entry on its own. The main agent and every dispatched agent never create or edit it and never write a sentence the operator did not say (rule BLD-6).

```markdown
# Acceptances

## ACC-1
- Date: 2026-11-24
- Operator: Meera Sharma
- Accepts: S-6 of `SECURITY_REPORT.md`
- Words: "Simran Kaur sees the mobile numbers in full; the shop has no other staff."

## ACC-2
- Date: 2026-11-24
- Operator: Meera Sharma
- Accepts: proof 6.5 of M-2 invoices, and the dark-mode cells of section 2 of `QA_COVERAGE.md`
- Words: "No browser here. I check the screens myself before the first customer."
```

An entry is a heading `ACC-n` with its date, the operator's name, what it accepts and the operator's words. What it accepts is named by its id (`S-6`, `A-2`, `Q-3`), by a cell or a section of `QA_COVERAGE.md`, or by a module's proof. Everywhere else a build cites an acceptance by its id and never copies a sentence of it:

- a finding's state is `accepted ACC-n` (a finding is `open`, `fixed` or `accepted ACC-n`);
- a cell or a row that is `NOT RUN` reads `NOT RUN (ACC-n)`, and its row in the report's `## Not run` section holds the same `ACC-n`;
- a module's row in `## Build order` reads `PASS (6.5 NOT RUN, ACC-n)`;
- a check of `DEPLOY.md` that is `NOT RUN` cites the `ACC-n` in its evidence.

`verify-done.mjs --strict` fails an `accepted` state, or a `NOT RUN` counted as accepted, whose `ACC-n` is not an entry of this file, and fails when a commit changes this file together with another file.

## Status lines

- A check, a matrix cell, a post-deploy check: exactly `PASS`, `FAIL` or `NOT RUN`; a cell may carry an evidence level in a parenthesis, defined with the matrix it belongs to. `NOT RUN` blocks like `FAIL` until the operator accepts it in `ACCEPTANCES.md`; an agent never writes an acceptance. A matrix lists only the cells that apply and states the rule for which cells apply once per section.
- `verify-done.mjs` prints the same three labels. A check that passes for development but would not pass a release claim prints `PASS` with a detail line starting `warning:`; `--strict` turns every warning and every `NOT RUN` into a failure. Exit 0 means that no check failed; only a `--strict` run whose last line is `DONE` means the build is done.
- Artifact status lines: `Status: DRAFT`; `Status: CONFIRMED by <name> on <YYYY-MM-DD>` (`EXECUTION_PLAN.md`); `Status: AGREED by <name> on <YYYY-MM-DD>` (`contracts/*.md`, `refactor/<module>/PLAN.md`); `Status: APPROVED by <name> on <YYYY-MM-DD>` (`prototype/MIGRATION_PLAN.md`).
- Verdict words, each used in one place only: `PRODUCT` / `HYBRID` / `DEMO` (the completeness verdict of `product-audit`); `REAL` / `MOCKED` / `HYBRID` (a screen's data source); `WIRED` / `STUB` / `NO-OP` (a control); `CONFIRMED` / `REJECTED` / `INCONCLUSIVE` (a debugging hypothesis); `READY TO COMMIT` / `REJECT` (`REGRESSION.md`); `READY` / `NOT READY` (a module score of 9 or more, or less, in the score mode of `product-audit`).

No other severity, status or verdict words are used.

## Output folders and what is committed

Every reporting agent writes `<out_dir>/<agent-name>.md` and puts its evidence (screenshots, logs, raw JSON) under `<out_dir>/<agent-name>/`. The caller passes `out_dir`: `audit`, `qa`, `security` or `debug/<slug>`.

- Committed: the files at the root of the app (`STACK.md`, `PRD_DIGEST.md`, `DESIGN_DIGEST.md`, `GAPS.md`, `EXECUTION_PLAN.md`, `SECURITY_REPORT.md`, `AUDIT_REPORT.md`, `QA_COVERAGE.md`, `DEPLOY.md`, and the operator's `ACCEPTANCES.md`), `contracts/`, each agent's `<out_dir>/<agent-name>.md`, and `qa/verify-done.txt`, the output of the last full done check.
- Git-ignored: the evidence sub-folders `qa/<agent-name>/`, `audit/<agent-name>/` and `security/<agent-name>/`, and the sub-folders of `qa/` that hold runs and sessions (`qa/runs/`, `qa/.auth/`). Step 1 adds `qa/*/`, `audit/*/` and `security/*/` to `.gitignore`, which ignore sub-folders only: the reports and `qa/verify-done.txt` beside them stay tracked.
