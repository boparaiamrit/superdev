# READINESS.md and READINESS_CHECKLIST.md

Two artifacts carry the loop's state. Both live on disk so the loop survives context compaction — after a compaction, re-reading these tells the main agent exactly which modules are still < 9 and what's left. READINESS.md is stamped with the commit hash it describes; scores for a different HEAD are stale and must be re-proven, not trusted.

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

One line per finding, ordered worst-first, each assigned to the fixer that will resolve it. This is what the main agent dispatches against.

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
- When a fixer reports an item done, the main agent re-runs that item's pass to confirm before ticking it.

## Evidence rule

Every score on the scoreboard carries an **Evidence** line naming the proof: the command and its output, the `curl` response, the DB query result, or the Playwright artifact path. A pass that did not run — or whose evidence cannot be pointed to — is scored **0**, never assumed. This replaces the old self-graded completion ledger, which a previous build marked all-`pass` without running the formal passes. Machine-checkable hygiene (build, boot, suppressions) belongs to `verify-done.mjs`; this scoreboard carries the judgment calls, with receipts.
