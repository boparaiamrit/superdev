# Production-readiness rubric (per module, per pass)

Each pass scores a module 0–10 on its dimension. The module's overall score is the **minimum** across passes (a module is only as ready as its weakest dimension). Two findings are **hard caps** — they force the module to ≤3 regardless of other passes: a cross-tenant leak (Pass 3) and a P0 security/data-loss bug (Pass 5).

The bands below are written so that **9–10 means genuinely shippable**. Do not award 9 to be nice — if a paying user would hit the gap, it is ≤8 and goes back into the loop.

## Universal bands

| Score | Meaning |
|------:|---------|
| 9–10 | Production-ready. A paying user can rely on this today. At most cosmetic nits that don't affect use. |
| 7–8  | Works in the happy path but has real gaps (an unwired action, a missing empty/error state, a hardcoded count, a flaky form). NOT done. |
| 4–6  | Demo-grade. Looks right but core paths are mocked, partially wired, or break on reload/edge input. |
| 1–3  | Broken or disqualified. Doesn't function, OR a hard-cap finding (tenancy leak / P0 security / data loss) applies. |
| 0    | Module absent or non-functional. |

## Pass 1 — Completeness & wiring

- **9–10**: every route renders real backend data; every button/form/menu/link triggers a real API call and reflects the result; no `TODO`/`coming soon`/`alert()`/`console.log("clicked")`/stub handlers; no demo-fallback fires on a success path.
- **7–8**: one or two interactive elements are not wired, or a secondary route still shows a placeholder.
- **≤6**: a primary route is a placeholder, or core actions are fire-and-forget / local-state-only.

## Pass 2 — Data realism & seed

- **9–10**: fresh DB + `db:seed` yields realistic volumes and a working initial owner/admin login; every aggregate (`*_count`, totals, rollups) is computed from the DB; the product works fully with demo mode OFF.
- **7–8**: seed exists but is thin/unrealistic, OR one aggregate is still hardcoded, OR the initial user requires manual steps to create.
- **≤6**: product only works in demo mode, no seedable login, or screens read from local fixtures in production mode.

## Pass 3 — Tenancy isolation  (hard cap)

- **9–10**: with ≥2 tenants holding overlapping data, every cross-tenant attempt fails correctly — direct `:id` access (IDOR), list endpoints, search, export, bulk ops, webhooks, and UI deep-links all scope to the caller's tenant; 404/403 (not 200) for foreign IDs.
- **≤3 (hard cap)**: ANY endpoint or screen returns, mutates, or even confirms the existence of another tenant's data. One leak = release blocker.

## Pass 4 — End-to-end (Playwright)

- **9–10**: every route loads without console errors; every form validates, submits, **persists (DB-verified)**, and re-renders; data created in step 1 is visible after reload/relogin; FE↔BE data shapes match (no `undefined` in any view; contract == API response == UI); happy path + the 13 edge categories handled.
- **7–8**: happy paths pass but some edge states (empty/loading/error/large-data) are missing, or one form doesn't persist on reload.
- **≤6**: a core flow can't be completed end-to-end, or a data-shape mismatch surfaces `undefined`/`NaN`/`[object Object]` to the user.

## Pass 5 — Code quality & security  (P0 = hard cap)

- **9–10**: `lint` and `typecheck` (TS: tsc/eslint; Laravel: Pint/PHPStan) are zero-error with **zero suppressions**; authorization enforced server-side on every mutation; inputs validated against the contract; no secrets in code; no files over the module's size budget.
- **7–8**: clean build but a non-critical authz/validation gap, or a god-file that needs decomposition. **A module with ANY suppression cannot exceed 7.**
- **≤3 (hard cap)**: a P0 — missing authz on a sensitive mutation, injection, secret in code, or a data-loss path.

## Worked example

A `billing` module: Pass 1 = 9, Pass 2 = 9, Pass 3 = 9, Pass 4 = 9, but Pass 5 finds card data hitting the server (PCI P0) → Pass 5 capped at 3 → **module_score = 3**. It does not ship at 8 "because everything else is great". That is the entire point.
