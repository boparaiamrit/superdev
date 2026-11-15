# Hard rules

Read these rules once at the start of a build. Each rule says where it applies and names the check that proves it was followed.

## Before code

### 1. Install the Navree CLI, create the app and install Navree's skills first

**Scope:** every build, before any other file is written.

Install the CLI (`cargo install navree-cli`), create the app with the `navree new` line the operator agreed, run `navree skills:install`, and record the line and the version in `STACK.md`. Navree's skills match the CLI's version; read them for every framework fact.

**Verify:** `navree --version` prints `navree <navree_version>` as written in `STACK.md`; `.claude/skills/navree/SKILL.md` and `.agents/skills/navree/SKILL.md` exist (`verify-done.mjs` checks both).

### 2. Confirm the plan on disk before code

**Scope:** every build and every revision of its plan.

Write the digests, `GAPS.md` and `EXECUTION_PLAN.md`, show the summary, and wait for the operator. A revision edits `GAPS.md` `## Decisions` first.

**Verify:** `EXECUTION_PLAN.md` holds `Status: CONFIRMED by <name> on <date>` (the `verify-done.mjs` check `plan confirmed`), and `git log --format=%h -- EXECUTION_PLAN.md src/modules` shows the commit adding that line before the first commit that touches `src/modules/` after `base_commit`.

### 3. Agree each module's contract before its code; one owner

**Scope:** every module. What a contract is on Navree is defined in [artifacts.md](artifacts.md).

The main agent writes `contracts/<module>.md`; the operator agrees; the contract in code is the module's first commit; a new shape goes into the contract first. Screens use only the contract's types (generated TypeScript types for Next.js). In a Navree UI module the routes are pages and form posts whose handlers are screen code, so they are filled at step 6.4 and the module's route-level tests and runtime proof follow them; with JSON routes they come before the screens (step 6 of `superdev-build`).

**Verify:** each module's contract holds `Status: AGREED by <name> on <date>` (the `verify-done.mjs` check `contracts agreed`), and the commit that sets it is older than the module's first handler-body commit; `navree routes --json` lists exactly the contract's routes with the same access; with `front_end: next`, the `verify-done.mjs` API contract drift check is `PASS`.

## Every module

### 4. Boot the release binary after each backend module

**Scope:** every module with routes, and the foundation at step 4.

Tests use an in-process app on SQLite files; only the built binary proves the app starts with its real configuration (`navree-deployment`).

**Verify:** `cargo build --release`; `target/release/<binary> serve` keeps running; `GET /health/live` answers `{"status":"up"}` and `GET /health/ready` answers 200; each route of the module answers as its contract says; the `verify-done.mjs` boot check is `PASS`.

### 5. A declaration is not proof

**Scope:** every access rule, write, audit entry, job, mail, live nudge and computed total.

An attribute, a config line or a guard shows intent. A test that performs the action and observes the result is the proof (`navree-testing`).

**Verify:** each row of a contract's `## Side effects` has a test that asserts the effect (row, audit entry, queued job, mail in the `array` transport, nudge); each `## Routes` row has a test with an allowed and a refused account that asserts the status and, for a refused write, that the database did not change.

## Navree traps

### 6. Declare access on every route

**Scope:** every route, JSON or page.

Every route carries an access declaration; a route without one does not compile. Which declarations a superdev build uses is rule BE-5 of [backend-on-navree](../../backend-on-navree/SKILL.md): abilities and permission keys, never role names. Never make a route `#[public]` to get past a 401 or 403. Public routes are listed in the plan. Read `navree-access-control`.

**Verify:** `cargo build` passes; in `<target>/release/<binary> routes --json`, the release binary, which ships, the routes with public access are exactly the plan's `## Access` list of public routes: the `verify-done.mjs` check `public routes` fails on, and prints, a public route whose method and path, written together in backticks, the list does not name, and a route of the list's bullet that the binary does not have as public.

### 7. Write inside the request's unit of work; make jobs safe to run twice

**Scope:** every handler, service and job.

The request is one transaction: writes commit when the status is below 400 and roll back otherwise, so a handler that writes and then answers 400 loses the write. Services take `&Uow` and open no transaction of their own. A job runs outside any unit of work, at least once, and is queued from a request only if the request commits. Mass updates and raw SQL skip model events and the audit log; record them with `uow.record_change`. Read `navree-database` and `navree-queues-and-scheduling`.

**Verify:** a test where a handler refuses after a write finds no row; a test dispatches a job twice and finds one effect; a test of each mass update finds its audit entry.

### 8. Validation errors are 400; only Navree UI forms answer 422

**Scope:** every request type and every client.

The API answers input errors with 400 (`validation_failed`, `bad_request`) and CSRF failures with 403; it never answers 422. Navree UI forms answer 422 with the errors under the fields. Clients branch on `code`, never on `message`. Read `navree-validation` and `navree-errors-and-responses`.

