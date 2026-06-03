# Deploy Checklist

Ordered pre-deploy and post-deploy steps for shipping a Bref-based Laravel app to AWS Lambda. Run every step in sequence — skipping any step is the most common source of production incidents.

## Mental model

```
Pre-deploy
  1. Publish serverless config
  2. Clear local config cache
  3. Run migrations (BEFORE the new code is live)
  4. Audit package size
  5. (Optional) load-test + reserved concurrency check

Deploy
  6. osls deploy --stage prod   ← default (OSS)
     bref deploy                ← managed alternative (Bref Cloud)

Post-deploy
  7. Invalidate CloudFront cache
  8. Smoke-test /api/v1/health
  9. Verify SQS worker receives and processes a message
  10. Verify EventBridge scheduler fires schedule:run
  11. Confirm CloudWatch logs are JSON
```

---

## Pre-deploy

### Step 1 — Publish `serverless.yml` (first deploy only)

Run this once after installing Bref. If `serverless.yml` already exists in `apps/api/`, skip this step.

```bash
# From apps/api/
composer require bref/bref bref/laravel-bridge --update-with-dependencies

php artisan vendor:publish --tag=serverless-config

serverless plugin install -n serverless-lift
```

The generated `serverless.yml` is the starting point. Customise it with the full blueprint from `references/serverless-yml.md` before the first deploy.

### Step 2 — Clear local config cache

Config values are baked into the Lambda package from the environment at deploy time. A stale local cache will produce a package that carries wrong values.

```bash
# From apps/api/
php artisan config:clear
php artisan cache:clear
```

Never commit `bootstrap/cache/config.php`. On Lambda the filesystem is read-only except `/tmp`, so `bootstrap/cache/` is not writable — do not run `php artisan config:cache` locally and bundle the cached file, as it will bake stale or wrong env values into the package. Config loads dynamically from the environment on every cold start.

### Step 3 — Run migrations BEFORE deploy

Migrations run against the live CockroachDB database before the new code is deployed. This preserves the invariant: at every moment the running code understands the schema it sees.

**Rule: never run migrations during boot.** Lambda cold starts are not safe for migrations — concurrent invocations will race, timeouts are short, and a failed migration may leave the schema in a partial state with hundreds of already-live Lambdas pointing at it.

**OSS Serverless (`osls`):**

```bash
# From apps/api/ — invoke the artisan console Lambda with migrate --force
osls bref:cli --args="migrate --force" --stage prod
```

`osls bref:cli` connects to the existing artisan Lambda function and runs the artisan command inside the Lambda environment, reaching CockroachDB over the public internet exactly as the web function does.

**Bref Cloud (`bref deploy`):**

```bash
bref cli artisan -- migrate --force
```

Both commands reach CockroachDB serverless over the public internet (no VPC). Confirm the migration ran cleanly in the output before proceeding.

> If a migration fails partway, do not proceed with the deploy. Fix the migration, verify on a staging stage first, then re-run.

### Step 4 — Audit package size (< 250 MB)

AWS Lambda enforces a 250 MB unzipped deployment package limit. `aws/aws-sdk-php` is the biggest culprit in a Laravel SQS stack — it installs ~70 MB of service SDKs you do not need.

```bash
# From apps/api/ — install production deps only, then check size
composer install --no-dev --optimize-autoloader

# Check the vendor directory size
du -sh vendor/

# If over ~150 MB, find the heaviest offenders:
du -sh vendor/* | sort -rh | head -20
```

Common fixes:

```bash
# Trim unused AWS SDK service clients — only SQS and SSM are used
# Add to composer.json "scripts" → "post-autoload-dump" or a Makefile:
find vendor/aws/aws-sdk-php/src -mindepth 1 -maxdepth 1 -type d \
  ! -name 'SQS' \
  ! -name 'SSM' \
  ! -name 'S3' \
  ! -name 'CloudFront' \
  ! -name 'data' \
  -exec rm -rf {} + 2>/dev/null || true
```

