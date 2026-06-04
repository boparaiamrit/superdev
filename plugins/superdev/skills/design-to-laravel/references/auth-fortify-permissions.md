# Auth: Fortify session + spatie/permission (Inertia)

How authentication and authorization work in the Inertia monolith, and how the React frontend reads permissions to gate UI. Read in the forms + auth wiring phase.

This is the **Inertia path** — auth is **Laravel Fortify (session-based)**, NOT Sanctum tokens. (Sanctum Bearer tokens are the decoupled Next.js path; do not introduce them here.) The roles/permissions/Policy machinery is shared with the backend skill — see `laravel-enterprise-backend/references/auth-sanctum-permissions.md` for the spatie matrix, Policy classes, and registration. This file covers only the Inertia-specific deltas: session identity, the shared-props wiring, and UI gating.

## The model

The Laravel React starter kit ships **Fortify** for identity. Fortify provides the scaffolded `login`/`register`/password-reset/email-verify/2FA routes and screens out of the box, backed by a **server session** (cookie + DB-backed session store). There are no tokens to mint, store, or attach — the session cookie travels automatically.

Authorization happens in the same three layers as the backend skill, with the **only** difference being how identity is established:

- **`auth` (session) middleware** — Fortify's web guard verifies the session and sets `$request->user()`. (The decoupled path uses `auth:sanctum` instead; everything below is identical.)
- **`BelongsToWorkspace` global scope** — workspace tenancy still applies. Every Eloquent query is auto-filtered by `workspace_id`; cross-workspace access 404s. Inertia changes nothing here.
- **Policies + `#[Authorize]`** — the **real guard**. The Policy is the resolution point; the attribute enforces it before the controller body runs.

The frontend reads `auth.permissions` from shared props to **gate `<Link>`/buttons**. That is **UI convenience only** — hiding a button is not security. The server `#[Authorize]` + Policy is what actually protects the action.

---

## Sharing `auth.user` + permissions as Inertia props

Inertia exposes the authenticated user and the resolved permission set to every page via shared props, set in `HandleInertiaRequests::share`. Resolve permissions with spatie's `getAllPermissions()` (roles + direct permissions, deduped) and pluck the names.

```php
// app/Http/Middleware/HandleInertiaRequests.php — share auth.user + resolved permissions
public function share(Request $request): array
{
    return array_merge(parent::share($request), [
        'auth' => [
            'user' => $request->user()
                ? ['id' => $request->user()->id, 'name' => $request->user()->name, 'email' => $request->user()->email]
                : null,
            'permissions' => $request->user()
                ? $request->user()->getAllPermissions()->pluck('name')->values()
                : [],
        ],
    ]);
}
```

Notes:

- **Shape the user explicitly.** Share only `id`/`name`/`email` — never `$request->user()` raw, which would leak `password`, tokens, and internal columns into the HTML payload.
- **`getAllPermissions()`** returns every permission the user holds via any role plus directly-assigned ones. `->pluck('name')->values()` gives a clean, re-indexed `string[]` for the frontend. (Use `getPermissionNames()` if you prefer; either yields names.)
- **`permissions` is always an array** (empty `[]` when logged out), so the frontend reads `auth.permissions.includes(...)` with no `?.`.
- These props are available on **every** page via `usePage().props.auth` — no per-controller wiring needed.

Type the shared `auth` prop once (hand-written, per the typed-props discipline), so pages get autocomplete and the "no `?.`" rule holds:

```ts
// resources/js/types/index.ts — shared (global) Inertia props
export interface AuthUser {
  id: string
  name: string
  email: string
}

export interface SharedProps {
  auth: {
    user: AuthUser | null      // null only on guest pages; gated routes guarantee non-null
    permissions: string[]      // always present, never undefined
  }
  [key: string]: unknown
}
```

