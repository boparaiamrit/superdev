# Edge case catalog

The `edge-case-prober` runs every route × every category below. Add categories for your domain; do not remove the defaults.

## Default categories (run for every route)

| Category | Setup | What you're verifying |
|---|---|---|
| **Empty data** | DB has zero rows for the relevant table | Empty-state UI exists; not a blank page |
| **Loading state** | Playwright network throttle to "Slow 3G" | Skeleton or spinner appears; layout doesn't shift |
| **Error state** | Stop the API container OR intercept and return 500 | Error UI with retry; not white screen |
| **Large data** | Seed 10,000 rows for the relevant entity | Virtualization or pagination; browser stays responsive (< 2s scripting) |
| **Concurrent mutations** | Two Playwright contexts perform conflicting writes | Optimistic concurrency handled; second writer gets clear feedback |
| **Long content** | Strings up to 500 chars in titles/descriptions | No overflow into adjacent UI; truncation with ellipsis or wrap |
| **Special characters** | Emoji, RTL, `<script>alert(1)</script>`, SQL-injection-shaped strings | No XSS; no SQL error; correctly rendered |
| **Keyboard only** | Disable mouse in Playwright, navigate with Tab/Enter/Esc | Every interactive element reachable; focus visible |
| **Mobile viewport** | 375×667 (iPhone SE) | Responsive layout; no horizontal scroll on portrait |

## Per-domain extensions

Add categories for your project. Examples:

| Domain | Extra category |
|---|---|
| Multi-tenant SaaS | Cross-tenant data leak — log in as workspace A, attempt to read workspace B's IDs directly |
| Money / billing | Currency edge cases — zero, negative, fractional cents, very large values |
| Time / scheduling | Timezone — user in UTC+13 with a record created at UTC+0 day boundary |
| File upload | Large file (100MB), wrong MIME, no-extension, malicious extension (.exe.png) |
| Real-time / collaborative | Two clients editing same field simultaneously; reconnect after disconnect |

## How to set up edge conditions

### Empty data
```sql
TRUNCATE companies, deals, contacts CASCADE;
```

### Slow network (Playwright)
```js
await page.route('**/*', async (route) => {
  await new Promise(r => setTimeout(r, 2000));
  await route.continue();
});
```

### Error state
```bash
docker stop <workspace>_postgres
# or intercept and return 500
```
```js
await page.route('**/v1/companies', route =>
  route.fulfill({ status: 500, body: '{"error":"forced"}' })
);
```

### Large data
```bash
psql <app>_dev -f scripts/seed-large.sql  # inserts 10,000 rows
```

### Concurrent mutations
```js
const [ctxA, ctxB] = await Promise.all([browser.newContext(), browser.newContext()]);
const [pageA, pageB] = await Promise.all([ctxA.newPage(), ctxB.newPage()]);
await Promise.all([
  pageA.click('button:has-text("Save")'),
  pageB.click('button:has-text("Save")'),
]);
```
