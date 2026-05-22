---
name: systematic-debugging
description: Use for ANY technical issue — test failures, runtime bugs, unexpected behavior, performance regressions, build failures, integration breakages, "it works on my machine" mysteries. Especially when under time pressure, when "just one quick fix" seems obvious, when previous fixes didn't work, or when the same bug keeps coming back. Dispatches a 5-agent investigation pipeline (reproduce → root-cause → hypothesis-test → fix → regression-verify) with optional 3-teammate competing-hypotheses team when the root cause is ambiguous. Refuses to apply fixes until a verified root cause exists.
---

# Systematic Debugging

A 5-phase brutal-debug pipeline that **refuses to fix symptoms**. Every fix must be justified by a verified root cause produced by a dedicated investigator agent — not by Claude's gut feel.

## The Iron Law

```
NO FIX IS APPLIED WITHOUT A VERIFIED ROOT CAUSE ARTIFACT ON DISK.
```

Phase 3 produces `ROOT_CAUSE.md`. Phase 4 (`fix-applier`) refuses to run if that file is missing or marked `UNVERIFIED`. There is no shortcut.

## When to use this skill

- Any test failure (unit, integration, E2E)
- Any production bug — outage, crash, data corruption, perf cliff
- "It worked yesterday" / "It works locally but not in CI"
- Same bug came back after a previous fix
- A previous fix touched unrelated code (red flag — symptom fix)
- Build failures that "started randomly"
- Integration drift — frontend renders wrong because backend changed shape

## When NOT to use it

- You haven't seen a real failure yet — use `brutal-exhaustive-audit` to find issues first
- You're refactoring with no bug to chase — use the framework refactor workflow
- The "bug" is actually a feature request — that's planning, not debugging

## Inputs

| Input | Source |
|---|---|
| Failure description | User message |
| Failing command / route / test | User message — exact reproduction |
| Recent changes (suspected) | `git log -20`, your own analysis |
| Logs / stack traces | User-pasted, or fetched from `apps/api/logs/`, container logs, browser console |

## The 5 phases

```
┌──────────────┐   ┌──────────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│   PHASE 1    │──▶│     PHASE 2      │──▶│   PHASE 3    │──▶│   PHASE 4    │──▶│     PHASE 5      │
│  REPRODUCE   │   │  ROOT-CAUSE      │   │  HYPOTHESIS  │   │     FIX      │   │   REGRESSION     │
│              │   │  INVESTIGATE     │   │  TEST        │   │              │   │   VERIFY         │
│ bug-         │   │  root-cause-     │   │ hypothesis-  │   │ fix-applier  │   │ regression-      │
│ reproducer   │   │  investigator    │   │ tester       │   │              │   │ verifier         │
│              │   │                  │   │ (per cand.)  │   │ ONE fix only │   │                  │
└──────────────┘   └──────────────────┘   └──────────────┘   └──────────────┘   └──────────────────┘
       │                    │                    │                   │                     │
       ▼                    ▼                    ▼                   ▼                     ▼
  REPRO.md          ROOT_CAUSE.md         HYPOTHESES.md          (code edits)        REGRESSION.md
                    (or                   (one verified
                     CANDIDATES.md)        as ROOT)
```

### Phase 1 — Reproduce (`bug-reproducer`)

Produces `REPRO.md` with the **smallest reliable reproduction**: exact command / curl call / Playwright snippet / failing test that demonstrates the bug deterministically.

If the bug is intermittent, repro must succeed at least **3/5** runs before moving on. Flaky-but-not-reproducible bugs go into a sidebar log; we do not fix them by guessing.

> ❌ **Gate:** without `REPRO.md`, no other phase runs.

### Phase 2 — Root-cause investigate (`root-cause-investigator`)

Reads `REPRO.md`, the failing code path, related git history (`git log -p --since=14.days`), logs, and recent deployments. Produces either:

- **`ROOT_CAUSE.md`** — when one cause is confidently identified, with evidence (stack trace + the specific lines, log entries, git commits)
- **`CANDIDATES.md`** — when 2+ plausible causes exist; triggers Phase 3

**Memory write:** `memory: project` — the investigator writes its conclusion to project memory so the same investigation isn't redone in a future session.

### Phase 3 — Hypothesis test (`hypothesis-tester`, dispatched per candidate)

For each candidate in `CANDIDATES.md`, dispatch one `hypothesis-tester` in parallel. Each one:
- Designs a **targeted experiment** that would confirm or reject *only* its candidate
- Runs the experiment (toggling code, running a minimal binary search, adding instrumentation)
- Returns `HYPOTHESIS_<n>.md` with `VERDICT: confirmed | rejected | inconclusive`

When exactly one returns `confirmed`, promote it to `ROOT_CAUSE.md` and proceed. If multiple confirm or none, the investigation is incomplete — re-dispatch `root-cause-investigator` with the new evidence.

