# product-completeness-audit — dispatch reference

Dispatch the four scanning agents in parallel; dispatch `journey-walker`
sequentially after them so it has the scanning output for context.

## Parallel group

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
- Prior outputs of the parallel group (so you know which journeys are at risk)

Walk each journey end-to-end with reload + relog + role-switch checks.
DB-verify every "data created" step.

Produce JOURNEY_REPORT.md.
```

## Synthesis (the SKILL itself produces COMPLETENESS_REPORT.md)

After all 5 reports are on disk, the main agent (or the user) reads them and
produces the verdict:

- **PRODUCT** — all routes REAL, all interactions WIRED, all journeys complete with persistence
- **HYBRID** — some routes REAL but some HYBRID (with hardcoded fields), or some routes MOCKED. Specific list of what blocks "PRODUCT" verdict.
- **DEMO** — multiple critical paths MOCKED, stub handlers in core flows, or journey-walker found data doesn't persist across reloads
