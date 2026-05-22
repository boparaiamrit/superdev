# product-completeness-audit — dispatch reference

Dispatch the four scanning agents in parallel; dispatch `journey-walker`
sequentially after them so it has the scanning output for context.

## Parallel wave

```
Dispatch in parallel:
- placeholder-hunter   → produces PLACEHOLDER_HITS.md
- route-completeness-checker → produces ROUTE_COMPLETENESS.md  (requires stack up in production mode)
- wiring-auditor       → produces WIRING_AUDIT.md
- data-flow-real-vs-mock → produces DATA_SOURCE_AUDIT.md
```

## Sequential

```
Use the journey-walker agent.

Inputs:
- Top 3-5 journeys from PRD_DIGEST.md
- QA_ENVIRONMENT.md credentials
- Production-mode stack (NEXT_PUBLIC_API_MODE=production)
- Prior outputs of the parallel wave (so you know which journeys are at risk)

Walk each journey end-to-end with reload + relog + role-switch checks.
DB-verify every "data created" step.

Produce JOURNEY_REPORT.md.
```

## Synthesis (the SKILL itself produces COMPLETENESS_REPORT.md)

After all 5 reports are on disk, the orchestrator (or the user) reads them and
produces the verdict:

- **PRODUCT** — all routes REAL, all interactions WIRED, all journeys complete with persistence
- **HYBRID** — some routes REAL but some HYBRID (with hardcoded fields), or some routes MOCKED. Specific list of what blocks "PRODUCT" verdict.
- **DEMO** — multiple critical paths MOCKED, stub handlers in core flows, or journey-walker found data doesn't persist across reloads

## Agent team — demo-vs-product debate

For findings where one teammate says DEMO and another says HYBRID:

```
Dispatch 3-teammate demo-vs-product debate.

Teammate A — strict: anything mocked = DEMO, period
Teammate B — pragmatic: mocked computed fields (counts derived from other
  tables) are acceptable IF clearly labeled "calculating..." in UI
Teammate C — user POV: "would I feel cheated if I bought this product
  expecting these features to work?"

Each round:
- One ambiguous finding at a time
- Each teammate proposes verdict + one-sentence justification
- After all three have spoken, vote; majority wins. Ties → strict.

Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```
