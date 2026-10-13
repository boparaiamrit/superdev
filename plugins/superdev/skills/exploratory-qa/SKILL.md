---
name: exploratory-qa
description: Senior-engineer exploratory QA for full-stack apps built with the design-to-nextjs + nestjs-enterprise-backend stack. Drives Playwright through the real app to find what automated tests miss — missing empty states, oversized buttons inconsistent across pages, overlapping z-indexes, frozen frames during large data loads, client-side filter/sort that should be server-side, three modules that should share one table component, slow queries with N+1, missing loading states, error states never tested, mobile breakpoints that explode, focus traps in dialogs, cross-module refactor candidates. Six-phase pipeline (environment, happy-path, edge-cases, consistency, performance, report) with four subagents (qa-environment, qa-flow-tester, qa-consistency-checker, qa-performance-prober). Produces QA_REPORT.md with severity-ranked findings, evidence, refactor recommendations. Use for production-readiness QA, UX audit, design consistency, load testing, exploratory testing.
---

# Exploratory QA

Senior-engineer-style exploratory QA: drive the real app like a discerning user, notice everything wrong, and produce a report a team can actually act on. This is not unit-test generation — it's "I spent two days clicking through your app and here's what's broken, inconsistent, or going to embarrass you in front of real users."

## When to use this skill

Use when:

- The build is functionally complete but you need a production-readiness check
- A user / customer / investor demo is coming up and you want to find issues before they do
- You suspect there are inconsistencies across pages but don't know where
- You're worried about performance with real data volumes
- The app was built by AI/agents and you want a human-style pass over the output
- The team needs an honest report of what's incomplete, missing, or visually wrong

Do NOT use this skill for:

- Unit test generation — Jest/Vitest skills handle that
- Functional regression suites — that's `integration-tester` from the main agent
- Security audit — that's `security-review-and-fix`
- Initial build — use the main agent or prototype-to-saas

This skill assumes a working app exists and runs. It explores; it doesn't build.

## How to invoke this skill

This skill is designed for **Claude Code**. It installs 4 specialized subagent definitions into `.claude/agents/` and the main session orchestrates them through six phases. The flow-tester agent drives Playwright; have Playwright available (`pnpm dlx playwright install chromium`) before kicking off.

### Pattern 1 — natural language (standalone QA pass)

Start a Claude Code session in the project's directory:

```
Run a production-readiness QA pass on this app. The stack is up at
localhost:3000 (web) and localhost:3001 (api).
```

The main session reads this skill's SKILL.md and runs the six phases by delegating to the 4 QA subagents through natural language. The agents are auto-loaded from the plugin's `agents/` directory — there is no install step.

### Pattern 2 — as part of a superdev-build run

During a [`superdev-build`](../superdev-build/SKILL.md) run, execute this skill at Step 6 (cross-cutting audits), after the security pass.

## What this skill catches that automated tests don't

Things automated tests usually pass but humans notice immediately:

- **Missing empty states** — table just shows headers and nothing else when zero rows
- **Inconsistent primitive sizing** — `<Button>` on /companies is `lg`, on /contacts is `default`, on /campaigns is `sm` — same semantic action, three sizes
- **Z-index collisions** — toast shows behind dialog backdrop, dropdown hidden under sticky header
- **Frozen UI during data load** — list page imports 5000 rows of fixtures, filter input is unresponsive while rendering
- **Client-side data work that should be server-side** — `.filter().sort()` over thousands of records in `useMemo` blocking the main thread
- **Refactor opportunities** — three modules each have a near-identical `<DataTable>` with slight differences; should be one shared component
- **Missing loading skeletons** — page flashes empty before content arrives
- **Missing error states** — API returns 500, page just stays in loading state forever
- **Overflow disasters** — long company name breaks the row layout, long text spills past container
- **Focus traps broken** — `<Dialog>` doesn't trap focus, Tab escapes to background
- **Mobile breakpoints exploding** — sidebar overlays content; modal extends past viewport
- **Inconsistent headers** — every page renders its title with different typography/spacing
- **Async race conditions** — fast-clicking the create button submits twice
- **N+1 query problems** — list of 50 companies fires 51 SQL queries server-side
- **Stale data after mutation** — created a company, list doesn't refresh, user thinks it failed
- **Form validation timing** — errors flash on every keystroke instead of on blur