**Verify:** a test per request type with `assert_validation_error("<field>")`; a Navree UI form test that asserts 422; no Next.js or Tauri code expects 422 from the API (a search for `422` in `web/` and `clients/` finds none outside Navree UI tests).

### 9. Keep secrets in `.env` or the environment, and know which source wins

**Scope:** all configuration, every environment.

Later sources win: `config/app.toml`, `config/<section>.toml`, `config/env/<env>.toml`, `.env`, then the process's `APP_*` variables. Only `APP_*` variables are read (`APP_DATABASE__URL`, never `DATABASE_URL`); `RUST_LOG` is not read. Secrets live only in `.env` or the environment, wrapped in `Secret<T>`, never in TOML, never with a default. `APP_KEY` is the same in every process. Demo accounts and demo data never reach production. Read `navree-config`.

**Verify:** `git ls-files .env` prints nothing; `APP_ENV=production navree config:check --env production` exits 0 on the deploy configuration (an app on SQLite cannot pass: rule 16); `navree config:show --origin` shows every secret coming from `.env` or the environment; a search of `config/` for quoted values of keys named `key`, `secret`, `password` or `token` finds none.

### 10. Models are global until marked for a workspace

**Scope:** every model holding a workspace's data.

Generators write global models. Workspace data needs `#[model(workspace)]` and a `workspace_id` column, queries through `WorkspaceRepo`, and `#[guard(InWorkspace::guard())]` on its controllers; without the guard, route checks use global roles. A workspace-scoped query with no workspace fails; it never falls back to every workspace. Read `navree-workspaces`.

**Verify:** `tests/isolation.rs` runs `app.isolation_suite::<M>()` for every module the plan marks `workspace`, and passes; `static-auditor` finds no workspace-module model without `workspace` in its `#[model(..)]`.

### 11. SQLite and MySQL have no row-level security

**Scope:** every workspace table; the database role in production.

On SQLite and MySQL the scoping of rule 10 is the only barrier. On PostgreSQL and TimescaleDB each workspace table's migration adds `RlsPolicy`, and the app connects as an ordinary role (not a superuser, not `BYPASSRLS`), or the policy does nothing.

**Verify:** SQLite or MySQL: the isolation suites of rule 10 pass and no raw statement on a workspace table lacks the workspace predicate. PostgreSQL or TimescaleDB: every workspace table's migration contains `RlsPolicy`, and as the app's role `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user` returns `f`, `f`.

### 12. Register the audit module; the minimal app does not

**Scope:** every app with staff, personal data, money or other sensitive writes.

The kits register `AuditModule`; the minimal app's root does not. Register it, put `#[audit(action = "..")]` on sensitive routes, and schedule `audit:prune` (nothing prunes on its own).

**Verify:** a test writes through a model and then reads the entry from `GET /api/audit` with an account holding `audit.read`; the scheduler registration contains `audit:prune`.

### 13. Give `navree check` its configuration and a migrated database

**Scope:** every run of `navree check` (step 4, every module, `verify-done.mjs`).

`navree check` validates the module graph and boots the app once for its conformity checks (some Navree texts say it does not boot; it does). Start the database first (`navree dock up` for TimescaleDB and PostgreSQL; MySQL runs on a server you provide at `database.url`; SQLite needs nothing), then run `navree migrate`. Conformity errors exit 1; warnings are only reported. Read `navree-module-conformity`.

**Verify:** `navree check` exits 0 and prints `module graph OK: <n> modules, <m> providers`.

### 14. Fill a gap in Navree UI the Navree way, never with raw markup

**Scope:** every Navree UI screen.

When a design needs something Navree UI does not have, in this order: (1) check the `navree-ui` skill and the docs again; it may exist under another name. (2) Compose it from existing Navree UI components in an app function, with no raw building block, so it is escaped, themed and tested like the built-ins; if the installed Navree version documents an extension point for new components, use it, and only it. (3) Otherwise write it up as an issue or pull request for Navree, record the gap with the nearest existing component the operator agrees to, and go on. Every gap is a row under `## Navree UI gaps` in `EXECUTION_PLAN.md`; what a gap is, the row's columns and when the operator agrees are in [design-to-navree-ui](../../design-to-navree-ui/SKILL.md), section "The gap rule".

Never the answer: HTML written by hand in a Rust string; a `style`, `class` or `on*` attribute in one; a `<style>` or `<script>` element; a script file the app serves; an island, unless the installed `navree-ui` skill allows it.

