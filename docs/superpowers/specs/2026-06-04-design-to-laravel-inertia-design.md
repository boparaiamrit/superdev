# Design — `design-to-laravel` (Claude Design → Inertia React) for the Laravel option

- **Date:** 2026-06-04
- **Status:** Approved (brainstorming → spec)
- **Author:** Amritpal Singh Boparai (with Claude)
- **Builds on:** `2026-06-03-laravel-backend-option-design.md` (the Laravel backend + Bref deploy + orchestrator selection gate, shipped in v1.4.0).
- **Scope:** Give the Laravel backend option a *fullstack, idiomatic* frontend story — translate a Claude Design handoff into a **Laravel + Inertia + React** monolith (the official Laravel starter-kit stack), as the **default** frontend for Laravel, while keeping the decoupled **Next.js** frontend as an alternative.

---

## 1. Problem & motivation

v1.4.0 added Laravel as a backend, but assumed the frontend stays **Next.js** (`apps/web`) consuming a JSON API (Sanctum tokens + generated TS contracts). That is the *decoupled SPA* model — **not** how Laravel natively does frontend. Laravel's own answer is **Inertia + a React starter kit**: one app that is backend *and* frontend, server-driven routing, session auth, props instead of a REST contract.

We need a "Claude Design → Laravel(Inertia React)" path so a Laravel build can be a true fullstack monolith. Today the only design-translation skill is `design-to-nextjs`.

---

## 2. Verified stack facts (Laravel 13 React starter kit)

