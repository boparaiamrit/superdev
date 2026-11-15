---
name: superdev-self-learning
description: Use when the operator corrects superdev's approach, reverts its code, a verifier rejects work, a runtime check catches what tests missed, or someone says remember this. Writes one lesson file in the project's .claude/memory/superdev-learned and reads the index at the start of a build.
---

# Superdev self-learning

A lesson is a rule a build learned from a real failure, written into the app so the next session and the next agent follow it. Lessons live in the app's `.claude/memory/superdev-learned/`, one file each, listed in `INDEX.md` in the same folder. Codex uses the same folder.

## When to write a lesson

Write one when:

- the operator corrects superdev's approach (not a detail such as a colour or a word);
- the operator reverts code superdev wrote;
- a verifier rejects work: `regression-verifier` returns `REJECT`, `visual-diff-auditor` finds a region over the drift threshold, `product-audit` finds a `MOCKED` screen;
- a runtime check catches what the tests missed: the release binary does not start, a page logs a console error, a side effect is missing;
- someone says "remember this".

An agent's return line `LESSON: <rule>` is a candidate; write it when it matches one of the cases above. Do not write a lesson for a typo, a bug in code the operator wrote, or a correct refusal.

## How to write it

1. Look in `INDEX.md` for a lesson about the same rule; if there is one, update that file (rule LRN-1).
2. Write `.claude/memory/superdev-learned/<name>.md` in the format of [references/memory-entry-format.md](references/memory-entry-format.md), or dispatch `lesson-writer` with the raw evidence (the operator's words, the command and its result line, file:line) and the app root.
3. Add or update the lesson's line in `INDEX.md`.
4. Check it against rules LRN-2 and LRN-3 before saving.

## How lessons are used

- [superdev-build](../superdev-build/SKILL.md) reads `INDEX.md` before step 1 of a build it resumes, and opens the lessons whose description applies.
- Before dispatching an agent named in a lesson's `applies_to_agents`, append the lesson (the rule, **Why:** and **How to apply:**) to the agent's prompt under `## Lessons for this project`.

## Proposing a rule for superdev

A lesson that would hold in any Navree build may become a superdev rule. Propose it to the operator as the generic rule, its scope, the fix and the check, with no project names, domains, dates or metrics. The build never writes into the plugin.

## Rules

- **LRN-1** One lesson per file, updated, not duplicated.
- **LRN-2** No credentials, tokens, personal data or customer payloads in a lesson.
- **LRN-3** A lesson names the check that proves it is followed.

## Reference files

| File | Read it |
|---|---|
| [references/memory-entry-format.md](references/memory-entry-format.md) | before writing or updating a lesson |
