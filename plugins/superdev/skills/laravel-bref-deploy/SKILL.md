---
name: laravel-bref-deploy
description: Deploy a Laravel backend to AWS Lambda serverless with Bref 3.x. Produces a serverless.yml with three functions — a php-84-fpm web function (httpApi), a php-84 SQS queue worker using Bref's QueueHandler, and a php-84-console Artisan function — plus an EventBridge schedule running schedule:run every minute, public HTML and static assets copied to S3 and served via CloudFront, secrets in AWS SSM Parameter Store, database-backed cache and sessions, and CockroachDB serverless reached over the public internet with no VPC. Defaults to the free OSS Serverless CLI (osls deploy) with Bref Cloud (bref deploy) documented as the simpler managed alternative. Use whenever the user wants to deploy, ship, or configure serverless hosting for a Laravel app; mentions Bref, AWS Lambda, serverless.yml, SQS workers, EventBridge scheduling, S3/CloudFront assets, SSM secrets, or serverless Laravel.
---

# Laravel Bref Deploy

A phased pipeline for deploying a Laravel 13 backend to AWS Lambda with **Bref 3.x**. It produces a working `serverless.yml`, the supporting AWS topology (SQS, EventBridge, S3/CloudFront, SSM), and a repeatable migrate-then-deploy workflow. Walk the phases in order; skipping them produces deploys that "work" on the first push and then break on the first queued job, the first scheduled command, the first asset request, or the first `php artisan migrate` during boot.

This is the deployment counterpart to `laravel-enterprise-backend`. That skill builds the app (Eloquent on CockroachDB, SQS jobs, `#[Audit]`, laravel-data contracts); this skill ships it. Do not build domain modules from here — the app is the input, the running serverless stack is the output.

## How to invoke this skill

This is a **recipe skill** — it provides the deploy patterns and references the orchestrator (or a standalone session) follows.

### Pattern 1 — invoked by the orchestrator (most common)

When `prd-design-build-orchestrator` reaches its ship phase (Phase D) and the operator chose the **Laravel** backend stack, it invokes this skill against the already-built `apps/api`. The skill reads `SKILL.md` plus the references for the step in flight (typically `serverless-yml.md`, `runtimes-and-functions.md`, then `deploy-checklist.md`).

### Pattern 2 — standalone deploy

For shipping an existing Laravel app without the orchestrator, start a Claude Code session:

```
Deploy this Laravel app to AWS Lambda with Bref, using the patterns from this skill.
It uses CockroachDB serverless, SQS queues, and database-backed cache/sessions.
```

The main session reads this `SKILL.md` and walks the seven phases. The app must already follow the `laravel-enterprise-backend` conventions (database-backed cache/sessions, SQS queues, no Redis, no Horizon) — Bref does not retrofit those.

## Deploy topology — three Lambda functions

Bref 3.x uses the simplified `runtime:` key (shorthand for the underlying layers). The deploy is **three functions, three runtimes** — never one Lambda for everything:

```
web      runtime php-84-fpm      httpApi event → FPM → public/index.php       (HTTP traffic)
worker   runtime php-84          Bref\LaravelBridge\Queue\QueueHandler ← SQS    (serverless-lift queue construct)
artisan  runtime php-84-console  one-off commands + EventBridge rate(1 minute) → schedule:run
```

- **`web`** — the FPM function. Handles all HTTP via API Gateway `httpApi`. Memory ≥ 1024 MB; bounded **reserved concurrency** so DB connection fan-out to CockroachDB stays sane (no RDS Proxy without a VPC).
- **`worker`** — the SQS consumer. Created by the serverless-lift `queue` construct, which provisions the queue + DLQ and wires the event source. The handler is Bref's `Bref\LaravelBridge\Queue\QueueHandler` (not `queue:work`).
- **`artisan`** — the console function. `php-84-console` is a **composite of the `php-84` layer + the console layer**. Runs one-off commands and is the EventBridge target for `schedule:run`.

