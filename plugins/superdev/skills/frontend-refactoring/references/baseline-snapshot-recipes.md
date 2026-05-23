# Baseline snapshot recipes

Playwright patterns for `module-behavior-snapshotter`. The whole point: capture enough detail that `conversion-verifier` can prove the conversion changed NOTHING.

## Per-route capture

```ts
import { test, expect } from '@playwright/test';

const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'tablet',  width: 768,  height: 1024 },
  { name: 'mobile',  width: 375,  height: 667  },
];

const ROUTES = ['/companies', '/companies/abc-123-id', '/companies/new'];

for (const v of VIEWPORTS) {
  for (const route of ROUTES) {
    test(`baseline: ${route} @ ${v.name}`, async ({ browser }) => {
      const ctx = await browser.newContext({ viewport: v });
      const page = await ctx.newPage();

      // Capture network
      const har = `baseline/companies/${slug(route)}/${v.name}.har`;
      await ctx.routeFromHAR(har, { update: true });

      // Capture console
      const logs: string[] = [];
      page.on('console', (msg) => logs.push(`${msg.type()}: ${msg.text()}`));

      await page.goto(`http://localhost:3000${route}`);
      await page.waitForLoadState('networkidle');

      // Screenshot
      await page.screenshot({
        path: `baseline/companies/${slug(route)}/${v.name}.png`,
        fullPage: true,
      });

      // DOM snapshot (main content only — skip nav/sidebar boilerplate)
      const html = await page.locator('main').innerHTML();
      require('fs').writeFileSync(`baseline/companies/${slug(route)}/${v.name}.html`, html);

      // Computed styles for key elements
      const styles = await page.evaluate(() => {
        const sample: Record<string, Record<string, string>> = {};
        for (const sel of ['.drawer', '.modal', '.popover', 'table', '[role="dialog"]', '[role="alertdialog"]']) {
          const el = document.querySelector(sel);
          if (!el) continue;
          const cs = getComputedStyle(el as Element);
          sample[sel] = {
            width: cs.width, height: cs.height,
            position: cs.position, zIndex: cs.zIndex,
            padding: cs.padding, margin: cs.margin,
            backgroundColor: cs.backgroundColor, color: cs.color,
          };
        }
        return sample;
      });
      require('fs').writeFileSync(`baseline/companies/${slug(route)}/${v.name}-styles.json`, JSON.stringify(styles, null, 2));

      // Console
      require('fs').writeFileSync(`baseline/companies/${slug(route)}/${v.name}-console.log`, logs.join('\n'));
    });
  }
}
```

## Per-interaction trace

Each "flow" in `BEHAVIOR_BASELINE.md` becomes a Playwright script that walks the flow and captures per-step artifacts.

### Wizard happy-path

```ts
test('flow: create-wizard happy path', async ({ page }) => {
  await login(page);
  await page.goto('/companies');
  await page.click('button:has-text("New company")');
  // Capture step 1
  await snap(page, 'flows/companies-create-happy/01-wizard-opened.png');

  await page.fill('[name=name]', 'Acme Industries');
  await page.fill('[name=industry]', 'Manufacturing');
  await page.fill('[name=website]', 'https://acme.example');
  await page.click('button:has-text("Next")');
  await snap(page, 'flows/companies-create-happy/02-step1-submitted.png');

  // ... continue through all 8 steps ...

  await page.click('button:has-text("Create")');
  await page.waitForURL(/\/companies\/[a-f0-9-]+$/);
  await snap(page, 'flows/companies-create-happy/09-created.png');

  // Verify DB state too (the UI can lie)
  // ... query DB ...
});

async function snap(page, file) {
  await page.screenshot({ path: `baseline/companies/${file}`, fullPage: true });
  const html = await page.locator('main').innerHTML();
  require('fs').writeFileSync(file.replace('.png', '.html'), html);
}
```

### Drawer open/close

```ts
test('flow: bulk-edit drawer', async ({ page }) => {
  await login(page);
  await page.goto('/companies');

  // Select 5 rows
  for (let i = 0; i < 5; i++) {
    await page.locator(`tr:nth-child(${i + 2}) input[type=checkbox]`).check();
  }
  await snap(page, 'flows/companies-bulk-edit/01-selected.png');

  // Open bulk drawer
  await page.click('button:has-text("Bulk edit")');
  await page.waitForSelector('[role="dialog"]'); // shadcn Sheet sets role
  await snap(page, 'flows/companies-bulk-edit/02-drawer-open.png');

  // Capture computed style of the drawer to verify size/position later
  const drawerStyles = await page.evaluate(() => {
    const el = document.querySelector('[role="dialog"]');
    return el ? Object.fromEntries(Object.entries(getComputedStyle(el)).filter(([k]) => /width|height|position|right|top|z-?index/i.test(k))) : null;
  });
  require('fs').writeFileSync('baseline/companies/flows/companies-bulk-edit/02-drawer-styles.json', JSON.stringify(drawerStyles, null, 2));

  // Submit
  await page.fill('[name=newOwner]', 'manager@example.com');
  await page.click('button:has-text("Apply to selected")');
  await page.waitForSelector('[role="dialog"]', { state: 'hidden' });
  await snap(page, 'flows/companies-bulk-edit/03-applied.png');
});
```

### Delete confirmation modal

```ts
test('flow: delete with confirm', async ({ page }) => {
  await login(page);
  await page.goto('/companies');
  await page.locator('tr:nth-child(2) [aria-label="Open menu"]').click();
  await page.click('text=Delete');
  await page.waitForSelector('[role="alertdialog"]');
  await snap(page, 'flows/companies-delete/01-confirm-shown.png');

  await page.click('button:has-text("Delete")');
  // Capture the 300ms delay if present in source
  const startMs = Date.now();
  await page.waitForSelector('[role="alertdialog"]', { state: 'hidden' });
  const elapsedMs = Date.now() - startMs;
  require('fs').writeFileSync('baseline/companies/flows/companies-delete/02-delay-ms.txt', String(elapsedMs));
});
```

## Capture under realistic data volume

Don't snapshot against an empty database — drift in pagination, virtualization, scroll, sticky headers won't show up. Seed real volumes:

```bash
psql <app>_dev -f scripts/seed-companies-realistic.sql  # inserts 5,000 rows
```

Or use the QA agent's seeder:

```
Dispatch qa-environment to seed realistic data before snapshotting.
```

## What NOT to capture

- ❌ Animations mid-frame (deterministic frame is fine; mid-animation isn't)
- ❌ Timestamps in rendered UI ("created 2 minutes ago") — these change between snapshots. Either freeze time or exclude from DOM diff.
- ❌ Random IDs in DOM (`data-id="abc-123"`) — same problem; use stable seed data
- ❌ Auth tokens / session IDs in HAR — strip before saving

## Auth-gated routes

```ts
async function login(page) {
  await page.goto('/login');
  await page.fill('[name=email]', process.env.QA_EMAIL || 'qa@example.com');
  await page.fill('[name=password]', process.env.QA_PASSWORD || 'qa-password');
  await page.click('button:has-text("Sign in")');
  await page.waitForURL(/^(?!.*\/login)/);
}
```

Use the same QA_EMAIL / QA_PASSWORD env vars as `qa-environment` so both phases capture under identical auth state.
