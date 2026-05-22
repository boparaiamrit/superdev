# Fix Plan Format (Phase 5 + 6)

The template for `SECURITY_FIX_PLAN.md` and the triage workflow that produces it.

## The triage workflow (Phase 5)

The orchestrator (not a subagent) walks the human user through `SECURITY_FINDINGS.md` and produces decisions.

Order:

1. **All Critical findings** — present each one, get explicit fix-or-accept. Accepts must record justification.
2. **All High findings** — present each, default fix, defer-with-reason allowed.
3. **Medium summary** — show counts, group by file. User selects which to fix this pass; rest go to deferred.
4. **Low + Info** — recorded for future hygiene; user can opt to fix any of them now.

For each finding being fixed, the orchestrator decides:

- **Which agent applies it** — almost always `security-fixer`. Exceptions:
  - Secret rotation: USER (security-fixer can scrub the repo, but rotation at the issuer is manual)
  - Dep major upgrade: USER (breaking changes need human review)
  - Infra topology: USER or DevOps (DNS, WAF, LB rules)
- **Which files it can touch** — listed explicitly; the security-fixer is forbidden from straying
- **Acceptance criteria** — how to verify the fix landed
- **Dependent fixes** — some fixes must happen in a specific order (e.g., fix the env-schema validator before fixing the JWT secret)

## SECURITY_FIX_PLAN.md template

```markdown
# Security Fix Plan

> Generated: <ISO 8601>
> Sources: SECURITY_INVENTORY.md, SECURITY_FINDINGS.md
> Triage by: <user>

## Summary

- **Total findings:** 47
- **Critical:** 3 → all to be fixed
- **High:** 11 → 9 to be fixed, 2 deferred
- **Medium:** 21 → 8 to be fixed, 13 deferred
- **Low:** 9 → all deferred (next hygiene pass)
- **Info:** 3 → recorded only

**Build-blocking:** all Critical fixes must land before deployment.

## Fix order

Group fixes by file and by dependency. Within a group, fixes are sequential; across groups, parallel-dispatchable.

### Group 1 — Foundational (do FIRST)

These touch shared config; subsequent fixes assume they're in place.

#### F-1 — fix S-S-3: JWT secret length validation

- **Severity:** High (originally)
- **Files:** `apps/api/src/infrastructure/config/env.schema.ts`
- **Recommendation:** Change `JWT_ACCESS_SECRET: z.string()` to `z.string().min(32)`. Same for `JWT_REFRESH_SECRET`.
- **Acceptance:**
  - `grep -n "min(32)" env.schema.ts` finds both secrets
  - App boot fails with a clear error if either env var is shorter than 32 chars
- **Agent:** `security-fixer`
- **Dependencies:** none
- **Estimated touch:** 2 lines

### Group 2 — AuthZ gaps (do AFTER Group 1)

#### F-2 — fix S-S-7: Missing @CheckAbility on POST /companies

- **Severity:** Critical
- **Files:** `apps/api/src/modules/companies/companies.controller.ts`
- **Recommendation:** Add `@CheckAbility({ action: 'create', subject: 'Company' })` above the `create` handler at line 28.
- **Acceptance:**
  - The decorator is present
  - `pnpm --filter @<scope>/api test -- --testPathPattern=companies` passes
  - The Phase 3 probe for `POST /companies as Viewer` returns 403 (was 201)
- **Agent:** `security-fixer`
- **Dependencies:** none
- **Estimated touch:** 1 line

#### F-3 — fix S-S-8: Missing @CheckAbility on DELETE /companies/:id

- (similar structure)

### Group 3 — Tenancy fixes (do AFTER Group 2)

#### F-4 — fix S-S-12: Companies repository bypasses tenantDb

- **Severity:** Critical
- **Files:** `apps/api/src/modules/companies/companies.repository.ts`
- **Recommendation:** Replace `db.select().from(companies).where(eq(companies.id, id))` with `db.select().from(companies).where(t.scope('companies', eq(companies.id, id)))` where `t = tenantDb(db, workspaceId)`. Verify caller passes `workspaceId`.
- **Acceptance:**
  - grep for `db\\.select.*from\\(companies\\)` in this file returns no hits without `t.scope`
  - Phase 3 probe: workspace A's admin cannot fetch workspace B's company → returns 404
- **Agent:** `security-fixer`
- **Dependencies:** none
- **Estimated touch:** ~5 lines

### Group 4 — Frontend XSS hardening (parallel-safe with backend)

#### F-5 — fix S-S-21: dangerouslySetInnerHTML in CampaignPreview

- **Severity:** High
- **Files:** `apps/web/src/modules/campaigns/components/campaign-preview.tsx`
- **Recommendation:** Wrap rendered HTML in DOMPurify. Install `isomorphic-dompurify`, import and call `DOMPurify.sanitize(html)` before passing to `dangerouslySetInnerHTML`.
- **Acceptance:**
  - DOMPurify import present
  - The render uses `dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }}`
  - Visual smoke test in demo mode shows campaign preview still renders
- **Agent:** `security-fixer`
- **Dependencies:** none
- **Estimated touch:** 3 lines + 1 dep install

### Group 5 — Dep upgrades (parallel-safe)

#### F-6 — fix S-P-2: CVE in `xlsx` package

- **Severity:** High
- **Files:** `apps/api/package.json`
- **Recommendation:** Upgrade `xlsx` from 0.18.5 to 0.20.0 (patched). Run `pnpm --filter @<scope>/api update xlsx`.
- **Acceptance:**
  - `pnpm audit --prod --audit-level high` shows zero `xlsx` advisories
  - `pnpm --filter @<scope>/api test` passes
- **Agent:** `security-fixer`
- **Dependencies:** none
- **Estimated touch:** lockfile + 1 line in package.json

## Manual fixes (USER must apply)

Items the security-fixer cannot or should not handle alone.

### M-1 — Rotate leaked Anthropic API key

- **Severity:** Critical
- **Origin:** S-S-1
- **What the agent did:** Replaced `sk-ant-...` in `apps/api/src/modules/ai/clients/anthropic.client.ts` with `config.get('ANTHROPIC_API_KEY')`. Removed the hardcoded value from git history via `git filter-repo` (or BFG). Added the var to `.env.example` with placeholder.
- **What you must do:**
  1. Log into Anthropic Console → API Keys
  2. Revoke the key starting `sk-ant-X1234...` (last 4 chars: `Y789`)
  3. Generate a new key
  4. Add to `apps/api/.env` (NOT committed)
  5. Distribute to other developers via the team password manager
- **Acceptance:**
  - The leaked key, when used, returns 401 from Anthropic
  - The new key is in `.env` (gitignored) on every dev machine and the prod secret manager
  - `git log --all -S 'sk-ant-X1234'` returns no commits

### M-2 — Upgrade @nestjs/core 10 → 11

- **Severity:** Medium
- **Origin:** S-P-7 (dep is current major but missing performance + security improvements in v11)
- **Why manual:** v11 has breaking changes in module loading. Needs human review of migration notes.
- **Recommended approach:**
  1. Read https://docs.nestjs.com/migration-guide
  2. Run on a feature branch
  3. Fix breaking imports
  4. Run full test suite
  5. Profile a smoke run

## Deferred

Findings the user explicitly chose NOT to fix this pass. Each must have a reason.

### D-1 — S-S-32 [Medium] — Missing CSP header

- **Reason:** App is not yet behind a known domain; CSP will be configured in deployment (Cloudflare).
- **Re-check by:** Pre-launch checklist
- **Risk if not fixed:** Some XSS impact reduction lost

### D-2 — S-P-15 [Low] — Outdated `lodash` (4.17.21 → 4.17.22)

- **Reason:** No CVE; patch contains only typo fix in docs.
- **Re-check by:** Next quarterly hygiene pass

### D-3 — S-S-44 [Low] — Docker image `redis:7-alpine` not pinned by digest

- **Reason:** Dev compose only. Will pin in prod compose when prod compose is added.
- **Re-check by:** Pre-launch

## Re-audit plan

After fixes are applied:

1. **Re-run Phase 2 (static)** to confirm fixed findings no longer match
2. **Re-run Phase 3 (dynamic)** on the relevant probes for behavioral fixes
3. **Re-run Phase 4 (deps)** to confirm `pnpm audit --prod --audit-level high` is clean
4. **Update this plan** with re-audit results — each fix moves to a "RESOLVED" section with date and SHA
```