These are the things that distinguish "I shipped" from "I shipped something I'd be proud to show."

## The six-phase pipeline

```
Phase 1: ENVIRONMENT      Verify stack, plant test data at realistic scale, capture baselines
Phase 2: HAPPY PATH       Drive canonical flow for every feature; record observations + screenshots
Phase 3: EDGE CASES       Empty/loading/error states; large data; slow network; failed mutations
Phase 4: CONSISTENCY      Cross-route checks: button sizing, spacing, headers, z-index, refactor smells
Phase 5: PERFORMANCE      Load times, layout shift, frozen frames, database query counts
Phase 6: REPORT           QA_REPORT.md with severity-ranked findings + recommendations
```

Phases 2, 3, 4 are largely parallel-safe — they share no inputs and write to different scratch directories. Phase 5 needs exclusive control of the running stack (performance measurement is sensitive to other activity). Phase 6 is the main agent's synthesis.

## The four agents

| Agent | Phase | Tools | Owns |
|---|---|---|---|
| `qa-environment` | 1 | Read, Glob, Bash | seed data, baseline state, `QA_ENVIRONMENT.md` |
| `qa-flow-tester` | 2 + 3 | Read, Bash, Glob, Grep | `qa/flows/<feature>/` directory with screenshots, traces, observations |
| `qa-consistency-checker` | 4 | Read, Glob, Grep, Bash | `qa/consistency/` with cross-route diff data + `QA_CONSISTENCY.md` |
| `qa-performance-prober` | 5 | Read, Bash | `qa/performance/` with timing data + `QA_PERFORMANCE.md` |

Plus reuse of `integration-tester` from the plugin agent roster for the pre-flight functional smoke (if integration tests fail, exploration is pointless — fix functional issues first).

Five agents would feel like the right number to match other skills, but a fifth agent here would just split work artificially. Four works.

Agent definitions live in `../../agents/` (`qa-environment.md`, `qa-flow-tester.md`, `qa-consistency-checker.md`, `qa-performance-prober.md`) and are auto-loaded by the plugin — dispatch by name.

## Phase 1 — Environment

**Goal:** the stack is up, the data is realistic, the baselines are captured.

Agents are auto-loaded by the plugin — no install step.

Then dispatch in natural language:

> "Use the qa-environment subagent to verify Docker + API + worker + web are running and healthy. Seed test data at REALISTIC SCALE (not toy size — see the seed-scale rules in `./references/environment-checklist.md`). Capture baselines: take screenshots of every route at 1440px, 768px, and 375px viewports. Plant the edge-case fixtures listed in the checklist. Produce QA_ENVIRONMENT.md."

The "realistic scale" matters. A test DB with 5 companies hides the performance and overflow issues that show up with 500. The agent seeds to numbers like:

- Workspaces: 3 (test cross-workspace isolation alongside the audit)
- Users per workspace: 5
- Companies: 250 per workspace (realistic SMB customer)
- Contacts: 8 per company → ~2000 per workspace
- Campaigns: 30 per workspace (mix of statuses)
- Leads + deals: enough to populate a multi-column kanban with realistic density
- Email sent: 50k+ rows per workspace (exercises the hypertable)

The exact numbers come from `MIGRATION_PLAN.md` if it exists, or `EXECUTION_PLAN.md` if greenfield, or from sensible defaults in `references/environment-checklist.md`.

Baseline screenshots become the reference for Phase 4's consistency checks.

## Phase 2 — Happy Path

