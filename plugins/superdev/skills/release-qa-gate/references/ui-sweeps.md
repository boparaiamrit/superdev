# UI sweeps — Playwright recipes

Use a standalone `playwright` install in a scratch folder (pin a version whose Chromium is already cached; do not download browsers mid-run). The Playwright MCP browser is one shared browser: at most one agent may use it, and parallel agents each need their own standalone install.

## Sign in once per role

Sign-in routes are rate limited and every agent shares one IP. Sign in once per role, save the session, reuse it for every route:

```js
async function session(browser, role) {
  const file = `qa/.auth/${role.name}.json`;            // gitignored with the rest of qa/
  if (existsSync(file)) return browser.newContext({ storageState: file });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  for (let attempt = 0; attempt < 5; attempt++) {
    const res = await signIn(page, role);                 // the app's real form, never a token shortcut
    if (res.status() !== 429) break;
    await page.waitForTimeout(Number(res.headers()['retry-after'] ?? 15) * 1000);
  }
  await ctx.storageState({ path: file });
  return ctx;
}
```

## Route × role × viewport × theme

```js
for (const role of roles) for (const theme of themes) {
  const ctx = await session(browser, role);
  const page = await ctx.newPage();
  await setTheme(page, theme);                            // the app's own switch, or emulateMedia({ colorScheme })
  const errors = [];
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', (e) => errors.push(String(e)));
  for (const route of routes) for (const width of [1280, 375]) {
    errors.length = 0;
    await page.setViewportSize({ width, height: 800 });
    const res = await page.goto(base + route.path, { waitUntil: 'networkidle' });
    const forbidden = await page.getByText(/does not allow|not allowed|permission/i).count();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    await page.screenshot({ path: `qa/${app}/${slug(route.path)}-${role.name}-${width}-${theme}.png`, fullPage: true });
    record({ route, role, width, theme, status: res?.status(), forbidden: forbidden > 0, overflow, errors: [...errors] });
  }
}
```

Expected outcome per cell comes from the permission map: allowed → content and no forbidden state; not allowed → the friendly forbidden state (never a crash, a blank page or a redirect loop).

Ignore only known framework noise (dev-only hot-reload logs) and record what was ignored.

## Link crawl (dead links = 0)

First learn what "not found" looks like: open `/qa-not-found-<random>` and record its heading text or a stable selector. Then collect every `a[href]` and every element with `role="link"` on every route visited; normalise internal URLs (strip hash, keep query); open each once following redirects. A status ≥ 400, a page showing the recorded not-found marker, or a redirect loop is a dead link. Also flag `href="#"`, `javascript:` links and buttons with no effect (click → no navigation, no network request, no DOM change within 1 s).

Buttons whose name implies a destructive or money action (delete, block, pay, unlock, adjust) are not clicked by the crawler; list them in the matrix (§3) for `role-matrix-tester` and `money-integrity-prober`.

## Forms

For every form: submit empty (expect field errors next to fields, focus on the first error), submit invalid values per field type, submit valid values (expect success state and the change visible after reload), submit twice quickly (expect one effect). Server 422 field errors must land on the matching fields.

## Dialogs, menus, keyboard

Open with keyboard (Enter/Space), focus moves inside, Tab cycles inside, Escape closes and focus returns to the trigger; no nested interactive elements (a button inside a clickable card); every icon-only button has an accessible name.

## Accessibility (axe)

Inject `axe-core` (exact version) and run `axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa'] })` per route × role × theme × viewport. Re-run after opening each dialog, once its animations have finished (below).

## Contrast across states

axe checks text at rest only. For every interactive element and every badge/tag variant, force each state, let transitions finish, then measure:

```js
const settle = (el) => el.evaluate((e) => Promise.all(e.getAnimations({ subtree: true }).map((a) => a.finished)));
// rest:     nothing
// hover:    await el.hover()
// focus:    press Tab until document.activeElement is the element (keyboard focus is what triggers :focus-visible; el.focus() is not)
// active:   await el.hover(); await page.mouse.down()  … measure … await page.mouse.up()
// disabled / selected: find a live instance on some route (an incomplete form disables Submit; a chosen filter is selected).
//           If no route can produce the state, record the cell N/A with that reason. Never build a fixture page.
await settle(el);
const { fg, bg } = await el.evaluate(effectiveColors);   // getComputedStyle color; walk ancestors compositing alpha for the background
```

When the background is a gradient, image or blur, sample the screenshot pixels behind the text's bounding box and use the worst pair.

| What | Minimum |
| --- | --- |
| Text | 4.5:1 (3:1 for ≥ 24 px, or ≥ 18.7 px bold) |
| Icons, focus rings, and the boundary of outline/ghost buttons, inputs, checkboxes and toggles against what surrounds them (WCAG 1.4.11) | 3:1 |
| Disabled controls | exempt from WCAG; house rule 3:1 so they stay legible — below that is a Minor finding |

Two rules beyond the ratio:

- **No black or near-black text (OKLCH lightness < 0.3) on a saturated fill (OKLCH chroma ≥ 0.1)**, even when the ratio passes. Use white or a dark ink of the fill's own hue. Brand colours used behind text must be their darker, text-safe shade.
- Hover and selected states must not drop below the rest state's minimum. Check light and dark themes separately.

## Mobile viewport

At 375 × 800: no horizontal scroll, tables inside scroll containers, sticky bars do not cover content, tap targets ≥ 44 × 44 CSS px (48 dp in the phone app), dialogs fit, the on-screen keyboard (in a real device run) does not hide the focused field.

## Inside the phone WebView

A debug build exposes the WebView over the DevTools protocol: `adb shell cat /proc/net/unix | grep webview_devtools_remote` → `adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>` → `chromium.connectOverCDP('http://127.0.0.1:9333')`. The same axe, contrast and tap-target scripts then run against the app's own pages.

## Live-update checks in the browser

Two contexts (e.g. staff in admin, user in web). Act in one, measure in the other with `page.waitForFunction` on the UI change; record milliseconds. Also: open three tabs of one app and confirm a single stream (DevTools protocol: count `text/event-stream` requests) and hand-over when the leader tab closes.
