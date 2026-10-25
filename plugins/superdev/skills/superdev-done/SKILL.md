---
name: superdev-done
description: Run superdev's live Definition-of-Done verification on demand. Executes (never reads a ledger): per-package typecheck/lint/build, boots the built API dist on a free port and polls its health endpoints, contracts module-format check, patchNestJsSwagger landmine check, Tauri shell checks (CSP, capability scopes, devtools), no-new-suppressions sweep vs git HEAD, demo/placeholder sweep, and with --suites every committed smoke/test:* runtime suite against the running stack. Use when asked "are we done", "is it production ready", "run the done gate / verify done", or BEFORE declaring any superdev build complete. Cross-platform (Node), no hooks, no sentinel files.
---

# superdev — Definition of Done (live verification)

"Is this build actually done?" is answered by running checks against the real tree and the real built artifact — not by reading a ledger the build marked `pass` itself, and not by narrative. This replaced the old bash Stop-hook gate, whose ledger a shipped project once marked all-green without running the formal passes.

## How to run

From the target monorepo root:

```bash
node <superdev-plugin>/scripts/verify-done.mjs                    # machine layer, while building
node <superdev-plugin>/scripts/verify-done.mjs --suites --strict  # release claim: + every committed runtime suite, no skips or warnings
```

`<superdev-plugin>` is this plugin's install location: `${CLAUDE_PLUGIN_ROOT}` where the host sets it, `plugins/superdev` inside the superdev repo, or wherever the host loaded the plugin from. Options: `--root <dir>`, `--skip-build`, `--skip-boot`, `--health-url <url>`, `--suites`, `--api-url <base>` (where the running stack answers for `--suites`; default `http://127.0.0.1:$PORT` or `:3001`), `--strict` (every `SKIP` and `WARN` fails).

Before `--suites`: start the stack (infra, API, worker) and reset the demo data — the suites create records, race for balances and block test accounts.

- Exit `0` → **DONE (machine layer)**: every package typechecks/lints/builds, the built API boots and answers health, contracts are require-able by the API, native shells are locked down, no new suppressions vs HEAD, no placeholder content in any client app — and with `--suites`, every committed runtime suite is green. If the summary line mentions warnings or skipped checks, it is **not** a release claim: a skipped boot or a debug origin left in a release capability proves nothing. Re-run with `--strict`.
- Exit `1` → **NOT DONE**: the report lists the exact failing checks with output tails. Fix each at the ROOT CAUSE — suppressions (`eslint-disable`, `@ts-ignore`, `as any`) are themselves a failing check — then re-run.

## What it checks

1. **Per-package scripts** — `typecheck`, `lint`, `build` for every `apps/*` and `packages/*` package that defines them (package manager detected from the lockfile).
2. **Contracts module format** — an ESM-only `packages/contracts` consumed by a CommonJS API fails (boot-time `ERR_PACKAGE_PATH_NOT_EXPORTED`; hard-rules #3 in [`superdev-build`](../superdev-build/references/hard-rules.md)).
3. **Swagger landmine** — any executable `patchNestJsSwagger()` call in `apps/api/src` fails (crashes boot on @nestjs/swagger 11; hard-rules #2).
4. **Runtime boot** — spawns `node apps/api/dist/main.js` with `PORT` set to a free port (so a running dev stack does not collide), polls `/health/ready`, `/health`, `/v1/health` (or `--health-url`). A process that exits during boot, or never answers, fails with its log tail (hard-rules #1).
5. **Tauri shell** — for every Tauri project in the repo (any folder with `tauri.conf.json`; `.json5`/`Tauri.toml` are reported as skipped): CSP set, with `default-src`, without `unsafe-eval` or any-origin sources; HTTP-plugin scopes with no `*` in scheme or host and `https` for remote hosts; no remote capabilities; no `devtools` feature on the tauri crate in any dependency form (hard-rules #18, [`design-to-tauri`](../design-to-tauri/references/security.md)). Warnings: emulator/LAN origins in a capability release builds enable, a release profile that does not strip, `withGlobalTauri`.
6. **No new suppressions** — added lines vs `git HEAD` plus untracked files under `apps/` and `packages/` must contain no `eslint-disable` / `@ts-ignore` / `@ts-expect-error` / `as any` / `as unknown as`.
7. **No demo/placeholder content** — every client app's `src/` (web, admin, mobile, desktop; not the API) and `resources/js` is swept for lorem ipsum, "coming soon", `mockData`, test card numbers, etc. (tests/mocks/stories excluded). Copy that is genuinely part of the product (a status literally named "Coming Soon") is a reason to reword the string or the check's scope with the operator — never a suppression.
8. **Committed suites (`--suites`)** — checks the stack answers, then runs every package's `smoke` and `test:*` scripts (contract and security first; watch/unit/coverage variants excluded). These are the runtime proofs [`security-foundation`](../security-foundation/references/security-test-suites.md) requires: contract, security, staff role matrix, money/concurrency, live updates.

## What it does NOT prove

Browser behaviour across routes and roles, accessibility and contrast, the phone app on a device, tenancy isolation beyond the suites, and business correctness are the judgment layer: [`release-qa-gate`](../release-qa-gate/SKILL.md) (its `QA_COVERAGE.md` cites evidence for every cell), [`exploratory-qa`](../exploratory-qa/SKILL.md), [`security-review-and-fix`](../security-review-and-fix/SKILL.md), [`product-completeness-audit`](../product-completeness-audit/SKILL.md), and [`production-readiness-audit`](../production-readiness-audit/SKILL.md). "Done" = this script green with `--suites` **and** those passes clean for the scope being shipped. There is no override file and no sentinel: if a check is wrong for your repo shape, fix the repo or pass the documented flags and say so in your summary.
