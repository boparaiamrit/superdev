---
name: prototype-to-saas
description: Convert a working single-user Next.js prototype (built with AI, fixtures-as-backend, all logic client-side) into a production multi-tenant SaaS by reverse-engineering the implicit backend, extracting shared contracts, building a Nest.js backend that matches what the frontend already expects, and incrementally rewiring the frontend module by module without breaking what works. Defines 5 subagents (codebase-discoverer, schema-reverse-engineer, migration-planner, backend-extractor, frontend-rewirer) and reuses agents from prd-design-build-orchestrator. Use whenever the user has a Next.js app where JSON files or hardcoded arrays serve as backend, business logic runs client-side, and they want a real backend, auth, multi-tenancy, persistence. Mentions productionizing an MVP, vibe-coded app, single-user-to-multi-user, JSON-to-database migration, or frontend-only prototype.
---

# Prototype to SaaS Converter

Convert a working Next.js prototype (single user, JSON-as-backend, logic in the frontend) into a production multi-tenant SaaS with a real Nest.js backend, auth, persistence, and the same architectural commitments as the greenfield orchestrator.

## When to use this skill

Use when the user has:

- A Next.js app that already renders the screens they want
- Data living in JSON files, hardcoded arrays, or `useState`-with-fixtures
- "Creating" / "updating" / "deleting" that works in the browser session but doesn't persist
- No real auth, no multi-tenancy, no backend
- A wish to turn this into a SaaS without rewriting the working UI

Do NOT use this skill for:

- Greenfield builds — use `prd-design-build-orchestrator` instead
- Prototype-to-prototype refactors — use the frontend skill directly
- Adding a feature to an already-productionized app — use the per-skill recipes

## What this skill assumes and what it discovers

**Assumes the input is roughly:**

- Next.js (App Router preferred, Pages Router acceptable)
- TypeScript (any flavor — strict, loose, or mixed)
- Some package manager (pnpm, npm, yarn, bun)
- Tailwind or another CSS approach
- shadcn/ui maybe or maybe not (this skill brings the project into shadcn-compliance during rewiring)

**Discovers (Phase 1) and decides per project:**

- Which routes correspond to features (and what to call those features)
- What entities exist implicitly in the JSON data
- What mutations the UI implies (create-company button → POST /companies)
- What client-side computations are "view-shape contract" candidates to move server-side
- Whether the existing UI lib will need shadcn migration

## Architectural target

Same as greenfield orchestrator's commitments — this skill brings the prototype to those standards:

1. **Monorepo** — `apps/web` (the existing app, refactored) + `apps/api` (new Nest.js) + `packages/contracts`
2. **View-shape contract** — backend returns view-ready data; frontend renders without `?.` or `??` on contract fields
3. **Dual-mode adapter** — `NEXT_PUBLIC_API_MODE=demo` keeps the existing fixtures working; `NEXT_PUBLIC_API_MODE=production` hits the new Nest backend
4. **Title Case enums** — DB value = wire value = UI label, no conversion code
5. **shadcn/ui everywhere** — every primitive from `@/components/ui/*`, sidebar uses shadcn's sidebar block
6. **Docker for all infra** — Postgres+Timescale, Redis, any project-specific services
7. **Drizzle, CASL, `@Audit`, BullMQ** — same backend conventions as greenfield

The prototype almost certainly violates several of these. The migration brings it into compliance.

## The five-phase pipeline

```
Phase 1: DISCOVERY     Read the existing app. Catalog everything.
Phase 2: EXTRACTION    Reverse-engineer contracts from JSON + TS types.
Phase 3: PLANNING      Module-by-module migration plan + user confirmation gate.
Phase 4: BACKEND BUILD Build Nest.js to match what the frontend already expects.
Phase 5: REWIRE        Per module: switch fixture imports to API calls.
```

Phases 1–3 are read/plan only; the prototype keeps running unchanged. Phase 4 builds the backend alongside. Phase 5 is the only phase that modifies the existing frontend code, and only in surgical per-module passes.

## How to invoke this skill

This skill is designed for **Claude Code**. It installs 5 specialized subagent definitions into `.claude/agents/` and the main session orchestrates them through five phases.

