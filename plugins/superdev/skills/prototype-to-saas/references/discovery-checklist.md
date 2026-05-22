# Discovery Checklist (Phase 1)

What `codebase-discoverer` extracts. The DISCOVERY.md format below is the source of truth for everything downstream.

## DISCOVERY.md template

```markdown
# Codebase Discovery

> Generated: <ISO 8601>
> Project root: <CWD>
> Git remote: <git remote -v | head -1, if any>
> Last commit: <git log -1 --oneline, if any>

## Project shape

- **Framework:** Next.js <version>
- **Router:** App Router | Pages Router | Mixed
- **TypeScript:** strict | loose | partial (some `.js` files)
- **Package manager:** pnpm | npm | yarn | bun
- **CSS approach:** Tailwind <version> | CSS modules | styled-components | mixed
- **shadcn/ui state:** initialized | not initialized | unclear
  - `components.json` present: yes/no
  - `src/components/ui/` populated: yes/no, count of files
- **Node version:** from `.nvmrc` / `engines` / inferred
- **Backend present:** no | partial (some Route Handlers, no DB)
- **Auth state:** none | scaffolded but not wired | mocked via context | real provider installed but unused

## Routes (App Router)

| Route | File | Auth implied | Layout group | Notes |
|---|---|---|---|---|
| / | app/page.tsx | no | (root) | Landing page |
| /companies | app/companies/page.tsx | yes (sidebar visible) | (authed) | List view |
| /companies/[id] | app/companies/[id]/page.tsx | yes | (authed) | Detail view |
| /companies/new | app/companies/new/page.tsx | yes | (authed) | Create form |
| /login | app/login/page.tsx | public | (auth) | Wired to nothing; just submits to /companies |
| /api/companies | app/api/companies/route.ts | — | — | Route handler reading from JSON |

Or for Pages Router, an equivalent list.

## Fixtures

Files that look like data, not code:

| Path | Format | Records (count or "many") | Entity | Notes |
|---|---|---|---|---|
| src/data/companies.json | JSON array | 47 | Company | Used by companies list page |
| src/data/contacts.json | JSON array | 312 | Contact | Used by contacts list + company detail |
| src/data/campaigns.json | JSON | 8 | Campaign | |
| public/seed/leads.json | JSON | 25 | Lead | Static asset, fetched at runtime |
| src/lib/sample-data.ts | TS const | ~50 | Mixed | Hardcoded array exported with type |

Plus hardcoded data in components (>5 items inline):

| File | Variable | Records | Entity |
|---|---|---|---|
| src/modules/dashboard/components/stat-cards.tsx:14 | DEMO_STATS | 6 | Dashboard stat |
| src/app/(marketing)/page.tsx:88 | TESTIMONIALS | 8 | Testimonial |

## Entities inferred

For each entity, the field union across all fixtures:

### Company

- **Sources:** `src/data/companies.json` (47 records); `src/data/companies-sample.json` (5 records); TS interface in `src/types/company.ts`
- **Fields observed:**
  - `id: string` — present in 100% of records, UUID-shaped
  - `name: string` — 100%
  - `domain: string | null` — 91% (null in 9%)
  - `industry: string` — 100%; values seen: `"tech"`, `"healthcare"`, `"finance"`, `"logistics"`, `"other"` (lowercase)
  - `headcount: number` — 78%; missing in older records
  - `last_active_at: string` — 100%; ISO 8601
  - `notes: string` — 12%; freeform
- **Drift:** the TS interface in `src/types/company.ts` declares `industry: 'tech' | 'health' | 'finance'` (missing `logistics`, `other`); fixtures contradict this
- **Used by:** /companies (list), /companies/[id] (detail), /companies/new (form), dashboard StatCards

### Contact

(same structure)

### Campaign

(same structure)

## Components per route

For `/companies`:

| Component | File | Type | Imports |
|---|---|---|---|
| `<CompaniesPage>` | app/companies/page.tsx | Server component | CompaniesList, AddCompanyButton |
| `<CompaniesList>` | src/modules/companies/components/list.tsx | Client component ("use client") | shadcn Table, shadcn Card |
| `<AddCompanyButton>` | src/modules/companies/components/add-button.tsx | Client | shadcn Button, shadcn Dialog, CompanyForm |
| `<CompanyForm>` | src/modules/companies/components/form.tsx | Client | react-hook-form, shadcn Form/Input/Select |
| `<CompanyFilters>` | src/modules/companies/components/filters.tsx | Client | shadcn Select, shadcn Input |

(repeat per route)

## State management

- **Server state:** No TanStack Query / SWR detected. Reads pull from JSON imports directly.
- **Client state:** raw `useState` in pages for the items list (the page imports the fixture and stores it in state to fake mutations).
- **Global state:** Zustand store at `src/lib/store.ts` for: theme, sidebar collapsed state. Not used for data.
- **Forms:** react-hook-form throughout (good — keep).

## Mutations the UI implies

| Mutation | Trigger | Current behavior | Backend equivalent (Phase 4) |
|---|---|---|---|
| Create company | "Add company" dialog → form submit | setCompanies([...companies, { ...new, id: uuid() }]); dialog closes | POST /companies |
| Update company | Edit dialog → form submit | replace in array by id | PATCH /companies/:id |
| Delete company | Trash icon in row → confirm dialog | filter out by id | DELETE /companies/:id |
| Send campaign | "Send" button on campaign detail | toast "Campaign sent" + setStatus('sent') | POST /campaigns/:id/send |
| Login | Form submit on /login | setUser(fake) + router.push('/companies') | POST /auth/login |

## Client-side computations (move to backend)

For each component doing data work:

### `src/modules/companies/components/list.tsx`

- Lines 28-40: `useMemo(() => companies.filter(c => c.industry === industryFilter && c.name.toLowerCase().includes(query.toLowerCase())).sort(...).slice(page * 20, page * 20 + 20))`
- **Decision:** move filtering, sorting, pagination to backend query params

### `src/modules/leads/components/score-calculator.tsx`

- Lines 12-44: implements lead-score formula using contact count, last-activity, deal-value
- **Decision:** move to backend service.computeScore() exposed as part of the view shape (`lead.score: number`)

### `src/modules/dashboard/components/conversion-funnel.tsx`

- Lines 50-89: aggregates campaigns + leads + deals into funnel counts
- **Decision:** new backend endpoint `GET /analytics/conversion-funnel` returning pre-aggregated view

## Auth state

- No login wiring. `/login` form submits and immediately navigates to `/companies` without any token.
- A user context provider at `src/lib/auth-context.tsx` returns a hardcoded `{ name: 'Demo User', email: 'demo@example.com', role: 'admin' }`.
- `next-auth` is in `package.json` (devDependency) but not imported anywhere — earlier attempt abandoned.
- **Implication:** full auth implementation needed in Phase 4.

## UI library state

- **shadcn:** initialized (components.json present)
- **Primitives installed:** button, input, label, select, dialog, table, card, badge (8 — incomplete)
- **Missing:** sidebar block (uses raw `<aside>`), form (uses raw react-hook-form), command, drawer, several others
- **Competing libraries:** none detected
- **Hand-rolled primitives:** none significant
- **Sidebar:** custom `<aside>` in `src/app/(authed)/layout.tsx` lines 8-42 — needs migration to shadcn sidebar block

## External integrations attempted

- **Stripe:** `@stripe/stripe-js` in dependencies; `src/lib/stripe.ts` exists with hardcoded test key (`pk_test_X1234...`). **FLAG: hardcoded key.**
- **Anthropic:** `@anthropic-ai/sdk` in dependencies; not imported anywhere.
- **Resend (email):** in dependencies, not used.
- **None active.**

## Routing & layout

- `app/layout.tsx` (root): HTML shell, providers (theme, query, auth context)
- `app/(authed)/layout.tsx`: sidebar + main content (hand-rolled aside; needs shadcn migration)
- `app/(auth)/layout.tsx`: centered card for login

## SECURITY-IMMEDIATE flags

Things `migration-planner` and the user should address before backend build:

- `src/lib/stripe.ts:8` — hardcoded Stripe test key
- `.env.local` — exists in repo but `.gitignore` does NOT list it (verify with `git ls-files`)
- `src/lib/api-keys.ts` — comments hint at "Anthropic key goes here" but file is empty; no immediate leak, but pattern is risky

## NOTES

Free-form observations:

- The user clearly knows Tailwind well; component code is clean
- Some routes have no design — `/settings` is referenced in sidebar but the page is a placeholder "Coming soon"
- Tests: `vitest.config.ts` exists, but `src/**/*.test.ts` files are empty/skeletal
```

