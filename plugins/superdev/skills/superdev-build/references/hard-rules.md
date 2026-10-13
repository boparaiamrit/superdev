# Hard Rules — reusable build and verification requirements

Read these rules before building. Apply each rule to the stack and configuration actually in use, and record its verification result. Static checks, runtime checks, and product audits cover different failure modes; none substitutes for the others.

Public documentation and bundled guidance contain no real project names, customer domains, local paths, incident dates, or customer metrics. Keep private provenance in project-local memory. Promote only the failure mechanism, applicable conditions, corrective action, and a reproducible check. Do not restore the removed conductor, hooks, agent-copy installers, or completion ledgers.

## Runtime and contract verification

### 1. Boot the built artifact after each backend module

**Scope:** Backend modules and their production entry points, on the selected stack.

Build and start the artifact using the actual production command. For the default Nest.js layout, run `node apps/api/dist/main.js`; for Laravel, start the configured application runtime. Source-based test imports and test application factories do not exercise the production entry point.

**Verify:** With required infrastructure healthy, request the configured health and readiness endpoints, then exercise a real module endpoint. Confirm the process stays alive and inspect its logs. Record the command and results.

### 2. Use supported validation and API-documentation integration

**Scope:** Nest.js projects using Zod and Swagger.

Do not scaffold `patchNestJsSwagger()` or private deep imports into Swagger internals. Use `ZodValidationPipe` and documented integration supported by the installed dependency versions. Keep optional documentation initialization isolated from application startup; report failures instead of silently hiding them. Required documentation must pass verification.

**Verify:** Build and boot the production artifact, submit valid and invalid request bodies, and request the generated documentation when enabled. A package-version change requires repeating these checks.

### 3. Match contracts to the backend module format

**Scope:** Shared TypeScript contracts consumed by the default CommonJS Nest.js backend.

Build contracts as CommonJS with a working `require` export and matching output paths. Do not expose import-only ESM exports to a CommonJS consumer. Keep frontend imports pointed at the same canonical package. An intentional module-format migration must cover all consumers, build configuration, tests, and verification together.

**Verify:** Load the built contracts from the backend's built entry point, boot the API, and build the frontend. Source aliases in a test runner are insufficient evidence of package-export compatibility.

### 4. Author canonical contracts before feature code

**Scope:** API responses and frontend consumers sharing a wire contract.

Give contracts one owner. Define all planned view shapes before building their modules, and import the canonical types and runtime schemas. Do not invent local response schemas in the frontend; form and filter input schemas may remain local. For a new shape during implementation, update and rebuild contracts before either consumer. Build dependent modules sequentially.

**Verify:** Compare an actual production-mode response with the shared schema and render it through the frontend. Check for duplicate local response schemas and conflicting exports.

### 5. Verify permissions and side effects at runtime

**Scope:** Mutations, audit logging, authorization, metrics, and computed aggregates.

Put metadata where the framework reads it. A Nest.js interceptor using `context.getHandler()` reads the controller handler, so a service-only `@Audit` annotation is insufficient unless the decorator executes its own logging. Compute aggregates from the real data source rather than fixture constants.

**Verify:** Perform an authorized mutation and inspect the resulting `audit_logs` row, including actor and tenant. Attempt a denied mutation and confirm no unauthorized change occurs. Compare aggregate output with source data. The presence of a decorator is not proof of its effect.

## Scaffolding and dependency requirements

### 6. Require secrets, constrain filesystem access, and gate mocks

**Scope:** Environment schemas, filesystem-backed routes, and demo adapters.

Do not provide default credentials in source or schemas. Require production credentials through server environment or secret storage. Validate filesystem path segments, reject traversal and separators, and prove resolved paths stay within the permitted base directory. Enable demo/mock routes only in explicit demo mode and exclude them from production builds.

**Verify:** Missing required production secrets prevent startup or explicitly disable the dependent feature. Traversal requests cannot read outside the permitted directory. Production requests cannot reach demo routes or silently receive fixture data.