### Pattern 1 — natural language

Start a Claude Code session in the prototype's directory:

```
I have a Next.js prototype where all data lives in JSON files and the
business logic runs client-side. Help me convert this to a real
multi-tenant SaaS with a Nest.js backend.
```

The main session reads this skill's SKILL.md, installs the 5 migration subagents via the install script, and runs the five phases by delegating to subagents through natural language.

### Pattern 2 — main session AS the migration conductor

For a session whose entire system prompt is this skill, launch with:

```bash
claude --agent prototype-to-saas
```

This requires an agent file with `name: prototype-to-saas` at the project or user level. See the install script.

### Pattern 3 — discovery-first front layer

If you have multiple skills installed and the right one isn't obvious:

```
User: "Help me productionize this Next.js prototype."
Claude: [reads package.json, sees Next.js + JSON fixtures + no apps/api]
Claude: "This looks like a Next.js prototype with implicit JSON backend.
         The right skill for this is prototype-to-saas. I'll proceed."
```

If the user instead has a PRD and design and no code yet → use `prd-design-build-orchestrator`. If they have a productionized app and want a security pass → `security-review-and-fix` standalone.

### Agent-teams mode (optional, experimental)

This skill is **mostly sequential** (discover → extract → plan → build → rewire) with parallel per-feature subagents inside Phases 4 and 5. Agent teams are NOT the default here — see "Agent teams (optional)" at the end of this skill for the one narrow case where they help (Phase 2 reverse-engineering on a messy prototype with conflicting evidence sources).

## The agent team

Five new agents, plus reuse of three from the orchestrator:

### New agents (this skill)

| Agent | Phase | Tools | Owns |
|---|---|---|---|
| `codebase-discoverer` | 1 | Read, Glob, Grep, Bash | `DISCOVERY.md` |
| `schema-reverse-engineer` | 2 | Read, Glob, Grep, Write | `EXTRACTED_CONTRACTS.md` + draft `packages/contracts/src/*.ts` |
| `migration-planner` | 3 | Read, Write | `MIGRATION_PLAN.md` |
| `backend-extractor` | 4 | Read, Write, Edit, Bash | `apps/api/src/modules/<feature>/*` per feature |
| `frontend-rewirer` | 5 | Read, Write, Edit, Bash | surgical edits to `apps/web/src/modules/<feature>/*` |

### Reused from `prd-design-build-orchestrator` (must be installed)

| Agent | Used in this skill's | Role |
|---|---|---|
| `monorepo-bootstrapper` | Phase 4.0 | Converts the standalone Next.js project into a pnpm/Turbo monorepo and scaffolds `apps/api` |
| `contracts-author` | Phase 2.5 | Formalizes the reverse-engineered drafts into final `@<scope>/contracts` package |
| `ui-auditor` | Phase 5 wave gates | Verifies shadcn compliance is maintained or achieved during rewiring |
| `integration-tester` | Phase 6 (final) | Functional gate before declaring done |

The five new agents live in `references/migration-agents.md`. Install them with `install-migration-agents.sh` in the same `references/` folder, which uses the orchestrator skill's `extract-agent.py`.

## Phase 1 — Discovery

**Goal:** know exactly what's in the prototype before deciding what to migrate.

Install agents first (Phase 0):

```bash
# Reuses the orchestrator's core agents (monorepo-bootstrapper, contracts-author, ui-auditor, integration-tester)
~/.claude/skills/prd-design-build-orchestrator/references/install-core-agents.sh

# Plus this skill's 5 migration agents
~/.claude/skills/prototype-to-saas/references/install-migration-agents.sh

# Plus optionally the security agents
if [[ -f ~/.claude/skills/security-review-and-fix/references/security-agents.md ]]; then
  ~/.claude/skills/security-review-and-fix/references/install-security-agents.sh
fi
```

Then dispatch in natural language:

> "Use the codebase-discoverer subagent to inventory the existing Next.js prototype: catalog routes, fixture files, entity shapes, client-side mutations, business logic, UI library state, auth state. Produce DISCOVERY.md per `~/.claude/skills/prototype-to-saas/references/discovery-checklist.md`."

