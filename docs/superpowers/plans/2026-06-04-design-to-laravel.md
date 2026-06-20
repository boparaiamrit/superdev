# design-to-laravel (Inertia React) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. When authoring each file follow `plugin-dev:skill-development` conventions and validate with `plugin-dev:plugin-validator`.

**Goal:** Add a `design-to-laravel` skill (Claude Design → Laravel + Inertia 3 + React 19 monolith) as the default frontend for the Laravel backend option, plus an `inertia-module-builder` agent and an orchestrator frontend-stack gate (Inertia vs Next.js), keeping the decoupled Next.js path intact.

**Architecture:** `design-to-laravel` mirrors `design-to-nextjs` and **reuses its token-extraction + shadcn references verbatim**, authoring only the Inertia-specific layer (pages/props/routing, `useForm`, Fortify+spatie authz, typed props in `resources/js/types`). The orchestrator gains a frontend-stack sub-gate (after the backend-stack gate, only when Laravel is chosen) that routes bootstrap/auth/builder/deploy. Backend core (CockroachDB, `#[Audit]`, tenancy, enums) is unchanged.

**Tech Stack:** Laravel 13 React starter kit (Inertia 3, React 19, TypeScript, Tailwind 4, shadcn/ui), Laravel Fortify (session auth) + `spatie/laravel-permission`, Wayfinder typed routes, Vite (client-only build), Bref 3.x. Source spec: `docs/superpowers/specs/2026-06-04-design-to-laravel-inertia-design.md`.

---

## Validation recipes (DRY — referenced by tasks)

- **VR-1 — SKILL/agent frontmatter parses (CRLF-aware).**
  `node -e "const fs=require('fs');let s=fs.readFileSync(process.argv[1],'utf8').replace(/\r/g,'');const m=s.match(/^---\n([\s\S]*?)\n---/);if(!m)throw 'no fm';const n=(m[1].match(/name:\s*(\S+)/)||[])[1];console.log('name',n)" <path>`
  Expected: `name` equals the skill dir / agent filename.
- **VR-2 — reference links resolve.** Every `references/<x>.md` named in a SKILL.md exists on disk (loop + `test -f`).
- **VR-3 — plugin validates.** Dispatch `plugin-dev:plugin-validator` on `plugins/superdev/`. Expected: new skill + agent discovered, no errors.
- **VR-4 — no framework leakage.** In `plugins/superdev/skills/design-to-laravel/`, Next.js-isms (`next/`, `use client`, `@tanstack/react-query`, "App Router", "server component") must appear **only** inside the explicit Claude-Design→Inertia translation/comparison table — never presented as the Inertia way. `grep -rniE "next/|use client|@tanstack/react-query|app router|server component"` and review each hit.
- **VR-5 — fence balance.** `grep -c '```' <file>` is even for every file.

Commits use Conventional Commits ending with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
Branch: `feat/design-to-laravel` (already created).

---

## File Structure

**New — `plugins/superdev/skills/design-to-laravel/`:**
- `SKILL.md` — recipe, phases, reuse pointers, reference table
- `references/inertia-scaffolding.md` — `laravel new` React kit; what ships; Vite; `npx shadcn add`
- `references/claude-design-to-inertia.md` — **(heart)** translation rules + worked example
- `references/pages-props-routing.md` — `Inertia::render`, `resources/js/pages/`, persistent layouts, `<Link>`, Wayfinder
- `references/forms-useform.md` — Inertia `useForm`, server validation errors, Fortify auth pages
- `references/typed-props.md` — hand-written prop types in `resources/js/types/`; the "no `?.`" discipline
- `references/auth-fortify-permissions.md` — Fortify session + spatie/permission; `HandleInertiaRequests::share`; `#[Authorize]`; UI gating
- `references/module-structure.md` — per-feature layout across `resources/js` + controller
- `references/state-and-data.md` — Inertia props vs Zustand (cite `design-to-nextjs/zustand-patterns.md`); no TanStack
- `references/deploy-notes.md` — pointer to `laravel-bref-deploy`; Vite build, assets, client-only

**New — agent:** `plugins/superdev/agents/inertia-module-builder.md`

