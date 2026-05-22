# Instrumentation tactics — diagnose without changing behavior

The `root-cause-investigator` and `hypothesis-tester` agents add diagnostics. Diagnostics MUST NOT change program behavior — otherwise you're testing a different program.

## Rules

1. **Read-only first.** Logs, traces, metrics, snapshots — anything that observes without mutating.
2. **Branch-protected mutations only.** If you must add `await sleep(500)` to force a race, gate it on `DEBUG_ARTIFICIAL_DELAY_MS` env var so production code path is unaffected.
3. **Revert before fixing.** All instrumentation reverted before `fix-applier` runs. The fix commit must not contain diagnostic code.

## Tactic library

### Tactic 1 — Structured log injection

```ts
// Before:
async function createCompany(input: CreateCompanyDto) {
  const company = await db.insert(companies).values(input).returning();
  return company[0];
}

// After (Phase 2 — diagnostic, will be reverted):
async function createCompany(input: CreateCompanyDto) {
  logger.debug('createCompany.input', { input, ctx: getRequestContext() });
  const company = await db.insert(companies).values(input).returning();
  logger.debug('createCompany.result', { company: company[0] });
  return company[0];
}
```

Capture log output, document in `ROOT_CAUSE.md`, revert.

### Tactic 2 — Database query logging

```sql
-- Enable for one session only
SET log_statement = 'all';
SET log_min_duration_statement = 0;

-- Reproduce the bug

-- Disable
RESET log_statement;
RESET log_min_duration_statement;
```

Output is in `<app>_postgres` container logs: `docker logs <workspace>_postgres --tail 200`.

### Tactic 3 — Binary search via git bisect

```bash
git bisect start
git bisect bad HEAD                # current code is broken
git bisect good <known-good-commit> # last commit you remember working
# Repeatedly run: git bisect run <pm> test -- <failing-test>
git bisect reset
```

The output names the exact commit that introduced the regression. Use as evidence in `ROOT_CAUSE.md`.

### Tactic 4 — Network HAR capture (frontend bugs)

```ts
// In Playwright
const context = await browser.newContext();
await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
// run the failing flow
await context.tracing.stop({ path: 'repro-trace.zip' });
```

Open the trace in `npx playwright show-trace repro-trace.zip` — every network call, every DOM change.

### Tactic 5 — Process snapshot (memory / CPU)

```bash
# CPU profile for a Node process
node --prof apps/api/dist/main.js &
PID=$!
# trigger the bug
kill -USR2 $PID  # emit profile
node --prof-process isolate-*.log > cpu-profile.txt
```

The hottest function in `cpu-profile.txt` is your suspect.

### Tactic 6 — Race-window widening

To prove a race condition, widen the window so the race is reliable:

```ts
if (process.env.DEBUG_ARTIFICIAL_DELAY_MS) {
  await new Promise(r => setTimeout(r, +process.env.DEBUG_ARTIFICIAL_DELAY_MS));
}
```

Run with `DEBUG_ARTIFICIAL_DELAY_MS=500 <pm> test`. If the bug now reproduces 100% of the time, you've confirmed the race.

## Anti-patterns

| 🚫 | ✅ |
|---|---|
| `console.log` scattered through code, never cleaned up | Use structured logger; revert after diagnosis |
| Adding `try/catch` to "see what error happens" — swallows the error | Let it crash; read the stack trace |
| Increasing timeouts to "make the flake go away" | Diagnose WHY the timing is tight, then fix it |
| Editing test assertions to match observed (broken) output | Tests assert intent; if intent changed, change the spec FIRST |
