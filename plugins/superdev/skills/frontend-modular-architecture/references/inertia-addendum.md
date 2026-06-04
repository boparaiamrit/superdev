# Inertia addendum — modular architecture for Laravel + Inertia React

The modular rules in this skill were written for Next.js (`apps/web/src/`). They apply almost unchanged to the **Laravel Inertia React** frontend (`resources/js/`), built by [`design-to-laravel`](../../design-to-laravel/SKILL.md) and the `inertia-module-builder` agent. This addendum lists only the deltas; everything not mentioned here is identical.

## Same rules (unchanged)

- **Page files ≤ 100 lines, component files ≤ 200 lines.** A page that grows past 100 lines extracts components.
- **shadcn/ui is the only visual primitive source** — `@/components/ui/*`. The React starter kit already ships shadcn incl. the **sidebar block**; use the starter-kit `layouts/` (sidebar/header) — never a hand-rolled `<aside>`.
- **Overlays (drawer/modal/popover) live in their own folders** and use shadcn Portal primitives (`Sheet` / `Dialog` / `AlertDialog` / `Popover` / `DropdownMenu` / `Tooltip`).
- **Wizards with ≥ 3 steps split into per-step files.**
- **No god-files; no `useState` soup for shared state.**

## Deltas for Inertia

| Topic | Next.js (this skill) | **Inertia React** |
|---|---|---|
| Location | `apps/web/src/modules/<feature>/` | `resources/js/pages/<feature>/` + `resources/js/components/<feature>/` |
| Routing | Next.js App Router (`app/.../page.tsx`) | Laravel routes + `Inertia::render` + **Wayfinder** typed helpers; navigate via `<Link>` from `@inertiajs/react` |
| Server data | TanStack Query hooks | **Inertia props** (typed in `resources/js/types/`); refresh with `router.reload({ only: [...] })` — **no TanStack Query** |
| Forms | RHF + Zod resolver | Inertia **`useForm`** |
| Client state (Zustand) | Zustand store per module when state crosses components | Same — but Inertia props replace most state, so a store is **rarely** needed (server data is never mirrored into a store) |
| Types | imported from `@<scope>/contracts` | hand-written in `resources/js/types/<feature>.ts` (the "no `?.` on prop data" discipline still holds) |

## What stays out

- No `'use client'` / RSC directives (Inertia pages are plain client React).
- No `next/*` imports.
- No `@tanstack/react-query`.

These are enforced by the `ui-auditor` Inertia check (greps `resources/js/` for the forbidden idioms) and by the `inertia-module-builder` agent's self-check.
