---
name: brutal-exhaustive-audit
description: Use when you need an absolutely thorough, no-shortcuts, multi-pass audit of the entire product before declaring it ready. Verifies every file, every route, every user flow, every data path, and every edge case via mandatory checklists that cannot be skipped. Use at the end of Phase D of the orchestrator, before any "ship it" claim, after major refactors, and on user demand ("audit this brutally"). Dispatches 6 specialized auditors with a 3-teammate severity-debate team for final triage. Refuses to declare done if any checklist item is unchecked.
---

# Brutal Exhaustive Audit

The "be exhaustive, be brutal, check everything" audit codified into an enforceable process.

Claude's context window forgets, skips files, and declares victory early. This skill prevents all of that through **mandatory multi-pass verification with explicit checklists tracked on disk**.

## The Iron Law

```
EVERY FILE CHECKED. EVERY ROUTE VISITED. EVERY FLOW WALKED. EVERY DATA PATH TRACED.
NO EXCEPTIONS. NO SHORTCUTS. NO "IT'S PROBABLY FINE."
```

If the file isn't on the checklist with a ✓, it wasn't checked. If a route returned 200 but you never walked the flow, you didn't audit it.

## When to use

- ✅ End of orchestrator Phase D, before declaring "ready to ship"
- ✅ After a major refactor or migration
- ✅ Before a release that touches multiple modules
- ✅ User explicitly asks for a brutal audit
- ✅ After repeated bug reports suggest something systemic is wrong

## When NOT to use

- ❌ During iterative feature development (use `integration-tester` or `ui-auditor` per wave instead)
- ❌ To debug a specific bug (use `systematic-debugging`)
- ❌ To verify functional completeness without UI rendering (use `product-completeness-audit`)
- ❌ When you just want a quick sanity check (this is the heavy machinery; expect tokens)

## How the orchestrator should use this skill

The orchestrator dispatches `brutal-exhaustive-audit` at the END of Phase D, AFTER:
- `integration-tester` has passed
- `security-review-and-fix` has produced a green SECURITY_REPORT.md
- `exploratory-qa` has produced QA_PERFORMANCE.md
- `product-completeness-audit` has run (functional completeness verified)

The orchestrator MUST read `.claude/memory/superdev-learned/` first and feed any relevant lessons into the audit prompt so the auditors don't repeat mistakes the project has previously learned from.

## The 6 phases (sequential — each gates the next)

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   PHASE 1    │──▶│   PHASE 2    │──▶│   PHASE 3    │──▶│   PHASE 4    │──▶│   PHASE 5    │──▶│   PHASE 6    │
│  CARTOGRAPHY │   │ ROUTE WALK   │   │  FLOW WALK   │   │  DATA TRACE  │   │  EDGE PROBE  │   │  SYNTHESIZE  │
│              │   │              │   │              │   │              │   │              │   │              │
│ repo-        │   │ route-       │   │ flow-walker  │   │ data-flow-   │   │ edge-case-   │   │ audit-       │
│ cartographer │   │ walker       │   │              │   │ tracer       │   │ prober       │   │ synthesizer  │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
       │                  │                  │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼                  ▼                  ▼
   MAP.md             ROUTES.md          FLOWS.md            DATA.md           EDGES.md          AUDIT.md
                                                                                              (prioritized
                                                                                               task list)
```

### Phase 1 — Cartography (`repo-cartographer`)

Produces `MAP.md` — the **complete inventory** with checkboxes:
- Every file under `apps/api/src/`, `apps/web/src/`, `packages/`
- Every route in `apps/web/src/app/` (Next.js App Router) and every controller in `apps/api/src/modules/`
- Every component under `apps/web/src/components/`
- Every Drizzle table
- Every Zod schema in `packages/contracts/`

No checking happens here — just listing with `[ ]` for every item. Phase 2–5 tick them off.

### Phase 2 — Route walk (`route-walker`)

For every route in `MAP.md`:
- HTTP GET it (frontend route) and check status
- Render in Playwright, screenshot, compare against design source if `design-source/` exists
- Ensure no placeholder text (`Lorem ipsum`, `TODO`, `Coming soon`)
- Tick the box. Note pass/fail in `ROUTES.md`.

### Phase 3 — Flow walk (`flow-walker`)

For every user journey in the PRD / EXECUTION_PLAN:
- Walk it end to end in Playwright with real seed data
- Verify the journey completes (user can actually do what they came to do)
- Record screenshots at every step
- Tick the box. Note pass/fail in `FLOWS.md`.

### Phase 4 — Data trace (`data-flow-tracer`)

For every entity in the contract:
- Trace: DB column → repository query → service → presenter → contract → frontend hook → component render
- Verify the value travels intact and is displayed where the design expects it
- Flag any field that is fetched but never rendered (waste) or rendered but mocked (incomplete)

### Phase 5 — Edge probe (`edge-case-prober`)

For every route in `MAP.md` × each edge category:
- Empty state (no data)
- Loading state (slow network — Playwright throttle)
- Error state (backend 500)
- Large data (10,000 rows)
- Concurrent mutations (two browsers)
- Long content (titles 500 chars)
- Special characters (emoji, RTL, SQL-injection-shaped strings)
- Keyboard-only navigation
- Mobile viewport (375×667)

Tick boxes. `EDGES.md`.

### Phase 6 — Synthesize (`audit-synthesizer`)

Reads all 5 prior reports. Produces `AUDIT.md`:
- Findings prioritized P0/P1/P2/P3
- For each: file:line, evidence (screenshot path or log line), suggested fix
- Concrete actionable task list — every item is a one-line ticket

## Agent teams (severity debate, optional)

For findings the synthesizer marks ambiguous (could be P0 or P2), dispatch a 3-teammate severity-debate team:

```
Dispatch 3-teammate severity debate.
Teammate A: harshest critic — defaults to higher severity, cites worst case
Teammate B: pragmatist — weighs realistic impact vs cost to fix
Teammate C: shipping advocate — asks "does this block ship today?"

For each ambiguous finding, run a round. Majority wins.
Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```

## Gate to declare audit complete

- [ ] `MAP.md` has every file/route/component/table/schema listed
- [ ] `ROUTES.md` has every box checked
- [ ] `FLOWS.md` has every journey walked end-to-end
- [ ] `DATA.md` has every entity traced
- [ ] `EDGES.md` has every edge category probed for every route
- [ ] `AUDIT.md` produced with prioritized findings
- [ ] All P0 findings have an owner and ETA

If ANY checkbox is unchecked, the audit is incomplete. The orchestrator MUST NOT mark "ready to ship".

## Reference files

- [`references/cartography-template.md`](references/cartography-template.md) — MAP.md format
- [`references/edge-case-catalog.md`](references/edge-case-catalog.md) — what to probe per route
- [`references/agent-definitions.md`](references/agent-definitions.md) — dispatch prompts
