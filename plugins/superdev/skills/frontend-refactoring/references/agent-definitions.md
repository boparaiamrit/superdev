# frontend-refactoring — dispatch reference

The five-phase pipeline. Each agent's dispatch prompt below.

## Phase 1 — module-conversion-planner

```
Use the module-conversion-planner agent.

Module to convert: apps/web/src/modules/<feature>/

Inputs:
- MODULE_STRUCTURE_AUDIT.md (if present — use as starting checklist)
- The full source of every file in the module
- The target structure from frontend-modular-architecture/references/folder-structure.md
- The plan format from frontend-refactoring/references/conversion-plan-format.md

Produce CONVERSION_PLAN.md following the format EXACTLY. Refuse vague entries.
Map every useState to a target store property. List every Portal extraction.
Enumerate every external consumer's import that needs updating.

Mark STATUS: DRAFT. The user/orchestrator changes to STATUS: APPROVED after
Phase 2 review.

Memory: write the conversion strategy summary to
.claude/memory/superdev-learned/conversion-patterns.md.
```

## Phase 2 — review gate

Option A — user reviews directly:

```
Read CONVERSION_PLAN.md aloud. After user reads and approves, change the
STATUS: line from DRAFT to APPROVED.
```

Option B — 3-teammate completeness review (requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`):

```
Dispatch 3-teammate plan-completeness review.

Teammate A — pessimist: "What did this plan FORGET? Is every useState
  accounted for? Is every external consumer's import listed? Is there a
  Portal extraction missing? A wizard step not split?"

Teammate B — pragmatist: "Is every proposed split actually warranted, or
  is this over-engineering? Would a smaller plan also satisfy the iron laws?"

Teammate C — surgeon: "Walk the atomic-execute order mentally. At step 6
  (pages depending on components), would TypeScript pass? At step 9
  (deletes), are all external imports updated?"

Round 1: each lists concerns
Round 2: each verifies the others' concerns
Verdict requires majority approve. Specific revisions go back to the planner.
```

Plan becomes APPROVED only after both human + (optional) team confirm.

## Phase 3 — module-behavior-snapshotter

```
Use the module-behavior-snapshotter agent.

Module: apps/web/src/modules/<feature>/
Routes: <list from CONVERSION_PLAN.md>
Stack must be running in production-build mode (<pm> build && <pm> start).

Capture for every route × viewport:
- Screenshot (full page)
- DOM snapshot (main content)
- Computed styles of drawer/modal/popover/table elements
- Network HAR
- Console logs

Capture every flow listed in CONVERSION_PLAN.md's "Behavior preservation
contract" section, including drawer open/close, modal confirm flows,
every wizard step.

Output: baseline/<feature>/ directory + BEHAVIOR_BASELINE.md summary.
```

## Phase 4 — atomic-module-converter

```
Use the atomic-module-converter agent.

Pre-flight gates:
- CONVERSION_PLAN.md exists with STATUS: APPROVED
- baseline/<feature>/ exists
- Working tree clean
- Not on main/master/production branch

Execute the plan's "Atomic-execute order" EXACTLY. Single commit on a
new branch refactor/<feature>-decompose. Run typecheck before committing —
if it fails, git reset --hard to the pre-conversion SHA and surface to
user. Do NOT attempt mid-conversion fixes.
```

## Phase 5 — conversion-verifier

```
Use the conversion-verifier agent.

Inputs:
- baseline/<feature>/ (from Phase 3)
- BEHAVIOR_BASELINE.md
- The commit on refactor/<feature>-decompose

Re-run the same Playwright snapshot against the converted module. Diff
every artifact against baseline. Zero-behavior-change required:
- Screenshots: ≤ 0.5% pixel drift per route × viewport
- DOM: identical text content; tag-name diffs only at documented Portal
  extraction sites
- Network: identical request shapes
- Console: zero new errors / warnings
- Interaction traces: identical state transitions

Also run portal-correctness-auditor on the converted module — must return
zero P1 findings.

On PASS: produce CONVERSION_VERIFIED.md, leave branch ready for user merge.
On REJECT: save evidence to .conversion-rejected-<ts>/, git reset --hard to
pre-conversion SHA, delete the refactor branch, return list of specific
divergences for the planner's next attempt.
```

## Full-pipeline dispatch (one command, all 5 phases)

When the orchestrator wants the whole flow:

```
Run the frontend-refactoring skill on the <feature> module.

1. Dispatch module-conversion-planner. Wait for CONVERSION_PLAN.md.
2. Present plan to user. Pause for "approve" / "revise <feedback>".
3. On approve: change STATUS to APPROVED. Dispatch module-behavior-snapshotter.
4. Dispatch atomic-module-converter.
5. Dispatch conversion-verifier.
6. On verifier PASS: announce branch ready to merge. On REJECT: surface
   divergences and ask user whether to re-plan or abandon.

At every phase boundary, write a project memory entry recording success/
failure patterns so future conversions in this project benefit.
```

## Agent team option — plan-completeness review (Phase 2)

```
Dispatch when CONVERSION_PLAN.md is unusually large (>500 lines plan body)
or the module is high-stakes (>1500 source lines, >5 wizard steps,
>3 Portal extractions).

Three teammates as defined in Phase 2 option B. Majority verdict before
APPROVED.

Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```