### 7. Confirm the installed shadcn backing library

**Scope:** Frontend components composed from shadcn primitives.

Inspect `components.json`, installed dependencies, and existing primitive imports. A style such as `base-nova` is a hint; the installed implementation is the source of truth. Mirror its composition API. Do not copy Radix `asChild` patterns into Base UI components or install an incompatible primitive. Reuse a sibling implementation only after checking compatibility.

**Verify:** Typecheck and browser-test the composed component, including open/close behavior, selection events, keyboard interaction, and provider requirements. Use the actual installed component API.

### 8. Keep migration tooling compatible with its compiler

**Scope:** Projects using drizzle-kit.

If migration tooling rejects the application's TypeScript target, isolate its configuration with a supported target, such as `es2022`, rather than changing the whole application blindly. Check the installed tooling's accepted configuration; an `es2023` rejection is a compatibility condition, not a universal ban on that target.

**Verify:** Run `db:generate` or the configured migration-generation command and inspect the emitted SQL before completing the first backend module.

### 9. Verify client-mounted libraries in the browser

**Scope:** Routes mounting canvas, WebGL, charts, editors, or custom React reconcilers.

Choose dependency versions compatible with the installed React major and with one another. A successful typecheck or server build does not prove that a browser-mounted component works. Avoid treating a previously working version pair as a permanent recommendation.

**Verify:** Open each affected route against the running application, mount and interact with the component, and inspect console and network errors. Verify production-mode loading as well as development rendering.

## Product and provider requirements

### 10. Use structured controls in operator interfaces

**Scope:** Configuration surfaces used by non-developer operators.

Use labeled inputs, switches, selects, readable summaries, and explicit controls for states such as unlimited. Do not require raw JSON, opaque key-value blobs, or numeric sentinels for routine operation. A developer-oriented editor requires an explicit product requirement and appropriate validation.

**Verify:** Complete the configuration task through the UI without editing JSON or knowing internal field names. Inspect validation, saved values, and the resulting behavior. Source searches identify candidates; inspect their user-facing purpose before deciding they violate this rule.

### 11. Use the configured canonical origin for public links

**Scope:** Public-site links generated by dashboards, APIs, and other applications.

Use one dedicated public-site origin, such as `NEXT_PUBLIC_PUBLIC_SITE_URL`, consistently across link builders. Keep authenticated application origins separate. The public origin may use an apex domain or a configured subdomain; do not derive it from an unrelated dashboard setting.

**Verify:** Generate the same public entity link from each application and compare the result. Open it without an authenticated dashboard session and verify it reaches the intended public surface.

### 12. Keep provider credentials private and production behavior explicit

**Scope:** Live provider integrations, tests, logs, and saved lessons.

Keep keys in server-side secret storage or gitignored environment files, never in committed files, client bundles, logs, or memory. Automated tests use stubs. A live integration probe requires task authorization and a configured test account. Record the endpoint shape, header names, redacted payload, supported model identifier, and result; never record authentication-header values or customer payloads.

**Verify:** Check client output and saved artifacts for secret leakage. Confirm tests use stub adapters. A required production integration with missing credentials must fail clearly or be explicitly disabled; it must not silently fall back to a demo stub.

## Applying these rules

- **Bootstrap:** apply #3, #6, #7, #8, and #9 to the selected stack.
- **Contracts:** verify #3 and #4 before implementing consumers.
- **Module loop:** verify #1, #2, #5, and #9 where applicable; check #10 and #11 on operator and public surfaces.
- **Audits and completion:** [`verify-done.mjs`](../../../scripts/verify-done.mjs) checks configured package scripts, default Nest.js boot/health, contracts format, forbidden Swagger patch calls, suppressions, and placeholders. It does not prove all 12 rules or Laravel runtime readiness. Record the remaining browser, database, security, and stack-specific evidence separately.
