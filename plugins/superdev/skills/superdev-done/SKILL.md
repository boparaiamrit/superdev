---
name: superdev-done
description: Run superdev's machine-checkable Definition-of-Done gate on demand. Reads COMPLETION_LEDGER.json (build/typecheck/lint/integration/completeness/security/qa/brutal verdicts) plus live no-suppressions and demo/placeholder sweeps, and reports PASS/FAIL with the exact failing checks. Use when asked "are we done", "is it production ready", "run the done gate / completeness gate", or BEFORE declaring any superdev build complete. The same gate runs automatically as a Stop hook during superdev builds, so a "done" claim cannot be made while any check is red.
---

# superdev — Definition of Done

The single source of truth for "is this build actually done?" — not narrative, not "it typechecks", but every Phase D verdict plus live anti-regression sweeps. This is what prevents the failure mode where a build is declared "done / live / production-ready" while it still has lint errors, mock data, or unaudited security holes.

## How to run

Run the gate in report mode and read the result:

```bash
_d="${CLAUDE_PLUGIN_DIR:-}"
[ -z "$_d" ] && _d="$(ls -d ~/.claude/plugins/cache/*/superdev/*/ 2>/dev/null | sort -V | tail -1)"
[ -z "$_d" ] && _d="$(ls -d ~/.claude/plugins/superdev/ 2>/dev/null | head -1)"
bash "${_d%/}/hooks/scripts/done-gate.sh" --report
```

- Exit `0` → **DONE**: every gate in `COMPLETION_LEDGER.json` is `pass` (or an explicitly `deferred` accepted risk), no suppressions were introduced since the build base, and no demo/placeholder content remains in `apps/web/src`.
- Exit `1` → **NOT DONE**: the report lists the exact failing checks. Resolve each at the ROOT CAUSE — do NOT suppress (no `eslint-disable`, `@ts-ignore`, `as any`, rule downgrades) and do NOT leave mock data on success paths. Then re-run.

## What it checks

See [`../prd-design-build-orchestrator/references/done-gate.md`](../prd-design-build-orchestrator/references/done-gate.md) for the full ledger schema and check definitions. In short:

1. **Ledger gates** — `typecheck`, `lint`, `build`, `integration`, `completeness`, `security`, `qa`, `brutal` must all be `pass`. A `deferred` value is allowed only as a recorded accepted risk.
2. **Ledger freshness** — the ledger's `head_sha` must match the current `HEAD`; a stale ledger (code changed after the last gate run) is a fail.
3. **No new suppressions** — `git diff` vs the build base AND new untracked files must contain no `eslint-disable` / `@ts-ignore` / `@ts-expect-error` / `as any` / `as unknown as`.
4. **No demo/placeholder** — `apps/web/src` must be free of `lorem ipsum`, `coming soon`, `not implemented`, hardcoded test cards (`4242…`), `mockData`/`fakeUsers`, etc. (mocks/tests/stories excluded).

## Relationship to the automatic gate

The orchestrator writes `COMPLETION_LEDGER.json` as each Phase D agent finishes and creates `.claude/.superdev-orchestrating` at Phase B. While that sentinel exists, the **Stop hook** runs this same script and BLOCKS any turn that ends on a completion claim while a check is red. This skill is the manual/explicit way to query the same gate at any time.

To intentionally accept the current state and stop anyway, create `.claude/.superdev-done-override` (records that the user consciously overrode the gate).
