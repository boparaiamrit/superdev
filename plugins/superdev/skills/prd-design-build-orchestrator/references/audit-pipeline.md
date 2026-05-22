# Audit Pipeline (Phase A)

How the orchestrator extracts structured intent from a PRD and a design, diffs them, and produces an execution plan.

## The Phase A dataflow

```
  PRD source                Design source
       │                          │
       ▼                          ▼
┌─────────────────┐      ┌──────────────────┐
│  prd-analyst    │      │ design-inventory │      ← parallel
└─────────────────┘      └──────────────────┘
       │                          │
       ▼                          ▼
   PRD_DIGEST.md           DESIGN_DIGEST.md
       │                          │
       └────────────┬─────────────┘
                    ▼
            ┌───────────────┐
            │  gap-auditor  │
            └───────────────┘
                    │
                    ▼
                AUDIT.md
                    │
                    ▼
            ┌────────────────┐
            │ plan-architect │
            └────────────────┘
                    │
                    ▼
             EXECUTION_PLAN.md  →  user-confirmation gate
```

## prd-analyst

**Role:** extract structured intent from the PRD. Read-only. No architectural decisions.

**Inputs:**

- Path to the PRD: a `.md`, `.docx`, `.pdf`, `.txt` file or a folder containing several
- For `.docx` / `.pdf`: the orchestrator should pre-extract to markdown (use the `docx` or `pdf` skill) and point the analyst at the extracted markdown. The analyst itself has only Read/Grep/Glob.

**Outputs to PRD_DIGEST.md:**

- **Product summary** — one paragraph
- **Target users / personas** — list with roles and key tasks
- **Features** — list of feature names with brief descriptions. These will become Nest.js feature modules.
- **Entities** — list of domain entities (Company, Contact, Campaign, ...) with:
  - Required fields per the PRD
  - Relationships (1:1, 1:N, M:N)
  - Whether the PRD implies high write volume / time-series (candidate for hypertable)
- **Screens** — list of screens with route suggestions, auth requirements, primary entity
- **External integrations** — third-party APIs with auth model and known endpoints
- **NFRs** — non-functional requirements (performance targets, scale assumptions, compliance)
- **QUESTIONS** — anywhere the PRD is unclear, contradictory, or silent on a critical decision

What the analyst should NOT do:

