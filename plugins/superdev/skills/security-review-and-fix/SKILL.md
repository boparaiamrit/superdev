---
name: security-review-and-fix
description: Six-phase security audit and remediation for Nest.js + Next.js monorepos built with the design-to-nextjs and nestjs-enterprise-backend skills. Catalogs tenancy boundaries, authorization coverage, authentication strength, input validation, audit logging, secret handling, rate limits, CORS/CSP, webhook signatures, dependency vulnerabilities, frontend XSS, and Docker hardening. Produces SECURITY_INVENTORY.md, SECURITY_FINDINGS.md, and SECURITY_FIX_PLAN.md, then optionally dispatches targeted fix passes. Findings use a five-level severity ladder (Critical, High, Medium, Low, Info) and cite the exact file and line. Use whenever the user wants to security-audit a codebase before launch, after a major feature drop, or as part of the orchestrator's Phase D before going to production; mentions security review, pen test prep, OWASP, tenancy bypass, secret scan, dependency audit, hardening, or compliance checklist.
---

# Security Review and Fix

A six-phase pipeline that audits a Nest.js + Next.js monorepo for security issues, triages them, and produces a fix plan that the orchestrator (or a developer) can execute. Designed to be both standalone (ad-hoc audit) and embedded as a final wave gate in the `prd-design-build-orchestrator`.

## When to use this skill

Use when:

- The user wants a pre-launch security review
- A major feature drop introduced new attack surface (new external integrations, new file uploads, new payment flows)
- Compliance prep (SOC2, ISO 27001, HIPAA) needs a documented audit
- The orchestrator's Phase D should include a security gate before shipping
- A pen-test report came back and findings need triage + fix-planning
- Periodic (quarterly) security hygiene check

Do NOT use this skill for:

- Production incident response — that's a different playbook
- Code review of a single PR — use a code review tool
- Compliance certification itself — this produces evidence; auditors interpret it

## How to invoke this skill

This skill installs 5 specialized subagent definitions into `.claude/agents/`. The main Claude Code session orchestrates them through six phases.

### Standalone invocation

After installing the skill, start a Claude Code session and describe what you want:

```
Run a security audit on this codebase. Pre-launch review.
```

The main session reads this skill's SKILL.md, installs the 5 subagents via the install script, then runs the six phases by delegating to subagents through natural language ("Use the security-inventory subagent to ...") or @-mentions.

### Invoked from the orchestrator

When `prd-design-build-orchestrator` runs end-to-end, this skill's audit is automatically executed as Step D.2 of Phase D — provided the security skill is installed. No separate invocation needed; the orchestrator's main session dispatches the 5 security subagents the same way it dispatches its own.

### Agent-teams mode (optional, experimental)

This skill defaults to subagents (stable, lower-cost). The three auditors (static, dynamic, dependency) can alternatively run as a **3-teammate agent team** that can challenge each other's findings — useful for high-stakes audits. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. See "Agent teams (optional)" near the end of this skill for the specific invocation prompt.

The 5 agent definition files work as both subagent definitions AND teammate types without modification.

## The six-phase pipeline

```
Phase 1: INVENTORY      What's in scope, what's deployed, what auth model.
Phase 2: STATIC AUDIT   Grep-based scans for known anti-patterns.
Phase 3: DYNAMIC AUDIT  Runtime probes when the stack is live.
Phase 4: DEPS AUDIT     pnpm audit + lockfile + license scan.
Phase 5: TRIAGE         Categorize findings, severity, blast radius.
Phase 6: FIX            Produce SECURITY_FIX_PLAN.md; optionally dispatch fixes.
```

Phases 2, 3, 4 run **in parallel** — they share no inputs and write to different files. Phases 5 and 6 are sequential.

## Severity ladder

