# Execution Pipeline (Phase C)

How the orchestrator dispatches per-feature builders in parallel waves. This is the speed lever.

> **Backend stack note:** the examples below use `backend-module-builder` (the Nest.js builder). When the Step A.5b selection gate set `backend_stack == Laravel`, substitute **`laravel-module-builder`** everywhere `backend-module-builder` appears, and the wave-gate typecheck/test commands become their Laravel equivalents (`php artisan test`, plus `npm run build` when the frontend is Inertia). The wave/batching mechanics are identical.

## The mental model

Imagine a Gantt chart:

```
        time ──→
Wave 1:  [auth ][workspaces]                            ← 2 features × 2 builders = 4 subagents
Wave 2:  ────────────────[companies][contacts][mailboxes]  ← 3 features × 2 builders = 6 subagents
Wave 3:                          ─────────────[campaigns][pipeline]  ← 2 × 2 = 4
Wave 4:                                          ─────[ai][email][webhooks]  ← 3 × 2 = 6
Wave 5:                                                   ─────[analytics][audit]  ← 2 × 2 = 4
```

Within a wave, all builders run in parallel. Between waves, the orchestrator waits and runs the wave gate.

A naïve sequential build of 12 features × 2 builders = 24 subagent runs in series. With waves, the same work takes 5 sequential gates, each with up to 6 concurrent builders. The wall-clock difference is large.

## Wave gate

After every wave, before advancing:

1. **Docker services still healthy**
   ```bash
   docker compose ps --format json | jq -e 'all(.Health == "healthy" or (.Health == "" and .State == "running"))'
   ```
   If unhealthy, no point running builders against a dead Postgres. Bring the stack back up before retrying the failed builder. `docker compose ps` and `docker compose logs <service>` are your friends.

2. **Typecheck the world**
   ```bash
   pnpm --filter @<scope>/contracts build
   pnpm --filter @<scope>/api typecheck
   pnpm --filter @<scope>/web typecheck
   ```

3. **Lint**
   ```bash
   pnpm turbo lint --filter=@<scope>/api --filter=@<scope>/web
   ```

4. **Validate fixtures (frontend)**
   ```bash
   pnpm --filter @<scope>/web validate:fixtures
   ```

5. **Unit tests for built modules**
   ```bash
   pnpm --filter @<scope>/api test -- --testPathPattern="(<feature1>|<feature2>)"
   ```

6. **UI audit** — verify the wave's frontend modules use shadcn primitives only. The orchestrator dispatches:

   > "Use the ui-auditor subagent to audit the frontend modules built in this wave (`<feature1>, <feature2>, ...`). Verify shadcn/ui is the sole UI primitive source. Check forbidden imports, raw HTML primitive usage, hand-rolled re-implementations, sidebar block usage. Report violations; do not edit code."

   The `ui-auditor` is fast (read-only greps) and parallel-safe with the typecheck/lint/test steps if the orchestrator wants to overlap them; default is sequential after the other checks.

If any check fails, do NOT advance. The orchestrator dispatches a focused fixer:

> "Use the backend-module-builder subagent to fix module `<feature>` which failed typecheck. Errors:
> ```
> <paste tsc output>
> ```
> Read `apps/api/src/modules/<feature>/`, identify the root cause, fix it. Do NOT add new features. Re-run `pnpm --filter @<scope>/api typecheck` to confirm."

For UI-audit violations, the orchestrator dispatches a frontend fix:

> "Use the frontend-module-builder subagent to fix UI audit violations in module `<feature>`:
> ```
> <paste ui-auditor report>
> ```
> Fix each violation by switching to shadcn primitives from `@/components/ui/*`. Do not add new features. Re-run ui-auditor to confirm."

Up to 3 fix attempts. After the third failure, surface to the user with the full diagnostic.

## Hook-driven wave gates (optional, recommended)

