# Memory entry format

Every entry under `.claude/memory/superdev-learned/` follows this exact format.

## Template

```markdown
---
name: <kebab-case-slug ≤ 50 chars>
description: <single line, ≤ 100 chars — what to do or not do, stated as a rule>
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: <user-correction | git-revert | regression-rejected | drift-failed | audit-pattern | explicit-remember>
  date: <YYYY-MM-DD>
  applies_to_agents:
    - <agent-name>
    - <agent-name>
---

<The rule as a 1–2 sentence directive. Use imperative voice ("Do X" / "Never Y").>

**Why:** <Cite the specific event. Include commit hashes, file:line, agent names. Future readers must understand WHEN the lesson was learned and WHY the failure happened.>

**How to apply:** <When the rule kicks in. Which agent's prompt should include it. The exact phrase the orchestrator should thread into the agent prompt.>

**Related:** [[other-learned-topic-slug]]   ← optional, link to related lessons
```

## Examples

### Drift-triggered (design-fidelity-auditor)

```markdown
---
name: no-restyle-source-buttons
description: Never swap source <button> markup for shadcn <Button> — wrap instead
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: drift-failed
  date: 2026-05-22
  applies_to_agents:
    - frontend-module-builder
    - frontend-rewirer
---

When componentizing the preserved source UI, **wrap source `<button>` markup** with a React component (adding `onClick` props). DO NOT swap to shadcn's `<Button>`.

**Why:** design-fidelity-auditor flagged 8% drift on /companies, /deals, /contacts after frontend-module-builder commits f3a8c2e, 9d1b740, 8e2cc11 replaced source buttons with shadcn. User reverted all three with message "I told you not to change the buttons".

**How to apply:** When design-preservation is active in this project, frontend-module-builder and frontend-rewirer prompts must include: "Source <button> elements must be wrapped (not replaced) — wrap source markup in a React component, add interactivity via props, preserve className verbatim."

**Related:** [[wrap-dont-replace-patterns]]
```

### Audit-pattern-triggered (audit-synthesizer)

```markdown
---
name: aggregate-counts-always-real
description: Aggregate fields (deal_count etc.) MUST be SELECT COUNT — never hardcode 0
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: audit-pattern
  date: 2026-05-22
  applies_to_agents:
    - backend-module-builder
    - contracts-author
---

Any field whose name ends in `_count`, `_total`, `_sum`, or `_avg` MUST be computed via SELECT in the presenter. Hardcoding to 0 is forbidden, even when fixtures show 0.

**Why:** product-completeness-audit on commit a4b7c8d found 3 separate HYBRID screens where counts were hardcoded. backend-module-builder repeatedly skipped the aggregate query "because the demo fixtures had 0 in them". User said "I want real counts everywhere now".

**How to apply:** backend-module-builder prompt must include: "For every contract field matching /^.*(count|total|sum|avg)$/, write a SELECT subquery (COUNT/SUM/AVG with appropriate GROUP BY) in the presenter. Never hardcode."

**Related:** [[data-flow-real-vs-mock]]
```

### User-correction-triggered

```markdown
---
name: do-not-add-error-boundaries-to-list-pages
description: List pages handle errors via TanStack Query's error state — do not wrap in ErrorBoundary
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: user-correction
  date: 2026-05-22
  applies_to_agents:
    - frontend-module-builder
---

Do NOT add `<ErrorBoundary>` wrappers to list pages. They already handle errors via `useQuery`'s `error` return — wrapping them in ErrorBoundary masks the inline error UI we want.

**Why:** Session 2026-05-22 14:32 — user repeatedly removed ErrorBoundary wrappers from /companies, /deals, /contacts after frontend-module-builder added them. Message: "Stop adding error boundaries to lists, the query's error state is what I want shown".

**How to apply:** frontend-module-builder prompt must include: "For list/table pages, rely on TanStack Query's `isError` + `error` for inline error UI. Do NOT add `<ErrorBoundary>` wrappers — they hide the inline state user wants. ErrorBoundary is for app-shell only."
```

## Rules

- **One rule per file.** Two unrelated lessons → two files.
- **The `description` is the most important field** — the orchestrator filters by it. Make it accurate and specific.
- **`applies_to_agents` is critical** — without it, the orchestrator doesn't know which dispatches to thread the lesson into.
- **Update, don't duplicate.** If a similar entry exists, add the new event as more evidence in the existing `**Why:**` section.