## Extraction techniques

### Finding routes (App Router)

```bash
find apps/web/src/app -name "page.tsx" -o -name "route.ts" 2>/dev/null \
  || find src/app -name "page.tsx" -o -name "route.ts" \
  || find app -name "page.tsx" -o -name "route.ts"
```

Look at folder names for route inference. `app/(authed)/companies/[id]/page.tsx` → route `/companies/[id]` in the `(authed)` group.

### Finding fixtures

```bash
# JSON files outside node_modules
find . -name "*.json" \
  -not -path "*/node_modules/*" \
  -not -name "package*.json" \
  -not -name "tsconfig*.json" \
  -not -name "components.json" \
  -not -name "*.config.json"

# Hardcoded data arrays in TS — heuristic: a const that's an array literal with >5 entries
grep -rn "^const \w\+ = \[" --include="*.ts" --include="*.tsx" -A20 \
  | awk '/^const / { name=$0; count=0 } /^--/ { if (count > 5) print name; count=0 } { count++ }'
```

### Detecting state

```bash
# useState anywhere
grep -rn "useState" --include="*.tsx" --include="*.ts" | wc -l

# Zustand stores
grep -rn "create(" --include="*.ts" | grep -i "zustand\|store"

# Context providers
grep -rn "createContext\|Provider" --include="*.tsx"
```

