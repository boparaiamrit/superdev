# Identity and sessions

Shown for the Nest.js + Drizzle stack; the same model maps to Laravel (Fortify sessions table + Sanctum tokens) — keep the behaviours, change the mechanics.

## Data model

```
users (or merchants/customers)   status: 'Pending Review' | 'Active' | 'Blocked', blocked_reason, password_hash (argon2id),
                                 last_login_at, two_factor_* (see mfa file), notification_prefs jsonb
auth_sessions                    id, user_id, family_id, token_hash (sha256 of the refresh token), client ('Web'|'Mobile'),
                                 user_agent, ip, created_at, last_used_at, expires_at, revoked_at, replaced_by_id
```

One **family** per sign-in on one device. Each refresh creates a new row in the family and points the old row's `replaced_by_id` at it. "Devices" in the UI are live families.

## Tokens

- **Access token:** short-lived JWT (10–15 min) carrying `sub`, `sid` (session row id), `typ`. Separate secret from anything else; secret length validated at boot (≥32 bytes); audience/typ distinguish end-user tokens from staff tokens so neither guard accepts the other's.
- **Refresh token:** 48 random bytes, base64url; only its SHA-256 is stored.
- **Web:** both in `HttpOnly` cookies. Access cookie scoped to the API path; refresh cookie scoped to the refresh path with `SameSite=Strict`; `Secure` in production; plus a non-secret hint cookie the frontend proxy can read for optimistic redirects. Cookies are cleared on **every** failed refresh path, or the browser loops between login and app.
- **Mobile:** token endpoints return the pair in JSON; the client sends `Authorization: Bearer`. Same session table with `client = 'Mobile'`, same rotation and theft detection, no grace window. The endpoint list the app needs is in `design-to-tauri/references/auth-and-api.md`.

## The guard — read the session on every request

```ts
// after verifying the JWT signature and typ:
const [row] = await db.select({ userId: sessions.userId, familyId: sessions.familyId, revokedAt: sessions.revokedAt,
                                status: users.status, blockedReason: users.blockedReason })
  .from(sessions).innerJoin(users, eq(users.id, sessions.userId))
  .where(eq(sessions.id, claims.sid)).limit(1);
if (!row || row.userId !== claims.sub) throw new UnauthorizedException();
if (row.status === 'Blocked') throw accountBlocked(row.blockedReason);   // BEFORE the revoked check
if (row.revokedAt) throw new UnauthorizedException();
req.user = { userId: claims.sub, sessionId: claims.sid, familyId: row.familyId };
```

One indexed primary-key join per request is the price of instant revocation; pay it. Blocking revokes every session too, which is why "blocked" is checked first: the user must see the reason, not "signed out".

## Refresh rotation

```
find row by sha256(refresh)            → none: 401, clear cookies
user Blocked                           → 403 ACCOUNT_BLOCKED with reason, clear cookies
expired                                → 401
replaced or revoked:
   web cookie, same user-agent + same IP, row last used < 10 s ago, not revoked
                                       → mint a sibling pair in the same family (two tabs raced)
   otherwise                           → revoke the whole family (token theft), 401
else                                   → mint next row, set replaced_by_id + last_used_at, return new pair
```

Mobile refresh gets no grace window: one client per device, single-flight refresh on the client side, strict reuse detection.

Run each rotation in a transaction that locks the presented row (`FOR UPDATE`), so two concurrent rotations cannot both see it as unreplaced. "Revoke the family" sets `revoked_at` on every row of the family — the guard checks the row behind the access token, so every device of that family stops at once. A sibling minted inside the grace window does not extend the window. `last_used_at` moves on refresh (every few minutes), which is precise enough for "last active" in the device list.

## Blocking, revoking, signing out

| Action | Effect |
| --- | --- |
| Sign out (this device) | Revoke the family; clear cookies; emit `session.ended {Signed Out}` for that family |
| Sign out a device (from the device list) | Revoke that family; emit `session.ended` targeted at it |
| Sign out everywhere / password reset / staff sets a temporary password | Revoke every family; emit `session.ended` to all |
| Block (staff) | `status = Blocked`, reason required, revoke every family **in the same transaction**, emit `session.ended {Blocked, message with reason}`, email the person |
| Unblock / approve | No reason required; emit `account.changed` so open screens refresh |

## First factor details

- **Password check equalizes timing:** verify against a dummy argon2 hash when the account does not exist, so "no such email" is as slow as "wrong password".
- **Reveal "blocked" only after the first factor succeeds.** Telling an unauthenticated caller that an account is blocked confirms it exists; check the password (or OTP) first, then report the block and its reason.
- **One-time codes:** 6 digits, hashed, 5 attempts, short TTL, rate limited per phone and per IP; return a masked destination ("+91 98••• ••210").
- **Rate limits:** stricter on sign-in, OTP, refresh and two-factor routes (e.g. 10/min/IP) than the global default. All local tooling shares one IP — runtime tests must wait and retry on 429 rather than weakening the limit.
- **Must-change-password** flag for staff-issued temporary passwords: every request except the change-password route returns a typed error until it is changed.

## New-device alert

After a successful sign-in, if no earlier session of this user has the same user agent, send a Security notification (in-app + email + push): device label, time, IP, "if this was not you, sign that device out and change your password", linking to the device list. The label must match the one the device list shows.

## Proof (committed tests)

Revoke → the next request with the old access token is 401; block → 403 with the reason on request, refresh and sign-in; refresh reuse from another browser → family revoked; two-tab race → both stay signed in; failed refresh clears cookies; timing of unknown-email vs wrong-password within a small ratio.