Alternatively, use the `bref/aws-sdk-php-strip` Composer plugin which automates this trimming:

```bash
composer require bref/aws-sdk-php-strip --dev
# It runs automatically during composer install --no-dev
```

Targets:

| Metric | Target |
|---|---|
| Total package size (unzipped) | < 250 MB |
| `vendor/aws/aws-sdk-php` | < 30 MB after stripping |
| Lambda `web` memory | >= 1024 MB |
| Architecture | `arm64` (~20% cheaper vs x86_64) |

Verify in `serverless.yml`:

```yaml
provider:
  architecture: arm64
  ...
functions:
  web:
    memorySize: 1024
```

### Step 5 — Reserved concurrency check (optional but recommended before first production deploy)

CockroachDB serverless has a connection limit. Under Lambda concurrency spikes, the `web` function can open more connections than CockroachDB allows. Set a bounded reserved concurrency to cap fan-out.

```yaml
# serverless.yml — add to the web function
functions:
  web:
    reservedConcurrency: 20   # tune based on CockroachDB connection limits + load test
    memorySize: 1024
    timeout: 28
    ...
```

See `references/cockroachdb-serverless-connection.md` for the fan-out analysis. No RDS Proxy — the stack uses no VPC.

---

## Deploy

### Step 6 — Deploy

**Default — OSS Serverless (`osls`):**

```bash
# Install the OSS Serverless CLI (free, open-source drop-in for Serverless Framework)
npm install -g osls

# From apps/api/
osls deploy --stage prod
```

`osls` is the default because the original Serverless Framework (the `serverless` binary) is no longer open-source. `osls` is a functionally equivalent open-source fork. Use `--stage` to target the right environment; never deploy without specifying a stage.

**Alternative — Bref Cloud (`bref deploy`):**

```bash
# bref/bref is already installed as a production dependency (Step 1).
# The `bref` CLI is provided by that package; no additional install is needed.
# Requires a Bref Cloud account: https://bref.cloud

# Deploy via Bref Cloud (handles packaging, upload, and CloudFormation automatically)
bref deploy
```

Bref Cloud is simpler: it packages the app, strips unused SDK clients, and manages CloudFormation for you. The trade-off is a Bref Cloud account and the associated cost for high-volume workloads.

**Environment-specific notes:**

```bash
# Deploy to staging first; promote to prod after smoke tests pass
osls deploy --stage staging
# ... smoke test staging ...
osls deploy --stage prod
```

The `--stage` value maps to `${opt:stage, 'prod'}` in `serverless.yml` and is used in SSM parameter paths (e.g., `/app/${stage}/APP_KEY`). Match your SSM parameter names to the stage being deployed.

---

## Post-deploy

### Step 7 — CloudFront invalidation

Static assets (CSS, JS, images) and public HTML were synced to S3 during the build step (see `references/storage-s3-cloudfront.md`). CloudFront caches them at edge. After every deploy, invalidate the cache so users receive the new assets.

```bash
# Replace DISTRIBUTION_ID with your CloudFront distribution ID (from serverless.yml outputs or AWS console)
aws cloudfront create-invalidation \
  --distribution-id DISTRIBUTION_ID \
  --paths "/*"
```

Automate as a post-deploy hook in `package.json` or a `Makefile`:

```bash
# Makefile (from monorepo root)
deploy-prod:
	cd apps/api && osls deploy --stage prod
	aws cloudfront create-invalidation \
	  --distribution-id $(CLOUDFRONT_DIST_ID) \
	  --paths "/*"
```

Invalidations take ~30 s to propagate globally. Wait before running the smoke test if you changed frontend assets.

### Step 8 — Smoke-test `/api/v1/health`

Confirm the `web` Lambda is responding and can reach CockroachDB and the database cache:

