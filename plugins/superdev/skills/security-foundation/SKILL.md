---
name: security-foundation
description: Use when building or extending any app with sign-in, staff/admin users, roles and permissions, personal data (phone, email, addresses), money or credits, or live updates — at bootstrap of a superdev build, before the first feature module, and whenever a module adds a login method, a permission, a payment path, a balance, a contact field or a real-time feature. Triggers include "2FA", "passkey", "sessions", "block a user", "admin panel", "roles", "mask phone numbers", "credits", "wallet", "idempotency", "real-time", "notifications".
---

# Security foundation — built in, not bolted on

`security-review-and-fix` finds problems after a build. This skill prevents them: it is the security layer every superdev build implements **at bootstrap and in every module**, with committed runtime tests that prove each control works. An audit at the end then confirms instead of discovering.

**Proof rule:** a control exists when a committed test exercises it against the running API (`security-test-suites.md`). A decorator, a config line or a guard class is not proof.

## When each part applies

| The product has… | Implement | Reference |
| --- | --- | --- |
| Any sign-in | Server-side sessions checked on every request; rotating refresh tokens with theft detection; blocking with a reason; rate limits; new-device alerts | [`identity-and-sessions.md`](references/identity-and-sessions.md) |
| Accounts worth protecting (money, personal data, staff) | TOTP two-factor + recovery codes; passkeys; device list with sign-out; QR sign-in for a companion app | [`mfa-passkeys-devices.md`](references/mfa-passkeys-devices.md) |
| Staff / admin users | A separate staff identity; a permission catalog with roles as bundles; escalation guards; masked personal data with audited reveal | [`staff-roles-and-pii.md`](references/staff-roles-and-pii.md) |
| Money, credits, stock, seats — any balance | Per-account serialization; idempotency keys; re-validation at payment; entitlements that expire; a reconciliation that proves the books | [`money-and-ledgers.md`](references/money-and-ledgers.md) |
| Live updates or notifications | Transactional outbox; authenticated SSE with replay and revocation; per-permission filtering; a notification service with preferences | [`realtime-and-notifications.md`](references/realtime-and-notifications.md) |
| Always | Headers, CORS allowlist, cookie flags, CSRF stance, uploads, error envelope, required secrets, audit log | [`platform-hardening.md`](references/platform-hardening.md) |
| Always | The committed runtime suites that prove all of the above | [`security-test-suites.md`](references/security-test-suites.md) |

## Where it sits in superdev-build

- **Step 1 (plan):** `EXECUTION_PLAN.md` gets a `## Security` section listing which rows above apply, the identities (end users, staff, devices), the permission catalog draft, personal-data fields to mask, balances and money paths, and live-update channels.
- **Step 3 (bootstrap):** identity, sessions, hardening and the audit log are part of the skeleton — the first feature module is built on them, never before them. Generate the encryption key and the VAPID keys with the env file; no defaults (hard-rules #6).
- **Step 4 (contracts):** auth results as discriminated unions (signed in | two-factor challenge), masked labels in admin view shapes, the event union for live updates, the error envelope.
- **Step 5 (each module):** the module's permission keys, masked fields, idempotent routes, ledger writes and emitted events are part of the module, verified at runtime like everything else.
- **Step 6:** `security-review-and-fix` then confirms; `release-qa-gate` runs the committed suites.

## Non-negotiables

1. The session row is read on **every** authenticated request. Revoking a device, disabling staff or blocking a user takes effect on the next request and ends live streams at once.
2. Refresh tokens rotate; a reused one ends the whole session family — except a few-second grace for the **same browser** refreshing from two tabs.
3. A blocked user is told **why** (the reason staff gave), on sign-in, on refresh and on any request.
4. Staff never see personal data by default: lists and detail views show masks; revealing is a separate permission, a separate audited call, and searching by a contact field needs that permission too.
5. Nobody can grant a permission they do not hold; there is always one active owner.
6. Every balance change takes a per-account lock in the same transaction; every money-moving request accepts an `Idempotency-Key`; a reconciliation proves the books nightly.
7. Live events are written in the same transaction as the change and delivered only after commit.
8. Every one of these has a committed test that runs against the live API.

## Common mistakes

| Mistake | Consequence |
| --- | --- |
| Stateless JWT only, no session lookup | A stolen token or a blocked user works until expiry; "sign out everywhere" is a lie |
| Checking "revoked" before "blocked" | The blocked user sees "signed out" and never learns why |
| Strict refresh reuse detection with no tab grace | Two browser tabs refreshing together sign the user out |
| Role names checked in code (`role === 'admin'`) | Roles cannot be edited; permissions drift from the UI |
| Masking only in the UI | The full phone number is in the JSON response and the network tab |
| `SELECT … LIMIT 1 FOR UPDATE` to pick a lot to spend | After waiting, Postgres may return no row; a parallel spend fails with "no balance" although balance exists |
| Emitting live events before commit | Screens show changes that were rolled back |
| A decorator per mutation with no runtime test | Nothing proves the audit row, the lock or the permission check happens |

## Reference files

| File | Read when |
| --- | --- |
| [`references/identity-and-sessions.md`](references/identity-and-sessions.md) | Building sign-in, refresh, sign-out, blocking |
| [`references/mfa-passkeys-devices.md`](references/mfa-passkeys-devices.md) | Two-factor, recovery codes, passkeys, devices, QR sign-in |
| [`references/staff-roles-and-pii.md`](references/staff-roles-and-pii.md) | Any admin/staff surface |
| [`references/money-and-ledgers.md`](references/money-and-ledgers.md) | Credits, wallets, payments, coupons, stock |
| [`references/realtime-and-notifications.md`](references/realtime-and-notifications.md) | Live updates, notification centre, push |
| [`references/platform-hardening.md`](references/platform-hardening.md) | Bootstrap; every new endpoint type (upload, webhook) |
| [`references/security-test-suites.md`](references/security-test-suites.md) | Writing the proof for each control |
