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

**How to apply:** <When the rule kicks in. Which agent's prompt should include it. The exact phrase the main agent should thread into the agent prompt.>

**Related:** [[other-learned-topic-slug]]   ← optional, link to related lessons
```

## Public promotion

Private evidence belongs only in the originating project's memory, with credentials and customer data redacted. Public READMEs, release notes, and plugin guidance contain no real project names, customer domains, local paths, incident dates, private metrics, or commit anecdotes.

For a transferable lesson, publish only:

- the failure mechanism;
- the applicable stack or conditions;
- the corrective action; and
- a reproducible verification check.

## Rules

- **One rule per file.** Two unrelated lessons → two files.
- **The `description` is the most important field** — the main agent filters by it. Make it accurate and specific.
- **`applies_to_agents` is critical** — without it, the main agent doesn't know which dispatches must include the lesson.
- **Update, don't duplicate.** If a similar entry exists, add the new event as more evidence in the existing `**Why:**` section.
