---
name: design-to-laravel
description: Translate a Claude Design handoff (HTML / claude.ai/design output / screenshots) into a Laravel + Inertia 3 + React 19 monolith — the official Laravel React starter-kit stack (TypeScript, Tailwind 4, shadcn/ui incl. the sidebar block). Pages live in resources/js/pages and receive typed props from controllers via Inertia::render; routing is server-driven via Laravel routes + Wayfinder; forms use Inertia useForm; auth is Laravel Fortify (session) plus spatie/laravel-permission with #[Authorize], sharing auth.user and resolved permissions as Inertia props. The frontend is part of the Laravel app (no separate Next.js), deployed serverless on AWS Lambda via Bref (client-only Inertia, Vite assets on S3/CloudFront). This is the DEFAULT frontend for the laravel-enterprise-backend option; the decoupled design-to-nextjs path remains an alternative. Use whenever the user wants a Laravel fullstack frontend, Inertia + React, a Laravel starter-kit UI, or to turn a Claude Design into a Laravel (not Next.js) app.
---

# Claude Design → Laravel + Inertia React Conversion

A pipeline for turning Claude Design output into a production-grade Laravel monolith where the frontend is **React via Inertia**, living inside the Laravel app at `resources/js/`. The skill operates in five phases. Walk them in order; skipping phases produces the throwaway code most "design-to-code" pipelines generate.

This is the **Inertia path** — the default frontend for the Laravel backend option. The component layer (shadcn primitives, Tailwind tokens) is the same craft as `design-to-nextjs`; the *delta* is how data, routing, forms, and auth work. Here data arrives as **typed props** from controllers (not client fetches), routing is **server-driven** (Laravel routes + Wayfinder, not file-based App Router), forms use **Inertia `useForm`** (not React Hook Form + fetch), and auth is **Fortify session + spatie/permission** (not token clients).

## When to use this skill

Use whenever the user has Claude Design output (HTML, screenshots, a handoff `.zip`, or a Claude Code handoff folder) **and** wants a Laravel fullstack frontend — Inertia + React, a Laravel starter-kit UI, or "turn this design into a Laravel app (not Next.js)". The trigger is the combination of (a) Claude Design as the input source and (b) **Laravel + Inertia** as the target.

Do NOT use this skill for:
- A **decoupled** Next.js frontend against a Laravel/Nest.js JSON API — that's `design-to-nextjs` (Sanctum tokens, `packages/contracts`, TanStack Query).
- Vue / Svelte / Livewire starter kits — React only (spec D5).
- Migrating an existing Next.js frontend to Inertia — this skill is greenfield translation only.
- A backend-only Laravel build with no design artifacts — use `laravel-enterprise-backend` directly.

If the target is Next.js, or the input isn't a Claude Design handoff, this is the wrong tool.

## Reuse pointers — read these first (do NOT duplicate)

Two parts of the craft are **identical** to the Next.js path and are reused verbatim. Read them from the sibling skill; this skill only adds the Inertia layer on top.

| Reused file (in `design-to-nextjs`) | Why it's identical here |
|---|---|
| `../design-to-nextjs/references/token-extraction.md` | shadcn CSS-variable token extraction (colors, type, spacing, radii, shadows, motion → Tailwind config + tokens) is the same regardless of Inertia vs Next.js. The Laravel starter kit uses Tailwind 4 + the same shadcn variable convention. |
| `../design-to-nextjs/references/component-patterns.md` | Translating Claude Design HTML into React + shadcn components is the same substrate. The only difference is where data comes from (props, not hooks) and how navigation works (`<Link>` from `@inertiajs/react`, not `next/link`). |

Do not copy these into the Laravel skill — cite them. Everything else (pages, props, routing, forms, auth, typed props, deploy) is Inertia-specific and lives in this skill's own references.

## Target stack

The output is always the **Laravel 13 React starter kit**:

