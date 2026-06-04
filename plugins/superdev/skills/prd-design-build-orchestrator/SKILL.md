---
name: prd-design-build-orchestrator
description: Multi-agent orchestration for full-stack monorepo builds. Audits a PRD against a design handoff (HTML, screenshots, claude.ai/design output) to find gaps, writes an execution plan, and dispatches parallel subagents through 4 phases. Coordinates ALL 16 superdev skills — design-preservation (when source is a prototype, not Claude Design), design-to-nextjs (shadcn translation when source is Claude Design), nestjs-enterprise-backend, security-review-and-fix, prototype-to-saas, exploratory-qa, systematic-debugging (on any bug found mid-build), product-completeness-audit (between QA and ship), brutal-exhaustive-audit (final pass before declaring done). Reads `.claude/memory/superdev-learned/` before every subagent dispatch and threads project-specific lessons into agent prompts so the system avoids repeating past mistakes (self-learning loop via superdev-self-learning skill).
---

# PRD ↔ Design Audit + Build Orchestrator

A multi-agent system for converting a PRD + a design handoff into a shipping full-stack monorepo. The orchestrator (the main Claude in Claude Code) does no implementation work itself — it dispatches specialized subagents and coordinates phases.

> 🧠 **Self-learning** — the orchestrator reads `.claude/memory/superdev-learned/` BEFORE every subagent dispatch and threads relevant lessons into agent prompts. The system learns from past mistakes in THIS project. See [`superdev-self-learning`](../../superdev-self-learning/SKILL.md).
>
> 🎨 **Design preservation** — when the user's source is a prototype (not Claude Design output), the orchestrator inserts the [`design-preservation`](../../design-preservation/SKILL.md) Phase B.0 to copy the source verbatim and gate every Phase C wave on a fidelity audit. Pixel drift > 1% blocks the wave.

## Mandatory pre-dispatch checklist (every subagent, every time)

Before dispatching ANY subagent, the orchestrator does:

```bash
# 1. Read learned lessons
ls .claude/memory/superdev-learned/ 2>/dev/null

# 2. For each lesson, check if applies_to_agents includes the about-to-dispatch agent

# 3. Append matched lessons to the agent's prompt under "## Lessons learned in this project"

# 4. Announce to user (first dispatch of the session only):
#    "Found N learned lessons for this project. Threading them into dispatches."
```

See [`superdev-self-learning/references/orchestrator-integration.md`](../../superdev-self-learning/references/orchestrator-integration.md) for the threading template.

## Skill routing — when to delegate to which sibling skill

The orchestrator coordinates 16 skills. Use this table to decide which to invoke and when:

| When… | Invoke skill | Why |
|---|---|---|
| Any frontend module being built | `frontend-modular-architecture` (mandatory rules) + wave-gate `module-structure-auditor` + `portal-correctness-auditor` | Prevent god-files / state soup / flat folders / Portal-less drawers from day 1 |
| Existing fat module needs decomposition (>300 line file, >5 useState, wizard god-file, no stores/) | `frontend-refactoring` (atomic one-module conversion in single commit) | Half-converted modules are worse than untouched ones |
| User has PRD + Claude Design output | `design-to-nextjs` (Phase C, frontend wave) | Translate to shadcn |
| User has PRD + prototype (HTML/Figma/existing app) | `design-preservation` (Phase B.0) THEN `design-to-nextjs` (Phase C, wiring only) | Preserve source verbatim |
| Backend selection gate (Step A.5b) chose **Nest.js** | `nestjs-enterprise-backend` (Phase C, backend wave) | Postgres17+Timescale / Drizzle / Redis+BullMQ / CASL patterns |
| Backend selection gate (Step A.5b) chose **Laravel** | `laravel-enterprise-backend` (Phase C build) + `laravel-bref-deploy` (Phase D ship) | Laravel 13 / CockroachDB (stock pgsql) / DB cache+sessions / SQS / Bref serverless; laravel-data contracts; #[Audit]; global-scope tenancy |
| Laravel backend + **Inertia** frontend (Step A.5c) | `design-to-laravel` (Phase C) + `inertia-module-builder` | Inertia React monolith; Fortify session; hand-written typed props; shadcn starter kit |
| Existing prototype with JSON fixtures to productionize | `prototype-to-saas` + `design-preservation` + `frontend-refactoring` (Phase B.5 — decompose BEFORE rewiring) | Migration + UI preservation + structural decomposition |
| Any bug found mid-build | `systematic-debugging` (interrupt current phase) | Verified-root-cause-before-fix discipline |
| Phase D security pass | `security-review-and-fix` | 6-phase audit |
| Phase D QA pass | `exploratory-qa` | Playwright flows |
| Before declaring "ready to ship" | `product-completeness-audit` (between QA and audit) THEN `brutal-exhaustive-audit` | Distinguishes demo-vs-product, then dots every i |
| User-frustration signal detected OR verifier rejection | `superdev-self-learning` (auto-dispatched by hook) | Capture lesson; future dispatches inherit |

When NOT to invoke a skill:
- ❌ Don't invoke `brutal-exhaustive-audit` for a single-feature edit (it's whole-product)
- ❌ Don't invoke `design-preservation` for Claude Design output (defeats translation purpose)
- ❌ Don't invoke `systematic-debugging` for refactors with no bug to chase
- ❌ Don't invoke `product-completeness-audit` mid-build (run only between QA pass and ship claim)
- ❌ Don't invoke `frontend-refactoring` for multiple modules at once — one module per dispatch, atomic. For N fat modules, run N separate dispatches.
- ❌ Don't dispatch `frontend-rewirer` on files > 300 lines — `frontend-refactoring` must run first (the rewirer itself refuses).

## When to use this skill

Use whenever the user has:

- A PRD (markdown, docx, pdf, or even pasted text) describing a product
- A design handoff (HTML from claude.ai/design, screenshots, a `.zip` bundle, or even just verbal spec)
- The intent to build BOTH a Nest.js backend AND a Next.js frontend in one monorepo

Do NOT use this skill for:

- Single-side builds (frontend-only or backend-only) — invoke `design-to-nextjs` or `nestjs-enterprise-backend` directly
- PRD-without-design (no UI to audit against — write the design first, or skip the audit phase)
- Existing codebases adding a feature — use the per-skill recipes; this is for greenfield orchestration

