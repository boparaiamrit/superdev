# Artifact Formats

The four artifacts that Phase A produces. These are the message bus — subagents communicate by writing and reading these files. Strict formats prevent drift.

## PRD_DIGEST.md

Owned by `prd-analyst`. Read by `gap-auditor` and `plan-architect`.

```markdown
# PRD Digest

> Source: <path/to/PRD>
> Generated: <ISO 8601>

## Product summary

<one paragraph describing what the product is and who it's for>

## Personas

| Persona | Role | Primary tasks |
|---|---|---|
| <name> | <admin/operator/...> | <bullet list> |

## Features

| ID | Name | Description | Source (PRD section) |
|---|---|---|---|
| F-1 | auth | Login, signup, password reset, JWT issuance | §1.1 |
| F-2 | companies | Company CRUD, custom fields, headcount tracking | §2.1 |
| ... | | | |

## Entities

For each entity:

### Company

- **Identifies as:** company / business / organization (synonyms used in PRD)
- **Fields per PRD:**
  - `name: string` (required) — §2.1
  - `domain: string | null` — §2.1
  - `industry: enum` — §2.1, values: [technology, healthcare, finance, logistics, other]
  - `headcount: number` — §2.1
  - `headcount_12mo_ago: number | null` — implied by §2.3 ("show YoY change")
- **Relationships:**
  - Belongs to: Workspace (1:N)
  - Has many: Contact (1:N), Campaign (1:N), Lead (1:N)
- **Hypertable signal:** No (CRUD frequency suggests regular table)

### EmailSent (event log)

- **Fields per PRD:**
  - `workspace_id, mailbox_id, draft_id, contact_id, message_id, sent_at, ...`
- **Relationships:** read-only event; references many entities
- **Hypertable signal:** YES — PRD §4.2 mentions "track every sent email for analytics", expected volume "hundreds of thousands per workspace per month"

(repeat for each entity)

## Screens

| ID | Name | Route suggestion | Auth | Primary entity | PRD section |
|---|---|---|---|---|---|
| S-1 | Login | /login | public | User | §1.1 |
| S-2 | Companies list | /companies | authed | Company | §2.1 |
| S-3 | Company detail | /companies/[id] | authed | Company | §2.2 |
| ... | | | | | |

## External integrations

| Integration | Auth model | Endpoints used | PRD section |
|---|---|---|---|
| InboxKit | Bearer + X-Workspace-Id | /v1/api/* (~70 endpoints) | §4.1 |
| Gmail API | OAuth 2.0 | messages.send, messages.list, ... | §4.2 |
| Anthropic Claude | API key | /v1/messages | §5.1 |

## Non-functional requirements

- **Performance:** p95 < 300ms for list views; p99 < 1s — §6.1
- **Scale:** 10k workspaces, 1M companies, 10M contacts total — §6.2
- **Compliance:** SOC2 Type II; audit log retention 1 year — §6.3
- **Multi-tenancy:** workspace-scoped data isolation, hard requirement — §1.4

## QUESTIONS

Issues for human resolution (block plan-architect):

- Q1: PRD §3.2 mentions "team accounts" but §1.4 says "single user per workspace." Are sub-users supported in v1?
- Q2: §4.1 references "InboxKit warmup" without defining what happens when a mailbox fails warmup. Hard fail? Soft warn?
- Q3: §5.1 says "AI composes email" but doesn't specify whether the user reviews before send. Auto-send or draft-first?

## NOTES

Anything the analyst observed that's not a field but a flag:

- PRD uses "lead" and "prospect" interchangeably — flag for naming-drift in audit
- Several screens are described in §2 but a "templates" feature is in §3 with no corresponding screens — note for cross-check with design
```

## DESIGN_DIGEST.md

Owned by `design-inventory`. Read by `gap-auditor` and `plan-architect`.

