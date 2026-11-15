---
name: backend-on-navree
description: Use when building or changing a backend module of a Navree app (models, migrations, routes, validation, access, workspace scope, lists, jobs, schedules, mail, audit, cache, seed data), at step 6 of a superdev build or on its own. Gives each product rule in Navree's terms, the Navree skill that holds the detail, and the test that proves it.
---

# Backend on Navree

This skill is the backend half of a module: steps 6.1 (contract in code), 6.2 (backend) and 6.3 (runtime proof) of a superdev build, or the same work in an existing Navree app. It gives the order to build a module in, what Navree provides for each backend need and what the app still does, the product rules BE-1 to BE-16, and the commands that prove a module. In a Navree UI app the module's routes are pages and form posts whose handlers are screen code ([design-to-navree-ui](../design-to-navree-ui/SKILL.md)): this skill then stops at the service layer, and the route-level tests and the runtime proof follow the screens (step 6 of [superdev-build](../superdev-build/SKILL.md)). Framework facts live in Navree's own skills, which `navree skills:install` puts in the app; this skill names the one to read and does not restate it. Security controls are in [security-foundation](../security-foundation/SKILL.md), screens in [design-to-navree-ui](../design-to-navree-ui/SKILL.md) or [design-to-nextjs](../design-to-nextjs/SKILL.md), and a hard rule cited by number is in [hard-rules.md](../superdev-build/references/hard-rules.md).

## Navree skills to read

- `navree`: first, for every module; it describes a Navree app and points to the right skill.
- `navree-cli-generators`: before generating a module, model, migration, job, mail, seeder or test (`navree make:*`).
- `navree-modules-and-di`: the module type, providers, imports and exports, and module-graph errors.
- `navree-controllers-and-routing`: controllers, routes, extractors and access attributes.
- `navree-validation`: request types, `Valid<..>` and database rules.
- `navree-errors-and-responses`: the error shape, refusal codes and response types.
- `navree-orm`: models, relations, eager loading, scopes, soft deletes, casts and factories.
- `navree-migrations`: tables, columns, indexes and foreign keys.
- `navree-database`: the unit of work, transactions in jobs, raw statements, seeders, pagination and TimescaleDB.
- `navree-access-control`: roles, permissions, abilities, record checks and list filters.
- `navree-workspaces`: workspace models, how the workspace is resolved, workspace roles and isolation.
- `navree-queues-and-scheduling`: jobs, workers, retries, failed jobs and schedules.
- `navree-mail-and-notifications`: mail templates and transports, and notifications.
- `navree-events-and-broadcasting`: events, listeners and real-time channels.
- `navree-cache-and-http-client`: the cache, locks and outgoing HTTP.
- `navree-openapi`: the OpenAPI document and typed clients, for every JSON route a Next.js front end or a Tauri client calls.
- `navree-testing`: `TestApp`, HTTP tests, database tests and fakes.
- `navree-module-conformity`: `navree check`, isolation suites and `navree gate`.
- `navree-config`: `.env`, `config/app.toml` and `APP_*` variables.
- `navree-time-zones`: the zones of people and workspaces, and local days.

When the plan needs them:

- `navree-storage`: files and uploads.
- `navree-billing`: subscriptions, payments and their webhooks.
- `navree-search`: full-text search over models.
- `navree-flags`: feature flags.
- `navree-settings`: typed settings per app, workspace or user.
- `navree-webhooks`: signed outgoing and verified incoming webhooks.
- `navree-sheets`: CSV and Excel imports and exports. An import has a row cap and a dry run that reports what it would write and writes nothing.
- `navree-documents`: PDF and DOCX files.
- `navree-workflows`: durable workflows.

## A module, in order

For one module whose `contracts/<module>.md` says `Status: AGREED`:

