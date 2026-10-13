---
name: superdev-self-learning
description: Capture hard lessons from corrections, reverts, verifier rejections, and runtime-check failures as structured feedback entries in the target project's `.claude/memory/superdev-learned/`, and read them once at the start of a build (and before dispatching an agent the lesson names). Manual and deliberate — there are no frustration-detection hooks. Invoke when the user corrects superdev's approach, reverts its code, a verifier rejects work, or the user says "remember this". Stack-general lessons belong in the superdev-build hard-rules, not siloed in one project.
---

# SuperDev Self-Learning — lessons, written down once

When a build goes wrong in a way that teaches something — the user corrects the approach, reverts generated code, a verifier rejects a fix, a runtime check catches what static gates missed — write the lesson to project memory in a strict format, and read project memory **once at the start of a build** (plus before dispatching an agent a lesson explicitly names). That is the whole loop. Earlier versions automated this with bash frustration-detection hooks and per-dispatch threading; the hooks never ran reliably cross-platform and at least once filed one project's frustration into another project's memory, so capture is now a deliberate act by the main agent.

## The rule

```
A REAL FAILURE BECOMES A WRITTEN LESSON, OR IT WILL HAPPEN AGAIN.
PROJECT LESSONS LIVE IN .claude/memory/superdev-learned/.
STACK-GENERAL LESSONS ARE PROMOTED TO superdev-build/references/hard-rules.md —
A LESSON SILOED IN ONE PROJECT DID NOT PREVENT THE SAME BUG IN THE NEXT.
```

The canonical cautionary tale: the `patchNestJsSwagger` boot crash was learned on ForgeMyTool (2026-06-20, project memory only) and still shipped on PostMitra. Both lessons now live in `hard-rules.md`. When you write a project lesson, ask: *would this bite a different project on the same stack?* If yes, say so in your summary so it can be promoted — do not just file it locally.

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

**Why:** <the concrete failure — files, agents, observed behavior. Cite evidence.>

**How to apply:** <when/where the rule kicks in; the exact check that proves compliance>

**Related:** [[other-topic]] (if applicable)
```

Full template and field rules: [`references/memory-entry-format.md`](references/memory-entry-format.md). To synthesize an entry from a messy correction sequence, dispatch the `learn-from-frustration` agent with the raw evidence (dispatch prompt: [`references/agent-definitions.md`](references/agent-definitions.md)), or write the entry directly when the lesson is already crisp — most are.

## How lessons get used

1. **Build start:** `superdev-build` Step 0 — the main agent skims `.claude/memory/superdev-learned/` once and keeps relevant constraints in working memory for the build.
2. **Before a named dispatch:** if an entry's `applies_to_agents` includes the agent about to be dispatched, append the entry (rule + why) to its prompt under `## Lessons learned in this project`.
3. **Promotion:** stack-general lessons are proposed for [`../superdev-build/references/hard-rules.md`](../superdev-build/references/hard-rules.md) with their project/date provenance. Only the user edits global/personal memory outside the project — never write there unasked.

## Reference files

- [`references/memory-entry-format.md`](references/memory-entry-format.md) — entry template and field rules
- [`references/frustration-patterns.md`](references/frustration-patterns.md) — correction signals worth capturing (and what to ignore)
- [`references/agent-definitions.md`](references/agent-definitions.md) — dispatch prompt for `learn-from-frustration`