```bash
# Replace with your API Gateway URL (from osls deploy output or AWS console)
API_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com

curl -sf "${API_URL}/api/v1/health" | jq .
```

Expected response:

```json
{
  "status": "ok",
  "database": "up",
  "cache": "up"
}
```

Failure triage:

| Symptom | Likely cause |
|---|---|
| 502 Bad Gateway | Lambda crash on boot — check CloudWatch `/aws/lambda/<service>-prod-web` |
| `"database":"down"` | CockroachDB DSN wrong in SSM, or SSL cert path missing |
| `"cache":"down"` | `cache` table missing (migration not run) |
| 504 Timeout | Memory too low (< 1024 MB) or cold start > 28 s timeout |
| Stale HTML/assets | CloudFront invalidation not run (Step 7) |

### Step 9 — Verify SQS worker

Confirm the worker Lambda (`php-84` function using `Bref\LaravelBridge\Queue\QueueHandler`) is consuming messages.

**Quick test — dispatch a test job via the console Lambda:**

```bash
osls bref:cli --args="tinker --execute=\"dispatch(new App\\Jobs\\HealthCheckJob())\"" --stage prod
```

Or, if you have a test job that writes to the database:

```bash
# dispatch a test job that logs to CloudWatch, then tail the worker log group
aws logs tail /aws/lambda/<service>-prod-jobs-worker --follow --since 1m
```

Expected: the worker Lambda log shows `[info] Processing ... SQS` and the job completes without a DLQ message.

**DLQ check:**

```bash
# Get approximate DLQ depth — should be 0 after a clean deploy
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/<account>/<service>-prod-jobs-dlq \
  --attribute-names ApproximateNumberOfMessages
```

A non-zero DLQ depth immediately after deploy indicates a worker crash — check the worker Lambda log group for the exception.

See `references/sqs-worker.md` for the full worker configuration.

### Step 10 — Verify EventBridge scheduler fires `schedule:run`

The artisan Lambda is triggered by EventBridge `rate(1 minute)` to run `schedule:run`. After deploy, wait up to 90 seconds then confirm the console Lambda executed.

```bash
# Tail the artisan Lambda log group for schedule:run output
aws logs tail /aws/lambda/<service>-prod-artisan --follow --since 3m
```

Expected log line:

```
[info] Running scheduled command: schedule:run
```

If no log line appears after 2 minutes, check:

1. The EventBridge rule was deployed (`osls info --stage prod` → look for the `ScheduleRule` resource).
2. The `artisan` function name in `serverless.yml` matches the EventBridge target.
3. The `input: '"schedule:run"'` field is present in the schedule event definition (see `references/serverless-yml.md`).

See `references/scheduler-eventbridge.md` for the full EventBridge wiring.

### Step 11 — Confirm CloudWatch logs are JSON

Every log line from the `web`, `artisan`, and worker Lambdas must be a JSON object (Monolog JSON formatter). Structured logs are required for CloudWatch Logs Insights queries and the audit observability contract.

```bash
# Sample recent logs from the web function
aws logs tail /aws/lambda/<service>-prod-web --since 5m | head -20
```

Expected format (one JSON object per line):

```json
{"message":"GET /api/v1/health","level":200,"level_name":"INFO","channel":"single","datetime":"2026-06-03T12:00:00+00:00","context":{"request_id":"abc123","workspace_id":null},"extra":{}}
```

If logs are plain text (Laravel default), set the log channel in `config/logging.php`:

```php
// config/logging.php — use the stderr channel on Lambda (Bref captures stderr → CloudWatch)
'default' => env('LOG_CHANNEL', 'stderr'),

'channels' => [
    'stderr' => [
        'driver'    => 'monolog',
        'handler'   => Monolog\Handler\StreamHandler::class,
        'formatter' => Monolog\Formatter\JsonFormatter::class,
        'with'      => ['stream' => 'php://stderr'],
        'level'     => env('LOG_LEVEL', 'debug'),
    ],
    // ...
],
```

