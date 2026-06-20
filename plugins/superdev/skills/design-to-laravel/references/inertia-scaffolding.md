# Inertia Scaffolding — Laravel React Starter Kit

Run this in Phase 2 (scaffold/confirm). Goal: a running Laravel app with the React starter kit, all
frontend dependencies installed, a successful Vite build, and the shadcn sidebar block confirmed.
Before any feature code, `composer run dev` should render the Fortify login page cleanly.

---

## Step 1 — Create the app with the React kit

```bash
laravel new my-app
```

The interactive wizard prompts for a starter kit. Choose **React**:

| Prompt | Answer |
|---|---|
| Which starter kit? | **React** |
| Testing framework? | Pest (recommended) |
| Initialize a git repository? | Yes |

The React kit installs:
- **Inertia 3** (`inertiajs/inertia-laravel`, `@inertiajs/react`)
- **React 19** + TypeScript
- **Tailwind CSS 4** (with the Vite plugin)
- **shadcn/ui** (pre-configured — `components.json` present, base primitives installed)
- **Wayfinder** (`tightenco/wayfinder`) for build-time typed route helpers
- **Laravel Fortify** for session-based authentication

> **Not asked:** Laravel asks whether you want WorkOS AuthKit for authentication. Choose the default **Fortify** session option — WorkOS is out of scope for this skill (D3).

```bash
cd my-app
```

---

## Step 2 — Install JS dependencies and do the first build

The starter kit's `package.json` is already populated. Install and build:

```bash
npm install
npm run build
```

`npm run build` runs the **Vite client-only build** (outputs to `public/build/`). Do **not** run
`npm run build:ssr` — this skill uses client-only Inertia (D2). The SSR binary is not needed.

A successful build prints a Vite manifest summary. If TypeScript errors appear (e.g., missing
Wayfinder route files), run the Wayfinder generation first:

```bash
php artisan wayfinder:generate
npm run build
```

Regenerate Wayfinder any time routes change. Unused Fortify feature routes can cause build
failures if Wayfinder generates references you never import — disable them in
`config/fortify.php` (comment out `Features::updateProfileInformation()` etc.) to keep the
generated file clean.

---

## Step 3 — Start the local dev server

```bash
composer run dev
```

This runs the full dev stack: `php artisan serve`, `npm run dev` (Vite HMR), and the queue
worker in parallel. Visit `http://localhost:8000`. You should see the Fortify **login page**
styled with shadcn/ui and the Tailwind 4 theme.

> `composer run dev` is the single command for local development — no separate terminal for Vite.

---

## What ships with the React starter kit

### Frontend tree

```
resources/js/
├── pages/              ← Inertia page components (one file per route)
│   ├── auth/           ← Fortify auth pages (login, register, etc.)
│   └── dashboard.tsx   ← The stub dashboard page
├── components/
│   ├── ui/             ← shadcn primitives (button, card, dialog, sidebar…)
│   └── app-sidebar.tsx ← Pre-wired sidebar component (sidebar block)
├── layouts/
│   ├── app-layout.tsx          ← Sidebar layout (uses app-sidebar)
│   ├── auth-layout.tsx         ← Centered auth card layout
│   └── guest-layout.tsx        ← Guest / marketing layout
├── hooks/
│   └── use-mobile.tsx  ← viewport hook (used by sidebar)
├── lib/
│   └── utils.ts        ← cn() helper (clsx + tailwind-merge)
└── types/
    └── index.d.ts      ← Global shared-prop types (auth.user, PageProps)
```

### Auth pages (Fortify)

The `resources/js/pages/auth/` directory contains fully styled Inertia pages for every Fortify
feature: `login.tsx`, `register.tsx`, `forgot-password.tsx`, `reset-password.tsx`,
`confirm-password.tsx`, `verify-email.tsx`. Do **not** re-translate these from the Claude Design
unless the design explicitly specifies custom auth screens — use the shipped pages as-is.

### shadcn sidebar block

The starter kit ships the **shadcn sidebar block** (`sidebar` component + `app-sidebar` +
`app-layout`). This satisfies the "shadcn everywhere" commitment (D5) out of the box. Variants
available from the shipped block:

- `sidebar` (default, collapsible)
- `inset` (inset with header/content padding)
- `floating` (floating sidebar over content)

Confirm the sidebar is wired:

```bash
ls resources/js/components/ui/sidebar.tsx   # must exist
ls resources/js/components/app-sidebar.tsx  # must exist
ls resources/js/layouts/app-layout.tsx      # must exist
```

### Wayfinder typed routes

`tightenco/wayfinder` generates TypeScript route helpers from your Laravel route definitions.
After `php artisan wayfinder:generate`, a `resources/js/routes/` directory is created with
one TypeScript file per route group, each exporting typed helper functions. Import them in
pages instead of hardcoding URL strings:

