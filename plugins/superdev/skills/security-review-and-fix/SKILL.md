---
name: security-review-and-fix
description: Use when a Navree app and its clients need a security review (before launch, after a large change, at step 7 of a superdev build, pen-test preparation, a secret scan, a dependency audit, hardening). Maps the attack surface, runs static, dynamic and dependency checks, agrees the fixes with the operator and applies them one at a time.
---

# Security review and fix

This skill reviews a Navree app and its clients for security faults, agrees with the operator what to fix, and applies the fixes one at a time. Its result is `SECURITY_REPORT.md`. It runs at step 7, first among the audits, before `product-audit`. The framework's own list is the `navree-security-checklist` skill: read it before the first step. This skill adds the order of work, the evidence rule and the fix loop. The controls a build implements are listed in [security-foundation](../security-foundation/SKILL.md); this skill confirms them and does not restate them.

## Steps

1. **Map.** Dispatch `repo-cartographer` with `out_dir: security`. It writes `security/repo-cartographer.md`: routes with their access from `navree routes --json`, models with their scope, configuration from `navree config:show --origin`, secrets on disk (`git ls-files .env` and key files), integrations (outgoing HTTP, webhooks, mail, storage) and clients. The main agent copies a summary into `SECURITY_REPORT.md` `## Surface`. A secret found in git stops the review: tell the operator which one, and continue only after they have rotated it at its issuer.
2. **Static checks.** Dispatch `static-auditor` per [references/static-checks.md](references/static-checks.md). It writes `security/static-auditor.md`.
3. **Dynamic probes.** Reset with `navree migrate:fresh --seed`, run the release binary, and confirm `GET /health/ready` answers 200; if it does not, halt and record every probe as `NOT RUN`. Dispatch `dynamic-auditor` per [references/dynamic-probes.md](references/dynamic-probes.md). It writes `security/dynamic-auditor.md`. The role, money and live-update probes belong to the `product-qa` gate (`role-matrix-tester`, `money-integrity-prober`, `realtime-prober`): cite `qa/role-matrix-tester.md`, `qa/money-integrity-prober.md` and `qa/realtime-prober.md` when they ran on the same commit; otherwise dispatch those agents here with `out_dir: security`, and they write `security/role-matrix-tester.md`, `security/money-integrity-prober.md` and `security/realtime-prober.md`.
4. **Dependencies.** Dispatch `dependency-auditor` per the `## Dependencies` section of [references/static-checks.md](references/static-checks.md). It writes `security/dependency-auditor.md`.
5. **Triage.** The main agent and the operator go through the findings in the order of [references/fix-plan-format.md](references/fix-plan-format.md) and write `SECURITY_REPORT.md`. Every `Blocker` and `Major` finding is fixed or accepted by the operator in writing; `Minor` findings are triaged.
6. **Fix.** Dispatch `fix-applier` once per finding, giving it the `S-n` of `SECURITY_REPORT.md`. After each fix, run the check that found the finding and `cargo test` (and `pnpm run typecheck` when `front_end: next`). When all fixes are in, re-run steps 2 and 3 for what changed. Fixes only the operator can make are listed for them: rotating a secret, a major version upgrade, infrastructure.

Dispatch every agent with absolute paths (rule BLD-4), `out_dir: security`, the app URL and the seeded accounts. Steps 2 to 4 share no inputs, so they may run in parallel. Each agent writes its own file under `security/` and its evidence under `security/<agent-name>/`. `SECURITY_REPORT.md` starts with the commit and the date, and is committed; the `security/` folder is git-ignored.

## Rules

- **SR-1** A finding has an id `S-n`, a severity from the scale in [artifacts.md](../superdev-build/references/artifacts.md), where it is, evidence and a fix. A finding without evidence is not reported.
- **SR-2** `Blocker` and `Major` findings are fixed, or accepted by the operator in writing (name, date, reason) in `SECURITY_REPORT.md`. `Minor` findings are triaged with the operator. The agent records the operator's words and never decides an acceptance (rule BLD-6).
- **SR-3** One fix per dispatch, verified by the check that found it and by `cargo test`. Fixes that only the operator can make are listed for them.
- **SR-4** The report lists the checks that came back clean, so a reader can see what was looked at.
- **SR-5** A probe that could not run is listed under `## Probes not run` as `NOT RUN`. It is not a finding.

## Reference files

| File | Read when |
|---|---|
| [references/static-checks.md](references/static-checks.md) | Step 2 and step 4: the static checks, the searches that run them, the dependency checks, and the severity each gets |
| [references/dynamic-probes.md](references/dynamic-probes.md) | Step 3: the probes against the running app |
| [references/fix-plan-format.md](references/fix-plan-format.md) | Step 5: the `SECURITY_REPORT.md` template and the triage order |
