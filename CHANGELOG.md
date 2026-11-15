# Changelog

All notable changes to Superdev are documented here. Releases are annotated git tags (`vX.Y.Z`) on `main`; from v2.0.0 they are also published as GitHub Releases with the packaged `superdev.zip` attached.

## v3.0.0 — 2026-11-15

Superdev now builds products on Navree, a Rust application framework, with Navree UI screens or a Next.js front end on the Navree API, and optional Tauri clients. Navree's own skills hold the framework facts; superdev keeps the order of work, the files on disk, the rules and the proofs, and names the Navree skill and command for each fact. NestJS and Laravel are no longer supported; version 2.1.0 stays available for them, and a project already on 2.1.0 pins its marketplace to `v2.1.0` (below) so an update does not bring 3.0.0.

Status: 3.0.0 was used once to build a two-module Navree UI app on SQLite with the published Navree 1.2.2, through all ten steps, on a host without a browser, so the browser proofs of steps 6 and 8 were `NOT RUN`; the done check ran against the real Navree CLI; what that build showed was fixed in the same release. It has not yet been used with a Next.js front end, a native client, a server database or a real deployment.

### Changed

- `superdev-build` runs ten steps: Navree and the app, digests, plan, foundation, contracts, modules, audits, QA gate, deployment, done. The app is created with `navree new` (or an existing Navree app is taken as it is) and Navree's skills are installed before any other file; `STACK.md` records the exact `navree new` line, the front end, the database and `base_commit`.
- A module's contract is `contracts/<module>.md`, agreed by the operator, and then the module's first commit: models, request types with their validation, list specs, and every route with its access declaration. For a Next.js front end it adds the generated OpenAPI document and TypeScript types. The shared contracts package is gone.
- Every step has a proof; each module's proofs are quoted in the `## Build order` table of `EXECUTION_PLAN.md`. `AUDIT.md` is now `GAPS.md`.
- The hard rules are rewritten for Navree: 25 rules, each with its scope and the check that proves it.
- One severity scale (`Blocker`, `Major`, `Minor`, `Note`), one set of check results (`PASS`, `FAIL`, `NOT RUN`), one list of artifact names and one order of steps across every skill and agent, defined in `superdev-build/references/artifacts.md`.
- `security-foundation` says, for each control, what Navree provides, what the app still builds and the committed test that proves it. Sign-out and revocation follow the client: a Navree UI browser session ends at once, a token client's refresh is refused at once and its access token ends within its lifetime; staff are global roles, not a separate user table.
- `verify-done.mjs` runs Navree's checks: `navree --version` against `STACK.md`, the installed skills, `cargo fmt`, `cargo clippy`, `cargo test`, `navree check`, `navree config:check`, the release build and its health routes. It checks the Next.js front end only when `STACK.md` says so (a missing `lint` or `test` script is `NOT RUN`), keeps the Tauri checks, and adds the checks `Navree UI raw markup`, `Navree UI gap rows` and `public routes`. Its suppression sweep diffs against `base_commit` instead of `HEAD`, so a committed suppression now fails, and it also reads lint settings in configuration files. Suite lines in `STACK.md` must be `cargo test` commands, and a missing `STACK.md` or an empty `test_database_url` for a server database fails. It has `--help`, `--base`, exit code 2 for usage errors, and the labels `PASS`, `FAIL` and `NOT RUN`.
- Agents have four frontmatter keys (`name`, `description`, `tools`, `model`) and receive absolute paths from the skill that dispatches them. Renamed: `data-flow-real-vs-mock` to `data-source-auditor`, `learn-from-frustration` to `lesson-writer`, `module-conversion-planner` to `refactor-planner`, `design-fidelity-auditor` to `visual-diff-auditor`.
- The tests read counts from disk and pass on Linux and Windows: `.github/workflows/tests.yml` runs them and the package check on both for every pull request and every push to `main`. Text files are stored with LF line endings.
- `superdev.zip` is built by `tools/build_zip.py`.
- The installer's `--verify` looks for the plugin id `superdev@superdev`.
- `verify-done.mjs` reads the release binary: `public routes` runs `<target>/release/<binary> routes --json` (the binary the boot check starts; `CARGO_TARGET_DIR` is honoured) and compares it with the plan's `Public routes` bullet both ways, and the new `first address (GET /)` check fails when the booted binary answers `GET /` with a 404 or a 5xx.
- `verify-done.mjs` reads the flow's files: the plan's `Status: CONFIRMED` line, `Status: AGREED` in the contract of every module, and a tracked `Cargo.lock`. With `--strict` it also reads `SECURITY_REPORT.md`, `AUDIT_REPORT.md`, `QA_COVERAGE.md` and the plan's `## Build order` (no open `Blocker` or `Major` finding, no `NOT RUN` without an acceptance; a `## Findings` section holds a table with the columns `Severity` and `State`, or `None.`). Exit 0 means that no check failed; only a `--suites --strict` run that ends `DONE` means done: without `--suites` the suites are `NOT RUN`, which `--strict` fails, and any other run ends with a line that says what passed and that steps 7 and 8 were not checked.
- `--suites` runs the `cargo test` lines of `STACK.md` without polling a running app, so `--api-url` and `--health-url` are gone. The full run is made on the last commit that changes code and its output, `qa/verify-done.txt`, is committed after it.
- An acceptance is the operator's entry in `ACCEPTANCES.md`; reports, the matrix and the build order cite its `ACC-n`, and the main agent and every agent never write one (rule BLD-6). The done check holds each entry to a number of its own and a commit of its own, also when the app is one folder of a larger repository.
- Step 1 lists what the starter brings and decides keep, rename or remove with the operator; step 4 removes it as its first commit, rewrites `README.md` and `AGENTS.md`, owns `GET /`, commits `Cargo.lock` and builds the release path of the roles and the first account (rule BE-14). The production check is `APP_ENV=production navree config:check --env production`, which a SQLite app cannot pass.

