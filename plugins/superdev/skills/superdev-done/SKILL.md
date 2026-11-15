---
name: superdev-done
description: Use when someone asks whether the build is done, before any completion claim, or to run the machine checks of a superdev build on demand. Runs verify-done.mjs against the live tree and reports each check as PASS, FAIL or NOT RUN.
---

# Superdev done

`verify-done.mjs` answers "is the build done?" by running its checks against the app as it is now; it never reads a status someone wrote down. Step 10 of [superdev-build](../superdev-build/SKILL.md) runs it on the last commit that changes code.

## Run it

From the app root (in another folder, the missing `STACK.md` fails the first check):

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs --fast            # while building: nothing is compiled
node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs                   # every check, no claim
node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs --suites --strict # the done check
```

The first full run compiles the app in three profiles (check, test and release): 10 to 20 minutes and several GB in `target/`, and the script prints only `running: <command>` lines meanwhile. Run it detached, with its output in a git-ignored file, and read the file when it ends (in PowerShell, `Start-Process` with `-RedirectStandardOutput` does the same):

```bash
mkdir -p qa/runs && nohup node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs > qa/runs/verify-done.log 2>&1 &
```

Later runs are incremental and take minutes. `--fast` runs only the checks that build nothing and prints `NOT RUN` for the rest, so a fast run is the quick look to use while building and never ends `DONE`. In Codex, use the path of the `plugins/superdev` folder the plugin was installed from in place of `${CLAUDE_PLUGIN_ROOT}`; with no CLI of either host, the same path of a checkout (step 1 of [superdev-build](../superdev-build/SKILL.md)). Before `--suites`, start the database (`navree dock up` for TimescaleDB and PostgreSQL; MySQL runs on a server you provide; SQLite needs nothing): each suite is a `cargo test` command that boots its own app, so no app has to be running. `test_database_url` in `STACK.md` must be set for any database but SQLite, or the real-database tests would pass without running. The sweeps compare with `base_commit`, so a CI run needs the full history (`fetch-depth: 0` in a GitHub Actions checkout); without it they are `NOT RUN` and `--strict` fails.

## Flags

`--help` prints the usage and the list of checks, which is the one list of them.

- `--root DIR`: the app root (default: the current directory).
- `--fast`: only the checks that build nothing (`STACK.md`, the `navree` CLI, the installed skills, `cargo fmt --check`, the flow's files, the sweeps over source); the others print `NOT RUN`. Not with `--suites`.
- `--skip-build`: no `cargo build --release` and no web `build` script; those checks print `NOT RUN`.
- `--skip-boot`: do not boot the release binary (`NOT RUN`).
- `--suites`: run the committed suites listed under `## Suites` in `STACK.md`. Without it the line `suites` prints `NOT RUN`, so a `--strict` run without `--suites` never ends `DONE`.
- `--base REF`: base commit for the suppression and raw-markup sweeps (default: `base_commit` in `STACK.md`).
- `--strict`: every warning and every `NOT RUN` fails, and `SECURITY_REPORT.md`, `AUDIT_REPORT.md`, `QA_COVERAGE.md` and `ACCEPTANCES.md` are read (below).

## Exit codes

- `0`: no check failed. That is not done: only a `--suites --strict` run whose last line is `DONE` means the build is done. Any other run with exit `0` ends with a line that says `NOT DONE`, lists the checks that passed and the checks not run, and says that steps 7 and 8 were not checked.
- `1`: a check failed (a `--strict` run also fails on a warning and on a `NOT RUN`). Fix each failing check at its cause (hard rule 15 of [superdev-build](../superdev-build/references/hard-rules.md)), then run it again.
- `2`: usage error: an unknown flag, a flag missing its value, or `--fast` with `--suites`.

## What a `--strict` run reads

Besides the machine checks, a `--strict` run reads the files of the flow, in the formats of [artifacts.md](../superdev-build/references/artifacts.md):

- `EXECUTION_PLAN.md` has `Status: CONFIRMED by <name> on <date>`; every module of its `## Modules` has `contracts/<module>.md` with `Status: AGREED by <name> on <date>`; `Cargo.lock` is tracked by git. These three checks run without `--strict` too.
- `SECURITY_REPORT.md`, `AUDIT_REPORT.md` and `QA_COVERAGE.md` exist; the `## Findings` section of each holds a table with the columns `Severity` and `State`, or `None.`, so a table it cannot read fails; none holds an open `Blocker` or `Major` finding, a `NOT RUN` cell or row, or a `PASS (server)` cell without an `ACC-n`; each `accepted` state and each `ACC-n` names an entry of `ACCEPTANCES.md`.
- Every module row of the plan's `## Build order` is `PASS`, or `PASS (6.5 NOT RUN, ACC-n)` with an entry of `ACCEPTANCES.md`; each entry of `ACCEPTANCES.md` has a number of its own; the file is committed, and no commit changes it together with another file (for an app that is one folder of a larger repository too).

Without `--strict`, the three reports and the acceptances print `NOT RUN`, with the words that they are read under `--strict`.

## What it does not prove

The script proves the machine layer and reads the files above. Behaviour in a browser across routes and roles, devices, accessibility and contrast, and business correctness are the job of the gate of [product-qa](../product-qa/SKILL.md), whose `QA_COVERAGE.md` cites evidence for every cell. A build is done when this script exits 0 with `--suites --strict` on the last commit that changes code, ending in `DONE`, and that gate is clean on the same commit.
