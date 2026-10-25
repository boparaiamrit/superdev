---
name: release-qa-gate
description: Use when a full build is functionally complete and someone asks whether it is ready, tested, safe to demo or ship — "have you done QA", "UI/UX QA", "functionality QA", "test everything", "check every page", "contrast", "dead links", "every button works", "test as each role", "test the phone app" — or before any superdev-build completion claim. Applies to web, admin and Tauri clients together.
---

# Release QA gate — everything covered, every cell cited

`exploratory-qa` hunts for what nobody thought of. This gate proves everything somebody **did** think of: every route, as every role, at every viewport and theme, on every client, with every committed suite green on a fresh seed. The output is `QA_COVERAGE.md` ([format](references/coverage-matrix.md)), a matrix in which **every cell cites evidence** (a command and its result line, a screenshot path, a log). A cell without evidence is `NOT RUN`, and `NOT RUN` blocks release exactly like `FAIL`.

`superdev-done` alone is the machine layer, not this gate. `production-readiness-audit` and `brutal-exhaustive-audit` are deeper audits chosen by risk in superdev-build Step 6; they run **before** this gate, and their results count here only for cells they recorded on the same commit and seed.

## Before starting

- **Record the commit** (`git rev-parse --short HEAD`) at the top of `QA_COVERAGE.md`. A code change after a cell ran makes that cell stale: re-run every cell the change can reach (a shared token or component → that component's contrast and screenshots on every route; an API change → the suites and that module's cells).
- **Accounts.** The demo seed must provide one account per role **per parallel agent**, plus one end user per phone run. List who uses which account in the matrix; no account appears under two agents.
- **Dispatching agents.** Agent files cite references as `../skills/…`, relative to the plugin's `agents/` folder. Pass each agent absolute paths (the plugin root the host loaded — `${CLAUDE_PLUGIN_ROOT}` where the host sets it — plus `skills/…`), the app URLs, its accounts and its evidence folder. If an agent type is not available in this session, read its file and run its procedure yourself.

## The gate, in order

| # | Step | Owner | Fills |
| --- | --- | --- | --- |
| 1 | **Fresh, realistic data:** `db:fresh` (drop, migrate, demo seed — superdev-build Step 3 defines it). Use the project's demo seed, not the synthetic dataset `qa-environment` generates. Confirm reconciliation and contract checks pass on the seed. | main agent | header, accounts |
| 2 | **Machine layer:** `node <plugin>/scripts/verify-done.mjs --suites --strict`, output saved to `qa/verify-done.txt`. All green or stop and fix. | main agent | §1 |
| 3 | **Route × role × viewport × theme:** every route of every web app and every screen of every client, per [`references/ui-sweeps.md`](references/ui-sweeps.md). Allowed → content; forbidden → the friendly forbidden state; zero console errors; no horizontal scroll at 375 px. | main agent, or `qa-flow-tester` per app | §2 |
| 4 | **Interactions:** every form (empty, invalid, valid, double submit), dialog and menu (keyboard, focus); every internal link and every button does something real. | `link-crawler` (links, inert buttons), `qa-flow-tester` (forms, dialogs) | §3 |
| 5 | **Accessibility and contrast:** axe on every route × role × theme × viewport, plus computed contrast in every interactive state and every badge/tag pair, on the web apps and inside the phone WebView. | `a11y-contrast-auditor` | §4 |
| 6 | **UI/UX consistency:** the same component looks and behaves the same everywhere; one primary action per screen; empty, loading and error states present and worded alike. | `qa-consistency-checker` (reads step 3–5 screenshots) | §5 |
| 7 | **Security behaviours in the browser:** masks for roles without reveal; reveal works and is audited; role change applies live; revoke and block end open tabs with the reason; two tabs refreshing together stay signed in. Also the destructive and money buttons `link-crawler` skipped. | `role-matrix-tester` | §6 |
| 8 | **Money and concurrency:** double-clicks on every money button → one effect; races at the last unit; balances restored net zero. | `money-integrity-prober` | §7 |
| 9 | **Live updates across clients:** a change in one app appears in the others within seconds; notifications arrive once, grouped; read state syncs. | `realtime-prober` | §8 |
| 10 | **Phone on a device:** the playbook in `design-to-tauri/references/device-qa.md` (final-pass list). | `mobile-qa-tester`, one device each | §9 |
| 11 | **Performance:** Web Vitals per main route, no N+1 on list endpoints, no client-side filtering of large lists. Runs **alone, after** steps 3–10, on an idle stack. | `qa-performance-prober` | §10 |
| 12 | **Close:** reconciliation after everything above; findings fixed at root cause and stale cells re-run; if code changed, step 2 again on the final commit; then `db:fresh` as the **last** command, recorded in the header. | main agent | Findings, header |

Steps 3–10 may run in parallel only under these rules:

- each agent has its own accounts and labels the records it creates with its name;
- one emulator or phone per `mobile-qa-tester`; no two agents drive the same device;
- every agent shares one IP: sign in **once per role** and reuse the session; on 429 wait for `Retry-After` and retry — never raise a rate limit for QA;
- the money prober records starting balances and restores them; reconciliation runs only after every agent has finished;
- after an API restart, wait for health and re-run the interrupted cell — it is not an app failure.

## Status, severity and acceptance

Cells use exactly four statuses: `PASS`, `FAIL`, `NOT RUN`, `N/A` (with a one-line reason).

| Severity | Meaning | Cell | Release |
| --- | --- | --- | --- |
| Blocker | Data leak, wrong money, a security control not working, a role can do what it must not, crash on a main path | `FAIL` | Blocks |
| Major | A main task cannot be completed, dead link or button on a main path, text contrast below AA, phone app unusable on a supported screen | `FAIL` | Blocks |
| Minor | Cosmetic, edge copy, a non-main path | `PASS` with the finding id | Listed with an owner |
| — | No evidence | `NOT RUN` | Blocks unless accepted |

Only the operator — the person who asked for the build — can accept a `NOT RUN` (for example iOS without a Mac). Acceptance is their name, the date and the reason in the matrix's "Not run" table; an agent never fills it.

Evidence lives under `qa/` at the repo root (gitignored). Each cell quotes its key result line (`31 ✓, 0 ✗`, `dead links: 0`, `lowest 4.9:1`) so the matrix can be reviewed without the files; attach or commit the folder only when the operator asks.

## Common mistakes

- Running QA on a database the build has been mutating for hours — results do not transfer to a fresh install. Reset first and last.
- Answering "have you done QA?" with `verify-done` alone. That is step 2 of twelve.
- Testing only as the most powerful role. Most leaks are visible only to the least powerful one.
- Contrast measured only at rest, or focus forced with `el.focus()` (no `:focus-visible`). Hover, focus and disabled states fail most often.
- Agents sharing an account or a device; one blocks it while another is mid-test.
- "The phone app works" from a browser at 390 px.
- Treating a scripted suite pass as browser proof, or the reverse. Both layers are required.
- Fixing a shared token and re-running only the page where the finding was reported.

## Reference files

| File | Read when |
| --- | --- |
| [`references/coverage-matrix.md`](references/coverage-matrix.md) | Building `QA_COVERAGE.md` |
| [`references/ui-sweeps.md`](references/ui-sweeps.md) | Steps 3–5 and 9: Playwright recipes for routes, links, forms, axe, contrast states, live checks |
