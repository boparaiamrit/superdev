# Two-factor, recovery codes, passkeys, devices, QR sign-in

## Principals

Implement once for every identity kind (end user, staff) with a `principal = { kind, id }` abstraction; recovery codes, passkeys and challenges tables carry `principal_kind` + `principal_id`. Expected WebAuthn origin depends on the kind (each app has its own origin).

## TOTP two-factor (RFC 6238)

- Implement with Node `crypto` (HMAC-SHA1, 30 s step, 6 digits, ±1 step window) or a maintained library; avoid AGPL dependencies in commercial products.
- **Secret at rest encrypted** (AES-256-GCM) with a 32-byte key from the environment (`SECRETS_ENCRYPTION_KEY`, base64url, required at boot — no default). Never store it plain.
- **Replay protection:** store the last accepted time step; reject a code whose step ≤ last step.
- **Setup:** `POST /me/2fa/setup` returns the otpauth URL (render as QR) and the secret for manual entry; nothing is enabled until `POST /me/2fa/enable {code}` verifies a code. Enabling returns **10 recovery codes once** (`XXXX-XXXX`), stored as SHA-256, single use.
- **Disable** needs the password **and** a current code (or a recovery code). Regenerating recovery codes needs a code.
- **Sign-in:** first factor returns `{ status: 'Two Factor', challenge_id }` instead of a session when two-factor is on. Challenges table: kind, principal, payload (incl. the client — a web challenge cannot be completed by the mobile endpoint), attempts ≤ 5, TTL 5 min, consumed once.
- Security notification on enable, disable and recovery-code regeneration.

## Passkeys (WebAuthn)

- `@simplewebauthn/server` on the API, `@simplewebauthn/browser` on web/admin (exact versions; server and browser majors aligned).
- RP ID = the registrable domain both apps share (`localhost` in development); expected origin = the app's own origin per principal kind.
- Registration and sign-in ceremonies store the challenge server-side (same challenges table), single use, short TTL.
- Store credential id, public key, counter, transports, device type, backed-up flag, a user-given name, last used.
- **A passkey sign-in skips two-factor** (it is already possession + inherence/knowledge). Removing a passkey needs a signed-in session and sends a Security notification.
- Not available inside Tauri/system WebViews — the phone app uses other methods.

## Device list

- `GET /me/security` → two-factor state, passkeys, and live session families as devices: label (browser + OS, or "<App> mobile app"), client, IP, signed-in time, last active, "This device".
- `DELETE /me/sessions/:familyId` revokes one device; "Sign out of all other devices" keeps the current family.
- Write the device label in one shared function used by the device list **and** the new-sign-in alert.
- Do not use AGPL user-agent parsers in commercial code; a small regex labeler is enough.

## QR sign-in for a companion app

- A signed-in web session creates a ticket: `POST /me/qr-sign-in` → `{ qr_payload: '<app-scheme>://sign-in?token=…', expires_in: 120 }`. Store only the token's hash; single use; 2-minute TTL; bound to the creating user.
- The app scans or pastes the payload, validates the prefix, and redeems it at the mobile endpoint; it gets its own new session family (the web session is untouched).
- The web card explains "keep it private — anyone who scans it is signed in as you" and counts down.
- Offer it where the person already is (dashboard "Open on phone" and the security page).

## Staff accounts

Staff get the same two-factor, recovery codes, passkeys and device list under `/admin/me/*`, and the admin app shows a persistent banner until two-factor is on. Consider requiring it for roles that can reveal personal data or move money.

## Proof (committed tests)

Setup → wrong code refused → enable returns 10 codes → sign-in requires the second factor → no session cookie before it → a code cannot be reused → a recovery code works once → a web challenge is refused by the mobile endpoint → disable needs password + code. Passkey ceremonies are covered in the browser with a virtual authenticator (`release-qa-gate`). QR: ticket created → redeemed once → second redemption refused → expired ticket refused.
