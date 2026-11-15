# Audit rubric and report format

Read this for score mode and for the `AUDIT_REPORT.md` format in every mode. Rules AUD-1 and AUD-2 in [SKILL.md](../SKILL.md) say how a score is earned and capped; the severity scale and the status words are in [artifacts.md](../../superdev-build/references/artifacts.md).

## Score bands

A pass score comes from the findings still open in that pass. A finding in state `accepted` (the operator's name, date and reason are in the report) does not count as open. A main path is a route or screen used by an acceptance criterion in `EXECUTION_PLAN.md`.

| Score | Open findings in the pass | Evidence the score needs |
|---|---|---|
| 10 | none | every check of the pass cited |
| 9 | only `Minor` and `Note` | the checks cited, the `Minor` findings listed with owners |
| 8 or 7 | `Major` findings, all off the main paths: 8 for one, 7 for two or more | the failing checks cited |
| 6, 5 or 4 | a `Major` finding on a main path: 6 for one, 5 for two, 4 for three or more | the failing checks cited |
| 3, 2 or 1 | a `Blocker`: 3 for one, 2 for two, 1 for three or more | the finding ids |
| 0 | the pass did not run, or cites nothing | none |

A module is `READY` at 9 or more, which means no open `Blocker` or `Major` finding in any pass. The caps of rule AUD-2 apply after the lowest pass score is taken.

## What each pass checks

| Pass | Checks | Evidence for a 9 or 10 |
|---|---|---|
| 1 Completeness | no placeholder; every control `WIRED`; every screen `REAL` ([completeness-checks.md](completeness-checks.md)) | the hunter's hit list (empty, or each hit with file and line); the classification table |
| 2 Data realism | each demo account signs in on a fresh seed; each count and total equals a query over the rows; no literal where a total belongs; volumes in the hundreds where a real workspace has them | the query result beside the screen value |
| 3 Isolation | a foreign record id answers 404 with the same body as a missing id; lists, search, exports, bulk actions, webhooks and screens hold only the caller's workspace; the database is unchanged after each attack | response excerpts; the result line of `cargo test --test isolation` |
| 4 End to end | every route loads with zero console errors; every form validates, stores and re-renders; data created in one step is visible after a reload and a new sign-in | screenshot paths and database rows |
| 5 Quality and security | `cargo fmt --all -- --check` and `cargo clippy --workspace --all-targets -- -D warnings` exit 0; no suppression since `base_commit`; no raw markup; no open `Blocker` or `Major` from the static checks | the lines of the `verify-done.mjs` output; the `static-auditor` report |

## AUDIT_REPORT.md

The main agent (completeness and inventory) or `module-readiness-rater` (score) writes it. `Mode:` is `inventory`, `completeness` or `score (round n)`. `Verdict:` is `PRODUCT`, `HYBRID` or `DEMO` in completeness mode, `READY` when every module is `READY` and `NOT READY` otherwise in score mode, and `none` in inventory mode. `## Inventory` appears in inventory mode only and `## Scores` in score mode only.

```markdown
# Audit Report

Mode: score (round 1)
Commit: 3f2a9c1
Date: 2026-11-22
Verdict: NOT READY

## Findings

| ID | Severity | Module | Where | Evidence | Owner | State |
|---|---|---|---|---|---|---|
| A-1 | Blocker | invoices | src/modules/invoices/controller.rs:48 | a member of Sharma Textiles, Pune read an invoice of Sandhu Traders, Ludhiana: HTTP 200 (audit/tenancy-isolation-tester/invoice-read.txt) | navree-module-builder | open |
| A-2 | Major | customers | `/customers` | the screen shows 0 open invoices for Sandhu Traders, Ludhiana; a count over the rows gives 14 (audit/data-source-auditor/customers.png) | navree-ui-screen-builder | open |
| A-3 | Minor | invoices | `/invoices/new` | the due-date hint reads "dd/mm/yyyy" and the field takes ISO dates | navree-ui-screen-builder | open |

## Scores

| Module | Pass 1 | Pass 2 | Pass 3 | Pass 4 | Pass 5 | Score | READY/NOT READY | Evidence |
|---|---|---|---|---|---|---|---|---|
| customers | 6 | 6 | 10 | 9 | 9 | 6 | NOT READY | A-2 |
| invoices | 9 | 9 | 3 | 9 | 9 | 3 | NOT READY | A-1; audit/tenancy-isolation-tester.md |
```

Each finding has an id, a severity, where, evidence and an owner; a finding without evidence is not reported. `State` is `open`, `fixed` or `accepted`; an accepted finding quotes the operator's words, name and date. Ids are never reused within the file. In score mode a row's `Evidence` cell names the findings that set the score or the report that supports a 9 or 10.