1. Generate. `navree make:module <name>` writes the whole module, JSON controller included (`--crud` adds five JSON routes with `#[can]`, their request types and tests); or use the single generators: `navree make:model <module> <Model> -m -f -s --policy`, `navree make:migration <module> create_<table>_table`, `navree make:job <module> <name>`, `navree make:mail <module> <name>`, `navree make:test <module> <name>` (`navree-cli-generators`), never both for one module: the single generators collide with the files `make:module` wrote. A Navree UI module has pages and form posts and no JSON API: run `make:module <name>` and remove its `controller.rs` and `dto.rs` with their tests, or start from the single generators. Generators write a file once and never overwrite it; keep their markers (rule BLD-7).
2. Correct what the generators cannot know. They write global models: make every model the contract marks `workspace` a workspace model (hard rule 10), with the row-level security its migration needs on PostgreSQL and TimescaleDB (hard rule 11). `navree make:module --crud` writes a `PageQuery` list, not a `ListResource`: replace it when the contract's `## Lists` has filters, sorts or search (rule BE-7).
3. Write the contract in code, as [artifacts.md](../superdev-build/references/artifacts.md) defines it: models, migrations, request types, list specs, every route with its access declaration, ability rules and permission keys, with handlers that return a refusal (a Navree UI module's page and form handlers stay that way until the screens). Commit. Proof: `cargo build` passes and `navree routes --json` lists exactly the contract's routes with the same access (hard rule 3).
4. Fill in the services, and the JSON handlers. Services take `&Uow` and open no transaction of their own (hard rule 7). Write the tests from the contract's tables. JSON routes: one per `## Routes` row with an allowed and a refused account (hard rule 5), one per request type of `## Validation`, one per `## Refusals` row, one per `## Side effects` row. A Navree UI module: tests of the service layer here (each rule of `## Validation` on the form type, each ability rule, workspace scoping: a service called for one workspace never reads or changes another's rows, the audit entry of each audited write, each job run twice); its route tests come with the page and form handlers ([design-to-navree-ui](../design-to-navree-ui/SKILL.md)). Add the module's seeder (BE-14) and its share of the committed suites (section "In every module" of [security-foundation](../security-foundation/SKILL.md)): the cases that go through a route belong to whoever writes the route's handler. In a superdev build, `navree-module-builder` writes all of this step.
5. Register the module above `// navree:modules` in `src/app.rs`; `navree make:module` does it.
6. Prove it (`## Proof of a module`) and record the result lines in the plan (rule BLD-5).

## Needs and what Navree provides