- **Laravel 13** backend, controllers returning `Inertia::render('page', $props)`
- **Inertia 3** + **React 19** + **TypeScript** — pages in `resources/js/pages/`
- **Tailwind CSS 4** with tokens extracted from the design output
- **shadcn/ui** for every primitive (`resources/js/components/ui/`), including the **sidebar block** — already shipped by the starter kit
- **Wayfinder** for type-safe, server-driven route helpers (build-time)
- **Laravel Fortify** (session auth) + **spatie/laravel-permission** + Policies + `#[Authorize]`
- **Inertia `useForm`** for all mutations; server validation errors surface in `form.errors`
- **lucide-react** for icons
- **Vite** build, **client-only** (no SSR) — `npm run build`, skip `build:ssr`
- Hand-written prop types in `resources/js/types/` (starter-kit convention, spec D4)

If the user requests Vue/Svelte/Livewire, push back — this skill is React only.

## Architectural commitments (non-negotiable)

These are baked into every generated app. They are not configurable — if the user wants a different shape, push back and explain why.

### 1. shadcn/ui is the ONLY visual primitive library (and the sidebar block ships with the kit)

Every primitive — buttons, inputs, selects, dialogs, tables, cards, badges, dropdowns, tooltips, popovers, sheets, drawers, sidebars — comes from shadcn/ui via `@/components/ui/*`. The starter kit already installs shadcn (incl. the **sidebar block** and the sidebar/header layouts). Add missing primitives with `npx shadcn@latest add <x>` → `resources/js/components/ui/`.

Forbidden alongside shadcn: `@radix-ui/*` (shadcn already wraps Radix), `@headlessui/*`, `@mui/*`, `@chakra-ui/*`, `@mantine/*`, `antd`, `react-bootstrap`, `flowbite-react`, `@nextui-org/*`, `tremor`, `daisyui`. Hand-rolled primitives (a 30-line `<MyButton>` wrapping `<button>`) are also banned. Raw HTML primitives in component code are forbidden where a shadcn equivalent exists: no `<button>`, `<input>`, `<select>`, `<textarea>`, `<dialog>`. Layout elements (`<div>`, `<section>`, `<nav>`, `<ul>`, `<li>`) are fine.

**Every sidebar uses shadcn's sidebar block** (`<Sidebar>`, `<SidebarProvider>`, `<SidebarMenu>`, …) via the starter-kit `layouts/`. No custom `<aside className="w-64 ...">` in a layout. Use the block's variants (`collapsible="icon"`, `variant="floating"`) rather than re-implementing.

### 2. Title Case for every enum value — render directly, no conversion

Every enum string on the wire / in props (statuses, stages, roles, industries, discriminator `kind` fields) is **Title Case**. Components render the value directly — no `.toUpperCase()`, no `STATUS_LABELS` lookup, no `humanize()` helper.

```tsx
<Badge>{company.status}</Badge>          {/* "Active" */}
<span>{lead.stage}</span>                {/* "Proposal Sent" */}
{activity.kind === 'Email Sent' && <Icon name="mail" />}
```

If you reach for a capitalize/humanize/labelize helper on a prop value, the value is wrong — fix it server-side, not in the component. Numeric ranges like `"51-200"` (size buckets) render naturally; append units in the view (`{company.size.bucket} employees`).

### 3. View-shape contract — render typed props without `?.` or `??` (a discipline, per D4)

Controllers return view-ready data via `Inertia::render`. Page/component code **never** uses `?.` or `??` to defend against missing fields on prop data.

What that means in practice:
- **Counts are always numbers**, defaulted to 0 server-side. `company.counts.contacts` is a `number`, never `number | undefined`.
- **Labels are pre-built server-side.** A growth signal arrives as `{ kind: 'Growing', label: '+12% YoY' }` — render `signal.label`, don't compute.
- **Variations are discriminated unions.** `last_activity` is `{ kind: 'None' } | { kind: 'Email Sent'; at: string; label: string }`. Pattern-match on `kind`; don't null-check.
- **Dates are ISO 8601 strings.** Convert to `Date` at the render site if needed; the type is never `Date | undefined`.
- **Genuinely nullable fields are explicit.** `domain: string | null` is fine; `domain?: string` is a smell.