From [laravel.com/docs/13.x/starter-kits](https://laravel.com/docs/13.x/starter-kits):

- `laravel new` (interactive) → **React kit = Inertia 3 + React 19 + TypeScript + Tailwind 4 + shadcn/ui.**
- Frontend lives in **`resources/js/`**: `pages/`, `components/`, `layouts/`, `hooks/`, `lib/`, `types/`. shadcn via `npx shadcn@latest add <x>` → `resources/js/components/ui/`.
- **Ships the shadcn sidebar block** (sidebar/header layouts; sidebar/inset/floating variants; auth layouts simple/card/split) — matches our "shadcn everywhere / shadcn sidebar" commitment out of the box.
- **Auth = Laravel Fortify (session-based):** login/register/reset/email-verify/2FA/teams scaffolded; optional WorkOS AuthKit variant. Type-safe routing via **Wayfinder** (build-time route definitions).
- **Inertia model:** controllers return `Inertia::render('page', $props)`; pages in `resources/js/pages/`; persistent layouts; `<Link>` navigation; `useForm` for forms.
- **SSR optional** (`npm run build:ssr` / `composer dev:ssr`). We use **client-only** → `npm run build`.
- **Bref:** "Laravel with Inertia runs without issue on Bref"; Bref 3.0 `serverless.yml` template covers **S3 + CloudFront**; set `ASSET_URL` → CloudFront ([Bref Laravel docs](https://bref.sh/docs/laravel/getting-started)).

---

## 3. Decisions locked during brainstorming

| # | Decision | Choice |
|---|---|---|
| D1 | Frontend architecture for the Laravel option | **Inertia-monolith is the DEFAULT**; decoupled **Next.js kept as an alternative**. Orchestrator asks which at a frontend-stack gate. |
| D2 | Inertia SSR on Bref/Lambda | **Client-only** (no SSR). `npm run build`; assets → S3/CloudFront; Laravel returns the HTML shell + JSON props, React hydrates. |
| D3 | Auth/authz for the monolith | **Fortify session** (starter-kit default) for identity + **`spatie/laravel-permission` + Policies + `#[Authorize]`** for authorization; share `auth.user` + resolved permissions as Inertia props. |
| D4 | Frontend typing / contract for the monolith | **Starter-kit hand-written prop types in `resources/js/types/`. NO `laravel-data`→TS for the monolith.** The view-shape "no `?.`" rule becomes a *discipline on typed props*, not a machine-generated guarantee. (`laravel-data` may still be used backend-side for validation/shaping, but it is not the FE contract source here.) |
| D5 | JS framework | **React** (Inertia 3 + React 19). Vue/Svelte/Livewire are out of scope for now. |

> **Note on D4 trade-off:** the decoupled Next.js path keeps `laravel-data` → `packages/contracts` as the single source of truth (machine-checked). The monolith path deliberately relaxes this for starter-kit alignment and simplicity — props are typed by hand in `resources/js/types/` and the "no `?.`" contract is enforced by the skill's discipline + a prop-shape lint/review, not by codegen. This is an accepted, explicit divergence.

---

## 4. Architecture: the frontend fork for the Laravel option

| Concern | Decoupled (Next.js) — *shipped v1.4.0* | **Inertia monolith — new default** |
|---|---|---|
| Apps / layout | `apps/api` (Laravel) + `apps/web` (Next.js), pnpm monorepo | **One Laravel app**; frontend in `resources/js/` (Vite via npm); no `apps/web`, no pnpm web package |
| Frontend framework | Next.js App Router | **React 19 via Inertia 3** |
| Data → UI | `laravel-data` → TS in `packages/contracts`, fetched via **TanStack Query** | **Inertia props** from controllers; types hand-written in `resources/js/types/` (D4) |
| Routing | Next.js file routes | Laravel routes + `Inertia::render` + **Wayfinder** typed helpers |
| Forms | RHF + fetch | **Inertia `useForm`** (server validation errors surfaced automatically) |
| Auth | Sanctum **tokens** + CORS | **Fortify session** + `spatie/permission` (D3) |
| shadcn | installed by `monorepo-bootstrapper` | **already in the starter kit** (incl. sidebar block) |
| Deploy | Laravel(Bref) + Next.js elsewhere | **one Bref app** + Vite assets → S3/CloudFront, client-only |
| Design-translation skill | `design-to-nextjs` | **`design-to-laravel` (new)** |

**Unchanged across both** (carried from the backend skill): CockroachDB + stock `pgsql`, UUID PKs + 40001 retry, database cache/sessions, SQS queues, `#[Audit]` → partitioned `audit_logs`, `BelongsToWorkspace` global-scope tenancy (cross-workspace 404), Title-Case enums, `spatie/laravel-permission`.

---

## 5. What gets built

| # | Artifact | Type |
|---|---|---|
| 1 | `skills/design-to-laravel/` | **New skill** (SKILL.md + references) — Claude Design → Inertia React |
| 2 | `agents/inertia-module-builder.md` | **New agent** (mirrors `frontend-module-builder` for the Inertia path) |
| 3 | `skills/prd-design-build-orchestrator/SKILL.md` | **Edit** — frontend-stack gate (Inertia vs Next.js) for the Laravel branch + routing |
| 4 | `agents/monorepo-bootstrapper.md` | **Edit** — Inertia-monolith scaffold branch (`laravel new` React kit; no `apps/web`) |
| 5 | `skills/laravel-enterprise-backend/SKILL.md` (+ a reference) | **Edit** — "Inertia variant" notes: Fortify/session auth, props instead of API, single-app layout |
| 6 | `skills/laravel-bref-deploy/` | **Edit** — Inertia monolith deploy (Vite build + assets, session auth, client-only) |
| 7 | `skills/frontend-modular-architecture/` + `agents/ui-auditor.md` | **Edit** — Inertia addendum (pages/props/forms differ; shadcn/sidebar rules unchanged) |
| 8 | `plugin.json` ×2, READMEs, `marketplace.json` | **Edit** — add the skill, bump version, refresh counts |

### 5.1 `design-to-laravel` skill structure

Reuses `design-to-nextjs` where identical; authors only the Inertia-specific parts.

**Reused from `design-to-nextjs` (cited, not duplicated):**
- `references/token-extraction.md` — shadcn CSS-variable token extraction is **identical**.
- `references/component-patterns.md` — shadcn component substrate is **identical** (with a short Inertia note).

**New references (9):**
| File | Purpose |
|---|---|
| `inertia-scaffolding.md` | `laravel new` React kit; what ships (pages/layouts/shadcn/sidebar/Fortify/Wayfinder); Vite; `npx shadcn add` |
| `claude-design-to-inertia.md` | **(the heart)** translation rules: Claude Design React/HTML → Inertia pages/components; what maps to what; what to drop (Next.js-isms) |
| `pages-props-routing.md` | `Inertia::render`, `resources/js/pages/`, persistent layouts, `<Link>`, Wayfinder typed routes |
| `forms-useform.md` | Inertia `useForm`, server-validation-error surfacing, Fortify auth pages reuse |
| `typed-props.md` | hand-written prop types in `resources/js/types/`; the view-shape "no `?.`" discipline; how controllers shape props |
| `auth-fortify-permissions.md` | Fortify session + `spatie/permission`; sharing `auth.user` + permissions as Inertia props; `#[Authorize]` on Inertia controllers; gating `<Link>`/UI by permission |
| `module-structure.md` | per-feature layout across `resources/js/{pages,components}` + the Laravel controller |
| `state-and-data.md` | when to use Inertia props vs Zustand client state (cite `design-to-nextjs/zustand-patterns.md`); no TanStack Query |
| `deploy-notes.md` | pointer to `laravel-bref-deploy`: Vite `npm run build` → S3/CloudFront, client-only, session auth |

**SKILL.md** covers: when-to-use; the reuse pointers; a phase pipeline (token extraction → scaffold/confirm starter kit → per-page translation → forms/auth wiring → build/verify); the architectural commitments (shadcn everywhere, Title-Case enums on the wire/props, view-shape "no `?.`", Wayfinder routes); a reference table; common pitfalls (returning untyped props; Next.js-isms like App Router/`use client`/`next/*` imports leaking in; bypassing shadcn; client-side data-fetching instead of props).

### 5.2 `inertia-module-builder` agent

Mirrors `frontend-module-builder`; one feature per invocation. Owns `resources/js/pages/<Feature>/*`, `resources/js/components/<feature>/*`, the feature's prop types in `resources/js/types/`, and the Laravel controller method(s) returning `Inertia::render`. Enforces: shadcn-only primitives, typed props (no `?.`), `useForm` for mutations, `#[Authorize]` on the controller, Wayfinder routes, component/page size limits. Does **not** touch other features or the backend domain logic (that's `laravel-module-builder`).

### 5.3 Orchestrator: frontend-stack gate

After the **backend-stack** gate (Step A.5b) selects Laravel, a new **frontend-stack** sub-gate asks:

> **Frontend for the Laravel backend?**
> - **Inertia monolith (default)** — one Laravel app, React via Inertia (`design-to-laravel`); Fortify session auth; one Bref deploy.
> - **Decoupled Next.js** — separate `apps/web` (`design-to-nextjs`); Sanctum token auth; Laravel API + Next.js.

Persist to `STACK.md` / `EXECUTION_PLAN.md` (`frontend_stack`). Routes: bootstrap (single Laravel app w/ React kit vs `apps/api`+`apps/web`), auth (Fortify session vs Sanctum tokens), frontend builder (`inertia-module-builder` vs `frontend-module-builder`), contracts (none / `resources/js/types` vs `packages/contracts`), deploy (one Bref app vs Laravel API + Next.js). The Nest.js backend branch is unaffected (always Next.js).

---

## 6. Claude Design → Inertia translation (the core mapping)

The component layer is ~the same as `design-to-nextjs` (React + shadcn + Tailwind). The translation rules cover the *delta*:

| Claude Design / Next.js idiom | → Inertia React equivalent |
|---|---|
| `app/.../page.tsx` route | `resources/js/pages/<Page>.tsx` + a Laravel route → `Inertia::render('<Page>', $props)` |
| `use client` / server components split | (none) — Inertia pages are client React components; drop RSC directives |
| `next/link`, `next/navigation`, `next/image` | Inertia `<Link>`, `router`, plain `<img>` / shadcn equivalents |
| TanStack Query / fetch in component | data arrives as **typed props** from the controller |
| RHF + fetch submit | Inertia `useForm` → `post/put/delete`; errors via `form.errors` |
| NextAuth / token client | Fortify session; `usePage().props.auth.user`; permissions in shared props |
| Next.js layout files | Inertia **persistent layouts** (starter-kit `layouts/`), sidebar/header |
| shadcn primitives, Tailwind tokens | **identical** (reuse token-extraction + shadcn refs) |
| Title-Case enum values | identical on the wire/props; rendered directly, no label maps |

**Step 8 proof:** translate one representative Claude Design page (e.g. a list + a create form) end-to-end into an Inertia page + controller + typed props, confirm it renders with shadcn and submits via `useForm`, and codify any gaps back into `claude-design-to-inertia.md`.

---

## 7. Deployment (Inertia monolith on Bref)

Extends `laravel-bref-deploy` (no new functions needed):
- **Build:** `npm install && npm run build` (Vite) during deploy; **skip** `build:ssr` (client-only).
- **Assets:** Vite output → S3, served via CloudFront; `ASSET_URL` → CloudFront (already covered by `storage-s3-cloudfront.md`).
- **Auth:** **session-based** (Fortify) → ensure the session driver is `database` (CockroachDB) and `APP_URL`/cookie domain are set; no cross-domain CORS/token dance.
- **Same 3 functions** (web `php-84-fpm` / SQS worker / `php-84-console`); the web function serves Inertia HTML + JSON prop responses. Client-only → no Node SSR Lambda.

---

## 8. Out of scope (YAGNI)

- Inertia **SSR** (client-only per D2).
- **Vue / Svelte / Livewire** starter kits (React only, D5).
- `laravel-data`→TS as the FE contract for the monolith (D4 — starter-kit types instead).
- WorkOS AuthKit variant (Fortify default; WorkOS can be a later opt-in).
- Migrating an existing Next.js frontend to Inertia (greenfield translation only).

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Next.js-isms leak into Inertia pages (RSC directives, `next/*` imports, TanStack data-fetch) | `ui-auditor` Inertia addendum greps for `next/`, `use client`, `@tanstack/react-query` in `resources/js/`; the translation skill lists them as forbidden |
| View-shape "no `?.`" no longer machine-checked (D4) | Skill discipline + `inertia-module-builder` writes exhaustive prop types + a review/lint pass for `?.`/`??` on prop fields |
| Fortify + `spatie/permission` + Inertia shared-props wiring is fiddly | `auth-fortify-permissions.md` gives the exact `HandleInertiaRequests::share` snippet (auth.user + permissions) and the `#[Authorize]` pattern; verified in step 8 proof |
| Wayfinder route drift if routes change | Document the build-time regeneration; note disabling unused Fortify feature routes (per starter-kit docs) to avoid build failures |
| Session auth on stateless Lambda | DB-backed sessions (CockroachDB) already in the backend skill; deploy-notes ensure `SESSION_DRIVER=database` + cookie/APP_URL config |

---

## 10. File manifest

**New:** `skills/design-to-laravel/SKILL.md` + 9 references (§5.1); `agents/inertia-module-builder.md`.
**Edited:** `skills/prd-design-build-orchestrator/SKILL.md` (frontend-stack gate); `agents/monorepo-bootstrapper.md` (Inertia scaffold branch); `skills/laravel-enterprise-backend/SKILL.md` (+ optional `references/inertia-variant.md`); `skills/laravel-bref-deploy/` (Inertia deploy notes); `skills/frontend-modular-architecture/` + `agents/ui-auditor.md` (Inertia addendum); `plugin.json` ×2; `README.md`; `plugins/superdev/README.md`; `.claude-plugin/marketplace.json`.

---

## 11. Acceptance criteria

1. Operator choosing **Laravel** backend is then asked **Inertia vs Next.js** frontend, and the choice routes bootstrap, auth, frontend builder, and deploy correctly (Nest.js branch unaffected).
2. `design-to-laravel` standalone translates a Claude Design handoff into a Laravel + Inertia 3 + React 19 app: pages in `resources/js/pages/`, shadcn primitives (incl. sidebar block), typed props in `resources/js/types/` (no `?.` on prop fields), forms via `useForm`, routes via Wayfinder, auth via Fortify + `spatie/permission` with `#[Authorize]` controllers.
3. The step-8 proof page renders and submits correctly; translation gaps are codified in `claude-design-to-inertia.md`.
4. `laravel-bref-deploy` documents the Inertia monolith deploy (Vite build, assets → S3/CloudFront, session auth, client-only).
5. shadcn-everywhere + Title-Case-enum + view-shape-"no `?.`" commitments hold in the Inertia output; `ui-auditor` Inertia addendum flags `next/*`/`use client`/TanStack leakage.
6. Plugin docs/manifests updated (new skill + agent, version bump, counts).