```markdown
# Design Digest

> Source: <path/to/design>
> Generated: <ISO 8601>

## Source bundle

- Files: <list>
- Total screens: <count>
- Total components observed: <count>
- Tokens extracted to: design-tokens.json (if applicable)

## Screens

For each screen (one HTML file = one screen typically):

### S-D-1 — Companies list (`companies.html`)

- **Route guess:** /companies
- **Layout:** sidebar nav + main content + right detail panel
- **Primary content:** data table with the following columns:
  - Company name (sortable)
  - Industry (filterable)
  - Headcount with +X% YoY indicator
  - Last activity (relative time, e.g. "2h ago")
  - Open leads (badge count)
  - Action menu (view, edit, delete)
- **Empty state:** present — "No companies yet" with CTA "Add company"
- **Loading state:** skeleton rows
- **Error state:** not shown
- **Actions visible:** + Add Company button (top right), bulk-select checkbox in header
- **Pagination:** numbered pages, 20 per page visible

### S-D-2 — Company detail (`company-detail.html`)

(repeat structure)

## Components (reusable)

| Pattern | Locations seen | Anatomy |
|---|---|---|
| DataTable | companies, contacts, campaigns | header row, sortable, row hover, action menu |
| StatCard | dashboard, company detail | label, value, delta with arrow icon |
| ActivityFeed | company detail, contact detail | timeline with icons per event type |
| ChipFilter | every list screen | rounded pill with × to remove |

## Forms

For each form:

### New Company form (`company-new.html`)

- Fields:
  - `name` — text input, required indicator
  - `domain` — text input, optional, with "auto-detect industry" link
  - `industry` — select dropdown, options: Technology / Healthcare / Finance / Logistics / Other
- Submit: "Create company" primary button
- Cancel: "Cancel" ghost button
- No multi-step indicator

## Navigation

- **Top bar:** workspace switcher, search, notifications, user menu
- **Sidebar (top to bottom):**
  - Dashboard
  - Companies
  - Contacts
  - Campaigns
  - Pipeline
  - Inbox
  - Settings
- **Sidebar bottom:** Templates (NEW)

## Design tokens

- **Colors:**
  - primary: #6366F1
  - primary-foreground: #FFFFFF
  - bg: #FAFAFA
  - bg-elevated: #FFFFFF
  - border: #E5E7EB
  - text-primary: #111827
  - text-muted: #6B7280
  - success: #10B981
  - warning: #F59E0B
  - danger: #EF4444
- **Typography:**
  - Sans: Inter, system-ui
  - Display sizes: 36px / 30px / 24px (h1 / h2 / h3)
  - Body: 14px line-height 20px
- **Radii:** 4px / 8px / 12px / full
- **Spacing scale:** Tailwind default
- **Shadow:** subtle 0 1px 2px / medium 0 4px 6px / overlay 0 12px 24px

## Implicit data shapes

For each computed field shown in the design:

- **"+12% YoY"** (on Company list, headcount column)
  - Implies: headcount delta vs. 12 months ago, formatted as signed percent
  - Backend must compute and label

- **"2h ago"** (on Company list, last activity column)
  - Implies: timestamp + relative format
  - Could be backend-formatted (preferred per view-shape contract) OR frontend-formatted with a `date-fns` helper

- **"Growing" pill with green dot** (on Company detail)
  - Implies: derived state from headcount delta
  - Backend should return: `{ kind: 'Growing' | 'Stable' | 'Declining', label: string }`

## States NOT covered

- Loading states for forms (only success/error)
- Server-error toast layout (designs only show inline form errors)
- Empty state for templates (templates list isn't in design)

## NOTES

- Sidebar shows "Templates" — not mentioned in PRD. Flag for audit.
- Several forms lack explicit validation rules; assume Zod schemas will be the source of truth.
- Dark mode: no toggle visible in design.
```

## AUDIT.md