Accounted for: Navree UI's own raw building blocks (`SafeHtml::trusted(..)`, `Node::Raw`, `Node::Static`, an element built by hand with `el(..)`) and an app stylesheet (`AppSheet`) have three uses, and only these: stored rich text that Navree has cleaned, wrapped as `navree-ui` shows (`el("div").flag("data-ui-stored", true).child(SafeHtml::trusted(..))`); the app's own fixed image or icon (a logo, a mark) that neither a Navree UI component nor `AppImage` can show; a drawing that shows the app's data (a ring, a gauge, a chart) is an element, never an image; and a stylesheet that sets only the theme's token values or the app's fonts. Each use is in a file that the `Files` column of a gap row names, with that use as the row's resolution and the operator's name and date. Drawing a missing element with them is never a resolution: the element is composed from components, or proposed to Navree and shipped with the nearest component.

**Verify:** the `verify-done.mjs` checks `Navree UI raw markup` and `Navree UI gap rows` are `PASS`. The second fails, printing the file, for every Rust file of the app (outside `target/`, `plugins/`, `.claude/`, `.agents/` and `tests/` folders) in which a line added since `base_commit` uses one of the building blocks above, and every stylesheet added or changed since `base_commit`, that no row of the gap table names; a script cannot tell which use a line serves, so `ui-auditor` checks that each named use is one of the three. The QA gate's render check (rule QA-10) is `PASS` on every Navree UI page; by step 7 every gap row has its resolution and the operator's name and date.

### 15. Fix the cause; add no suppression

**Scope:** every change after `base_commit`.

No `#[allow(..)]`, `#![allow(..)]`, `#[expect(..)]`, `#[cfg_attr(.., allow(..))]`, `eslint-disable`, `oxlint-disable`, `@ts-ignore`, `@ts-expect-error`, `@ts-nocheck` or `as any` to make a check pass, and no lint turned off in configuration (`allow` in a `[lints]` table of `Cargo.toml`, `-A` in `rustflags`, a `clippy.toml` key that allows a lint or raises a threshold, an ESLint or oxlint rule set to `off`, `"strict": false` in `tsconfig.json`). Code that `navree new` wrote is the baseline. One exception: `#![allow(dead_code)]` as the first attribute of `tests/support/mod.rs`, the helpers the suites share, because each suite is a test binary of its own that leaves some helpers unused; Navree's API kit writes the same line.

**Verify:** the `verify-done.mjs` suppression sweep against `base_commit` is `PASS`; `cargo clippy --workspace --all-targets -- -D warnings` exits 0.

### 16. Never edit a shipped migration; set the production defaults

**Scope:** migrations; the production configuration.

A migration that has run anywhere but your machine is never edited; add a new one. In production, `database.migrate_on_boot = false` and migrations run as a release step; `navree deploy:rollback` does not undo them, so a release's migrations are additive. Also `session.secure = true` and a mail transport other than `log`. These settings live in `config/env/production.toml`, which Navree reads only when `APP_ENV=production` is set. Read `navree-migrations`, `navree-config` and `navree-deployment`.

**Verify:** `git diff --name-status <last released commit> -- src` lists migration files only as added (`A`); before a first release there is no such commit, and the rule holds from the first deploy on; `APP_ENV=production navree config:check --env production` exits 0. An app on SQLite cannot pass it, because the check refuses a SQLite file in production: for a SQLite deployment the finding about the SQLite file is recorded in `DEPLOY.md` with the operator's `ACC-n`, and every other finding is fixed.

### 17. Never edit regenerated files by hand

**Scope:** `openapi.json` and the generated `schema.d.ts`; `.navree/dock/compose.yaml`; the `.env` block between `# dock:start` and `# dock:end`; `.claude/skills/navree*` and `.agents/skills/navree*`.

Regenerate with `navree openapi:export` and `navree openapi:client` and commit both after a route or type change; edit `dock.toml`, not the compose file; edit `AGENTS.md`, not `CLAUDE.md`; `navree skills:install` replaces the Navree skill folders. Read `navree-openapi` and `navree-dock`.

**Verify:** the `verify-done.mjs` API contract drift check is `PASS` (Next.js); after `navree skills:install`, `git status --short .claude/skills .agents/skills` prints nothing.

## Product, security and clients

### 18. Prove every screen in a real browser

**Scope:** every page of the web app and of the admin screens.

A type check, a build or a page test does not prove a page works in a browser.

**Verify:** each route opened in a real browser at 1440 and 390 px wide with zero console errors, recorded in the plan (rule BLD-5) and in `QA_COVERAGE.md` section 2.

### 19. Give operators structured controls

**Scope:** settings screens used by people who are not developers.

Labelled inputs, switches and selects with plain words; an explicit control for states such as "unlimited"; no raw JSON, no key-value blobs, no magic numbers.

**Verify:** an operator account completes the settings task through the screen without knowing any field name; a test checks the saved values and their effect.

### 20. Use one canonical public origin

**Scope:** every public link in pages, mails, API responses and clients.

