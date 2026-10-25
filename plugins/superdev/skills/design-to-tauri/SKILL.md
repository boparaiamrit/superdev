---
name: design-to-tauri
description: Use when a superdev build needs a desktop or mobile client (Android, iOS, Windows, macOS, Linux) — "Tauri app", "phone app", "mobile app", "APK", "desktop app", "native app from the web screens" — or when an existing Tauri client needs sign-in, live updates, phone notifications, emulator QA, hardening or a store release. Assumes the monorepo already has packages/contracts and an API, with or without mobile sign-in endpoints.
---

# Design to Tauri — one codebase, real devices, verified

A Tauri 2 client lives in the monorepo as `apps/mobile` (or `apps/desktop`), renders the same contracts as the web app, and talks to the same API. It is **not** a wrapped website: it has its own auth flow (Bearer tokens), its own security surface (capabilities, CSP, on-device secrets) and its own failure modes (keyboard insets, back button, background freezing, WebView limits). Each of those is covered by a reference below; read the one you need, when you need it.

**Done means proven on a device.** A green `typecheck` + Vite build says nothing about whether the APK installs, signs in, survives a token refresh, or shows a notification. Every client module is verified on an emulator or phone with `adb` (or the iOS simulator) before the next one starts.

## When to use / not

Use for: a new desktop or mobile client in a superdev build; adding sign-in, live updates, phone alerts or QR sign-in to an existing Tauri app; hardening or releasing one.

Not for: the web frontend (`design-to-nextjs`), server security (`security-foundation`), the final cross-app QA pass (`release-qa-gate`, which runs this skill's device QA).

## Build order (inside superdev-build Step 5)

0. **Say the platform limits and ask.** Before building: iOS builds, signing and simulator runs need a Mac with Xcode; alerts to a fully closed app need FCM/APNs credentials only the person can create. Ask whether they want closed-app push set up; record the answer in `EXECUTION_PLAN.md`.
1. **Scaffold** per [`references/scaffolding.md`](references/scaffolding.md): Vite + React + TypeScript + Tailwind + shadcn (same tokens as the web app), `@<scope>/contracts`, TanStack Query, plugin set chosen deliberately (http, store or stronghold, opener, os; barcode-scanner, notification, deep-link only if used). Generate `src-tauri/gen/android` and keep it in version control.
2. **Lock it down** per [`references/security.md`](references/security.md) before the first screen: CSP set, capabilities least-privilege, HTTP scope listing exact API origins, devtools only in debug, cleartext only in debug, no secrets in the bundle, refresh token in the OS keystore (not a plain store file) in debug and release alike.
3. **Auth** per [`references/auth-and-api.md`](references/auth-and-api.md): the API's mobile token endpoints (build them on the server first, per `security-foundation`, if the API has only cookie sign-in), Bearer access token in memory, single-flight refresh with one retry, `403 ACCOUNT_BLOCKED` → blocked screen with the reason, QR sign-in from the web app, `Idempotency-Key` on money-moving calls. Passkeys do not work in the system WebView — do not ship a passkey button.
4. **Screens**, one module at a time against the canonical contracts (no local response schemas). No phone design? Derive it from the web app's tokens and components: one column, a bottom tab bar of at most five destinations, sheets for secondary actions, 48 dp tap targets, the same words as the web app. Lists: skeleton, empty state with a next action, error with retry, pull to refresh. Android back: close the open sheet → go back a screen → home tab → leave.
5. **Live updates and phone alerts** per [`references/realtime-and-notifications.md`](references/realtime-and-notifications.md): one SSE stream through the native HTTP client, replay with `Last-Event-ID`, reconnect on resume/online, local notifications only when backgrounded and allowed by the person's Push preference.
6. **Verify on a device** per [`references/device-qa.md`](references/device-qa.md) after every module: build the APK, install, drive the flow with `adb`, screenshot, read logcat. Record evidence under `apps/mobile/qa/` (gitignored).
7. **Release** per [`references/release.md`](references/release.md) when asked: signing, version codes, AAB, iOS on a Mac.

## Quick reference

| Concern | Rule |
| --- | --- |
| API calls | Through `@tauri-apps/plugin-http` (native, no CORS, streams). Allowed origins listed exactly in the HTTP capability. |
| Emulator → host | Android emulator reaches the computer at `10.0.2.2`; iOS simulator and desktop use `localhost`. |
| Tokens | Access token in memory; refresh token rotated on every refresh and kept in the Android Keystore / iOS Keychain (security.md §3), in debug and release alike. A plain store file is for preferences only. |
| Debug vs release | Emulator/LAN origins live in `capabilities/dev.json`, enabled only through `tauri.dev.conf.json` (`--config`). `verify-done.mjs --strict` fails a release set that still contains them. |
| Windows host | C++ Build Tools, WebView2, Rust MSVC; Developer Mode if the Android build cannot create symlinks. Android works on Windows; iOS does not. |
| Versions | Exact versions, at least two weeks old, same 2.x line for every Tauri crate/npm pair (crate `=x.y.z` matches npm `x.y.z`). |
| Insets | Edge-to-edge Android needs an insets listener that pads for status bar, cutout, gesture bar **and keyboard**, or the tab bar and sheets hide under them. |
| Camera from file input | Android 11+ needs a `<queries>` entry for `IMAGE_CAPTURE` or "Take a photo" falls back to the gallery. |
| Background | Android freezes a cached app ~10 s after it leaves the screen: the stream pauses, alerts stop. Closed-app push needs FCM (Android) / APNs (iOS) credentials — design for it, say so in settings. |
| iOS | Builds only on macOS with Xcode. Configure identifiers, icons and `Info.ios.plist` usage strings on any OS; build and sign on a Mac. |
| Proof | APK installed and driven on an emulator, screenshots + logcat with no app errors. Typecheck is not proof. |

## Common mistakes

- Shipping `"csp": null` or an HTTP capability with `"url": "https://*"` — any compromised page script can then call anything.
- Storing the refresh token in `tauri-plugin-store` for production — it is a plain JSON file in app data.
- Treating `fetch` 401 as "signed out" when the server said `ACCOUNT_BLOCKED` — the person never learns why.
- Letting two requests refresh at once — the second presents a rotated token and the server ends the whole session family.
- Showing an OS notification while the app is in the foreground and the in-app banner too — or showing one for a category whose Push switch is off.
- Declaring the phone app done from a desktop window or a 390 px browser tab.
- Copying a WebView workaround or plugin version pin from memory instead of checking the installed version's changelog.

## Reference files

| File | Read when |
| --- | --- |
| [`references/scaffolding.md`](references/scaffolding.md) | Creating the app, Android/iOS toolchains, generated projects |
| [`references/security.md`](references/security.md) | Before the first screen; before every release |
| [`references/auth-and-api.md`](references/auth-and-api.md) | Sign-in, tokens, refresh, QR sign-in, idempotency |
| [`references/realtime-and-notifications.md`](references/realtime-and-notifications.md) | Live updates, phone alerts, background behaviour |
| [`references/device-qa.md`](references/device-qa.md) | After every module; in `release-qa-gate` |
| [`references/release.md`](references/release.md) | Signing and store builds |
