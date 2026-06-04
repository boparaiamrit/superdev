# Pages, Props & Routing (Inertia)

This is the spine of the Inertia path: a Laravel route hits a controller, the controller returns `Inertia::render('<page>', $props)`, Inertia resolves a React component from `resources/js/pages/`, and that component receives `$props` as typed React props. There is **no client router, no fetch layer, no REST contract** — routing is server-driven and data arrives as props.

If you are coming from `design-to-nextjs`, this is the single biggest mental shift. See `references/claude-design-to-inertia.md` for the full idiom-by-idiom mapping.

---

## The round trip

```
GET /companies
  → routes/web.php          Route::get('/companies', [CompanyController::class, 'index'])
  → CompanyController@index  return Inertia::render('companies/index', ['companies' => ...])
  → Inertia resolves         resources/js/pages/companies/index.tsx
  → React renders            export default function CompaniesIndex({ companies }) { ... }
```

The first argument to `Inertia::render` is a **page name**, not a URL and not a file path with an extension. Inertia maps it to `resources/js/pages/<name>.tsx` (the default resolver lowercases nothing and keeps your slashes — `'companies/index'` → `resources/js/pages/companies/index.tsx`). Keep the page name and the file path in lockstep.

---

## Controllers return `Inertia::render`

```php
// app/Http/Controllers/CompanyController.php
use Inertia\Inertia;

class CompanyController
{
    public function index(): \Inertia\Response
    {
        return Inertia::render('companies/index', [
            'companies' => CompanyData::collect(
                Company::query()->withCount('contacts')->paginate()
            ),
        ]);
    }

    public function show(Company $company): \Inertia\Response
    {
        return Inertia::render('companies/show', [
            'company' => CompanyData::from($company->loadCount(['contacts', 'leads'])),
        ]);
    }
}
```

Rules that keep the frontend honest:

- **Shape the props in the controller**, not the page. Eager-load relations (`withCount`, `loadCount`, `with`) and project to a view shape so the page never has to guard for missing data.
- **Counts default to numbers.** `withCount('contacts')` always yields an integer (0 when empty) — the page renders `{c.counts.contacts}` with no `?.` or `?? 0`.
- **Enum values arrive Title-Cased and render directly** — no label maps. (See `references/typed-props.md`.)
- The prop keys you pass here are the prop names the page destructures. They are the contract — and that contract is hand-written in `resources/js/types/` (decision D4), so it is your job to keep `Inertia::render`'s shape and the type file in lockstep.

> An **Eloquent API Resource** is used here only to **shape the data on the backend**. It is NOT the frontend type source for the Inertia path — frontend types are hand-written. See `references/typed-props.md`.

---

## Pages live in `resources/js/pages/`

A page is a normal React component with a **default export**. It receives the controller's props as its props.

```tsx
// resources/js/pages/companies/index.tsx
import { Link, usePage } from '@inertiajs/react'
import AppLayout from '@/layouts/app-layout'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { CompanyView, Paginated } from '@/types/companies'

export default function CompaniesIndex({ companies }: { companies: Paginated<CompanyView> }) {
  const { auth } = usePage().props
  return (
    <AppLayout>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Companies</h1>
        {auth.permissions.includes('company.create') && (
          <Button asChild><Link href="/companies/create">New company</Link></Button>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {companies.data.map((c) => (
          <Card key={c.id} className="p-4">
            <div className="font-medium">{c.name}</div>
            <div className="text-muted-foreground">{c.industry}</div>
            <div>{c.counts.contacts} contacts</div>
          </Card>
        ))}
      </div>
    </AppLayout>
  )
}
```

Page conventions:

- **One default export per page file** (Inertia resolves the default export). Everything else in the file is a named local helper or — better — lives in `resources/js/components/<feature>/`.
- **Pages stay thin** (≤ 100 lines per `frontend-modular-architecture`). Compose feature components; don't inline tables, forms, or business logic.
- **Destructure typed props.** `{ companies }: { companies: Paginated<CompanyView> }` — never `(props: any)`.
- Use `@/` to reach `resources/js/` (the starter kit ships this alias). `@/pages`, `@/components`, `@/layouts`, `@/lib`, `@/types`, `@/hooks`.

---

## Persistent layouts

The React starter kit ships **`app-layout.tsx`** plus sidebar/header variants (built on the shadcn **sidebar block**). Wrapping a page in `<AppLayout>` works, but it remounts the layout on every navigation. For a layout that **persists across navigations** (sidebar scroll position kept, no re-mount flash), assign it to the page instead:

```tsx
// resources/js/pages/companies/index.tsx
import AppLayout from '@/layouts/app-layout'
import type { ReactNode } from 'react'

function CompaniesIndex({ companies }: { companies: Paginated<CompanyView> }) {
  return (/* ...page body, no <AppLayout> wrapper... */)
}

CompaniesIndex.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default CompaniesIndex
```

Layout variants shipped by the starter kit:

| Layout | Use for |
|---|---|
| `app-layout.tsx` (sidebar) | Authenticated app shell — sidebar nav + header. The default for feature pages. |
| header/sidebar variants (`app/*`) | Choose sidebar vs. top-header chrome; sidebar `inset` / `floating` variants per the shadcn block. |
| auth layouts (`auth/*` — simple / card / split) | Login / register / reset screens (Fortify pages already use these). |

Do **not** hand-roll an `<aside>` or a bespoke shell — reuse the shipped layouts so the sidebar block stays the single source of chrome (`ui-auditor` flags hand-rolled shells). Pick the layout that matches the Claude Design's chrome; restyle via Tailwind tokens, not by replacing the layout.

> Next.js `app/layout.tsx` files map to these Inertia persistent layouts — see the mapping table in `references/claude-design-to-inertia.md`.

