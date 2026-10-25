# Live updates and notifications (server)

## Transactional outbox

```
realtime_events   id bigint identity, channel text ('user:<id>' | 'broadcast' | 'admin' | 'staff:<id>'), type, payload jsonb, created_at
trigger AFTER INSERT → pg_notify('realtime_events', json of the row)   -- or {id, truncated:true} if > ~7900 bytes
```

- Services write the event row **in the same transaction** as the change. `pg_notify` is delivered only on commit, so a rolled-back change never reaches a screen.
- Each API process holds one dedicated `LISTEN` connection (reconnect with backoff) and fans events out to its open streams. Several API processes work without extra infrastructure.
- Events carry ids and types, never contact details or secrets. Routing-only fields (e.g. the session family a `session.ended` targets) start with `_` and are stripped before sending.
- Prune rows older than a day; that is the replay window.

## Streams (Server-Sent Events)

- `GET /events` (end users: cookie or Bearer), `GET /admin/events` (staff). Exempt from the request rate limiter.
- Headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`; `retry:` hint; a `: ping` comment every ~20 s.
- **Replay:** on `Last-Event-ID`, send missed events for the connection's channels in order; if the gap is too large or pruned, send `resync`. Hold live events that arrive during the replay and de-duplicate by id. Then `ready` with the current cursor.
- **Revalidate** the session every ~30 s (revoked → `session.ended Signed Out`; blocked → `session.ended Blocked` with the reason; staff disabled → `Disabled`; staff permissions re-read). Revocation paths also emit `session.ended` immediately; the stream closes after sending it.
- **Filter per connection:** staff events by permission key (credit events only to `credits.view`, etc.); end-user broadcast events by what that user can see. If the UI lists items from everywhere, broadcast item events to everyone and let clients act only on what is on screen; targeted alerts stay targeted.
- Verify the stream passes through the frontend's dev proxy/rewrite unbuffered before relying on it.
- **Browsers allow ~6 connections per origin on HTTP/1.1:** clients keep one stream per browser (leader tab via Web Locks + BroadcastChannel relaying to other tabs; hand-over resumes from the last id). Production behind HTTP/2 relaxes this but do not depend on it.

## Contract

A discriminated union per stream in the shared contracts (`ready`, `resync`, `session.ended`, then domain events such as `item.created {id, scope}`, `item.updated`, `wallet.changed`, `notification.created {notification, unread}`, `notification.read {ids?, unread}`, `account.changed`, `me.changed`). Each event documents what the client should refetch. Clients validate and skip unknown types.

## Notification service — one entry point

`notify({ to, category, template, title, body, href, group?, email?, sms?, push? })`:

1. Load the person's preferences (category × channel; Security in-app and email **locked on**; staff have no SMS).
2. **In-app item** (the inbox row). With `group`, merge into the person's unread item with the same key within a window, incrementing a count by `add` ("12 new items in your area") instead of stacking twelve rows; bump it to the top.
3. Emit `notification.created` with the item and the unread count (in the caller's transaction when there is one).
4. **Push** (web push via VAPID keys from the environment, later FCM/APNs) to the person's subscriptions, at most one per group key per ~10 min; delivery rows point at the in-app item so a click can mark it read.
5. **Email / SMS** rows per preference, delivered by the worker with retries.
6. Messages that must always go (one-time codes, messages to third parties such as customers) bypass preferences through separate `sms()`/`email()` calls.

Worker rules: a delivery job whose row is not visible yet (written in an uncommitted transaction) **throws and retries** — it must not silently drop. Push endpoints that are gone (404/410), rejected (400/403) or whose host does not resolve are deleted at once; transient failures count up to a limit. A sweep re-queues rows stuck in `Queued`.

Endpoints: list (`All`/`Unread`, category, paginated), mark read (`ids?` — none means all; emits `notification.read` to the person's other devices), preferences GET/PUT (locked switches ignored), push config (public VAPID key), subscribe/unsubscribe, "send me a test" (in-app + push regardless of preferences, wording that suits every client).

## What to notify (typical)

New items in the person's area (grouped, only to those who can act), money in/out, expiring balances (days before), plans ending, payments received/failed, reports resolved, approvals, and Security events (new-device sign-in, password/two-factor/passkey changes). Staff: items to review (grouped), people awaiting approval, payments received, failed ledger checks.

## Proof (committed tests)

A live-update suite: delivery latency printed; filtering (an out-of-scope user and a role without the permission receive nothing); grouped alerts increment one item; mark read on one connection reaches another; preferences off → feed still updates but no alert; push subscription with an unreachable endpoint is removed; reconnect with `Last-Event-ID` replays missed events; revoke and block end the stream with the reason.
