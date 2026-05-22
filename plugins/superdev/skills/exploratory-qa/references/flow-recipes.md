# Flow Recipes (Phase 2 + 3)

Playwright snippets for `qa-flow-tester` to copy/adapt. Each recipe is a self-contained TypeScript block.

## Bootstrap (all flows start with this)

```ts
import { chromium, Page, Browser, BrowserContext } from 'playwright';
import * as fs from 'fs';

const API = 'http://localhost:3001/v1';
const WEB = 'http://localhost:3000';

async function bootstrap(role: 'admin'|'operator'|'viewer', viewport: 'desktop'|'mobile' = 'desktop') {
  const VIEWPORTS = {
    desktop: { width: 1440, height: 900 },
    mobile: { width: 375, height: 667 },
  };

  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: VIEWPORTS[viewport],
    recordHar: { path: `qa/flows/${process.env.FEATURE}/network.har` },
    recordVideo: { dir: `qa/flows/${process.env.FEATURE}/` },
  });

  await ctx.tracing.start({ screenshots: true, snapshots: true, sources: true });

  // Login by injecting the access token rather than clicking through login form
  // (login flow itself is tested separately under the auth feature)
  const email = `qa-${role}@example.com`;
  const resp = await ctx.request.post(`${API}/auth/login`, {
    data: { email, password: 'password123' },
  });
  const { accessToken } = await resp.json();
  await ctx.addInitScript((token) => {
    // App-specific: how does the FE persist the token?
    // For Bearer-in-memory: a global must be set or refresh on first request handles it
    // For httpOnly cookie: ctx.request.post above already set it
    (window as any).__qa_access_token = token;
  }, accessToken);

  const page = await ctx.newPage();
  return { browser, ctx, page };
}

async function teardown(browser: Browser, ctx: BrowserContext) {
  await ctx.tracing.stop({ path: `qa/flows/${process.env.FEATURE}/trace.zip` });
  await ctx.close();
  await browser.close();
}

function obs(severity: 'Critical'|'High'|'Medium'|'Low'|'Refactor',
             category: string, where: string,
             what: string, expected: string,
             evidence: string[],
             cause?: string) {
  return { severity, category, where, what, expected, evidence, cause };
}
```

## Happy-path recipe (CRUD feature)

