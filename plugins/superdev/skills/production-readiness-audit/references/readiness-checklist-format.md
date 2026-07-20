# READINESS.md, READINESS_CHECKLIST.md, and the ledger update

Three artifacts carry the loop's state. All live on disk so the loop survives context compaction — after a compaction, re-reading these (and `COMPLETION_LEDGER.json`) tells the orchestrator exactly which modules are still < 9 and what's left.

## READINESS.md — the scoreboard

```markdown
# Production readiness — <commit hash> — round <N>

| Module     | P1 Wire | P2 Data | P3 Tenancy | P4 E2E | P5 Quality | Score | Verdict |
|------------|:------:|:------:|:----------:|:-----:|:----------:|:-----:|---------|
| auth       |   10   |   9    |    10      |  10   |    10      |  9    | READY   |
| companies  |   9    |   9    |    9       |  9    |    9       |  9    | READY   |
| billing    |   9    |   9    |    9       |  9    |    3       |  3    | BLOCKED |
| reports    |   6    |   4    |    9       |  6    |    8       |  4    | BLOCKED |

Score = min(passes). Hard caps: tenancy leak or P0 security → ≤3.

## Blocking summary
- billing  3 — P5: card data hits the server (PCI P0). See checklist B-1.
- reports  4 — P2: reads mockReports in prod; P4: revenue shows $0 vs $50k in DB.

Overall: NOT READY (2 of 4 modules < 9). Continue loop → round <N+1>.
```

## READINESS_CHECKLIST.md — every finding as an owned ticket

One line per finding, ordered worst-first, each assigned to the fixer that will resolve it. This is what the orchestrator dispatches against.

```markdown
# Readiness checklist — round <N>

## billing (3 → target 9)
- [ ] B-1 [P5/P0] Card PAN reaches the API — move to Paddle.js client tokenization. file: apps/api/src/billing/billing.controller.ts:44 — owner: security-fixer
- [ ] B-2 [P1] "Download invoice" button calls alert() — wire to GET /billing/invoices/:id.pdf. file: apps/web/src/modules/billing/invoice-row.tsx:31 — owner: frontend-module-builder

## reports (4 → target 9)
- [ ] R-1 [P2] /reports reads mockReports[] in production. file: .../reports/page.tsx:14 — owner: frontend-module-builder
- [ ] R-2 [P4] Revenue tile shows $0 (hardcoded) vs $50k in DB. compute in presenter. — owner: backend-module-builder
```

Rules:
- Every item has: id, `[pass/severity]`, one-line fix, `file:line`, and an `owner` (the agent type).
- Items are NEVER resolved by suppression or by adding demo data — only by the real fix.
- When a fixer reports an item done, the orchestrator re-runs that item's pass to confirm before ticking it.

## COMPLETION_LEDGER.json update

After each round, `module-readiness-rater` updates the ledger the done-gate reads:

```jsonc
{
  "base_sha": "...", "head_sha": "<current HEAD>", "updated": "<iso>",
  "gates": {
    "typecheck": "pass", "lint": "pass", "build": "pass",
    "integration": "pass", "completeness": "pass", "security": "pass",
    "qa": "pass", "brutal": "pass",
    "readiness": "fail"        // pass ONLY when every module readiness_score >= 9
  },
  "features": {
    "auth":      { "readiness_score": 9, "passes": {"wire":10,"data":9,"tenancy":10,"e2e":10,"quality":10} },
    "companies": { "readiness_score": 9, "passes": {"wire":9,"data":9,"tenancy":9,"e2e":9,"quality":9} },
    "billing":   { "readiness_score": 3, "passes": {"wire":9,"data":9,"tenancy":9,"e2e":9,"quality":3} },
    "reports":   { "readiness_score": 4, "passes": {"wire":6,"data":4,"tenancy":9,"e2e":6,"quality":8} }
  }
}
```

- `gates.readiness` = `pass` iff every `features.*.readiness_score >= 9` (else `fail`).
- The done-gate (`hooks/scripts/done-gate.sh`) requires `gates.readiness == pass` AND every `readiness_score >= 9`. A module may be set to `"deferred": "<reason the user explicitly accepted>"` only with explicit user sign-off — that records an accepted risk rather than a silent drop.
- `head_sha` is refreshed each round so the done-gate's freshness check stays valid; if code changes after the last round, the ledger is stale and the gate re-blocks until the loop re-runs.
