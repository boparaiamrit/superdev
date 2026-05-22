# Systematic debugging — agent dispatch reference

Copy-paste prompts for dispatching each agent. Substitute placeholders.

## bug-reproducer

```
Use the bug-reproducer agent.

Failure: <one-line user description>
Exact failing command/route/test: <verbatim>
Suspected recent changes: <git commit hash or "unknown">

Produce REPRO.md with reliability ≥ 3/5 for intermittent bugs. Refuse to
declare success if reliability is insufficient — write that in REPRO.md and
stop.
```

## root-cause-investigator

```
Use the root-cause-investigator agent.

Inputs:
- REPRO.md (in working dir)
- 'git log -p --since=14.days -- <files in stack trace>'
- Container logs: docker logs <workspace>_postgres --tail 500 (if DB-related)

Produce ROOT_CAUSE.md (VERIFIED:true, defect class named, falsifying experiment
included) OR CANDIDATES.md (2+ candidates with their own experiments).

Write a feedback memory entry to .claude/memory/superdev-learned/ describing
the defect class pattern so future agents avoid it.
```

## hypothesis-tester (one per candidate, dispatched in parallel)

```
Use the hypothesis-tester agent.

You are responsible for candidate <N> in CANDIDATES.md. Design an experiment
that would FALSIFY candidate <N> (not just confirm the bug exists). Run it.

Produce HYPOTHESIS_<N>.md with VERDICT: confirmed | rejected | inconclusive
and the experiment output verbatim.
```

When dispatching multiple candidates, do it in a single message with N parallel
agent calls so they run concurrently.

## fix-applier

```
Use the fix-applier agent.

ROOT_CAUSE.md MUST exist with VERIFIED: true. Apply ONE fix scoped strictly
to the files listed in ROOT_CAUSE.md's "Fix scope" section.

Re-run the REPRO.md reproduction. Run typecheck. Run closest test pattern.

Include a one-line LESSON in your output for the self-learning hook.
```

## regression-verifier

```
Use the regression-verifier agent.

Inputs: REPRO.md, ROOT_CAUSE.md, fix-applier's diff (git diff HEAD).

Run:
1. Full test suite for the affected workspace
2. Playwright smoke for every route in git diff
3. Diff-aware review: every changed line must be explained by ROOT_CAUSE.md's fix scope
4. Cross-cutting checks: view-shape contract, CASL, @Audit

Produce REGRESSION.md with verdict READY TO COMMIT or REJECT.
If REJECT, the orchestrator re-dispatches fix-applier with the reasons.
```

## Agent teams (competing hypotheses)

When CANDIDATES.md has 3+ candidates and stakes are high (prod outage, repeat regression):

```
Dispatch a 3-teammate competing-hypotheses team.

Teammate A: champion candidate 1 from CANDIDATES.md
Teammate B: champion candidate 2
Teammate C: champion candidate 3

Each teammate must:
- Defend their own candidate with new evidence
- Propose an experiment that would FALSIFY one of the other candidates
- After the experiment runs, evaluate the others' new evidence

When 2 teammates converge on the same candidate, promote it to ROOT_CAUSE.md.
When all 3 disagree after one round of cross-experiments, the investigation
is incomplete — re-dispatch root-cause-investigator with the new evidence.

Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```