```ts
const { browser, ctx, page } = await bootstrap('admin');
const findings: any[] = [];
const log = (m: string) => console.log(`[${process.env.FEATURE}] ${m}`);

try {
  // 1. List page loads
  log('Navigate to list page');
  const t0 = Date.now();
  await page.goto(`${WEB}/companies`);
  await page.waitForLoadState('networkidle');
  const listLoadTime = Date.now() - t0;
  await page.screenshot({
    path: `qa/flows/${process.env.FEATURE}/happy-path/screenshots/01-list-loaded.png`,
    fullPage: true,
  });
  if (listLoadTime > 2000) {
    findings.push(obs('High', 'Performance', 'list page',
      `List took ${listLoadTime}ms to network-idle`,
      '<1500ms for a list with default page size',
      ['screenshots/01-list-loaded.png']));
  }

  // 2. List has rows
  const rowCount = await page.locator('tbody tr').count();
  if (rowCount === 0) {
    findings.push(obs('Critical', 'Functional', 'list page',
      'Zero rows rendered despite seeded data',
      'At least 20 rows for default per_page=20',
      ['screenshots/01-list-loaded.png']));
  }

  // 3. Filter
  log('Apply filter');
  await page.fill('input[placeholder*="Search"]', 'Acme');
  await page.waitForLoadState('networkidle', { timeout: 5000 });
  await page.screenshot({
    path: `qa/flows/${process.env.FEATURE}/happy-path/screenshots/02-list-filtered.png`,
  });
  const filteredCount = await page.locator('tbody tr').count();
  log(`Filtered to ${filteredCount} rows`);

  // 4. Sort
  log('Sort by name');
  await page.click('th:has-text("Name")');
  await page.waitForLoadState('networkidle');
  await page.screenshot({
    path: `qa/flows/${process.env.FEATURE}/happy-path/screenshots/03-list-sorted.png`,
  });

  // 5. Click row → detail
  log('Click first row');
  await page.click('tbody tr:first-child');
  await page.waitForLoadState('networkidle');
  await page.screenshot({
    path: `qa/flows/${process.env.FEATURE}/happy-path/screenshots/04-detail.png`,
    fullPage: true,
  });

  // Detail page should have populated content
  const headingText = await page.locator('h1').first().textContent();
  if (!headingText || headingText.trim() === '') {
    findings.push(obs('High', 'Functional', 'detail page',
      'h1 empty on detail page', 'Entity name as h1',
      ['screenshots/04-detail.png']));
  }

  // 6. Create
  log('Open create dialog');
  await page.goto(`${WEB}/companies`);
  await page.click('button:has-text("Add")');  // or whatever your label is
  await page.waitForSelector('[role="dialog"]');
  await page.screenshot({
    path: `qa/flows/${process.env.FEATURE}/happy-path/screenshots/05-create-dialog.png`,
  });

  // 7. Fill form
  const uniqueName = `QA Test Co ${Date.now()}`;
  await page.fill('input[name="name"]', uniqueName);
  // ... other required fields per your contract

  // 8. Submit
  log('Submit create form');
  await page.click('button[type="submit"]:has-text("Create")');

  // 9. Toast appears
  const toastVisible = await page.locator('[data-sonner-toast]').isVisible({ timeout: 5000 });
  if (!toastVisible) {
    findings.push(obs('High', 'UX', 'create flow',
      'No success toast appeared after create', 'Sonner toast confirming creation',
      ['screenshots/05-create-dialog.png']));
  }

  // 10. List refreshed
  await page.waitForLoadState('networkidle');
  const listAfter = await page.locator(`tbody tr:has-text("${uniqueName}")`).count();
  if (listAfter === 0) {
    findings.push(obs('Critical', 'Functional', 'create flow',
      'Created record does not appear in list', 'List should refresh; record visible',
      []));
  }
  await page.screenshot({
    path: `qa/flows/${process.env.FEATURE}/happy-path/screenshots/06-list-after-create.png`,
  });

  // Cleanup: delete the QA-created record
  // (omitted for brevity)

} finally {
  await teardown(browser, ctx);
}

// Write observations
fs.writeFileSync(
  `qa/flows/${process.env.FEATURE}/happy-path/observations.md`,
  formatFindings(findings),
);
```

## Edge case: empty state

```ts
const { browser, ctx, page } = await bootstrap('admin');
// Log in as the user in "Empty Co" workspace (from QA_ENVIRONMENT.md)
// ... switch workspace via API or sign in as different user
const findings: any[] = [];

await page.goto(`${WEB}/companies`);
await page.waitForLoadState('networkidle');
await page.screenshot({
  path: `qa/flows/${process.env.FEATURE}/edge-cases/empty-state/screenshots/01-empty.png`,
  fullPage: true,
});

// Verify empty state component appears (not just headers)
const emptyState = await page.locator('text=/no .* yet|get started/i').count();
const rowCount = await page.locator('tbody tr').count();
if (rowCount === 0 && emptyState === 0) {
  findings.push(obs('High', 'Empty state', 'list page',
    'Zero rows AND no empty-state UI — just headers or blank',
    'Designed empty state with CTA button',
    ['screenshots/01-empty.png']));
}

// Empty state should have a CTA
const ctaCount = await page.locator('button:has-text("Add"),button:has-text("Create"),a:has-text("Create")').count();
if (emptyState > 0 && ctaCount === 0) {
  findings.push(obs('Medium', 'Empty state', 'list page',
    'Empty state has no CTA to add the first item',
    'Empty state includes a primary action button',
    ['screenshots/01-empty.png']));
}
```

## Edge case: error state