**Modified:**
- `plugins/superdev/skills/prd-design-build-orchestrator/SKILL.md` — frontend-stack gate (Step A.5c) + routing
- `plugins/superdev/agents/monorepo-bootstrapper.md` — Inertia-monolith scaffold branch
- `plugins/superdev/skills/laravel-enterprise-backend/SKILL.md` + `references/inertia-variant.md` — auth/contract/layout deltas when paired with Inertia
- `plugins/superdev/skills/laravel-bref-deploy/SKILL.md` + `references/inertia-monolith-deploy.md` — Vite build + session auth + client-only
- `plugins/superdev/skills/frontend-modular-architecture/SKILL.md` + `references/inertia-addendum.md` — Inertia structure rules
- `plugins/superdev/agents/ui-auditor.md` — Inertia forbidden-import checks
- `plugins/superdev/.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` — v1.5.0, 16 skills, keywords
- `README.md`, `plugins/superdev/README.md`, `.claude-plugin/marketplace.json`

---

## PHASE 1 — `design-to-laravel` skill

### Task 1.1: Skill scaffold + SKILL.md

**Files:** Create `plugins/superdev/skills/design-to-laravel/SKILL.md`

- [ ] **Step 1: Create the dir + SKILL.md with this exact frontmatter (verbatim):**

```yaml
---
name: design-to-laravel
description: Translate a Claude Design handoff (HTML / claude.ai/design output / screenshots) into a Laravel + Inertia 3 + React 19 monolith — the official Laravel React starter-kit stack (TypeScript, Tailwind 4, shadcn/ui incl. the sidebar block). Pages live in resources/js/pages and receive typed props from controllers via Inertia::render; routing is server-driven via Laravel routes + Wayfinder; forms use Inertia useForm; auth is Laravel Fortify (session) plus spatie/laravel-permission with #[Authorize], sharing auth.user and resolved permissions as Inertia props. The frontend is part of the Laravel app (no separate Next.js), deployed serverless on AWS Lambda via Bref (client-only Inertia, Vite assets on S3/CloudFront). This is the DEFAULT frontend for the laravel-enterprise-backend option; the decoupled design-to-nextjs path remains an alternative. Use whenever the user wants a Laravel fullstack frontend, Inertia + React, a Laravel starter-kit UI, or to turn a Claude Design into a Laravel (not Next.js) app.
---
```

- [ ] **Step 2: Write the body** with these sections (mirror `plugins/superdev/skills/design-to-nextjs/SKILL.md` structure):
  1. Intro — recipe skill; when source is Claude Design → translate to Inertia React inside the Laravel app.
  2. **Reuse pointers** — explicitly: token extraction is identical to `design-to-nextjs/references/token-extraction.md`; the shadcn component substrate is identical to `design-to-nextjs/references/component-patterns.md` (read those; this skill only adds the Inertia layer).
  3. Architectural commitments — shadcn-everywhere (starter kit already does this), Title-Case enums on the wire/props, the view-shape "no `?.`" **discipline** on typed props (per spec D4), Wayfinder typed routes, Fortify session + spatie authz.
  4. Phase pipeline: `token extraction → scaffold/confirm React starter kit → per-page translation → forms + auth wiring → build + verify`.
  5. Per-phase sections, each pointing to its reference.
  6. Reference table (the 9 references + the 2 reused design-to-nextjs files).
  7. Common pitfalls: returning untyped props / `?.` on prop fields; leaking Next.js-isms (`next/*`, `use client`, App Router, TanStack data-fetch); client-side data-fetching instead of props; bypassing shadcn; forgetting `#[Authorize]` on Inertia controllers.

- [ ] **Step 3: Validate** — VR-1 (name == `design-to-laravel`). **Step 4: Commit** `feat(laravel): add design-to-laravel SKILL.md`.

---

### Task 1.2: `references/claude-design-to-inertia.md` (the heart — novel)

**Files:** Create `plugins/superdev/skills/design-to-laravel/references/claude-design-to-inertia.md`

- [ ] **Step 1: Author** with the translation mapping table (verbatim) and a worked example:

```
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
```

  Worked example — a "Companies" index page translated from a Claude Design list:

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

  Document the rules: every prop is typed (Task 1.5), every field exhaustive (no `?.`), enum values render directly, the controller eager-loads + shapes the props (cross-ref `pages-props-routing.md`). List forbidden leakage (`next/*`, `use client`, `@tanstack/react-query`).

