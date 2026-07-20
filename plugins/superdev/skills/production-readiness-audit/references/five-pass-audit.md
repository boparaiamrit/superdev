# The five passes — dispatch prompts

The orchestrator dispatches these. Scanning passes (1, 2, 5-static) are read-only and run in parallel. Browser passes (3, 4) need the stack up in production mode. Every dispatch is prefixed with relevant lessons from `.claude/memory/superdev-learned/`.

Each pass agent writes a per-module score line into its report:
`MODULE <name>: <0-10> — <one-line reason>` so `module-readiness-rater` can aggregate.

## Precondition — seed first

```
Use the seed-data-architect agent.
Produce a deterministic seeder that creates: an initial product OWNER/ADMIN user
with a known login, realistic per-module volumes (not 3 rows — hundreds where a
real tenant would have them), and a SECOND tenant with overlapping data for the
tenancy test. No aggregate may be hardcoded — counts/totals come from the rows.
The product must work with demo mode OFF. Output: db/seed.* + SEED.md (logins,
volumes, how to run). Verify: fresh DB → seed → owner can log in → dashboards
show non-zero real numbers.
```

## Pass 1 — Completeness & wiring (parallel, read-only)

```
Dispatch in parallel, each scoped to ALL modules, each emitting per-module scores:
- placeholder-hunter          → PLACEHOLDER_HITS.md
- route-completeness-checker  → ROUTE_COMPLETENESS.md   (stack up, production mode)
- wiring-auditor              → WIRING_AUDIT.md
- data-flow-real-vs-mock      → DATA_SOURCE_AUDIT.md
Score 9–10 only if a module has zero placeholders, every interactive element is
wired to a real API, and no demo-fallback fires on a success path.
```

## Pass 2 — Data realism & seed (read-only + DB check)

```
Use data-flow-real-vs-mock (HYBRID focus) + verify the seed:
- Every screen reads REAL data in production mode; flag every HYBRID (real shell,
  hardcoded field) — these are the dangerous ones.
- Confirm the seed produces realistic volumes and a working owner login.
- Grep for hardcoded aggregates (return 0 / count: 0 / length of a literal).
Emit per-module scores → DATA_REALISM.md.
```

## Pass 3 — Tenancy isolation (browser + API, stack up)

```
Use the tenancy-isolation-tester agent.
With the two seeded tenants (A, B), for EVERY module attempt cross-tenant access:
direct :id GET/PATCH/DELETE with B's IDs while authed as A (expect 404/403, never
200), list/search/export endpoints (expect only A's rows), bulk ops, any webhook
or public token path, and UI deep-links to B's resources. DB-verify nothing of
A's was mutated/read. ANY leak caps that module at ≤3.
Output: TENANCY_REPORT.md with per-module scores + each leak as file:line + repro.
```

## Pass 4 — End-to-end via Playwright (stack up, production mode)

```
Dispatch (batched at 6), each scoped per module:
- route-walker     → every route loads, 200 + no console errors, screenshot
- qa-flow-tester   → every FORM: validate → submit → persist → re-render; happy +
                     13 edge categories (empty/loading/error/large-data/slow-net/
                     validation/concurrent/stale/long-content/special-chars/
                     keyboard/mobile/a11y). DB-verify every persist.
- journey-walker   → top journeys with reload + relogin + role-switch, DB cross-check
- data-flow-tracer → DB → repo → service → presenter/Resource → contract → hook →
                     component for every entity; flag any undefined/mismatch on the wire
Score 9–10 only if EVERY route and EVERY form passed and FE↔BE shapes match.
Output: E2E_REPORT.md with per-module scores + screenshots/traces per finding.
```

> Coverage is exhaustive, not sampled: every route and every form. If the module
> has 14 forms, all 14 are exercised. A sampled pass is not a Pass-4 pass.

## Pass 5 — Code quality & security (static, parallel)

```
Dispatch in parallel:
- static-auditor          → authz on every mutation, input validation vs contract,
                            secrets, injection → per-module scores
- dependency-auditor      → CVEs / lockfile
- ui-auditor              → shadcn-only, no forbidden imports, no raw primitives
- module-structure-auditor→ no god-files, store/folder discipline
PLUS run the no-suppressions check: zero new eslint-disable/@ts-ignore/as any/
@phpstan-ignore vs the build base. Lint + typecheck must be ZERO-error with no
suppressions. Any suppression caps the module at 7; any P0 caps it at ≤3.
Output: QUALITY_SECURITY.md with per-module scores.
```

## After the passes — rate, then fix

```
Use the module-readiness-rater agent → READINESS.md + READINESS_CHECKLIST.md and
update COMPLETION_LEDGER.json (per-module readiness_score, gates.readiness).
For each module < 9, dispatch the matching fixer on its checklist items:
- backend-module-builder / laravel-module-builder  (API gaps, authz, tenancy scope)
- frontend-module-builder / frontend-rewirer / inertia-module-builder  (wiring, states, shapes)
- security-fixer  (P0/P1 security)
Fix the ROOT CAUSE. No suppressions. No new demo data. Then re-run only the
sub-9 passes for those modules. Repeat until all ≥ 9 or round 5 is reached.
```