Manual wave gates work, but Claude Code's hooks system can automate them. Define `SubagentStop` hooks in `.claude/settings.json` so that whenever a backend or frontend builder finishes, the relevant typecheck runs automatically:

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "matcher": "backend-module-builder",
        "hooks": [
          { "type": "command", "command": "pnpm --filter @<scope>/api typecheck" }
        ]
      },
      {
        "matcher": "frontend-module-builder",
        "hooks": [
          { "type": "command", "command": "pnpm --filter @<scope>/web typecheck && pnpm --filter @<scope>/web lint" }
        ]
      }
    ]
  }
}
```

Exit code 2 from the hook command blocks the wave from advancing and feeds the error back to the orchestrator, which then dispatches a fixer subagent. See [hook docs](https://code.claude.com/docs/en/hooks).

## Batching within a wave

Concurrency cap: **6 `Agent` tool calls per tool-use batch.** This keeps coordination overhead manageable.

### Wave with ≤3 features

The orchestrator emits one tool-use batch with six concurrent subagent dispatches:

> "Dispatch six subagents in parallel:
> 1. backend-module-builder — build companies module
> 2. frontend-module-builder — build companies module
> 3. backend-module-builder — build contacts module
> 4. frontend-module-builder — build contacts module
> 5. backend-module-builder — build mailboxes module
> 6. frontend-module-builder — build mailboxes module"

Claude Code translates this into six `Agent` tool calls in one batch. They run with independent contexts and return when each one completes.

### Wave with 4+ features

Two batches. The orchestrator waits for batch 1 to complete before launching batch 2.

> Batch 1: dispatch 6 subagents (3 features × 2 builders).
> Wait for all 6 to complete.
> Batch 2: dispatch the remaining (features-3) × 2 subagents.

Why not run all 8 in one batch? Two reasons:

1. Diminishing returns past 6 concurrent (Claude Code's scheduling tax)
2. If batch 1 surfaces a contract bug, you can catch it before batch 2 runs

For a 4-feature wave, prefer 4+4 over 6+2 — keeps batches balanced.

### When NOT to split a wave

If features in a wave depend on each other, they're not actually a wave — they belong in separate waves. If `plan-architect` placed them together, that's a planning bug; rerun `plan-architect` with the corrected dependency.

## Prompt anatomy for module builders

Both `backend-module-builder` and `frontend-module-builder` receive the same structure:

```
Task: Build the <feature> module per EXECUTION_PLAN.md.

Inputs to read:
  - EXECUTION_PLAN.md (especially the <feature> entry)
  - packages/contracts/src/<feature>.ts (already exists from Phase B.2)
  - ~/.claude/skills/{nestjs-enterprise-backend OR design-to-nextjs}/SKILL.md
  - Relevant references from that skill