> **Why separate functions:** a slow SQS job must never block HTTP requests, and the console runtime has a different invocation model. One Lambda for web + worker is the classic Bref anti-pattern.

## The seven-phase pipeline

```
Phase 1: Install Bref          → composer require bref/bref bref/laravel-bridge; vendor:publish serverless-config; install serverless-lift.
Phase 2: Configure functions   → web (php-84-fpm), worker (php-84 QueueHandler), artisan (php-84-console) in serverless.yml.
Phase 3: SQS + scheduler       → serverless-lift queue construct (+ DLQ); EventBridge rate(1 minute) → schedule:run.
Phase 4: Assets to S3/CloudFront → build + copy public/ to S3, serve via CloudFront, set ASSET_URL. [owned by storage-s3-cloudfront.md, D8]
Phase 5: Secrets via SSM       → APP_KEY, DATABASE_URL, AWS config in SSM Parameter Store; ${ssm:/app/...} or runtime bref-ssm:.
Phase 6: Migrate-then-deploy   → run migrations BEFORE deploy (never during boot); osls deploy --stage prod (or bref deploy).
Phase 7: Verify                → smoke-test the API, confirm worker + scheduler fire, CloudFront invalidation, JSON logs in CloudWatch.
```

---

## Phase 1 — Install Bref

See `references/runtimes-and-functions.md`.

```bash
composer require bref/bref bref/laravel-bridge --update-with-dependencies   # bridge >= 3.0
php artisan vendor:publish --tag=serverless-config                           # generates serverless.yml
serverless plugin install -n serverless-lift                                 # SQS 'queue' construct
```

`bref/laravel-bridge` >= 3.0 is required for the Laravel 13 / PHP 8.4 runtimes. `vendor:publish --tag=serverless-config` scaffolds the initial `serverless.yml`; you then shape it into the three-function topology below. `serverless-lift` adds the `queue` construct used in Phase 3.

## Phase 2 — Configure the web / worker / artisan functions

See `references/serverless-yml.md` (full blueprint) and `references/runtimes-and-functions.md`.

Shape the generated `serverless.yml` into the three functions: `web` (`php-84-fpm`, `httpApi: '*'`), `artisan` (`php-84-console`), and the `worker` (`php-84`) inside a serverless-lift `queue` construct. Set `architecture: arm64` (~20% cheaper) and `runtime: provided.al2` at the provider level. Give `web` `memorySize: 1024` and bounded reserved concurrency.

## Phase 3 — SQS worker + EventBridge scheduler

See `references/sqs-worker.md` and `references/scheduler-eventbridge.md`.

- **Queue:** the serverless-lift `queue` construct creates the SQS queue **and** its DLQ and wires the worker function. The app already runs `QUEUE_CONNECTION=sqs`; set `SQS_QUEUE=${construct:jobs.queueUrl}`. No `queue:work` daemon, no Horizon. Keep jobs < 60 s (well under the 15-min Lambda cap); rely on job idempotency (SQS is at-least-once); alarm on the DLQ via CloudWatch.
- **Scheduler:** an EventBridge `schedule` event on the `artisan` function fires `rate(1 minute)` → `schedule:run`. Cron definitions live in `routes/console.php`; the audit-prune command runs here.

## Phase 4 — Public HTML + static assets to S3/CloudFront (D8)

See `references/storage-s3-cloudfront.md` — **this reference owns asset/HTML handling.**

The Lambda filesystem is **read-only except `/tmp`**, so `public/` cannot serve static files. Build the assets, **copy `public/` HTML + static assets to S3** on deploy, and serve them via **CloudFront**. Set `ASSET_URL` to the CloudFront domain and always use `asset()` in the app. Invalidate CloudFront on every deploy. For uploads larger than the ~4 MB API Gateway payload cap, use **presigned S3 URLs**; user uploads live on an S3 disk (`allowAcl: true` for Flysystem ACLs).

## Phase 5 — Secrets via SSM Parameter Store

