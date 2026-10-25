# Committed runtime suites — the proof

Every control in this skill is proven by a script in the repo that runs against the live API with seeded data. They are `package.json` scripts named `test:<suite>` so `verify-done.mjs --suites` and `release-qa-gate` can run them all. Each prints one `PASS`/`FAIL` line per check and exits non-zero on any failure.

| Script | Proves |
| --- | --- |
| `test:contract` | Every end-user response parses with its shared schema **and** has no keys the schema does not declare; items not yet unlocked/purchased carry no contact fields |
| `test:security` | Two-factor, recovery codes, challenge binding, passkey-free mobile path, QR tickets, device list, revoke → next request 401, block → reason everywhere, refresh reuse and the tab grace window |
| `test:admin` (or `test:staff`) | Every staff endpoint against its contract; role × endpoint matrix; masking in every response; reveal audited; escalation guards; permission removal applies on the next request |
| `test:credits` (or `test:money`) | Parallel spends at exact balance, across lots, same item many times, last-unit races between accounts; idempotency (concurrent, replay, mismatch); discount re-validation at payment; reconciliation clean |
| `test:realtime` | Delivery and latency, filtering by scope and permission, grouping, read sync, preferences, push clean-up, replay, live session end |
| `smoke` (shell or node) | Health, auth round trip, the main money path, uploads, audit rows, outbound messages delivered by the worker |

## Shared helpers (copy into `apps/api/test/`)

**Retry on rate limits** — all local clients share one IP:

```ts
export async function testFetch(url: string, init: RequestInit): Promise<Response> {
  const res = await fetch(url, init);
  if (res.status !== 429) return res;
  await new Promise((r) => setTimeout(r, 61_000));   // wait out the window, retry once
  return fetch(url, init);
}
```

**Extra-key detection** — Zod strips unknown keys, so compare raw to parsed:

```ts
function extraKeys(raw: unknown, parsed: unknown, path = ''): string[] {
  if (Array.isArray(raw) && Array.isArray(parsed)) return raw.flatMap((r, i) => extraKeys(r, parsed[i], `${path}[${i}]`));
  if (raw && parsed && typeof raw === 'object' && typeof parsed === 'object')
    return Object.keys(raw).flatMap((k) => (k in parsed ? extraKeys((raw as any)[k], (parsed as any)[k], `${path}.${k}`) : [`${path}.${k}`]));
  return [];
}
```

**A cookie-jar client** per person (end user, each staff role), and **a stream reader** on `fetch` that parses `id:`/`data:` frames, records events with arrival times and offers `waitFor(predicate, ms)` and `waitClosed()`.

## Rules for writing them

- Sign in **once per role** and reuse that cookie jar for the whole suite; sign-in routes are rate limited and suites with many roles otherwise spend minutes waiting.
- Use seeded accounts that no one else is driving (other agents, a phone on an emulator); create the test's own records and clean up or leave them clearly labelled.
- Never weaken a control to make a test pass (raising rate limits, skipping the session check). Make the test patient instead.
- Tests that change shared state (block, revoke, reset password) restore it before exiting.
- A suite that crashes mid-run must not leave a security flag on (two-factor enabled on a demo account); restore in `finally`.
- After a code change restarts the API, wait for `/health` and re-open streams; a stream reader that does not reconnect will report false failures.
- Run the whole set on a fresh seed before declaring done: `db:fresh && smoke && test:contract && test:security && test:admin && test:credits && test:realtime`.
