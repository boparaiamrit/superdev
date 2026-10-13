---
name: superdev-self-learning
description: Capture hard lessons from corrections, reverts, verifier rejections, and runtime-check failures as structured feedback entries in the target project's `.claude/memory/superdev-learned/`, and read them once at the start of a build (and before dispatching an agent the lesson names). Manual and deliberate — there are no frustration-detection hooks. Invoke when the user corrects superdev's approach, reverts its code, a verifier rejects work, or the user says "remember this". Stack-general lessons belong in the superdev-build hard-rules, not siloed in one project.
---

# SuperDev Self-Learning — lessons, written down once

When a correction or failed verification reveals an actionable rule, write it deliberately to project-local memory. Read relevant lessons **once at build start**, and before a dispatch explicitly named by a lesson. Keep the evidence local and redact credentials and customer payloads.

## The rule

```
A REAL FAILURE BECOMES A WRITTEN LESSON, OR IT WILL HAPPEN AGAIN.
PROJECT LESSONS LIVE IN .claude/memory/superdev-learned/.
TRANSFERABLE RULES MAY BE PROMOTED TO superdev-build/references/hard-rules.md.
PRIVATE PROVENANCE STAYS IN PROJECT-LOCAL MEMORY.
```

Before promotion, identify the failure mechanism, applicable conditions, corrective action, and reproducible check. Public READMEs, release notes, and bundled guidance must contain no real project names, customer domains, local paths, incident dates, private metrics, commit anecdotes, or copied customer evidence. Preserve those details only in the originating project's memory when needed, with secrets and personal data redacted.

## When to write a lesson

- The user corrects an approach, not just a detail ("don't do X here", repeated correction, sharp dissatisfaction) — see [`references/frustration-patterns.md`](references/frustration-patterns.md) for the signal list. Normal iteration ("change the color to blue") is not a lesson.
- The user reverts generated code.
- A verifier/auditor rejects work (`regression-verifier` REJECT, design drift FAIL, completeness audit finds mocked data) or a runtime check (dist boot, browser smoke, side-effect probe) catches what tests missed.
- A fixing agent returns a `LESSON:` line (see `fix-applier`).
- The user says "remember that…", "learn from this", "from now on, always…".

Do NOT write lessons for bugs in user-written code, correct refusals, or one-off typos with no transferable pattern. False positives cost every future reader tokens; when unsure, don't write.

## Entry format

One file per lesson at `.claude/memory/superdev-learned/<topic>.md` in the **target project** (never in the plugin repo itself):

```markdown
---
name: <kebab-case-topic>
description: <one line: what to do / not do>
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: <user-correction | git-revert | verifier-rejected | runtime-check | audit-pattern>
  date: <YYYY-MM-DD>
  applies_to_agents: [<agent names this lesson must reach, if dispatched>]
---

<The rule>

**Why:** <the concrete failure and redacted local evidence; never credentials or customer payloads>

**How to apply:** <when/where the rule kicks in; the exact check that proves compliance>

**Related:** [[other-topic]] (if applicable)
```

Full template and field rules: [`references/memory-entry-format.md`](references/memory-entry-format.md). To synthesize an entry from a messy correction sequence, dispatch the `learn-from-frustration` agent with the raw evidence (dispatch prompt: [`references/agent-definitions.md`](references/agent-definitions.md)), or write the entry directly when the lesson is already crisp — most are.

## How lessons get used

1. **Build start:** `superdev-build` Step 0 — the main agent skims `.claude/memory/superdev-learned/` once and keeps relevant constraints in working memory for the build.
2. **Before a named dispatch:** if an entry's `applies_to_agents` includes the agent about to be dispatched, append the entry (rule + why) to its prompt under `## Lessons learned in this project`.
3. **Promotion:** propose the generic rule, applicable scope, corrective action, and verification check for [`../superdev-build/references/hard-rules.md`](../superdev-build/references/hard-rules.md). Keep project/date provenance local; do not copy it into the plugin, public documentation, package, or release notes. Do not write global/personal memory without an explicit user instruction.

## Reference files

- [`references/memory-entry-format.md`](references/memory-entry-format.md) — entry template and field rules
- [`references/frustration-patterns.md`](references/frustration-patterns.md) — correction signals worth capturing (and what to ignore)
- [`references/agent-definitions.md`](references/agent-definitions.md) — dispatch prompt for `learn-from-frustration`
