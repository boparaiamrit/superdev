# brutal-exhaustive-audit — agent dispatch reference

## Phase 1 — repo-cartographer

```
Use the repo-cartographer agent. Produce MAP.md with totals per section
derived from filesystem commands (not from memory). Sort items.
Compare counts to .claude/memory/superdev-learned/last-audit-counts.md if
present; flag any dropped count as a finding.
```

## Phase 2 — route-walker

```
Use the route-walker agent. MAP.md must exist.
For each frontend route: curl + Playwright render + placeholder grep + tick box.
For each backend endpoint: curl with auth + status check + shape check + tick box.
Produce ROUTES.md.
```

## Phase 3 — flow-walker

```
Use the flow-walker agent. Inputs: PRD_DIGEST.md (or EXECUTION_PLAN.md)
and QA_ENVIRONMENT.md.
Walk every PRD-listed user journey end-to-end in Playwright with real seed
data. Verify final UI state AND final DB state.
Produce FLOWS.md. Screenshots required for every step, pass or fail.
```

## Phase 4 — data-flow-tracer

```
Use the data-flow-tracer agent. For each Zod schema in packages/contracts/,
trace every field through DB → repository → service → presenter → contract →
hook → component. Flag MOCKED, WASTE, OPTIONAL-ON-CONTRACT-FIELD, SHAPE-DRIFT.
Produce DATA.md. Write wiring percentages to project memory.
```

## Phase 5 — edge-case-prober

```
Use the edge-case-prober agent. For every route in MAP.md cross every category
from references/edge-case-catalog.md. Run via Playwright. Save evidence under
edges/. Categorize each result GRACEFUL | DEGRADED | BROKEN with severity.
Produce EDGES.md.
```

## Phase 6 — audit-synthesizer

```
Use the audit-synthesizer agent. Inputs: MAP, ROUTES, FLOWS, DATA, EDGES.
Refuse to run if any input has unchecked items.
Dedupe findings, assign P0/P1/P2/P3, group by feature.
Produce AUDIT.md with summary, P0 ship-blockers, suggested fixes, owners TBD.
Write recurring-issue classes to .claude/memory/superdev-learned/audit-patterns.md
so future builds default-on the missing patterns.
```

## Agent teams (severity debate)

For each finding in AUDIT.md marked `SEVERITY: ambiguous`, dispatch the
3-teammate severity-debate team:

```
Dispatch 3-teammate severity debate.

Teammate A — harshest critic: defaults to higher severity, cites worst case
Teammate B — pragmatist: weighs realistic impact vs cost to fix
Teammate C — shipping advocate: asks "does this block ship today?"

For each ambiguous finding, one round:
- Each teammate proposes severity + one-sentence justification
- Each teammate critiques the other two
- Vote. Majority wins; ties go to the harshest critic by default.

Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```