The discoverer is read-only. It writes `DISCOVERY.md` with everything subsequent agents need.

## Phase 2 — Extraction

**Goal:** reverse-engineer the contracts the existing frontend implicitly expects.

> "Use the schema-reverse-engineer subagent to read DISCOVERY.md. For each entity, derive a Zod schema using the view-shape contract (no `.optional()` on data fields; Title Case enums; discriminated unions for variations). Compare derived shapes against JSON fixtures; report mismatches. Produce EXTRACTED_CONTRACTS.md and draft contract files in `packages/contracts/src/`."

The schema is derived from:

- TypeScript interfaces in the prototype (if present)
- JSON fixture shapes (sampled across files)
- How fields are used in components (rendered directly? optional-chained? formatted?)

Then formalize:

> "Use the contracts-author subagent to review the drafts in `packages/contracts/src/`. They were reverse-engineered — review each against view-presenter.md rules. Promote drafts to final contracts. Run `pnpm --filter @<scope>/contracts build` to verify."

`contracts-author` (from the orchestrator skill) reviews and finalizes — same rules as greenfield apply (Title Case, no `.optional()` on view fields, discriminated unions).

## Phase 3 — Planning (user-confirmation gate)

**Goal:** decide migration order, per-module strategy, and what to discard.

> "Use the migration-planner subagent to read DISCOVERY.md and EXTRACTED_CONTRACTS.md. Group routes into feature modules. Order modules by dependency (auth and workspaces first). For each module, classify FE state as: KEEP_AS_IS, REWIRE_TO_API, or DISCARD. Identify business logic that must move backend-side. Produce MIGRATION_PLAN.md."

The planner produces three lists per module:

- **KEEP_AS_IS** — pure presentation (e.g., a hover-card with no data dependency)
- **REWIRE_TO_API** — currently client-side but should call the backend (filtering, sorting, paginating, mutating, fetching)
- **DISCARD** — was needed to fake a backend but won't be needed once the real one exists (in-memory mutation reducers, fake-delay setTimeouts, mock auth providers)

**Mandatory user-confirmation gate.** The orchestrator shows the user:

- N feature modules and their order
- M JSON files to convert into seed data
- K client-side computations that will move backend-side
- Which UI library state will be ported (if not shadcn already)

User must approve before Phase 4 starts.

## Phase 4 — Backend build

**Goal:** stand up the Nest.js backend that matches what the frontend already expects.

### Phase 4.0 — Bootstrap monorepo

The migration's main session dispatches `monorepo-bootstrapper`:

> "Use the monorepo-bootstrapper subagent to convert the existing Next.js project to a pnpm/Turbo monorepo. Move existing code into `apps/web`. Scaffold `apps/api` per the nestjs-enterprise-backend skill. Write root `docker-compose.yml` with postgres+redis (and project-specific services from MIGRATION_PLAN.md). Initialize shadcn/ui in `apps/web` if not already done; install all primitives plus sidebar. Verify both apps boot."

This is THE risky step — it physically moves files. Run it once, verify the prototype still runs unchanged after the move (`pnpm dev` in `apps/web`), then continue.

### Phase 4.1 — Build backend modules in waves

Same wave structure as greenfield orchestrator, but the per-module agent is `backend-extractor` instead of `backend-module-builder`. The difference: `backend-extractor` has the existing frontend code as ground truth, so it builds endpoints that match what the FE already calls (or will call after Phase 5).

> **Subagents cannot spawn other subagents.** The migration's main session (running this skill) dispatches every wave. Per-feature `backend-extractor` calls return and stop; they do not chain.

The main session emits one batch per wave. For Wave 1 (foundation, 2 features):

> "Dispatch two backend-extractor subagents in parallel: one for `apps/api/src/modules/auth/`, one for `apps/api/src/modules/workspaces/`, both per MIGRATION_PLAN.md."

For Wave 2 (independent domain features):

> "Dispatch three backend-extractor subagents in parallel: companies, contacts, mailboxes, each per MIGRATION_PLAN.md."