| Severity | Definition | Examples |
|---|---|---|
| **Critical** | Exploitable in production with no auth, leads to full data exposure, RCE, tenancy bypass, or auth bypass | Cross-workspace data leak, hardcoded API key in repo, SQL injection via `sql.raw()`, missing auth on a data endpoint |
| **High** | Exploitable with low effort, leads to data leak or privilege escalation | XSS in user-facing component, missing CSRF on state-changing endpoint, weak JWT secret (<32 chars), refresh token in localStorage |
| **Medium** | Defense-in-depth gap, exploitable in specific conditions | Missing `@Audit` on a mutation, missing rate limit on a non-auth endpoint, verbose error messages in prod, missing CSP |
| **Low** | Hardening recommendation, no direct exploit | Dependency outdated but no CVE, missing security headers (HSTS, X-Frame-Options), Docker container running as root |
| **Info** | Informational — review at leisure | License compatibility notes, code style smells with security implications |

Critical findings are **build-blocking**. The orchestrator MUST refuse to ship until they're resolved.

## Artifacts

| File | Owned by | Read by |
|---|---|---|
| `SECURITY_INVENTORY.md` | Phase 1 | All other phases |
| `SECURITY_FINDINGS.md` | Phases 2, 3, 4 | Phase 5, 6 |
| `SECURITY_FIX_PLAN.md` | Phase 5 + 6 | Builders (in fix mode) |

Each finding has a stable ID (`S-1`, `S-2`, ...) so cross-references survive edits.

## The five sub-agents

This skill defines five specialized subagents, installable into `.claude/agents/`:

| Agent | Phase | Tools | Owns |
|---|---|---|---|
| `security-inventory` | 1 | Read, Glob, Grep, Bash | `SECURITY_INVENTORY.md` |
| `static-auditor` | 2 | Read, Glob, Grep, Bash | findings appended to `SECURITY_FINDINGS.md` |
| `dynamic-auditor` | 3 | Read, Bash | findings appended to `SECURITY_FINDINGS.md` |
| `dependency-auditor` | 4 | Read, Bash | findings appended to `SECURITY_FINDINGS.md` |
| `security-fixer` | 6 | Read, Write, Edit, Bash | targeted code edits + commits |

Full definitions in `references/security-agents.md`. The standalone installer at `references/install-security-agents.sh` extracts each definition into `.claude/agents/<name>.md`.

**Triage** (Phase 5) is the orchestrator's job, not a subagent — it requires synthesis across all three findings sources, plus user input for accept/fix decisions on Medium and Low findings.

## Install (Phase 0)

Before running any phase, install the five security agents:

```bash
# Standalone (ad-hoc audit on an existing project)
~/.claude/skills/security-review-and-fix/references/install-security-agents.sh

# Verify
ls .claude/agents/ | grep -E "security-inventory|static-auditor|dynamic-auditor|dependency-auditor|security-fixer"
# Should print 5 lines
```

If this skill is invoked **from within** the `prd-design-build-orchestrator` (Phase D.2), the install is already done by the orchestrator's Phase A.1 (it detects this skill's presence and runs `install-security-agents.sh` automatically). Re-running the installer is a no-op — the files are simply overwritten.

## Phase 1 — Inventory

**Goal:** know what you're auditing.

Dispatch `security-inventory`. In natural language:

> "Use the security-inventory subagent to inventory the codebase. List every external integration, every authentication mechanism, every data store, every deployment surface. Produce SECURITY_INVENTORY.md."

Output catalogs:

- **Apps**: every Nest.js controller endpoint (route, auth required, role, audit decorator presence), every Next.js route (public/auth-required, server component vs client)
- **Data stores**: Postgres tables (workspace-scoped vs global), Redis usage (cache, queue, lock), object storage (MinIO/S3)
- **External integrations**: API keys used, OAuth flows, webhook receivers
- **Auth**: JWT model (TTL, secrets source), refresh strategy, session storage, CASL ability map
- **Infrastructure**: every Docker service, exposed ports, health endpoints, public vs private
- **Secrets surface**: every env var the apps read, every `.env.example` entry

See `references/inventory-checklist.md` for the full extraction template.

## Phase 2 — Static audit (parallel-safe)

**Goal:** find known anti-patterns by grep before runtime.