Outputs:
  - Backend: apps/api/src/modules/<feature>/* (controller, service, presenter, repository, dto, tests)
            apps/api/src/db/schema/<feature>.ts
            Register the module in apps/api/src/app.module.ts (if not already)
  - Frontend: apps/web/src/modules/<feature>/* (api, hooks, components, page)
              apps/web/src/mocks/<feature>/*.json
              apps/web/src/app/<route-group>/<feature>/* (page files)

Constraints:
  - Use the view-shape contract — no .optional() on view fields; use .nullable() or defaults
  - Import schemas only from @<scope>/contracts; never define them locally
  - Run pnpm --filter @<scope>/<app> typecheck before finishing
  - Report any blocking issues you encounter (e.g., missing contract field)

Done = typecheck green for this module + tests pass.
```

The prompt is verbose because subagents don't share context with the orchestrator. They need the full picture in the prompt.

## Cross-feature wiring

Some files must be touched by every feature module:

- `apps/api/src/app.module.ts` — every feature module is imported here
- `apps/web/src/app/layout.tsx` — navigation entries
- `apps/web/src/lib/query-keys.ts` — keys for the new feature (if you use a central registry)

Two strategies:

### Strategy A — Append-only per agent (preferred)

If the wiring is a simple add (e.g., one import + one entry in a list), let each builder append its own. Use file-locking via the subagent's tool batching — Edit is atomic-per-call, so two subagents editing the same file sequentially is fine; in parallel it's a race.

### Strategy B — Wiring agent after the wave

For risky shared files (e.g., `app.module.ts`), the builders leave a marker in their output ("registered" or "needs registration"), and the orchestrator runs a single sequential pass at the wave gate. In natural language:

> "Use the backend-module-builder subagent to register the following modules in `apps/api/src/app.module.ts`: companies, contacts, mailboxes. Import each, add to the imports array, do not touch other lines."

Use Strategy B when:

- The file has complex structure where blind appends could break order
- Multiple shared files need coordinated changes
- The wave has 5+ features (more risk of races)

## Pipelining (advanced — usually skip)

In principle, if Wave N+1 has zero dependency on Wave N, you can start Wave N+1 while waiting for Wave N. In practice:

- Wave N+1 often depends on contracts that Wave N might modify
- The wave gate is what catches type drift; pipelining around it loses that safety
- Coordination overhead in the orchestrator grows

**Default: do not pipeline.** Run waves strictly sequentially with a gate between each.

Only pipeline if profile shows the wave gate is the bottleneck (typically not — the builders dominate).

## Failure modes and recovery

### Failure 1: Builder reports done, typecheck fails

This is the common case — a subagent thinks it finished but introduced a type error.

Recovery: dispatch a focused fixer with the exact typecheck output. The fixer is the same agent type with a "fix" prompt.

### Failure 2: Two builders both modify the same shared file

Strategy A's risk. Symptom: `git status` shows a merge conflict marker, or one agent's changes overwrite the other's.

Recovery: revert the file to the last known-good state, dispatch a single wiring agent (Strategy B) to redo the wiring.

### Failure 3: Builder produces correct code but in the wrong location

E.g., wrote a contract schema in `apps/api/src/contracts/` instead of `packages/contracts/`. This violates exclusive ownership.

Recovery: dispatch a cleanup agent to move the file. Update EXECUTION_PLAN if the builder's prompt was ambiguous.

### Failure 4: Cascade failure across a wave

A bug in `packages/contracts` causes every builder in the wave to fail.

Recovery: do NOT re-dispatch all builders. First fix the contract (one targeted Task on `contracts-author`), rerun the wave gate, then if still red, fix individual modules.

### Failure 5: User changes their mind mid-build

Common. The user says "actually, drop the audit log feature."

Recovery: stop dispatching, do not delete already-built work, mark the feature as deferred in EXECUTION_PLAN.md, and continue from the next wave. If the dropped feature is a dependency of a later wave, replan with `plan-architect`.

## Wave-by-wave reporting

At each wave gate, the orchestrator reports to the user:

```
Wave 2 complete (companies, contacts, mailboxes)
  ✓ pnpm typecheck — green
  ✓ pnpm lint — zero warnings
  ✓ Backend tests — 47 passed, 0 failed
  ✓ Fixture validation — 12 fixtures valid

  Files created: 38 (backend: 21, frontend: 17)
  Subagent invocations: 6 (3 backend + 3 frontend), all parallel
  Duration: ~4 minutes

  Proceeding to Wave 3: campaigns, pipeline.
```

Concise. The user follows the gantt.

## Anti-patterns

- ❌ **Skipping the wave gate.** Type drift compounds; fixing wave 5 to repair a wave 2 contract bug is hours of work.
- ❌ **All-at-once batching.** Spawning 12 builders at once isn't faster; it's slower and harder to debug.
- ❌ **Builder fixing more than its module.** A backend-module-builder for `companies` should not modify `contacts`. Surface the dependency to the orchestrator.
- ❌ **Trusting "done" without verification.** Every wave gate runs typecheck + lint + tests; no exceptions.
- ❌ **One agent owning multiple modules.** Split the work; restart on failure.
- ❌ **Pipelining waves "to save time."** Saves minutes, costs hours when it breaks.