```tsx
// Wayfinder generates per-group helpers — import the functions you need:
import { index, create, show } from '@/routes/companies'   // generated by Wayfinder
import { Link } from '@inertiajs/react'

// Type-safe, build-time checked — URL params are typed:
<Link href={create()}>New company</Link>
<Link href={show(company.id)}>{company.name}</Link>
```

Re-run `php artisan wayfinder:generate` whenever you add or rename a route, and commit the
generated files. See `references/pages-props-routing.md` for the full Wayfinder usage guide.

---

## Step 4 — Add shadcn primitives

The starter kit pre-installs the most common shadcn primitives. If a feature page needs a
component not yet present, add it individually:

```bash
npx shadcn@latest add <component>
```

Examples:

```bash
npx shadcn@latest add table
npx shadcn@latest add calendar
npx shadcn@latest add chart
npx shadcn@latest add data-table
```

Components are added to `resources/js/components/ui/`. They are TypeScript source files you own
— no bundler impact for unused ones.

**Do NOT re-initialize shadcn** (`npx shadcn@latest init`). The starter kit has already run
this and written `components.json`. Re-running it would overwrite the theme configuration.

For the same reason modules should not install shadcn components individually during parallel
generation — pre-install all needed primitives before dispatching `inertia-module-builder`
agents, for the same lockfile-race reason as `design-to-nextjs`.

The typical pre-install for a full app:

```bash
npx shadcn@latest add \
  button input label textarea select checkbox radio-group switch slider \
  dialog sheet drawer popover hover-card tooltip alert-dialog \
  dropdown-menu context-menu menubar navigation-menu command \
  form table card badge avatar skeleton separator scroll-area tabs accordion \
  toast sonner alert progress \
  calendar \
  breadcrumb pagination chart
```

The `sidebar` component is already present from the kit — skip it in the add command.

---

## Step 5 — Verify the scaffold before feature work

Run these checks before moving to Phase 3 (per-page translation):

```bash
# TypeScript + Vite build passes
npm run build

# shadcn primitives present
ls resources/js/components/ui/ | wc -l          # ≥ 15
test -f resources/js/components/ui/sidebar.tsx  # sidebar block
test -f resources/js/components/app-sidebar.tsx # sidebar wired
test -f components.json                          # shadcn config

# Wayfinder generated
test -d resources/js/routes                      # or wherever Wayfinder outputs

# Fortify auth pages present
test -f resources/js/pages/auth/login.tsx
test -f resources/js/pages/auth/register.tsx

# App boots cleanly
php artisan serve &
curl -s http://localhost:8000 | grep -q "login\|<!DOCTYPE" && echo "OK"
```

---

## Final scaffold state

```
my-app/
├── app/
│   ├── Http/
│   │   └── Middleware/HandleInertiaRequests.php  ← share auth props here
│   └── Providers/
├── resources/
│   ├── js/
│   │   ├── pages/
│   │   │   ├── auth/        ← Fortify pages (use as-is)
│   │   │   └── dashboard.tsx
│   │   ├── components/
│   │   │   ├── ui/          ← shadcn primitives
│   │   │   └── app-sidebar.tsx
│   │   ├── layouts/
│   │   │   ├── app-layout.tsx
│   │   │   ├── auth-layout.tsx
│   │   │   └── guest-layout.tsx
│   │   ├── hooks/
│   │   ├── lib/utils.ts     ← cn() helper
│   │   └── types/
│   │       └── index.d.ts   ← PageProps, auth.user type
│   └── views/
│       └── app.blade.php    ← Inertia root template
├── routes/
│   └── web.php              ← all Laravel routes (no separate API routes for Inertia)
├── components.json           ← shadcn config (do not re-init)
├── vite.config.ts
├── tsconfig.json
└── package.json
```

Now Phase 3 (per-page translation via `claude-design-to-inertia.md`) can begin.

---

## Anti-patterns / pitfalls

| Pitfall | Correct approach |
|---|---|
| Running `npm run build:ssr` | Run `npm run build` only — client-only (D2) |
| Running `npx shadcn@latest init` again | The kit already has `components.json` — only `npx shadcn@latest add <x>` |
| Adding shadcn components per-module during parallel generation | Pre-install all needed primitives before dispatching agents (lockfile races) |
| Forgetting `php artisan wayfinder:generate` after adding routes | Wayfinder output is build-time; stale route types cause TypeScript errors |
| Leaving unused Fortify feature routes enabled | Wayfinder generates references you never import — disable unused features in `config/fortify.php` |
| Hardcoding URL strings in `<Link href="...">` | Use Wayfinder typed helpers for all named routes |
| Treating `resources/js/pages/auth/` as translatable pages | Use the Fortify auth pages as-is unless the design specifies custom auth screens |
