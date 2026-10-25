# Sign-in, tokens and API calls on the phone

The server side of all of this is defined in `security-foundation` (identity-and-sessions, mfa-passkeys-devices). This file is the client half, plus the server contract the client needs.

## Endpoints the API must provide

Mobile clients cannot rely on cookies. The API exposes token endpoints that return the tokens in JSON instead of setting cookies. Paths below are relative to the API base the app is configured with (origin + prefix, e.g. `https://api.example.com/api/v1`); field names follow the contracts package's casing — the shape is what matters.

| Purpose | Endpoint | Needed when |
| --- | --- | --- |
| Password / one-time code sign-in | `POST /auth/mobile/login`, `POST /auth/mobile/otp/verify` | whichever first factors the web app offers |
| Two-factor step | `POST /auth/mobile/2fa/verify` (challenge bound to the mobile client; TOTP or recovery code) | any account can enable two-factor |
| QR sign-in from a signed-in web session | `POST /auth/mobile/qr { token }` | the product offers QR sign-in |
| Refresh (rotating) | `POST /auth/mobile/refresh { refresh_token }` | always |
| Sign out | `POST /auth/mobile/logout { refresh_token }` | always |
| Live updates | `GET /events` (Bearer, `text/event-stream`) | the app shows live data |

Sign-in responses are a discriminated union on `status`: signed in (`user` + `tokens { access_token, refresh_token, expires_in }`) or two-factor required (`challenge_id`, the allowed methods). Errors use the API's envelope; a blocked account is `403 ACCOUNT_BLOCKED` with the reason, returned only after the first factor succeeds.

**The API does not have these yet?** Build them first, per `security-foundation/references/identity-and-sessions.md` (the mobile client row of the token model) and `realtime-and-notifications.md` — same session table, same rotation and theft detection, `client = 'Mobile'`, no grace window. Then build the app's sign-in screen. Never give the app a long-lived token or a cookie workaround in the meantime.

## Client rules

- **Access token in memory, `Authorization: Bearer`.** Refresh a little before expiry, and on any 401.
- **Single-flight refresh.** One refresh at a time — API calls **and** the live-update stream share the same lock; every request that got a 401 waits for it and retries once. Two concurrent refreshes present the same rotated token and the server ends the whole session family (theft detection) — the user is signed out for no reason.
- **Store the new refresh token every time.** Rotation means the old one is dead.
- **Rejected refresh** → wipe tokens and caches → sign-in screen with a plain message.
- **`403 ACCOUNT_BLOCKED`** (any request, refresh included) → blocked screen with the server's message, which carries the reason. Never collapse it into "your session ended".
- **QR sign-in:** the web app shows a single-use code (short TTL); the app scans it (barcode plugin) or accepts a pasted code, validates the prefix, and exchanges it. Always offer the paste fallback — scanners need camera, permissions and sometimes a downloaded model.
- **Two-factor:** a six-digit TOTP field and a "use a recovery code" switch; both go to the same verify endpoint.
- **No passkey button** in the WebView (see security.md §7). An account that has only passkeys signs in on the phone by QR from the web app, or with a one-time code.
- **Idempotency-Key** (a UUID per user action, reused when that same action is retried after a dropped connection) on every money-moving or record-creating request: unlocks, purchases, bookings. A retry must never charge twice.

## Errors and offline

- Parse the API's error envelope (`{ error: { code, message, fields } }`); show `message`, put `fields` on the form.
- Offline at start-up: a dedicated screen with retry; offline later: lists keep cached data and show a strip; skeletons never spin forever.
- Rate limited (429): wait and retry once with the server's `Retry-After`; tell the user if it persists.

## Proving it (on the emulator)

- Sign in with every first factor the product offers, sign out; with two-factor (an account with it enabled) and a recovery code; with QR (paste fallback at minimum).
- Token expiry: run the QA stack with a short access-token lifetime (an env setting such as 30 s, never in production builds) and use the app for a few minutes — refreshes happen, every 401 is retried once, the stream reconnects, still signed in, and no session family is revoked.
- Revoke the device from the web or admin: the app lands on sign-in with the server's message within seconds.
- Block the account: blocked screen with the reason; unblock and sign in again.
