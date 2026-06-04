# Inertia variant — backend deltas when the frontend is Inertia

Read this when the orchestrator's **Step A.5c** chose `frontend_stack == Inertia` (the default for the Laravel option). It describes how the backend changes versus the **decoupled Next.js** default this skill otherwise assumes. The frontend itself is built by the [`design-to-laravel`](../../design-to-laravel/SKILL.md) skill.

## What stays exactly the same

Everything that makes this an enterprise backend is **unchanged**:

- CockroachDB via the stock `pgsql` driver, UUID PKs (`gen_random_uuid()`), the 40001 serialization-retry wrapper, additive migrations (`cockroachdb-eloquent.md`).
- `#[Audit]` attribute → `AuditManager` → SQS `AuditWrite` job → partitioned `audit_logs` (`audit-attribute.md`).
- `BelongsToWorkspace` global-scope tenancy + the cross-workspace 404 test (`multitenancy-global-scope.md`).
- Title-Case PHP string-backed enums (`enums-title-case.md`).
- `spatie/laravel-permission` + Policies for authorization (`auth-sanctum-permissions.md` — the role/permission/Policy parts).
- Database-backed cache + sessions, SQS queues (`db-cache-sessions.md`, `sqs-queues.md`).

## What changes (decoupled Next.js → Inertia monolith)

| Concern | Decoupled Next.js (this skill's default) | **Inertia monolith** |
|---|---|---|
| App layout | `apps/api` (Laravel) + `apps/web` (Next.js) | **One Laravel app**; frontend in `resources/js/` (no `apps/web`) |
| Auth | **Laravel Sanctum tokens** (cross-domain, `Authorization: Bearer`, CORS) | **Laravel Fortify (session)** — login/register/reset/2FA scaffolded by the React starter kit |
| Response shape | JSON API; `spatie/laravel-data` → TS in `packages/contracts`, fetched via TanStack Query | **Inertia props**: controllers `return Inertia::render('page', $props)`; types hand-written in `resources/js/types/` (no `packages/contracts`, no `typescript:transform`) |
| Authorization surface | `#[Authorize]` on JSON API controllers | `#[Authorize]` on the **Inertia controllers**; permissions also shared as `auth.permissions` props for UI gating (see `design-to-laravel/references/auth-fortify-permissions.md`) |
| Session driver | (tokens; sessions optional) | **`SESSION_DRIVER=database`** (CockroachDB) — required for stateless Lambda |

## Auth: Fortify session instead of Sanctum tokens

For the Inertia monolith, **do not** issue Sanctum personal-access tokens. The React starter kit ships **Laravel Fortify** session auth (login/register/password-reset/2FA pages already built). Keep `spatie/laravel-permission` + Policies on top — only the *identity/session* mechanism changes (Fortify session cookie instead of a bearer token). Share `auth.user` + resolved permissions to the frontend via `HandleInertiaRequests::share` (snippet in `design-to-laravel/references/auth-fortify-permissions.md`).

> If you genuinely need both a first-party Inertia UI **and** a token API for mobile/third-party, you can add Sanctum tokens alongside Fortify — but that is out of scope for the default monolith; document it explicitly if requested.

## Contracts: props, not `packages/contracts`

In the monolith there is no shared TS contract package. Controllers shape exhaustive, view-ready props (the same view-shape discipline — counts default to 0, related entities populated, discriminated unions, ISO dates) and the frontend types them by hand in `resources/js/types/`. `spatie/laravel-data` may still be used **server-side** for request validation and for shaping the props object, but it is **not** the emitted FE contract source here. Keep the controller's `Inertia::render` props and the hand-written types in lockstep.

## Anti-patterns

- ❌ Issuing Sanctum tokens for the first-party Inertia frontend — use Fortify session.
- ❌ Building a separate `apps/web` / `packages/contracts` for the monolith — the frontend is `resources/js/` in the same app.
- ❌ Returning JSON from controllers meant to render pages — use `Inertia::render`.
- ❌ Forgetting `SESSION_DRIVER=database` — file/`/tmp` sessions don't survive across Lambda invocations.
- ❌ Dropping `#[Authorize]` because the UI already hides the button — the server check is the real guard.