- Decide which features get hypertables (record the signal; let `plan-architect` decide)
- Decide module boundaries (the PRD's feature list is the input, not the final modules)
- Invent fields not in the PRD (if PRD says "company has a name", don't add `industry` unless the PRD says so)

## design-inventory

**Role:** catalog what the design actually shows. Read-only.

**Inputs:**

- Path to the design: HTML file, folder with HTML + screenshots, `.zip` archive, or a hosted URL
- For `.zip`: the agent has Bash and can unzip; for hosted URLs, it has WebFetch

**Outputs to DESIGN_DIGEST.md:**

- **Screens** — every screen with its filename / route, brief description, primary action
- **Components** — reusable UI patterns (cards, tables, forms, dialogs, navs)
- **Tables** — every data table with columns, sort/filter affordances, row actions, pagination shape
- **Forms** — every form with fields, validation hints, submit action
- **Navigation** — sidebar / topbar structure, route tree
- **Design tokens** — colors, typography, spacing, radii, shadows (extracted from CSS)
- **States visible** — empty, loading, error, success — note which ones the design covers and which it omits
- **Implicit data shapes** — for every field shown, what type/shape it implies (e.g., "growth: +12% YoY" implies a numeric delta with a label)

What the inventory should NOT do:

- Invent screens the design doesn't show
- Speculate about backend behavior
- Make design judgments ("this is ugly") — purely descriptive

## gap-auditor

**Role:** diff PRD_DIGEST.md against DESIGN_DIGEST.md and write the gap report.

**Inputs:** both digests.

**Outputs to AUDIT.md:**

Findings categorized by type. Each finding has: ID, category, severity (blocker / warn / info), description, recommendation.

### Categories

**`missing-from-design`** — PRD mentions it, design doesn't show it.

Example:
```
Finding A-1 [warn]: PRD §3.4 "Audit log read API" — no screen in design covers
  audit log viewing. Recommendation: add an /audit-logs admin route during planning,
  or descope from v1.
```

**`missing-from-prd`** — Design shows it, PRD doesn't describe it.

Example:
```
Finding A-7 [warn]: Design includes a "Templates" sidebar item with a Templates
  list screen, but PRD does not mention templates. Recommendation: confirm with
  user whether templates are in scope, then add to PRD_DIGEST or remove from
  DESIGN_DIGEST.
```

**`type-mismatch`** — Both have it, but they disagree on shape.

Example:
```
Finding A-12 [blocker]: PRD §2.1 says Company has "headcount: number". Design
  shows "+12% YoY" alongside headcount, implying a delta calculation. The view
  needs current + 12-months-ago + delta. Recommendation: contracts must include
  a structured headcount object: { current, twelve_months_ago, delta_pct,
  growth_signal: { kind, label } }.
```

**`naming-drift`** — Both have it but use different names.

Example:
```
Finding A-18 [info]: PRD calls it "lead pipeline"; design labels it
  "Sales pipeline". Recommendation: pick one canonical name. Suggested:
  "pipeline" for the feature module, "Sales Pipeline" for the UI label.
```

**`scope-creep`** — Design or PRD includes a feature that's clearly v2.

Example:
```
Finding A-22 [info]: Design shows an "AI Insights" panel on the company detail
  screen. PRD §1.3 explicitly defers AI features to v2. Recommendation: hide
  the panel behind a feature flag for v1.
```

### Severity

- **blocker** — execution cannot start until the user resolves it (typically type-mismatches on contracts)
- **warn** — execution can proceed if the user explicitly accepts the gap (typically missing-from-X with a clear default)
- **info** — record-keeping; safe to proceed with the recommended default

### Resolution loop

The orchestrator must present blocker findings to the user before running `plan-architect`. The user can:

1. Edit PRD_DIGEST.md or DESIGN_DIGEST.md to align
2. Accept the auditor's recommendation
3. Override with a different decision (record in AUDIT.md's "DECISIONS" section)

After resolutions, AUDIT.md's "DECISIONS" section is the source of truth for `plan-architect`.

## plan-architect

**Role:** synthesize the digests + audit into an executable plan. The plan is what the rest of the orchestration acts on.

**Inputs:** PRD_DIGEST.md, DESIGN_DIGEST.md, AUDIT.md (including DECISIONS section).

**Outputs to EXECUTION_PLAN.md:**

- **Module list** — final list of feature modules (consolidated from PRD features and design screens)
- **Entity catalog** — for each entity: regular table or hypertable, key fields, view shape proposal
- **Module dependencies** — which modules depend on which (companies → contacts → campaigns, etc.)
- **Build waves** — ordered batches of features that can be built in parallel
- **CASL ability map** — subject + action + role matrix
- **Queues + crons** — async work cataloged from PRD + design implications
- **External integrations** — auth model, webhook handlers needed
- **Open items** — anything not decided that needs user input mid-build

See `references/artifacts-format.md` for the exact template.

The plan-architect is the **only** Phase A agent that makes design decisions. The previous three agents extract; this one decides.

### Wave construction rules

A feature module belongs in **Wave N** if:

- All its dependencies are in waves 1..N-1
- It has no dependency on any other feature in Wave N

Foundation features (`auth`, `workspaces`) usually form Wave 1 alone — everything else depends on them.

Read-side features (`analytics`, `audit-log-viewer`) usually form the last wave — they depend on every entity that produces events.

Aim for **wide waves** (more parallelism) but never sacrifice correctness — a feature that touches Wave-N-1 code should wait, not race.

## Outputs of Phase A

After all four agents complete, the project root contains:

```
PRD_DIGEST.md         ← prd-analyst
DESIGN_DIGEST.md      ← design-inventory
AUDIT.md              ← gap-auditor + user-edited DECISIONS section
EXECUTION_PLAN.md     ← plan-architect (source of truth for Phases B–D)
```

The orchestrator reads EXECUTION_PLAN.md and summarizes for the user-confirmation gate. The summary should include:

- N modules to build, grouped by wave
- M blocker findings, all resolved (or escalate any unresolved ones)
- Approximate wave count + builder count = (waves × features-per-wave × 2)
- Estimated parallelism (max concurrent builders per wave)

Wait for explicit "yes, proceed." Then Phase B begins.

## Anti-patterns

- ❌ Letting `prd-analyst` make architecture decisions. Its job is extraction.
- ❌ Letting `design-inventory` invent screens. Stick to what's visible.
- ❌ Auditor producing only "warn" / "info" — missing blockers means the contract drifts.
- ❌ Skipping the user-confirmation gate. Worth saying twice.
- ❌ Plan-architect ignoring AUDIT.md DECISIONS. Those overrides are how the user shapes the build.
- ❌ Building waves around alphabetical order instead of dependencies.