## How to invoke this skill

This skill is designed for **Claude Code** (the CLI), where it has access to the subagent system. The skill installs 10 specialized subagent definitions into `.claude/agents/` and the main session orchestrates them.

**Three invocation patterns, from least to most opinionated:**

### Pattern 1 — natural language (default, recommended)

After installing the skill, just describe what you want in a normal Claude Code session:

```
I have a PRD at docs/PRD.md and a design handoff bundle at design/.
Build the full-stack app.
```

The main session reads this skill's SKILL.md, runs Phase A.1 to install the subagents into `.claude/agents/`, and then drives the four phases by delegating to subagents through natural language ("Use the prd-analyst subagent to read the PRD and produce PRD_DIGEST.md") or @-mentions (`@"prd-analyst (agent)" read the PRD`).

### Pattern 2 — main session AS the orchestrator (`claude --agent`)

If you want the entire session to behave as the orchestrator (its system prompt replaces the default Claude Code prompt), launch with:

```bash
claude --agent prd-design-build-orchestrator
```

This requires a `prd-design-build-orchestrator.md` agent file at the project or user level. The skill's install step writes one automatically if you opt in (see `references/install-orchestrator-as-agent.sh`).

### Pattern 3 — interactive setup via `/agents`

In an existing session, run `/agents` to open the agent management UI, navigate to the Library tab, and confirm all 10 subagents are present. Use this to inspect or edit agent definitions before kicking off Phase A.

### Optional: agent-teams mode for specific phases

This skill defaults to subagents (stable, lower-cost, results-only). Some phases benefit from **agent teams** — independent Claude sessions that can message each other and be steered individually — particularly the audit phase and feature-by-feature builds. Agent teams are experimental and require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `settings.json` or environment.

See the "Agent teams (optional)" section near the end of this skill for which phases can use teams and how to invoke them. The agent definitions in `.claude/agents/<name>.md` work as both subagent definitions AND teammate types without modification — when the user asks the lead to "spawn a static-auditor teammate," the same definition file applies.

## Cross-cutting conventions enforced by every agent

These conventions span both apps and every feature. The orchestrator surfaces violations during wave gates.

### shadcn/ui is THE component substrate — no other UI libraries

Every visual primitive in the frontend comes from shadcn/ui via `@/components/ui/*`. No Headless UI, no raw Radix imports, no MUI, no Mantine, no Chakra, no Ant Design, no DaisyUI, no Bootstrap, no react-bootstrap, no semantic-ui, no flowbite, no nextui, no tremor. Hand-rolled buttons/inputs/dialogs are also forbidden — if shadcn has it, use shadcn's.

**What this includes:**

- Every form input: `<Input>`, `<Textarea>`, `<Select>`, `<Checkbox>`, `<Switch>`, `<RadioGroup>`, `<Slider>` from `@/components/ui/*`. The form itself uses `<Form>` from shadcn (which wraps react-hook-form).
- Every button: `<Button>` with shadcn's variant API (`variant="default" | "destructive" | "outline" | "secondary" | "ghost" | "link"`).
- Every overlay: `<Dialog>`, `<Sheet>`, `<Drawer>`, `<Popover>`, `<HoverCard>`, `<Tooltip>`, `<AlertDialog>` from shadcn.
- Every table: shadcn's `<Table>` from `@/components/ui/table` (paired with TanStack Table for data plumbing, but the visual primitives are shadcn).
- Every menu: `<DropdownMenu>`, `<ContextMenu>`, `<Menubar>`, `<NavigationMenu>` from shadcn.
- Every list/data display: `<Card>`, `<Badge>`, `<Avatar>`, `<Skeleton>`, `<Separator>`, `<ScrollArea>` from shadcn.
- **Every sidebar uses the shadcn `sidebar` block** (`<Sidebar>`, `<SidebarProvider>`, `<SidebarTrigger>`, `<SidebarMenu>`, `<SidebarMenuItem>`, `<SidebarHeader>`, `<SidebarContent>`, `<SidebarFooter>` from `@/components/ui/sidebar`). No custom drawer/aside layouts.
- Every notification: `<Sonner>` (sonner via shadcn) or shadcn's `<Toast>`.
- Every command palette: shadcn's `<Command>` / `<CommandDialog>`.

**What's allowed alongside shadcn:**

