# QA_COVERAGE.md format

One file at the app root, written by the main agent and the QA agents. Sections are numbered by what fills them, with the gate step in brackets. Every row has a status (`PASS`, `FAIL` or `NOT RUN`) and an evidence cell holding the key result line and the path under `qa/`. A matrix lists only the cells that apply, and each section states its applicability rule once. A section with nothing to test keeps its heading and one line giving the reason. Re-running a cell replaces its evidence. The status words, the severity scale and the finding ids are defined in [artifacts.md](../../superdev-build/references/artifacts.md).

```markdown
# QA Coverage

Commit: a1b2c3d
Seed: `navree migrate:fresh --seed` at 2026-11-24 10:02 IST
Final reset: `navree migrate:fresh --seed` at 16:40 IST

## Accounts
| Role | Account | Workspace | Used by |
|---|---|---|---|
| owner | harpreet.sandhu@example.com | Sandhu Traders, Ludhiana | route sweep |
| viewer | arjun.mehta@example.com | Sharma Textiles, Pune | route sweep, role-matrix-tester |

## 1. Machine layer and suites [2]
Applies to: `verify-done.mjs`, then each suite line of `STACK.md` `## Suites`.
| Check | Command | Status | Evidence |
|---|---|---|---|
| verify-done | `node .../verify-done.mjs --suites --strict` | PASS | DONE: all live checks and committed suites green (qa/verify-done.txt) |

## 2. Routes, roles, widths, modes [3]
Applies to: each route a role can reach (Expect `page`) and each route it must be refused (Expect `refusal`), at 1440 and 390 px, in light and dark mode.
| Client | Route | Role | Width | Mode | Expect | Status | Console errors | Overflow | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| web | `/invoices` | owner | 1440 | light | page | PASS | 0 | none | qa/web/invoices-owner-1440-light.png |
| admin | `/admin` | viewer | 390 | dark | refusal | PASS | 0 | none | qa/admin/admin-viewer-390-dark.png |

## 3. Interactions [4]
Applies to: every form, dialog and menu, and a link crawl per role.
| Client | Item | Check | Status | Evidence |
|---|---|---|---|---|
| web | New invoice form | empty, invalid, valid, double submit, keyboard | PASS | qa/web/forms/new-invoice.log |

## 4. Accessibility and contrast [5]
Applies to: the rows of section 2 with Expect `page`.
| Client | Route | Role | Width | Mode | axe violations | Lowest contrast (element, state) | Status | Evidence |
|---|---|---|---|---|---|---|---|---|
| web | `/invoices` | owner | 390 | dark | 0 | 4.8:1 (filter chip, hover) | PASS | qa/a11y-contrast-auditor/raw/invoices-390-dark.json |

## 5. Consistency [6]
Applies to: the consistency checks of explore-checklist.md, one row each.

## 6. Security in the browser [7]
Applies to: masks, audited reveal, live role change, sign-out and block ending open tabs.

## 7. Money [8]
Applies to: a product with balances or payments (`tests/money.rs` exists).

## 8. Live updates [9]
Applies to: each live region and notification the plan lists.
| From, to | Event | Latency | Status | Evidence |
|---|---|---|---|---|
| admin, web | invoice marked paid | 33 ms | PASS | qa/realtime-prober/paid.log |

## 9. Native clients [10]
Applies to: each Tauri client in `STACK.md` `clients`, one row per area of the device pass.

## 10. Performance [11]
Applies to: each main route. Columns: Route, LCP, CLS, Queries (1 row and 50 rows), Status, Evidence.

## Findings
| ID | Severity | Module | Where | What | Expected | Evidence | Owner | State |
|---|---|---|---|---|---|---|---|---|

## Not run
| Cell | Why | Operator's words | Name | Date |
|---|---|---|---|---|
| native client on iOS | no Mac on this host | | | |
```

Sections 5, 6 and 7 use the columns `| Area or behaviour | Check | Status | Evidence |`. Section 9 uses `| Area | Device and build | Steps | Status | Evidence |`, with the step count quoted as `9/9`, and its rows come from the results file of the device pass ([device-qa.md](../../design-to-tauri/references/device-qa.md)). The consistency checks are in [explore-checklist.md](explore-checklist.md). A finding's `State` is `open` or `fixed`.

## Listing routes

- Navree UI and API: `navree routes --json` lists every route with its access. The page routes are the GET routes drawn by Navree UI, declared with a `!` prefix; `navree routes --json` shows them with `"page": true` and their address, which has no `!`, and the matrices use the address. Fill dynamic segments with seeded ids.
- Next.js: `web/app/**/page.tsx`; a folder in parentheses is a route group and is not part of the URL.
- Staff panel: `/admin` and each resource registered with `navree make:resource`, read from the panel's menu. Tauri clients: the router table of each client.
- Cross-check with the navigation: every menu item reaches a route of the list, and every route is reachable from somewhere or is reached only by a deep link.

## Roles

Every global role and every workspace role in `EXECUTION_PLAN.md` `## Access`, at least two end users in different workspaces (to prove scoping), and a signed-out visitor (public pages, and the redirect to sign-in). When roles can be edited, also one custom role created during the run.

Widths are 1440 and 390 px, in every colour mode the client ships (Navree UI is dark by default and has a light mode). Screenshots are named `<route-slug>-<role>-<width>-<mode>.png`, under `qa/<client>/` when the main agent takes them and in the agent's own folder (`qa/<agent-name>/`) otherwise. They are the input of the consistency check.
