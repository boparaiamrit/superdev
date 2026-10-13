---
name: superdev-done
description: Run superdev's live Definition-of-Done verification on demand. Executes (never reads a ledger): per-package typecheck/lint/build, boots the built API dist and polls its health endpoints, contracts module-format check, patchNestJsSwagger landmine check, no-new-suppressions sweep vs git HEAD, and demo/placeholder sweep. Use when asked "are we done", "is it production ready", "run the done gate / verify done", or BEFORE declaring any superdev build complete. Cross-platform (Node), no hooks, no sentinel files.
---

# superdev — Definition of Done (live verification)

"Is this build actually done?" is answered by running checks against the real tree and the real built artifact — not by reading a ledger the build marked `pass` itself, and not by narrative. This replaced the old bash Stop-hook gate, whose ledger a shipped project once marked all-green without running the formal passes.

## How to run

From the target monorepo root:

```bash
node <superdev-plugin>/scripts/verify-done.mjs
```

`<superdev-plugin>` is this plugin's install location (`plugins/superdev` inside the superdev repo, or wherever the host loaded the plugin from). Options: `--root <dir>`, `--skip-build`, `--skip-boot`, `--health-url <url>`.

- Exit `0` → **DONE (machine layer)**: every package typechecks/lints/builds, the built API boots and answers health, contracts are require-able by the API, no new suppressions vs HEAD, no placeholder content in the frontend.
- Exit `1` → **NOT DONE**: the report lists the exact failing checks with output tails. Fix each at the ROOT CAUSE — suppressions (`eslint-disable`, `@ts-ignore`, `as any`) are themselves a failing check — then re-run.

## What it checks

1. **Per-package scripts** — `typecheck`, `lint`, `build` for every `apps/*` and `packages/*` package that defines them (package manager detected from the lockfile).
2. **Contracts module format** — an ESM-only `packages/contracts` consumed by a CommonJS API fails (boot-time `ERR_PACKAGE_PATH_NOT_EXPORTED`; hard-rules #3 in [`superdev-build`](../superdev-build/references/hard-rules.md)).
3. **Swagger landmine** — any executable `patchNestJsSwagger()` call in `apps/api/src` fails (crashes boot on @nestjs/swagger 11; hard-rules #2).
4. **Runtime boot** — spawns `node apps/api/dist/main.js`, polls `/health/ready`, `/health`, `/v1/health` (or `--health-url`). A process that exits during boot, or never answers, fails with its log tail. This is the check green test suites kept hiding (hard-rules #1).
5. **No new suppressions** — added lines vs `git HEAD` plus untracked files under `apps/` and `packages/` must contain no `eslint-disable` / `@ts-ignore` / `@ts-expect-error` / `as any` / `as unknown as`.
6. **No demo/placeholder content** — frontend `src/` is swept for lorem ipsum, "coming soon", `mockData`, test card numbers, etc. (tests/mocks/stories excluded).

## What it does NOT prove

Browser behavior, tenancy isolation, business correctness, and security posture are the judgment layer: [`exploratory-qa`](../exploratory-qa/SKILL.md), [`security-review-and-fix`](../security-review-and-fix/SKILL.md), [`product-completeness-audit`](../product-completeness-audit/SKILL.md), and [`production-readiness-audit`](../production-readiness-audit/SKILL.md) (scores cited with evidence). "Done" = this script green **and** those audits clean for the scope being shipped. There is no override file and no sentinel: if a check is wrong for your repo shape, fix the repo or pass the documented flags and say so in your summary.
