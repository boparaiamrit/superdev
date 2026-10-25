# QA_COVERAGE.md — format

One file at the repo root. Sections are numbered by what fills them (gate steps in brackets). Every row has a status (`PASS`, `FAIL`, `NOT RUN`, `N/A`) and an evidence column quoting the key result line plus the file under `qa/`. `N/A` needs a one-line reason. Re-running a cell replaces its evidence; the file never claims a pass it cannot point to.

```markdown
# QA coverage

Commit: a1b2c3d · Started: 2026-10-25 10:05 · Fresh seed: `pnpm db:fresh` (10:02)
verify-done: `verify-done.mjs --suites --strict` → DONE, 31 ✓ 0 ✗ (qa/verify-done.txt)
Final reset: `pnpm db:fresh` (16:40)

## Accounts used (one agent per account)
| Role / persona | Account | Used by |
| Owner | owner.a@example.com | route sweep |
| Owner | owner.b@example.com | money-integrity-prober |
| Least-privileged staff role | caller.a@example.com | route sweep, role-matrix-tester (read only) |
| End user A (city X) | user.a@example.com | web sweep |
| End user B (city Y, restricted) | user.b@example.com | realtime-prober |
| Phone | user.c@example.com | mobile-qa-tester (emulator-5554) |

## 1. Machine layer and suites [2]
| Suite | Command | Status | Evidence |
| verify-done | node …/verify-done.mjs --suites --strict | PASS | 31 ✓, 0 ✗ — qa/verify-done.txt |
| contract | pnpm --filter api test:contract | PASS | 38 passed, 0 failed |

## 2. Route × role × viewport × theme [3]
| App | Route | Role | Viewport | Theme | Expect | Status | Console errors | Overflow | Evidence |
| web | /dashboard | end user | 1280 | light | page | PASS | 0 | none | qa/web/dashboard-user-1280-light.png |
| web | /dashboard | end user | 375 | dark | page | PASS | 0 | none | qa/web/dashboard-user-375-dark.png |
| admin | /credits | marketer | 1280 | light | 403 state | PASS | 0 | none | qa/admin/credits-marketer-1280-light.png |

## 3. Interactions [4]
| App | Item | Check | Status | Evidence |
| web | Login form | empty, invalid, valid, double submit, keyboard | PASS | qa/web/forms/login.log |
| all | Internal links | crawl as each role | PASS | dead links: 0 of 214 — qa/links/REPORT.md |
| admin | Skipped destructive/money buttons (14) | handed to role-matrix-tester / money prober | PASS | see §6, §7 |

## 4. Accessibility and contrast [5]
| App | Route | Role | Viewport | Theme | axe violations | Lowest contrast (element, state) | Status | Evidence |
| web | /leads | end user | 375 | dark | 0 | 4.8:1 (filter chip, hover) | PASS | qa/a11y/raw/web-leads-375-dark.json |
| phone | Leads | end user | device | light | 0 | 5.1:1 (tab bar, selected) | PASS | qa/a11y/phone-leads.json |

## 5. UI/UX consistency [6]
| Area | Check | Status | Evidence |
| Buttons | one size scale, one primary per screen | PASS | QA_CONSISTENCY.md §1 |

## 6. Security behaviours (browser) [7]
| Behaviour | Status | Evidence |
| Masked contact for roles without reveal | PASS | … |
| Reveal audited with staff name | PASS | … |
| Block ends open tab with reason (< 2 s) | PASS | … |
| Two tabs refresh together, both signed in | PASS | … |

## 7. Money [8]
| Check | Status | Evidence |
| Double-click on every money button → one effect | | |
| Balances restored net zero | | |
| Reconciliation after the whole QA run [12] | | |

## 8. Live updates [9]
| From → to | Event | Latency | Status | Evidence |
| admin → web | new item | 33 ms | PASS | … |
| web → phone | read sync | 900 ms | PASS | … |

## 9. Phone (device) [10]
One row per line of each `apps/mobile/qa/<area>/RESULTS.md`, or one row per area quoting its pass count.
| Area | Device / build | Steps | Status | Evidence |
| sign-in | emulator-5554, debug APK 1.4.0 (sha256 …) | 9/9 | PASS | apps/mobile/qa/sign-in/RESULTS.md |
| final-smoke | QA-signed release APK | 7/7 | PASS | apps/mobile/qa/final-smoke/RESULTS.md |

## 10. Performance [11]
| Route | LCP | CLS | TBT | Queries/request | Status | Evidence |

## Findings
| ID | Severity | Where | What | Owner | Status (Open/Fixed/Accepted) | Fix commit | Re-run evidence |

## Not run (needs operator acceptance)
| Cell | Why | Accepted by (operator) | Date |
| iOS build and device pass | no Mac on this host | — | — |
```

## Enumerating routes

- Next.js: list `src/app/**/page.tsx` (exclude route groups' parentheses in the URL; expand dynamic segments with seeded ids). Inertia: `php artisan route:list --json` for GET routes rendering pages.
- Admin: the same, plus the permission each page needs (from the menu/permission map).
- Phone: the router's route table.
- Cross-check against the navigation: every menu item reaches a route in the list; every route is reachable from somewhere or is intentionally deep-linked only.

## Roles

Every seeded staff role, at least two end users with different scopes (to prove filtering), and a signed-out visitor (public pages and redirects). If roles are editable, also test one custom role created during QA.

## Viewports and themes

1280 × 800 and 375 × 800 for every route, in every theme the app ships (light, dark). The full screenshot set is the input to the consistency check (§5); keep the names `<route>-<role>-<width>-<theme>.png`.