- [ ] **Step 2:** VR-5 (even fences). **Step 3: Commit** `feat(laravel): add claude-design-to-inertia translation reference`.

---

### Task 1.3: `references/auth-fortify-permissions.md` (novel)

**Files:** Create `plugins/superdev/skills/design-to-laravel/references/auth-fortify-permissions.md`

- [ ] **Step 1: Author** with the exact shared-props + controller snippets:

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

  Cover: Fortify provides login/register/etc. (session); `spatie/laravel-permission` roles/permissions; Policies + `#[Authorize]`; the frontend reads `auth.permissions` to gate `<Link>`/buttons (UI gating is convenience — the server `#[Authorize]` is the real guard). Note `BelongsToWorkspace` tenancy still applies. Cross-ref the backend skill's `auth-sanctum-permissions.md` for the spatie/Policy details (shared), and clarify: **Inertia path uses Fortify session, NOT Sanctum tokens.**

- [ ] **Step 2:** VR-5. **Step 3: Commit** `feat(laravel): add auth-fortify-permissions reference`.

---

### Task 1.4: `references/pages-props-routing.md` (novel)

**Files:** Create `plugins/superdev/skills/design-to-laravel/references/pages-props-routing.md`

- [ ] **Step 1: Author.** Cover: `Inertia::render('companies/index', $props)`; pages resolve from `resources/js/pages/`; persistent layouts (`app-layout.tsx`, sidebar/header variants); `<Link href>` client navigation; **Wayfinder** typed route helpers (build-time; regenerate on route change; disable unused Fortify feature routes to avoid build failures); shared props via `HandleInertiaRequests` (cross-ref auth ref). Include a route + render snippet:

```php
// routes/web.php
Route::middleware(['auth','verified'])->group(function () {
    Route::get('/companies', [CompanyController::class, 'index'])->name('companies.index');
    Route::get('/companies/create', [CompanyController::class, 'create'])->name('companies.create');
    Route::post('/companies', [CompanyController::class, 'store'])->name('companies.store');
});
```

- [ ] **Step 2:** VR-5. **Step 3: Commit** `feat(laravel): add pages-props-routing reference`.

---

### Task 1.5: `references/typed-props.md` (novel)

**Files:** Create `plugins/superdev/skills/design-to-laravel/references/typed-props.md`

- [ ] **Step 1: Author.** Per spec D4: hand-written prop types in `resources/js/types/`, the view-shape "no `?.`" discipline. Example:

```ts
// resources/js/types/companies.ts
export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'
export interface CompanyView {
  id: string
  name: string
  domain: string | null            // explicit null, never "missing"
  industry: Industry               // value IS the label
  counts: { contacts: number; open_leads: number; won_deals: number }  // default 0 server-side
  last_activity: { kind: 'None' } | { kind: 'Email Sent'; at: string; label: string }
  created_at: string               // ISO 8601
}
export interface Paginated<T> { data: T[]; total: number; page: number; per_page: number }
```

  Rules: every field present and typed; nullable explicit; counts numbers; discriminated unions for variants; ISO date strings; **no `?.` / `??` on prop fields** in pages (the controller guarantees the shape). Note the trade-off (D4): unlike the Next.js path's `laravel-data`→`packages/contracts` codegen, these are hand-written — keep them in lockstep with the controller's `Inertia::render` shape; the `inertia-module-builder` + review enforce this.

- [ ] **Step 2:** VR-5. **Step 3: Commit** `feat(laravel): add typed-props reference`.

---

### Task 1.6: `references/forms-useform.md`

**Files:** Create `plugins/superdev/skills/design-to-laravel/references/forms-useform.md`

- [ ] **Step 1: Author.** Inertia `useForm` for create/edit; server validation errors surface in `form.errors` (Laravel FormRequest/laravel-data validation drives them); shadcn form primitives for inputs. Example:

