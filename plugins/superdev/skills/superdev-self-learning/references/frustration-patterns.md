# Correction signals — the main agent's watchlist

There is no detection hook. The main agent watches for these signals in user messages and verifier verdicts; on a strong signal it captures a lesson (see `../SKILL.md`) before declaring the affected work done. The patterns below are the recognition list — they were originally tuned for the removed `UserPromptSubmit` hook, whose loop never produced a single lesson across two real builds (regex too narrow, consumer pinned to agents not in the roster, stderr the model never saw). The signal list itself is good; the automation was not.

Conservative bias: false negatives are fine, false positives pollute memory. Normal iteration is not a signal.

## Strong signals (capture on sight)


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
\b(again\?|still (not|broken|wrong|the same)|keep (doing|breaking|changing))\b

# Sharp dissatisfaction / profanity (the real-world signal the old set missed)
\b(what the (fuck|hell)|wtf|this sucks|garbage|useless|terrible|awful)\b
\b(that's not what i (asked|wanted|said))\b

# Lint / type SUPPRESSION vetoes (user forbidding the shortcut)
do ?n'?t .*(disable|suppress|ignore|warn|as any)
\b(no (inline )?(eslint|ts).?(disable|ignore)|no suppress)\b
fix .*(root cause|properly|professionally)

# Fake / mock data callouts (demo-vs-product)
\b(fake data|mock data|not real|still (mock|fake|dummy|hardcoded)|hardcoded|placeholder)\b
don't (show|use) (fake|mock|dummy)

# Preserve-intent ("keep it / don't remove / don't change")
keep (the|it|them|that).*(don't remove| stay)
don't (remove|delete|change|touch)
\b(put|bring) (it|them) back\b
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
