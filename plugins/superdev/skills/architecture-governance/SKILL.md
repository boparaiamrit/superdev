---
name: architecture-governance
description: Use when deciding how a Navree app scales, which workloads belong in HTTP versus queues or schedules, how modules depend on each other without cycles, what belongs on the backend versus the frontend, how backend layers stay single-responsibility, how payloads are bounded against hostile input, or how user stories define pass and reject cases before code.
---

# Architecture governance

This skill sets the structural rules that keep a growing Navree product fast, clean and safe under real traffic and hostile inputs. It applies at step 3 (plan), step 5 (contracts) and step 6 (modules) of [superdev-build](../superdev-build/SKILL.md), and on its own whenever an operator asks to review architecture, scaling, workers, module boundaries, input ceilings or test coverage. Framework facts stay in Navree's installed skills; this skill states the decisions the framework leaves to the product, rules GOV-1 to GOV-8, and the checks that prove them.

## Navree skills to read

- `navree-modules-and-di`: module exports, dependency wiring and graph checks (`navree check`).
- `navree-queues-and-scheduling`: `QueueModule`, workers, retries, failed jobs and `ScheduleModule`.
- `navree-events-and-broadcasting`: domain events, listeners and post-commit live channels.
- `navree-database`: unit of work, transactions in jobs, keyset pagination and TimescaleDB hypertables.
- `navree-validation`: `Valid<..>`, field length and value bounds, custom validation rules.
- `navree-security-checklist`: request body limits, headers, auth and workspace isolation.
- `navree-ui` and `navree-native`: server-drawn UI components and native composition.
- `navree-testing`: `TestApp`, HTTP tests, job tests and database assertions.
- `navree-module-conformity`: `navree check` and `navree gate`.

## Rules

**GOV-1** Declare the app's scale tier (`T1`, `T2` or `T3`) in `EXECUTION_PLAN.md` `## Scaling and workers` and match database indexing, pagination, caching and worker pools to it ([references/scaling-and-workers.md](references/scaling-and-workers.md)). Admin tables stay bounded at `per_page <= 100` (rule BE-7); append-only event, audit and high-volume lists use keyset cursors (`navree-database`); time-ordered telemetry uses TimescaleDB hypertables with time-range predicates (rule BE-16).
Proof: `EXECUTION_PLAN.md` names the scale tier; every list query in the contract specifies offset or cursor paging and its supporting index.

**GOV-2** Assign every non-trivial workload to one of five execution classes (`sync-http`, `async-queue`, `scheduled-cron`, `isolated-worker` or `sse-stream`) using the selection matrix in [references/scaling-and-workers.md](references/scaling-and-workers.md). A queue worker runs outside HTTP middleware and guards: every workspace job payload carries `workspace_id`, and every query in the job scopes by it explicitly (rule BE-17, hard rule 27).
Proof: `EXECUTION_PLAN.md` `## Scaling and workers` lists the execution class of each background, bulk, scheduled or streaming workload; each workspace job has a test proving it cannot read or change another workspace's rows.

**GOV-3** Keep the backend-versus-frontend ownership boundary explicit ([references/stories-and-srp.md](references/stories-and-srp.md), hard rule 28). Authentication, authorization, workspace scoping, business invariants, server-derived fields (computed totals, resolved emails, UTC timestamps, risk scores), filtering and sorting over server datasets, payload ceilings and audit writes always live on the backend. Frontend clients own responsive layout, draft state, inline server validation display, optimistic rollback on 409, accessibility and lazy loading.
Proof: direct HTTP requests bypassing the UI cannot forge `workspace_id`, alter server-derived fields or bypass access checks.

**GOV-4** Decompose each backend module by single responsibility ([references/stories-and-srp.md](references/stories-and-srp.md), rule BE-19). Transport handlers parse `Valid<..>` inputs, invoke a service and map errors without embedding domain rules or raw SQL; policies own authorization; services take `&Uow` and enforce invariants and transactions; repositories or query modules isolate data access; worker jobs isolate async execution; cross-module facades expose narrow typed ports.
Proof: handlers delegate business decisions to services; `navree check` exits 0; no handler mixes multi-step business calculations and raw database queries.

**GOV-5** Place every module in one of four hierarchy tiers in `EXECUTION_PLAN.md` `## Modules`: `0` Kernel and platform foundation, `1` Core identity and shared libraries, `2` Domain execution engines, `3` Intelligence, automation and reporting ([references/scaling-and-workers.md](references/scaling-and-workers.md), hard rule 26). A module depends only on same-or-lower-tier modules through their exported service facades (`navree-modules-and-di`); a lower tier never imports a higher tier and never queries another module's database tables directly (rule BE-18). Upward notifications use domain events (`navree-events-and-broadcasting`).
Proof: `verify-done.mjs` check `module dependency graph` reports zero cycles, zero tier inversions and zero build-order inversions; `navree check` exits 0.

**GOV-6** Enforce hard input ceilings and adversarial validation before domain logic runs ([references/stories-and-srp.md](references/stories-and-srp.md), rule BE-20, hard rule 29). Cap JSON bodies (default 64 KB, 413 on exceed), multipart uploads (per contract, 413 on exceed), JSON nesting depth (max 16) and plain-text field lengths; refuse `<script>`, `javascript:` and null bytes in plain-text fields (stored rich text uses Navree's sanitizer per hard rule 14); refuse prototype-pollution keys (`__proto__`, `prototype`, `constructor`) at Next.js and BFF JSON boundaries; refuse self-parent or circular hierarchy edges (`A -> B -> A`).
Proof: committed unit tests and the adversarial probes of [dynamic-probes.md](../security-review-and-fix/references/dynamic-probes.md) assert 400, 413 or 422 with zero stored rows.

**GOV-7** Every `contracts/<module>.md` defines a `## Stories` table mapping each user story (`US-n`) and route to BOTH observable `Must pass` outcomes and explicit adversarial `Must reject` cases ([references/stories-and-srp.md](references/stories-and-srp.md), hard rule 30).
Proof: `verify-done.mjs` check `contract stories` passes; every `Must pass` and `Must reject` row is exercised by `cargo test` (`navree-testing`) or a committed suite.

**GOV-8** Choose how to build UI in four rungs ([references/stories-and-srp.md](references/stories-and-srp.md)): (1) reuse existing Navree UI or design-system kit components; (2) compose higher-level screens declaratively from existing components or Navree Native views without hand-written markup; (3) add a focused composable behavior primitive (focus trap, keyboard navigation, viewport-clamped popover, drag-and-drop) when the UI stack lacks it; (4) build a fault-isolated lazy screen widget only after documenting any gap per hard rule 14.
Proof: zero raw markup violations (`verify-done.mjs` `Navree UI raw markup` and `Navree UI gap rows`), and every new UI pattern passes desktop (1440 px), mobile (390 px), light and dark checks.

## Reference files

| File | Read when |
|---|---|
| [references/scaling-and-workers.md](references/scaling-and-workers.md) | Planning scale tiers, choosing execution classes and worker isolation, and verifying the 4-tier module hierarchy |
| [references/stories-and-srp.md](references/stories-and-srp.md) | Splitting backend and frontend responsibilities, laying out single-responsibility backend roles, enforcing input ceilings, authoring `## Stories` pass/reject tables and applying the 4-rung UI ladder |
