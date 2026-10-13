# superdev-self-learning — dispatch reference

Lesson capture is deliberate, never hook-driven. The main agent notices a capture-worthy signal (see `frustration-patterns.md`), then either writes the entry directly (usual — most lessons are one crisp rule) or dispatches `learn-from-frustration` to synthesize an entry from a messy correction sequence.

## Capture dispatch

```
Use the learn-from-frustration agent.

Triggering event: <user-correction | git-revert | verifier-rejected | runtime-check | audit-pattern | explicit-remember>
Evidence: <the user's words verbatim, the reverted commit, the verifier verdict, or the failing check output>
Files/agents involved: <concrete paths and agent names>

Identify the transferable lesson, check for duplicates against
.claude/memory/superdev-learned/, write or update one entry per
references/memory-entry-format.md. If the lesson is stack-general,
flag it for promotion to superdev-build hard-rules in your return.
Confirm what was captured.
```

## Update / remove

```
Use the learn-from-frustration agent in UPDATE mode.
Existing lesson: <slug>
New rule: <as user expressed>
```

```
Use the learn-from-frustration agent in REMOVE mode.
Lesson to remove: <slug>
Reason for removal: <user's reason>
```

## Bulk surface (review)

To see all current lessons:

```
List every file in .claude/memory/superdev-learned/. For each, show the
description from frontmatter and applies_to_agents. Group by applies-to.
Flag any lesson that is stack-general and not yet in hard-rules.md.
```