**Goal:** the canonical flow works end-to-end for every feature. Find what's broken even on the easy case.

The main session dispatches one `qa-flow-tester` per feature, in parallel batches of up to 6. For a 6-feature group:

> "Dispatch six qa-flow-tester subagents in parallel, each scoped to one feature module (companies, contacts, mailboxes, campaigns, pipeline, inbox). Mode: happy-path. Each should follow the recipes in `./references/flow-recipes.md` — login → list page → filter → sort → detail → create → toast verification → list refresh. Take screenshots at every step. Write to `qa/flows/<feature>/happy-path/`."

For projects with more than 6 features, run in successive batches; do not exceed 6 concurrent subagents per tool-use turn.

Each flow tester writes to its own directory:

```
qa/flows/companies/
  ├── screenshots/
  │   ├── 01-list.png
  │   ├── 02-list-filtered.png
  │   ├── 03-detail.png
  │   ├── 04-add-dialog.png
  │   └── 05-list-after-create.png
  ├── trace.zip                  (Playwright trace)
  ├── network.har                (network log)
  ├── console.log                (browser console output)
  └── observations.md            (what the agent noticed)
```

`observations.md` is the structured output: timed steps, visual issues spotted, console errors, network anomalies. The main agent collates these in Phase 6.

## Phase 3 — Edge Cases

Same `qa-flow-tester` agent, different prompts. Now the agent deliberately tries to break things.

Categories per feature:

- **Empty data** — clear all rows, verify empty state renders correctly (not just a blank page)
- **Single item** — verify list with one row, detail with no related items
- **Large data** — load with 1000+ items, check render time, scroll performance, filter responsiveness
- **Slow network** — Chrome devtools throttling to "Slow 3G," verify loading skeletons appear
- **API errors** — mock the API to return 500, verify error state renders (not just stuck on loading)
- **Validation errors** — submit form with missing required fields, verify inline errors, check that errors don't flash on every keystroke
- **Concurrent mutations** — fast-click submit button, verify only one POST fires (debounce or disable-while-pending)
- **Stale data** — open two tabs, mutate in tab A, refresh tab B, verify update visible
- **Long content** — extremely long names, descriptions, URLs — verify no overflow disasters
- **Special characters** — names with emoji, Unicode, HTML entities — verify rendering and persistence
- **Boundary numbers** — quantity = 0, very large numbers, negative numbers in inputs that should reject them
- **Browser back/forward** — navigate via browser controls, verify state is preserved
- **Tab/keyboard nav** — Tab through a form; verify logical order; Escape closes dialogs; focus traps work in modals
- **Mobile breakpoints** — same flows at 375px width; check for overflow, layout breakage, untouchable buttons

Each category becomes its own observation file under `qa/flows/<feature>/edge-cases/`. The agent flags severity (Critical/High/Medium/Low) inline.

## Phase 4 — Consistency

Cross-cutting analysis across the whole app. The `qa-consistency-checker` agent reads the source + the Phase 1 baseline screenshots + the Phase 2/3 observations.

### Visual consistency

For every component used in 2+ places, compare:

- Computed font sizes / weights / line-heights
- Computed padding / margin around the primitive
- Computed border-radius / shadow
- Hover / focus state appearance

Example findings:

- "Primary `<Button>` is `size="lg"` (height 44px) on /companies/new but `size="default"` (height 40px) on /contacts/new. Inconsistent."
- "Page title `<h1>` is `text-2xl font-semibold` on /companies but `text-3xl font-bold` on /contacts. Should be one component."
- "Table row hover background is `bg-muted` on /companies but `bg-accent` on /contacts."

### Structural consistency

Source-code analysis for refactor opportunities:

- Three modules each define their own `<DataTable>`, `<PageHeader>`, `<StatCard>`, `<EmptyState>` — should be shared in `apps/web/src/components/shared/`
- The same data-fetching pattern (`useQuery` + filter state in URL) is re-implemented per module — extract a `useListQuery` hook
- Multiple confirm-delete dialogs exist with slightly different wording — should be one `<ConfirmDeleteDialog>` component