### Added

- Skills `backend-on-navree`, `design-to-navree-ui`, `product-audit` (inventory, completeness and score modes), `product-qa` (explore and gate modes), `frontend-structure` and `prototype-to-navree`.
- Agents `navree-app-bootstrapper`, `navree-module-builder`, `navree-ui-screen-builder` and `nextjs-module-builder`.
- The gap rule for Navree UI: a missing component is composed from Navree UI components or proposed to Navree, never drawn with hand-written markup, a stylesheet or a script; Navree UI's raw building blocks serve only stored rich text, the app's own fixed images and icons, and token-only stylesheets, each named in a gap row and checked by `verify-done.mjs`.
- The deploy checklist, `superdev-build/references/deploy-checklist.md`, for Harbor, a container image or processes set up by hand.
- `install-superdev.sh --here`, for an app that is one folder of a larger repository: the project is the folder the command is run from, which is where Claude Code keeps a project's plugins.
- `verify-done.mjs --fast`, which runs only the checks that build nothing, for use while building; the first full run compiles the app in three profiles and is run detached.
- `ACCEPTANCES.md` in `artifacts.md`, the operator's own file, and the row `PASS (6.5 NOT RUN, ACC-n)` and the evidence levels `PASS (server)` and `PASS (Q-n)` for a build on a host without a browser.
- A no-browser recipe for the runtime proof of a Navree UI module (sign in through the form, keep the cookie, send `X-XSRF-TOKEN`, follow no redirect), in `design-to-navree-ui`.

### Removed

- `nestjs-enterprise-backend`.
- `laravel-enterprise-backend`, `design-to-laravel`, `laravel-bref-deploy`, the Inertia variants, and the builders `laravel-module-builder` and `inertia-module-builder`.
- `brutal-exhaustive-audit`, `product-completeness-audit` and `production-readiness-audit`, merged into `product-audit`; `exploratory-qa` and `release-qa-gate`, merged into `product-qa`; `frontend-modular-architecture` and `frontend-refactoring`, merged into `frontend-structure`; `prototype-to-saas`, replaced by `prototype-to-navree`.
- 23 agents, merged into others or no longer dispatched: `atomic-module-converter`, `audit-synthesizer`, `backend-extractor`, `backend-module-builder`, `contracts-author`, `conversion-verifier`, `data-flow-tracer`, `design-source-mirror`, `edge-case-prober`, `flow-walker`, `frontend-module-builder`, `frontend-rewirer`, `integration-tester`, `module-behavior-snapshotter`, `monorepo-bootstrapper`, `portal-correctness-auditor`, `route-completeness-checker`, `route-walker`, `security-fixer`, `security-inventory`, `wiring-auditor`, and the two Laravel builders.
- The dual-mode demo adapter and mock routes: demos run on the real app with the seed.
- The `db:seed` and `db:fresh` package scripts: `navree migrate:fresh --seed` resets the data.
- `docs/superpowers/`, the plans and specs of earlier versions.
- The installer's `--enable-teams` flag.
- The hard rules for NestJS, Drizzle and the shadcn backing library; the shadcn check lives in `design-to-nextjs`.