## Triage prompts for the orchestrator

When the orchestrator walks the user through findings, use this script structure:

### For each Critical:

```
FINDING S-S-12 [CRITICAL]: Companies repository bypasses tenantDb at companies.repository.ts:47.

This is a cross-workspace data leak. Workspace A's admin can read workspace B's companies.

  Evidence:
    db.select().from(companies).where(eq(companies.id, id))   ← missing workspace filter

  Recommendation: wrap in tenantDb(db, workspaceId).scope('companies', ...)
  Estimated fix: 5 lines, agent can handle.

  Fix or accept? [F/a]
```

Default = fix. Accept requires a typed justification (the user must say WHY).

### For each High:

```
FINDING S-S-21 [HIGH]: dangerouslySetInnerHTML in CampaignPreview without sanitization.

  Evidence: <code block>
  Recommendation: <fix>

  Fix now / defer / explain? [F/d/e]
```

### For Medium (batch):

```
12 MEDIUM findings:
  - 7 missing @Audit on mutations  (compliance gap)
  - 3 verbose error in prod        (info leakage)
  - 2 missing rate limit           (DOS risk)

  Fix all / fix some / defer all / show one-by-one? [a/s/d/o]
```

### For Low + Info:

```
8 LOW and 3 INFO findings recorded. Default: deferred to next hygiene pass.

  Override and fix some now? [y/N]
```

## Re-running after fixes

After Phase 6 applies fixes, the orchestrator:

1. Marks each fixed item with status RESOLVED + date + commit SHA in SECURITY_FIX_PLAN.md
2. Re-runs Phase 2 (static-auditor)
3. Re-runs the relevant probes from Phase 3 (dynamic-auditor)
4. Re-runs Phase 4 (dependency-auditor)
5. Generates a delta report: "Before / After / Still Open"
6. If new findings appeared (unlikely but possible from the fixes themselves), they go through triage as a new batch

## What constitutes "done"

The security review is done when:

- Every Critical finding has STATUS=RESOLVED in SECURITY_FIX_PLAN.md OR a documented accept with justification
- Every High finding has STATUS=RESOLVED or STATUS=DEFERRED with explicit reason
- Mediums are explicitly triaged (RESOLVED, DEFERRED, or DECIDED-NOT-FIX)
- Lows and Infos are at minimum acknowledged (RECORDED)
- The re-audit confirms previously-flagged patterns no longer match
- Manual fixes (M-N) have user confirmation that they were applied (e.g., the user reports "rotated the key")

The skill DOES NOT close itself. The orchestrator presents the final state to the user and waits for explicit "ship it" or "keep iterating."
