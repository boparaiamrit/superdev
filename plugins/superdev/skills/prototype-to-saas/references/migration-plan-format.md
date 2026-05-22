# Migration Plan Format (Phase 3)

The MIGRATION_PLAN.md template that `migration-planner` writes and the user reviews before any code changes.

## MIGRATION_PLAN.md template

```markdown
# Migration Plan

> Generated: <ISO 8601>
> Source artifacts: DISCOVERY.md, EXTRACTED_CONTRACTS.md
> Status: AWAITING USER APPROVAL — do not start Phase 4 until confirmed

## Summary

- **Feature modules:** 11
- **Migration waves:** 5
- **Total state items classified:** 87 (KEEP: 23, REWIRE: 41, DISCARD: 23)
- **shadcn migration scope:** partial — sidebar block + form primitives + drawer
- **Risk items:** 6 (see Risks section)
- **Estimated backend modules to build:** 11
- **Estimated frontend modules to rewire:** 11

## Architectural target (same as greenfield)

- Monorepo: `apps/web` (refactored prototype) + `apps/api` (new) + `packages/contracts`
- Drizzle + TimescaleDB + Redis (Docker)
- CASL authorization, `@Audit` on mutations
- View-shape contract (no `?.` or `??` on contract data in components)
- Title Case enums everywhere
- shadcn/ui-only frontend

## Module list

| ID | Module | Wave | Source routes | Source fixtures | Notes |
|---|---|---|---|---|---|
| M-1 | auth | 1 | /login, /signup, /forgot-password | (none — mock auth currently) | Build from scratch; replace fake user context |
| M-2 | workspaces | 1 | /onboarding (workspace creation) | src/data/workspaces.json (1 record — current "demo workspace") | Wire user → workspace relationship |
| M-3 | companies | 2 | /companies, /companies/[id], /companies/new | src/data/companies.json (47 records) | High volume of compute-on-client; flag for backend |
| M-4 | contacts | 2 | /contacts, /contacts/[id], /companies/[id] (contacts tab) | src/data/contacts.json (312 records) | Cross-referenced from companies |
| M-5 | mailboxes | 2 | /mailboxes | src/data/mailboxes.json (3 records) | Empty in prototype; build from contract |
| M-6 | campaigns | 3 | /campaigns, /campaigns/[id], /campaigns/[id]/edit | src/data/campaigns.json (8 records) | Depends on companies + contacts + mailboxes |
| M-7 | pipeline | 3 | /pipeline, /leads, /deals | src/data/leads.json (25), src/data/deals.json (12) | Drag-and-drop kanban; state work non-trivial |
| M-8 | inbox | 4 | /inbox | (none — was mocked) | New entity; design implies email-received list |
| M-9 | ai | 4 | (no route; "Compose with AI" button on campaigns) | (none) | Anthropic SDK installed but unused; wire properly |
| M-10 | analytics | 5 | /analytics, /dashboard | src/data/analytics.json (precomputed) | Move all aggregation backend-side |
| M-11 | audit | 5 | (no current route) | (none) | New: audit log viewer for compliance |

## Waves

```
Wave 1 (foundation):     auth, workspaces
Wave 2 (independent):    companies, contacts, mailboxes
Wave 3 (depends on W2):  campaigns, pipeline
Wave 4 (engines):        inbox, ai
Wave 5 (read-side):      analytics, audit
```

Each wave builds backend modules in parallel; rewire passes follow in same wave order. Frontend rewiring of a module can begin as soon as that module's backend is up and seeded.

## Per-module migration plans

### M-3: companies

**Routes:** /companies, /companies/[id], /companies/new

**Source fixtures (to be moved to apps/web/src/mocks/companies/ during Phase 4.0):**
- `src/data/companies.json` (47 records) → `apps/web/src/mocks/companies/list.json`
- Split off detail samples → `apps/web/src/mocks/companies/detail.json`
- Sample create/update payloads (newly written) → `apps/web/src/mocks/companies/create.json`, `update.json`

**Seed source:**
- `src/data/companies.json` re-cased to Title Case (per EXTRACTED_CONTRACTS.md drift D-1, D-3)

**Classification of state in this module:**

| Component | State | Classification | Notes |
|---|---|---|---|
| `list.tsx` line 22: `const [companies, setCompanies] = useState(...)` | Local list cache | DISCARD | Replace with TanStack Query data |
| `list.tsx` line 24: `const [filter, setFilter] = useState('')` | Filter input | KEEP_AS_IS | Pure UI state; passes to query hook as param |
| `list.tsx` line 26: `const [sortBy, setSortBy] = useState('name')` | Sort selection | KEEP_AS_IS | Same — passes to query hook |
| `list.tsx` lines 28-40: `useMemo` filter+sort+slice | Client-side compute | REWIRE_TO_API | Move filter+sort+paginate to query params |
| `list.tsx` line 88: row click handler | Navigation | KEEP_AS_IS | Just router.push |
| `add-button.tsx` line 14: dialog open state | UI state | KEEP_AS_IS | Stay as useState |
| `add-button.tsx` line 35: `setCompanies([...companies, new])` | In-memory mutation | DISCARD | Replace with `useCreateCompany().mutate()` |
| `detail.tsx` line 18: `const company = companies.find(c => c.id === id)` | Lookup in cached array | REWIRE_TO_API | Replace with `useCompany(id)` |
| `detail.tsx` line 42-48: headcount delta computation | Client compute | DISCARD | Now in view shape; render `company.headcount.delta_pct` directly |
| `detail.tsx` line 61: tab state (overview/contacts/leads) | UI state | KEEP_AS_IS | |

**Backend module to build (Phase 4):**
- Drizzle schema: `companies` table with TitleCase enums
- Endpoints: `GET /companies` (with `?q=&industry=&sort=&page=&per_page=`), `GET /companies/:id`, `POST`, `PATCH`, `DELETE`
- Presenter: builds `headcount.{current,twelve_months_ago,delta_pct,growth_signal}` from raw fields + queries `contacts_count`, `open_leads_count`, `won_deals_count` from related tables
- `@CheckAbility` on every endpoint
- `@Audit` on create/update/delete
- Seed script imports `src/data/companies.json` with Title Case re-casing

**Rewire steps (Phase 5):**
1. Move `src/data/companies.json` → `apps/web/src/mocks/companies/list.json` (re-format if needed to match view-shape contract for demo mode)
2. Create `apps/web/src/modules/companies/api.ts` with `getCompanies()`, `getCompany()`, `createCompany()`, `updateCompany()`, `deleteCompany()`
3. Create `apps/web/src/modules/companies/hooks/use-companies.ts` and `use-companies-mutations.ts`
4. Edit `list.tsx`: replace `useState(initialCompanies)` with `useCompanies({ filter, sortBy, page })`
5. Edit `add-button.tsx`: replace `setCompanies` with `useCreateCompany().mutate`
6. Edit `detail.tsx`: replace lookup with `useCompany(id)`; strip headcount computation
7. Delete the source fixture from `src/data/companies.json` (now lives in mocks/)
8. Run `pnpm validate:fixtures` for the new mocks; run typecheck + lint + smoke test in both modes

### M-7: pipeline (HIGH-RISK)

**Routes:** /pipeline (kanban view), /leads, /deals

**Special concern:** the kanban has drag-and-drop that currently mutates client state. Real backend needs `PATCH /leads/:id` with stage change, and the UI needs optimistic update with rollback on error.

**Classification:**

| Component | State | Classification | Notes |
|---|---|---|---|
| `kanban.tsx` line 30: column state | Server data | REWIRE_TO_API | TanStack Query keyed by `stage` |
| `kanban.tsx` line 78: drag handler updates local order | Mutation | REWIRE_TO_API | Optimistic update + PATCH /leads/:id |
| `kanban.tsx` line 92: `setColumns(reorder(...))` | In-memory mutation | DISCARD | Replace with mutation + onMutate optimistic |

**Risks for this module:**
- Drag-and-drop UX must NOT regress. Optimistic update is mandatory; user can't wait for API roundtrip.
- Sorting within a column was client-side (lead.created_at); ensure backend returns same order.

### (... similar entries for every module ...)

## shadcn migration scope

The prototype has shadcn initialized but only 8 primitives installed. Missing:

- sidebar block (currently a custom `<aside>` in `app/(authed)/layout.tsx`)
- form (currently raw react-hook-form; replace with shadcn `<Form>` wrapper)
- drawer (used in 2 mobile flows; currently raw modal pretending to be a drawer)
- command (used by "Cmd+K search" feature; currently a hand-rolled `<input>` filter)
- chart (used in dashboard; currently raw recharts — wrap in shadcn `<ChartContainer>`)
- toast (currently using `react-hot-toast`; replace with shadcn sonner)

**Scheduled for `monorepo-bootstrapper` in Phase 4.0:**

```bash
pnpm dlx shadcn@latest add \
  sidebar form drawer command chart sonner \
  textarea checkbox radio-group switch slider \
  popover hover-card tooltip alert-dialog \
  dropdown-menu context-menu menubar navigation-menu \
  avatar skeleton separator scroll-area tabs accordion \
  alert progress calendar date-picker breadcrumb pagination