See `references/secrets-ssm.md`.

Secrets live in **AWS SSM Parameter Store** (free tier), never in the repo or `serverless.yml`. Reference them at deploy time with `${ssm:/app/...}` or resolve them at runtime with the `bref-ssm:` prefix via `bref/secrets-loader`. `APP_KEY` (`php artisan key:generate`, then store), `DATABASE_URL` (the CockroachDB DSN), and AWS config all come from SSM.

## Phase 6 — Migrate, then deploy

See `references/deploy-checklist.md` and `references/cockroachdb-serverless-connection.md`.

**Run migrations BEFORE the deploy, never during boot.** A boot-time `migrate` races every cold-starting Lambda. Migrate against CockroachDB, then deploy:

```bash
php artisan config:clear
osls bref:cli --args="migrate --force"     # migrate FIRST, against CockroachDB
osls deploy --stage prod                    # then deploy
```

Audit the deploy package against the **250 MB** Lambda limit (watch `aws/aws-sdk-php` — pin to the services you use). CockroachDB serverless is reached over the **public internet with no VPC** (avoids ~$32/mo NAT + ENI cold starts); the trade-off is bounded reserved concurrency on `web` to cap connection fan-out.

## Phase 7 — Verify

See `references/deploy-checklist.md`.

After deploy: smoke-test `GET /api/v1/health` over the API Gateway URL; dispatch a test job and confirm the **worker** drains it; confirm the **scheduler** fires (`schedule:run` invocation in CloudWatch); run the CloudFront invalidation and load an asset via `ASSET_URL`; confirm CloudWatch log lines are JSON with `request_id` / `workspace_id`; confirm nothing is leaking secrets to stdout.

---

## Deploy tool

**Default: OSS Serverless (`osls`).** The original Serverless Framework is **no longer open-source** (it moved to a paid license for larger orgs), so the default deploy CLI here is **`osls`** — the free, open-source fork that is a drop-in for the `serverless` command:

```bash
npm i -g osls
osls deploy --stage prod
osls bref:cli --args="migrate --force"     # run an Artisan command against the deployed stack
osls remove --stage prod                   # tear down
```

**Alternative: Bref Cloud (`bref deploy`).** Bref Cloud is the documented **managed** alternative — it handles the AWS account wiring and provides a dashboard. Same `serverless.yml`, simpler operator experience:

```bash
bref deploy
```

> Do not install or invoke the original `serverless` CLI by name — use `osls` for the OSS path or `bref deploy` for the managed path. The `serverless.yml` format is identical for both.

---

## Reference files

| File | When to read |
|---|---|
| `references/serverless-yml.md` | Phase 2 (the complete `serverless.yml` blueprint — provider, three functions, queue construct, env) |
| `references/runtimes-and-functions.md` | Phase 1–2 (the three Bref 3.x runtimes `php-84-fpm` / `php-84` / `php-84-console`, memory/timeout, ARM64, cold-start budget) |
| `references/sqs-worker.md` | Phase 3 (Bref `QueueHandler` + serverless-lift `queue` construct + DLQ; no `queue:work`/Horizon) |
| `references/scheduler-eventbridge.md` | Phase 3 (EventBridge `rate(1 minute)` → `schedule:run`; cron defs in `routes/console.php`; audit prune) |
| `references/storage-s3-cloudfront.md` | Phase 4 (read-only FS; copy `public/` → S3 + CloudFront; `ASSET_URL`; presigned uploads) — owns D8 |
| `references/secrets-ssm.md` | Phase 5 (SSM Parameter Store; `${ssm:/app/...}` vs runtime `bref-ssm:`; `APP_KEY` / `DATABASE_URL`) |
| `references/cockroachdb-serverless-connection.md` | Phase 6 (public-internet / no-VPC connection, `sslmode=verify-full`, bounded reserved concurrency) |
| `references/deploy-checklist.md` | Phase 6–7 (migrate-before-deploy, package < 250 MB, `osls deploy` / `bref deploy`, post-deploy smoke tests) |
| `references/inertia-monolith-deploy.md` | When deploying a fullstack **Inertia monolith** — Vite `npm run build` (client-only), asset sync, session-auth config |

