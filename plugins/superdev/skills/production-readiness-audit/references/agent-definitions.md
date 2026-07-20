# production-readiness-audit — agents

This skill composes existing superdev specialists (the completeness, QA, and security agents) plus **three readiness-specific agents**. The three live in the plugin roster at `plugins/superdev/agents/` and are auto-registered as agent types — dispatch them by name.

## The three readiness-specific agents

| Agent | Role | When |
|---|---|---|
| `seed-data-architect` | Authors the deterministic seeder + initial owner/admin user + a second tenant with overlapping data; ensures aggregates are computed, not hardcoded; product works with demo mode OFF. | Precondition, before any scoring |
| `tenancy-isolation-tester` | Adversarial cross-tenant attacks (IDOR, list/search/export scoping, bulk, tokens/webhooks, UI deep-links) with DB cross-check. Any leak caps the module ≤3. | Pass 3, each round |
| `module-readiness-rater` | Aggregates the five pass reports into per-module 1–10 scores (min of passes, hard caps applied), writes `READINESS.md` + `READINESS_CHECKLIST.md`, updates `COMPLETION_LEDGER.json`. | After the passes, each round |

## Reused specialists (already in the roster)

- Pass 1: `placeholder-hunter`, `route-completeness-checker`, `wiring-auditor`, `data-flow-real-vs-mock`
- Pass 2: `data-flow-real-vs-mock` (HYBRID focus) + the seed verification
- Pass 4: `route-walker`, `qa-flow-tester`, `journey-walker`, `edge-case-prober`, `data-flow-tracer`
- Pass 5: `static-auditor`, `dependency-auditor`, `ui-auditor`, `module-structure-auditor`
- Fixers (the loop): `backend-module-builder` / `laravel-module-builder`, `frontend-module-builder` / `frontend-rewirer` / `inertia-module-builder`, `security-fixer`

## Dispatch order per round

```
(round 0 only) seed-data-architect → SEED.md
parallel:  Pass 1 agents, Pass 2 check, Pass 5 static agents
stack-up:  Pass 3 (tenancy-isolation-tester), Pass 4 (Playwright agents, batched at 6)
then:      module-readiness-rater → READINESS.md + READINESS_CHECKLIST.md + ledger
then:      for each module < 9, dispatch its checklist items to the owner fixers
re-run the sub-9 passes for fixed modules; repeat until all ≥ 9 or round 5.
```

The full per-pass prompts are in [`five-pass-audit.md`](five-pass-audit.md); the scoring rubric is in [`rubric.md`](rubric.md); the artifact formats + ledger schema are in [`readiness-checklist-format.md`](readiness-checklist-format.md).
