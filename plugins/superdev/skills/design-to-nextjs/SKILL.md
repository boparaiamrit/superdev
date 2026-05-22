---
name: design-to-nextjs
description: Convert design handoff bundles from claude.ai/design (or other design-to-code tools) into a production-grade enterprise Next.js codebase using App Router, Tailwind, TanStack Query, TanStack Table, Zustand, Zod, React Hook Form, and TypeScript strict. The skill supports a dual-mode adapter pattern — a demo mode where every API call reads from local JSON fixtures, and a production mode that hits a real backend (typically Nest.js), switched by NEXT_PUBLIC_API_MODE. Use this skill any time the user mentions a design.html, a handoff bundle, design tokens, converting a prototype to Next.js/React, or "design to code". Use it even with just one HTML file, screenshots, or a verbal description — the skill walks through inventory, token extraction, module planning, scaffolding, dual-mode adapter setup, and module-by-module code generation. Especially trigger when the user mentions enterprise structure, demo mode, JSON mocks, TanStack patterns, or Tailwind token extraction.
---

# Claude Design → Next.js Enterprise Conversion

A pipeline for turning Claude Design HTML output into a production-grade Next.js application. The skill operates in five phases. Walk them in order; skipping phases produces the throwaway code most "design-to-code" pipelines generate.

## When to use this skill

Use whenever the user has Claude Design output (HTML, screenshots, a handoff `.zip`, or a Claude Code handoff folder) and wants a Next.js codebase that is actually maintainable. The trigger is the *combination* of (a) Claude Design as the input source and (b) Next.js/React as the target. If either is absent, this skill is the wrong tool.