---

## Validation checklist

- [ ] `serverless.yml` defines **three functions** — `web` (`php-84-fpm`, `httpApi`), `worker` (`php-84`, `Bref\LaravelBridge\Queue\QueueHandler`), `artisan` (`php-84-console`)
- [ ] The **SQS worker** is created via the serverless-lift `queue` construct, with a **DLQ** and a CloudWatch alarm; `SQS_QUEUE=${construct:jobs.queueUrl}`; `QUEUE_CONNECTION=sqs`; no `queue:work`, no Horizon
- [ ] The **EventBridge scheduler** fires `rate(1 minute)` → `schedule:run` on the `artisan` function
- [ ] **Public HTML + static assets are copied to S3 and served via CloudFront**; `ASSET_URL` is set; CloudFront is invalidated on deploy (D8)
- [ ] **Secrets are in SSM Parameter Store** (`APP_KEY`, `DATABASE_URL`, AWS config); nothing committed; `${ssm:/app/...}` or runtime `bref-ssm:`
- [ ] **Cache + sessions are database-backed** (`CACHE_STORE=database`, `SESSION_DRIVER=database`); no `/tmp`, no Redis
- [ ] CockroachDB is reached **over the public internet with no VPC**; `web` has bounded **reserved concurrency**; `sslmode=verify-full`
- [ ] **Migrations run BEFORE deploy** (`osls bref:cli --args="migrate --force"`), never during boot
- [ ] Deploy **package < 250 MB** (audited `aws/aws-sdk-php`); `architecture: arm64`; `web` `memorySize >= 1024`
- [ ] Deploy command documented for **both** `osls deploy --stage prod` (default) and `bref deploy` (Bref Cloud); the original Serverless Framework is **not** used
- [ ] Post-deploy: `/api/v1/health` smoke test passes; a test job drains through the worker; CloudWatch logs are JSON with `request_id` / `workspace_id`

---

## Anti-patterns

**A1 — One Lambda for web + worker (+ scheduler).** A slow SQS job blocks HTTP, and the console runtime is invoked differently. Use the three separate functions / runtimes (`php-84-fpm`, `php-84`, `php-84-console`).

**A2 — Migrating during boot.** A boot-time `php artisan migrate` races every cold-starting Lambda and can corrupt schema. Migrate **before** deploy (`osls bref:cli --args="migrate --force"`).

**A3 — Serving `public/` from Lambda.** The Lambda filesystem is read-only except `/tmp`. Static assets must be copied to S3 + CloudFront; set `ASSET_URL` and use `asset()`. Never write app data outside `/tmp`.

**A4 — Putting the app in a VPC for CockroachDB.** CockroachDB serverless is on the public internet; a VPC adds ~$32/mo NAT cost and ENI cold-start latency for no benefit. Stay VPC-less and bound `web` reserved concurrency instead.

**A5 — Using `queue:work` or Horizon.** Both assume a long-running daemon and Redis. The Bref SQS worker is event-driven via `QueueHandler`; the DLQ + CloudWatch alarms replace the Horizon dashboard.

**A6 — Installing the original `serverless` CLI.** It is no longer OSS. Use `osls` (default) or `bref deploy` (Bref Cloud). The `serverless.yml` is identical for both.

**A7 — Committing secrets to `serverless.yml` or `.env`.** All secrets resolve from SSM (`${ssm:/app/...}` or runtime `bref-ssm:`). Generate `APP_KEY` and store it in SSM; never commit it.

**A8 — Ignoring the 250 MB package / 4 MB payload limits.** Audit the package (especially `aws/aws-sdk-php`) and use presigned S3 URLs for uploads over ~4 MB; do not stream large bodies through API Gateway.