Wave gates run typecheck + lint + tests + UI auditor (same as orchestrator).

**Optional: worktree isolation for risky migrations.** Migration is one of the few situations where a builder agent can plausibly damage files outside its scoped folder (a misread of MIGRATION_PLAN.md, a bad search-replace). For projects where the prototype is in active use and a corrupted file would be expensive, dispatch backend-extractor and frontend-rewirer with `isolation: worktree` so each agent runs in a temporary git worktree — its file edits are written to a separate checkout that's discarded if the agent makes no changes. The main session pulls successful changes back into the working tree via a single merge step. Set this via the per-invocation prompt:

> "Use the backend-extractor subagent for the companies module per MIGRATION_PLAN.md. Run in an isolated worktree (`isolation: worktree`) — the migration plan is complex and I want any edits sandboxed until I review them."

This costs a few seconds per dispatch (worktree creation + cleanup) and gives you reviewable per-feature diffs.

### Phase 4.2 — Seed from existing JSON fixtures

`backend-extractor` for each module also produces a Drizzle seed script that imports the existing JSON fixtures (under `apps/web/src/mocks/` or wherever the prototype stored them) and inserts them into the dev database. This means the dev backend starts with the same data the prototype had, which makes Phase 5's rewiring testable against known state.

## Phase 4.5 — Frontend module decomposition (NEW — runs BEFORE rewiring)

**Goal:** decompose every fat module in the prototype into the canonical [`frontend-modular-architecture`](../frontend-modular-architecture/SKILL.md) layout BEFORE `frontend-rewirer` touches anything.

**Why this phase exists:** AI-built prototypes routinely have 1000+ line page files, 8-step wizards in one component, 30+ useState chains, and absolute-positioned drawers that violate Portal rules. If `frontend-rewirer` runs on these as-is, it adds TanStack Query hooks INTO the fat file — preserving every antipattern with new data wiring layered on top. The prototype becomes a "real backend" version of the same unmaintainable mess.

The fix: run [`frontend-refactoring`](../frontend-refactoring/SKILL.md) on each fat module FIRST. Each conversion is atomic (one commit, on a feature branch, behavior-verified). Only after the module is decomposed does `frontend-rewirer` operate on it — and now it works against small, focused files where data wiring is straightforward.

### Per-module decomposition workflow

For each module in MIGRATION_PLAN.md, BEFORE dispatching `frontend-rewirer`:

> "Run frontend-refactoring on apps/web/src/modules/<feature>/.
> Phase 1: dispatch module-conversion-planner to produce CONVERSION_PLAN.md.
> Phase 2: user reviews + approves the plan.
> Phase 3: dispatch module-behavior-snapshotter to capture baseline behavior of the prototype.
> Phase 4: dispatch atomic-module-converter to execute the plan on a feature branch (single commit).
> Phase 5: dispatch conversion-verifier to confirm zero behavior change.
> Merge to migration branch on PASS. Then proceed to frontend-rewirer for this module in Phase 5."

If `frontend-rewirer` is dispatched on a module that wasn't decomposed first, it will refuse (it has a built-in 300-line file refusal). The orchestrator must respect the ordering.

### When Phase 4.5 can be skipped