> **D4 trade-off (important):** unlike the Next.js path, this contract is **not** machine-generated. The Next.js path derives types from `laravel-data` → `packages/contracts` (codegen, machine-checked). Here, prop types are **hand-written** in `resources/js/types/` per starter-kit convention, and the "no `?.`" rule is a **discipline** — the controller's `Inertia::render` shape and the hand-written type must be kept in lockstep by the author, the `inertia-module-builder`, and a review/lint pass for `?.`/`??` on prop fields. Do not introduce `laravel-data`→TS as the frontend contract for the monolith. See `references/typed-props.md`.

### 4. Wayfinder typed routes — routing is server-driven

Routes are defined in Laravel (`routes/web.php`) and rendered via `Inertia::render`. **Wayfinder** generates type-safe route helpers at build time. Regenerate them when routes change; disable unused Fortify feature routes to avoid build failures. There is no file-based routing in `resources/js/pages/` — page files are *resolved by name* from the controller's `Inertia::render('companies/index', …)`, not by their path mapping to a URL. See `references/pages-props-routing.md`.

### 5. Fortify session auth + spatie authorization (not tokens)

Identity is **Laravel Fortify** (session-based; login/register/reset/verify/2FA scaffolded by the kit). Authorization is **`spatie/laravel-permission` + Policies + `#[Authorize]`** on controllers. `HandleInertiaRequests::share` exposes `auth.user` and the user's resolved permissions as Inertia props so the UI can gate `<Link>`/buttons. UI gating is convenience; the server `#[Authorize]` is the real guard. This is **NOT** Sanctum tokens — tokens are the decoupled-Next.js path. `BelongsToWorkspace` tenancy still applies. See `references/auth-fortify-permissions.md`.

## The five-phase pipeline

```
Phase 1: Token Extraction      → Pull design tokens into the Tailwind config + tokens file.
Phase 2: Scaffold / Confirm    → laravel new (React kit), or confirm the kit is present. Add shadcn primitives.
Phase 3: Per-page Translation  → For each screen: typed props → controller render → page → components.
Phase 4: Forms + Auth Wiring   → useForm for mutations; share auth.user + permissions; #[Authorize] controllers.
Phase 5: Build + Verify        → npm run build (Vite typecheck), grep for leakage, visual diff.
```

Walk them in order. Inventory the design first (read every HTML file, screenshot, and `design-notes.md`; catalog screens, repeated components, tables, forms) exactly as the Next.js skill describes — that step is identical and feeds Phase 1. Each screen maps roughly 1:1 to a page in `resources/js/pages/` plus a Laravel route + controller method.

---

## Phase 1 — Token extraction (identical to Next.js)

**Goal:** Extract design tokens (colors, typography, spacing, radii, shadows, motion) from the Claude Design HTML into the Tailwind 4 config + a tokens file. This is the highest-leverage step; skipping it scatters hex codes across components.

This phase is **identical** to the Next.js path. Read `../design-to-nextjs/references/token-extraction.md` for the full procedure and the canonical config template. The starter kit already ships Tailwind 4 + the shadcn CSS-variable convention, so you wire the extracted tokens into the kit's existing `resources/css/app.css` / Tailwind config and tokens file rather than creating them from scratch.

---

## Phase 2 — Scaffold / confirm the React starter kit

**Goal:** A runnable Laravel + Inertia app with shadcn, the sidebar block, Fortify auth pages, and Wayfinder already in place, booting cleanly before any feature code is added.

See `references/inertia-scaffolding.md` for the full procedure. Summary:

1. `laravel new <app>` → choose the **React** kit (Inertia 3 + React 19 + TS + Tailwind 4 + shadcn/ui). If the project already exists, confirm the kit is present (`resources/js/{pages,components,layouts,hooks,lib,types}`, `resources/js/components/ui/`, the sidebar block, Fortify pages, Wayfinder).
2. `npm install && npm run build`; `composer run dev` to boot.
3. Confirm the **shadcn sidebar block** is present (it ships with the kit) — matches the shadcn-everywhere commitment. Add any missing primitives with `npx shadcn@latest add <x>`.
4. Verify the app boots with the starter pages before adding features.

Do not re-init shadcn — the kit already did it.

---

## Phase 3 — Per-page translation

**Goal:** Translate each screen from the design into an Inertia page + a controller method that supplies its typed props. This is the heart of the skill.

