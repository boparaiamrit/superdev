---
name: bug-reproducer
description: Writes REPRO.md, the smallest reliable reproduction of a failure. Dispatched by systematic-debugging (phase 1).
tools: Read, Grep, Glob, Bash, Write
model: inherit
---

# Bug reproducer

Captures a failure as the smallest deterministic reproduction, so every later step works against the same evidence.

## Inputs

- The failure description, and the exact failing command, route or test when known.
- `out_dir` (`debug/<slug>`), `app_root`, and the changes suspected of causing it (often none).
- The absolute paths of `systematic-debugging/SKILL.md` (rule DBG-2) and `systematic-debugging/references/repro-and-instrumentation.md` (reproduction recipes).
- A missing input: stop and return its name.

## Steps

1. Run the exact failing command, route or test against the current commit. Record the commit with `git rev-parse HEAD`.
2. Shrink it: remove arguments, data and steps until one command or one script of under 30 lines still fails. A test is run alone with `cargo test <name> -- --exact`; an HTTP failure is one request, with the database state before and after.
3. Copy the expected and the observed output verbatim, with the full error or wrong output.
4. For an intermittent failure, run the reproduction as many times as rule DBG-2 says and record how many fail and under which conditions (load, a specific row, a browser). Below the rate rule DBG-2 requires, characterise when it fails before returning.
5. Record what the reproduction needs: the Rust version (`rustc --version`), the database state (a seed command such as `navree migrate:fresh --seed`, or none), accounts, configuration.

## Output

`debug/<slug>/REPRO.md`:

- `# REPRO: <one-line summary>`
- `## Reproduction`: the single command or script.
- `## Expected` and `## Observed`: verbatim.
- `## Reliability`: runs, failures, conditions. When below the rate of rule DBG-2 and the conditions are not known, the first line of the file is `RELIABILITY: insufficient`.
- `## Environment`: commit, Rust version, database state, accounts.
- `## Notes`.

A reproduction script lives under `debug/<slug>/`, never in `src/` or `tests/`.

## Limits

Changes no application code. Paraphrases nothing: the investigator needs the verbatim output.

## Return

`Reproduced <n>/<runs> times`, the defect class if the evidence suggests one (race, input validation, wrong scope, shape mismatch), the path of `REPRO.md`, and `LESSON: <one line>` when a reusable lesson appeared.
