# Deploy Notes — Inertia Monolith on Bref

The Inertia monolith is **one Laravel app**: it serves both the Inertia HTML shell and the JSON prop responses from the same three Bref Lambda functions described in `laravel-bref-deploy`. There is no separate Node SSR Lambda and no `apps/web` to deploy independently.

This file covers the **Inertia-specific additions** to that deploy flow. Read it alongside `laravel-bref-deploy` — it does not repeat the full pipeline, it only documents what differs or is new.

> **The authoritative, detailed Inertia deploy reference is** `laravel-bref-deploy/references/inertia-monolith-deploy.md` (authored in Phase 3 of the `design-to-laravel` implementation plan). This file is the short pointer and quick-reference you reach from the skill.

---

## What is different from a Laravel API deploy

| Concern | API-only deploy (v1.4.0 default) | Inertia monolith (this path) |
|---|---|---|
| Frontend | Separate `apps/web` (Next.js), deployed elsewhere | `resources/js/` compiled by Vite into `public/build/`; same deploy |
| Vite build step | None in the Laravel app | **`npm install && npm run build`** must run before `osls deploy` |
| SSR build | N/A | **Skip `build:ssr`** — client-only per D2 |
| Static assets | Minimal (`public/` vendor assets) | `public/build/` output (JS, CSS bundles with content hashes) |
| `ASSET_URL` | Required for any vendor assets | **Required** — Vite `@vite` directive reads it; every asset URL emits the CloudFront domain |
| Session auth | Optional (Sanctum tokens are the default) | **Required** — Fortify session auth; configure `SESSION_DRIVER`, `APP_URL`, `SESSION_DOMAIN` |
| Node SSR Lambda | N/A | **None** — client-only; drop any `build:ssr` / SSR Lambda step |

---

## Build step: Vite (client-only)

Insert this before the `osls deploy` step in your deploy script:

```bash
# From the Laravel app root (same directory as package.json)
npm install
npm run build          # Vite — builds resources/js/* -> public/build/
                       # DO NOT run: npm run build:ssr
```

`npm run build` compiles the Inertia React frontend into `public/build/` with content-hashed filenames. The `build:ssr` script (if present in `package.json`) produces a Node bundle for Inertia SSR — **never run it** on this path because there is no Node Lambda to execute it.

After the build, `public/build/` contains the production JS and CSS bundles. These must be synced to S3 before the Lambda handles any requests.

---

## Assets: Vite output → S3/CloudFront

Vite output lands in `public/build/` with content-hashed names (`app.abc123.js`, `app.def456.css`). Sync it to S3 exactly as the existing asset pipeline does — the hashed names mean no CloudFront invalidation is needed for them on subsequent deploys:

```bash
# Hashed Vite bundles — immutable, cache for a year
aws s3 sync public/build/ s3://app-assets-prod/build/ \
  --cache-control "public, max-age=31536000, immutable"

# Unhashed files (favicon, robots.txt, etc.)
aws s3 sync public/ s3://app-assets-prod/ \
  --exclude "index.php" --exclude "*.php" --exclude "build/*" \
  --cache-control "public, max-age=3600"
```

Set `ASSET_URL` to the CloudFront distribution domain (SSM parameter, resolved at deploy time). The `@vite` Blade directive — already in the starter kit's `app.blade.php` — reads `ASSET_URL` and emits CloudFront URLs:

```php
// resources/views/app.blade.php (starter kit default)
@vite(['resources/css/app.css', 'resources/js/app.tsx'])
```

With `ASSET_URL` set, this renders as:

```html
<link rel="stylesheet" href="https://d111111abcdef8.cloudfront.net/build/assets/app.def456.css">
<script src="https://d111111abcdef8.cloudfront.net/build/assets/app.abc123.js"></script>
```

Without `ASSET_URL` the directive points at the Lambda, which has no static files, and assets 404.

See `laravel-bref-deploy/references/storage-s3-cloudfront.md` for the full S3 bucket + CloudFront CloudFormation resources and the CloudFront invalidation step.

---

## Session auth: environment configuration

Inertia uses **Fortify session auth** (D3), not Sanctum tokens. Session persistence on stateless Lambda requires the database session driver and correct domain config.

### Required environment variables

```bash
# Session driver — must be 'database'; uses the 'sessions' table on PostgreSQL
SESSION_DRIVER=database

# Your public application domain — used for cookie generation + CSRF verification
APP_URL=https://app.example.com

# Cookie domain — set to your apex or subdomain; must match what the browser sends
# For app.example.com -> '.example.com' (leading dot = shared across subdomains)
# For a single subdomain only -> 'app.example.com'
SESSION_DOMAIN=.example.com

# Cookie secure flag — always true in production (HTTPS)
SESSION_SECURE_COOKIE=true
```