For modules that are ALREADY well-structured in the prototype (rare but possible — e.g., a tiny one-page module that's only 80 lines), `module-structure-auditor` returns no P1 findings → skip refactoring for that module → proceed directly to rewiring.

The orchestrator dispatches `module-structure-auditor` on every prototype module as the first step of Phase 4.5 to decide which modules need refactoring.

## Phase 5 — Frontend rewiring

**Goal:** per module, replace fixture-loading + client-side logic with API calls to the new backend.

The main session dispatches one `frontend-rewirer` per module, in the same wave order as backend. For a wave:

> "Dispatch three frontend-rewirer subagents in parallel: one each for companies, contacts, and mailboxes. Each rewires `apps/web/src/modules/<feature>/` per MIGRATION_PLAN.md: replace fixture imports with `@<scope>/contracts` schemas + `apiRequest` calls, move client-side filter/sort/paginate to server query params, keep components rendering as-is — change data flow, not presentation. Maintain demo mode by routing `/api/mock/*` through the same fixture data."

### What gets rewired

For each module:

- **`api.ts`** — replace `import companies from './fixtures.json'` with `apiRequest('/companies', companyListResponseSchema)`
- **`hooks/use-*.ts`** — wrap in TanStack Query (`useQuery` for reads, `useMutation` for writes)
- **`page.tsx` / `components/*.tsx`** — switch from local `useState` for the list to the query hook
- **Filtering** — strip the `companies.filter(c => ...)` and pass filters as query params
- **Sorting** — strip the `companies.sort(...)` and pass `?sort=` query param
- **Pagination** — strip the slice; rely on server pagination response shape
- **Mutations** — strip the `setCompanies([...companies, newCompany])` and use mutation hook that POSTs and invalidates the query

### What stays

- Component visual structure (JSX, Tailwind classes, shadcn primitives)
- TanStack Table column definitions (with adjustments for server-side sort/filter)
- Form layouts (now wired to mutations)
- Routing structure (the Next.js routes don't change)

### What's deleted

- The fixture JSON files in the module folder (moved to `apps/web/src/mocks/<feature>/` for demo mode, or deleted if seeded server-side)
- Client-side computation that's now server-side
- Any "fake auth" mocking (replaced by real JWT)
- `useEffect` loaders that read from JSON (replaced by TanStack Query)

### Wave gate per module

After each rewirer runs:

```bash
pnpm --filter @<scope>/web typecheck
pnpm --filter @<scope>/web lint
pnpm --filter @<scope>/web validate:fixtures        # demo mode fixtures still valid
pnpm --filter @<scope>/web build
# Visual smoke: start API + worker + web, request /companies, verify list renders
```

Plus the ui-auditor:

> "Use the ui-auditor subagent to audit the rewired module(s). Verify shadcn compliance: no raw HTML primitives introduced during rewiring, no competing UI library imports added, sidebar still uses shadcn block."

If the existing prototype was NOT shadcn-based, the rewirer also migrates components to shadcn during this pass (this is in `migration-agents.md`). If it was already shadcn, leave the components alone — just swap data flow.

## Phase 6 — Final integration + security

Reuse the orchestrator's Phase D pattern:

> "Use the integration-tester subagent to run cross-workspace isolation tests, CASL ability tests, view-shape compliance, demo+production mode boot, and any tests written during Phase 5."

If the security skill is installed, run its 5-agent pipeline as Step D.2 of the orchestrator's Phase D — see `security-review-and-fix` SKILL.md for the natural-language dispatch sequence.

Critical findings block release. High findings get user deferral decisions. Done = green integration + zero unresolved Critical security findings.

## Reference files

| File | When to read |
|---|---|
| `references/discovery-checklist.md` | Phase 1 — what to inventory |
| `references/extraction-patterns.md` | Phase 2 — JSON shape + TS type → Zod schema patterns |
| `references/migration-plan-format.md` | Phase 3 — MIGRATION_PLAN.md template |
| `references/rewiring-patterns.md` | Phase 5 — common fixture-to-API rewiring transformations |
| `references/migration-agents.md` | Phase 0 — agent definitions for the 5 new agents |
| `references/install-migration-agents.sh` | Phase 0 install script |

## Validation checklist

Before declaring the conversion done:

- [ ] `.claude/agents/` contains all 5 migration agents + the 4 reused orchestrator agents + 5 security agents (14 minimum, 19 if security present)
- [ ] `DISCOVERY.md`, `EXTRACTED_CONTRACTS.md`, `MIGRATION_PLAN.md` exist at project root
- [ ] User confirmed MIGRATION_PLAN.md before Phase 4 started
- [ ] Monorepo structure in place: `apps/web` (refactored prototype) + `apps/api` (new Nest.js) + `packages/contracts`
- [ ] Root `docker-compose.yml` with postgres+redis healthy
- [ ] **`pnpm dev` in the original prototype location no longer works (it's been moved to apps/web); `pnpm dev` from monorepo root works**
- [ ] Demo mode (`NEXT_PUBLIC_API_MODE=demo`) still renders every screen with fixture data
- [ ] Production mode (`NEXT_PUBLIC_API_MODE=production`) renders every screen with API data from the Nest backend
- [ ] Every module's data flow goes through TanStack Query, not direct JSON imports
- [ ] Every endpoint has `@CheckAbility` and applicable mutations have `@Audit`
- [ ] shadcn compliance maintained (`ui-auditor` clean across `apps/web/src/modules/`)
- [ ] Title Case enum sweep clean
- [ ] Integration tests pass
- [ ] If security skill ran: zero unresolved Critical findings

## Common pitfalls

**P1 — Rewriting the frontend instead of rewiring it.** The prototype is the design spec. Phase 5 changes data flow, not visual structure. If a rewirer starts rewriting JSX, stop.

**P2 — Skipping the user-confirmation gate.** The MIGRATION_PLAN must be approved before Phase 4. Bad classification (KEEP_AS_IS vs REWIRE_TO_API) at planning time leads to half a day of wasted work.

**P3 — Building the backend without the frontend's actual shapes.** The whole point of this skill is that the frontend already knows what it wants. Don't invent contracts; reverse-engineer them. If a backend-extractor's output doesn't match the EXTRACTED_CONTRACTS, that's the bug.

**P4 — Trying to do Phase 4 and Phase 5 in parallel.** The frontend must keep working in demo mode while the backend is being built. Rewiring only starts when the backend module is up.

**P5 — Migrating UI library AND data flow in the same pass.** If the prototype isn't shadcn, decide at planning time whether to migrate UI first (Phase 4.5 inserted) or rewire first. Doing both at once produces unreviewable diffs.

**P6 — Deleting fixture JSON before demo mode is verified.** The fixtures power the demo mode in production. Don't `rm fixtures.json` until `apps/web/src/mocks/<feature>/` has the equivalent content AND `pnpm validate:fixtures` is green.

**P7 — Assuming the prototype's TS types are correct.** Vibe-coded apps often have `any` and incomplete types. The schema-reverse-engineer treats types as hints, not contracts; JSON fixtures and actual component usage are the ground truth.

**P8 — Ignoring business logic in the frontend.** If `companies.filter(c => c.last_active > 30days && c.deal_value > 10000)` is in a component, that's a real piece of product logic. It belongs in the backend (`/companies?last_active_after=...&min_deal_value=...`), not transplanted as-is into a useMemo.

## Agent teams (optional, experimental)

Most of this skill's pipeline is sequential or per-feature parallel — patterns that fit subagents cleanly. There's one narrow case where an agent team helps:

### Phase 2 schema reverse-engineering on a messy prototype

When the prototype's evidence sources disagree — TS interfaces say one thing, JSON fixtures say another, component usage implies a third — a single `schema-reverse-engineer` subagent has to pick a winner with limited debate. For prototypes where the schemas matter (the contracts you derive will define the entire backend's shape), a 3-teammate team produces stronger schemas.

Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

After Phase 1 (discovery) finishes, instead of dispatching a single `schema-reverse-engineer` subagent, ask the main session:

> "Spawn a 3-teammate agent team using the schema-reverse-engineer agent type as a base: one teammate advocates for the TS interface as the source of truth, one advocates for the JSON fixtures, one advocates for the actual component usage. Have them debate the canonical shape for each entity. Produce EXTRACTED_CONTRACTS.md by consensus, with drift findings recording where each evidence source disagreed."

The resulting contracts have stronger provenance — each schema decision is justified by which evidence won and why. Recommended when:

- The prototype has been worked on by multiple developers (inconsistent evidence)
- TS interfaces are stale or use `any` heavily
- Multiple JSON fixtures exist for the same entity with different shapes

Not recommended for clean prototypes where the schemas are obvious from any single source. The token cost (~3×) only pays off when the contracts are genuinely contested.

### What stays in subagent mode

- **`codebase-discoverer`** — read-only inventory; no debate needed
- **`migration-planner`** — produces a plan reviewed by the user; the user does the debate
- **`backend-extractor`** and **`frontend-rewirer`** — per-feature parallel work where teammates would have nothing to say to each other (each rewires its own module)