---

## `<Link>` for navigation

Client-side navigation uses Inertia's `<Link>` (from `@inertiajs/react`). It issues an XHR visit, swaps the page component, and updates history — no full page reload, no client router config.

```tsx
import { Link, router } from '@inertiajs/react'

// declarative
<Link href="/companies/create">New company</Link>
<Link href={`/companies/${c.id}`} className="font-medium hover:underline">{c.name}</Link>

// methods other than GET
<Link href={`/companies/${c.id}`} method="delete" as="button">Delete</Link>

// programmatic (e.g. after a non-form action)
router.visit('/companies')
router.delete(`/companies/${c.id}`)
```

- A plain `<a href>` triggers a full reload — only use it to leave the app. **Inside the app, always `<Link>`** (or `router`).
- For state-changing navigation use `method="post|put|patch|delete"` (with `as="button"` so it renders an accessible button). For actual create/edit **forms**, use `useForm` — see `references/forms-useform.md`.
- Wrap a shadcn `Button` around a `Link` with `asChild`: `<Button asChild><Link href="...">…</Link></Button>`.

---

## Wayfinder — typed route helpers

Wayfinder generates **type-safe route helpers from your Laravel routes at build time**, so you reference routes by name with autocomplete and compile-time checks instead of hand-typing URL strings.

```tsx
import { show, create } from '@/routes/companies'   // generated from companies.* named routes
import { Link } from '@inertiajs/react'

<Link href={create()}>New company</Link>
<Link href={show(c.id)}>{c.name}</Link>
```

Operational rules — these are where Inertia builds most often break:

- **Build-time, not runtime.** Wayfinder reads your routes and emits TS helpers during the Vite build. The generated definitions are a snapshot.
- **Regenerate on every route change.** Add, rename, or change the signature of a route and the helpers are stale until you regenerate. Run the Wayfinder generate step (or a fresh `npm run build`, which runs it) after editing `routes/web.php`. Treat a route edit and a Wayfinder regenerate as one atomic change.
- **Disable unused Fortify feature routes to avoid build failures.** The Fortify scaffold registers routes for features you may not use (2FA, teams, email verification, etc.). If those feature routes are disabled in `config/fortify.php` but Wayfinder still tries to emit helpers for them — or vice versa — the build can fail. Keep `config/fortify.php`'s enabled features and the routes Wayfinder generates in sync: turn off the Fortify features you don't use so no helper is generated for a route that doesn't exist.
- Plain string `href`s (`href="/companies"`) remain valid and are fine for a handful of static links. Prefer Wayfinder helpers for parameterized routes and anywhere a route rename should fail the build.

---

## Shared props (`HandleInertiaRequests`)

Some props are needed by **every** page — the authenticated user, their resolved permissions, flash messages. Rather than pass these from each controller, the starter kit shares them globally from `app/Http/Middleware/HandleInertiaRequests.php`. Read them with `usePage().props`:

```tsx
import { usePage } from '@inertiajs/react'

const { auth } = usePage().props
auth.user            // { id, name, email } | null
auth.permissions     // string[]  — gate <Link>/buttons in the UI
```

The exact `HandleInertiaRequests::share` snippet (auth.user + resolved permissions), the `#[Authorize]` controller pattern, and the rule that **UI gating is convenience while the server `#[Authorize]` is the real guard** all live in `references/auth-fortify-permissions.md`. This page only consumes the shared `auth` prop; that page defines it.

---

## The route snippet

Feature routes go behind the **`auth` + `verified`** middleware group so every Inertia page in the group requires an authenticated, email-verified session (Fortify):

```php
// routes/web.php
Route::middleware(['auth','verified'])->group(function () {
    Route::get('/companies', [CompanyController::class, 'index'])->name('companies.index');
    Route::get('/companies/create', [CompanyController::class, 'create'])->name('companies.create');
    Route::post('/companies', [CompanyController::class, 'store'])->name('companies.store');
});
```

- **Always name routes** (`->name('companies.index')`) — Wayfinder helpers and `route()` calls key off the name, and a named route is what survives a URL refactor.
- The `auth` middleware enforces a session (Fortify); `verified` requires a verified email. Public pages (the Fortify login/register screens) live **outside** this group.
- Authorization (who may do *what*) is layered on top with `#[Authorize]` / Policies — middleware gets you "logged in", `#[Authorize]` gets you "allowed". See `references/auth-fortify-permissions.md`.

---

## Pitfalls

- **`?.` / `??` on prop fields.** If you reach for `companies.data?.map` or `c.counts?.contacts ?? 0`, the controller failed to guarantee the shape. Fix the controller (eager-load, default counts to numbers), not the page. The "no `?.`" discipline (D4) is the whole point of typed props.
- **A page name with an extension or a leading slash.** `Inertia::render('companies/index')`, never `'companies/index.tsx'` or `'/companies/index'`.
- **Plain `<a href>` inside the app.** Full reload, lost SPA state. Use `<Link>` / `router`.
- **Hand-rolled layout shells.** Reuse the shipped `app-layout.tsx` + sidebar block; restyle with tokens.
- **Stale Wayfinder helpers after a route edit.** Regenerate (or `npm run build`) after every change to `routes/web.php`; keep `config/fortify.php` features and generated route helpers in sync to avoid build failures.
- **Client-side data fetching.** No `fetch`, no `@tanstack/react-query`, no `axios` in a page to load server data — data is a prop. For refreshing a subset of props use Inertia partial reloads (`router.reload({ only: [...] })`); see `references/state-and-data.md`.
- **Next.js routing idioms** (`next/link`, `next/navigation`, file-based `app/.../page.tsx` routes). These do not exist on the Inertia path — they appear only in the translation table in `references/claude-design-to-inertia.md`, never as the way to do it here.
