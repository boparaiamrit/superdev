# Frustration patterns — conservative detection

The `UserPromptSubmit` hook checks each user message against these patterns. Match → queue `learn-from-frustration` for the next SubagentStop.

## Strong signals (fire on match alone)

```regex
# Short emphatic corrections (message ≤ 40 chars total)
^\s*(no|stop|wrong|nope|don't|don't do that|undo|revert|that's wrong)[\s.!,]*$

# "I already told you" markers (any message length)
\b(i (already )?(told|said))\b
\b(for the (second|third|fourth|fifth) time)\b
\b(stop ignoring (me|this))\b
\b(why (are you|do you keep))\b
\b(i (just )?said (not to|don't))\b

# Reversion announcements
\b(i('m| am)? going to revert)\b
\b(rolling? this back)\b
\b(this needs to be undone)\b

# Direct breakage callouts
\b(you broke (it|the))\b
\b(this is broken)\b
\b(this isn't working)\b
\b(nothing works)\b
```

## Code revert signals (fire on detection at next Bash invocation)

The hook also runs:

```bash
# Files Claude wrote in last 5 commits
git log --author='Claude' --pretty=format: --name-only HEAD~5..HEAD 2>/dev/null \
  | sort -u > /tmp/claude-files.txt

# Files the user reverted in last 1 commit
git log --pretty=format: --name-only HEAD~1..HEAD 2>/dev/null \
  | sort -u > /tmp/recent-files.txt

# Intersection: files Claude wrote AND user just touched
comm -12 /tmp/claude-files.txt /tmp/recent-files.txt
```

If non-empty AND the recent commit message contains "revert" / "undo" / "rollback" → fire.

## Implicit signals (fire only with confirming evidence)

These require BOTH:
- The user re-prompted within 2 minutes of Claude's last response, AND
- The new prompt contradicts what Claude just did

```regex
^\s*(actually,?|wait,?|hmm,?|hold on,?|on second thought)
\b(meant to say|should be|need to|instead)\b
```

Detected, but **suppressed if the previous message was a question Claude asked the user** — in that case the user is just clarifying their answer, which is normal iteration.

## What does NOT trigger learning

Normal back-and-forth, even when it includes corrections:

| Message | Triggers? | Why |
|---|:---:|---|
| "Actually, let's use blue not red" | ❌ No | normal iteration |
| "Change the heading to 'Welcome'" | ❌ No | normal edit |
| "Hmm, can we try a different layout?" | ❌ No | exploring |
| "Actually wait — that's not what I asked" | ✅ Yes | implicit + contradicts prior |
| "no stop — you keep restyling the buttons!" | ✅ Yes | strong signal |
| "I already told you not to swap to shadcn buttons" | ✅ Yes | repeat-correction marker |
| "I'm going to revert this commit" | ✅ Yes | revert announcement |
| "Why did you change the spacing again?" | ✅ Yes | repeat-correction marker |

## Tuning

If users find the system too noisy, tighten by removing "implicit signals" entirely.
If users find lessons being missed, add their team's specific frustration vocabulary to the strong-signals list (e.g. *"this is the third time I've asked"*).

Update this file when patterns are added/removed; the hook reads it at startup.
