---
name: product-audit
description: Use when a product looks done and someone needs to know whether it really is (do screens show real data, is every control wired, do journeys persist), wants a readiness score per module before a ship claim, or wants a full inventory of routes, models and screens. One audit, run in inventory, completeness or score mode, that writes AUDIT_REPORT.md.
---

# Product audit

This skill decides whether a built Navree app is a product or a demo. It runs in one of its modes and writes one report, `AUDIT_REPORT.md`: `inventory` counts what exists, `completeness` checks that it works on real data, and `score` rates every module from 0 to 10 and loops fixes until each one is 9 or more. It runs at step 7, after `security-review-and-fix`. The `navree-module-conformity` skill covers `navree check` and the isolation suites; this audit cites their results and does not repeat them.

## Choose the mode

| Mode | Use it when | Result |
|---|---|---|
| `completeness` | step 7, by default | a verdict: `PRODUCT`, `HYBRID` or `DEMO` |
| `score` | the operator asks for readiness scores, or says "make it production ready" | a score per module and `READY` or `NOT READY` |
| `inventory` | the operator asks for it, or after a large refactor | counts and the differences from the plan |

At step 7 the audit is clean when `AUDIT_REPORT.md` holds no open `Blocker` or `Major` finding that the operator has not accepted in writing (rule BLD-6). A single failing test or bug goes to [systematic-debugging](../systematic-debugging/SKILL.md). Browser, role and device coverage is [product-qa](../product-qa/SKILL.md).

## Before any mode

1. Run `node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs` ([superdev-done](../superdev-done/SKILL.md)). A `FAIL` there is fixed first: an app whose release binary does not boot cannot be audited.
2. Reset the data with `navree migrate:fresh --seed`, then run the release binary (`target/release/<binary> serve`) and its worker (`<binary> queue:work`). For `front_end: next`, also run the web app built and started in production mode. The running configuration holds no in-memory stand-ins (the `array` mail transport, a memory queue): a memory queue is per process, so a separate worker would see no jobs.
3. Write the mode, `git rev-parse --short HEAD` and the date at the top of `AUDIT_REPORT.md`. Results for another commit are stale: a new commit means a new run.
4. Dispatch each agent with absolute paths (rule BLD-4), its mode, `out_dir: audit` and the accounts from `EXECUTION_PLAN.md` `## Demo accounts`. Evidence goes under `audit/<agent-name>/`, which is git-ignored; `AUDIT_REPORT.md` is committed. Findings take ids `A-n` and the scale in [artifacts.md](../superdev-build/references/artifacts.md).

## Inventory mode

1. `repo-cartographer` with `out_dir: audit` lists routes with their access (`navree routes --json`), models with their scope, jobs and schedules, configuration, screens (for Next.js, `web/app/**/page.tsx`) and secrets on disk.
2. `link-crawler` in `list` mode visits every route of that list as each role, including routes nothing links to. Dynamic segments are filled with seeded ids.
3. `data-source-auditor` in `trace` mode follows each field of each contract from its column to the screen. It reports a field fetched and never shown, and a value shown that is not stored.
4. `qa-flow-tester` in `matrix` mode runs the edge categories of [explore-checklist.md](../product-qa/references/explore-checklist.md) that apply to each route.
5. The main agent writes `AUDIT_REPORT.md` with `## Inventory`: counts of routes (by access), models (by scope), pages, jobs, schedules, migrations and suites, taken from the router, the migrations and the files on disk (AUD-6). A route in a contract that the router lacks is a `Major` finding. A route in the router that no contract lists is `Minor`, and `Major` when its access is public. `Verdict:` is `none`.

## Completeness mode

1. `placeholder-hunter` finds placeholder text and stub handlers and grades each control `WIRED`, `STUB` or `NO-OP`, with the patterns of [completeness-checks.md](references/completeness-checks.md).
2. `data-source-auditor` in `classify` mode grades each screen `REAL`, `MOCKED` or `HYBRID` and confirms it in a browser: change a row in the database and reload (Navree UI), or follow the request through the BFF (Next.js).
3. `journey-walker` at depth `top` walks 3 to 5 journeys taken from `EXECUTION_PLAN.md` `## Acceptance criteria`, with a reload, a sign-out and sign-in, and a role switch, and checks the database after every write.
4. The main agent writes `AUDIT_REPORT.md` with the verdict of [completeness-checks.md](references/completeness-checks.md) and one finding per `STUB`, `NO-OP`, `MOCKED` or `HYBRID` result.

## Score mode

1. If the seed lacks what rule BE-14 asks for (one account per role per agent, a second workspace with overlapping names, realistic volumes, totals computed from rows), dispatch `seed-data-architect` first and copy its accounts table into `EXECUTION_PLAN.md` `## Demo accounts`.
2. Run the passes below. Each agent writes `audit/<agent-name>.md` with `## Module scores` (`| Module | Score | Evidence |`, 0 to 10). Passes 3 and 4 need the running app and their own accounts (rule QA-3).
   1. Completeness: the agents of completeness mode.
   2. Data realism: `data-source-auditor` in `trace` mode, and the seed check: every count and total equals a query over the rows, volumes are in the hundreds where a real workspace has hundreds, each demo account signs in.
   3. Isolation: `tenancy-isolation-tester` on two workspaces, citing the result of `cargo test --test isolation`.
   4. End to end: `journey-walker` at depth `all`, `qa-flow-tester` in `matrix` mode and `link-crawler` in `crawl` mode.
   5. Quality and security: `repo-cartographer` when `audit/repo-cartographer.md` is missing or from another commit (its map is the input of `static-auditor`), then `static-auditor`, `dependency-auditor`, `ui-auditor` (mode `navree` or `next` from `front_end`), `module-structure-auditor` when `front_end: next`, and the sweeps of `verify-done.mjs --strict` (suppressions, raw markup, placeholders).
3. `module-readiness-rater` reads the pass reports and writes `AUDIT_REPORT.md` with `## Scores`, per [rubric.md](references/rubric.md).
4. Each finding of a module under 9 goes to its owner: `navree-module-builder` for backend and contract code, `navree-ui-screen-builder` for Navree UI screens, `nextjs-module-builder` for Next.js screens, `fix-applier` for one finding that names its file. A finding that needs a change in `contracts/<module>.md` goes to the main agent first (rule BLD-2).
5. Re-run only the passes that found the fixed findings, then rewrite `AUDIT_REPORT.md`; the `Mode:` line carries the round, for example `score (round 2)`.
6. After the third round, the open findings go to the operator, who accepts them in writing or sets the order (rule BLD-6).

## Rules

- **AUD-1** Every score and verdict cites its evidence: a command and its result line, a file and line, a screenshot path or a response excerpt. A score without a citation is 0.
- **AUD-2** A module's score is the lowest of its pass scores. An open `Blocker` caps it at 3. A suppression added since `base_commit` caps it at 7. `READY` means 9 or more.
- **AUD-3** Fixes go to the root cause (hard rule 15): no suppression, no new demo data to pass a check, no lowering of the bar after the last round.
- **AUD-4** A screen that shows a hard-coded value where the contract says it comes from the database is `HYBRID`, and its finding is `Major`.
- **AUD-5** A finding closes only when the pass that found it runs again and passes.
- **AUD-6** Inventory counts come from the router, the migrations and the files on disk, never from the plan or from memory.

## Reference files

| File | Read when |
|---|---|
| [references/rubric.md](references/rubric.md) | Scoring a module, and writing `AUDIT_REPORT.md` in any mode |
| [references/completeness-checks.md](references/completeness-checks.md) | Hunting placeholders, grading controls and screens, giving the verdict |