```tsx
import { useForm } from '@inertiajs/react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export default function CompanyCreate() {
  const form = useForm({ name: '', industry: 'Technology' })
  return (
    <form onSubmit={(e) => { e.preventDefault(); form.post('/companies') }}>
      <Input value={form.data.name} onChange={(e) => form.setData('name', e.target.value)} />
      {form.errors.name && <p className="text-destructive">{form.errors.name}</p>}
      <Button disabled={form.processing}>Create</Button>
    </form>
  )
}
```

  Note: reuse the Fortify-scaffolded auth pages (login/register) as-is; don't re-translate them from the design unless the design specifies custom auth screens.

- [ ] **Step 2:** VR-5. **Step 3: Commit** `feat(laravel): add forms-useform reference`.

---

### Task 1.7: `references/inertia-scaffolding.md`

- [ ] **Step 1: Author** `plugins/superdev/skills/design-to-laravel/references/inertia-scaffolding.md`: `laravel new <app>` → choose **React** kit (Inertia 3 + React 19 + TS + Tailwind 4 + shadcn); `npm install && npm run build`; `composer run dev`; what ships (`resources/js/{pages,components,layouts,hooks,lib,types}`, shadcn sidebar block, Fortify auth pages, Wayfinder); add shadcn primitives via `npx shadcn@latest add <x>`; confirm the sidebar block is present (matches the shadcn-everywhere commitment). **Step 2:** VR-5. **Step 3: Commit** `feat(laravel): add inertia-scaffolding reference`.

### Task 1.8: `references/module-structure.md`

- [ ] **Step 1: Author**: per-feature layout — `resources/js/pages/<feature>/{index,create,edit,show}.tsx`, `resources/js/components/<feature>/*`, prop types in `resources/js/types/<feature>.ts`, and the Laravel `app/Domains/<Feature>/Http/<Feature>Controller.php` returning `Inertia::render`. One agent owns one feature's page/component/type files + its controller render methods. Canonical order: types → controller render → page(s) → components → forms. **Step 2:** VR-5. **Step 3: Commit** `feat(laravel): add module-structure (inertia) reference`.

### Task 1.9: `references/state-and-data.md`

- [ ] **Step 1: Author**: prefer **Inertia props** for server data; use **Zustand** only for genuine client-only UI state (cite `design-to-nextjs/references/zustand-patterns.md`); **no TanStack Query** (Inertia replaces it); partial reloads / `router.reload({ only: [...] })` for refreshing specific props. **Step 2:** VR-5. **Step 3: Commit** `feat(laravel): add state-and-data reference`.

### Task 1.10: `references/deploy-notes.md`

- [ ] **Step 1: Author**: short pointer to `laravel-bref-deploy` — for the Inertia monolith, deploy is the single Laravel app; add `npm install && npm run build` (Vite, client-only — skip `build:ssr`) to the deploy flow; Vite assets → S3/CloudFront (`ASSET_URL`); session auth needs `SESSION_DRIVER=database` + correct `APP_URL`/cookie domain. Cross-ref `laravel-bref-deploy/references/inertia-monolith-deploy.md`. **Step 2:** VR-5. **Step 3: Commit** `feat(laravel): add deploy-notes reference`.

### Task 1.11: Validate skill 1

- [ ] **Step 1:** VR-1 (SKILL.md), VR-2 (all 9 refs resolve), VR-4 (no Next.js leakage outside the mapping table), VR-5 (all fences). **Step 2:** Fix inline; commit `chore(laravel): validate design-to-laravel skill` if needed.

---

## PHASE 2 — `inertia-module-builder` agent

### Task 2.1: Create the agent

**Files:** Create `plugins/superdev/agents/inertia-module-builder.md`

- [ ] **Step 1: Author** with frontmatter:

```yaml
---
name: inertia-module-builder
description: Builds one feature's Inertia React frontend in a Laravel monolith — resources/js/pages/<feature>/*, components, hand-written prop types in resources/js/types/, and the controller's Inertia::render methods. Uses shadcn primitives only, typed props (no ?.), Inertia useForm for mutations, #[Authorize] on controllers, Wayfinder routes. One feature per invocation, for parallel dispatch.
tools: Read, Write, Edit, Bash
model: inherit
permissionMode: acceptEdits
skills:
  - design-to-laravel
---
```