| Need | What Navree provides | What the app still does | Proof |
|---|---|---|---|
| Request validation | `Valid<Json<T>>`, `Valid<Query<T>>`, `ValidAsync`; `#[derive(Validate)]` needs a rule or `#[validate(skip)]` on every field or the code does not compile; a plain `Json<T>` checks nothing (`navree-validation`) | wrap every body and query in `Valid<..>`; back each database rule (unique, exists) with a unique index | a test per request type with `assert_validation_error("<field>")` (hard rule 8) |
| Error shape | one body, `{statusCode, message, error, code, errors?}`; the request id in `X-Request-Id`, never in the body (`navree-errors-and-responses`) | a `code` for every refusal (BE-6); no internals in `message` (SEC-13) | tests assert the `code` of every refusal |
| Response shape | no envelope: `Json` is 200, `Created` 201 with `Location`, `NoContent` 204; pages are `{data, meta}` or `{data, next_cursor, prev_cursor}` (`navree-errors-and-responses`) | resource structs (BE-1); a named page struct for a route in the OpenAPI document, because `Page<T>` has no schema | a test compares a response with the contract |
| Lists | `ListResource` specs and one list grammar (`filter[..]`, `sort`, `search`, `page` and `per_page`, or `cursor`); an unknown filter or sort is 400 naming it (`navree-database`, `navree-controllers-and-routing`) | BE-7, BE-16 | a test: an unknown filter answers 400, `per_page=101` answers 400 |
| Access | a route without an access declaration does not compile; `#[can]`, `Accessible`, `Authorized`, `check_fields`; ability rules in `src/abilities.rs`; `navree access:explain` shows why a request was refused (`navree-access-control`) | BE-5; hard rule 6 | `tests/access.rs` |
| Workspace scope | `WorkspaceModule` in every app, `InWorkspace`, `WorkspaceRepo`, `#[model(workspace)]`, `RlsPolicy`, isolation suites (`navree-workspaces`) | BE-2, BE-3, BE-4; hard rules 10 and 11 | `tests/isolation.rs` |
| Unit of work | the request is one transaction (`navree-database`) | hard rule 7 | a test: a refusal after a write leaves no row |
| Audit | `AuditModule` (registered at step 4 by `security-foundation`); writes through models are audited in the same transaction; `#[audit]` on a route; entries at `GET /api/audit` (`navree-security-checklist`, audit group) | hard rule 12; BE-12 | a test: a write, then its entry |
| Jobs | `QueueModule` with the `database` driver in new apps; 3 attempts with backoff from 1 s to 300 s; `<binary> queue:work`, `queue:failed` (`navree-queues-and-scheduling`) | hard rule 7; BE-10 | a test dispatches a job twice and finds one effect |
| Schedules | `ScheduleModule`, with its `schedule_runs` table (`navree-queues-and-scheduling`) | BE-11 | a test runs the task twice and finds one effect |
| Mail and notifications | `MailModule` (the `log` transport in new apps, `array` for tests), `navree make:mail`, notification channels (`navree-mail-and-notifications`) | a template per mail; no personal data beyond what the mail needs | a test with the `array` transport finds the mail; the test runs the queue (`queue.driver = "memory"`, then `Queue::run_pending()`), because mail goes through it |
| Cache | `CacheModule`, memory or redis, with locks (`navree-cache-and-http-client`) | BE-13 | a test: two workspaces, the same key, each reads its own value |
| Money | billing's `Money` (an integer in the smallest unit and a currency code, `navree-billing`); Navree UI's `Money` for form fields and table columns (the smallest unit; it reads `12,34,567` and `12,500.50`, and shows Indian grouping when the page asks for it with `Grouping::Indian`; check `navree-ui`); the ORM's `Decimal` (`navree-orm`) | BE-9 | a test: a total equals the sum of its rows |
| OpenAPI (Next.js front end or a Tauri client) | `ApiModule`, `#[api(..)]`, `navree openapi:export`, `navree openapi:client`; the document and its docs page are off in production unless configured (`navree-openapi`) | `#[api(..)]` on every JSON route; regenerate and commit both files after a route or type change (hard rule 17) | the `verify-done.mjs` API contract drift check |
| Migrations | migrations per module; `navree migrate`, `navree migrate:status`, `navree migrate:fresh --seed`; `navree make:migration` (`navree-migrations`) | an index for every filter and sort (BE-16); `RlsPolicy` on PostgreSQL and TimescaleDB (hard rule 11); never edit a shipped migration (hard rule 16) | `navree migrate:status` shows every migration `Ran` |
| Seed data | seeders, factories, demo workspaces; seeding refuses a production environment unless forced (`navree-database`, `navree-orm`, `navree-workspaces`) | BE-14 | `navree migrate:fresh --seed`, then each demo account signs in |
| Time zones | zones per user and per workspace, local days (`navree-time-zones`) | BE-15 | a test at 00:30 IST |
| Health | `GET /health/live`, `GET /health/ready`, `GET /metrics` (`navree-deployment`) | nothing; never add a liveness check that reads the database | the boot at step 6.3 |
| Logs | `LoggerModule` takes its levels from configuration only, never from `RUST_LOG` (`navree-config`) | set levels in `config/app.toml`; no bodies, tokens or personal data in logs (SEC-13) | `static-auditor` |
| Idempotency | nothing for the app's own routes; only the outgoing HTTP client's keys, unique jobs and `first_or_create` with a unique index (`navree-cache-and-http-client`, `navree-queues-and-scheduling`, `navree-orm`) | hard rule 23 | `tests/money.rs` |

## Rules

**BE-1** A JSON response is a resource struct built from the model (the API kit builds `ProjectResource::from(&*project)`), never the model itself. Counts are numbers computed from rows (0 when there are none, never missing); related names the screen shows are included; a value with several shapes is one tagged type, not several optional fields; optional fields are `Option` and marked nullable in the contract (`navree-errors-and-responses`).
Proof: a test per resource reads every field the contract lists, counts included when they are 0.

**BE-2** `workspace_id` is set from `CurrentWorkspace` (the API kit passes `ws.id()` to the service), never read from the request body (`navree-workspaces`).
Proof: a test posts a body naming another workspace's id and finds the row in the caller's workspace.

**BE-3** Another workspace's record answers exactly like a missing one: 404, the same body, no model or type name in the message (the API kit's `#[can(.., from = "id")]` answers 404 for another workspace's record). A record route on a model that is not a workspace model answers 403 for another user's record; when existence itself must stay hidden, scope the query so the record is not found. For soft-deleted records Navree's documents disagree (403 or 404): check `navree-access-control` at build time and record the behaviour in the contract's `## Refusals`.
Proof: the isolation suite, and a test that requests a missing id and another workspace's id and finds the same status and body.

**BE-4** A query that leaves out the workspace scope (check `navree-workspaces` for how one is written) runs only in tests, console commands and seeders, never in a request handler or in a job acting for one workspace.
Proof: `static-auditor` finds no unscoped query of a workspace model elsewhere; the isolation suites pass.