### Layout consistency

- Every `<aside>` sidebar should be the same width (we now use shadcn's block, but the QA verifies in practice)
- Every page in the (authed) layout has the same content padding
- Modal/dialog widths are from a consistent scale (sm/md/lg/xl), not ad-hoc px values
- Z-indexes used: should be a finite ordered scale, not random `z-50` here and `z-100` there

### Behavioral consistency

- Every list page implements filter+sort+paginate the same way
- Every mutation surfaces success the same way (sonner toast position + duration)
- Every form's validation timing matches (on blur, or on submit, not both inconsistently)
- Every keyboard shortcut works across pages (Esc closes dialogs everywhere, not just some)

The agent produces `QA_CONSISTENCY.md` with findings grouped by category, each citing exact file:line for source issues and screenshot diffs for visual ones.

## Phase 5 — Performance

The `qa-performance-prober` agent runs instrumented flows and measures.

### Per-page metrics

For each route:

- **Time to first content** — `<main>` becomes non-empty
- **Time to interactive** — buttons respond to clicks
- **Largest Contentful Paint** — the standard Web Vitals metric
- **Cumulative Layout Shift** — does the page jump after first render?
- **Total Blocking Time** — main thread blocked time during page load
- **JS bundle size** — Next.js build output for this route

### Per-flow timing

For each happy-path flow from Phase 2:

- Total flow duration
- Time per step
- Network requests fired (count + total bytes)
- Frames dropped during interactions (scroll, drag, animate)

### Database query counts

For each frontend-initiated action, count backend queries:

```sql
-- Enable on dev DB
SET log_statement = 'all';
-- Run the flow
-- Tail the Postgres log; count queries per HTTP request
```

Flag:

- **N+1 patterns** — list endpoint fires `N` queries where 1 join would do
- **Missing eager loads** — detail endpoint hits the DB 8 times instead of 2
- **Full-table scans** — query plan shows `Seq Scan` on a table with an indexable column
- **Unbounded results** — query without `LIMIT` running against a large table

### Frontend data-volume analysis

The reason your `useMemo` example matters:

- Component renders `<Table>` from `useQuery` data
- Data array length is N
- Filter/sort applied via `.filter().sort()` in `useMemo`
- Test: at N=5000, type a character in the filter input — frame budget?

Flag any pattern where:
- Data length is dynamic (not bounded to <100 by pagination)
- Filter/sort is client-side
- The filter input doesn't debounce

These cause UI freezes that don't show up in functional tests but feel terrible to users.

### Memory / leak detection

Long-running interactions (5 minutes of clicking around) — does heap usage grow unbounded? Likely places: chart libraries forgetting to dispose, WebSocket subscriptions not cleaning up, image listeners.

The agent produces `QA_PERFORMANCE.md` with timing tables, query counts, flagged anti-patterns.

## Phase 6 — Report

The main agent (not a subagent) reads everything:

- `qa/flows/*/observations.md` (every happy + edge case observation)
- `qa/consistency/QA_CONSISTENCY.md`
- `qa/performance/QA_PERFORMANCE.md`
- Screenshots, traces, network logs for evidence references

And writes `QA_REPORT.md` per the template in `references/qa-report-format.md`.

The report:

- Executive summary (counts by severity)
- Per-feature breakdown (what's solid, what's broken)
- Cross-cutting findings (consistency, performance, refactors)
- Recommended ordered fix list
- Evidence appendix (screenshots, traces referenced by ID)

Severity ladder:

| Severity | Definition | Examples |
|---|---|---|
| **Critical** | Blocks launch — feature is broken or major UX failure | Form doesn't submit; create button shows wrong dialog; mobile sidebar covers content uncloseable |
| **High** | Embarrassing in front of users; noticeable in normal use | Missing empty state; 4-second page load; toast hidden behind dialog; broken on iPhone |
| **Medium** | Inconsistency or polish issue that compounds | Button sizes vary across pages; page titles inconsistent; minor layout shifts |
| **Low** | Nice-to-fix; doesn't impact real users | Hover state subtle inconsistency; 200ms delay where 100ms would feel snappier |
| **Refactor** | Not a bug; a code-quality opportunity | Three modules duplicate DataTable; useListQuery hook waiting to be extracted |

Critical findings should block launch. High findings need explicit user acknowledgment. Medium/Low/Refactor go in the report as recommendations.

## Place in a superdev-build run

In [`superdev-build`](../superdev-build/SKILL.md) Step 6, run the cross-cutting passes in this order: integration smoke (`integration-tester`) → `security-review-and-fix` → **this skill** → final report. A failed integration test stops the sequence before security/QA runs (no point exploring broken). Unresolved Critical findings in the QA report block any "done" claim.

Standalone (post-launch quality pass), invoke this skill directly.

## Reference files

| File | When to read |
|---|---|
| `../../agents/qa-*.md` | The 4 QA agent definitions (auto-loaded) |
| `references/environment-checklist.md` | Phase 1 — seed scale + baseline capture procedure |
| `references/flow-recipes.md` | Phase 2 + 3 — Playwright snippets for common flows (login, list, create, update, delete, etc.) and edge-case scenarios |
| `references/consistency-checklist.md` | Phase 4 — what to compare across pages, what counts as a finding |
| `references/performance-checklist.md` | Phase 5 — metrics to capture, anti-patterns to flag, query-count methodology |
| `references/qa-report-format.md` | Phase 6 — QA_REPORT.md template |

## Validation checklist

Before declaring QA complete:

- [ ] The 4 QA agents ran (or the main agent executed their checklists directly)
- [ ] `QA_ENVIRONMENT.md` exists with seed counts and baseline screenshots
- [ ] `qa/flows/<feature>/` exists for every feature module (happy + edge)
- [ ] `QA_CONSISTENCY.md` exists
- [ ] `QA_PERFORMANCE.md` exists with timing tables
- [ ] `QA_REPORT.md` exists with severity-ranked findings
- [ ] All Critical findings either resolved or explicitly accepted by user
- [ ] Screenshots are referenced by file path in the report (reviewer can verify)
- [ ] Database query counts are recorded for at least one full happy-path flow
- [ ] Mobile breakpoint coverage: 375px tested for every list/detail/form
- [ ] Performance baselines recorded (LCP, CLS, TBT per route)

## Common pitfalls

**P1 — Running with toy data.** A 5-row test DB hides 80% of what this skill exists to find. Phase 1's seed scale matters; don't shortcut it.

**P2 — Skipping mobile.** Most issues live at 375px width. The flow-tester should re-run every flow at mobile viewport, not just desktop.

**P3 — Treating "no console error" as "no issue."** Many UX issues produce zero errors. The agent must observe behavior + visual state, not just console output.

**P4 — Reporting noise.** A 200ms render diff on a primitive isn't a finding; a 2-second freeze on filter is. The agent applies severity rubric, not just "everything different."

**P5 — Trying to test things automated tests already cover.** Don't re-run unit tests. Don't re-run integration tests. Focus on what only an exploring engineer would find.

**P6 — Forgetting to flag refactor opportunities.** This skill is a unique vantage point for cross-module patterns. Three modules with duplicated table code = one refactor finding, not three "bug" findings.

**P7 — Reporting without evidence.** Every finding cites a screenshot path, source file:line, trace ID, or query log excerpt. "Companies page is slow" is a useless finding; "Companies list with 250 rows: LCP 3.8s, TBT 1.1s, see qa/performance/companies-list.trace.zip" is actionable.

**P8 — Running Phase 5 alongside Phase 2/3.** Performance measurement needs an idle system. Run perf last, after all flow testing is done and the system has settled.