```ts
const { browser, ctx, page } = await bootstrap('admin');

// Mock the list endpoint to fail
await page.route(`**/v1/${process.env.FEATURE}**`, route =>
  route.fulfill({
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({ code: 'INTERNAL', message: 'Test failure', request_id: 'qa-test' }),
  }),
);

await page.goto(`${WEB}/${process.env.FEATURE}`);
// Give it 3s to settle into error state (not loading state)
await page.waitForTimeout(3000);
await page.screenshot({
  path: `qa/flows/${process.env.FEATURE}/edge-cases/error-state/screenshots/01-error.png`,
  fullPage: true,
});

// Check what's visible
const stillLoading = await page.locator('[role="status"]:has-text("loading"),.animate-pulse').count();
const errorMessage = await page.locator('text=/something went wrong|error|failed/i').count();
const retryButton = await page.locator('button:has-text("Retry"),button:has-text("Try again")').count();

if (stillLoading > 0) {
  findings.push(obs('High', 'Error state', 'list page',
    'Page stuck in loading state when API returns 500',
    'Error UI with message + retry',
    ['screenshots/01-error.png']));
}
if (errorMessage === 0) {
  findings.push(obs('High', 'Error state', 'list page',
    'No error message visible to user',
    'Friendly error message explaining what went wrong',
    ['screenshots/01-error.png']));
}
if (retryButton === 0) {
  findings.push(obs('Medium', 'Error state', 'list page',
    'No retry option',
    'Retry button to refetch',
    ['screenshots/01-error.png']));
}
```

## Edge case: large data + filter freeze

```ts
const { browser, ctx, page } = await bootstrap('admin');
// Use the "Big Co" workspace with 2500+ records
// (switch via auth as a user in that workspace)

await page.goto(`${WEB}/${process.env.FEATURE}?per_page=1000`);
await page.waitForLoadState('networkidle');

await page.screenshot({
  path: `qa/flows/${process.env.FEATURE}/edge-cases/large-data/screenshots/01-loaded.png`,
});

// Time the filter input response
const t0 = Date.now();
await page.fill('input[placeholder*="Search"]', 'A');
// Wait until visible row count changes OR a network request completes
await Promise.race([
  page.waitForFunction(() => {
    const tbody = document.querySelector('tbody');
    if (!tbody) return false;
    return tbody.children.length < 1000;
  }, { timeout: 5000 }),
  page.waitForResponse(r => r.url().includes(`/v1/${process.env.FEATURE}`), { timeout: 5000 }),
]);
const filterTime = Date.now() - t0;

if (filterTime > 500) {
  findings.push(obs(filterTime > 1500 ? 'Critical' : 'High',
    'Performance', `${process.env.FEATURE} list (1000 rows)`,
    `Filter took ${filterTime}ms to respond`,
    '<300ms (debounced server-side filter)',
    ['screenshots/01-loaded.png']));
}

// Source check: is filter implemented client-side?
// (qa-performance-prober does this too; flagging here is a hint)
```

## Edge case: keyboard navigation

```ts
const { browser, ctx, page } = await bootstrap('admin');

await page.goto(`${WEB}/${process.env.FEATURE}`);
await page.waitForLoadState('networkidle');

// Tab through the page header → action buttons
const tabbedElements: string[] = [];
for (let i = 0; i < 20; i++) {
  await page.keyboard.press('Tab');
  const focusedTag = await page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body) return null;
    return `${el.tagName.toLowerCase()}${el.getAttribute('role') ? `[role=${el.getAttribute('role')}]` : ''}:${(el.textContent || '').trim().slice(0, 30)}`;
  });
  if (focusedTag) tabbedElements.push(focusedTag);
}

await page.screenshot({
  path: `qa/flows/${process.env.FEATURE}/edge-cases/keyboard-nav/screenshots/01-after-tabbing.png`,
});

// Check focus visibility
const focusStyles = await page.evaluate(() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const cs = window.getComputedStyle(el);
  return { outline: cs.outline, outlineWidth: cs.outlineWidth, boxShadow: cs.boxShadow };
});
if (focusStyles && focusStyles.outline === 'none' && !focusStyles.boxShadow.includes('rgb')) {
  findings.push(obs('High', 'Accessibility', `${process.env.FEATURE} list`,
    'Focused element has no visible focus ring',
    'Visible outline or shadow on focused interactive elements',
    ['screenshots/01-after-tabbing.png']));
}

// Open a dialog, verify Escape closes
await page.click('button:has-text("Add")');
await page.waitForSelector('[role="dialog"]');
await page.keyboard.press('Escape');
const dialogStillOpen = await page.locator('[role="dialog"]').isVisible();
if (dialogStillOpen) {
  findings.push(obs('Medium', 'Accessibility', `${process.env.FEATURE} create dialog`,
    'Escape does not close dialog',
    'Dialog dismisses on Escape',
    []));
}

// Focus trap: open dialog, Tab repeatedly, focus should stay inside
await page.click('button:has-text("Add")');
await page.waitForSelector('[role="dialog"]');
let focusEscaped = false;
for (let i = 0; i < 30; i++) {
  await page.keyboard.press('Tab');
  const inDialog = await page.evaluate(() => {
    const el = document.activeElement;
    return el?.closest('[role="dialog"]') !== null;
  });
  if (!inDialog) { focusEscaped = true; break; }
}
if (focusEscaped) {
  findings.push(obs('Medium', 'Accessibility', `${process.env.FEATURE} create dialog`,
    'Focus escapes dialog when tabbing',
    'Focus trapped inside dialog',
    []));
}
```

