# QA Report Format (Phase 6)

The `QA_REPORT.md` template the orchestrator writes by synthesizing observations from Phases 1-5.

This is the artifact the team reads. It must be skimmable, actionable, and evidence-cited.

## Template

```markdown
# QA Report

> Generated: <ISO 8601>
> Stack: web=http://localhost:3000, api=http://localhost:3001
> Scope: <feature list or "full app">
> Seed scale: <N> workspaces, <N> companies, <N> contacts, ... (per QA_ENVIRONMENT.md)

## TL;DR

(One paragraph an exec can read in 30 seconds.)

Example:
> The app is functional but not production-ready. 4 critical issues block launch (duplicate submission on every form, missing empty states on 3 modules, mobile sidebar unusable, companies filter freezes at 1000 rows). 12 high-severity issues should be addressed before customer onboarding. There are 8 strong refactor opportunities — primarily duplicated DataTable/EmptyState/PageHeader components across modules — that would reduce code by ~1100 lines and prevent future inconsistency.

## Summary

- **Critical:** N (block launch)
- **High:** N (address before customer onboarding)
- **Medium:** N (compound over time; fix this sprint or next)
- **Low:** N (polish backlog)
- **Refactor:** N (debt reduction, not bugs)

## Findings by phase

| Phase | Findings | Critical | High | Medium | Low | Refactor |
|---|---|---|---|---|---|---|
| Happy-path flows | N | N | N | N | N | — |
| Edge cases | N | N | N | N | N | — |
| Consistency | N | — | N | N | N | N |
| Performance | N | N | N | N | — | — |

## Critical findings (LAUNCH BLOCKERS)

Each Critical gets a full entry with evidence. Linked from the TL;DR.

### C-1: Companies create form fires duplicate POSTs on fast click

- **Severity:** Critical
- **Origin:** Phase 3 edge case — concurrent-mutation
- **Feature:** companies
- **Source:** apps/web/src/modules/companies/components/add-button.tsx:32 — `onClick={mutate}` without disable-while-pending
- **What happens:** Clicking the submit button 5 times in 100ms fires 5 POST /companies — creates 5 duplicate records.
- **Expected:** Submit disabled on first click; only 1 POST fires regardless of click frequency.
- **Evidence:**
  - Network HAR: qa/flows/companies/edge-cases/concurrent-mutation/network.har
  - Trace: qa/flows/companies/edge-cases/concurrent-mutation/trace.zip
- **Recommendation:** Use TanStack Query's `isPending` to disable the submit button. Likely a single-line fix: `<Button disabled={isPending} type="submit">Create</Button>`
- **Related:** Same pattern needs checking on every create/update form (qa-consistency-checker found it in contacts/new and campaigns/new too — same fix everywhere).

### C-2: ...

## High-severity findings

Brief format — 1 paragraph each.

### H-1: Companies list LCP is 3.8s with 250 records

- **Origin:** Phase 5 perf
- **Source:** apps/web/src/modules/companies/components/list.tsx
- **Metric:** LCP 3.8s (target <2.5s; >4s would be Critical)
- **Root cause:** Companies presenter on backend issues N+1 for `counts.contacts` — 1 query per company × 20 companies = 20 sub-queries on top of the main query
- **Recommendation:** Use a single grouped query for `counts.contacts` keyed by `company_id IN (...)`; reduce 21 queries → 2.
- **Evidence:** qa/performance/companies-list-trace.zip, qa/performance/companies-list-queries.log
- **Estimated improvement:** LCP should drop to ~1.5s.

### H-2: ... (more Highs)

## Medium and Low findings (summary table)

Skip full entries for these; one row per finding:

| ID | Severity | Category | Feature | Title | Recommendation |
|---|---|---|---|---|---|
| M-1 | Medium | Consistency | (all) | Page padding varies (`p-4` vs `p-6` vs `p-8` across pages) | Standardize on `p-6` for authed layouts |
| M-2 | Medium | Empty state | campaigns | Empty state has no CTA | Add "Create your first campaign" button |
| M-3 | Medium | UX | contacts | Validation errors flash on every keystroke | `useForm({ mode: 'onBlur' })` |
| ... | | | | | |

## Refactor opportunities

Each refactor with size + risk.

### R-1: DataTable duplicated across 4 modules

- **Files:**
  - apps/web/src/modules/companies/components/list-table.tsx (142 lines)
  - apps/web/src/modules/contacts/components/list-table.tsx (138 lines)
  - apps/web/src/modules/campaigns/components/list-table.tsx (151 lines)
  - apps/web/src/modules/leads/components/list-table.tsx (148 lines)
- **Total:** 579 lines
- **Estimated savings:** ~400 lines after extracting `<DataTable<T>>` generic + per-feature column definitions
- **Risk:** Medium — implementations are structurally similar but each has custom row-action menus
- **Suggested location:** `apps/web/src/components/shared/data-table/`
- **API sketch:**
  ```tsx
  <DataTable<CompanyView>
    data={data.items}
    columns={columns}
    pagination={{ page, total: data.total, perPage: data.per_page, onPageChange: setPage }}
    isLoading={isLoading}
    rowActions={(row) => <CompanyRowActions company={row} />}
    emptyState={<EmptyState ... />}
  />
  ```
- **Sequencing:** Do after R-2 (EmptyState) and R-3 (PageHeader) since DataTable uses both.

### R-2: EmptyState component duplicated 4 times

(...)

### R-3: PageHeader component duplicated 6 times

(...)

### R-4: ConfirmDestructiveAction dialog duplicated 7 times

(...)

### R-5: useListQuery hook waiting to be extracted

- **Files:** 5 hooks each implementing the same pattern: filters state + URL sync + TanStack Query with stable keys
- **Estimated savings:** ~250 lines
- **Risk:** Medium — variations in filter shape per feature

## Cross-cutting concerns

### Performance anti-patterns

- 3 list pages do client-side filter/sort with >100 rows (companies, contacts, campaigns) — should be server-side
- 1 list page (analytics) fetches without `LIMIT` — returns the entire table

### Consistency anti-patterns

- Button sizing varies on equivalent primary actions across 5 modules
- Submit button labels: "Save" (3), "Create" (4), "Submit" (2), "Done" (1) — pick one verb per semantic action
- Validation timing: `onChange` (3 modules), `onBlur` (2 modules), `onSubmit` (1 module) — pick `onBlur` per design system

### Mobile concerns

- Sidebar overlay on mobile (375px) doesn't close on tap-outside on /campaigns (Critical)
- Several primary buttons render at 28×28px on mobile — below 44×44 WCAG threshold
- Dialog widths set in `px` not `max-w-*` — some exceed 375px viewport

### Accessibility concerns

- Page titles missing on 2 routes (no `<h1>`)
- Focus rings invisible on `<Card>` clickable variants
- 1 dialog doesn't trap focus
- No keyboard shortcuts (no `Cmd+K` or similar — flag as future enhancement, not a finding)

## Recommended fix order

Ordered list with severity and effort. The team works top-to-bottom.

1. **C-1** Companies submit double-fire — 5 min fix, affects every form — DO FIRST
2. **C-2** Mobile sidebar uncloseable — 30 min — DO BEFORE ANY MOBILE TESTING
3. **C-3** Companies filter freeze at 1000 rows — 2-4 hours — move filter to server (already supported on backend)
4. **C-4** Missing empty states (3 modules) — 1 hour total — add the `<EmptyState>` (sets up R-2 refactor)
5. **R-2** Extract `<EmptyState>` shared component — 30 min — sets up future modules
6. **R-3** Extract `<PageHeader>` — 1 hour
7. **H-1..H-N** High findings — group by feature; do one feature at a time
8. **R-1** Extract `<DataTable>` — 4-6 hours; biggest impact
9. ... etc

## Evidence appendix

Index of every screenshot, trace, and log referenced above:

- `qa/baselines/` — Phase 1 baselines (route × viewport)
- `qa/flows/<feature>/happy-path/` — Phase 2 per-feature flows
- `qa/flows/<feature>/edge-cases/<category>/` — Phase 3 edge cases
- `qa/consistency/` — Phase 4 diff data
- `qa/performance/` — Phase 5 traces, query logs, EXPLAIN ANALYZE plans

## Acknowledged risks

The user (during Phase 6 review) may accept some findings as deferred:

| Finding | User decision | Reason | Re-check by |
|---|---|---|---|
| H-7 | Defer to v1.1 | Affects only the rarely-used audit log viewer | Q2 |
| M-12 | Won't fix | Cosmetic; design intent confirmed | — |

## Sign-off

The QA review is complete when:
- All Critical findings have a status: Fixed, In Progress, or Accepted Risk
- All High findings have been triaged
- The team has a copy of this report and the recommended fix order
- Re-running the relevant edge-case flows confirms fixes work (Phase 7 re-test, not part of initial pass)
```

## Report-writing principles

- **Every finding cites evidence.** No "I think this feels slow"; cite the trace ID with metrics.
- **Severity is rule-based, not vibe-based.** Use the rubric; don't downgrade Critical findings to be polite.
- **Refactor findings are a feature.** This skill is uniquely positioned to find cross-module patterns; capture them while you can see them.
- **Fix order is opinionated.** "Here are 47 things wrong" is overwhelming; "Here's the order to fix them" is actionable.
- **TL;DR drives priorities.** Most readers won't get past it. Make sure the top 3-5 things are in it.
- **Don't include findings outside scope.** Security findings → security skill. Functional regressions → integration tests. This report is for things only a human-style exploratory pass catches.

## Anti-patterns

- ❌ Padding the report with every minor inconsistency to look thorough — focus on impact.
- ❌ Writing recommendations the team won't act on ("rewrite in Svelte") — recommend within their stack.
- ❌ Withholding refactor candidates because "they're not bugs" — they are arguably the most valuable findings.
- ❌ Reports without an ordered fix list — the team needs a starting point, not a checklist.
- ❌ Mixing severity with priority. A Medium finding in the main login flow is more urgent than a Critical in an admin-only debug page. Recommend order in the "Recommended fix order" section.