- [ ] **Step 2: Author body** (mirror `agents/frontend-module-builder.md`, translate to Inertia): inputs (feature name, EXECUTION_PLAN, design source, the skill + refs); outputs (pages/components/types + controller render methods + routes); critical patterns (shadcn-only; typed props no `?.`; `useForm`; `#[Authorize]`; Wayfinder; page ≤ 100 / component ≤ 200 lines per frontend-modular-architecture); forbidden (`next/*`, `use client`, `@tanstack/react-query`, returning untyped props); after-writing (`npm run build` to typecheck Vite/TS; fix; ≤ 3 attempts); strict rules (own one feature; Edit `routes/web.php`; don't touch backend domain logic — that's `laravel-module-builder`). Return format.

- [ ] **Step 3:** VR-1 (name == `inertia-module-builder`). **Step 4: Commit** `feat(laravel): add inertia-module-builder agent`.

---

## PHASE 3 — Orchestrator + sibling-skill edits

### Task 3.1: Frontend-stack gate in the orchestrator

**Files:** Modify `plugins/superdev/skills/prd-design-build-orchestrator/SKILL.md`

- [ ] **Step 1:** Immediately after the existing **Step A.5b — Backend-stack selection gate**, add **Step A.5c**:

````markdown
### Step A.5c — Frontend-stack selection gate (Laravel only)

If `backend_stack == Laravel` AND the plan has frontend modules, ask (AskUserQuestion) which frontend:

> **Frontend for the Laravel backend?**
> - **Inertia monolith (default)** — one Laravel app, React via Inertia (`design-to-laravel`), Fortify session auth, one Bref deploy.
> - **Decoupled Next.js** — separate `apps/web` (`design-to-nextjs`), Sanctum token auth, Laravel API + Next.js.

Persist `frontend_stack` to `STACK.md` / `EXECUTION_PLAN.md`. Routing when `frontend_stack == Inertia`:
- bootstrap: single Laravel app via the React starter kit (no `apps/web`, no pnpm web package) — see `monorepo-bootstrapper`.
- auth: **Fortify session + spatie/permission** (see `laravel-enterprise-backend/references/inertia-variant.md`), NOT Sanctum tokens.
- frontend builder (Phase C): `inertia-module-builder` (not `frontend-module-builder`).
- contracts: typed props in `resources/js/types/` (no `packages/contracts`).
- deploy (Phase D): `laravel-bref-deploy` single-app Inertia flow.

When `backend_stack == Nest.js`, the frontend is always Next.js (no gate). When `frontend_stack == Next.js` with Laravel, use the decoupled path exactly as v1.4.0.
````

- [ ] **Step 2:** Add a row to the skill-routing table: `| Laravel backend + Inertia frontend (Step A.5c) | design-to-laravel (Phase C) + inertia-module-builder | Inertia React monolith; Fortify session; typed props |`.
- [ ] **Step 3:** VR-1; re-read edits. **Step 4: Commit** `feat(orchestrator): add frontend-stack gate (Inertia vs Next.js) for Laravel`.

### Task 3.2: monorepo-bootstrapper Inertia branch

**Files:** Modify `plugins/superdev/agents/monorepo-bootstrapper.md`

- [ ] **Step 1:** In its "Backend stack — read FIRST" section (added in v1.4.0), add an Inertia note: if `backend_stack == Laravel` AND `frontend_stack == Inertia`, scaffold a **single Laravel app via the React starter kit** (`laravel new` → React) — frontend is `resources/js/`, **no `apps/web`, no pnpm web package**; run `npm install && npm run build`; shadcn + sidebar block already present (do not re-init shadcn). If `frontend_stack == Next.js`, use the v1.4.0 `apps/api` + `apps/web` layout. Add `design-to-laravel` to the agent's `skills:` frontmatter.
- [ ] **Step 2:** VR-1. **Step 3: Commit** `feat(orchestrator): monorepo-bootstrapper Inertia-monolith scaffold branch`.

### Task 3.3: laravel-enterprise-backend Inertia variant

**Files:** Create `plugins/superdev/skills/laravel-enterprise-backend/references/inertia-variant.md`; Modify that skill's `SKILL.md` (add a pointer row in the reference table + a one-paragraph "Inertia variant" note).