## Edge case: mobile

```ts
const { browser, ctx, page } = await bootstrap('admin', 'mobile');  // 375x667

await page.goto(`${WEB}/${process.env.FEATURE}`);
await page.waitForLoadState('networkidle');
await page.screenshot({
  path: `qa/flows/${process.env.FEATURE}/edge-cases/mobile/screenshots/01-list.png`,
  fullPage: true,
});

// Sidebar should be off-screen by default at mobile width
const sidebarVisible = await page.locator('[data-sidebar="sidebar"]').isVisible();
const sidebarOverlay = await page.locator('[data-sidebar="overlay"]').count();
// shadcn sidebar block uses Sheet on mobile; the trigger button should be present
const sidebarTrigger = await page.locator('[data-sidebar="trigger"]').isVisible();
if (!sidebarTrigger) {
  findings.push(obs('Critical', 'Mobile', `${process.env.FEATURE} list`,
    'No sidebar trigger on mobile — no way to navigate',
    'Hamburger / sidebar trigger button visible at top',
    ['screenshots/01-list.png']));
}

// Horizontal scroll check
const hasHorizontalScroll = await page.evaluate(() => {
  return document.documentElement.scrollWidth > document.documentElement.clientWidth;
});
if (hasHorizontalScroll) {
  findings.push(obs('High', 'Mobile', `${process.env.FEATURE} list`,
    'Horizontal scroll on mobile viewport',
    'Page fits within 375px width',
    ['screenshots/01-list.png']));
}

// Buttons should be tappable (>= 44x44 per WCAG)
const buttons = await page.locator('button').all();
for (const button of buttons.slice(0, 10)) {  // sample
  const box = await button.boundingBox();
  if (box && (box.width < 32 || box.height < 32)) {
    const text = await button.textContent();
    findings.push(obs('Medium', 'Mobile', `${process.env.FEATURE} list`,
      `Button "${text?.trim().slice(0, 20)}" is ${box.width}×${box.height}px — too small to tap`,
      '≥44×44px for primary touch targets (WCAG 2.5.5)',
      ['screenshots/01-list.png']));
  }
}

// Open create dialog at mobile
await page.click('button:has-text("Add"),[data-sidebar="trigger"]');
await page.waitForTimeout(500);
await page.screenshot({
  path: `qa/flows/${process.env.FEATURE}/edge-cases/mobile/screenshots/02-after-tap.png`,
  fullPage: true,
});
// Verify dialog fits viewport
const dialog = page.locator('[role="dialog"]').first();
if (await dialog.isVisible()) {
  const dBox = await dialog.boundingBox();
  if (dBox && dBox.width > 375) {
    findings.push(obs('High', 'Mobile', `${process.env.FEATURE} create dialog`,
      `Dialog width ${dBox.width}px exceeds 375px viewport`,
      'Dialog fits viewport (full-width or with safe margin)',
      ['screenshots/02-after-tap.png']));
  }
}
```

## Edge case: concurrent mutation (double-submit)

