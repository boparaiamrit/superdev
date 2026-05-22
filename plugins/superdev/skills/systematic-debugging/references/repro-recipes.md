# Minimal-reproduction recipes

Patterns the `bug-reproducer` agent should use to capture the smallest possible reproduction of a bug.

## HTTP / API bugs

```bash
# 1. Capture the exact request
curl -i -X POST http://localhost:3001/v1/companies \
  -H 'authorization: Bearer <test-token>' \
  -H 'content-type: application/json' \
  -d '{"name":"Acme","industry":"SaaS"}'

# 2. Capture the response (status, headers, body) verbatim

# 3. Capture the database state before and after
psql -h localhost -U dev <app>_dev -c \
  "SELECT id, name, industry, created_at FROM companies ORDER BY created_at DESC LIMIT 5;"
```

If the bug depends on a specific DB row, the repro snippet must include the seed SQL or fixture path.

## Frontend / Playwright bugs

```js
// repro.spec.ts — single test file, < 30 lines
import { test, expect } from '@playwright/test';

test('repro: clicking save on empty company form shows wrong error', async ({ page }) => {
  await page.goto('http://localhost:3000/login');
  await page.fill('[name=email]', 'qa@example.com');
  await page.fill('[name=password]', 'qa-password');
  await page.click('button:has-text("Sign in")');

  await page.goto('http://localhost:3000/companies/new');
  await page.click('button:has-text("Save")');

  // Expected: "Name is required"
  // Observed: "Internal server error"
  await expect(page.getByRole('alert')).toContainText('Name is required');
});
```

Run via the MCP Playwright server — same one `qa-flow-tester` uses.

## Test failures

```bash
# Isolate to the smallest failing test
<pm> test -- --testPathPattern=companies --testNamePattern="creates with valid input"

# Re-run 5 times to detect flake
for i in 1 2 3 4 5; do
  <pm> test -- --testPathPattern=companies --testNamePattern="creates with valid input" \
    | grep -E 'PASS|FAIL' | tail -1
done
```

If 5/5 fail → deterministic. If 1–4/5 fail → flake; characterize WHEN before fixing.

## Async race conditions

```bash
# Force the race window wider with a deliberate delay
NODE_OPTIONS='--inspect=0.0.0.0:9229' \
DEBUG_ARTIFICIAL_DELAY_MS=500 \
<pm> test -- --testPathPattern=concurrent-update
```

If adding artificial latency makes the bug appear reliably, the diagnosis is "no locking around the critical section" — write that in `ROOT_CAUSE.md`.

## "Works locally, fails in CI"

```bash
# Reproduce the CI environment locally with Docker
docker run --rm -it \
  -v "$PWD:/app" -w /app \
  -e NODE_ENV=test \
  -e DATABASE_URL="postgres://test:test@host.docker.internal:5432/<app>_test" \
  node:20-bookworm-slim \
  bash -c '<pm> install && <pm> test'
```

If the bug reproduces in the container but not on bare-metal local → environment-specific. The repro snippet IS the docker command.

## Memory / leak bugs

```bash
# Snapshot heap before and after the suspect operation
node --inspect=0.0.0.0:9229 --expose-gc apps/api/dist/main.js &
PID=$!
sleep 5
curl http://localhost:9229/json | jq '.[0].webSocketDebuggerUrl'
# Use Chrome DevTools to take heap snapshots before/after triggering the bug
kill $PID
```

The repro is "after N invocations of route X, heap grows by Y MB" with concrete numbers.

## Production-only bugs (cannot reproduce locally)

- Capture: full request/response logs, container resource limits, env vars (redacted), recent deploys
- The repro is the **forensic timeline** — there is no minimal repro because you don't control the environment
- Move directly to Phase 2 with the timeline as evidence — Phase 1's checklist is satisfied by "production timeline captured at <commit hash>"
