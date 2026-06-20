---
name: production-readiness-audit
description: Use to take a "looks done" product to genuinely production-ready by scoring EVERY module 1–10 across five audit passes, then looping fix→re-audit until every module scores 9+. This is the skill to invoke whenever the user says "rate each module 1 to 10", "check production readiness", "complete the product fully", "what's left before we ship", "make it production ready", or asks for completeness/parity/tenancy/seed-data work. It enforces the hard requirements that real builds always need and always forget: zero lint/type suppressions (fix the root cause, never disable), proper seed data plus an initial product (admin/owner) user, a multi-tenancy leakage test, and exhaustive Playwright coverage of every route, every form, and every data shape on both frontend and backend. Runs at the end of orchestrator Phase D and writes per-module scores + the `readiness` gate into COMPLETION_LEDGER.json so the done-gate cannot pass until all modules are 9+. Do NOT use for a single-component tweak or a quick sanity check — this is the heavy, iterative, whole-product readiness loop.
---

# Production Readiness Audit

The skill that answers the only question that matters before shipping: **"Is every module actually production-ready — scored, proven, and fixed — or does it just look done?"**

Real builds stall at ~70% because "done" is self-asserted. This skill replaces the assertion with a **scored, looping, evidence-backed process**: every module is rated 1–10 across five passes, every gap becomes a checklist item, agents fix the items, and the audit re-runs until **every module scores 9+**. Nothing is taken on faith — data is proven real, tenancy is proven isolated, every route/form/data-shape is proven working in a real browser against a real backend.

## The Iron Law

```
EVERY MODULE SCORED 1–10. NOTHING SHIPS BELOW 9.
LOOP fix → re-audit UNTIL EVERY MODULE IS 9+.
NO LINT/TYPE SUPPRESSIONS — fix the root cause, never disable.
REAL SEED DATA + AN INITIAL PRODUCT USER. TENANCY PROVEN ISOLATED.
EVERY ROUTE, EVERY FORM, EVERY DATA SHAPE EXERCISED IN PLAYWRIGHT (FE + BE).
```

A 9 means: a paying user could rely on this module today. An 8 is not "almost there" — it is "not done", and it goes back into the loop.

## When to use

- ✅ End of orchestrator Phase D, as the capstone gate before any "ready to ship" claim
- ✅ User asks to "rate each module 1–10", "check completeness", "complete it fully for production", "what's left to ship"
- ✅ Before a stakeholder/PM walkthrough where things must actually work
- ✅ After a brownfield→production migration, to prove nothing is still demo/mock

## When NOT to use

- ❌ A single-component visual tweak (use `frontend-modular-architecture` / `design-review`)
- ❌ Debugging one specific bug (use `systematic-debugging`)
- ❌ A quick sanity check (this is the heavy iterative machinery — expect many agent dispatches and tokens)

## How the orchestrator runs it

This runs **after** `integration-tester`, `security-review-and-fix`, and `exploratory-qa` have each produced their artifacts, and it **subsumes and finalizes** `product-completeness-audit` + `brutal-exhaustive-audit` into a single scored loop. The orchestrator (the main session) drives the loop; it reads `.claude/memory/superdev-learned/` first and threads relevant lessons into every dispatch.

Preconditions the orchestrator verifies before scoring (a build cannot be rated if these are absent):

1. **Stack is up in production mode** (`NEXT_PUBLIC_API_MODE=production` / `MAIL_PROVIDER`/`BILLING_PROVIDER` set to real-or-env-switched), not demo mode.
2. **Seed data + an initial product user exist** — dispatch `seed-data-architect` first if not. The product must be usable on a fresh DB with a real owner/admin login, realistic volumes, and zero hardcoded fallbacks.

## The five passes

Each pass scores **every module** 0–10 on one dimension and emits findings. The passes reuse superdev's existing specialist agents plus three readiness-specific agents. Run the scanning passes (1, 2, 5-static) in parallel; the browser passes (3, 4) need the stack up.

| # | Pass | Dimension | Agents |
|---|------|-----------|--------|
| 1 | **Completeness & wiring** | Every route renders real data; every button/form/menu hits a real API; no placeholders, stubs, `alert()`, or demo-fallbacks on success paths | `placeholder-hunter`, `route-completeness-checker`, `wiring-auditor`, `data-flow-real-vs-mock` |
| 2 | **Data realism & seed** | Real seed data at realistic scale; an initial product (owner/admin) user that can log in; aggregate counts computed from the DB (never hardcoded 0); product works with demo mode OFF | `seed-data-architect`, `data-flow-real-vs-mock` |
| 3 | **Tenancy isolation** | With ≥2 seeded tenants, tenant A cannot read / list / search / export / mutate / enumerate tenant B's data via API or UI (IDOR on every `:id`, list scoping, search, webhooks). **Any leak caps the module at ≤3.** | `tenancy-isolation-tester` |
| 4 | **End-to-end (Playwright)** | Every route loads; every form validates → submits → **persists (DB-verified)** → re-renders; data-shape parity FE↔BE (no `undefined` in any view; contract == API == UI); happy + 13 edge categories | `route-walker`, `qa-flow-tester`, `journey-walker`, `edge-case-prober`, `data-flow-tracer` |
| 5 | **Code quality & security** | Zero lint errors and zero type errors with **no suppressions** (`eslint-disable`/`@ts-ignore`/`as any`/`@phpstan-ignore`); authz enforced (CASL/Policies), input validated, no secrets in code, no god-files. **Any P0 security/data-loss caps the module at ≤3.** | `static-auditor`, `dependency-auditor`, `ui-auditor`, `module-structure-auditor` |