- `lucide-react` icons (shadcn's default icon set)
- TanStack Table, TanStack Query (data plumbing, no visual primitives of their own)
- `react-hook-form` (wired through shadcn's `<Form>`)
- `zod` (validation, no UI)
- `cmdk` (used by shadcn's Command)
- `sonner` (used by shadcn's toast)
- `recharts` for charts (shadcn doesn't ship charts as primitives; the shadcn chart wrapper around recharts is acceptable, otherwise raw recharts)
- Tailwind utility classes for layout, spacing, color application

**Forbidden import paths** (the `ui-auditor` agent enforces this; see below):

```
@radix-ui/*        (use @/components/ui/* — shadcn already wraps Radix correctly)
@headlessui/*
@mui/*
@material-ui/*
@chakra-ui/*
@mantine/*
antd
@ant-design/*
react-bootstrap
bootstrap
semantic-ui-react
flowbite-react
@nextui-org/*
tremor
@tremor/*
daisyui
```

**Setup is owned by `monorepo-bootstrapper`** (Phase B): runs `pnpm dlx shadcn@latest init`, then bulk-adds every primitive plus the `sidebar` block. By the time `frontend-module-builder` runs in Phase C, every primitive is already in `apps/web/src/components/ui/`.

**Enforcement is owned by `ui-auditor`** (Phase C wave gates + Phase D): greps for forbidden import paths, raw `<button>` / `<input>` / `<dialog>` JSX elements where a shadcn equivalent exists, and any local files that re-implement a primitive shadcn already ships.

**The design system flows downstream from this commitment:** token extraction emits shadcn-standard CSS variable names (`--background`, `--foreground`, `--primary`, `--primary-foreground`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring`, `--radius`) in HSL channel form (`222.2 47.4% 11.2%`, not `hsl(...)`); brand-specific extensions (`--brand-50` … `--brand-900`) are layered on top.

### Docker for every infrastructure dependency — no local installs

Every infrastructure service the project needs runs in Docker via a single `docker-compose.yml` at the **monorepo root**. No local Postgres, no Homebrew Redis, no manually-installed Timescale extension. The repo clones, `docker compose up -d` starts the world, the apps connect.

Default services every project gets (set up by `monorepo-bootstrapper` in Phase B):

```yaml
# docker-compose.yml (at monorepo root)
services:
  postgres:
    image: timescale/timescaledb:latest-pg17      # Postgres 17 + Timescale extension
    container_name: <workspace>_postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: <app>_dev
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: <workspace>_redis
    restart: unless-stopped
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    healthcheck:
      test: ["CMD-SHELL", "redis-cli ping | grep PONG"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  postgres_data:
  redis_data:
```

Additional services added when the EXECUTION_PLAN calls for them:

- **`mailpit`** — local SMTP catcher (port 1025 SMTP, 8025 web UI) for any project with email features. CRM/outreach projects always get this.
  ```yaml
  mailpit:
    image: axllent/mailpit:latest
    ports: ["1025:1025", "8025:8025"]
    restart: unless-stopped
  ```
- **`minio`** — S3-compatible object storage for file uploads, CSV imports, generated documents.
  ```yaml
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes: [minio_data:/data]
  ```
- **`adminer`** — lightweight DB UI on port 8080 if the team wants a browser DB explorer (optional, not default).

Rules `monorepo-bootstrapper` and `integration-tester` enforce:

- `docker-compose.yml` lives at the monorepo root, NOT inside `apps/api/`
- Every service has a `healthcheck` block — readiness is provable, not assumed
- Every service binds to `127.0.0.1:<port>:<port>` in production-profile compose files (default file is dev; ports exposed for local tooling)
- Every service has a named volume for persistence — `docker compose down` doesn't lose state; `docker compose down -v` does
- Container names are prefixed with the workspace name (`<workspace>_postgres`, `<workspace>_redis`) so multiple monorepos can run side-by-side
- `.env.example` documents every connection string the apps expect (`DATABASE_URL`, `REDIS_URL`, `SMTP_URL`, etc.)
- A root-level `pnpm dev:infra` script wraps `docker compose up -d` and a `pnpm dev:infra:down` wraps `docker compose down`

**Wave-gate check (every wave in Phase C):**

Before dispatching builders, `monorepo-bootstrapper` (Phase B) and the orchestrator (start of every wave in Phase C) verify:

```bash
docker compose ps --format json | jq -e 'all(.Health == "healthy" or .State == "running")'
```

If any service is unhealthy, builders DO NOT run. The orchestrator surfaces the Docker status to the user, attempts `docker compose up -d` once, re-checks, and if still red, halts with a clear message.

### Title Case for every enum value — DB = wire = UI label

Every enum/status/stage/role/discriminator on the wire uses **Title Case**. The string stored in Postgres equals the string the frontend renders. Zero conversion code.

Concrete examples the agents enforce:

```
Status        → 'Active' | 'Inactive' | 'Pending' | 'Suspended'
Plan          → 'Starter' | 'Growth' | 'Enterprise'
Role          → 'Admin' | 'Operator' | 'Pipeline' | 'Viewer'
Industry      → 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'
Stage         → 'New' | 'Qualified' | 'Proposal Sent' | 'Negotiation' | 'Won' | 'Lost'
Bounce        → 'None' | 'Soft' | 'Hard' | 'Complaint'
Warmup        → 'Not Started' | 'In Progress' | 'Active' | 'Paused' | 'Failed'
Campaign      → 'Draft' | 'Scheduled' | 'Sending' | 'Paused' | 'Completed' | 'Archived'
AuditStatus   → 'Success' | 'Failure'
ActivityKind  → 'None' | 'Email Sent' | 'Email Received' | 'Deal Won' | 'Deal Lost'
GrowthSignal  → 'Growing' | 'Stable' | 'Declining'
```

Rules the agents follow:

- Drizzle `pgEnum` values are Title Case strings (spaces allowed)
- Zod `z.enum([...])` literals in `packages/contracts` are Title Case
- Discriminated-union `kind` fields are Title Case (`{ kind: 'Email Sent', ... }`)
- Numeric ranges (`"1-10"`, `"51-200"`) stay as ranges — not word-based, not converted
- The label-map pattern (`INDUSTRY_LABELS = { tech: 'Technology' }`) is BANNED for simple enums — the value IS the label
- Complex enums keep `{ kind, label }` ONLY when `label` carries computed context (e.g., `growth_signal.label = "+12% YoY"`); `kind` is still Title Case

This convention is enforced in:
- `contracts-author` agent when generating `packages/contracts/src/*.ts`
- `backend-module-builder` when defining Drizzle `pgEnum` values
- `frontend-module-builder` when authoring fixtures and rendering components
- `gap-auditor` flags any PRD or DESIGN_DIGEST enum that uses non-Title-Case strings
- `plan-architect` produces an entity catalog with Title Case enums baked in
- `integration-tester` greps for casing helpers (`capitalize`, `humanize`, `LABELS[`, `toLowerCase`, `toUpperCase`) in component code

## Prerequisites

This skill is the conductor. The two skills it conducts must be installed and available:

- `design-to-nextjs` — frontend recipe
- `nestjs-enterprise-backend` — backend recipe

Verify before starting:

```bash
ls ~/.claude/skills/design-to-nextjs/SKILL.md
ls ~/.claude/skills/nestjs-enterprise-backend/SKILL.md
```

If either is missing, install it before running this orchestrator.

## The four-phase pipeline

```
Phase A: AUDIT        Read-only. Extract from PRD + design, diff them, produce execution plan.
Phase B: BOOTSTRAP    Sequential. Stand up the monorepo + shared contracts.
Phase C: EXECUTE      Parallel per feature module. The speed lever.
Phase D: INTEGRATE    Sequential. Run the cross-cutting validation tests.
```

Phase A ends with a **mandatory user-confirmation gate** — the orchestrator presents the EXECUTION_PLAN.md and waits for explicit approval before any code is written.

## The agent team

Fifteen specialized subagents — ten core (build pipeline) and five security (loaded only if the `security-review-and-fix` skill is installed). Each has a focused role, a restricted tool set, and a single artifact it owns.

### Core agents (always installed)

| Agent | Phase | Tools | Owns artifact |
|---|---|---|---|
| `prd-analyst` | A | Read, Grep, Glob | `PRD_DIGEST.md` |
| `design-inventory` | A | Read, Glob, Bash, WebFetch | `DESIGN_DIGEST.md` |
| `gap-auditor` | A | Read, Write | `AUDIT.md` |
| `plan-architect` | A | Read, Write | `EXECUTION_PLAN.md` |
| `monorepo-bootstrapper` | B | Read, Write, Edit, Bash | `apps/{api,web}` scaffold, `packages/*`, root `docker-compose.yml`, shadcn install |
| `contracts-author` | B | Read, Write | `packages/contracts/src/*.ts` |
| `backend-module-builder` | C | Read, Write, Edit, Bash | `apps/api/src/modules/<feature>/*` |
| `frontend-module-builder` | C | Read, Write, Edit, Bash | `apps/web/src/modules/<feature>/*` and fixtures |
| `ui-auditor` | C (wave gates) + D | Read, Glob, Grep, Bash | UI compliance report (`UI_AUDIT.md` if violations found) |
| `integration-tester` | D | Read, Bash | functional test report |

### Security agents (installed only if `security-review-and-fix` skill is present)

| Agent | Phase | Tools | Owns artifact |
|---|---|---|---|
| `security-inventory` | D.2.1 | Read, Glob, Grep, Bash | `SECURITY_INVENTORY.md` |
| `static-auditor` | D.2.2 | Read, Glob, Grep, Bash | findings → `SECURITY_FINDINGS.md` (prefix `S-S-`) |
| `dynamic-auditor` | D.2.3 | Read, Bash | findings → `SECURITY_FINDINGS.md` (prefix `S-D-`) |
| `dependency-auditor` | D.2.4 | Read, Bash | findings → `SECURITY_FINDINGS.md` (prefix `S-P-`) |
| `security-fixer` | D.2.6 | Read, Write, Edit, Bash | targeted code edits per `SECURITY_FIX_PLAN.md` |

### QA agents (installed only if `exploratory-qa` skill is present)

| Agent | Phase | Tools | Owns artifact |
|---|---|---|---|
| `qa-environment` | D.3.1 | Read, Glob, Bash | seed data + baselines + `QA_ENVIRONMENT.md` |
| `qa-flow-tester` | D.3.2, D.3.3 | Read, Bash, Glob, Grep | `qa/flows/<feature>/` screenshots + traces + `observations.md` |
| `qa-consistency-checker` | D.3.4 | Read, Glob, Grep, Bash | `QA_CONSISTENCY.md` + `qa/consistency/` |
| `qa-performance-prober` | D.3.5 | Read, Bash | `QA_PERFORMANCE.md` + `qa/performance/` |

Full core-agent definitions live in `references/agent-definitions.md`. Full security-agent definitions live in the `security-review-and-fix` skill's `references/security-agents.md`. Full QA-agent definitions live in the `exploratory-qa` skill's `references/qa-agents.md`. The orchestrator's install step (Phase A.1) reads from each file when the relevant skill is detected.

## Phase A — AUDIT

**Goal:** produce an EXECUTION_PLAN.md that lists every feature module to build, what each module needs (contracts, schemas, endpoints, screens), what the PRD/design disagree on, and what order to build in.

### Step A.1 — Install agents

Before any subagent runs, the orchestrator copies all agent definitions into `.claude/agents/`. Always install the ten core agents from this skill. **Also install the five security agents if and only if the `security-review-and-fix` skill is present** (so Phase D.2 can dispatch them), and **the four QA agents if and only if the `exploratory-qa` skill is present** (so Phase D.3 can dispatch them).

```bash
mkdir -p .claude/agents

# 1) Install core agents from this skill
~/.claude/skills/prd-design-build-orchestrator/references/install-core-agents.sh

# 2) Conditionally install security agents
if [[ -f ~/.claude/skills/security-review-and-fix/references/security-agents.md ]]; then
  ~/.claude/skills/security-review-and-fix/references/install-security-agents.sh
  echo "Security skill detected — security agents installed; Phase D.2 will run."
else
  echo "Security skill not detected — Phase D.2 will be skipped with a warning."
fi

# 3) Conditionally install exploratory QA agents
if [[ -f ~/.claude/skills/exploratory-qa/references/qa-agents.md ]]; then
  ~/.claude/skills/exploratory-qa/references/install-qa-agents.sh
  echo "Exploratory QA skill detected — QA agents installed; Phase D.3 will run."
else
  echo "Exploratory QA skill not detected — Phase D.3 will be skipped with a warning."
fi

ls .claude/agents/
# Expected counts:
#  - 10 core agents always
#  - 15 with security skill installed
#  - 14 with QA skill installed
#  - 19 with both security and QA skills installed
```

> **Backend stack note:** `backend-module-builder` (Nest.js) and `laravel-module-builder` (Laravel) are both auto-discovered plugin agents. The orchestrator dispatches whichever matches the `backend_stack` chosen at Step A.5b; the other simply goes unused. No conditional install step is needed — they ship with the plugin.

The full install scripts (with the awk-based extraction) live in:
- `references/agent-definitions.md` of this skill (core agents)
- `references/security-agents.md` of the `security-review-and-fix` skill (security agents)
- `references/qa-agents.md` of the `exploratory-qa` skill (QA agents)

Run once at project start.

### Step A.2 — Parallel inventory

The orchestrator (main session) dispatches `prd-analyst` and `design-inventory` **in parallel** — both via the `Agent` tool in a single tool-use batch. In natural language:

> "Use the prd-analyst subagent to read the PRD at `<path>` and produce PRD_DIGEST.md per the format in references/artifacts-format.md. In parallel, use the design-inventory subagent to inventory the design at `<path>` and produce DESIGN_DIGEST.md per the format in references/artifacts-format.md."

Claude Code emits both as `Agent` tool calls in one batch; they run concurrently with independent contexts. Wait for both to complete before advancing.

> **Note on tool naming:** In Claude Code v2.1.63+, the tool for spawning subagents is named `Agent`. The previous name `Task` still works as an alias. The legacy `Task(subagent_type='X', prompt='Y')` shorthand used in older docs is equivalent to invoking `Agent` with the same parameters.

### Step A.3 — Audit

The orchestrator dispatches `gap-auditor`:

> "Use the gap-auditor subagent to read PRD_DIGEST.md and DESIGN_DIGEST.md and produce AUDIT.md."

The audit categorizes gaps as: `missing-from-design`, `missing-from-prd`, `type-mismatch`, `naming-drift`, `scope-creep`. See `references/audit-pipeline.md`.

**Optional: agent-teams mode for the audit.** For PRDs where the design diverges substantially or the cost of missed gaps is high, the gap audit benefits from adversarial review. If `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set, instead of dispatching a single `gap-auditor` subagent, ask the orchestrator:

> "Spawn an agent team with three teammates using the gap-auditor agent type as a base: one PRD advocate (arguing the PRD is the source of truth), one design advocate (arguing the design is), and one neutral arbiter. Have them debate the gaps and produce AUDIT.md by consensus. Require the arbiter to sign off on each gap classification."

Token cost is roughly 3× the subagent path; recommended only for high-stakes audits.

### Step A.4 — Plan

The orchestrator dispatches `plan-architect`:

> "Use the plan-architect subagent to read PRD_DIGEST.md, DESIGN_DIGEST.md, and AUDIT.md, then produce EXECUTION_PLAN.md with build order, dependencies, and parallelizable lanes."

### Step A.5 — User-confirmation gate

The orchestrator reads EXECUTION_PLAN.md, summarizes:
- N features to build, grouped by parallel lane
- Resolved gaps (PRD-only and design-only items now have decisions)
- Estimated wave count (waves are batches of parallel feature builds)

Show this to the user. **Do not proceed without explicit confirmation.** If the user wants to revise (drop a feature, change an entity name, etc.), edit AUDIT.md and rerun `plan-architect`.

### Step A.5b — Backend-stack selection gate

If `EXECUTION_PLAN.md` contains backend modules, the orchestrator asks the operator — **before Phase B** — which backend stack to build, using `AskUserQuestion`:

> **Backend stack?**
> - **Nest.js** — Postgres 17 + TimescaleDB + Drizzle + Redis/BullMQ + CASL (`nestjs-enterprise-backend`)
> - **Laravel** — Laravel 13 + CockroachDB (stock `pgsql`) + database cache/sessions + SQS, deployed via Bref (`laravel-enterprise-backend` + `laravel-bref-deploy`)

Persist the answer to `STACK.md` and a `backend_stack:` field in `EXECUTION_PLAN.md` so every later phase — and any resume — reads the same value. **All backend routing in Phases B/C/D below is conditioned on `backend_stack`.** When the backend is **Nest.js**, the frontend is always Next.js and the frontend half (design-to-nextjs, frontend-modular-architecture, QA/security/audit) is unaffected. When the backend is **Laravel**, the frontend stack is chosen separately at **Step A.5c** (Inertia monolith vs decoupled Next.js).

The agents this gate re-routes:
- `monorepo-bootstrapper` (B.1) — Nest scaffold vs Laravel scaffold (see its stack-aware section).
- `contracts-author` (B.2) — hand-authored Zod vs `spatie/laravel-data` classes emitted to TS.
- backend module builder (C.2) — `backend-module-builder` (Nest) vs `laravel-module-builder` (Laravel).
- Phase D ship — add `laravel-bref-deploy` when the stack is Laravel.

### Step A.5c — Frontend-stack selection gate (Laravel only)

If `backend_stack == Laravel` AND the plan has frontend modules, the orchestrator asks — **before Phase B** — which frontend to build, using `AskUserQuestion`:

> **Frontend for the Laravel backend?**
> - **Inertia monolith (default)** — one Laravel app, React via Inertia (`design-to-laravel`); Fortify session auth; one Bref deploy.
> - **Decoupled Next.js** — separate `apps/web` (`design-to-nextjs`); Sanctum token auth; Laravel API + Next.js.

Persist `frontend_stack` to `STACK.md` / `EXECUTION_PLAN.md`. Routing when `frontend_stack == Inertia`:
- **bootstrap:** a single Laravel app via the React starter kit (frontend in `resources/js/`; no `apps/web`, no pnpm web package) — see `monorepo-bootstrapper`.
- **auth:** **Fortify session + `spatie/laravel-permission`** (see `laravel-enterprise-backend/references/inertia-variant.md`), NOT Sanctum tokens.
- **frontend builder (C.2):** `inertia-module-builder` (not `frontend-module-builder`).
- **contracts:** hand-written typed props in `resources/js/types/` — no `packages/contracts`, no `laravel-data`→TS.
- **deploy (Phase D):** `laravel-bref-deploy` single-app Inertia flow (Vite `npm run build`, assets → S3/CloudFront, client-only).

When `frontend_stack == Next.js` (with Laravel), use the decoupled path exactly as the backend-stack gate describes. When `backend_stack == Nest.js`, this gate does not run (frontend is always Next.js).

## Phase B — BOOTSTRAP

**Goal:** monorepo skeleton + shared contracts in place, ready for parallel feature builds.

### Step B.1 — Monorepo bootstrap

Dispatch `monorepo-bootstrapper`:

> "Use the monorepo-bootstrapper subagent to read EXECUTION_PLAN.md, then scaffold the pnpm workspace per nestjs-enterprise-backend/references/monorepo-setup.md, scaffold apps/api per nestjs-enterprise-backend/references/scaffolding.md, and scaffold apps/web per design-to-nextjs/references/scaffolding.md. Stop after pnpm install + first health check pass."

**If `backend_stack == Laravel`** (Step A.5b): instead scaffold `apps/api` as a Laravel 13 app per `laravel-enterprise-backend/references/scaffolding.md` + `monorepo-setup.md` (composer, Laravel Boost, stock `pgsql`/CockroachDB, database cache/session tables, single-node CockroachDB compose for local), and `packages/contracts` is populated by `php artisan typescript:transform` rather than hand-authored Zod. See the stack-aware section in the `monorepo-bootstrapper` agent definition.

This is sequential and foundational — it must finish before contracts-author runs.

### Step B.2 — Author all contracts up front

The orchestrator dispatches `contracts-author`:

> "Use the contracts-author subagent to read EXECUTION_PLAN.md and, for each feature module, author the Zod schemas in `packages/contracts/src/<feature>.ts` following the view-shape contract in nestjs-enterprise-backend/references/view-presenter.md and the contracts patterns in nestjs-enterprise-backend/references/monorepo-setup.md."

**If `backend_stack == Laravel`** (Step A.5b): `contracts-author` instead authors `spatie/laravel-data` classes under `apps/api/app/Domains/<feature>/Data/` per `laravel-enterprise-backend/references/laravel-data-contracts.md`, then runs `php artisan typescript:transform` to emit the TS types into `packages/contracts/src/generated.ts`. It does NOT hand-author Zod. See the stack-aware section in the `contracts-author` agent definition.

Why all contracts up front? Because module builders in Phase C depend on `@<scope>/contracts` (Nest) / the generated TS contracts (Laravel) being complete. If contracts are written piecemeal alongside modules, the backend builder for module X can race the contracts for module Y.

After contracts-author finishes, run `pnpm --filter @<scope>/contracts build` (Nest) or confirm `php artisan typescript:transform` produced `packages/contracts/src/generated.ts` (Laravel) before parallel builders depend on it.

## Phase C — EXECUTE (the parallel phase)

**Goal:** all feature modules built, in both backend and frontend, as fast as possible.

> **Important architectural note:** Subagents cannot spawn other subagents. The orchestrator (the main session running this skill) is the ONLY entity that dispatches subagents. Every wave dispatch, every wave-gate check, every retry is initiated by the main session. Builder subagents return results and stop; they do not chain.

### Step C.1 — Read the lanes

EXECUTION_PLAN.md groups features into parallel **waves**. A wave is a batch of features that can be built concurrently because they have no inter-feature dependencies.

Example wave structure for an <APP_NAME>-like product:

```
Wave 1: auth, workspaces                          (foundation — everyone depends on these)
Wave 2: companies, contacts, mailboxes            (parallel — no deps between)
Wave 3: campaigns, pipeline                       (depend on Wave 2)
Wave 4: ai, email, webhooks                       (depend on campaigns/pipeline)
Wave 5: analytics, audit                          (read-side, depend on everything)
```

### Step C.2 — For each wave, the orchestrator dispatches builders in parallel

For each feature in the current wave, the orchestrator emits BOTH a backend builder AND a frontend builder in the same tool-use batch. **The backend builder is `backend-module-builder` when `backend_stack == Nest.js`, or `laravel-module-builder` when `backend_stack == Laravel`** (Step A.5b); the frontend builder is unchanged. In natural language to the main session:

> "For Wave 2, dispatch six subagents in parallel: a backend-module-builder for companies, a frontend-module-builder for companies, a backend-module-builder for contacts, a frontend-module-builder for contacts, a backend-module-builder for mailboxes, a frontend-module-builder for mailboxes. Each gets the prompt 'Build the <feature> module per EXECUTION_PLAN.md feature: <feature>.' Wait for all to complete before advancing."

Claude Code translates this into six `Agent` tool calls in a single batch. They run concurrently with independent contexts. Wait for all six to complete before moving to the next wave.

**Optional: agent-teams mode for pair-programming within a feature.** For features where backend↔frontend contract negotiation is likely (e.g., a complex pipeline module where stages, scoring, and view shapes are still in flux), the user can ask the orchestrator to spawn each feature as a 2-teammate agent team instead of two independent subagents. Teammates can message each other ("frontend: I need `lead.score.label` in the view shape" → "backend: adding to presenter"). Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Token cost is roughly 1.5× the subagent path because teammates share more context. Recommended only for features flagged in EXECUTION_PLAN.md as having unresolved contract questions.

### Step C.3 — Wave gate (orchestrator-driven)

After each wave, the orchestrator (not the builders) runs:

1. `pnpm --filter @<scope>/api typecheck` and `pnpm --filter @<scope>/web typecheck` — catch contract drift early
2. The full wave gate procedure in `references/execution-pipeline.md` (Docker health, lint, fixture validation, unit tests, UI audit)
3. If failures, the orchestrator dispatches a focused fixer subagent on the failing module (`backend-module-builder` or `frontend-module-builder` with a "fix the typecheck errors in module X" prompt)
4. Only advance to the next wave when all checks are green

The orchestrator can also wire `PostToolUse` hooks in `.claude/settings.json` to run typecheck automatically after every builder's `Write` or `Edit` finishes — see "Hook-driven wave gates" in `references/execution-pipeline.md`.

### Step C.4 — Parallelism budget

Claude Code allows multiple `Agent` tool calls per turn, but each subagent consumes context and compute. Rules:

- **Cap concurrent subagents at 6** per tool-use batch. For waves with >3 features, the orchestrator runs two backend builders + one frontend builder, then the rest in a follow-up call.
- **Same wave, same call** — never split a wave across multiple tool calls unless you hit the cap. The wave boundary is the synchronization point.
- **Independent waves can pipeline**, but only if Wave N has no dependencies on Wave N-1's output. Default: don't pipeline; wait.

See `references/execution-pipeline.md` for batching details.

## Phase D — INTEGRATE

**Goal:** prove the assembled system works end-to-end, and run a security audit before release.

### Step D.1 — Run integration tests

The orchestrator dispatches `integration-tester`:

> "Use the integration-tester subagent to run the full validation checklist: cross-workspace isolation test, CASL ability test (per role), audit decorator test (every mutation produces audit_logs row), view-shape contract test (no undefined in any view response), demo mode fixture validation, production mode boot. Report results."

### Step D.2 — Security review (if `security-review-and-fix` skill is installed)

If the `security-review-and-fix` skill is available (verified at Step A.1), the orchestrator runs its six-phase audit. The five security agents are already in `.claude/agents/`, so the orchestrator dispatches them directly — do not start a separate orchestration session.

**D.2.1 — Inventory (sequential, foundational):**

The orchestrator dispatches:

> "Use the security-inventory subagent to inventory the codebase per `~/.claude/skills/security-review-and-fix/references/inventory-checklist.md` and produce SECURITY_INVENTORY.md."

Wait for completion.

**D.2.2–D.2.4 — Static + Dynamic + Dependency audit (parallel, one tool-use batch):**

These three share no inputs; they all append to `SECURITY_FINDINGS.md` using disjoint ID prefixes (`S-S-*`, `S-D-*`, `S-P-*`), so race-safe. The orchestrator dispatches all three in a single batch:

> "Dispatch three subagents in parallel:
> 1. Use the static-auditor subagent to run the full static audit per static-audit-checklist.md, read SECURITY_INVENTORY.md for context, and append findings to SECURITY_FINDINGS.md with prefix `S-S-`.
> 2. Use the dynamic-auditor subagent to verify the stack is up (docker compose ps + curl /readiness), then run probes per dynamic-audit-checklist.md and append findings with prefix `S-D-`.
> 3. Use the dependency-auditor subagent to run pnpm audit and lockfile checks per dependency-audit-checklist.md and append findings with prefix `S-P-`."

Wait for all three.

**Optional: agent-teams mode for the audit phase.** Security audits are a strong fit for the "competing hypotheses" pattern. Instead of three independent subagents, three teammates that can challenge each other's findings often surface more issues. If `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`:

> "Spawn a 3-teammate agent team using the static-auditor, dynamic-auditor, and dependency-auditor agent types as bases. Have them debate findings as they go (a static-flagged SQL injection should be cross-checked against the dependency auditor's CVE database; a dynamic auditor's CSRF observation should be validated against static analysis of the upstream middleware). Each teammate's findings are challenged before being recorded. Produce SECURITY_FINDINGS.md by consensus."

The user can directly message any auditor mid-investigation via Shift+Down. Recommended for pre-launch audits and post-incident reviews. The `security-inventory` and `security-fixer` agents remain subagents in both modes.

**D.2.5 — Triage (orchestrator + user, no subagent):**

The orchestrator reads `SECURITY_FINDINGS.md`, walks the user through Critical → High → Medium following the triage prompts in `~/.claude/skills/security-review-and-fix/references/fix-plan-format.md`, and writes `SECURITY_FIX_PLAN.md`. **This is not a subagent dispatch** — it's interactive with the user.

**D.2.6 — Apply fixes (per-fix dispatches):**

For each fix item in `SECURITY_FIX_PLAN.md` that has `Agent: security-fixer`, the orchestrator dispatches one subagent per fix (never batch):

> "Use the security-fixer subagent to apply fix F-2 per SECURITY_FIX_PLAN.md. Edit only the files listed in that entry. Run pnpm typecheck and the relevant tests. Re-grep for the original anti-pattern to confirm it is gone. Return per the format in security-agents.md."

Run sequentially through the Critical/High fixes. Same-module Mediums can batch into a single dispatch only when the plan explicitly lists them as a group.

**D.2.7 — Re-audit:**

After all fixes applied, re-run the three auditors in parallel (same prompts as D.2.2–D.2.4). Append a "RE-AUDIT" section to `SECURITY_FINDINGS.md`. The originally-flagged patterns should no longer match; any that do represent incomplete fixes and trigger another fix pass (max 2 re-audit cycles before escalating to user).

**Halt conditions for D.2:**

- **Critical findings unresolved after Phase D.2.7** → halt; do not produce the final report. Surface `SECURITY_FIX_PLAN.md` with the unresolved items to the user.
- **High findings with explicit user deferrals** → record in the final report's "accepted risks" section.
- **Medium/Low/Info** → record as recommendations in the final report.

If the security skill is not installed (Step A.1 didn't install the security agents), skip D.2 entirely and add to the final report: "⚠ Pre-launch security review was not performed. Install the `security-review-and-fix` skill and re-run before production deployment."

### Step D.3 — Exploratory QA (if `exploratory-qa` skill is installed)

If the `exploratory-qa` skill is available, run it after security passes. Exploratory QA finds the issues that automated tests systematically miss (missing empty states, button-size drift across modules, frozen frames on large data, refactor candidates) — different category from functional regressions and security.

Install the QA agents if not already done (Phase A.1 should have detected and installed them):

```bash
if [[ ! -f .claude/agents/qa-flow-tester.md ]]; then
  ~/.claude/skills/exploratory-qa/references/install-qa-agents.sh
fi
```

Then run the six-phase QA pipeline. Same dispatch pattern as the security skill — agents are local to the project's `.claude/agents/`, the orchestrator drives them.

**D.3.1 — Environment (sequential):**

The orchestrator dispatches:

> "Use the qa-environment subagent to verify stack health, seed at realistic scale per `~/.claude/skills/exploratory-qa/references/environment-checklist.md`, capture baseline screenshots, plant edge-case fixtures, and capture test credentials. Produce QA_ENVIRONMENT.md."

**D.3.2 — Happy path (parallel per feature, batched at 6):**

The orchestrator dispatches one qa-flow-tester per feature in a single tool-use batch (capped at 6):

> "Dispatch six qa-flow-tester subagents in parallel, each scoped to one feature module (companies, contacts, mailboxes, campaigns, pipeline, mailboxes), mode happy-path, following the recipes in flow-recipes.md. Each writes to `qa/flows/<feature>/happy-path/`."

For projects with more than 6 features, run in successive batches; do not exceed 6 concurrent subagents per tool-use turn.

**D.3.3 — Edge cases (parallel per feature, same batching):**

The orchestrator dispatches:

> "Dispatch qa-flow-tester subagents in parallel (max 6 per batch), each scoped to one feature, mode edge-cases. Cover all 13 categories: empty-state, loading-state, error-state, large-data, slow-network, validation-errors, concurrent-mutation, stale-data, long-content, special-characters, keyboard-nav, mobile, accessibility."

**D.3.4 — Consistency (single subagent, runs after flows finish):**

> "Use the qa-consistency-checker subagent to audit cross-module consistency per consistency-checklist.md. Read all `qa/flows/*/observations.md` and the frontend source. Produce QA_CONSISTENCY.md."

**D.3.5 — Performance (single subagent, runs LAST with idle system):**

> "Use the qa-performance-prober subagent to measure Web Vitals per route, database query counts per action, frontend data-volume freezes, bundle sizes, worker latency, and memory growth. Run only after all flow-testers complete and the system is idle. Produce QA_PERFORMANCE.md."

**Optional: agent-teams mode for adversarial report synthesis.** Phase D.3.6 (final QA report synthesis) can run as a 3-teammate agent team that debates severity assignment before writing the report. Useful when the report drives launch/no-launch decisions. If `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`:

> "Spawn a 3-teammate agent team for the QA synthesis: a harshest-critic teammate pushing for higher severities, a pragmatist teammate pushing back, and a shipping-advocate teammate arguing what genuinely blocks launch. Have them debate each finding's severity. Produce QA_REPORT.md by consensus."

**Optional: competing-hypotheses team for hard performance issues.** When qa-performance-prober flags an issue with multiple plausible causes (e.g., "companies list LCP 3.8s — could be N+1, bundle size, or unindexed query"), the orchestrator can on-demand spawn a 3-teammate investigation team (one investigator per hypothesis) that messages each other to disprove competing theories. Same pattern as the docs' "scientific debate" example.

**D.3.6 — Synthesis (orchestrator, no subagent):**

The orchestrator reads `QA_ENVIRONMENT.md`, all `qa/flows/*/observations.md`, `QA_CONSISTENCY.md`, `QA_PERFORMANCE.md` and writes `QA_REPORT.md` per `~/.claude/skills/exploratory-qa/references/qa-report-format.md`.

**Halt conditions for D.3:**

- **Critical findings unresolved** → halt; surface `QA_REPORT.md` to the user before producing the orchestrator's final report.
- **High findings need explicit user acknowledgment** in the final report's "accepted risks" section.
- **Medium/Low/Refactor** are recorded as recommendations.

If the QA skill is not installed, skip D.3 with: "⚠ Exploratory QA was not performed. Install the `exploratory-qa` skill and re-run for a production-readiness pass."

### Step D.4 — Final report

The orchestrator collects:

- Wave-by-wave build status (from Phase C)
- Test report (from `integration-tester`)
- Security review summary (from D.2, if performed)
- Any unresolved audit findings (from `AUDIT.md`)
- Files created / lines of code summary

Present to the user. Done.

## Reference files

| File | When to read |
|---|---|
| `references/orchestration-patterns.md` | Before any subagent dispatch — the Task tool + parallelism rules |
| `references/audit-pipeline.md` | Phase A — what each audit agent does and how findings are categorized |
| `references/execution-pipeline.md` | Phase C — wave construction, batching, error handling |
| `references/artifacts-format.md` | Reading or writing PRD_DIGEST / DESIGN_DIGEST / AUDIT / EXECUTION_PLAN |
| `references/agent-definitions.md` | Phase A.1 — install agents to `.claude/agents/`. Source-of-truth for every subagent. |

## Validation checklist

Before declaring the build done:

- [ ] `.claude/agents/` contains all 10 core agent definitions
- [ ] If security skill is installed, `.claude/agents/` also contains the 5 security agents (15 total)
- [ ] If exploratory-qa skill is installed, `.claude/agents/` also contains the 4 QA agents (14 with QA only; 19 with security and QA)
- [ ] `PRD_DIGEST.md`, `DESIGN_DIGEST.md`, `AUDIT.md`, `EXECUTION_PLAN.md` exist at project root
- [ ] If security skill ran in D.2: `SECURITY_INVENTORY.md`, `SECURITY_FINDINGS.md`, `SECURITY_FIX_PLAN.md` exist; zero unresolved Critical findings
- [ ] If QA skill ran in D.3: `QA_ENVIRONMENT.md`, `QA_CONSISTENCY.md`, `QA_PERFORMANCE.md`, `QA_REPORT.md` exist; zero unresolved Critical QA findings
- [ ] User confirmed EXECUTION_PLAN.md before Phase B started
- [ ] **`docker-compose.yml` exists at the monorepo root** (not inside `apps/api/`)
- [ ] **`docker compose up -d` brings every service to `healthy` state** (postgres, redis, and any plan-specific extras)
- [ ] **No infrastructure dependency is installed locally** — Postgres, Redis, Timescale, SMTP, S3 all run in Docker
- [ ] Root `package.json` has `dev:infra`, `dev:infra:down`, `dev:infra:reset`, `dev:infra:logs` scripts
- [ ] Root `.env.example` documents every Docker-service connection string
- [ ] **shadcn/ui initialized in `apps/web` with all primitives installed** (`components.json` present, `src/components/ui/` populated, sidebar block installed)
- [ ] **`ui-auditor` ran clean at the final wave gate** — no forbidden UI library imports, no raw `<button>`/`<input>`/`<dialog>` JSX where shadcn equivalent exists, every sidebar uses shadcn's sidebar block
- [ ] `pnpm install` succeeds at the monorepo root
- [ ] `pnpm --filter @<scope>/contracts build` succeeds
- [ ] `pnpm turbo build` succeeds across all packages
- [ ] `pnpm turbo typecheck` is green
- [ ] `pnpm turbo lint` is zero-warning
- [ ] All integration tests from Phase D pass
- [ ] **Title Case enum sweep clean** — `grep -rEn "(capitalize|humanize|\\.toLowerCase\\(\\)|\\.toUpperCase\\(\\)|_LABELS\\[|LABELS\\[)" apps/web/src/modules` returns zero hits on contract-typed data; every Drizzle `pgEnum` uses Title Case values
- [ ] Final report has zero unresolved blocking audit findings
- [ ] No agent definition was loaded that wasn't in the install list (no rogue agents)

## Common pitfalls

**P1 — Skipping the user-confirmation gate.** The orchestrator must show EXECUTION_PLAN.md and wait for explicit "yes, proceed". A subtly wrong plan costs hours of wasted parallel builds.

**P2 — Authoring contracts inside the module builders.** Then two features race on `packages/contracts`. Always do all contracts in Phase B.2.

**P3 — Pipelining waves.** Tempting for speed; lethal for correctness when Wave N depends on Wave N-1's types. Default: wait at wave boundaries.

**P4 — Letting subagents talk to each other.** They can't. State lives on disk. If two agents need to coordinate, that's a sign the orchestrator should split the work differently.

**P5 — Giving every agent every tool.** A read-only agent (e.g. `prd-analyst`) given Write/Bash will sometimes "helpfully" create files prematurely. Restrict tools per agent.

**P6 — One mega-prompt to one mega-agent.** That's not multi-agent; that's a long-context single agent. The win comes from specialization + parallel execution, not from delegation alone.

**P7 — Trusting agent self-reports.** A `backend-module-builder` may report "done" with a broken typecheck. Always run the wave-gate typecheck (Step C.3) before advancing.

**P8 — Forgetting the design-to-nextjs / nestjs-enterprise-backend skill references.** The builders need them. Verify the skills are installed at Phase A start.