See `references/claude-design-to-inertia.md` for the translation mapping table and a full worked example. Supporting references: `references/pages-props-routing.md` (render + routing), `references/typed-props.md` (prop types), `references/module-structure.md` (per-feature file layout).

**Canonical order per feature** — types first, components last (components without types behind them encode bad assumptions):

```
1. types       → resources/js/types/<feature>.ts (hand-written, exhaustive, no optional data fields)
2. controller  → app/.../<Feature>Controller.php render methods (Inertia::render + eager-load + shape props)
3. route       → routes/web.php entry (auth/verified middleware) — Wayfinder picks it up
4. page        → resources/js/pages/<feature>/index.tsx (reads typed props; no ?. / ??)
5. components  → resources/js/components/<feature>/* (shadcn primitives only)
```

**Tactical rules:**
- **Data arrives as typed props**, not client fetches. There is no TanStack Query, no `useEffect(fetch)`, no client-side data layer. The controller eager-loads and shapes the props.
- **Drop Next.js-isms.** Inertia pages are plain client React components — no `'use client'`, no RSC split, no `next/*` imports. Use `<Link>` and `router` from `@inertiajs/react`.
- **Render enum values directly** (Title Case), counts as numbers, variations as discriminated unions.
- For client-only UI state (modal open, selected rows), use Zustand — see `references/state-and-data.md`. Inertia props replace most "state".

---

## Phase 4 — Forms + auth wiring

**Goal:** Wire mutations through Inertia `useForm`, and wire identity/authorization through Fortify + spatie, sharing auth context as Inertia props.

See `references/forms-useform.md` (forms) and `references/auth-fortify-permissions.md` (auth/authz).

**Forms:** every create/edit uses Inertia `useForm` → `form.post/put/delete`. Server validation errors (from a Laravel FormRequest) surface automatically in `form.errors`. Inputs are shadcn primitives. Reuse the Fortify-scaffolded auth pages (login/register/reset) as-is — don't re-translate them from the design unless the design specifies custom auth screens.

**Auth:** Fortify provides session login/register/etc. `spatie/laravel-permission` provides roles/permissions. `HandleInertiaRequests::share` exposes `auth.user` + the resolved `auth.permissions`. Controllers gate actions with `#[Authorize]` (Policies). Pages gate `<Link>`/buttons by reading `auth.permissions` — convenience only; the server attribute is the real guard.

---

## Phase 5 — Build + verify

**Goal:** Prove the app typechecks, builds, and is free of framework leakage and contract gaps.

```bash
npm run build        # Vite + TypeScript build — client-only; do NOT run build:ssr
```

Then walk the checklist:

- [ ] `npm run build` succeeds (Vite + TS, no type errors)
- [ ] **No `?.` / `??` on prop fields** in `resources/js/pages/**` and `resources/js/components/**` — grep and review each hit. If it defends against a contract gap, fix the type + controller; if it's genuine null safety on a `| null` field, leave it.
- [ ] **No Next.js-isms** in `resources/js/` — `grep -rniE "next/|use client|@tanstack/react-query|app router|server component" resources/js` returns zero hits (these belong only in a translation/comparison table, never in code).
- [ ] **No client-side data fetching** — no `useEffect(fetch)`, no `axios`/`fetch` calls for page data. Data comes from props.
- [ ] **shadcn primitives only** — no competing UI libs; no raw `<button>/<input>/<select>/<textarea>/<dialog>` where a shadcn equivalent exists; sidebar comes from the starter-kit block.
- [ ] **No enum casing helpers** on prop data (`capitalize`, `humanize`, `LABELS[`).
- [ ] **No arbitrary color/radius Tailwind classes** — `(bg|text|border)-[#...]` / `rounded-[...]` returns zero hits; tokens come from the config.
- [ ] Every screen renders at its route; every form submits and shows loading + error + success states; `#[Authorize]` guards every gated controller method.
- [ ] If screenshots were provided, do a visual diff side-by-side and flag drift.

Deploy is the single Laravel app on Bref — Vite build (client-only) + assets to S3/CloudFront, session auth. See `references/deploy-notes.md` and the `laravel-bref-deploy` skill.

---

## Reference files