See [`references/five-pass-audit.md`](references/five-pass-audit.md) for the exact dispatch prompts per pass.

## Scoring — module readiness is the WEAKEST pass

```
module_score = min(pass1, pass2, pass3, pass4, pass5)
```

A module is only as production-ready as its weakest dimension — a beautiful, fully-wired UI with a tenancy leak is **not** an 8, it is a 3. Hard caps make disqualifying findings impossible to average away: a tenancy leak (Pass 3) or a P0 security/data-loss bug (Pass 5) caps the module at ≤3 no matter how good everything else is.

`module-readiness-rater` reads all five pass reports for a module and emits its score + the consolidated, fix-ordered checklist. The full rubric (what 9–10 vs 7–8 vs ≤6 means per dimension) is in [`references/rubric.md`](references/rubric.md). The rubric defines 9–10 as "production-ready, at most cosmetic nits" so `min` is honest, not trivia-driven.

## The loop (the heart of the skill)

```
round = 0
do:
  round += 1
  1. Run the five passes across all modules → per-module pass scores
  2. module-readiness-rater → READINESS.md (per-module score + verdict)
     and READINESS_CHECKLIST.md (every finding as a one-line, owned ticket)
  3. Update COMPLETION_LEDGER.json: features.<module>.readiness_score, gates.readiness
  4. If every module ≥ 9 → DONE, break.
  5. For each module < 9: dispatch the matching fixer (backend/frontend/laravel/
     inertia-module-builder, security-fixer) on THAT module's checklist items.
     Fix the ROOT CAUSE. No suppressions. No new demo data.
  6. Re-run ONLY the passes that scored < 9 for the fixed modules.
while (any module < 9 AND round < 5)

if any module still < 9 after round 5:
  STOP. Surface READINESS_CHECKLIST.md with the blocking items to the user —
  do not loop forever, and do not lower the bar.
```

The orchestrator dispatches; builders/fixers never chain. State lives in `READINESS.md`, `READINESS_CHECKLIST.md`, and `COMPLETION_LEDGER.json` — all on disk, so the loop survives context compaction. See [`references/readiness-checklist-format.md`](references/readiness-checklist-format.md).

## Hard requirements (non-negotiable, enforced by the passes)

- **No suppressions.** Pass 5 and the wave gate fail on any new `eslint-disable` / `@ts-ignore` / `@ts-expect-error` / `as any` / `as unknown as` / `@phpstan-ignore`. The fix is the root cause, every time. A module with suppressions cannot exceed 7.
- **Real seed + initial user.** Pass 2 fails if the product needs demo mode to function, if there is no seedable owner/admin login, or if any aggregate (`*_count`, totals) is hardcoded.
- **Tenancy isolation.** Pass 3 actively attacks cross-tenant boundaries; a single leak is a release blocker.
- **Exhaustive Playwright.** Pass 4 must touch *every* route and *every* form (not a sample) and DB-verify persistence; data-shape parity is checked on both sides of the wire.

## Integration with the done-gate

This skill is how the `completeness`, `qa`, `security`, `brutal`, and `readiness` gates in `COMPLETION_LEDGER.json` reach `pass`. The Stop-hook done-gate (`hooks/scripts/done-gate.sh`) requires `gates.readiness == pass` **and** every `features.<module>.readiness_score ≥ 9` before any completion claim is allowed. So this loop is not optional politeness — it is the only path to a legitimate "done". See [`../prd-design-build-orchestrator/references/done-gate.md`](../prd-design-build-orchestrator/references/done-gate.md).

## Completion gate

- [ ] Stack verified up in production mode; demo mode OFF
- [ ] Seed data + initial product (owner/admin) user present and login-verified
- [ ] All five passes ran for every module
- [ ] `READINESS.md` + `READINESS_CHECKLIST.md` produced
- [ ] **Every module scores ≥ 9** (or remaining blockers explicitly surfaced to the user)
- [ ] Tenancy isolation test passed (zero cross-tenant leaks)
- [ ] Playwright touched every route + every form; persistence DB-verified; FE↔BE data shapes match
- [ ] Zero lint/type errors with zero suppressions
- [ ] `COMPLETION_LEDGER.json`: `gates.readiness == pass`, all `readiness_score ≥ 9`

If any box is unchecked, the product is not ready and the done-gate will block the claim.

## Reference files

- [`references/rubric.md`](references/rubric.md) — the 1–10 scoring rubric per dimension
- [`references/five-pass-audit.md`](references/five-pass-audit.md) — exact dispatch prompts for each pass
- [`references/readiness-checklist-format.md`](references/readiness-checklist-format.md) — `READINESS.md` + `READINESS_CHECKLIST.md` formats and the ledger update
- [`references/agent-definitions.md`](references/agent-definitions.md) — the three readiness-specific agents