```ts
const { browser, ctx, page } = await bootstrap('admin');

// Track POST requests to the create endpoint
let postCount = 0;
page.on('request', req => {
  if (req.method() === 'POST' && req.url().endsWith(`/v1/${process.env.FEATURE}`)) {
    postCount++;
  }
});

await page.goto(`${WEB}/${process.env.FEATURE}`);
await page.click('button:has-text("Add")');
await page.waitForSelector('[role="dialog"]');
await page.fill('input[name="name"]', `Race ${Date.now()}`);
// Fill other required fields...

// Click submit 5 times rapidly
const submit = page.locator('button[type="submit"]');
await Promise.all([
  submit.click(),
  submit.click({ noWaitAfter: true }),
  submit.click({ noWaitAfter: true }),
  submit.click({ noWaitAfter: true }),
  submit.click({ noWaitAfter: true }),
]);
await page.waitForLoadState('networkidle');

if (postCount > 1) {
  findings.push(obs('Critical', 'Mutation', `${process.env.FEATURE} create form`,
    `Fast-clicked submit ${postCount} times — fired ${postCount} POSTs (created duplicates)`,
    'Submit button should disable on first click; only 1 POST fires',
    []));
}
```

## Edge case: long content overflow

```ts
const longCo = process.env.LONG_NAME_COMPANY_ID;  // from QA_ENVIRONMENT.md
await page.goto(`${WEB}/companies/${longCo}`);
await page.waitForLoadState('networkidle');
await page.screenshot({
  path: `qa/flows/${process.env.FEATURE}/edge-cases/long-content/screenshots/01-detail.png`,
  fullPage: true,
});

// Check the h1 isn't overflowing
const h1Box = await page.locator('h1').first().boundingBox();
const viewport = page.viewportSize();
if (h1Box && viewport && h1Box.x + h1Box.width > viewport.width) {
  findings.push(obs('High', 'Layout', 'company detail',
    `h1 overflows viewport (text extends past ${viewport.width}px)`,
    'Long names ellipsis or wrap gracefully',
    ['screenshots/01-detail.png']));
}

// Same for table row — go to list view, find this company in the row
await page.goto(`${WEB}/companies`);
await page.fill('input[placeholder*="Search"]', 'Acme Pharmaceutical');
await page.waitForLoadState('networkidle');
await page.screenshot({
  path: `qa/flows/${process.env.FEATURE}/edge-cases/long-content/screenshots/02-list-row.png`,
});
// Inspect the row's height
const row = page.locator(`tr:has-text("Acme Pharmaceutical")`).first();
const rowBox = await row.boundingBox();
if (rowBox && rowBox.height > 80) {
  findings.push(obs('Medium', 'Layout', 'companies list row',
    `Row with long name renders ${rowBox.height}px tall`,
    'All rows uniform height; long names truncate with ellipsis',
    ['screenshots/02-list-row.png']));
}
```

## Edge case: special characters / XSS check

```ts
await page.goto(`${WEB}/contacts/new`);
await page.fill('input[name="name"]', `<script>window.__qa_xss=true</script>`);
await page.fill('input[name="email"]', `qa-xss-${Date.now()}@example.com`);
await page.click('button[type="submit"]');
await page.waitForLoadState('networkidle');

// Did the script execute?
const xss = await page.evaluate(() => (window as any).__qa_xss === true);
if (xss) {
  findings.push(obs('Critical', 'Security', 'contacts create',
    'XSS: script content executed in browser context',
    'Content stored and rendered as literal text',
    []));
  // Escalate to security skill if installed
}
```

## Writing observations.md

`formatFindings` produces:

```markdown
# Observations: <feature> / <mode>

## Summary

- Critical: 1
- High: 3
- Medium: 2
- Low: 0
- Refactor: 0

## Findings

### F-companies-1: List took 2.4s to network-idle [High]

- **Category:** Performance
- **Where:** /companies (desktop, admin role)
- **What I saw:** List page took 2.4 seconds from navigation to network-idle.
- **What I expected:** <1.5s for the default page size (20 items).
- **Evidence:**
  - Screenshot: qa/flows/companies/happy-path/screenshots/01-list-loaded.png
  - Trace: qa/flows/companies/happy-path/trace.zip
- **Likely cause:** Backend N+1 on company counts; or large bundle size. See qa-performance-prober for deep dive.

### F-companies-2: ...
```

## Notes on Playwright setup

- Run with `pnpm dlx playwright install chromium` if browsers aren't installed
- Use `recordVideo` sparingly — videos are large; only on flows that produce findings
- Trace files (`trace.zip`) are gold — they're viewable in trace.playwright.dev with full step-by-step replay
- `networkidle` is the safest wait for SPA navigation; `domcontentloaded` is too early