**BE-5** Code checks abilities and permission keys, never role names: a route that needs more than a signed-in person declares `#[can]` or `#[permissions]` on a JSON route, `.can(action, subject, from)` or `.permissions(..)` on a page route's `RouteDef`, never roles; record routes take their record from the path (`from = "id"`, or `Some("id")` on a `RouteDef`); lists take `Accessible<M, Read>`; updates call `check_fields`; every ability rule in `src/abilities.rs` has a unit test (`navree-access-control`, `navree-ui`).
Proof: `tests/access.rs` passes, and a search of `src/` finds no `#[roles(`, no `.roles(` and no comparison with a role name.

**BE-6** Every refusal the contract lists has its own `code` (`AppError::conflict("..").with_code("invoice_already_sent")`); no 200 carries an error. `impl From<MyError> for AppError` does not compile; map a module's error type with `m.map_error::<E>(..)` (`navree-errors-and-responses`).
Proof: a test per row of the contract's `## Refusals` asserts its status and `code`.

**BE-7** Every list is bounded: a `ListResource` with explicit filters, sorts and search fields, default sort `-created_at`, `per_page` at most 100, or cursor pages for long lists (`navree-database`). Navree UI tables follow rule NUI-3.
Proof: a test per list: an unknown filter answers 400, `per_page=101` answers 400, and the default order is newest first.

