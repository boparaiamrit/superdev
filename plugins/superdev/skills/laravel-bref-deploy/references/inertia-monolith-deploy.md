# Deploying the Inertia monolith on Bref

Read this when the Laravel app is a **fullstack Inertia monolith** (Step A.5c chose `frontend_stack == Inertia`) rather than a pure JSON API paired with a separate Next.js app. The Bref topology is **the same three functions** as the API-only deploy — there is no extra Lambda for the frontend, because the frontend ships *inside* the Laravel app. The only additions are a **Vite build step** and **session-auth config**.

## What's the same

- The three functions from `serverless-yml.md`: `web` (`php-84-fpm`), SQS `worker` (`php-84` + `QueueHandler`), `artisan` (`php-84-console`).
- EventBridge `schedule:run`; SSM secrets; CockroachDB serverless over the public internet (no VPC); database-backed cache/sessions/queues→SQS.
- Assets to **S3 + CloudFront** (`storage-s3-cloudfront.md`) — same mechanism.

## What's added for Inertia

### 1. Build the frontend (Vite) — client-only, no SSR

Add to the deploy flow **before** `osls deploy`:

```bash
npm install
npm run build          # Vite build — client-only. Do NOT run build:ssr.
```

We deploy **client-only Inertia**: Laravel returns the initial HTML shell + JSON props and React hydrates in the browser. There is **no Inertia SSR Node Lambda** — that keeps the deploy to PHP-only functions and avoids a Node sidecar. (If SEO later demands SSR, that's a separate Node-runtime Lambda running `build:ssr` output — out of scope here.)

### 2. Ship Vite assets via S3/CloudFront

The Vite `public/build/` output is uploaded to S3 and served via CloudFront (see `storage-s3-cloudfront.md`); set `ASSET_URL` to the CloudFront domain so `@vite`/`asset()` emit CDN URLs. Invalidate CloudFront on deploy so new asset hashes are served.

### 3. Session auth config (Fortify)

The Inertia monolith uses **Fortify session auth** (not Sanctum tokens), so sessions must persist across stateless Lambda invocations:

```dotenv
SESSION_DRIVER=database          # sessions table in CockroachDB (NOT file/ /tmp)
APP_URL=https://your-domain
SESSION_DOMAIN=your-domain       # so the session cookie is valid for the app domain
SESSION_SECURE_COOKIE=true
```

No CORS / cross-origin token dance is needed — the frontend and backend share an origin.

## Deploy checklist additions

In addition to the steps in `deploy-checklist.md`:

- [ ] `npm install && npm run build` ran and `public/build/manifest.json` exists (Vite).
- [ ] Vite assets synced to S3; `ASSET_URL` points at CloudFront; CloudFront invalidated.
- [ ] `SESSION_DRIVER=database`, `APP_URL`, `SESSION_DOMAIN`, `SESSION_SECURE_COOKIE` set (via SSM).
- [ ] `sessions` table migrated on CockroachDB.
- [ ] Smoke test: load a page (Inertia HTML shell renders), log in (Fortify session persists across requests), navigate via `<Link>` (XHR prop responses), submit a `useForm` (validation errors surface).

## Anti-patterns

- ❌ Running `build:ssr` / standing up a Node SSR Lambda for the default deploy (we're client-only).
- ❌ `SESSION_DRIVER=file` — `/tmp` is per-invocation; sessions vanish. Use `database`.
- ❌ Serving Vite assets from the Lambda filesystem — they belong on S3/CloudFront.
- ❌ Adding CORS/token middleware for the first-party Inertia frontend — same-origin session, no tokens.