### Detecting auth

```bash
# Auth packages in package.json
jq -r '.dependencies // {} | keys[]' package.json | grep -iE "auth|clerk|kinde|nextauth|auth0|firebase"

# Login form / hardcoded user
grep -rn "demo@\|test@example\|hardcoded.*user\|fake.*user" --include="*.tsx" --include="*.ts"
```

### Detecting hardcoded secrets

```bash
grep -rEn "(sk-ant-|sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|pk_(live|test)_[a-zA-Z0-9]{24,})" \
  --include="*.ts" --include="*.tsx" --include="*.json" --include="*.env*" \
  --exclude-dir=node_modules --exclude-dir=.git
```

Hits go to SECURITY-IMMEDIATE.

### Inferring entity fields from JSON

```bash
# Field frequency across a fixture
jq -r '.[] // .items[] // . | keys[]' src/data/companies.json | sort | uniq -c | sort -rn
```

Records with 100% frequency → required. Records with <100% frequency → either optional or evidence of fixture drift.

```bash
# Detect enum-shaped fields (limited distinct values across many records)
jq -r '.[] | .industry' src/data/companies.json | sort -u
```

If the result is a small finite set, it's an enum. Title Case rewriting goes in EXTRACTED_CONTRACTS notes.

## Anti-patterns to avoid

- **Speculating about intent.** The job is inventory. If a route is missing UI, record "/settings — placeholder only"; don't decide what it should become.
- **Deduplicating eagerly.** If `companies.json` and `companies-sample.json` have different fields, record both shapes.
- **Skipping hardcoded data.** Vibe-coded apps often inline `const ITEMS = [...]` in components. Those records imply backend data too.
- **Running the project.** Static reading only.
- **Treating TS interfaces as truth.** Vibe-coded apps frequently have stale types. The JSON shape is more reliable than the interface, but both should be recorded.