- [ ] **Step 1: Author `inertia-variant.md`**: the deltas when the backend is paired with an Inertia frontend (vs the decoupled Next.js default): auth = **Fortify session + spatie/permission** (not Sanctum tokens); responses are **Inertia props** from controllers (not JSON API + laravel-data→packages/contracts); single-app layout (frontend in `resources/js/`, no `apps/web`); session driver = database (CockroachDB). Everything else (CockroachDB/pgsql, `#[Audit]`, `BelongsToWorkspace`, Title-Case enums) is unchanged. Cross-ref `design-to-laravel` + `auth-fortify-permissions.md`.
- [ ] **Step 2:** Add to the SKILL.md reference table: `| references/inertia-variant.md | When the frontend is Inertia (Fortify session, props, single-app) |` and a sentence in the auth/architecture section pointing to it.
- [ ] **Step 3:** VR-1 (SKILL.md), VR-5. **Step 4: Commit** `feat(laravel): document Inertia variant in laravel-enterprise-backend`.

### Task 3.4: laravel-bref-deploy Inertia deploy

**Files:** Create `plugins/superdev/skills/laravel-bref-deploy/references/inertia-monolith-deploy.md`; Modify that skill's `SKILL.md` (reference-table row + pointer).

- [ ] **Step 1: Author `inertia-monolith-deploy.md`**: deploying the Inertia monolith — add `npm install && npm run build` (Vite, **client-only**, skip `build:ssr`) to the deploy flow before `osls deploy`; Vite output → S3/CloudFront (`ASSET_URL`, cross-ref `storage-s3-cloudfront.md`); **session auth** needs `SESSION_DRIVER=database` (CockroachDB) + correct `APP_URL`/`SESSION_DOMAIN` (no cross-domain CORS/token dance); the same 3 Bref functions serve Inertia HTML + JSON prop responses (no Node SSR Lambda). Update the `deploy-checklist.md` ordering note via a pointer (do not duplicate the checklist).
- [ ] **Step 2:** Add the reference-table row + a sentence in the deploy SKILL.md. **Step 3:** VR-1, VR-5. **Step 4: Commit** `feat(laravel): document Inertia monolith deploy in laravel-bref-deploy`.

### Task 3.5: frontend-modular-architecture + ui-auditor Inertia addendum

**Files:** Create `plugins/superdev/skills/frontend-modular-architecture/references/inertia-addendum.md`; Modify its `SKILL.md` (pointer) and `plugins/superdev/agents/ui-auditor.md`.

- [ ] **Step 1: Author `inertia-addendum.md`**: the modular rules adapted for Inertia — pages in `resources/js/pages/` (≤ 100 lines), components ≤ 200 lines, shadcn-only + sidebar block (unchanged), Zustand only for client-only state (Inertia props replace most state), forms via `useForm`, routes via Wayfinder. The shadcn/Portal rules are unchanged from the Next.js doc; only routing/data/forms differ.
- [ ] **Step 2:** Add a pointer in `frontend-modular-architecture/SKILL.md`.
- [ ] **Step 3:** In `ui-auditor.md`, add an Inertia check: when the frontend is Inertia, grep `resources/js/` for forbidden `next/`, `use client`, `@tanstack/react-query`, and raw `<button>/<input>/<dialog>` where a shadcn equivalent exists; flag `?.`/`??` on Inertia prop fields.
- [ ] **Step 4:** VR-1 (ui-auditor), VR-5. **Step 5: Commit** `feat(frontend): add Inertia addendum to modular-architecture + ui-auditor`.

---

## PHASE 4 — Docs & manifests

### Task 4.1: plugin.json ×2

**Files:** Modify `plugins/superdev/.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`

- [ ] **Step 1:** Bump `version` 1.4.0 → **1.5.0**. Update description: "15-skill" → "16-skill"; append: "v1.5.0 adds design-to-laravel (Claude Design → Laravel + Inertia 3 + React 19 monolith) as the default frontend for the Laravel option, with a frontend-stack gate (Inertia vs Next.js)." Add keywords: `inertia`, `react`, `fortify`, `vite`, `fullstack`. (Programmatic Node edit like v1.4.0: parse → mutate → write + newline.)
- [ ] **Step 2:** `node -e "require('./plugins/superdev/.claude-plugin/plugin.json');require('./plugins/superdev/.codex-plugin/plugin.json');console.log('OK')"`. **Step 3: Commit** `chore: bump to v1.5.0; document design-to-laravel in manifests`.

