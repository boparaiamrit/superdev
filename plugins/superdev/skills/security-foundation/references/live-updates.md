# Live updates

How a build sends live updates and notifications without leaking data or showing a change that was rolled back. It serves rule SEC-12 of [security-foundation](../SKILL.md) and builds on hard rule 24 (publish only after the commit). Read `navree-events-and-broadcasting` first.

## Navree UI: nudges

- A live region listens to a topic; the server sends a nudge and the page fetches the region again from its source (rule NUI-5). A nudge carries no data, and nothing a stream says becomes markup.
- The server sends it with `live.nudge` and a workspace topic (`Topic::workspace` with the workspace id and a name such as `invoices`); inside a unit of work the nudge waits for the commit. It needs `RealtimeModule`, which a Navree UI app (`--ui navree`) registers.

## Next.js and other clients: channels

- A Next.js front end authorizes channels through the BFF's `/broadcasting/auth`; the WebSocket goes from the browser straight to Navree's server (`navree-frontend-next`). Tauri clients follow `design-to-tauri`.
- Every channel belongs to one workspace. A channel that only some roles may hear is a channel of its own, authorized by permission key (`navree-events-and-broadcasting`).
- An event carries its type and ids (`invoice.sent` with the invoice id), never names, amounts, contact details or secrets. The client checks each event, skips types it does not know, and fetches again only what is on screen.

## Workers and several processes

- A job or a scheduled task publishes through `dyn Broadcaster`, with the same `APP_KEY` as the web process (hard rule 24).
- With more than one process, set `realtime.backplane = "redis"` (`navree-redis`).

## Topics in the contract

Each live topic is a row of the contract's `## Side effects` table: the trigger, the topic (workspace and name), who may hear it (the permission key), and what the client fetches again.

## Notifications

- Notifications go through `navree-mail-and-notifications`, with channels from `navree-notification-channels` and each person's choices from `navree-notification-preferences`.
- Security notices (a password or second-factor change, SEC-5; a permission change, SEC-8; a block, SEC-3) go to every channel the person has, and the person cannot turn them off.
- Mail from a request goes through the mailer's queue, and a job dispatched in a unit of work is queued only if the request commits (hard rule 7); check `navree-mail-and-notifications` that each notification channel the plan uses is queued the same way.

## Check at build time

Two behaviours are confirmed at build time, not assumed: replaying missed events after a reconnect, and ending an open stream when the person signs out or is blocked. Check `navree-events-and-broadcasting` and `navree-auth`, and write what Navree does into the contract's `## Side effects` and the plan's `## Security` section. When the product needs one that Navree lacks, record an open item `O-n` that says what an open page of a signed-out or blocked person can still receive.

## Proof

`tests/live.rs`, with `send_stream()` (`navree-testing`):

- a write that is rolled back sends no nudge; a committed write sends one (hard rule 24);
- a member of another workspace receives nothing; a role without the topic's permission receives nothing;
- an event holds only its type and ids.

Channels used by Next.js or Tauri clients, delivery across two clients, replay and the end of a stream at sign-out are proven in the running app by `realtime-prober` at the QA gate.