**BE-8** Enum values are stored as strings and listed in the contract (the API kit's `projects.status` holds `active` or `archived`); a request type takes them as a Rust enum so an unknown value is refused. Labels are made where the screen is drawn, never by changing the stored value.
Proof: a test posting a value outside the contract's list answers 400.

**BE-9** Money is an integer in paise in a field ending `_paise`, never a float, and is shown as ₹ 1,00,000 by the screen (the Navree UI app's `src/ui/format.rs` formats rupees). In Navree UI forms and tables a money field is Navree UI's `Money`, which holds paise, reads `12,34,567` and `12,500.50`, and shows Indian grouping when the page asks for it (`Grouping::Indian`; check `navree-ui`), so nobody types 50000 for ₹ 500; the column stays `i64` ending `_paise`. Billing's `Money` is for `navree-billing`; the ORM's `Decimal` is for quantities that are not money (`navree-orm`).
Proof: a test finds that a total equals the sum of its rows; a search of `src/` finds no `f32` or `f64` field whose name ends `_paise`.

**BE-10** A job's `NAME` is `<module>.<verb>`. Work longer than a request should take is queued, and the route answers at once; a job that would run long splits into smaller jobs. A job runs outside any unit of work and opens its own (`navree-database`, transactions in jobs). Keep the `database` or `redis` queue driver: the `memory` driver lives in one process, so a separate `<binary> queue:work` sees nothing. Failed jobs are listed with `queue:failed` and retried only after the cause is fixed (`navree-queues-and-scheduling`).
Proof: a test dispatches each job twice and finds one effect (hard rule 7).

**BE-11** A scheduled task is safe to run twice. The scheduler skips missed minutes and does not catch up, so a task for which a missed day matters records what it last did and catches up on its next run (`navree-queues-and-scheduling`; schedules in local time: `navree-time-zones`).
Proof: a test runs the task twice for the same day and finds one effect; when a missed day matters, a test skips a day and finds both days done after the next run.

**BE-12** A write through a model inside a unit of work is audited by Navree with no code, as `<subject>.<created|updated|deleted>` (`customer.created`, `ledger_entry.created`: the model's name in snake case). An action you add yourself, with `#[audit(action = "..")]` on a JSON route or with `AuditLog`'s `record` in a page handler, is named `<module>.<past-tense verb>` (`invoices.sent`); a contract's `Audit action` column names whichever of the two the route produces. An action that must be recorded even when the request fails uses `AuditLog`'s `record`, which writes outside the unit of work; `record_in` writes inside it. Jobs and scheduled tasks that change data are audited too. No secret or personal data goes into audit metadata.
Proof: a test makes each audited write (and runs each job that changes data) and reads the entry (action, actor, subject) from `GET /api/audit` as an account holding `audit.read` (hard rule 12), and finds no seeded phone number or email in the metadata.

**BE-13** Caching is opt-in per query; every key carries the workspace id; sign-in state, audit entries and write responses are never cached; a write invalidates what it changed (`navree-cache-and-http-client`).
Proof: a test caches the same key in two workspaces and each reads its own value; after a write, the next read shows the change.

**BE-14** The demo seed (`navree make:seeder`, factories with `navree make:factory`): one account per role, and one more per role for every agent the operator names as running in parallel at the QA gate, plus one end user per phone run (none unless named); when the product has workspaces, a second workspace with overlapping names (both "Sandhu Traders, Ludhiana" and "Sharma Textiles, Pune" have a customer called Gurpreet Kaur and an invoice `INV-0001`, so a leak shows); realistic volumes (hundreds where a real workspace has hundreds); every count and total computed from rows, never stored as a constant; the money invariants of `security-foundation` satisfied; Indian demo data (Harpreet Sandhu, Meera Sharma, +91 98140 12345, ₹ 1,00,000, IST). A public demo runs on a demo workspace (`kind = "demo"`, read-only or reset nightly, `navree-workspaces`), never on a mock. The seed never runs in production (hard rule 9). `navree migrate:fresh --seed` is the reset every suite and the QA gate start from, and it drops every table, so the seeder creates the global staff roles, their permission keys and the staff accounts that hold them through `AccessService` (`create_role`, `grant`, `assign_role`; check `navree-access-control`). `create_role` answers `RoleExists` for a role that is there: the seeder treats that as done, so that it runs twice. `navree access:role` and `navree access:grant` are for trying a grant by hand: a reset deletes what they wrote, and no command gives a role to a person. Production never runs the seed, so its release has two steps of its own, built at step 4: a data migration that creates the roles and their permission keys (check `navree-access-control` for how a migration writes them), and one console command of the app (`navree make:command <module> <name>`) that creates the first account through the app's own `AuthService`, takes its password from the environment, never from an argument or a file, and gives it its role. At step 4 the seed holds the accounts, the roles and the workspaces the product has; each module's seeder adds its rows. The accounts go into `EXECUTION_PLAN.md` `## Demo accounts`.
Proof: `navree migrate:fresh --seed` exits 0, twice running, then each demo account signs in and each staff account holds its role; a database that was migrated and not seeded has the roles (`tests/security.rs`).

**BE-15** "Today", due dates, overdue checks and every date shown or compared come from the person's or the workspace's time zone, never from `Utc::now()` alone; a function that needs the current day takes it as a parameter, computed once in the handler (`navree-time-zones`). The `navree-ui` skill and the generated UI kit disagree here (the kit's customer page adds 330 minutes to UTC): follow `navree-time-zones`.
Proof: a test passes 00:30 IST on 21 November 2026 (19:00 UTC on 20 November) and finds an invoice due on 20 November overdue and one due on 21 November not.

**BE-16** Every filter and sort of a list has an index in a migration; relations a list shows are eager loaded, never fetched per row (`navree-orm`); a list over a TimescaleDB hypertable always carries a time range (`navree-database`). Query counts per action are measured by `qa-performance-prober` in `product-qa` explore mode.
Proof: every filter and sort field of the contract's `## Lists` has an index in the module's migrations; a list request makes the same number of queries for 1 row and for 50.

## Proof of a module

Run from the app root, in this order, and record the result lines in `EXECUTION_PLAN.md` `## Build order` (rule BLD-5):

1. `cargo fmt --all -- --check` exits 0.
2. `cargo clippy --workspace --all-targets -- -D warnings` exits 0 (no suppression, hard rule 15).
3. `cargo test` prints `test result: ok. <n> passed; 0 failed` for every test binary. Tests run on SQLite files; row-level security, locks and parallel spends are proven by the real-database tests of [security-suites.md](../security-foundation/references/security-suites.md).
4. `navree check` prints `module graph OK: <n> modules, <m> providers` and exits 0; it needs the database started and migrated first (hard rule 13).
5. `navree routes --json` lists exactly the routes of the contract's `## Routes` table, with the same access (how to read it: [artifacts.md](../superdev-build/references/artifacts.md), section `contracts/<module>.md`).
6. `cargo build --release`; start `target/release/<binary> serve` (`.exe` on Windows); `GET /health/live` answers `{"status":"up"}` and `GET /health/ready` answers 200 (hard rule 4). Sign in fresh (see stale tokens in `security-foundation`), call each route of the module once as the contract says (a JSON route with the contract's request; for a Navree UI module, after its screens: open each page and post each form, by the recipe of "Runtime proof without a browser" in [design-to-navree-ui](../design-to-navree-ui/SKILL.md)) and compare the answer with the contract. Observe one side effect: a row, an audit entry, a queued job, a mail in the `log` transport's output, a nudge.
7. With `front_end: next`, or a Tauri client: `navree openapi:export` and `navree openapi:client`, then commit both files (hard rule 17).

`navree gate` runs steps 1 to 4 with `navree config:check` and the web checks in one command; it may replace them once the app passes it.