### Task 4.2: READMEs

**Files:** Modify `README.md`, `plugins/superdev/README.md`

- [ ] **Step 1:** Top README: "15 Skills" → "16 Skills"; add row 16 `design-to-laravel`; add a sentence to the backend-stack-choice note about the frontend-stack sub-gate; update agent count 50 → **51** (added `inertia-module-builder`) wherever stated; update tech-stack to note the Inertia fullstack frontend option.
- [ ] **Step 2:** plugin README: "Fifteen skills" → "Sixteen skills" + add the `design-to-laravel` row; add `inertia-module-builder` to the build-agents list (→ **51 role prompts**); add a frontend-stack note.
- [ ] **Step 3:** `grep -rniE "15 skills|15-skill|50 (agents|subagents|specialized|role prompts)"` returns no stale counts. **Step 4: Commit** `docs: add design-to-laravel to READMEs; 16 skills / 51 agents`.

### Task 4.3: marketplace.json

**Files:** Modify `.claude-plugin/marketplace.json`

- [ ] **Step 1:** Node edit: "15 skills"/"15 production-grade skills" → 16; append `design-to-laravel` to the enumerated skill list; bump `plugins[0].version` → 1.5.0. **Step 2:** validate JSON parses. **Step 3: Commit** `docs: update marketplace to 16 skills / v1.5.0`.

---

## PHASE 5 — Final verification

### Task 5.1: Whole-plugin validation + acceptance check

- [ ] **Step 1:** VR-3 (`plugin-dev:plugin-validator`). Expected: 16 skills + 51 agents discovered, no errors.
- [ ] **Step 2:** VR-2 for `design-to-laravel` (9 refs) + VR-4 across the skill dir; `ls -d plugins/superdev/skills/*/ | wc -l` == 16; `ls plugins/superdev/agents/*.md | wc -l` == 51; `test -f plugins/superdev/agents/inertia-module-builder.md`.
- [ ] **Step 3:** Confirm every `design-to-laravel`/`inertia-module-builder` name referenced by the orchestrator + edited agents resolves.
- [ ] **Step 4:** Walk spec §11 acceptance criteria 1–6; note any gaps as follow-up tasks. (The §11.3 "proof page" is execution-time on a real project — within this repo the deliverable is the complete, self-consistent `claude-design-to-inertia.md` worked example; confirm it's coherent.)
- [ ] **Step 5: Commit** `chore(laravel): final validation of design-to-laravel` (if fixes), then summarize the branch diff.

---

## Self-Review

**1. Spec coverage:**
- §3 D1 (Inertia default + Next.js alt) → Tasks 3.1, 3.2. ✓
- §3 D2 (client-only SSR) → Tasks 1.10, 3.4. ✓
- §3 D3 (Fortify + spatie authz) → Tasks 1.3, 3.3. ✓
- §3 D4 (starter-kit hand-written types, no laravel-data FE) → Tasks 1.5, plus the trade-off noted. ✓
- §3 D5 (React) → Task 1.1, 1.7. ✓
- §5.1 skill (SKILL + 9 refs) → Tasks 1.1–1.11. ✓
- §5.2 agent → Task 2.1. ✓
- §5.3 frontend-stack gate → Task 3.1. ✓
- §6 translation mapping → Task 1.2. ✓
- §7 deploy → Task 3.4 (+1.10). ✓
- §5 edits (backend variant, bref, modular/ui-auditor) → Tasks 3.3, 3.4, 3.5. ✓
- §8 docs/manifests → Tasks 4.1–4.3. ✓
- §11 acceptance → Task 5.1. ✓

**2. Placeholder scan:** novel refs (1.2–1.6, 2.1, 3.1) carry complete code/text; outline refs cite the in-repo `design-to-nextjs`/`frontend-module-builder` source to mirror. No TBD/TODO.

**3. Name consistency:** consistent throughout — `design-to-laravel`, `inertia-module-builder`, `frontend_stack`, `HandleInertiaRequests::share`, `auth.permissions`, `resources/js/pages/`, `resources/js/types/`, `useForm`, `#[Authorize]`, `Inertia::render`, Wayfinder, `npm run build` (client-only), counts 16 skills / 51 agents / v1.5.0.
