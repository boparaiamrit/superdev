---
name: superdev-self-learning
description: The meta-skill that makes superdev self-improving. Captures user-frustration signals (explicit corrections, code reverts, regression-verifier failures, design-drift above 1%, re-prompts with frustration markers) and writes structured **feedback** memory entries to `.claude/memory/superdev-learned/`. Future orchestrator dispatches read this memory first so the system learns what NOT to do in this project, what skills to call (or never call) in which context, and which defaults to pre-apply. Project-scoped only; never global. Triggered automatically by the `UserPromptSubmit` hook on frustration patterns and by `SubagentStop` after fix-applier or design-fidelity-auditor.
---

# Superdev Self-Learning — the meta-loop

The skill that makes superdev get smarter every time it fails. When you correct it, when you revert its code, when a verifier catches a regression, when an audit fails — the system **learns the lesson, writes it to project memory, and primes every future agent dispatch with that lesson**.

This is what turns "a plugin" into "the ultimate superdev team".

## The Iron Law

```
EVERY FRUSTRATION SIGNAL BECOMES A FEEDBACK MEMORY ENTRY.
EVERY ORCHESTRATOR DISPATCH READS `.claude/memory/superdev-learned/` FIRST.
THE SAME MISTAKE MUST NEVER BE MADE TWICE IN THE SAME PROJECT.
```

## When this skill is invoked

**Automatically** (via hooks — see below):

- `UserPromptSubmit` hook detects frustration keywords ("no", "wrong", "stop", "that's not what I asked", "I already told you", "for the third time") AND there were recent superdev edits in this session
- `SubagentStop` after `fix-applier` succeeds (extracts the `LESSON:` line)
- `SubagentStop` after `design-fidelity-auditor` reports drift (extracts drift-cause patterns)
- `SubagentStop` after `regression-verifier` REJECTs (the rejection IS a lesson)
- `SubagentStop` after `audit-synthesizer` (recurring-issue classes become defaults)

**Manually** when the user says:
- "Remember that we don't do X here"
- "Learn from this — Y was the wrong approach"
- "From now on, always Z in this project"

## When this skill is NOT invoked

- ❌ Normal iteration ("actually, change the color to blue") — that's normal back-and-forth, not frustration
- ❌ Bugs in user-written code (not Claude's responsibility to learn from)
- ❌ User asking superdev to do something it correctly refused to do (the refusal was right)

## How frustration detection works (conservative)

The `UserPromptSubmit` hook fires on every user message. It checks:

1. **Strong signal — fire immediately:**
   - "no" / "wrong" / "stop" / "don't do that" / "you broke it" — as a near-complete message (< 40 chars)
   - "I already told you" / "for the third time" / "stop ignoring" / "listen" — frustration markers

2. **Code revert signal — fire immediately:**
   - `git diff HEAD~1 HEAD` shows the user reverted files Claude wrote in the last 5 commits

3. **Implicit signal — fire only if combined with corrections:**
   - User re-prompts with "actually..." within 2 minutes of Claude's last response, AND the new prompt contradicts what Claude just did

**Conservative bias:** false negatives are fine (we'll catch the pattern next time). False positives create noisy memory entries that future agents waste tokens reading.

## What gets written

For each frustration event, the `learn-from-frustration` agent writes a memory entry to `.claude/memory/superdev-learned/<topic>.md`:

```markdown
---
name: <kebab-case-topic>
description: <one-line — what to do / not do in this project>
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: <user-correction | git-revert | regression-rejected | drift-failed | audit-pattern>
  date: 2026-05-22
---

<The rule>

**Why:** <The frustration event that produced this lesson. Cite specific files / agents / decisions that went wrong.>

**How to apply:** <When / where this rule kicks in. Which agent's prompt should include it.>

**Related:** [[other-learned-topic]] (if applicable)
```

Examples of real learned entries:

### `.claude/memory/superdev-learned/no-restyle-source-buttons.md`
```markdown
---
name: no-restyle-source-buttons
description: In this project, never replace source `<button>` elements with shadcn `<Button>`
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: drift-failed
  date: 2026-05-22
---

When componentizing the preserved source UI, **wrap source `<button>` markup** with a React component (adding `onClick` props). DO NOT swap to shadcn's `<Button>`.

**Why:** design-fidelity-auditor flagged 8% drift on three pages after frontend-module-builder replaced source buttons with shadcn. User reverted those commits twice and said "I told you not to change the buttons".

**How to apply:** frontend-module-builder and frontend-rewirer must include this rule in their prompts when design-preservation is active in this project.

**Related:** [[wrap-dont-replace-patterns]]
```

### `.claude/memory/superdev-learned/aggregate-counts-always-real.md`
```markdown
---
name: aggregate-counts-always-real
description: In this project, presenters must always compute aggregate counts from the DB — never hardcode 0
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: audit-pattern
  date: 2026-05-22
---

Aggregate fields like `deal_count`, `note_count`, `member_count` must be SELECT COUNT(...) computed in the presenter, not hardcoded to 0.

**Why:** product-completeness-audit found 3 separate HYBRID screens in this repo where counts were hardcoded. The pattern came from the demo-mode fixtures. Backend-module-builder repeatedly skipped the aggregate query "because the fixtures had 0".

**How to apply:** backend-module-builder's prompt must include a line: "Any field whose name ends in `_count` MUST be computed via SELECT COUNT in the presenter, not hardcoded".

**Related:** [[data-flow-real-vs-mock]]
```

## How the orchestrator uses learned memory

At the start of every skill dispatch, the orchestrator runs:

```bash
ls .claude/memory/superdev-learned/ 2>/dev/null
```

For each file found, it reads the frontmatter `description` and the body. Relevant entries (matched by topic against the about-to-dispatch agent) are appended to that agent's prompt as a **"Lessons learned in this project"** section.

Example agent prompt augmentation:

```
[Original frontend-module-builder prompt…]

## Lessons learned in this project — APPLY THESE
- no-restyle-source-buttons: wrap source `<button>` markup; do NOT swap to shadcn's `<Button>` (design-fidelity-auditor flagged 8% drift twice, user reverted)
- aggregate-counts-always-real: …
- never-add-error-boundaries-to-list-pages: …
```

## Project scope only

All learned lessons stay inside the current repository so one project's rules cannot affect another project. Superdev never writes learned memory to a user-level or personal instruction file and never promotes project lessons automatically. Reuse in another repository requires an explicit copy or a new lesson created in that repository.

## Self-improving lifecycle

```
   User dispatches superdev
        │
        ▼
   Orchestrator reads .claude/memory/superdev-learned/
        │
        ▼
   Threads relevant lessons into agent prompts
        │
        ▼
   Agents do work informed by past mistakes
        │
        ▼
   Something goes wrong? (revert / frustration / verifier reject)
        │
        ▼
   Frustration hook fires → learn-from-frustration agent
        │
        ▼
   New memory entry written to .claude/memory/superdev-learned/
        │
        ▼
   NEXT dispatch reads the new entry too → mistake is not repeated
        │
        └─────── (loop forever, getting smarter each iteration)
```

## Reference files

- [`references/frustration-patterns.md`](references/frustration-patterns.md) — exact regex/keyword list for hook detection
- [`references/memory-entry-format.md`](references/memory-entry-format.md) — the writing template
- [`references/orchestrator-integration.md`](references/orchestrator-integration.md) — how the orchestrator threads memory into prompts
- [`references/agent-definitions.md`](references/agent-definitions.md) — dispatch prompt for learn-from-frustration