Owned by `gap-auditor`. Read by `plan-architect`. **The DECISIONS section is written by the user** (or the orchestrator, on the user's explicit instructions).

```markdown
# Audit — PRD vs Design

> Generated: <ISO 8601>
> Sources: PRD_DIGEST.md, DESIGN_DIGEST.md

## Summary

- **Total findings:** 24
- **Blockers:** 3
- **Warnings:** 11
- **Info:** 10

## Findings

### Blockers (must resolve before planning)

#### A-1 [blocker / type-mismatch] — Headcount delta shape

- **PRD:** `headcount: number` (single field)
- **Design:** shows current count + "+12% YoY" delta + "Growing" pill
- **Implication:** view shape must include current, prior, delta_pct, growth_signal (with `kind` + `label`)
- **Recommendation:** contract field `headcount: { current, twelve_months_ago, delta_pct, growth_signal: { kind, label } }`

#### A-2 [blocker / missing-from-prd] — Templates feature

- **Design:** has a "Templates" sidebar entry and (implied) Templates list
- **PRD:** no mention of templates
- **Recommendation:** user decides — add to PRD with shape, or remove from design

#### A-3 [blocker / type-mismatch] — Last activity field

- **PRD:** `last_active_at: timestamp` (a single date)
- **Design:** shows activity type icon ("email sent", "deal won") with contextual label
- **Implication:** discriminated union with kind + at + label
- **Recommendation:** `last_activity: { kind: 'None' | 'Email Sent' | 'Email Received' | 'Deal Won', at, label, ... }`

### Warnings (proceed with default if not addressed)

#### A-4 [warn / missing-from-design] — Audit log viewer

(... details ...)

#### A-5 [warn / naming-drift] — "Lead" vs "Prospect"

- **PRD:** uses both terms; appears synonymous
- **Design:** uses only "Lead"
- **Recommendation:** canonical name is `lead`; update PRD_DIGEST notes

(... more warnings ...)

### Info (default decisions)

(... low-impact items ...)

## DECISIONS

> This section is owned by the human user.
> Each entry overrides the auditor's recommendation.
> plan-architect reads only this section; the findings above are advisory.

- **A-1:** Accept recommendation — view shape `{ current, twelve_months_ago, delta_pct, growth_signal }`
- **A-2:** Defer Templates to v2 — remove from DESIGN_DIGEST navigation entry
- **A-3:** Accept recommendation — discriminated union for last_activity
- **A-4:** Build audit log viewer in v1 — add module `audit-viewer`
- **A-5:** Canonical name: `lead` everywhere
- **A-7:** ... (etc., for every warn/blocker the user reviews)
```

## EXECUTION_PLAN.md

Owned by `plan-architect`. Read by every Phase B/C/D agent.

```markdown
# Execution Plan

> Generated: <ISO 8601>
> Source artifacts: PRD_DIGEST.md, DESIGN_DIGEST.md, AUDIT.md

## Module list (final)

| ID | Module | Type | Owner-app | Notes |
|---|---|---|---|---|
| M-1 | auth | Foundation | api + web | JWT + CASL setup; affects every other module |
| M-2 | workspaces | Foundation | api + web | Workspace switcher in web; tenancy in api |
| M-3 | companies | Domain | api + web | Rich view shape per A-1 decision |
| M-4 | contacts | Domain | api + web | |
| M-5 | mailboxes | Domain | api + web | InboxKit integration |
| M-6 | campaigns | Domain | api + web | Depends on companies + contacts + mailboxes |
| M-7 | pipeline | Domain | api + web | Leads + Deals; depends on companies + contacts |
| M-8 | email | Engine | api | Send + receive engine; depends on mailboxes + campaigns |
| M-9 | ai | Engine | api | Claude composer; depends on campaigns |
| M-10 | webhooks | Integration | api | InboxKit + provider webhooks |
| M-11 | analytics | Read-side | api + web | Reads from hypertables |
| M-12 | audit | Cross-cutting | api + web | @Audit decorator infra + viewer (per A-4) |

## Entity catalog

For each entity:

### Company (regular table)

- Fields (per A-1 resolved):
  - `id, workspace_id, name, domain, industry, size_bucket, headcount_current, headcount_12mo_ago, growth_signal, custom_fields, created_at, updated_at`
- View shape (built by CompaniesPresenter):
  - `id, name, domain, industry, size_bucket,`
  - `headcount: { current, twelve_months_ago, delta_pct, growth_signal: { kind, label } },`
  - `counts: { contacts, open_leads, won_deals },`
  - `last_activity: discriminated union,`
  - `created_at, updated_at`
- Indexes: `(workspace_id, created_at)`, `(workspace_id, industry)`, unique `(workspace_id, domain)`

### EmailSent (HYPERTABLE)

- Primary key includes `sent_at` (Timescale requirement)
- Chunk interval: 7 days
- Compression after 30 days, retention 2 years
- Continuous aggregate: `daily_send_metrics` (per workspace, per mailbox)

(repeat for each entity)

## Build waves

```
Wave 1 (parallel): auth, workspaces
  ↳ Foundation. Everything else depends on these.

Wave 2 (parallel): companies, contacts, mailboxes
  ↳ Independent domain entities. No inter-feature deps.

Wave 3 (parallel): campaigns, pipeline
  ↳ Depend on Wave 2 entities.

Wave 4 (parallel): email, ai, webhooks
  ↳ Depend on campaigns + mailboxes.

Wave 5 (parallel): analytics, audit
  ↳ Read-side. Depend on hypertables populated by earlier waves.
```

**Total: 5 waves, 12 features, 24 builder dispatches.**

## CASL ability map

| Subject | manage | read | create | update | delete | send | export |
|---|---|---|---|---|---|---|---|
| Workspace | ADMIN | all | — | ADMIN | — | — | — |
| Company | ADMIN | all | ADMIN, OPERATOR | ADMIN, OPERATOR | ADMIN | — | ADMIN |
| Campaign | ADMIN | all | ADMIN, OPERATOR | ADMIN, OPERATOR | ADMIN | ADMIN, OPERATOR | ADMIN |
| Lead | ADMIN | all | ADMIN, OPERATOR, PIPELINE | ADMIN, OPERATOR, PIPELINE | ADMIN | — | — |
| ... | | | | | | | |

## Queues + crons

| Queue | Producer | Consumer | Concurrency | Rate limit |
|---|---|---|---|---|
| email-send | campaigns.send() | EmailSendWorker | 5 | per-mailbox token bucket |
| ai-generate | campaigns.composeDraft() | AiGenerateWorker | 3 | per-workspace 10/min |
| audit-write | @Audit interceptor | AuditWriterProcessor | 10 | none |
| import-csv | imports.upload() | ImportWorker | 2 | none |
| webhook-dispatch | webhooks.publish() | WebhookDispatchWorker | 10 | none |

| Cron | Schedule | Job |
|---|---|---|
| warmup-status-poll | */5 * * * * | poll InboxKit warmup status |
| daily-rollup | 0 2 * * * | rollup yesterday's send metrics |
| sla-warning-leads | 0 * * * * | flag stale leads |
| dns-health-check | */30 * * * * | check domain health |
| cleanup-drafts | 0 3 * * * | delete drafts > 30 days old |

## External integrations

| Integration | Auth | Module | Webhook path |
|---|---|---|---|
| InboxKit | Bearer + X-Workspace-Id header | mailboxes | /v1/webhooks/inboxkit |
| Gmail API | OAuth (per user) | email | n/a |
| Microsoft Graph | OAuth (per user) | email | n/a |
| Anthropic Claude | API key | ai | n/a |

## Open items (mid-build escalations)

These are decisions deferred to mid-build:

- O-1: After Wave 3, decide whether to deploy AI behind a feature flag or always-on.
- O-2: After Wave 4, decide on webhook signature verification approach (HMAC vs JWT).

These do NOT block any wave; they're checklist items at the wave boundary.

## Acceptance criteria

The build is complete when:

- All 12 modules in the table above are built
- Wave gates all green
- Phase D integration tests all pass
- The user runs `pnpm dev` and `pnpm worker:dev` in two terminals and both boot cleanly
- The demo-mode frontend renders every screen with realistic fixture data
- The production-mode frontend (pointed at the running backend) renders the same data from live API
```

## Format discipline

Every artifact MUST:

- Have a generated-by line at the top (which agent + ISO timestamp)
- Be valid Markdown — parseable by every agent that reads it
- Use stable IDs (F-1, S-1, A-1, M-1) so cross-references survive edits
- Survive the orchestrator's prompt-construction (no markdown that breaks code blocks when quoted)
- **Use Title Case for every enum value mentioned.** Statuses, stages, roles, industries, discriminator `kind` fields — all Title Case (with spaces allowed: `"In Progress"`, `"Proposal Sent"`, `"Email Sent"`). Numeric ranges (`"1-10"`, `"51-200"`) stay as ranges. If a digest or audit finding shows a non-Title-Case value, the agent that produced it is wrong; rerun it.

If an agent has reason to deviate, it adds a `## DEVIATIONS` section at the bottom explaining why. Subsequent agents read that section first.

## Anti-patterns

- ❌ Sneaking architectural decisions into PRD_DIGEST. That's plan-architect's job.
- ❌ Sneaking implementation details into DESIGN_DIGEST. ("Use a Tailwind grid here" — no.)
- ❌ AUDIT.md without a DECISIONS section. The user can't navigate findings without one.
- ❌ EXECUTION_PLAN with hand-wavy waves ("Wave 2: most things"). Each wave lists exact features.
- ❌ Mixing artifacts. One file per artifact, exclusively owned, no exceptions.
