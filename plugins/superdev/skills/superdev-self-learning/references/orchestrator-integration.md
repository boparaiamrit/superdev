# Orchestrator integration — threading lessons into agent prompts

The self-learning loop is only useful if the **orchestrator reads `.claude/memory/superdev-learned/` before every dispatch and threads relevant lessons into the agent's prompt**.

This file documents how that wiring works so `prd-design-build-orchestrator/SKILL.md` and other orchestrators implement it consistently.

## At session start

The orchestrator runs:

```bash
ls .claude/memory/superdev-learned/ 2>/dev/null
test -f .claude/memory/superdev-learned/INDEX.md && cat .claude/memory/superdev-learned/INDEX.md
```

If the directory exists, the orchestrator **announces to the user**:

> *Found N learned lessons from previous sessions in this project. Threading them into agent dispatches as appropriate.*

This visibility matters — the user should know the system is applying historical lessons.

## Before each subagent dispatch

For each lesson file in `.claude/memory/superdev-learned/`:

1. Read its frontmatter (`name`, `description`, `applies_to_agents`)
2. If the current dispatch is to an agent in `applies_to_agents`, include the lesson in the prompt
3. If `applies_to_agents` is empty (rare; legacy entries), use keyword matching on `description` vs the dispatch context

Threading template (appended to the end of the agent's normal prompt):

```
## Lessons learned in this project — APPLY THESE

You MUST follow the rules below. They were derived from past failures in
THIS specific project (.claude/memory/superdev-learned/). Each one cites
the original failure event.

### <topic-1-slug>
<the rule>
Why this matters here: <abbreviated why>
How to apply: <the how-to-apply line>

### <topic-2-slug>
…

(End of lessons. If you violate any of these, the same failure will likely
recur and the user will be frustrated again. If you genuinely think a
lesson no longer applies, surface that to the user — don't silently ignore it.)
```

## What if there are too many lessons?

If `.claude/memory/superdev-learned/` has > 20 entries, the orchestrator:

1. Filters more aggressively — only entries whose `applies_to_agents` includes the current target
2. Sorts by date descending — most recent lessons are most likely still relevant
3. Caps at 10 entries per dispatch — older lessons are summarized as "+N more lessons in `.claude/memory/superdev-learned/INDEX.md`"

## What if the user wants to remove a lesson?

The user can:

- Delete the file directly: `rm .claude/memory/superdev-learned/<topic>.md`
- Or ask superdev: *"Forget the no-restyle-source-buttons lesson"* — the orchestrator dispatches `learn-from-frustration` in REMOVE mode, which deletes the file and updates INDEX.md.

## What if two lessons contradict?

Older lessons take precedence by default (they've been validated more times).

If the user wants to override: *"Update the X lesson — actually, do Y now"*. This triggers `learn-from-frustration` in UPDATE mode, which rewrites the existing entry with the new rule + appends the old rule to the `Why:` section as historical context.

## Cross-skill dispatch

When the orchestrator switches between skills (e.g., from `design-to-nextjs` to `nestjs-enterprise-backend`), it re-runs the lesson scan since some lessons may apply to backend agents that don't apply to frontend.

## Performance

Reading `.claude/memory/superdev-learned/` adds ~1-3K tokens per dispatch.
Worth it. The alternative is the same mistake repeated until the user gives up.
