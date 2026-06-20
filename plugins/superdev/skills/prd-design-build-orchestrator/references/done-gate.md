# Definition of Done — the enforced gate

superdev's pipeline used to be advisory prose: "run the audits before declaring done." In two real builds that meant the audits ran only when the user forced them — completeness/security days late, brutal-audit not at all — so builds were declared "done / live / production-ready" at ~70%. This gate makes "done" a machine-checkable pass/fail that the model cannot talk past.

## The two enforcement points

1. **Stop hook** (`hooks/scripts/done-gate.sh`, wired in `hooks/hooks.json`). On every turn the assistant tries to end, if `.claude/.superdev-orchestrating` exists AND the last assistant message claims completion (`done`, `ready`, `production-ready`, `is live`, 🎉, 🚀, …), the gate runs. Any red check returns `{"decision":"block","reason":…}` so the turn cannot end on a false "done". It is fail-open (any inability to inspect state approves) and loop-bounded (after 6 consecutive blocks it allows the stop with a warning).
2. **`/superdev-done` skill** — runs the same script in `--report` mode for an on-demand human-readable verdict.

## What arms it

The orchestrator MUST, at **Phase B start**:

```bash
mkdir -p .claude
touch .claude/.superdev-orchestrating            # arms the Stop gate
git rev-parse HEAD > /dev/null 2>&1 && BASE=$(git rev-parse HEAD)
cat > COMPLETION_LEDGER.json <<JSON
{
  "base_sha": "$BASE",
  "head_sha": "$BASE",
  "updated": "",
  "gates": {
    "typecheck": "pending", "lint": "pending", "build": "pending",
    "integration": "pending", "completeness": "pending",
    "security": "pending", "qa": "pending", "brutal": "pending"
  },
  "features": {}
}
JSON
```

Without the sentinel, the Stop gate stays dormant (so the plugin never interferes with non-superdev sessions).

## The ledger schema (`COMPLETION_LEDGER.json`, repo root)

```jsonc
{
  "base_sha": "<git SHA when the build started>",   // anchors the no-new-suppressions diff
  "head_sha": "<git SHA when gates last ran>",       // freshness: must equal HEAD at done-time
  "updated": "<ISO timestamp>",
  "gates": {
    "typecheck":    "pass|fail|pending|deferred",
    "lint":         "pass|fail|pending|deferred",    // at --max-warnings=0
    "build":        "pass|fail|pending|deferred",
    "integration":  "pass|fail|pending|deferred",    // integration-tester
    "completeness": "pass|fail|pending|deferred",     // product-completeness-audit
    "security":     "pass|fail|pending|deferred",     // security-review-and-fix (0 Critical/High)
    "qa":           "pass|fail|pending|deferred",     // exploratory-qa (0 Critical)
    "brutal":       "pass|fail|pending|deferred",      // brutal-exhaustive-audit (0 open P0)
    "readiness":    "pass|fail|pending|deferred"      // production-readiness-audit (every module >= 9)
  },
  "features": {
    "<feature>": { "built": true, "typecheck": true, "lint": true,
                   "integration": true, "completeness": true,
                   "security": true, "qa": true,
                   "readiness_score": 9,               // production-readiness-audit; < 9 fails the gate
                   "passes": { "wire": 9, "data": 9, "tenancy": 9, "e2e": 9, "quality": 9 },
                   "deferred": [] }
  }
}
```

- A gate value of `pass` passes. `deferred` (string reason) is an **accepted risk** — allowed but reported. Anything else (`pending`/`fail`/missing) **fails** the gate.
- A feature flag set to `false` fails, and a feature `readiness_score < 9` fails (unless that feature is explicitly `deferred` with a user-accepted reason). A feature's `deferred` (string or list) is reported as accepted risk.
- The driver updates `head_sha`/`updated` whenever it re-runs gates after code changes — otherwise the ledger is **stale** and the gate fails (this is what stops "done" surviving a post-compaction summary that dropped the audit work).

## How the gates get to `pass`

The wave gate (`wave-gate.sh`) sets `typecheck`/`lint` per wave. The **Phase D driver** runs, in order, and records each verdict:

1. `integration-tester` → `gates.integration`
2. `product-completeness-audit` → `gates.completeness` (DEMO verdict ⇒ `fail`)
3. `security-review-and-fix` → `gates.security` (any unresolved Critical/High ⇒ `fail`)
4. `exploratory-qa` → `gates.qa` (any unresolved Critical ⇒ `fail`)
5. `brutal-exhaustive-audit` → `gates.brutal` (any open P0 ⇒ `fail`)
6. `production-readiness-audit` → `gates.readiness` + per-module `readiness_score` (the iterative 5-pass loop; `pass` ONLY when every module scores ≥ 9)

Because the Stop gate requires all of these to be `pass` AND every module `readiness_score ≥ 9`, the ONLY way to satisfy it is to actually run Phase D and the readiness loop — neither is something the user has to remember to ask for.

## Live checks (run by done-gate regardless of the ledger)

- **No new suppressions** vs `base_sha` (and in new untracked files) — stack-aware: TS `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `as any`, `as unknown as`; PHP `@phpstan-ignore`, `@phpcs:ignore`, `@codingStandardsIgnore`, `@phan-suppress`.
- **No demo/placeholder** in the frontend — `apps/web/src` (Next.js) AND `apps/api/resources/js` (the Inertia monolith): `lorem ipsum`, `coming soon`, `not implemented`, hardcoded test cards, `mockData`/`fakeUsers` (mocks/tests/stories excluded).

> The expensive per-stack gates (typecheck/lint for TS via tsc+eslint; Pint+PHPStan for Laravel; Pest/integration tests) are recorded into the ledger by `wave-gate.sh` and the Phase D driver — done-gate reads those verdicts rather than re-running them, so it stays fast regardless of stack.

## Override

`touch .claude/.superdev-done-override` records that the user consciously accepts the current state; the gate then approves. Remove it to re-arm.
