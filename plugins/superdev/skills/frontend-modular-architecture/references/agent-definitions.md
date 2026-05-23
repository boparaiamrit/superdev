# frontend-modular-architecture — dispatch reference

## module-structure-auditor

```
Use the module-structure-auditor agent.

Module path: apps/web/src/modules/<feature>/

Audit against the 7 iron laws from frontend-modular-architecture/SKILL.md:
1. Pages ≤ 100 lines
2. Components ≤ 200 lines
3. Shared state → module store (≥ 5 useState in one component = finding)
4. Wizards with ≥ 3 steps split per-step
5. Drawers / modals / popovers in parts/<name>/ folders
6. Pages delegate (no inline columns / form state / business logic)
7. useMemo / useCallback only when needed (≥ 3 in one component = finding)

Produce MODULE_STRUCTURE_AUDIT.md with P1 (block ship) and P2 (fix soon).
Cite file:line for every finding. Suggest the specific fix path per finding.

Write recurring-violation classes to .claude/memory/superdev-learned/structure-violations.md
so future builds avoid them.
```

## portal-correctness-auditor

```
Use the portal-correctness-auditor agent.

Module path: apps/web/src/modules/<feature>/

Scan for:
- Raw <dialog> / absolute-positioned div modals → P1
- fixed-position drawers without shadcn Sheet → P1
- Direct Radix imports inside module code → P2
- parts/<name>/ folders that don't host a Portal primitive → P2

Produce PORTAL_AUDIT.md. For each finding, name the specific shadcn primitive
that should replace it (Dialog, Sheet, Popover, DropdownMenu, ContextMenu,
Tooltip, AlertDialog, Select, HoverCard).

Write recurring-pattern classes to .claude/memory/superdev-learned/portal-violations.md.
```

## Wave-gate (run both auditors after every frontend agent)

After `frontend-module-builder` or `frontend-rewirer` finishes on a module:

```
Dispatch in parallel:
- module-structure-auditor for the just-touched module
- portal-correctness-auditor for the just-touched module

If either returns P1 findings, BLOCK the wave. The orchestrator surfaces the
findings to the user with the suggested fix paths and offers to re-dispatch
the builder/rewirer with the audit findings appended to its prompt.
```

## Agent team — store-design debate (optional)

When a module's state model is non-obvious (e.g. 3+ candidate boundaries between entity / UI / wizard / cache stores), dispatch:

```
Dispatch 3-teammate store-design debate.

Teammate A — minimalist:
  "One store unless the bundle / re-render cost is measurable. Defer separation."

Teammate B — separator:
  "Default to splitting by concern (entity / UI / wizard / prefs). Boundaries
   are clarified upfront, cheaper to maintain at scale."

Teammate C — futurist:
  "Where will this state live in 6 months? Will the wizard ever resume after
   route change? Will the UI store need to persist across sessions?"

Round 1: each proposes a store split + selectors.
Round 2: each critiques the others' (re-render surface area? cross-cutting
         updates? localStorage candidates?).
Majority verdict. Ties go to the separator (the cost of premature split is
lower than the cost of god-store).

Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```
