---
name: design-to-tauri
description: Use when a superdev build needs a desktop or mobile client in Tauri (Android, iOS, Windows, macOS, Linux) on its Navree API, or when such a client needs sign-in, live updates, notifications, hardening, device QA or a store build. Optional step of a build.
---

# Design to Tauri

Navree Native is the framework's own client path; it is a preview behind `ui-native-preview` and may
change in a minor release. Use it only when the operator asks, with `navree-native`. This skill
builds the other kind of client: a Tauri 2 shell under `clients/<name>/` that calls the Navree API's
JSON routes. It is an optional step of a build, used when the `clients` line of `STACK.md` lists
`tauri-android`, `tauri-ios` or `tauri-desktop`. The client is not a wrapped website: it has its own
sign-in, its own security surface and its own failure modes, and it is done when it is proven on a
device (hard rule 25).

## Before building

- iOS builds, signing and the simulator need a Mac with Xcode. Android builds need the Android SDK
  and a JDK; Tauri's prerequisites page lists the rest for each host.
- Alerts to a fully closed app need Firebase (Android) or Apple push credentials that only the
  operator can create. Ask whether they want them and record the answer in `EXECUTION_PLAN.md`
  `## Integrations`.
- The client calls JSON routes, so every route it uses is in a contract with `#[api(..)]` even when
  `front_end` is `navree`; its types are generated from the OpenAPI document and no screen carries a
  hand-written response type.

## Steps

1. **Scaffold** under `clients/<name>/` from Tauri's official template (React and TypeScript), then
   `tauri android init`, and `tauri ios init` on a Mac; commit the generated `gen/` folders.
   - API types: `navree openapi:client --out clients/<name>/src/lib/api` (add `--input <openapi>`
     when `STACK.md` names a committed document); commit the output (hard rule 17).
   - Look: the web app's tokens when `front_end` is `next`, the Navree UI theme's values otherwise.
   - Plugins: the HTTP plugin for API calls (native, streams, no browser CORS), a keystore plugin for
     the refresh token, `opener` for links, and the notification plugin only for step 5. Each is
     pinned per rule TAU-9 and granted only the permissions it uses. Read a plugin's changelog for
     open mobile bugs before pinning it, and write any workaround next to the code with the version
     it applies to.
   - Edits to keep in `gen/android`: an insets listener in `MainActivity` that pads the content for
     the status bar, cutout, gesture bar and keyboard (an edge-to-edge window is not resized for the
     keyboard); Android back wired to the app's own stack (rule TAU-8); cleartext HTTP allowed in the
     debug manifest only; a `<queries>` entry for the `IMAGE_CAPTURE` intent when a screen opens the
     camera.
2. **Lock down** per [security](references/security.md) before the first screen. `verify-done.mjs`
   checks the shell's configuration, and that file names each check.
3. **Sign in.** On Android and iOS use Navree's app sign-in hand-over: `auth.apps.android.<name>` or
   `auth.apps.apple.<name>` in the API's configuration, each with a `callback`; it needs
   `SessionModule`. Read `navree-auth` (platform sign-in and token exchange) for what the callback
   is and what the app receives, and record the method in the plan. Navree documents the hand-over
   for those two platforms only; on desktop, check `navree-auth` at build time and record in the
   plan the method used and the skill section that describes it. If the skill describes none, ask
   the operator before building sign-in. Then apply rules TAU-1 to TAU-4.
4. **Screens**, one module at a time (rule BLD-1) against the contracts, with no local response
   types. When there is no phone design, derive one from the tokens and components of the web app
   (rule TAU-8). Every list has a skeleton, an empty state with the next action, an error with retry
   and pull to refresh.
5. **Live updates and notifications.** Navree offers a WebSocket and a server-sent stream
   (`GET /broadcasting/stream`). Check `navree-events-and-broadcasting` and `navree-native` at build
   time for which one a native client uses, how it authorizes and whether it replays missed events,
   and record the answer in the plan. If the stream does not replay, refetch the open screen after
   every reconnect. Then apply rules TAU-5 and TAU-6.
6. **Device QA** after every module, per [device-qa](references/device-qa.md), by `mobile-qa-tester`
   or the main agent.
7. **Store build** only when the operator asks (rule TAU-10).

## Client rules

- **TAU-1** The access token lives in memory and travels as `Authorization: Bearer`. Refresh a
  little before it expires and on any 401, one refresh at a time, shared by API calls and the live
  stream: Navree rotates refresh tokens, and a reused one, or two parallel refreshes, revokes the
  session (hard rule 21). Store the new refresh token every time, in the OS keystore. A refused
  refresh wipes the tokens and the cached data and shows sign-in.
- **TAU-2** A blocked account shows the server's reason (rule SEC-3), never "your session ended".
- **TAU-3** Errors have Navree's shape and the client branches on `code`; on 429 it waits for
  `Retry-After` and retries once.
- **TAU-4** Money-moving and record-creating requests send an `Idempotency-Key`, one per user
  action, reused when the same action is retried (hard rule 23).
- **TAU-5** One live stream, made with the native HTTP client. Events are checked and unknown types
  are skipped. Reconnect with backoff from 1 s to 30 s with jitter, and at once on return to the
  foreground; refetch only what is on screen, batched.
- **TAU-6** Ask for notification permission after explaining it, never at first launch. An OS
  notification shows only while the app is hidden and the person's preference is on; events replayed
  after a long absence update the inbox silently.
- **TAU-7** No secret in the bundle; tokens, codes and contact details are never logged; release
  builds use HTTPS only; deep links and scanned codes are checked against an exact allowlist before
  the app acts on them.
- **TAU-8** Phone layout: one column, a bottom tab bar of at most five destinations, sheets for
  secondary actions, 48 dp tap targets and the web app's words. Android back closes the open sheet,
  then goes back one screen, then returns to the home tab, then leaves.
- **TAU-9** Exact dependency versions at least two weeks old; a Tauri crate and its npm plugin are
  pinned to the same version.
- **TAU-10** Store builds: signing keys live outside the repository in a secret store, a version
  code is never reused, and a store build is made only when the operator asks.

## Reference files

| File | Read when |
|---|---|
| [references/security.md](references/security.md) | before the first screen and before every release; it names each check of `verify-done.mjs` |
| [references/device-qa.md](references/device-qa.md) | after every module and at the `product-qa` gate |