### Phase 4 — Fix (`fix-applier`)

Reads `ROOT_CAUSE.md`. **Refuses to run** if the file is missing or contains `VERIFIED: false`.

Applies **one fix only** (no opportunistic cleanup, no refactor, no "while I'm here"). Then:
- Re-runs the exact reproduction from `REPRO.md` — must now pass
- Runs the package manager's typecheck (via `<pm>`, auto-detected by hook)
- Runs the closest test pattern (`<pm> test -- <feature>`)

### Phase 5 — Regression verify (`regression-verifier`)

The actual reproduction passing is not enough. Runs:
- Full test suite for the affected workspace
- Playwright smoke test for any route the fix touched (uses the same MCP server as `exploratory-qa`)
- A diff-aware check: every file in `git diff` is examined for behavior changes you didn't intend

Produces `REGRESSION.md`. If anything beyond the targeted bug shifted, re-open Phase 2 with the new evidence.

## Dispatch invocations

> Use these in the main session to drive the pipeline. Each one runs the named agent fresh — no context leakage.

### Phase 1 — reproduce

```
Use the bug-reproducer agent. Failure: <paste user's failure description>.
Exact reproduction command/route: <paste>.
Recent changes the user suspects: <paste git log line or "none">.
Produce REPRO.md per the systematic-debugging skill.
```

### Phase 2 — investigate

```
Use the root-cause-investigator agent.
Inputs: REPRO.md (in the working dir), plus 'git log -p --since=14.days'.
Produce ROOT_CAUSE.md with VERIFIED: true|false, OR CANDIDATES.md if you have 2+
plausible causes. Write your conclusion to project memory.
```

### Phase 3 — test hypotheses in parallel

```
Dispatch <N> hypothesis-tester agents in parallel — one per candidate in
CANDIDATES.md. Each must return HYPOTHESIS_<n>.md with VERDICT: confirmed |
rejected | inconclusive plus the experiment that produced it.
```

### Phase 4 — fix

```
Use the fix-applier agent. ROOT_CAUSE.md MUST exist with VERIFIED: true.
Apply ONE fix. Re-run the REPRO.md reproduction. Confirm it passes.
```

### Phase 5 — verify no regressions

```
Use the regression-verifier agent. Run full test suite for the affected
workspace, Playwright smoke for any touched route, and diff-aware behavior
review. Produce REGRESSION.md.
```

## Agent teams (optional — for ambiguous root causes)

When Phase 2 returns `CANDIDATES.md` with **3+ candidates** that all look equally plausible, run a **competing-hypotheses team** instead of parallel hypothesis-testers.

Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

> *Three teammates each champion one hypothesis. They share an evidence chat — each must attack the others' evidence and defend their own. When two agree, the third's hypothesis is rejected. When all three disagree, the investigation is incomplete and Phase 2 must re-run with new instrumentation.*

The team is dispatched as:

```
Dispatch a 3-teammate competing-hypotheses team.
Teammate A champions candidate 1 (from CANDIDATES.md).
Teammate B champions candidate 2.
Teammate C champions candidate 3.
Each must propose an experiment that would falsify the others' candidates.
Run them. Produce ROOT_CAUSE.md if 2+ teammates converge.
```

This is **~3× the token cost** of single-agent investigation. Use only when the bug is expensive (production outage, repeat regression) and the root cause is genuinely ambiguous.

## Anti-patterns this skill exists to prevent

| 🚫 Anti-pattern | ❓ Why it's wrong | ✅ What this skill does instead |
|---|---|---|
| "Let me try a fix and see if it helps" | You're testing fixes against your gut, not evidence | Fix-applier refuses to run without `ROOT_CAUSE.md` |
| Cleaning up "while I'm in there" | Multiple changes in one commit hide which one fixed what | One fix per `fix-applier` invocation |
| Calling it fixed because the test passes | Tests cover the cases you thought of, not the ones you didn't | Phase 5 regression-verifier checks every touched file for unintended behavior shift |
| Re-debugging the same bug 2 weeks later | The original investigation wasn't persisted | `root-cause-investigator` writes to project memory |
| Adding `try/catch` to make the error go away | Catching the symptom isn't fixing the cause | Investigator's verdict must name a specific defect — "missing index", "race condition", not "exception handling" |

## Reference files

- [`references/phase-checklist.md`](references/phase-checklist.md) — gate criteria per phase
- [`references/repro-recipes.md`](references/repro-recipes.md) — patterns for minimal reproductions (HTTP, Playwright, CLI, async race)
- [`references/instrumentation-tactics.md`](references/instrumentation-tactics.md) — how to add diagnostics without changing behavior
- [`references/agent-definitions.md`](references/agent-definitions.md) — copy-paste dispatch prompts per agent
