---
name: superdev-done
description: Use when someone asks whether the build is done, before any completion claim, or to run the machine checks of a superdev build on demand. Runs verify-done.mjs against the live tree and reports each check as PASS, FAIL or NOT RUN.
---

# Superdev done

`verify-done.mjs` answers "is the build done?" by running its checks against the app as it is now; it never reads a status someone wrote down. Step 10 of [superdev-build](../superdev-build/SKILL.md) runs it on the final commit.

## Run it

From the app root (in another folder, the missing `STACK.md` fails the first check):

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs                    # while building
node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs --suites --strict  # a release claim
```

In Codex, use the path of the `plugins/superdev` folder the plugin was installed from in place of `${CLAUDE_PLUGIN_ROOT}`. Before `--suites`, start the database (`navree dock up` for TimescaleDB and PostgreSQL; MySQL runs on a server you provide) and the app so it answers on `--api-url`, and reset the data with `navree migrate:fresh --seed`: the suites create records and sign in as the demo accounts. `test_database_url` in `STACK.md` must be set for any database but SQLite, or the real-database tests would pass without running. The sweeps compare with `base_commit`, so a CI run needs the full history (`fetch-depth: 0` in a GitHub Actions checkout); without it they are `NOT RUN` and `--strict` fails.

## Flags

`--help` prints the usage and the list of checks, which is the one list of them.

- `--root DIR`: the app root (default: the current directory).
- `--skip-build`: no `cargo build --release` and no web `build` script; those checks print `NOT RUN`.
- `--skip-boot`: do not boot the release binary (`NOT RUN`).
- `--health-url URL`: for `--suites`, poll this URL instead of `<api-url>/health/ready`. The boot check always probes the release binary it started, on a port of its own.
- `--suites`: run the committed suites listed under `## Suites` in `STACK.md` against the running app.
- `--api-url URL`: base URL of the running app for `--suites` (default `http://127.0.0.1:8080`).
- `--base REF`: base commit for the suppression and raw-markup sweeps (default: `base_commit` in `STACK.md`).
- `--strict`: every warning and every `NOT RUN` fails; a release claim uses it.

## Exit codes

- `0`: done. Without `--strict`, the last line says when warnings or checks not run make it no release claim.
- `1`: not done. Fix each failing check at its cause (hard rule 15 of [superdev-build](../superdev-build/references/hard-rules.md)), then run it again.
- `2`: usage error: an unknown flag, or a flag missing its value.

## What it does not prove

The script proves the machine layer only. Behaviour in a browser across routes and roles, devices, accessibility and contrast, and business correctness are the job of the gate of [product-qa](../product-qa/SKILL.md), whose `QA_COVERAGE.md` cites evidence for every cell. A build is done when this script exits 0 with `--suites --strict` on the final commit and that gate is clean on the same commit.
