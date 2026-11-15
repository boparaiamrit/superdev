---
name: product-qa
description: Use when a build is functionally complete and someone asks whether it is tested or ready to demo or ship (have you done QA, check every page, contrast, dead links, every button works, test as each role, test the phone app), or to explore the running app for what tests miss. Runs in explore mode or gate mode; the gate writes a coverage matrix in which every cell cites evidence.
---

# Product QA

This skill tests the running app in a real browser, in two modes. `explore` mode looks for what nobody thought of and writes `QA_REPORT.md`. `gate` mode proves what somebody did think of: every route, as every role, at two widths and in both colour modes, on every client, with every committed suite green on a fresh seed. Its result is `QA_COVERAGE.md`, a matrix in which every cell cites evidence. It is step 8: explore mode (optional) runs first, and gate mode is always the last check before deployment. Navree's `navree-browser-testing` skill covers browser tests written in Rust; the sweeps here are the browser proof that the committed suites do not give (rule QA-8).

## Modes

| Mode | Use it when | Writes |
|---|---|---|
| `explore` | any time after the modules exist, to find missing states, inconsistencies and slow paths | `QA_REPORT.md`, evidence under `qa/` |
| `gate` | before deployment, and whenever someone asks whether the build is ready | `QA_COVERAGE.md`, evidence under `qa/` |

The `verify-done.mjs` run ([superdev-done](../superdev-done/SKILL.md)) is step 2 of the gate. It is not the gate.

## Before either mode

- Reset the data with `navree migrate:fresh --seed` and run the release binary with `serve` and its worker, `<binary> queue:work`. For `front_end: next`, also run the web app built and started in production mode.
- Write the commit (`git rev-parse --short HEAD`) at the top of the report. A code change after a cell ran makes that cell stale (rule QA-2).
- Use one account per role per agent from the seed (rule BE-14), and one end user per phone run. List who uses which account in the report; no account appears under two agents.
- Dispatch each agent with absolute paths (rule BLD-4), its accounts, the app URL and `out_dir: qa`. Evidence goes under `qa/<agent-name>/`, a git-ignored sub-folder; `QA_REPORT.md`, `QA_COVERAGE.md`, each `qa/<agent-name>.md` and `qa/verify-done.txt` are committed.
- Browser agents install a pinned Playwright release in a scratch folder, because agents shipped in a plugin cannot declare MCP servers. Navree UI targets Chrome 135 and later, so the release must bring Chromium 135 or newer. [references/ui-sweeps.md](references/ui-sweeps.md) has the recipes.

## Explore mode

1. `qa-environment` checks that the app is healthy (`/health/live`, `/health/ready`, a running worker, the web app for Next.js), adds edge records on top of the demo seed through the app's own routes (rule QA-9) and takes baseline screenshots.
2. One `qa-flow-tester` per module, in `happy` mode first and then `edges`, using the categories of [explore-checklist.md](references/explore-checklist.md).
3. `qa-consistency-checker` runs the consistency checks of the same file over the screenshots and the source.
4. `qa-performance-prober` runs alone, last, on an idle app (rule QA-7).
5. The main agent writes `QA_REPORT.md` in the format of [explore-checklist.md](references/explore-checklist.md). Fix `Blocker` and `Major` findings at the root cause before the gate; the gate starts from a fresh seed either way.

## Gate mode

The gate runs these steps in this order. The matrix format is in [coverage-matrix.md](references/coverage-matrix.md).

| # | Step | Owner | Fills |
|---|---|---|---|
| 1 | Fresh data: `navree migrate:fresh --seed`; reconciliation and contract suites pass on it | main agent | header, accounts |
| 2 | Machine layer: `node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs --suites`, saved to `qa/verify-done.txt` (without `--strict`: the reports it reads are not written yet) | main agent | §1 |
| 3 | Routes × roles × widths (1440, 390) × modes (light, dark): allowed shows content, refused shows the friendly refusal, zero console errors, no horizontal scroll at 390; Navree UI pages pass the render check (rule QA-10) | main agent or `qa-flow-tester` | §2 |
| 4 | Interactions: every form (empty, invalid, valid, double submit), dialog and menu; every link and button does something | `link-crawler`, `qa-flow-tester` | §3 |
| 5 | Accessibility and contrast in every state | `a11y-contrast-auditor` | §4 |
| 6 | Consistency from the step 3 to 5 screenshots | `qa-consistency-checker` | §5 |
| 7 | Security in the browser: masks, reveal audited, live role change, sign-out and block end open tabs | `role-matrix-tester` | §6 |
| 8 | Money and concurrency | `money-integrity-prober` | §7 |
| 9 | Live updates across clients | `realtime-prober` | §8 |
| 10 | Native clients on a device (when `clients` has a Tauri client), per [device-qa.md](../design-to-tauri/references/device-qa.md) | `mobile-qa-tester`, one device each | §9 |
| 11 | Performance, alone, after steps 3 to 10 | `qa-performance-prober` | §10 |
| 12 | Close: fix at the root cause and re-run stale cells; step 2 again if code changed; `navree migrate:fresh --seed` as the last command | main agent | Findings, header |