```

**Per-module shadcn work scheduled into `frontend-rewirer`:**

- M-2 workspaces: migrate the layout sidebar to shadcn sidebar block
- M-7 pipeline: kanban currently uses `@dnd-kit/core` (acceptable — shadcn doesn't ship a kanban); column header uses raw `<select>`, switch to `<Select>`
- M-10 analytics: charts wrapped in shadcn `<ChartContainer>`
- (modules with shadcn already passing: M-3 companies, M-4 contacts, M-6 campaigns)

**To remove from package.json:**
- `react-hot-toast` (replaced by sonner)
- Anything else discovered during rewiring that competes with shadcn

## Seed plan

For each module's Phase 4 backend-extractor:

| Module | Seed source | Re-casting | Records |
|---|---|---|---|
| M-2 workspaces | src/data/workspaces.json | (none — already correct) | 1 |
| M-3 companies | src/data/companies.json | industry: lowercase → Title Case | 47 |
| M-4 contacts | src/data/contacts.json | role: SCREAMING_CASE → Title Case | 312 |
| M-5 mailboxes | (none — empty seed) | — | 0 |
| M-6 campaigns | src/data/campaigns.json | status: lowercase → Title Case | 8 |
| M-7 pipeline (leads + deals) | src/data/leads.json + deals.json | stage: lowercase_underscored → Title Case (e.g. proposal_sent → Proposal Sent) | 37 |
| M-10 analytics | (none — computed live from other tables) | — | 0 |

**A single workspace ID is hardcoded into seeds during dev:** all records go to the "demo workspace" created by M-2's seed. Real users create new workspaces post-launch.

## Demo-mode preservation

After migration:

- Every JSON file currently in `src/data/` is moved to `apps/web/src/mocks/<feature>/` and reformatted (if needed) to match the view-shape contract
- `apps/web/src/app/api/mock/[...path]/route.ts` serves these via dual-mode adapter (`NEXT_PUBLIC_API_MODE=demo`)
- `pnpm validate:fixtures` runs every mock through its Zod schema

**Verification:** at the end of Phase 5, `NEXT_PUBLIC_API_MODE=demo pnpm dev` renders every route with the same data the prototype had.

## Risks

### R-1 [High] — Lead score calculator

- Location: `src/modules/leads/components/score-calculator.tsx:12-44`
- Complexity: ~50 lines of business logic using contact count, last activity, deal value
- Migration: move to backend `leads.service.computeScore()`; expose as `lead.score: number` in view shape
- Test gap: no tests exist for the formula; risk of behavior drift during port
- Mitigation: in Phase 4 backend-extractor, write tests that assert score for fixture records matches what the FE currently computes; if they diverge, choose intentional value

### R-2 [High] — Hardcoded Stripe test key

- Location: `src/lib/stripe.ts:8` (per DISCOVERY.md SECURITY-IMMEDIATE)
- Action: USER rotates the key at Stripe before any commits push to remote; replace literal with `process.env.STRIPE_SECRET_KEY`
- Scheduled: BEFORE Phase 4 starts. Do NOT proceed without this being addressed.

### R-3 [Medium] — Stale TS interfaces

- Location: `src/types/*.ts` (per EXTRACTED_CONTRACTS.md drift findings)
- Action: replace every `import { Company } from '@/types/company'` with `import { CompanyView } from '@<scope>/contracts/companies'`; delete the local types/ folder after migration

### R-4 [Medium] — Auth context wired everywhere

- Location: `useAuth()` from `src/lib/auth-context.tsx` is imported in 23 components
- Action: replace context with real-auth-provided hook from `apps/web/src/modules/auth/hooks/use-auth.ts`; same hook signature where possible to limit per-file changes

### R-5 [Medium] — Drag-and-drop kanban (M-7)

- See M-7 plan above. Optimistic updates required.

### R-6 [Low] — `next-auth` in devDependencies

- Was attempted, abandoned. Remove from package.json during M-1 (auth module build).

## Open items (needs user decision)

- **O-1: Templates.** A "Templates" sidebar item exists in the layout but no page implements it; DISCOVERY notes it as "Coming soon". Is this in scope for v1? If yes, schedule a module. If no, hide the sidebar item until v2.
- **O-2: AI compose.** `@anthropic-ai/sdk` is installed; a "Compose with AI" button exists on campaigns. Is AI in v1? If yes, schedule M-9 ai (currently in Wave 4); if no, remove the button.
- **O-3: Mobile.** Designs include a mobile menu drawer but the prototype only works at desktop widths. Mobile breakpoints in scope for v1?

## Acceptance criteria

Migration complete when:

- All 11 modules built (backend + rewired frontend)
- `pnpm dev:infra && pnpm dev` brings up everything from a fresh clone
- Demo mode renders every screen with mock data
- Production mode renders every screen with API data from the seeded backend
- Original prototype URL paths still work (no broken links)
- `ui-auditor` clean across `apps/web/src/modules/`
- `integration-tester` passes
- Security skill (if installed) returns zero unresolved Critical findings
- No fixture file remains in the OLD location (`src/data/`); all moved to `apps/web/src/mocks/` or seeded into backend
```

## Approval gate

Before the user approves MIGRATION_PLAN.md, the orchestrator surfaces:

```
MIGRATION PLAN READY FOR REVIEW

11 feature modules across 5 waves.
- 23 KEEP_AS_IS state items (unchanged)
- 41 REWIRE_TO_API state items (data flow rewrite)
- 23 DISCARD items (fake-backend cruft removed)

shadcn migration: 6 missing primitives to install; 1 custom-sidebar to replace; ~4 modules need minor primitive swaps.

Seed sources mapped for 6 modules; 5 modules start with empty data.

6 risks flagged:
  R-1 [High]  Lead score calculator — needs port + tests
  R-2 [High]  Hardcoded Stripe key — rotate FIRST
  R-3 [Med]   Stale TS interfaces — replace during rewire
  R-4 [Med]   Auth context in 23 files — replace via consistent hook
  R-5 [Med]   Drag-and-drop kanban — optimistic update required
  R-6 [Low]   next-auth devDep — remove during M-1

3 open items need user decision:
  O-1: Templates feature in v1 or v2?
  O-2: AI compose in v1 or v2?
  O-3: Mobile breakpoints in v1 or v2?

Approve plan? [Y/n] — or list specific items to revise.
```

Do not proceed past this gate without explicit user confirmation. Revisions go back to `migration-planner` with notes.
