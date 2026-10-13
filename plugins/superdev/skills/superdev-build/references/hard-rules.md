# Hard Rules — failures that already shipped once

Every rule below was learned on a real project built with SuperDev (ForgeMyTool/ForgeMesh, PostMitra, 4Brokr, June 2026) and originally recorded in that project's `.claude/memory/superdev-learned/`. They live here now because project-siloed lessons did not prevent the *same* bug on the *next* project (rule #2 was learned on ForgeMyTool on 2026-06-20 and still hit PostMitra). Read this file before building; the checks are part of [`verify-done.mjs`](../../../scripts/verify-done.mjs) where automatable.

## Runtime truth beats static green

### 1. Boot the built artifact, every module — green tests prove nothing about boot

Run `node apps/api/dist/main.js` and `curl /health` + `/health/ready` (DB up) after every backend module. PostMitra had **119 unit + 15 e2e tests passing and `turbo build` green while the production binary was dead on arrival**. Jest hides boot failures twice: `moduleNameMapper` runs TS source (not the built exports), and `Test.createTestingModule` never executes `main.ts`.

### 2. Never call `patchNestJsSwagger()` with @nestjs/swagger 11

`nestjs-zod@4.3.1`'s `patchNestJsSwagger()` deep-imports `@nestjs/swagger/dist/services/schema-object-factory`, which swagger 11 no longer exports — the app crashes on boot (both ForgeMyTool and PostMitra). Use `ZodValidationPipe` for validation; wrap `SwaggerModule.setup` in try/catch so doc generation can never crash boot. Only reintroduce with a verified compatible version pair, proven by rule #1.

### 3. The contracts package builds as CommonJS (Nest.js stack)

A CommonJS Nest app `require()`-ing an ESM-only `@<scope>/contracts` (`"type": "module"`, import-only exports) throws `ERR_PACKAGE_PATH_NOT_EXPORTED` at boot. Build contracts with `module: "CommonJS"`, `moduleResolution: "node10"`, no `"type": "module"`, and `exports` covering `require`/`import`/`default` → `./dist/index.js`. Next.js consumes it via `transpilePackages`. Never flip it back.

### 4. Contracts have one owner and come first — the parallel race rule

When backend and frontend are built against a contract created *in the same step*, the frontend cannot see it and invents a local schema; demo mode passes, production parsing fails, and typecheck/build see nothing (PostMitra Wave 6, `InsightsView`). Author all view shapes in `packages/contracts` up front; the frontend imports the canonical type and **must not** define a local `z.object`/`z.discriminatedUnion` for a server view (form/filter input schemas may stay local). New shape mid-build → contracts first, rebuild, then code.

### 5. Cross-cutting decorators must sit where the framework reads them — verify the side effect

A Nest interceptor/guard resolves metadata from the **controller** handler (`context.getHandler()`). PostMitra shipped **71 `@Audit`-decorated service methods writing 0 `audit_log` rows** because the decorator sat on services. Either put the decorator on the controller method, or make it self-acting (wrapping decorator reading actor/tenant from request context). Then prove it: perform a real mutation and assert the row exists (`SELECT count(*) FROM audit_log` increased). General form: **verify the side effect at runtime, never the decorator's presence** — same for permission checks, metrics, and computed aggregates (presenters must `SELECT COUNT`, never hardcode counts).

## Scaffolding defaults are production defaults

### 6. No default secrets, no unsanitized filesystem routes, no ungated mocks

Scaffolders optimize for "boots out of the box" and silently trade away security (flagged on PostMitra's bootstrap commit):

- Secret env vars (`JWT_*_SECRET`, `S3_*_KEY`, …) get **no `.default()`** in the schema. Use a `NODE_ENV`-gated refine that aborts boot when absent outside development; dev values live only in the gitignored `.env`.
- Any `[...path]` route touching the filesystem validates each segment (`/^[a-zA-Z0-9_-]+$/`), rejects `..`/separators/NUL, and asserts the resolved path stays inside its base dir.
- Demo/mock route handlers register only behind an explicit demo-mode flag and are excluded from production builds.

### 7. Confirm the shadcn backing library before writing components

SuperDev references are Radix-shaped, but a project may run **base-nova on `@base-ui/react`** (PostMitra: `"style": "base-nova"` in `components.json`, 54 primitives importing `@base-ui/react`). On Base UI: **no `asChild`** — compose with the `render` prop (a React element); menu items use `onClick`, not `onSelect`; state classes use `data-open`/`data-active`, not `data-[state=...]`; `FormControl` is render-prop; tooltips need a provider ancestor. Before writing any component, read one existing `components/ui/*` primitive and mirror an existing usage. A missing primitive gets copied from a sibling app — never `shadcn add` the Radix version into a Base UI project.

### 8. drizzle-kit gets its own tsconfig target

`drizzle-kit generate` crashes with `Invalid target "es2023"` reading a shared tsconfig whose target its bundled esbuild rejects (ForgeMyTool bootstrap). Give drizzle-kit its own tsconfig/config with `target: "es2022"` (or a JS config) and prove `db:generate` emits SQL before calling the first backend module done.

### 9. Client-mounted libraries fail only in the browser — smoke them

`@react-three/fiber` v8 on React 19 throws `ReactCurrentOwner` undefined the moment `<Canvas>` mounts; `tsc`, `next build`, and eslint all pass (ForgeMyTool; fix: `@react-three/fiber@^9` + `@react-three/drei@^10`, zero API changes). Rule: pin React-19-compatible majors for reconciler-based libs, and **browser-smoke every route that client-mounts canvas/WebGL/charts/editors** with zero console errors. A green build is not evidence these routes work.

## Operator-facing product rules

### 10. No raw JSON in operator UI

Admin/operator surfaces are run by non-developers. Never ship raw JSON textareas, key-value blobs, or magic-number sentinels (`999999999` = unlimited) — render structured controls (number/text inputs, switches, selects, "Unlimited" toggles) with plain-language labels and readable summaries (4Brokr, 2026-06-27). A "structured form + advanced JSON escape hatch" still fails; an advanced editor is an explicit product decision, not a default. Smell test: grep operator apps for `Textarea`, `JSON.stringify`, `JSON.parse`, `<pre>` in config UIs.

### 11. One canonical public origin for every public URL

Public links (microsites, share links, profiles) come from a single dedicated public origin (apex domain, e.g. `NEXT_PUBLIC_PUBLIC_SITE_URL` or a shared contracts constant) — never from dashboard/app env vars (`*_APP_URL` is for authenticated handoffs). 4Brokr's admin showed `app.4brokr.com/broker/…` while every public surface showed `4brokr.com/broker/…`. When you touch a public URL builder, grep the other apps and confirm identical output for the same entity.

### 12. Secrets and live providers stay out of tests and commits

Live API keys live only in the gitignored server `.env`; never in committed files or client bundles (grep the client output for key absence before shipping AI features). Tests/CI use stub adapters — never call a real paid provider from a test suite. Verify a provider integration once, live, by hand (record endpoint, auth header, exact working payload, and real model names — do not guess model IDs), then env-gate the real adapter behind key presence with the stub as no-key fallback.

## Applying these rules

- **Step 3 (bootstrap):** #3, #6, #7 (detect at scaffold), #8, #9 (pins).
- **Step 4 (contracts):** #3, #4.
- **Step 5 (build loop):** #1, #2, #5, #9 after every module; #10, #11 on every operator/public surface.
- **Step 6–7 (audits + verify):** `verify-done.mjs` automates #1 (boot+curl when a dist exists) and the suppression/placeholder sweeps; auditors explicitly check #5 side effects and #4 local view schemas.