Register it as the default `PageProps` in `resources/js/app.tsx` (the starter kit's `usePage<SharedProps>()` or a typed `usePage` wrapper) so every page sees `auth` typed.

---

## The controller: `#[Authorize]` + `Inertia::render`

A feature controller returns an Inertia response instead of a JSON `Data` collection, but the authorization attribute is **identical** to the backend skill. Fortify's session handles login; spatie + `#[Authorize]` gate the action.

```php
// a feature controller — Fortify handles login/session; spatie + #[Authorize] gate the action
use Illuminate\Routing\Attributes\Controllers\Authorize;

class CompanyController
{
    #[Authorize('viewAny', Company::class)]
    public function index(): \Inertia\Response
    {
        return Inertia::render('companies/index', [
            'companies' => CompanyData::collect(Company::query()->withCount('contacts')->paginate()),
        ]);
    }
}
```

The same rules from the backend skill apply unchanged:

- **Every public controller method is authorized** — `#[Authorize(...)]` (preferred, runs before the body) or `$this->authorize(...)` inside the body when the decision needs loaded data. No "obviously safe" exceptions.
- **The Policy is the resolution point.** `CompanyPolicy::viewAny` checks `$user->can('company.read')`; `view`/`update`/`delete` additionally check the workspace match as defense-in-depth. Don't hand-roll `hasRole()` checks in the controller.
- **A failed Policy check** throws `AuthorizationException` → Laravel renders a 403. With Inertia, that surfaces as an Inertia error response, not a JSON body.
- **Policy classes, the permission seeder, the User-model `HasRoles` trait, and Policy registration are shared** with the decoupled path — author them per `laravel-enterprise-backend/references/auth-sanctum-permissions.md`. The User model keeps `HasRoles` + `BelongsToWorkspace`; for the Inertia monolith it does **not** need `HasApiTokens` (no Sanctum tokens).

The controller shapes the data passed into `Inertia::render` with an **Eloquent API Resource**, but the **frontend contract** is the hand-written prop type in `resources/js/types/`, not generated TS — see `typed-props.md` and decision D4.

---

## Gating the UI by permission (convenience only)

Pages read `auth.permissions` to show or hide actions. This keeps the UI honest (don't show a "Delete" button to a Viewer) but is **never** the security boundary — the matching `#[Authorize]` on the controller is.

```tsx
import { Link, usePage } from '@inertiajs/react'
import { Button } from '@/components/ui/button'
import type { SharedProps } from '@/types'

export default function CompaniesHeader() {
  const { auth } = usePage<SharedProps>().props
  const canCreate = auth.permissions.includes('company.create')   // no ?. — permissions is always string[]

  return (
    <div className="flex items-center justify-between">
      <h1 className="text-2xl font-semibold">Companies</h1>
      {canCreate && (
        <Button asChild>
          <Link href="/companies/create">New company</Link>
        </Button>
      )}
    </div>
  )
}
```

For repeated checks, a tiny `usePermissions` hook reads the same shared prop:

```tsx
// resources/js/hooks/use-permissions.ts
import { usePage } from '@inertiajs/react'
import type { SharedProps } from '@/types'

export function usePermissions() {
  const { permissions } = usePage<SharedProps>().props.auth
  return {
    can: (name: string) => permissions.includes(name),   // permissions is always an array
  }
}
```

```tsx
const { can } = usePermissions()
{can('company.delete') && <Button variant="destructive" onClick={onDelete}>Delete</Button>}
```

The golden rule: **for every permission you gate in the UI, the corresponding controller action carries an `#[Authorize]` that checks the same Policy.** UI gating and server authorization are two expressions of one permission — keep them in lockstep.

---

## How this differs from the decoupled (Next.js) path

This table exists only to map the decoupled idioms to the Inertia equivalents — the right-hand column is the Inertia way; do not bring the left column into Inertia pages.

| Decoupled Next.js path | Inertia monolith (this skill) |
|---|---|
| `auth:sanctum` + `Authorization: Bearer <token>` | Fortify **session** cookie (set automatically) |
| Token issued by an `AuthController::login` action | Fortify's scaffolded `login` route + screen |
| Token stored in client state, attached per fetch | No token — the session cookie travels with every request |
| NextAuth / a token client wrapper | `usePage().props.auth.user` (shared prop) |
| `GET /me` returns `UserData` JSON, fetched on load | `auth.user` already in shared props on every page |
| `User` model uses `HasApiTokens` | `User` model omits `HasApiTokens` (keeps `HasRoles`) |
| Permissions fetched into the SPA via an endpoint | `auth.permissions` resolved server-side into shared props |

**Identical across both:** the spatie permission matrix/seeder, Policy classes, `#[Authorize]` attribute usage, `BelongsToWorkspace` tenancy (cross-workspace 404), Title-Case role names. Author them once per `auth-sanctum-permissions.md`.

---

## Anti-patterns

- **Treating UI gating as security.** Hiding a `<Link>`/button is convenience. Without the matching `#[Authorize]` on the controller, the action is wide open to anyone who knows the route. Always gate the server first.
- **Sharing the raw User model.** `'user' => $request->user()` leaks `password`/tokens/internal columns into the page HTML. Always project to an explicit `id`/`name`/`email` shape.
- **Reaching for Sanctum tokens in the Inertia path.** No `HasApiTokens`, no `createToken`, no `Authorization: Bearer`. Fortify's session is the identity mechanism here; tokens belong to the decoupled Next.js path only.
- **`?.` / `??` on `auth.user` or `auth.permissions`.** `permissions` is always an array, and gated routes guarantee `auth.user` is non-null — type it and access it directly. (Guest-only pages are the one place `auth.user` is legitimately `null`; handle that with an explicit branch, not optional chaining sprinkled everywhere.)
- **Hand-rolled role checks in controllers/pages.** `if ($user->hasRole('Admin'))` or `auth.permissions.includes('admin')` as a stand-in for a real permission is a Policy bypass. Gate on the specific permission (`company.create`), resolved by the Policy server-side.
- **Re-translating Fortify's auth screens from the Claude Design.** Reuse the scaffolded login/register/reset pages as-is unless the design explicitly specifies custom auth screens (see `forms-useform.md`). Don't rebuild what the starter kit already ships.
- **Forgetting tenancy because "it's a monolith now."** `BelongsToWorkspace` still applies in the Inertia path exactly as in the decoupled path — every query is workspace-scoped and cross-workspace access 404s. Inertia does not relax tenancy.
- **Resolving permissions per-controller instead of in `share`.** Put `auth.user` + `auth.permissions` in `HandleInertiaRequests::share` once so every page has them; don't re-pass them as page-specific props.