### Staying on 2.1.0

NestJS and Laravel projects keep version 2.1.0. Install it in such a project with:

```shell
claude plugin marketplace add boparaiamrit/superdev#v2.1.0 --scope project
claude plugin install superdev@superdev --scope project
```

A project already on 2.1.0 added the marketplace without the pin: uninstall superdev from the project (`claude plugin uninstall superdev@superdev --scope project`, as the helper's `--uninstall` does), then run the two lines above. Adding the marketplace with the pin replaces its unpinned source; this was tried with Claude Code 2.1.302. `INSTALL.md` has the steps, and what to mind when one machine holds a 2.1.0 project and a 3.0.0 project.

## v2.1.0 — 2026-10-25

Native clients, security built in from bootstrap, and a release QA gate where every coverage cell cites evidence.

### Added

- **`design-to-tauri`** — Tauri 2 desktop, Android and iOS clients in the monorepo on the shared contracts. References cover:
  - scaffolding and toolchains, including Android insets, camera intents, back-button handling and the iOS-on-macOS boundary;
  - shell security: CSP, least-privilege capabilities, exact HTTP origins, keystore-held refresh tokens, release flags, deep-link and QR validation, WebView passkey limits;
  - mobile token auth with single-flight refresh, blocked handling and idempotency keys;
  - SSE live updates and local notifications, with the background limits stated plainly;
  - an `adb`-driven device QA playbook (emulator setup, physical phones, WebView contrast checks, stored-secret check, QA-signed release smoke), and store release;
  - a debug-only capability set for emulator origins, OS-protected refresh-token storage in debug and release, and the server endpoints to add when an API has only cookie sign-in.
- **`security-foundation`** — the security layer every build implements at bootstrap and in every module:
  - sessions checked on every request (instant revocation, blocking with a reason);
  - refresh rotation with family theft detection and a same-browser tab grace;
  - TOTP with encrypted secrets and replay protection, hashed one-time recovery codes, bound challenges, passkeys, a device list and QR sign-in;
  - a separate staff identity with permission keys, escalation guards, and masked personal data with audited reveal;
  - per-account balance locks, idempotency keys, discount re-validation, expiring entitlements and a reconciliation of ledger invariants;
  - a transactional outbox with authenticated SSE streams, and a notification service with preferences, grouping and web push;
  - platform hardening, and the committed runtime suites (`test:contract`, `test:security`, `test:admin`, `test:credits`, `test:realtime`) that prove each control;
  - a starting permission catalog with default roles, precise escalation definitions, fail-closed and rate-limited reveals, and lock ordering for limited items.
- **`release-qa-gate`** — the final pass on a fresh seed:
  - committed suites, route × role × viewport × theme, forms, links and dialogs;
  - axe plus computed contrast in every interactive state;
  - security behaviours in the browser, money races, live updates across clients, and the device pass.
  - every step has an owner agent and a matrix section; parallel agents get their own accounts and devices; the commit is recorded so stale cells are re-run;
  - the output is `QA_COVERAGE.md`, where a cell without evidence is `NOT RUN` and blocks release like `FAIL` until the operator accepts it.
- **Six agents:** `mobile-qa-tester`, `a11y-contrast-auditor`, `role-matrix-tester`, `money-integrity-prober`, `realtime-prober`, `link-crawler`.
- **Hard rules #13–#18:**
  - check the session on every request;
  - serialize balance changes per account;
  - make money-moving requests idempotent;
  - publish live updates inside the writing transaction;
  - do not trust correlated subqueries in single-table ORM selects;
  - prove native clients on a device.

### Changed

- **`superdev-build`:**
  - asks which clients the product needs (web, staff admin, Tauri);
  - plans a `## Security` section;
  - lays the security foundation in the bootstrap skeleton;
  - verifies Tauri modules on a device and extends the committed suites per module;
  - always ends with `release-qa-gate` and `verify-done.mjs --suites`.
- **`verify-done.mjs`:**
  - boots the built API on a free port, so a running dev stack does not collide;
  - checks every Tauri shell (CSP, wildcard HTTP scopes, remote capabilities, devtools on release);
  - with `--suites` (and `--api-url`), runs every committed `smoke`/`test:*` script against the running stack;
  - adds a `WARN` status and `--strict`, which fails on any warning or skipped check, for release claims;
  - sweeps every client app (mobile and desktop included) for placeholder content.
- **`security-review-and-fix`:** static checks §21–28 and dynamic probes §13–19 cover the new controls, and Phase 3 dispatches the role-matrix, money and real-time agents.
- **`superdev-done`**, **`exploratory-qa`**, **`production-readiness-audit`** and **`brutal-exhaustive-audit`** point to the new gate.
- **`nestjs-enterprise-backend`**, **`laravel-enterprise-backend`** and **`design-to-nextjs`** defer the identity, staff and client-refresh model to `security-foundation`.
- **`superdev-build`** defines `db:seed` and `db:fresh` at bootstrap.
- **Integrity tests** cover the new skills, agents, hard rules 1–18, the build wiring, and the Tauri shell checks behaviourally (an open shell fails, a locked-down one passes).

## v2.0.1 — 2026-10-13

- Public READMEs, release guidance, and bundled skills describe generic requirements without real project names, customer domains, incident anecdotes, or private metrics.
- All 12 hard rules now state their applicable scope and verification. Dependency guidance follows the installed stack; credentials and saved evidence must be redacted, and production integrations cannot silently substitute demo stubs.
- Self-learning retains redacted provenance in project-local memory and promotes only the generic mechanism, scope, corrective action, and verification check. Removed conductor, hooks, agent-copy installers, and completion ledgers remain removed.
- Validation instructions cover Windows/WSL path handling, and regression checks cover public attribution, generic domains, and hard-rule scope/verification fields. The packaged plugin is refreshed.

## v2.0.0 — 2026-10-13

**The conductor is removed.** Superdev v2 uses direct sequential builds, canonical contracts, and live runtime verification. The main agent executes the recipes and uses standalone audits; agent copies, bash hook machinery, and self-graded completion ledgers are removed.

### Added

- **`superdev-build` skill** — the full-build SOP executed by the main agent: plan artifacts (`PRD_DIGEST` / `DESIGN_DIGEST` / `AUDIT` / `EXECUTION_PLAN`) → user confirmation → stack choice (Nest.js/Laravel × Next.js/Inertia) → bootstrap proven by boot → **all contracts first** → one module at a time (backend → boot-the-dist + curl + side-effect verify → frontend → browser verify) → standalone audits → verify-done.
- **`hard-rules.md`** (`superdev-build/references/`) — the 12 production failure lessons promoted out of per-project memory: boot the built artifact, never `patchNestJsSwagger()`, CommonJS contracts, contracts single-owner/upfront, verify side effects not decorators, no default secrets / unsanitized fs routes / ungated mocks, Radix-vs-Base-UI detection, drizzle-kit tsconfig, browser-smoke client-mounted routes, no raw-JSON operator UI, one canonical public origin, secrets hygiene.
- **`scripts/verify-done.mjs`** — cross-platform (Node) live Definition-of-Done: per-package typecheck/lint/build, boots `apps/api/dist` and polls health endpoints, contracts module-format + `patchNestJsSwagger` landmine checks, no-new-suppressions sweep vs git HEAD, demo/placeholder sweep. `superdev-done` now runs it.
- **`tests/test_plugin_integrity.py`** — guards frontmatter, skill links, documented counts (18 skills / 54 agents), zip parity, and regressions (removed machinery, taught boot crashes).

### Changed

- Recipes fixed at the source: NestJS scaffolding/validation no longer call `patchNestJsSwagger()` (boot crash on @nestjs/swagger 11; docs setup is try/catch-guarded), contracts package builds as **CommonJS** with `require` exports, `@Audit` guidance now places the decorator on **controller handlers** with a runtime side-effect proof, env schema warns against secret defaults, the dual-mode mock route sanitizes path segments and is demo-gated, and `design-to-nextjs` requires confirming the shadcn backing library (Radix vs Base UI) before composing components.
- `production-readiness-audit`: every 1–10 score must cite its command/browser/DB evidence (uncited = 0); state lives in `READINESS.md` only.
- `superdev-self-learning`: deliberate, manual lesson capture (no hooks); transferable technical rules are promoted into `hard-rules.md`.
- Build order language is dependency **groups** built **sequentially** everywhere (plan format, builders, migration) — no parallel backend+frontend work against a same-step contract.
- All bundled-resource references are plugin-relative; the v1.8.1 project-scoped install contract (installer helper, `--scope project`, tests) is retained and its docs updated to v2.

### Removed (breaking)

- `prd-design-build-orchestrator` skill and its references (execution/audit pipelines, orchestration patterns, embedded agent copies). The artifact formats live on under `superdev-build/references/artifacts-format.md`.
- Agent-extractor installers (`install-core/qa/security/migration-agents.sh`, `extract-agent.py`) and their stale embedded agent copies — `agents/*.md` are the single source and are auto-loaded by the plugin; nothing is copied into target projects.
- The bash hook machinery (`hooks/`): done-gate Stop sentinel + completion ledger, wave-gate, stack-up check, frustration detection, per-dispatch lesson threading. Verification is explicit (`verify-done.mjs`, per-module runtime checks). Existing projects may delete `.claude/.superdev-orchestrating`, `.claude/.superdev-donegate-attempts`, and `COMPLETION_LEDGER.json`.
- "Agent teams" 3-teammate debate sections from skills (the plan-review value is kept as a single-pass three-lens self-review in `frontend-refactoring`). The installer's `--enable-teams` flag remains available as a host setting.

### Migration from v1.x

- Reinstall at project scope: `claude plugin marketplace add boparaiamrit/superdev --scope project` + `claude plugin install superdev@superdev --scope project` (or `bash /path/to/superdev/install-superdev.sh`).
- Prompts that said "use the orchestrator / build the full-stack app" now route to `superdev-build`. Standalone skill invocations are unchanged.
- Projects with copied agents under `.claude/agents/` (from the old installers) can delete the stale copies — the plugin's `agents/` are canonical.
- Replace any `COMPLETION_LEDGER.json` done-checks with `node <plugin>/scripts/verify-done.mjs`.

## v1.8.1 — 2026-07-20

Project-scoped Superdev: installation and activation live in the target repository (Claude `--scope project`, Codex repository marketplace); bundled resources resolve from the plugin root; learning stays project-local; `tests/test_project_scope.py` enforces no global/personal Superdev paths.

## v1.8.0 — 2026-06-20

Production-readiness-audit: scores every module 1–10 across five passes and loops fix → re-audit until every module is 9+. Requires real seed data + an initial owner/admin user, demo-mode OFF, and a multi-tenancy leak test. New agents: module-readiness-rater, tenancy-isolation-tester, seed-data-architect (18 skills / 54 agents).

## v1.7.0 — 2026-06-20

Completion ENFORCED (done-gate) + Laravel/Inertia merge.

## v1.6.0 — 2026-06-04

Laravel backend reworked to PostgreSQL + TimescaleDB + Eloquent API Resources (dropping CockroachDB + spatie/laravel-data); `audit_logs` hypertable; hand-written TS contracts.

## v1.5.0 — 2026-06-04

design-to-laravel (Claude Design → Laravel + Inertia 3 + React 19 monolith), frontend-stack gate (Inertia vs Next.js). 16 skills / 51 agents.

## v1.4.0 — 2026-06-03

Laravel backend option (laravel-enterprise-backend + laravel-bref-deploy), backend-stack selection gate. 15 skills / 50 agents.

## v1.3.1 — 2026-05-26

Earlier release (see git history).