Load these as needed. Each is focused; don't read all of them upfront. The first two are reused verbatim from the sibling `design-to-nextjs` skill.

| File | When to read |
|---|---|
| `../design-to-nextjs/references/token-extraction.md` *(reused)* | Phase 1 — token extraction (identical to Next.js) |
| `../design-to-nextjs/references/component-patterns.md` *(reused)* | Phase 3 — translating design HTML → React + shadcn components (identical substrate) |
| `references/inertia-scaffolding.md` | Phase 2 — `laravel new` React kit, what ships, Vite, `npx shadcn add` |
| `references/claude-design-to-inertia.md` | Phase 3 — **(the heart)** translation rules + worked example |
| `references/pages-props-routing.md` | Phase 3 — `Inertia::render`, `resources/js/pages/`, persistent layouts, `<Link>`, Wayfinder |
| `references/typed-props.md` | Phase 3 — hand-written prop types in `resources/js/types/`; the no-`?.` discipline |
| `references/module-structure.md` | Phase 3 — per-feature layout across `resources/js` + the controller |
| `references/forms-useform.md` | Phase 4 — Inertia `useForm`, server validation errors, Fortify auth pages |
| `references/auth-fortify-permissions.md` | Phase 4 — Fortify session + spatie/permission; `HandleInertiaRequests::share`; `#[Authorize]`; UI gating |
| `references/state-and-data.md` | Phase 3/4 — Inertia props vs Zustand client state; no TanStack Query; partial reloads |
| `references/deploy-notes.md` | Phase 5 — pointer to `laravel-bref-deploy`: Vite build, assets, client-only, session auth |

---

## Common pitfalls

These come up every time. Watch for them.

**Pitfall 1: Returning untyped props / using `?.` on prop fields.** The controller's `Inertia::render` shape and the hand-written `resources/js/types/` type must match exactly, with no optional data fields. If you find `company?.counts?.contacts ?? 0` in a page, the type or the controller is wrong — make counts a non-optional `number` defaulted server-side and drop the `?.`. (Per D4 this is a discipline, not codegen — so it's on you and the reviewer to keep them in lockstep.)

**Pitfall 2: Leaking Next.js-isms.** `next/link`, `next/image`, `next/navigation`, `'use client'`, the App Router, server components, `@tanstack/react-query` — none of these belong in an Inertia app. They appear in this skill *only* inside the explicit Claude-Design→Inertia translation/comparison table, never as the Inertia way. Use `<Link>`/`router` from `@inertiajs/react`, plain `<img>` or a shadcn image component, and props instead of TanStack.

**Pitfall 3: Client-side data fetching instead of props.** `useEffect(() => fetch('/api/companies'))` is the decoupled-SPA pattern, not Inertia. Page data comes from the controller as typed props. To refresh specific props, use Inertia partial reloads (`router.reload({ only: [...] })`), not a client fetch. See `references/state-and-data.md`.

**Pitfall 4: Bypassing shadcn.** Hand-rolling a `<button>`-with-Tailwind, pulling in another UI library, or building a custom `<aside>` sidebar. Use `@/components/ui/*` and the starter-kit sidebar block; `npx shadcn@latest add <x>` for anything missing.

**Pitfall 5: Forgetting `#[Authorize]` on Inertia controllers.** Gating the UI by `auth.permissions` is convenience only — anyone can hit the route directly. Every gated controller method needs a `#[Authorize]` attribute (Policy-backed). The shared `auth.permissions` prop just hides links the user can't use.

**Pitfall 6: Treating Claude Design's HTML as final markup.** It's a *visual specification*, not the output. Re-implement against shadcn components; don't transcribe `<div class="...">` blocks one-for-one into JSX.

**Pitfall 7: Wayfinder route drift.** Routes live in Laravel; Wayfinder generates typed helpers at build time. Regenerate them when routes change, and disable unused Fortify feature routes so the build doesn't fail on missing route definitions.

**Pitfall 8: Running the SSR build.** Deploy is client-only (D2). Use `npm run build`; do **not** run `build:ssr` or stand up a Node SSR Lambda. Vite assets go to S3/CloudFront; the same Bref web function serves Inertia HTML + JSON prop responses.
