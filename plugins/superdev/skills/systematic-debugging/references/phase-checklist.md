# Systematic debugging — gate criteria per phase

Each phase gates the next. If you cannot tick every checkbox, you do not advance — you re-dispatch the previous agent with the new evidence.

## Phase 1 — Reproduce

- [ ] `REPRO.md` exists in the working dir
- [ ] Reproduction command is a single shell line OR a Playwright snippet under 30 lines
- [ ] Reproduction succeeded **at least 3 of 5 runs** if the bug is intermittent
- [ ] Reproduction was demonstrated against the **current `HEAD`** (not stale code)
- [ ] Expected output / observed output are both captured verbatim
- [ ] No environment-specific magic: if the repro needs a specific DB row or session, it's seeded in the snippet

❌ **Do not advance** if the bug only reproduces "sometimes" and you have not characterized when.

## Phase 2 — Root-cause investigate

- [ ] `ROOT_CAUSE.md` OR `CANDIDATES.md` exists
- [ ] Every claim cites either a file:line, a log entry, or a git commit
- [ ] The defect class is named explicitly (race condition / missing index / type coercion / off-by-one / etc.) — not "weird behavior"
- [ ] If `ROOT_CAUSE.md`: contains `VERIFIED: true` AND an experiment that would falsify it (so reviewers can re-check)
- [ ] If `CANDIDATES.md`: at least 2 candidates, each with its own falsifiable experiment design
- [ ] Investigator wrote conclusion to project memory (so future sessions don't re-investigate)

❌ **Do not advance to fix** unless `VERIFIED: true`.

## Phase 3 — Hypothesis test (only when CANDIDATES.md was produced)

- [ ] One `hypothesis-tester` dispatched **per candidate**, in parallel
- [ ] Each returned `HYPOTHESIS_<n>.md` with `VERDICT: confirmed | rejected | inconclusive`
- [ ] Exactly **one** candidate is `confirmed`
  - If zero confirmed → re-dispatch `root-cause-investigator` with new evidence
  - If multiple confirmed → the candidates were not mutually exclusive; redesign experiments
- [ ] Promote the confirmed hypothesis to `ROOT_CAUSE.md` with `VERIFIED: true`

## Phase 4 — Fix

- [ ] `ROOT_CAUSE.md` present with `VERIFIED: true` (refuse to run otherwise)
- [ ] Exactly **one** logical change committed (no opportunistic cleanup)
- [ ] Reproduction from `REPRO.md` now passes against the fixed code
- [ ] `<pm> typecheck` for the affected workspace is clean
- [ ] The closest test pattern (`<pm> test -- <feature>`) passes
- [ ] No new files outside the workspace the bug lives in

❌ **Do not advance** if the typecheck failed — the fix is wrong or incomplete.

## Phase 5 — Regression verify

- [ ] Full test suite for the affected workspace passes
- [ ] For every route the fix touched: Playwright smoke test passes (uses `exploratory-qa`'s MCP server)
- [ ] Diff-aware behavior review: every line in `git diff` is explained — "this changed because…"
- [ ] `REGRESSION.md` produced, listing every check and its result

❌ **Re-open Phase 2** if any check finds behavior shifted in a file you didn't intend to touch.