Dispatch `static-auditor`:

> "Use the static-auditor subagent to run the full static audit per references/static-audit-checklist.md. Append findings to SECURITY_FINDINGS.md with IDs `S-S-1`, `S-S-2`, ... (S-S prefix = Static)."

Major check categories (`references/static-audit-checklist.md` has the grep commands):

- **Tenancy**: every workspace-scoped Drizzle query uses `tenantDb().scope()`
- **AuthZ**: every controller endpoint has `@CheckAbility` (no decorator = no auth check)
- **AuthN**: JWT config, password hashing, secret strength patterns
- **SQL injection**: any `sql.raw()` or string-template SQL with non-literal values
- **Input validation**: every `@Body()` / `@Query()` / `@Param()` types to a Zod DTO, never `: any`
- **Audit**: every mutation method has `@Audit`
- **Secrets**: hardcoded keys (`sk-`, `key-`, `AKIA`, JWT-shaped strings) anywhere in the repo
- **Rate limits**: auth/password endpoints have stricter throttling than default
- **Mass assignment**: no `...input` spreads into Drizzle `.values()` / `.set()`
- **XSS**: no `dangerouslySetInnerHTML` without explicit sanitization wrapper
- **Token storage**: no `localStorage.setItem('token'`, no `localStorage.setItem('accessToken'`
- **CORS**: explicit origin allowlist, not `*`
- **Helmet**: `app.use(helmet())` present
- **Cookies**: refresh token sets `httpOnly: true, secure: true, sameSite: 'strict'`
- **Mock route in production**: `/app/api/mock/[...path]/route.ts` returns 404 when `NEXT_PUBLIC_API_MODE !== 'demo'`
- **Webhook signatures**: every inbound webhook controller verifies HMAC
- **Docker hardening**: services bound to `127.0.0.1` in prod compose, no default passwords on exposed services, images pinned by digest in prod

## Phase 3 — Dynamic audit (requires live stack)

**Goal:** probe a running stack for runtime issues static analysis can't catch.

Dispatch `dynamic-auditor`. The agent first verifies the stack is up (`pnpm dev:infra`, `pnpm start:dev`), then runs probes:

> "Use the dynamic-auditor subagent to probe the live stack. Test cross-workspace isolation, CASL role enforcement on every endpoint, rate-limit triggering, header presence, error response leakage, and auth flow. Append findings to SECURITY_FINDINGS.md with IDs `S-D-1`, `S-D-2`, ... (S-D prefix = Dynamic)."

Probes (`references/dynamic-audit-checklist.md` has the full procedure):

- **Tenancy round-trip**: workspace A token reading workspace B resource → must return 404, not 403, not 200
- **Auth probes**: missing token → 401; expired token → 401; wrong-signature token → 401
- **CASL matrix**: for every endpoint, every role, expected status code per the ability map
- **Rate-limit triggers**: hammer auth endpoint, verify 429 with `Retry-After` header
- **Error leakage**: trigger errors (404, 500, DB constraint), inspect response — no stack traces, no DB column names, no internal paths in production env
- **Header sweep**: `X-Frame-Options`, `Strict-Transport-Security`, `Content-Security-Policy`, `X-Content-Type-Options` all present
- **Cookie inspection**: refresh cookie is `HttpOnly`, `Secure`, `SameSite=Strict`
- **Mock route**: in `NEXT_PUBLIC_API_MODE=production` build, request to `/api/mock/foo` returns 404
- **Webhook bypass**: send unsigned payload to every webhook receiver → 401/403

## Phase 4 — Dependency audit (parallel-safe)

**Goal:** catch CVEs in the lockfile and license issues.

Dispatch `dependency-auditor`:

> "Use the dependency-auditor subagent to run `pnpm audit` across the workspace, check the lockfile for unpinned versions, verify no devDependencies leaked to production deps. Optional: license scan if osv-scanner or license-checker is available. Append findings to SECURITY_FINDINGS.md with IDs `S-P-1`, `S-P-2`, ... (S-P prefix = Package)."

