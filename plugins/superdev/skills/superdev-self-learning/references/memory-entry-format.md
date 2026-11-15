# Lesson format

Every lesson in `.claude/memory/superdev-learned/` is one file in this format, named `<name>.md`.

```markdown
---
name: <kebab-case, at most 50 characters>
description: <one line, at most 100 characters, stated as a rule>
metadata:
  type: feedback
  source: superdev-self-learning
  triggered_by: user-correction | git-revert | verifier-rejected | runtime-check | audit-pattern | explicit-remember
  date: YYYY-MM-DD
  applies_to_agents: [agent-name, agent-name]
---

The rule, one or two sentences.

**Why:** what failed, with redacted local evidence (file:line, command, result line).

**How to apply:** when it applies and the check that proves it.
```

Fields:

- `name` equals the file name without `.md`.
- `description` is what the main agent reads in `INDEX.md` to decide whether the lesson applies; write it as the rule itself.
- `triggered_by` is one of the values above; `date` is the day the lesson was written, in IST.
- `applies_to_agents` lists the superdev agents whose prompts must carry the lesson; `[]` when it is for the main agent only.
- **Why:** and **How to apply:** carry evidence, never credentials, tokens, personal data or customer payloads (rule LRN-2). A new failure of the same rule is added to **Why:** of the existing file (rule LRN-1).

`INDEX.md` has one line per lesson, in the order they were written: `- `, the lesson's `name` as a Markdown link to its file, then `: ` and its `description`. For the lesson `migrate-before-boot.md`, the line links the text `migrate-before-boot` to `migrate-before-boot.md` and ends with `: Run navree migrate before booting the release binary at step 6.3.`