Do NOT use this skill for:
- Converting Figma → React (different input shape; no design system extraction step from Claude Design's tokens)
- Building a Next.js app from a written spec/PRD with no design artifacts (use the design tooling first, or scaffold from the spec directly)
- One-off HTML snippet → single React component (overkill; just do it)

## How to invoke this skill

This is a **recipe skill** — it provides the patterns and references that builder agents follow. Three invocation paths:

### Pattern 1 — invoked by the orchestrator (most common)

When `prd-design-build-orchestrator` runs, its `frontend-module-builder` subagent reads this skill's references directly. No separate invocation needed; the orchestrator's Phase A.1 install puts this skill at `~/.claude/skills/design-to-nextjs/`, and the builder reads `SKILL.md` + relevant references per the module it's building.

### Pattern 2 — invoked by the migration skill

When `prototype-to-saas` runs Phase 4.0 (bootstrap), the `monorepo-bootstrapper` agent reads this skill's `references/scaffolding.md` to set up shadcn correctly in `apps/web/`. Phase 5's `frontend-rewirer` reads `references/tanstack-patterns.md` and `references/dual-mode-adapter.md` for rewiring patterns.

### Pattern 3 — standalone (frontend-only build)

For frontend-only builds without the orchestrator (e.g., converting a Claude Design output into a Next.js codebase you'll wire to an existing backend), start a Claude Code session:

```
I have a Claude Design handoff at design/index.html and screenshots in design/screenshots/.
Build a production Next.js codebase from it.
```

The main session reads this skill's SKILL.md and walks the five phases (inventory, tokens, planning, scaffolding, module generation). No subagents required for this path; the main session does the work.

## Target stack

The output is always:

- **Next.js 14+** with App Router, TypeScript strict mode, `src/` directory
- **Tailwind CSS 3.4+** with tokens extracted from the design output
- **TanStack Query v5** (`@tanstack/react-query`) for all server state
- **TanStack Table v8** (`@tanstack/react-table`) for every data table in the design
- **Zustand 4+** for client/UI state only (never server state)
- **Zod** for runtime validation of API responses + form schemas
- **React Hook Form** for all forms (paired with Zod resolvers)
- **shadcn/ui** for primitive components (Button, Input, Dialog, etc.) unless the user explicitly opts out
- **lucide-react** for icons

If the user requests a different state library (Jotai, Redux Toolkit), tooltip library, or icon set, swap the relevant module — everything else stays.

## Architectural commitments (non-negotiable)

These are baked into every generated app. They are not configurable — if the user wants a different shape, push back and explain why.

### 1. Monorepo with shared contracts

The Next.js app lives at `apps/web/` in a pnpm workspace. Zod schemas and TypeScript types come from `packages/contracts` (workspace dep `@<scope>/contracts`), which is shared with the Nest.js backend (`apps/api/`). The frontend never defines its own response schemas — it imports them.

```
<workspace>/
├── apps/
│   ├── web/                  ← This skill's output
│   └── api/                  ← nestjs-enterprise-backend skill's output
├── packages/
│   └── contracts/            ← Zod schemas + view types — SINGLE SOURCE OF TRUTH
```

If the user is starting fresh, scaffold the monorepo first (using the procedure in the `nestjs-enterprise-backend` skill's `monorepo-setup.md`), then run this skill inside it. If the user already has a monorepo, scaffold the Next.js app at `apps/web/`.

### 2. View-shape contract — render without `?.` or `??`

The backend returns view-ready data. Frontend code **never** uses `?.` or `??` to defend against missing fields. This is non-negotiable.

What that means in practice:

- **Counts are always numbers**, defaulted to 0 on the backend. `company.counts.contacts` is a `number`, not `number | undefined`.
- **Labels are pre-built server-side.** A growth signal returns as `{ kind: 'growing', label: '+12% YoY' }` — render `signal.label`, don't compute.
- **Variations are discriminated unions.** `last_activity` is `{ kind: 'None' } | { kind: 'Email Sent', label: string } | ...`. Pattern-match on `kind`; don't check for null.
- **Dates are ISO 8601 strings.** Convert to `Date` at the render site if needed; the type is never `Date | undefined`.
- **Genuinely nullable fields are explicit.** `domain: z.string().nullable()` is fine; `domain: z.string().optional()` is a smell.

The Zod schemas in `@<scope>/contracts` enforce this — they don't use `.optional()` on data fields, only on filter inputs. If the user adds an optional field to a view schema, push back.

Frontend reviewers should grep for `?.` and `??` in JSX and ask: "Is this defending against a contract gap, or genuinely null-safe?" If the former, fix the contract.

### 3. Dual-mode adapter (demo + production)

Every generated app supports two modes, switched by `NEXT_PUBLIC_API_MODE`:

- **`demo`** — every API call reads from local JSON fixtures under `src/mocks/`, served by a Next.js Route Handler at `/app/api/mock/[...path]/route.ts`. No backend required.
- **`production`** — every API call hits the Nest.js backend at `NEXT_PUBLIC_API_BASE_URL`.

The production code path is **identical between the two modes** — same hooks, same Zod validation (against `@<scope>/contracts` schemas), same error handling. Only the base URL differs.

JSON fixtures live under `apps/web/src/mocks/<module>/` and validate against the same `@<scope>/contracts` schemas the backend's presenters produce. A CI script (`pnpm validate:fixtures`) runs every fixture through `companyViewSchema.parse(fixture)` — drift fails the build. See `references/dual-mode-adapter.md`.

### 4. Title Case for every enum value — render directly, no conversion

Every enum string in `@<scope>/contracts` (statuses, stages, roles, industries, discriminator `kind` fields) is **Title Case**. Components render `company.status` directly — no `.toUpperCase()`, no `STATUS_LABELS` lookup, no `humanize()` helper.

**Good:**

```tsx
<Badge>{company.status}</Badge>          {/* "Active" */}
<span>{lead.stage}</span>                {/* "Proposal Sent" */}
<chip>{user.role}</chip>                 {/* "Operator" */}
{activity.kind === 'Email Sent' && <Icon name="mail" />}
```

**Bad — none of this in component code:**

```tsx
<Badge>{capitalize(company.status)}</Badge>
<span>{STAGE_LABELS[lead.stage]}</span>
<chip>{user.role.toLowerCase()}</chip>
```

If you find yourself reaching for a capitalize/humanize/labelize helper on contract data, the contract is wrong — fix the backend value, not the frontend.

Numeric ranges like `"1-10"` and `"51-200"` (size_bucket) are not word-based and render naturally — append units in the view if needed (`{company.size.bucket} employees` → `"51-200 employees"`).

Fixture files in `src/mocks/` use the same Title Case values byte-for-byte. The `validate:fixtures` script catches drift.

### 5. shadcn/ui is the ONLY visual primitive library

Every primitive in the app — buttons, inputs, selects, dialogs, tables, cards, badges, dropdowns, tooltips, popovers, sheets, drawers, sidebars, command palettes, toasts — comes from shadcn/ui via `@/components/ui/*`. The scaffolding step runs `pnpm dlx shadcn@latest add ...` for every primitive plus the **sidebar block** up front, so when feature modules are built they import directly without re-installing.

Forbidden alongside shadcn:

```
@radix-ui/*       (use @/components/ui/* — shadcn already wraps Radix correctly)
@headlessui/*
@mui/*, @material-ui/*
@chakra-ui/*
@mantine/*
antd, @ant-design/*
react-bootstrap, bootstrap
semantic-ui-react
flowbite-react
@nextui-org/*
tremor, @tremor/*
daisyui
```

Hand-rolled primitives are also banned. If you find yourself writing a 30-line `<MyButton>` that wraps `<button>` with Tailwind classes, stop — use shadcn's `<Button>`.

**Every sidebar uses shadcn's sidebar block** (`<Sidebar>`, `<SidebarProvider>`, `<SidebarTrigger>`, `<SidebarMenu>`, `<SidebarMenuItem>`, `<SidebarHeader>`, `<SidebarContent>`, `<SidebarFooter>` from `@/components/ui/sidebar`). No custom `<aside className="w-64 ...">` constructions in `layout.tsx`. If the design shows a sidebar variant the block doesn't natively support (e.g. floating, mini-mode), use the block's built-in variants (`collapsible="icon"`, `variant="floating"`, etc.) rather than re-implementing.

**Raw HTML primitives in component code are forbidden where a shadcn equivalent exists:** no `<button>`, `<input>`, `<select>`, `<textarea>`, `<dialog>`. Layout elements (`<div>`, `<section>`, `<nav>`, `<ul>`, `<li>`) are fine — shadcn doesn't ship those.

**The exception** is the rare case where shadcn genuinely doesn't have something. shadcn covers ~50 primitives — almost everything. If something is missing, surface as a question rather than reaching for an alternative library.

This commitment is enforced by the `ui-auditor` agent at every wave gate (in orchestrator mode) and as a standalone grep when this skill runs alone — see the validation checklist.

## The five-phase pipeline

```
Phase 1: Inventory        → Read every HTML file, screenshot, note. Catalog everything.
Phase 2: Token Extraction → Pull design tokens into a Tailwind config + tokens file.
Phase 3: Module Planning  → Split the design into bounded feature modules. Get user buy-in.
Phase 4: Scaffolding      → create-next-app, install deps, set up providers + base files.
Phase 5: Module Generation → For each module: types → schemas → api → hooks → store → components → page.
```

Walk them in order. Phase 3 has a mandatory user-confirmation gate (don't generate code against a module plan the user hasn't seen). Phases 4 and 5 can be partially parallelized but should be presented to the user sequentially.

---

## Phase 1 — Inventory the input

**Goal:** Build a complete catalog of what's in the Claude Design output before writing any code.

**Inputs you might receive:**
- A folder containing `design.html` + `screenshots/` + `design-notes.md` + `README.md` (standard handoff bundle)
- A single `design.html` file
- A `.zip` archive that needs extraction
- Multiple HTML files in a folder (one per screen)
- Just screenshots (rare — degrade gracefully)
- A URL pointing to a hosted Claude Design preview

**Step 1.1 — Locate and inspect.** Use `view` on the folder if it's a directory, then read every HTML file. If there's a `design-notes.md` or `README.md`, read those first — they contain the PM's intent. Do not skim these. The design notes often contain critical information that the HTML doesn't (e.g., "this list is server-paginated", "the table should support multi-select").

**Step 1.2 — Catalog the screens.** A "screen" maps roughly 1:1 to a Next.js route. For each HTML file (or each major `<section>` block in a single-file design), record:

- Screen name (best guess; confirm with user later)
- Auth requirement (login screens are public; dashboards are gated)
- Route path suggestion (e.g., `/companies`, `/companies/[id]`, `/inbox`)
- Whether it's a list, detail, form, or composite view

**Step 1.3 — Catalog repeated patterns.** Walk each HTML file and identify components that appear more than twice. These are the candidates for `components/ui/` or module-scoped components. Common examples in CRM/SaaS designs: card, stat tile, table row, badge, avatar, empty state, toolbar, filter chip, side drawer.

**Step 1.4 — Catalog tables.** Every `<table>` or grid-like structure becomes a TanStack Table. For each, record:

- Columns (label, what data it shows, sortable/filterable hints from the design)
- Whether the design implies server-side or client-side pagination
- Selection model (single, multi, none)
- Row actions (the `...` menu, inline buttons)

**Step 1.5 — Catalog forms.** Every form becomes a React Hook Form + Zod schema. For each:

- Fields (name, type, required, validation hints from the design)
- Submit behavior (suggests a mutation)
- Multi-step? (suggests a wizard pattern + a Zustand store for cross-step state)

**Step 1.6 — Catalog interactive widgets.** Drawer/modal/dropdown/tabs/accordion — note them, but don't over-engineer; most will become shadcn/ui primitives.

**Step 1.7 — Read `design-notes.md` for intent that isn't in the HTML.** Empty states, loading states, error states, what happens on hover, animation hints, accessibility requirements.

**Output of Phase 1:** an inventory document. Write it out as `INVENTORY.md` in the working directory so the user can review it. Keep it terse — bullet lists, no prose.

---

## Phase 2 — Token extraction

**Goal:** Extract design tokens (colors, typography, spacing, radii, shadows, motion) from the Claude Design HTML into a Tailwind config + a `tokens.ts` file. This is the single highest-leverage step. Skipping it leads to hex codes scattered across components and a UI that drifts within a week.

See `references/token-extraction.md` for the full extraction procedure and the canonical `tailwind.config.ts` template.

**Quick summary of what to extract:**

1. **Colors** — collect every unique hex/rgb/hsl value from inline styles and Tailwind classes (`bg-[#1a2b3c]`, `text-[hsl(220_30%_15%)]`). Cluster by purpose (brand, surface, text, border, status). Name them semantically (`brand.500`, `surface.muted`, `text.primary`), not by hex.
2. **Typography** — font families (look for `font-family` in inline styles or `font-['...']` in classes), font sizes used, weights used, line-heights. Build a type scale even if the design uses arbitrary sizes.
3. **Spacing** — Tailwind has a default scale (0, 0.5, 1, 1.5, 2, ...); extend only if the design uses arbitrary values consistently.
4. **Radii** — round any inline `border-radius` values to the nearest Tailwind step or add custom ones.
5. **Shadows** — extract every shadow into a named token.
6. **Breakpoints** — usually leave as default unless the design uses custom ones.
7. **Motion** — durations and easings used in `transition` and `@keyframes`.

**Output of Phase 2:**
- `tailwind.config.ts` (final form, ready to drop in)
- `src/styles/tokens.ts` (raw token values for use in JS/TS)
- `src/styles/globals.css` (CSS custom properties for dark mode / theming if applicable)

---

## Phase 3 — Module planning (mandatory user-confirmation gate)

**Goal:** Decide how the design splits into feature modules before any code is generated. Get explicit user sign-off before proceeding.

**Why this gate matters:** Module boundaries are the single most expensive thing to change later. A feature scoped wrong now becomes a multi-week refactor in three months. Always show the proposed split to the user and wait for confirmation.

See `references/enterprise-structure.md` for the canonical folder layout and module conventions.

**Step 3.1 — Group screens into modules.** A module is a bounded business capability. For an <APP_NAME>-like product, typical modules:

- `auth` — login, signup, password reset, MFA
- `workspace` — workspace settings, members, billing
- `companies` — list, detail, import, custom fields
- `contacts` — list, detail, conversation history
- `campaigns` — list, builder, preview, send
- `inbox` — unified inbox, thread view, reply
- `pipeline` — kanban board, lead detail, deal conversion
- `analytics` — dashboards, reports

The right module count for most products is 5–10. Fewer than 5 = monolith risk. More than 12 = over-fragmented.

**Step 3.2 — Identify shared primitives.** What lives in `components/ui/` (shadcn primitives) vs `components/shared/` (cross-module composites like `<DataTable>`, `<PageHeader>`, `<EmptyState>`).

**Step 3.3 — Identify cross-module dependencies.** A `Lead` references a `Contact` references a `Company`. Decide whether modules expose typed public APIs (`modules/companies/index.ts` re-exports types + hooks) or whether everything imports from deep paths. Default to **typed public APIs** — it forces clean boundaries.

**Step 3.4 — Present the plan to the user.** Show:

```
Proposed modules:
1. auth         — login, signup, password reset
2. workspace    — settings, members
3. companies    — list, detail, import wizard
4. contacts     — list, detail
5. campaigns    — builder, list, preview
6. inbox        — threads, reply
7. pipeline     — kanban, lead detail
8. analytics    — dashboard, reports

Shared components/ui:    Button, Input, Select, Dialog, DropdownMenu, Toast, Badge, Avatar, Skeleton
Shared components/shared: DataTable, PageHeader, EmptyState, LoadingState, ErrorBoundary, FilterBar, KanbanBoard

Cross-module dependencies:
  pipeline → contacts → companies
  inbox    → contacts
  campaigns → contacts

Confirm or revise.
```

**Wait for confirmation before moving to Phase 4.** If the user pushes back, iterate. Do not skip this gate even if the user seems impatient — a wrong module split costs more time than the confirmation step does.

---

## Phase 4 — Scaffolding

**Goal:** Get a runnable Next.js app with all dependencies, providers, and base files in place. The app should `pnpm dev` cleanly with an empty home page before any feature code is added.

See `references/scaffolding.md` for the full setup procedure (commands, config files, providers).

**Order of operations:**

1. `pnpm create next-app@latest` with: TypeScript yes, ESLint yes, Tailwind yes, src/ yes, App Router yes, custom alias `@/*`, Turbopack yes (Next 15+)
2. Install runtime deps: `@tanstack/react-query @tanstack/react-query-devtools @tanstack/react-table zustand zod react-hook-form @hookform/resolvers lucide-react clsx tailwind-merge class-variance-authority`
3. Install dev deps: `@types/node prettier prettier-plugin-tailwindcss eslint-config-prettier`
4. Initialize shadcn/ui: `pnpm dlx shadcn@latest init`
5. Drop in the `tailwind.config.ts` and `tokens.ts` produced in Phase 2
6. Set up the four base files (see `references/scaffolding.md`):
   - `src/lib/query-client.ts` — QueryClient singleton with sensible defaults
   - `src/app/providers.tsx` — wraps QueryClientProvider + any other providers (theme, toast)
   - `src/app/layout.tsx` — imports providers, applies fonts, sets html lang
   - `src/lib/api-client.ts` — fetch wrapper with auth headers, error normalization, Zod parsing
7. Set up the enterprise folder layout (empty directories with `.gitkeep`):
   ```
   src/
   ├── app/
   ├── components/
   │   ├── ui/        ← shadcn primitives go here
   │   └── shared/    ← cross-module composites
   ├── modules/       ← one folder per planned module
   ├── lib/
   ├── hooks/
   ├── stores/        ← global Zustand stores only
   ├── styles/
   └── types/
   ```
8. Configure path aliases in `tsconfig.json`: `@/*`, `@/modules/*`, `@/components/*`, `@/lib/*`
9. Set up ESLint + Prettier + (optionally) Husky + lint-staged
10. Verify the app boots: empty home page should render

**Don't generate feature code until scaffolding boots cleanly.** It's much harder to debug missing-provider or path-alias issues once 50 files are in flight.

---

## Phase 5 — Module-by-module generation

**Goal:** For each planned module, generate the code in a deterministic order. Resist the urge to start with components — components without types/hooks behind them encode bad assumptions that are painful to undo.

**The canonical order within a module:**

```
1. (schemas come from @<scope>/contracts; no local types or schemas)
2. api/       — fetcher functions (getCompanies, createCompany) using the api-client wrapper,
                 typed against schemas imported from @<scope>/contracts
3. hooks/     — TanStack Query hooks (useCompanies, useCreateCompany, useUpdateCompany)
4. store/     — Zustand store IF AND ONLY IF the module has UI state that crosses components
                 (e.g., a multi-step form, a selection state shared between toolbar and table)
5. fixtures   — JSON files under src/mocks/<module>/ (list.json, detail.json, create.json, ...)
                 each fixture validates against the module's schema in @<scope>/contracts
6. components/ — feature components, including DataTable column defs.
                 NO ?. or ?? — render contract fields directly.
7. (pages)    — files under src/app/(route-group)/ that import from modules/
```

See `references/tanstack-patterns.md` for query/mutation patterns, `references/zustand-patterns.md` for store conventions, `references/component-patterns.md` for translating design HTML to React components, and `references/dual-mode-adapter.md` for fixture authoring rules.

**Tactical rules during generation:**

- **Server Components by default.** Mark client components with `'use client'` only when you need event handlers, hooks, or browser APIs. Lists are server components; tables that filter/sort/paginate are client.
- **Never use Zustand for server state.** TanStack Query owns the cache. Zustand owns ephemeral UI state (modal open/closed, selected row IDs, active tab).
- **Every API response goes through Zod.** The api-client wrapper takes a Zod schema and returns the parsed type. This catches contract drift the moment it happens.
- **Every form uses React Hook Form + Zod resolver.** No raw `useState` for forms. No uncontrolled inputs.
- **Every table uses TanStack Table.** No raw `<table>` with manual state. The `<DataTable>` shared component takes column defs + data + options.
- **Imports respect module boundaries.** Within a module, deep imports are fine. From outside, import only from the module's `index.ts`.

**Order across modules:** start with the module that has the most cross-module dependents (usually `companies` or `auth` for a CRM). Build it end-to-end (types → page renders with mock data). Then build the next module that depends on it. This produces working slices instead of half-built layers.

---

## Validation checklist

Before declaring done, walk this list:

- [ ] `pnpm typecheck` passes (TypeScript strict, no `any`)
- [ ] `pnpm lint` passes (zero warnings, not just zero errors)
- [ ] `pnpm build` succeeds
- [ ] `pnpm validate:fixtures` passes (every JSON fixture conforms to its `@<scope>/contracts` Zod schema)
- [ ] **No `?.` or `??` in `src/modules/**/components/`** — grep and review every hit. If it's defending against a contract gap, fix the contract; if it's genuine null safety on a `nullable` field, leave it.
- [ ] **No local Zod schemas in `apps/web/src/`** — all schemas come from `@<scope>/contracts`. Grep for `z.object` outside `node_modules`; non-form schemas are a smell.
- [ ] **No enum casing helpers in components** — grep for `capitalize`, `humanize`, `toLowerCase`, `toUpperCase`, `LABELS[`, `_LABEL` inside `src/modules/**/components/`. Any hit on contract data means a contract value isn't Title Case; fix the contract, not the component.
- [ ] **shadcn primitives installed** — `apps/web/components.json` exists, `apps/web/src/components/ui/` has ≥30 primitive files, `apps/web/src/components/ui/sidebar.tsx` exists
- [ ] **No competing UI libraries** — `grep -rEn "from '(@radix-ui/|@headlessui/|@mui/|@material-ui/|@chakra-ui/|@mantine/|antd|@ant-design/|react-bootstrap|flowbite-react|@nextui-org/|tremor|@tremor/|daisyui)" apps/web/src --include="*.tsx" --include="*.ts" | grep -v "apps/web/src/components/ui/"` returns ZERO hits
- [ ] **No raw HTML primitives where shadcn equivalents exist** — `grep -rEn "<button(\\s|>)|<input(\\s|>)|<select(\\s|>)|<textarea(\\s|>)|<dialog(\\s|>)" apps/web/src/modules --include="*.tsx" | grep -v "apps/web/src/components/ui/"` returns zero hits (excepting hidden inputs)
- [ ] **Sidebar uses shadcn block** — every layout with navigation imports from `@/components/ui/sidebar`; no custom `<aside className="w-64 ...">` in any `layout.tsx`
- [ ] **No hand-rolled primitives in modules** — `function MyButton`, `function MyDialog`, etc. that wrap raw HTML
- [ ] **No arbitrary color/radius Tailwind classes** — `grep -rEn "(bg|text|border)-\\[#[0-9a-fA-F]{3,8}\\]|rounded-\\[" apps/web/src/modules` returns zero hits
- [ ] App boots cleanly in **demo mode** — every route renders with realistic fixture data
- [ ] App boots cleanly in **production mode** when pointed at the Nest.js backend
- [ ] Every route in the design renders at `/[route]`
- [ ] Every table sorts and filters
- [ ] Every form submits and shows loading + error + success states
- [ ] Every mutation invalidates the right queries
- [ ] Dark mode (if in the design) toggles correctly
- [ ] Responsive: 375px, 768px, 1280px — no horizontal scroll
- [ ] No hex codes outside `tailwind.config.ts` and `tokens.ts`
- [ ] No `console.log` left in code
- [ ] No `// TODO` left without a tracking issue

If the user provided screenshots, do a final visual diff: open the screenshot and the live page side-by-side, compare spacing, color, typography. Flag any drift.

---

## Reference files

Load these as needed during the phases above. Each is focused; don't read all of them upfront.

| File | When to read |
|---|---|
| `references/enterprise-structure.md` | Phase 3 (module planning), Phase 4 (folder setup) |
| `references/token-extraction.md` | Phase 2 (token extraction) |
| `references/scaffolding.md` | Phase 4 (project scaffold, config files, provider setup) |
| `references/dual-mode-adapter.md` | Phase 4 (mocks folder + Route Handler), Phase 5 (every module's `api.ts` and fixtures) |
| `references/component-patterns.md` | Phase 5 (translating HTML → React components) |
| `references/tanstack-patterns.md` | Phase 5 (Query hooks, Table column defs, mutation patterns) |
| `references/zustand-patterns.md` | Phase 5 (when to use Zustand and the store conventions) |

---

## Common pitfalls

These come up every time. Watch for them.

**Pitfall 1: Treating Claude Design's HTML as the final markup.** It isn't. It's a *visual specification*. The job is to re-implement against the target stack's components, not to copy-paste HTML into JSX. If you find yourself transcribing `<div class="...">` blocks one-for-one, stop and refactor into proper components.

**Pitfall 2: Hex codes leaking into components.** Every color reference outside `tailwind.config.ts` and `tokens.ts` is technical debt. Map them all in Phase 2.

**Pitfall 3: Mixing server and client state.** Zustand for `useCompanies()` data is a smell. TanStack Query owns server state. Zustand owns UI state. Confusing these two costs weeks of refactoring later.

**Pitfall 4: Skipping Phase 3 confirmation.** Generating 50 files against the wrong module split is the most expensive failure mode. Always confirm.

**Pitfall 5: Generating components before types/hooks.** Reverse the order and components encode wrong assumptions that propagate.

**Pitfall 6: Using `useEffect` for data fetching.** Use TanStack Query. Always. `useEffect(() => fetch(...))` is a 2020 pattern.

**Pitfall 7: Over-using `'use client'`.** Most pages should be server components. Push `'use client'` to the leaves (the interactive widgets), not the page roots.

**Pitfall 8: Forgetting to set `queryKey` consistently.** Use a centralized `queryKeys` object per module (see `references/tanstack-patterns.md`) so invalidation is predictable.
