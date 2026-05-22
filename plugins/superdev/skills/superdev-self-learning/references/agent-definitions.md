# superdev-self-learning — dispatch reference

## Hook-triggered (automatic)

The plugin's `hooks/hooks.json` includes:

```jsonc
{
  "UserPromptSubmit": [
    {
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "bash hooks/scripts/detect-frustration.sh \"$CLAUDE_USER_PROMPT\" && touch .claude/memory/.frustration-queued"
      }]
    }
  ],
  "SubagentStop": [
    {
      "matcher": "fix-applier|regression-verifier|design-fidelity-auditor|audit-synthesizer",
      "hooks": [{
        "type": "command",
        "command": "bash hooks/scripts/maybe-learn.sh \"$CLAUDE_SUBAGENT_NAME\""
      }]
    }
  ]
}
```

The hook scripts:
- `detect-frustration.sh` — applies regex from `references/frustration-patterns.md`; on match, touches a queue file
- `maybe-learn.sh` — if the queue file exists OR the just-finished agent has a captured `LESSON:` line, dispatches `learn-from-frustration` and clears the queue

## Manual dispatch

When the user explicitly says "remember that…" / "learn from this":

```
Use the learn-from-frustration agent.

Triggering event: explicit-remember
User's request: <quote them verbatim>

Identify the lesson, check for duplicates against .claude/memory/superdev-learned/,
write or update an entry. Confirm to the user what was captured.
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

## Bulk surface (debug)

To see all current lessons:

```
List every file in .claude/memory/superdev-learned/. For each, show the
description from frontmatter and applies_to_agents. Group by applies-to.
```
