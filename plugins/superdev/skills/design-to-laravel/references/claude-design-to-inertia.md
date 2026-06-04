# Claude Design → Inertia React (the translation)

This is the heart of `design-to-laravel`. It tells you how to turn a Claude Design handoff (HTML, `claude.ai/design` output, or screenshots) into an **Inertia 3 + React 19** page inside the Laravel app — and, just as importantly, what to **drop** so that no Next.js-isms leak in.

The component layer (shadcn primitives + Tailwind tokens) is **identical** to the Next.js path. Do not re-derive it here:

- **Token extraction** — reuse `design-to-nextjs/references/token-extraction.md` verbatim (shadcn CSS-variable extraction is the same).
- **Component substrate** — reuse `design-to-nextjs/references/component-patterns.md` for the shadcn primitive/composite catalog (buttons, cards, tables, dialogs, sidebar block, charts). The *only* deltas are routing, data flow, forms, auth, and the `'use client'` directive — covered below.

The job is not transcription. Claude Design HTML is a **visual specification**; you re-implement the intent against the Inertia + shadcn substrate. If you are pasting `<div class="...">` blocks one-for-one into a page, stop and refactor against a shadcn primitive.

---

## The mapping table

| Claude Design / Next.js idiom        | Inertia React equivalent                                            |
|--------------------------------------|---------------------------------------------------------------------|
| app/.../page.tsx route               | resources/js/pages/<Page>.tsx + Laravel route -> Inertia::render     |
| 'use client' / RSC split             | (none) — Inertia pages are client React; drop RSC directives        |
| next/link, next/navigation           | Inertia <Link>, router (@inertiajs/react)                           |
| next/image                           | plain <img> or a shadcn/Tailwind image component                     |
| TanStack Query / fetch in component  | data arrives as TYPED PROPS from the controller                     |
| react-hook-form + fetch submit       | Inertia useForm() -> form.post/put/delete; errors via form.errors   |
| NextAuth / token client              | Fortify session; usePage().props.auth.user; permissions in props    |
| Next.js layout files                 | Inertia persistent layouts (starter-kit layouts/), sidebar/header   |
| shadcn primitives, Tailwind tokens   | IDENTICAL — reuse design-to-nextjs token-extraction + shadcn refs    |
| Title-Case enum values               | identical on the wire/props; render directly, no label maps         |

Read the right column as the **only** way to express each idiom in this skill. The left column exists to help you recognize what a design (or a copy-pasted Next.js snippet) is doing — never to license shipping it.

---

## Worked example: a "Companies" index page

A Claude Design list view — a header with a "New company" action and a grid of company cards — translates to a single Inertia page that receives **typed props** from the controller. No fetching, no `'use client'`, no TanStack.

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
            <div className="text-muted-foreground">{c.industry}</div>{/* enum value IS the label */}
            <div>{c.counts.contacts} contacts</div>{/* always a number, no ?. */}
          </Card>
        ))}
      </div>
    </AppLayout>
  )
}
```

Note what is **absent** and what that buys you:

- **No `'use client'`.** Inertia pages are already client React — there is no server/client split to annotate. The directive is meaningless here.
- **No `import Link from 'next/link'`.** `Link` comes from `@inertiajs/react`. For programmatic navigation, import `router` from the same package — not `next/navigation`.
- **No `useQuery` / `fetch` / `useEffect`.** `companies` is a prop. The controller already ran the query, eager-loaded relations, and shaped the payload.
- **No `?.` or `??` on prop fields.** `companies.data`, `c.industry`, and `c.counts.contacts` are guaranteed by the typed prop shape and the controller. Reaching for `?.` is a signal your prop type is wrong (or your controller isn't shaping the field).
- **No label map.** `c.industry` is a Title-Case enum value (`"Technology"`) that renders directly.

---

## The rules

### 1. Every prop is typed, and the type is exhaustive

The page's props come from `@/types/<feature>` (hand-written, per spec D4 — see `typed-props.md`). The destructured signature names every prop; the prop types name every field. No optional chaining, no nullish coalescing on prop fields. If a field can be absent, the type says `string | null` and the page handles both arms explicitly — "missing" is not a representable state.

```tsx
// WRONG — optional chaining hides a contract gap
<div>{c.counts?.contacts ?? 0} contacts</div>

// RIGHT — the type guarantees counts is present and contacts is a number
<div>{c.counts.contacts} contacts</div>
```

If you find yourself wanting `?.`, fix the prop type and the controller's `Inertia::render` shape — not the page.

### 2. Enum values render directly — no label maps

Title-Case enum values travel on the wire exactly as stored (`"Technology"`, `"Email Sent"`, `"Won"`) and are usable as labels with zero mapping. Do not build `{ technology: 'Technology' }` lookup objects. The enum value *is* the label. This is the same Title-Case-enum commitment as the rest of the stack — see `typed-props.md` for the discriminated-union pattern when a field carries variant data.

```tsx
// WRONG — label map for an already-human-readable enum
const INDUSTRY_LABELS = { technology: 'Technology', healthcare: 'Healthcare' }
<div>{INDUSTRY_LABELS[c.industry]}</div>

