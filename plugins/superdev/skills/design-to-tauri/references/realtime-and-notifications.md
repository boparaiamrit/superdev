# Live updates and phone alerts

The server contract (events, replay, notification preferences) is in `security-foundation/references/realtime-and-notifications.md`. This is the client half.

## The stream

- One Server-Sent Events stream per signed-in app: `GET /events` under the API base, with `Authorization: Bearer` and `Accept: text/event-stream`, made with the native HTTP plugin. It delivers the body chunk by chunk; parse `id:` / `data:` frames yourself (do not use `EventSource`: it cannot send headers).
- **Verify streaming on the installed plugin version** with a first event arriving while the request is still open. If that version buffers the whole response, do not ship a stream that never fires: fall back to polling the server's replay query (events after the last id) every few seconds while in the foreground, and record the plugin version that forced it.
- Validate each event with the shared schema; skip unknown types (newer servers add types).
- Keep the last `id:`; reconnect with `Last-Event-ID` and missed events replay. On `resync`, or on `ready` after a reconnect, refetch every active query.
- Backoff 1 s → 30 s with jitter; reset to 1 s and reconnect **at once** when the app returns to the foreground or the network comes back.
- A silence watchdog (a little over twice the server's heartbeat) replaces a stream that went quiet without closing.
- 401 on connect: wait on the same single-flight refresh the API client uses, then reconnect; refresh failure → sign-in.
- `session.ended`: blocked screen (Blocked) or sign-in with the message; close the stream.

## Foreground and background

Use `document.visibilitychange` as the signal on phones: the WebView reports `hidden` when the activity pauses and `visible` when it resumes. On desktop also listen to the window's focus events. This one signal drives three things: reconnect on `visible`, choose banner vs OS notification, and stop the watchdog while `hidden`.

## Event → screen

- Batch invalidations (a few hundred ms) so a burst refetches once.
- Act only on what is on screen: an updated item in a loaded list page is refetched alone and swapped in place; ignore events for items the phone is not showing.
- New items: a floating "N new · Show" pill over the list, never a reflow under the thumb; Show loads them and scrolls to the top.
- Counters (credits, unread) come from the server's numbers in the event or a refetch, not client arithmetic.

## Phone alerts (local notifications)

- `@tauri-apps/plugin-notification` + the crate. One named channel with an explicit importance; delete the plugin's default channel if it is unused. A monochrome small icon kept in release builds.
- **Ask permission only after explaining it** (Android 13+ `POST_NOTIFICATIONS`): after the first relevant live event or from a "Turn on phone alerts" button — never on a cold start.
- Show an OS notification for `notification.created` **only while hidden** and when the person's Push preference for that category is on (fetch and cache the preferences). While visible, show the in-app banner instead.
- Tapping an alert opens the matching screen (map the server's web paths to app routes) and marks the item read. Remove alerts for items read on another device (`notification.read`).
- Check the installed plugin version's payload handling: some versions drop the extra data a tap needs on Android — use the plugin API that carries it, and note the version.
- Replayed events older than a few minutes update the inbox silently; no alert storm after a long absence.

## Background limits — say them plainly, and ask

- Android freezes a cached app about ten seconds after it leaves the screen; the stream pauses and local alerts stop. Missed events replay on return.
- Alerts to a **fully closed** app need Firebase Cloud Messaging (Android) and APNs (iOS). **Tell the person this before building alerts, and ask whether to set it up** — it needs accounts and credentials only they can create. Until then, the settings screen says in one line that alerts arrive while the app is open or recently used.
- When they want closed-app push, the parts are: a Firebase project with `google-services.json` and an APNs key (operator-supplied, kept out of git); a native push plugin pinned after reading its changelog; a device-token endpoint (`POST /devices/push-tokens { platform, token }`, tied to the session and removed when the session ends); a server sender (FCM HTTP v1, APNs) with credentials from the environment; and a mobile-push channel in `notify()` that honours the same Push preference. Prove it on a real phone with the app swiped away.

## Proving it (on the emulator)

1. Staff create an item → the pill appears within ~2 s, the alert banner arrives.
2. Credits change → the pill/counter updates live.
3. Mark all read on the web → the app badge clears live.
4. Home button, then create an item **within ten seconds** → an OS notification appears in the shade; tapping it opens the right screen. An event after the freeze shows on return, not in the shade — record which case you tested.
5. Revoke this device → sign-in with the message; block → blocked screen with the reason.
6. Airplane mode on/off → "Reconnecting…" then recovery with replayed events.
7. `adb logcat` shows no app errors throughout.