And in `.env` / SSM:

```
LOG_CHANNEL=stderr
LOG_LEVEL=info    # use 'debug' only in staging
```

---

## Full deploy script (reference)

Combine all steps into a repeatable script:

```bash
#!/usr/bin/env bash
# deploy-prod.sh — run from apps/api/
set -euo pipefail

STAGE="prod"
CLOUDFRONT_DIST_ID="${CLOUDFRONT_DIST_ID:?set CLOUDFRONT_DIST_ID}"

echo "==> 1. Clear config cache"
php artisan config:clear && php artisan cache:clear

echo "==> 2. Install production dependencies"
composer install --no-dev --optimize-autoloader

echo "==> 3. Audit package size"
du -sh vendor/
# Fail if vendor > 200MB as a safety buffer
VENDOR_SIZE=$(du -sm vendor/ | cut -f1)
if [ "$VENDOR_SIZE" -gt 200 ]; then
  echo "ERROR: vendor/ is ${VENDOR_SIZE}MB — exceeds 200MB budget. Strip aws-sdk-php first."
  exit 1
fi

echo "==> 4. Sync public assets to S3 (see storage-s3-cloudfront.md)"
# aws s3 sync public/ s3://<bucket>/ --exclude index.php --delete

echo "==> 5. Run migrations BEFORE deploy"
osls bref:cli --args="migrate --force" --stage "${STAGE}"

echo "==> 6. Deploy"
osls deploy --stage "${STAGE}"

echo "==> 7. Invalidate CloudFront"
aws cloudfront create-invalidation \
  --distribution-id "${CLOUDFRONT_DIST_ID}" \
  --paths "/*"

echo "==> 8. Smoke test /api/v1/health"
API_URL=$(osls info --stage "${STAGE}" --verbose 2>/dev/null | grep 'ANY -' | head -1 | awk '{print $3}' | sed 's|/\{proxy+\}||')
STATUS=$(curl -sf "${API_URL}/api/v1/health" | jq -r '.status')
if [ "$STATUS" != "ok" ]; then
  echo "ERROR: health check returned status=${STATUS}"
  exit 1
fi
echo "Health: OK"

echo "==> Deploy complete. Verify SQS worker (Step 9) and scheduler (Step 10) in CloudWatch."
```

---

## Anti-patterns

- **Running `php artisan migrate` during boot / Lambda cold start.** Concurrent invocations will race; failed migrations leave the schema broken with live traffic already hitting the new code. Always run migrations as a pre-deploy CLI step.
- **Deploying without `--stage`.** Without an explicit stage, `osls deploy` defaults to `dev` and may overwrite the wrong environment's stack.
- **Skipping the CloudFront invalidation.** Users will see stale CSS/JS after a deploy. The Lambda serves new API responses immediately but the CDN still serves old assets.
- **Not checking package size before deploy.** A package > 250 MB fails silently during upload, causing a cryptic CloudFormation error. Always run `du -sh vendor/` before `osls deploy`.
- **Committing `.env` or storing secrets in `serverless.yml` plaintext.** All secrets (`APP_KEY`, `DATABASE_URL`, AWS credentials) live in SSM Parameter Store via `${ssm:/app/...}`. See `references/secrets-ssm.md`.
- **Using the original `serverless` binary** (`npm install -g serverless`). The original Serverless Framework is no longer open-source. Use `osls` (OSS drop-in) or `bref deploy` (Bref Cloud managed).
- **Deploying with `composer install` (including dev dependencies).** Dev packages (Pest, Boost, etc.) add tens of MB and may expose debugging tools in production. Always deploy with `--no-dev`.
- **Forgetting the `arm64` architecture flag.** Without it, Lambda defaults to `x86_64` — ~20% more expensive and no performance benefit for PHP workloads.
- **Smoke-testing immediately after CloudFront invalidation.** Invalidations take ~30 s to propagate. Wait before asserting new assets are live.