## Parallel rules

Steps 3 to 10 may run in parallel only under rule QA-3, except that steps 7 and 8 start after step 4: they use the destructive and money buttons that `qa/link-crawler.md` lists as skipped. Step 11 never runs beside anything else (rule QA-7).

## Status, severity and acceptance

Every cell is `PASS`, `FAIL` or `NOT RUN`. The severity scale, the finding fields and the status words are defined once, in [artifacts.md](../superdev-build/references/artifacts.md).

- A `Blocker` or `Major` finding makes its cell `FAIL`. A `Minor` finding marks its cell `PASS (Q-n)` with the finding's id, never a bare `PASS`, and is listed with an owner.
- A cell with no evidence is `NOT RUN`. A cell whose server answer was proved over HTTP and whose browser half is `NOT RUN` is `PASS (server)` ([coverage-matrix.md](references/coverage-matrix.md)). A `NOT RUN`, and the browser half of a `PASS (server)`, block like a `FAIL` until the operator accepts them in `ACCEPTANCES.md`; the cell then cites the entry, `NOT RUN (ACC-n)` or `PASS (server, ACC-n)`, and `## Not run` lists it with the same `ACC-n`. An agent never writes an acceptance and copies no sentence of one (rule BLD-6): it returns the question to the operator. A `FAIL` cannot be accepted: it is fixed and its cell re-run.
- The gate passes only when `QA_COVERAGE.md` has no `FAIL`, no `NOT RUN` and no `PASS (server)` without an `ACC-n`, and no open `Blocker` or `Major` finding in its `## Findings` table. Otherwise the result is not a pass, and the file says which cells and findings are in the way. `verify-done.mjs --strict` reads the file and fails on each of these.

## Rules

- **QA-1** Every cell cites evidence: a command and its result line, a screenshot path or a log line. A cell without evidence is `NOT RUN`.
- **QA-2** Fresh data first and last. A code change after a cell ran makes it stale; re-run every cell the change can reach (a shared token or component reaches every page that uses it, an API change reaches that module's cells and the suites).
- **QA-3** Each parallel agent owns its accounts and labels the records it creates with its name. One device per phone tester. Sign in once per role through the real form and reuse that session inside the one agent that owns the account. On a 429, wait for `Retry-After` and retry; never raise a rate limit for QA. The money prober records starting balances and restores them, and reconciliation runs only after every agent has finished. After an API restart, wait for `/health/ready` and re-run the interrupted cell; it is not an app failure.
- **QA-4** Every route is tested as the least powerful role too.
- **QA-5** Contrast is measured in every state (rest, hover, keyboard focus, active, disabled, selected) after transitions end: 4.5:1 for text, 3:1 for large text and controls.
- **QA-6** At 390 px: no horizontal page scroll, tables scroll inside their container, tap targets at least 44 CSS px, dialogs fit.
- **QA-7** Performance runs alone, last, on an idle app.
- **QA-8** What the committed suites prove is cited, not re-tested. A suite pass is not browser proof, and a browser pass is not a suite.
- **QA-9** Explore mode adds edge records on top of the demo seed. It never replaces the seed the gate uses.
- **QA-10** A rendered Navree UI page has no `style` attribute, no `<style>` element and no `<script>` element other than the framework's own, whose `src` starts with `/_navree/ui/`, because the runtime picks its script modules from the rendered tree (hard rule 14).

## Reference files

| File | Read when |
|---|---|
| [references/coverage-matrix.md](references/coverage-matrix.md) | Building `QA_COVERAGE.md`: format, listing routes and roles |
| [references/ui-sweeps.md](references/ui-sweeps.md) | Gate steps 3 to 5 and 9: browser recipes for routes, links, forms, axe, contrast states, the render check, live latency |
| [references/explore-checklist.md](references/explore-checklist.md) | Explore mode: edge categories, consistency checks, performance table, `QA_REPORT.md` |