All four live in SSM Parameter Store (`/app/prod/SESSION_DRIVER`, etc.) and are referenced in `serverless.yml` via `${ssm:/app/prod/...}`. See `laravel-bref-deploy/references/secrets-ssm.md`.

### Why SESSION_DRIVER=database

Lambda instances are stateless and ephemeral — each invocation may run on a different instance. File-based sessions (`SESSION_DRIVER=file`) are written to the read-only Lambda filesystem and do not survive across invocations. The `database` driver persists the `sessions` table to **PostgreSQL** (already the database for the app), making sessions available to all Lambda instances. `CACHE_STORE=database` for the same reason.

### No cross-domain CORS or token dance

Because the Inertia HTML shell and the JSON prop responses are both served by the same Laravel Lambda (same origin), there is no CORS configuration for the frontend — Fortify session cookies are same-origin and there is no token exchange. This is simpler than the decoupled Next.js path where `SANCTUM_STATEFUL_DOMAINS` and CORS headers must be set up across two origins.

---

## The Inertia deploy flow (ordered)

This adds Vite to the existing `laravel-bref-deploy` seven-phase pipeline. Insert the bolded additions:

```
Pre-deploy
  1. Clear config cache                   (unchanged)
  2. composer install --no-dev            (unchanged)
  3. Audit package size                   (unchanged)
  **4. npm install && npm run build       (NEW — Vite, client-only)**
  **5. aws s3 sync public/build/ ...      (NEW — Vite bundles to S3)**
  6. Run migrations BEFORE deploy         (unchanged)

Deploy
  7. osls deploy --stage prod             (unchanged)

Post-deploy
  8. Invalidate CloudFront                (for unhashed files; hashed bundles skip this)
  9. Smoke-test: load the Inertia app     (NEW — check JS/CSS assets load from CloudFront)
  10. Smoke-test /api/v1/health           (unchanged)
  11. Verify SQS worker                   (unchanged)
  12. Verify EventBridge scheduler        (unchanged)
  13. Confirm CloudWatch logs are JSON    (unchanged)
```

The full detailed checklist lives in `laravel-bref-deploy/references/deploy-checklist.md`. The Inertia-specific smoke test (step 9) should confirm:

1. The Inertia HTML shell loads from the Lambda (`GET /` returns 200, Content-Type `text/html`).
2. The `<link>` and `<script>` tags point at the CloudFront domain (not the Lambda URL).
3. JS and CSS load from CloudFront (HTTP response header `via: ... cloudfront` or `x-cache: Hit from cloudfront`).
4. Logging in via Fortify works — the session cookie is set and subsequent Inertia visits are authenticated.

---

## Quick reference: Inertia-specific env vars

| Variable | Value | Purpose |
|---|---|---|
| `SESSION_DRIVER` | `database` | Persist sessions to PostgreSQL (stateless Lambda) |
| `APP_URL` | `https://app.example.com` | Fortify login redirects; CSRF cookie domain |
| `SESSION_DOMAIN` | `.example.com` | Cookie domain scope |
| `SESSION_SECURE_COOKIE` | `true` | HTTPS-only cookies in production |
| `ASSET_URL` | `https://d111....cloudfront.net` | Vite `@vite` directive emits CloudFront URLs |
| `VITE_APP_NAME` | `App Name` | Optional — appears in the browser title bar |

---

## Anti-patterns

**Running `npm run build:ssr`.** There is no Node SSR Lambda on this path. The `build:ssr` output is never executed. Run only `npm run build` (client-only). Running `build:ssr` wastes CI time and produces a dead artifact.

**Omitting `npm install && npm run build` before `osls deploy`.** Deploying without the Vite build means `public/build/` either does not exist or contains stale bundles. The Lambda serves the Inertia HTML shell but the `<script>` tag points at an S3 path that was never uploaded — blank screen in the browser.

**Leaving `ASSET_URL` unset.** The `@vite` directive falls back to the app URL (the Lambda). The Lambda cannot serve static files from `public/build/` (read-only filesystem). Every JS/CSS request 404s.

**Using `SESSION_DRIVER=file`.** File sessions are written to the read-only Lambda filesystem and are not shared across Lambda instances. Fortify authentication will appear to work on the first request and then break on subsequent requests served by a different instance.

**Setting `APP_URL` or `SESSION_DOMAIN` to the API Gateway URL.** Fortify uses `APP_URL` for CSRF cookies and login redirects. If it points at `https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com`, the cookie domain will not match your app's domain and sessions will not persist. Always set `APP_URL` to your real domain.

**Cross-origin session config from the decoupled Next.js path.** The Inertia monolith is same-origin — do not add `SANCTUM_STATEFUL_DOMAINS`, `CORS_ALLOWED_ORIGINS`, or `FRONTEND_URL` from the Sanctum token path. Those settings are irrelevant here and can conflict with Fortify's CSRF validation.
