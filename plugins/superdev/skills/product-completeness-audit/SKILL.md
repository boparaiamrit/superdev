---
name: product-completeness-audit
description: Use when a product "looks done" but you suspect flows are broken, pages are placeholders, data is hardcoded, or the frontend and backend aren't fully wired. Audits every route and component for FUNCTIONAL completeness vs visual completeness. A beautiful UI rendering hardcoded data is a demo, not a product — this skill proves it either way. Dispatches 5 agents (placeholder-hunter, route-completeness-checker, wiring-auditor, data-flow-real-vs-mock, journey-walker) with optional 3-teammate demo-vs-product debate for edge cases. Reuses exploratory-qa's Playwright MCP server.
---

# Product Completeness Audit

The skill that asks the question: *"If a user opened this RIGHT NOW and tried to actually use it with real data, what would break?"*

## The Iron Law

```
A BEAUTIFUL UI WITH HARDCODED DATA IS A DEMO, NOT A PRODUCT.
If a user cannot complete their intended journey end-to-end with real data, the product is NOT done.
```

## When to use

- ✅ Between `exploratory-qa` (which tests flows) and final "ship" claim (which assumes the flows MEAN something real)
- ✅ When the UI looks polished but the user can't quite tell if the buttons work
- ✅ After a `prototype-to-saas` migration to verify nothing is still reading from JSON fixtures in "production" mode
- ✅ Before a demo where a stakeholder will click on things expecting them to work

## When NOT to use

- ❌ For visual / design fidelity (use `design-preservation` instead)
- ❌ For security (use `security-review-and-fix`)
- ❌ For performance (use `exploratory-qa`'s `qa-performance-prober`)
- ❌ For brutal whole-product audit (use `brutal-exhaustive-audit` — this skill is more focused)

## How the orchestrator should use this skill

The orchestrator dispatches `product-completeness-audit` after `integration-tester` and `exploratory-qa` pass — BEFORE `brutal-exhaustive-audit`. The order matters:

1. Integration tests prove the wires connect
2. Exploratory QA proves the flows behave
3. **Product-completeness audit proves the wires + flows are connected to REAL DATA, not mocks** ← here
4. Brutal exhaustive audit dots every i and crosses every t

The orchestrator also reads `.claude/memory/superdev-learned/completeness-patterns.md` before dispatch — if past audits found certain placeholder-shaped patterns are common in this repo, those become extra grep targets.

## The 5 agents (run in parallel where possible)

```
┌────────────────────────┐        ┌──────────────────────────────┐
│ placeholder-hunter     │        │ route-completeness-checker   │
│ Greps for TODO, lorem  │        │ Every route renders real data│
│ ipsum, mock data, etc. │        │ (no skeletons in production) │
└──────────┬─────────────┘        └──────────────┬───────────────┘
           │                                     │
           ▼                                     ▼
┌────────────────────────┐        ┌──────────────────────────────┐
│ wiring-auditor         │        │ data-flow-real-vs-mock       │
│ Every button click     │        │ Every screen reads from real │
│ triggers a real API,   │        │ backend, not local JSON      │
│ not console.log/alert  │        │ fixtures (in production mode)│
└──────────┬─────────────┘        └──────────────┬───────────────┘
           │                                     │
           └──────────────┬──────────────────────┘
                          ▼
                ┌────────────────────┐
                │ journey-walker     │
                │ End-to-end journey │
                │ in Playwright with │
                │ REAL backend       │
                └─────────┬──────────┘
                          ▼
              COMPLETENESS_REPORT.md
```

## Agent responsibilities

### `placeholder-hunter`
Greps the codebase for placeholder patterns:
- `TODO`, `FIXME`, `XXX`, `HACK`
- `lorem ipsum`, `placeholder`, `coming soon`, `not implemented`
- `console.log("clicked")`, `alert(`, `// stub`
- Hardcoded sample data: arrays inline in components, `mockData`, `fakeUsers`
- `return null` / `return <div />` in handlers that should do real work

### `route-completeness-checker`
For every route:
- In **production mode** (`NEXT_PUBLIC_API_MODE=production`), does the route render REAL data fetched from the backend?
- Are there any routes that still serve the demo-mode JSON in production mode? (This is a regression failure of the dual-mode adapter.)

### `wiring-auditor`
For every interactive element (button, link, form submit, menu item):
- Inspect its handler. Does it call a real API or fire-and-forget local state?
- Form submits: does the data actually persist? Check the DB after.
- Navigation: does the destination exist and render its data?

### `data-flow-real-vs-mock`
For every screen, classify:
- **REAL** — reads from backend via TanStack Query
- **MOCKED** — reads from local JSON / hardcoded array / `useState([...])`
- **HYBRID** — reads from backend BUT some fields are hardcoded (most dangerous — looks real but isn't)

### `journey-walker`
Walks the top 3–5 user journeys in **production mode against a real backend** (not demo mode). Verifies:
- Data created in step 1 actually appears in step 3
- Refreshing the page in the middle preserves state
- Logging out and back in still shows the data
- Different roles see appropriately different data

## Output: COMPLETENESS_REPORT.md

```markdown
# Product completeness report — <commit hash>

## Verdict
- DEMO (multiple critical paths are mocked/placeholder)
- HYBRID (some real, some demo — see breakdown)
- PRODUCT (all flows complete with real data)

## Per-route completeness

| Route | Data source | Wiring | Real-data journey | Verdict |
|---|---|---|---|---|
| /companies | REAL | ✓ all buttons wired | ✓ | PRODUCT |
| /companies/[id] | HYBRID | ✗ "Add note" alerts instead of saves | ✓ for view | DEMO for write paths |
| /reports | MOCKED | n/a | ✗ | DEMO |

## Placeholder hits
- apps/web/src/components/export-button.tsx:88 — `// TODO: implement`
- apps/web/src/modules/reports/page.tsx:14 — hardcoded mockReports array

## Wiring violations
- apps/web/src/modules/companies/[id]/notes-panel.tsx:42 — onClick calls alert(), not API

## Recommendation
- Block ship until P0 items in the above tables are resolved
- Or: ship as "early access" with explicit "Reports coming soon" UX
```

## Agent teams (optional — demo-vs-product debate)

For findings classified HYBRID where it's ambiguous whether it counts as DEMO or PRODUCT, dispatch:

```
Dispatch 3-teammate demo-vs-product debate.
Teammate A: strict — anything mocked = DEMO
Teammate B: pragmatic — mocked fields that are eventually-computed (e.g. counts derived from other tables) can ship as TODO if labeled in UI
Teammate C: user — "would I feel cheated if I bought this?"

Majority verdict. Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```

## Reference files

- [`references/placeholder-patterns.md`](references/placeholder-patterns.md) — grep targets per stack
- [`references/wiring-checklist.md`](references/wiring-checklist.md) — what counts as "wired"
- [`references/agent-definitions.md`](references/agent-definitions.md) — dispatch prompts
