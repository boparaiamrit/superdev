---
name: systematic-debugging
description: Use when anything fails (a test, a build, a runtime error, a regression, a flaky test, a works-locally-but-not-in-CI problem). Reproduces it, finds a falsifiable cause, tests competing hypotheses, applies one scoped fix and checks for regressions; no fix without a verified cause on disk.
---

# Systematic debugging

This skill is the order of work for any failure: reproduce it, find a cause that an experiment could prove wrong, apply one scoped fix, and check what else moved. Each phase leaves a file under `debug/<slug>/`, where `<slug>` is a short kebab-case name for the failure. Pass every agent absolute paths, the failure description and `out_dir: debug/<slug>` (rule BLD-4). A bug found at any step of a build comes here, and the step that found it continues after the fix. When the same kind of bug is likely to return, the `LESSON:` line from the fix goes to [superdev-self-learning](../superdev-self-learning/SKILL.md).

## Phases

1. **Reproduce.** `bug-reproducer` writes `debug/<slug>/REPRO.md`: the smallest reproduction that fails, on the current commit, with the expected and observed output quoted.
2. **Cause.** `root-cause-investigator` reads `REPRO.md`, the failing path, `git log -p --since=14.days` and the logs. It writes `ROOT_CAUSE.md` with a `VERIFIED: true` line, the defect class, an experiment that could prove the cause wrong (with its output) and a `## Fix scope` section. When two or more causes remain, it writes `CANDIDATES.md` instead.
3. **Hypotheses.** For `CANDIDATES.md`, dispatch one `hypothesis-tester` per candidate, in parallel. Each designs an experiment to prove its candidate wrong and writes `HYPOTHESIS_<n>.md` with `VERDICT: CONFIRMED`, `REJECTED` or `INCONCLUSIVE`. Exactly one `CONFIRMED` is promoted by the main agent to `ROOT_CAUSE.md`, with its experiment and output. With none or several, return to phase 2 with the new evidence.
4. **Fix.** `fix-applier` takes `ROOT_CAUSE.md`, applies one fix inside its `## Fix scope`, re-runs the reproduction, runs the closest tests and adds a regression test.
5. **Regression.** `regression-verifier` writes `REGRESSION.md` with `READY TO COMMIT` or `REJECT`. After a `REJECT`, return to phase 2 with its evidence.

## Gates

- Before phase 2: `REPRO.md` exists and its reproduction fails on the current commit as rule DBG-2 requires.
- Before phase 4: `ROOT_CAUSE.md` has `VERIFIED: true`, a defect class, a file and line, a log line or a commit, and the output of the experiment that could have proved it wrong.
- Before phase 5: the reproduction passes, the closest `cargo test` passes (and `pnpm run typecheck` when `front_end: next`), and the diff touches only files named in `## Fix scope`.
- Done: `REGRESSION.md` says `READY TO COMMIT` and quotes the result line of the full test run.

## Where to look in a Navree app

| Symptom | Look at |
|---|---|
| A request fails and the code does not say why | the `X-Request-Id` of the response and the log lines with that id; the `/_logbook` timeline in a debug build; Lighthouse at `/_lighthouse` in production (`navree-logbook`, `navree-lighthouse`) |
| Navigator is connected to the coding agent (`claude mcp add navree -- navree mcp`) | its `last_error`, `read_logs` and read-only `query_database` tools (`navree-navigator`) |
| Log levels do not change | `RUST_LOG` is not read; set the levels in configuration (`navree-config`) |
| A 403 | `navree access:explain <user> <action> <Subject> [id]` and the rules in `src/abilities.rs`; a 403 `forbidden_fields` means a field outside the rule (`navree-access-control`) |
| A 404 or 405 | `navree routes --json` for the path, the method and the `!` prefix of page routes; another workspace's record answers 404 |
| A 401 on a route that should work | an invalid bearer token is a 401 on every route, public ones included: drop the stale token |
| A write that vanished | the handler answered 400 or more, so its unit of work rolled back: read the status (`navree-database`) |
| An audit entry is missing | a mass update or raw SQL skips model events and the audit log; record it with `uow.record_change` |
| A job ran twice, or never | jobs run at least once, outside any unit of work, and are queued only if the request commits; a memory queue is per process, so a separate `queue:work` sees nothing; `queue:failed` lists the failures (`navree-queues-and-scheduling`) |
| A scheduled task skipped a day | the scheduler skips missed minutes and does not catch up |
| A live update never arrived | a worker broadcasts through `dyn Broadcaster` with the same `APP_KEY`; `Realtime::broadcast` from a worker reaches nobody (hard rule 24) |
| A test passes on SQLite and fails on PostgreSQL | tests run on SQLite unless `NAVREE_TEST_POSTGRES_URL` or `NAVREE_TEST_MYSQL_URL` is set and the test uses `#[navree::test(database = "postgres")]`; a test whose server is not configured is skipped with a notice, so look for the notice (`navree-testing`) |
| A test passes locally and fails in CI | a test booted with `ConfigSources::defaults()` reads the developer's `.env`; on Windows call `app.shutdown().await` |
| A configuration value is not what was set | `navree config:show --origin`: later sources win, `.env` beats `config/app.toml`, and only `APP_*` variables are read |
| The app fails at start with a module graph error | `navree check`, which needs configuration and a migrated database (hard rule 13) |

## Rules

- **DBG-1** No fix without `ROOT_CAUSE.md` showing `VERIFIED: true`.
- **DBG-2** The reproduction is the smallest that fails, on the current commit, with the expected and observed output verbatim and the data it needs. An intermittent failure reproduces in at least 3 of 5 runs.
- **DBG-3** A root cause names a defect class (race, missing index, type coercion, off-by-one, wrong scope) and cites a file and line, a log line or a commit, with an experiment that could prove it wrong.
- **DBG-4** Instrumentation reads first. Anything that changes behaviour sits behind a flag and is removed before the fix.
- **DBG-5** One fix within the files the root cause names, with a regression test. No cleanup alongside, no swallowed error, no raised timeout, no test edited to match broken output, no suppression.
- **DBG-6** The regression check runs the full `cargo test` (and the web tests when `front_end: next`), opens each touched route, and explains every changed line.

## Reference files

| File | Read when |
|---|---|
| [references/repro-and-instrumentation.md](references/repro-and-instrumentation.md) | Writing `REPRO.md`, and adding diagnostics in phases 2 and 3 |