Build public links from `app.url` (`APP_APP__URL` in production), never from a request's `Host` header or another app's setting.

**Verify:** the same public link generated from a page, a mail and an API response equals `app.url` plus the path, and opens signed out.

### 21. End access the way each client signs in

**Scope:** sign-out, sign-out everywhere, a revoked device, a blocked account, a disabled staff member, a password change or reset.

Browser sessions (Navree UI pages and Navree's own sign-in pages, through `SessionModule`): each event above ends the session at once, a copy of its cookie included, and the browser is a guest from its next request; signing out ends its live subscriptions too (for the other events, check `navree-auth`). Token clients (a Next.js front end through its BFF, a Tauri client, an API client): refresh tokens rotate and a reused one ends the family; refresh is refused at once after any of the events above; access tokens are stateless and end within their lifetime (900 s by default), so keep it short. Parallel refreshes count as reuse: the BFF refreshes one at a time per token, and several BFF processes need sticky sessions. A token client that needs access to end at once records a gap. Read `navree-auth` (sessions, tokens).

**Verify:** for each kind of client the app has: browser sessions, a test performs each event and finds the same cookie's next request is a guest; token clients, a test revokes a session and the next refresh answers 401 at once, a test reusing a rotated refresh token ends the family, and the configured access-token lifetime is at most 900 s.

### 22. Serialize balance changes per account

**Scope:** credits, wallets, stock, seats, quotas: any stored balance changed by concurrent requests or jobs.

Inside the request's unit of work, take a transaction-scoped lock per account before reading or changing the balance, on every path (spend, grant, debit, expiry, refund): on PostgreSQL and TimescaleDB `pg_advisory_xact_lock`, run as a raw statement in the unit of work (check `navree-database` for how); on MySQL and SQLite check `navree-database` and record the method. Lock several accounts in sorted order. A reconciliation proves the books nightly and on demand, and the seed satisfies it. The ledger itself is described in [money-and-ledgers](../../security-foundation/references/money-and-ledgers.md).

**Verify:** with an exact balance N, a test fires N+k parallel spends on the real database (`#[navree::test(database = "postgres")]` when the app uses PostgreSQL): exactly N succeed and the balance never goes below 0; the reconciliation reports nothing broken.

### 23. Make money-moving and record-creating requests idempotent

**Scope:** payments, purchases, credit adjustments, order creation, imports, refunds.

JSON routes that a Next.js front end, a Tauri client or a partner calls: Navree handles no inbound `Idempotency-Key`; the app builds it. Keep the first response for 24 hours per actor, route and key (a unique index); a repeat replays it with `Idempotent-Replayed: true`; a concurrent repeat answers 409 `idempotency_in_progress`; the same key with a different body answers 409 `idempotency_key_reused` (the API never answers 422); a handler error releases the key. Clients send one key per user action and reuse it on retry. A Navree UI form sends no such header; its runtime ignores a second identical submit while the first is on its way, which does not cover a retry or a second tab. So the form carries a one-time token, built in three parts: a hidden field in the form struct (`#[form(widget = hidden)]`, a `token` field), given its value on each render with `FormView::with_values(..)` (declaring the field and also calling `FormView::hidden` draws the input twice), and the token stored with the write under a unique index. A repeat post with the same token answers like the first and changes nothing. Re-validate time-limited discounts at payment.

**Verify:** JSON routes: a test sends the same keyed request twice at once and once later: one effect, one replay; a different body gets 409 with its code. Navree UI forms: a test posts the same form with the same token twice, as a client without the runtime would: one effect. At the QA gate, a double-click on every money button makes one effect.

### 24. Publish live updates only after the commit

**Scope:** live regions, real-time channels, notifications.

A nudge inside a unit of work waits for the commit; a job is queued only if the request commits; a worker broadcasts through `dyn Broadcaster` with the same `APP_KEY` (`Realtime::broadcast` from a worker reaches nobody). Topics are scoped by workspace and carry ids, not data. Read `navree-events-and-broadcasting`.

**Verify:** a test with `send_stream()` sees no nudge for a rolled-back write and one for a committed write; a member of another workspace receives nothing.

### 25. Prove native clients on a device

**Scope:** Tauri clients (and Navree Native if the operator chose it).

A type check and a web build do not prove that an app installs, signs in, survives a token refresh, handles the keyboard and system insets, or shows notifications. The client itself is built per [design-to-tauri](../../design-to-tauri/SKILL.md).

**Verify:** the debug build installed on an emulator or phone, each module's main flow driven with `adb` (or the iOS simulator), screenshots and logcat with no app error; the `verify-done.mjs` Tauri checks `PASS`; platforms that could not be run recorded as `NOT RUN`, which blocks until the operator accepts it in `ACCEPTANCES.md`.