Checks (`references/dependency-audit-checklist.md`):

- `pnpm audit --prod` (production deps only — devDep CVEs don't ship)
- `pnpm audit --audit-level moderate`
- Lockfile committed (`pnpm-lock.yaml` in git, not `.gitignore`)
- No `"*"` or `"latest"` versions in any `package.json`
- No `file:` or `git+ssh://` deps (supply chain risk) unless explicitly approved
- No production dep in devDependencies and vice-versa
- Optional: `osv-scanner` for OSV database matches if installed
- Optional: `license-checker --summary` for incompatible licenses

## Phase 5 — Triage (orchestrator does this, with user)

**Goal:** convert raw findings into a fix plan with prioritization and decisions.

The orchestrator reads `SECURITY_FINDINGS.md` and walks the user through:

1. **Critical findings** — present each, get fix-or-accept decision (default: fix; very narrow accept criteria)
2. **High findings** — present, default fix, allow defer with explicit justification recorded
3. **Medium findings** — review summary, user picks which to fix this pass
4. **Low + Info** — recorded for future hygiene work

After triage, write `SECURITY_FIX_PLAN.md` with:

- Ordered list of fixes by severity then file (group fixes that touch the same module)
- Per-fix: the file path, the line, the recommended change, the agent who'll apply it (`security-fixer` for most; sometimes the user must do it manually, e.g., rotate a leaked secret)
- Acceptance criteria per fix (how do we verify it's fixed?)
- A "deferred" section with decisions to defer and why

See `references/fix-plan-format.md` for the template.

## Phase 6 — Fix (optional)

**Goal:** apply the fixes the user approved.

For each fix item in SECURITY_FIX_PLAN.md, dispatch `security-fixer`:

> "Use the security-fixer subagent to apply fix `S-S-12` per SECURITY_FIX_PLAN.md. Edit only the files listed in the plan. Run `pnpm typecheck` and `pnpm test` for the affected app before returning. Do not bundle multiple fixes in one pass."

Rules:

- **One fix per dispatch.** Bundling several fixes into one agent run makes it hard to review and roll back. Each Critical/High gets its own pass.
- **Same-module fixes can batch** (e.g., five Medium findings in `companies.controller.ts` go in one dispatch if and only if they're tightly related).
- **Verify after each fix.** Typecheck + relevant tests must pass.
- **Re-run the static audit at the end.** The very issue you "fixed" might have a sibling in another module.

Some fixes can't be automated and require user action — flag them clearly:

- Rotating a leaked secret (the user must invalidate it at the issuing provider)
- Upgrading a major dep with breaking changes (needs human review of migration notes)
- Changing infra topology (DNS, load balancer, WAF rules)

## Integration with the orchestrator

When `prd-design-build-orchestrator` includes this skill, slot the audit into Phase D — after integration tests, before the final report.

```
Phase D — INTEGRATE (orchestrator flow):

  Step D.1 — integration-tester       (existing)
  Step D.2 — security-review-and-fix  (NEW)
    Phase 1: security-inventory       sequential
    Phase 2,3,4: static + dynamic + deps   parallel
    Phase 5: triage with user
    Phase 6: security-fixer per approved item
    Re-run Phase 2 to verify
  Step D.3 — final report
```

Critical findings block the final report. High findings trigger an explicit acknowledgement. Medium and below appear in the report as recommendations.

## Reference files

| File | When to read |
|---|---|
| `references/security-agents.md` | Phase 1 install — source-of-truth for all 5 agent definitions |
| `references/inventory-checklist.md` | Phase 1 — what to extract |
| `references/static-audit-checklist.md` | Phase 2 — the full grep playbook |
| `references/dynamic-audit-checklist.md` | Phase 3 — runtime probes |
| `references/dependency-audit-checklist.md` | Phase 4 — pnpm audit + licensing |
| `references/fix-plan-format.md` | Phase 5 — SECURITY_FIX_PLAN.md template |

## Validation checklist

Before declaring the audit done:

- [ ] `.claude/agents/` contains all 5 security agents
- [ ] `SECURITY_INVENTORY.md` exists and reflects current code
- [ ] `SECURITY_FINDINGS.md` exists with findings from all three audit phases
- [ ] Every finding has: ID, severity, file:line, evidence, recommendation
- [ ] User has triaged all Critical and High findings
- [ ] `SECURITY_FIX_PLAN.md` records every decision (fix or defer)
- [ ] If fixes were applied, all checks re-ran clean
- [ ] No Critical findings remain unresolved
- [ ] Final summary lists deferred items with justification

## Common pitfalls

**P1 — Running Phase 3 (dynamic) without the stack up.** The agent will report failures that are actually "service unreachable." Verify `docker compose ps` shows healthy and the API is listening before dispatching.

**P2 — Skipping triage on Mediums.** "It's only medium" compounds. A monorepo with 40 Medium findings has the audit profile of one with 4 Highs.

**P3 — Auto-fixing Critical findings without user review.** Critical fixes often have downstream impact (rotating keys, changing JWT format) — the user must sign off, not just the agent.

**P4 — One agent fixes everything.** Bundling 20 fixes in one pass produces an unreviewable diff. One fix, one dispatch, one verification.

**P5 — Trusting `pnpm audit` alone.** It catches known CVEs in the lockfile but misses: deps with no advisory yet, license issues, supply-chain risks (e.g., a dep installing a postinstall script). The dependency-auditor does more than `pnpm audit`.

**P6 — Findings without file:line.** A finding like "missing rate limit on auth" with no location forces the fixer to re-discover the file. Every finding cites exact path + line.

**P7 — Re-running the audit on the same SHA after a "fix" and seeing the same finding.** Re-grep with the fix in place; if the pattern still matches, the fix didn't land. The verify step in Phase 6 is non-negotiable.

**P8 — Confusing severity with priority.** A Medium finding in the public-facing login endpoint is more urgent than a High in an admin-only debug tool. Triage uses BOTH severity and exposure.

## Agent teams (optional, experimental)

This skill's default operating mode uses subagents — stable, well-understood, lower token cost. Phases 2–4 (Static + Dynamic + Dependency audits) can alternatively run as an **agent team** when teammates would benefit from cross-talk.

Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `settings.json` or environment.

### When team mode helps

Subagents in this skill don't talk to each other — each writes findings to `SECURITY_FINDINGS.md` with disjoint ID prefixes. That's fine for most audits. But some classes of finding emerge only from cross-discipline correlation:

- The static auditor flags a SQL injection at `companies.repository.ts:84`. The dependency auditor has a CVE database — is the SQL builder library affected? Worth checking.
- The dynamic auditor reports the CSRF token isn't validated on a particular endpoint. The static auditor can confirm whether middleware actually skips it — or whether the dynamic probe was misconfigured.
- A high-severity finding from one auditor should survive challenges from the others before being recorded.

In subagent mode, this correlation happens during triage by the main session reading all findings. In team mode, the auditors do it live with each other.

### How to invoke team mode

After Phase 1 (inventory) finishes, instead of dispatching three independent subagents, ask the main session:

> "Spawn a 3-teammate agent team using the static-auditor, dynamic-auditor, and dependency-auditor agent types as bases. Have them debate findings as they go — every Critical or High finding gets cross-checked against the other auditors before being recorded. Produce SECURITY_FINDINGS.md by consensus."

The user can directly message any auditor mid-investigation (Shift+Down in in-process mode, or click the pane in split mode). Useful when you want to dig into a specific finding without waiting.

### What stays in subagent mode

- **`security-inventory`** (Phase 1) — single agent, no cross-talk needed, runs alone before the team spawns.
- **`security-fixer`** (Phase 6) — one fix at a time, sequential, no benefit from a team.

### Cost note

3-teammate mode costs ~3× the subagent path in tokens (each teammate has its own context window and runs as a separate Claude Code instance). Recommended for pre-launch audits and post-incident reviews where missed findings have real consequences. Not recommended for routine quarterly scans.
