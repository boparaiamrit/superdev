# Platform hardening

## HTTP layer

- `helmet()` with a CSP for anything the API renders (docs pages); `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, HSTS in production.
- **CORS allowlist:** the web origin, the admin origin and, if a native client's WebView calls the API directly, its WebView origins (`http://tauri.localhost`, `tauri://localhost`) and dev server origin — from configuration, never `*` with credentials. Expose only the headers clients need (`Idempotent-Replayed`).
- **CSRF stance:** cookie auth with `SameSite=Strict` on the refresh cookie and `Lax`/`Strict` on the access cookie, JSON-only bodies, and no state change on GET. If any cookie-authenticated form posts cross-site, add a CSRF token.
- **Error envelope:** `{ error: { code, message, fields } }` for every failure; 5xx bodies never contain stack traces, SQL or paths. Validation errors map to `fields` for the form.
- **Global rate limit** with stricter limits on auth, OTP and refresh routes; SSE streams exempt.
- **Request ids** on every log line and audit row.

## Inputs

- Every body, query and param through a schema from the shared contracts (Zod DTOs / Form Requests). UUID params validated (invalid → 404, not 500).
- Lists: bounded `per_page`, server-side filtering and sorting.
- Search terms escaped for `LIKE`.
- **Uploads:** size limit in the multipart parser, magic-byte type check (not the extension or client MIME), images re-encoded or stored under random names outside the web root, served with `Content-Type` and `nosniff`; CSV imports have a row cap and a dry-run mode.
- **Webhooks:** HMAC signature verified with a timing-safe compare before parsing; replay window enforced.

## Secrets and configuration

- Every secret required at boot with a minimum length (JWT secrets ≥ 32 bytes, encryption key exactly 32 bytes base64url); no defaults in schemas (hard-rules #6). Generate them into the gitignored env file during bootstrap and document generation commands in `.env.example`.
- Separate secrets per purpose: access JWT, refresh, staff JWT if different, payment signing, TOTP encryption, VAPID keys.
- Demo conveniences (OTP shown on screen, sandbox gateway) behind an explicit `DEMO_MODE` that refuses to start in production.

## Data at rest

- Passwords argon2id; refresh tokens, OTPs, recovery codes, QR tickets stored as hashes; TOTP secrets encrypted.
- Least-privilege database user for the app in production; migrations run with a separate role.
- Backups encrypted; restore tested.

## Infrastructure

- Docker services bound to `127.0.0.1` in development compose, healthchecks on each, no default passwords on anything exposed.
- Production API behind TLS; `trust proxy` configured so `req.ip` is the client, not the proxy (rate limits and device labels depend on it).

## Dependency hygiene

Exact versions ≥ two weeks old; licences checked (avoid AGPL in commercial closed-source code); `pnpm audit --prod` clean of High/Critical or each finding triaged.