// RIGHT
<div>{c.industry}</div>
```

### 3. Counts default to numbers

A count is always a `number`, defaulted to `0` server-side (e.g. `withCount('contacts')`), never `null`/`undefined` and never rendered through `?.`/`??`. The page can do arithmetic and comparisons on it without guards.

### 4. The controller eager-loads and shapes the props

The page is dumb on purpose; the controller is where data work happens. It eager-loads relations, computes counts, paginates, and returns a payload matching the prop type exactly:

```php
// app/Http/Controllers/CompanyController.php
return Inertia::render('companies/index', [
    'companies' => CompanyData::collect(
        Company::query()->withCount('contacts')->paginate()
    ),
]);
```

The page name (`'companies/index'`) resolves to `resources/js/pages/companies/index.tsx`. The route, the persistent layout resolution, shared props (`auth`), `<Link>` navigation, and Wayfinder typed route helpers all live in **`pages-props-routing.md`** — read it for the routing half of this loop. The hand-written prop types and the "no `?.`" discipline live in **`typed-props.md`**. Auth sharing (`HandleInertiaRequests::share`) and `#[Authorize]` gating live in **`auth-fortify-permissions.md`**.

### 5. Auth and permissions come from shared props

`usePage().props.auth.user` and `auth.permissions` are shared on every request by `HandleInertiaRequests` (see `auth-fortify-permissions.md`). Gate UI affordances — buttons, `<Link>`s, menu items — with `auth.permissions.includes('...')`. This is **convenience only**: the real guard is `#[Authorize]` on the controller. Hiding a `<Link>` is never a substitute for authorizing the action server-side.

```tsx
{auth.permissions.includes('company.create') && (
  <Button asChild><Link href="/companies/create">New company</Link></Button>
)}
```

### 6. Forms go through `useForm`

A create/edit form in the design becomes an Inertia `useForm` form: `form.post('/companies')`, with server validation surfacing in `form.errors`. No `react-hook-form`, no `fetch`, no mutation hooks. See `forms-useform.md`.

---

## Forbidden leakage

These appear in Inertia output **only** as wrong answers. They are the left column of the mapping table — never ship them in `resources/js/`:

- `next/*` imports — `next/link`, `next/navigation`, `next/image`, `next/font`, etc. Use `@inertiajs/react` (`Link`, `router`, `usePage`, `useForm`) and plain `<img>`.
- `'use client'` / `'use server'` directives. Inertia pages are client React; there is no RSC boundary to annotate.
- `@tanstack/react-query` (`useQuery`, `useMutation`, `QueryClient`) and any in-component `fetch`/`useEffect` data fetching. Data is props; mutations are `useForm`. (For genuine client-only UI state, Zustand is fine — see `state-and-data.md`. For refreshing a subset of props, use Inertia partial reloads, `router.reload({ only: [...] })`, not a query client.)
- App Router constructs — `app/` route segments, `page.tsx`/`layout.tsx`/`loading.tsx` files, route groups, parallel/intercepting routes, server components. Pages live in `resources/js/pages/`; layouts are Inertia persistent layouts; routing is Laravel routes + Wayfinder.
- NextAuth / token-based client auth. Auth is Fortify session; identity and permissions arrive as shared props.

`ui-auditor` greps `resources/js/` for `next/`, `use client`, and `@tanstack/react-query`, and flags `?.`/`??` on prop fields. Treat any hit as a translation bug.

---

## Anti-patterns

- **Optional-chaining a prop "just in case."** `c.counts?.contacts ?? 0` is a smell: the prop type is under-specified or the controller isn't shaping the field. Fix the type and the `Inertia::render` payload; keep the page guard-free.
- **Building a label map for a Title-Case enum.** The enum value is already the label. A `LABELS` lookup is dead code and a place for the label and the enum to drift apart.
- **Treating a count as nullable.** `withCount` returns `0`, not `null`. Type it `number`, render it directly.
- **Pasting a Next.js page in and "fixing the imports."** `'use client'`, `next/link`, and `useQuery` are structural, not cosmetic. Re-implement the *intent* as an Inertia page with typed props + `useForm`, don't transliterate.
- **Fetching in the component instead of receiving props.** If a page calls `fetch`/`useQuery`/`useEffect` to load server data, the controller isn't doing its job. Move the query into the controller and pass the result as a prop.
- **Gating only the UI.** Hiding a `<Link>` behind `auth.permissions.includes(...)` without `#[Authorize]` on the controller leaves the action wide open. Always authorize server-side; UI gating is cosmetic.
- **Hand-rolling layout/sidebar.** Use the starter-kit persistent layouts (`@/layouts/app-layout`) and the shipped shadcn sidebar block. Don't author a bespoke `<aside>`.
- **Bypassing shadcn primitives.** Raw `<button>`/`<input>`/`<dialog>` where a shadcn equivalent exists is a regression — same rule as the Next.js path (`component-patterns.md`).
- **Letting prop types drift from the controller.** Because the types are hand-written (D4), an `Inertia::render` change that isn't mirrored in `resources/js/types/` is silent until runtime. Update both together; the `inertia-module-builder` + review enforce lockstep.
