# UI sweeps

Browser recipes for gate steps 3 to 5 and 9. Use a standalone `playwright` install in a scratch folder: an exact release at least two weeks old whose Chromium is 135 or newer (Navree UI targets Chrome 135 and later), with the browsers installed before the run and not during it. Every agent has its own install and its own context; never share a browser.

## Sign in once per role

Sign in through the app's real sign-in form, never through a token shortcut: a Navree UI app's sign-in page, or a Next.js app's `/login`, which posts to `/api/auth/login` and, for an account with two-factor, to `/api/auth/2fa/verify`. Save the session with `storageState` under `qa/.auth/<role>.json` (git-ignored with the rest of `qa/`). On a 429 wait for `Retry-After`.

One account, one agent, one context at a time. On Next.js the session is a pair of token cookies: refresh tokens rotate and a reused one ends the family, so a saved session loaded into two contexts breaks as soon as the first one refreshes (rule QA-3, hard rule 21).

```js
async function session(browser, role) {
  const file = `qa/.auth/${role.name}.json`;
  if (existsSync(file)) return browser.newContext({ storageState: file });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  for (let attempt = 0; attempt < 5; attempt++) {
    const res = await signIn(page, role);                // the real form
    if (res.status() !== 429) break;
    await page.waitForTimeout(Number(res.headers()['retry-after'] ?? 15) * 1000);
  }
  await ctx.storageState({ path: file });
  return ctx;
}
```

## Routes, roles, widths, modes

For each role, mode and route, at 1440 and 390 px: open the page and record the status, the console errors (`console` events of type `error` and `pageerror`), horizontal overflow (`document.documentElement.scrollWidth > innerWidth + 1`) and a full-page screenshot named `<route-slug>-<role>-<width>-<mode>.png`. Set the mode with the app's own switch; where the app follows the device (`Mode::System` on Navree UI), `page.emulateMedia({ colorScheme })` does it.

The expected result of each cell comes from `## Access` of `EXECUTION_PLAN.md`: allowed shows content; refused shows the app's refusal state, never a crash, a blank page, a redirect loop or a JSON error body. A page route that answers a JSON error was declared without the `!` prefix (rule NUI-2). The app decides what its refusal and not-found pages look like, so learn the markers once: open `/qa-not-found-<random>` and a page the role may not open, and record each one's heading text or a stable selector in the matrix. Ignore only known framework noise, and record what was ignored.

## Link crawl

Collect every `a[href]` and `role="link"` on each visited route. Normalise internal URLs (strip the hash, keep the query) and open each once, following redirects. A status of 400 or more, a page showing the not-found marker or a redirect loop is a dead link. Also flag `href="#"`, `javascript:` links and buttons with no effect (a click that causes no navigation, no request and no change to the page within 1 s). Navree UI links are boosted: a click fetches the next page and morphs what changed, so judge the resulting URL and content rather than a full page load. The crawler does not click controls named delete, block, pay, unlock or adjust; it lists them in section 3 for `role-matrix-tester` and `money-integrity-prober`.

## Forms and dialogs

For every form: submit it empty, with invalid values per field type, with valid values, and twice quickly. Expect field errors beside the fields with focus on the first, the success state and the change visible after a reload, and one effect from the double submit. A rejected Navree UI form answers 422 with the errors under the fields; on Next.js the API's 400 `errors` land on the matching fields (hard rule 8).

For every dialog and menu: open it with Enter or Space, focus moves inside, Tab cycles inside, Escape closes it and returns focus to the trigger. No interactive element sits inside another (a button inside a clickable card), and every icon-only button has an accessible name.

## Accessibility with axe

Inject `axe-core` at an exact version and run it with `runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']` on each route, role, mode and width. Run it again after each dialog opens and its animation has finished. No violation is allowed, the bar `navree-design-to-ui` sets for its own screens.

## Contrast across states

axe checks text at rest only. For each interactive element and each badge or tag variant, force each state, let transitions finish, then measure. `Theme::custom` refuses text that fails WCAG AA when the theme is built, but the gate measures what is rendered in every state, so the two checks do not replace each other.

```js
const settle = (el) => el.evaluate((e) => Promise.all(e.getAnimations({ subtree: true }).map((a) => a.finished)));
// rest: nothing        hover: await el.hover()
// focus: press Tab until document.activeElement is the element (keyboard focus triggers :focus-visible; el.focus() does not)
// active: await el.hover(); await page.mouse.down() ... measure ... await page.mouse.up()
// disabled, selected: find a live instance on some route (an incomplete form disables Submit; a chosen filter is selected);
//   if no route produces the state it has no cell, and nobody builds a fixture page
await settle(el);
const { fg, bg } = await el.evaluate(effectiveColors);   // computed colour; composite the ancestors' alpha for the background
```

When the background is a gradient, an image or a blur, sample the screenshot pixels behind the text's bounding box and use the worst pair.

| What | Minimum |
|---|---|
| Text | 4.5:1 (3:1 at 24 px or more, or 18.7 px bold or more) |
| Icons, focus rings, and the edge of outline or ghost buttons, inputs, checkboxes and toggles against what surrounds them (WCAG 1.4.11) | 3:1 |
| Disabled controls | exempt from WCAG; the house minimum is 3:1, and less is `Minor` |

Text, icons and control edges under their minimum are `Major` findings. Two further rules apply. Text with OKLCH lightness below 0.3 on a fill with OKLCH chroma of 0.1 or more fails even when the ratio passes (a `Minor` finding): use white or a dark ink of the fill's own hue. Hover and selected states must not fall below the rest state's minimum; check light and dark mode separately.

## Mobile width

At 390 × 800: no horizontal scroll, tables inside scroll containers, sticky bars do not cover content, tap targets at least 44 × 44 CSS px (48 dp in a Tauri client), dialogs fit and, on a real device, the on-screen keyboard does not hide the focused field. Below 768 px the Navree UI sidebar becomes a sheet: open it and use it.

## Inside a Tauri client's WebView

A debug build exposes the WebView over the DevTools protocol. Find the socket with `adb shell cat /proc/net/unix` (the name holds `webview_devtools_remote`), forward it with `adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>`, and connect with `chromium.connectOverCDP('http://127.0.0.1:9333')`. The axe, contrast and tap-target scripts above then run on the app's own pages.

## Render check for Navree UI pages (rule QA-10)

The prefix of a framework script's `src` is `/_navree/ui/`; when the app serves a `/profile` page, load it and compare what its scripts look like. For every Navree UI page of section 2 with Expect `page`, as an allowed role, read the rendered HTML. A `style` attribute, a `<style>` element, or a `<script>` that rule QA-10 does not allow is a `Major` finding citing hard rule 14 (a page with a table may load a script module that another page does not; the rule allows it when its `src` has the prefix). The matrix cell quotes the counts: `render check: 38 pages, 0 style attributes, 0 style elements, 0 unexpected scripts`.

## Live-update latency

Open two contexts, for example staff in the admin client and a person in the web client. Act in one and measure in the other with `page.waitForFunction` on the visible change. The latency is the time from the committed write to the new content on the other screen; record it in milliseconds.
