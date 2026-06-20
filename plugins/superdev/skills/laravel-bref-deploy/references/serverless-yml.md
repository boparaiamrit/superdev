# serverless.yml — The Bref 3.x Deploy Blueprint

The single source of truth for the AWS topology: one `serverless.yml` that declares three Lambda functions (web, artisan, worker), the SQS queue, the EventBridge schedule, and the production environment. Read this first in the deploy pipeline (Phase 2); the other references drill into each block.

`php artisan vendor:publish --tag=serverless-config` generates a starter `serverless.yml`. This file is the target shape you edit it into.

## The complete blueprint

```yaml
service: app-api
provider:
  name: aws
  region: ${env:AWS_REGION, 'us-east-1'}
  runtime: provided.al2
  architecture: arm64
  environment:
    APP_ENV: production
    APP_KEY: ${ssm:/app/APP_KEY}
    DATABASE_URL: ${ssm:/app/DATABASE_URL}      # managed PostgreSQL + TimescaleDB DSN (sslmode=require)
    CACHE_STORE: database
    SESSION_DRIVER: database
    QUEUE_CONNECTION: sqs
    SQS_QUEUE: ${construct:jobs.queueUrl}
    FILESYSTEM_DISK: s3
    ASSET_URL: ${env:ASSET_URL}                 # CloudFront domain

plugins:
  - ./vendor/bref/bref
  - serverless-lift

functions:
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28
    memorySize: 1024
    events:
      - httpApi: '*'
  artisan:
    handler: artisan
    runtime: php-84-console
    timeout: 720
    events:
      - schedule:
          rate: rate(1 minute)
          input: '"schedule:run"'              # EventBridge -> scheduler

constructs:
  jobs:
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 60

resources:
  # S3 bucket + CloudFront for public assets are managed in storage-s3-cloudfront.md
```

That is the whole file for a standard deployment. Each block is explained below.

## `service`

```yaml
service: app-api
```

The CloudFormation stack name prefix. Every resource AWS creates (functions, queues, log groups) is namespaced under `app-api-<stage>`. Keep it short and DNS-safe; it shows up in ARNs and the API Gateway URL. Pick it once — renaming later orphans the old stack.

## `provider`

```yaml
provider:
  name: aws
  region: ${env:AWS_REGION, 'us-east-1'}
  runtime: provided.al2
  architecture: arm64
```

- `runtime: provided.al2` — the Amazon Linux 2 custom-runtime base. Bref's layers (selected per-function via `runtime:` keys below) sit on top of it. You set this once at the provider level; the per-function `runtime:` shorthand picks the actual PHP layer.
- `architecture: arm64` — Graviton2. ~20% cheaper per GB-second than x86 and Bref ships arm64 layers for all three runtimes. Set it once here so every function inherits it; do not mix architectures across functions.
- `region` — read from `AWS_REGION` at deploy time with a sensible default. Keep the region pinned to where your managed PostgreSQL + TimescaleDB host lives to minimise round-trip latency.

### `provider.environment` — the production env

```yaml
  environment:
    APP_ENV: production
    APP_KEY: ${ssm:/app/APP_KEY}
    DATABASE_URL: ${ssm:/app/DATABASE_URL}      # managed PostgreSQL + TimescaleDB DSN (sslmode=require)
    CACHE_STORE: database
    SESSION_DRIVER: database
    QUEUE_CONNECTION: sqs
    SQS_QUEUE: ${construct:jobs.queueUrl}
    FILESYSTEM_DISK: s3
    ASSET_URL: ${env:ASSET_URL}                 # CloudFront domain
```

Provider-level `environment` is injected into **every** function (web, artisan, worker), which is exactly what you want here — all three share the same DB, queue, cache, and asset config.

| Var | Value | Why |
|---|---|---|
| `APP_ENV` | `production` | Disables debug pages, enables prod caching. |
| `APP_KEY` | `${ssm:/app/APP_KEY}` | Encryption key, pulled from SSM Parameter Store at **deploy time** — never committed. See `secrets-ssm.md`. |
| `DATABASE_URL` | `${ssm:/app/DATABASE_URL}` | Full managed PostgreSQL + TimescaleDB DSN (`postgresql://…:5432/db?sslmode=require`). The stock `pgsql` driver reads `url`. See `postgres-timescale-connection.md`. |
| `CACHE_STORE` | `database` | DB-backed cache — Lambda is stateless and Redis would need a VPC. The `cache` table lives in PostgreSQL. |
| `SESSION_DRIVER` | `database` | DB-backed sessions for the same reason. The `sessions` table lives in PostgreSQL. |
| `QUEUE_CONNECTION` | `sqs` | Jobs dispatch to SQS, not a DB queue, and not Redis. SQS remains the right choice for the Bref serverless deploy. |
| `SQS_QUEUE` | `${construct:jobs.queueUrl}` | The queue URL is **produced by serverless-lift** at deploy time from the `jobs` construct below — you never hardcode the account-scoped URL. |
| `FILESYSTEM_DISK` | `s3` | The Lambda filesystem is read-only except `/tmp`; the default disk must be S3. See `storage-s3-cloudfront.md`. |
| `ASSET_URL` | `${env:ASSET_URL}` | The CloudFront domain so `asset()` emits CDN URLs instead of the Lambda's own host. |

> `${ssm:/app/...}` resolves at **deploy time** (the value is baked into the function config). `${env:...}` reads the deployer's shell environment. `${construct:...}` is a serverless-lift cross-reference resolved during the same deploy. None of these put secrets in the repo.

## `plugins`

```yaml
plugins:
  - ./vendor/bref/bref
  - serverless-lift
```

- `./vendor/bref/bref` — the Bref plugin (installed by Composer, hence the `vendor/` path). It registers the `php-84-fpm` / `php-84` / `php-84-console` runtime layers. Without it the `runtime:` shorthand keys below are unrecognised.
- `serverless-lift` — adds high-level CloudFormation **constructs** like `queue` (used below). Install once with `serverless plugin install -n serverless-lift`.

## `functions`

Two of the three functions are declared here; the **worker** is declared by the `jobs` queue construct (see `constructs` below) so it is wired to the SQS event source automatically. The three runtimes are detailed in `runtimes-and-functions.md`.

### `web` — the HTTP function

```yaml
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28
    memorySize: 1024
    events:
      - httpApi: '*'
```

- `runtime: php-84-fpm` — Bref 3.x shorthand for the PHP 8.4 FPM layer. FPM gives you the standard PHP-FPM request lifecycle, which is what Laravel's HTTP kernel expects.
- `handler: public/index.php` — Laravel's standard front controller. FPM invokes it per request.
- `events: - httpApi: '*'` — a single catch-all route on API Gateway HTTP API. Every path and method is forwarded to FPM; Laravel's router does the rest. (HTTP API is cheaper and lower-latency than REST API.)
- `timeout: 28` — API Gateway HTTP API hard-caps the integration at 29 s, so 28 s is the practical ceiling for a synchronous request. Long work belongs on the queue or scheduler, not here.
- `memorySize: 1024` — at least 1024 MB for the web function. Lambda CPU scales with memory, so this is also a latency knob; cold start lands around ~250 ms p99 at this size.

#### Reserved concurrency on `web` — guarding DB fan-out

There is **no RDS Proxy** here (that needs a VPC, which we deliberately avoid — see `postgres-timescale-connection.md`). Each warm `web` Lambda holds its own DB connection, so unbounded Lambda concurrency means unbounded connections to the managed PostgreSQL host. Bound it:

```yaml
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28
    memorySize: 1024
    reservedConcurrency: 20          # cap concurrent web Lambdas -> caps DB connections
    events:
      - httpApi: '*'
```

Pick a number that keeps peak connections inside the managed PostgreSQL connection budget. Treat it as a launch-time load-test output, not a guess; `deploy-checklist.md` covers verifying it. (`reservedConcurrency` is omitted from the base blueprint above to keep it minimal — add it before any real traffic.)

### `artisan` — console + scheduler

```yaml
  artisan:
    handler: artisan
    runtime: php-84-console
    timeout: 720
    events:
      - schedule:
          rate: rate(1 minute)
          input: '"schedule:run"'              # EventBridge -> scheduler
```

- `runtime: php-84-console` — Bref 3.x shorthand for a **composite** of the `php-84` layer plus the Bref console layer. It runs Artisan commands as one-off invocations.
- `handler: artisan` — Laravel's `artisan` entry script.
- The `schedule` event is an **EventBridge** rule firing `rate(1 minute)`. The `input: '"schedule:run"'` passes the command name to the console handler, so every minute this Lambda runs `php artisan schedule:run` — the standard Laravel scheduler tick. Your cron definitions live in `routes/console.php`; EventBridge just provides the per-minute heartbeat. See `scheduler-eventbridge.md`.
- The double-quoting `'"schedule:run"'` is required: the outer single quotes are YAML, the inner double quotes make it a valid JSON string (EventBridge `input` must be JSON).
- `timeout: 720` — 12 minutes, the headroom a scheduler tick or a one-off command may need. Individual scheduled commands should still finish well inside this; heavy work fans out to the queue.

This same function is also how you run ad-hoc commands in production (e.g. migrations) via `osls bref:cli` — see `deploy-checklist.md`.

## `constructs` — the SQS queue + worker

```yaml
constructs:
  jobs:
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 60
```

This is a **serverless-lift** construct, not a raw `functions` entry. `type: queue` provisions, in one block:

- the main **SQS queue** (its URL is exposed as `${construct:jobs.queueUrl}`, referenced in `environment` above),
- a **dead-letter queue** (DLQ) with a sensible default `maxRetries`,
- the **worker Lambda** and its SQS event-source mapping.

The worker:

- `handler: Bref\LaravelBridge\Queue\QueueHandler` — the Laravel Bridge's SQS handler. It receives the SQS message, rehydrates the Laravel job, and runs it. You never write a `queue:work` daemon; there is none.
- `runtime: php-84` — Bref 3.x shorthand for the plain PHP 8.4 layer (event-driven, **not** FPM — there is no HTTP request lifecycle for a queue worker).
- `timeout: 60` — jobs must complete within 60 s. This matches the queue's visibility timeout; longer jobs get redelivered and double-processed. Keep jobs small and idempotent. See `sqs-worker.md` and the build skill's `sqs-queues.md`.

> Need more than one queue (e.g. a dedicated `audit` queue)? Add another `type: queue` construct under `constructs:` and reference its `${construct:<name>.queueUrl}`. Multi-queue routing is covered in `sqs-worker.md`.

## `resources` — assets live elsewhere

```yaml
resources:
  # S3 bucket + CloudFront for public assets are managed in storage-s3-cloudfront.md
```

The Lambda filesystem is read-only except `/tmp`, so public HTML and static assets are **not** served from the function. They are copied to S3 and fronted by CloudFront. The S3 bucket, the CloudFront distribution, the `ASSET_URL` wiring, and the deploy-time `aws s3 sync` all live in **`storage-s3-cloudfront.md`** (decision D8). Keep that infrastructure there so this file stays focused on the compute topology; the `resources:` block here is just the insertion point.

## Bref 3.x `runtime:` shorthand — what the keys mean

Bref 3.x replaced the verbose `layers: [...]` arrays with a single `runtime:` key per function. The three values used in this blueprint:

| `runtime:` key | What it is | Used by |
|---|---|---|
| `php-84-fpm` | PHP 8.4 + PHP-FPM layer — full HTTP request lifecycle | `web` |
| `php-84` | PHP 8.4 layer — event-driven, no FPM | the `jobs` worker |
| `php-84-console` | composite: `php-84` layer **+** the Bref console layer | `artisan` |

The provider's `runtime: provided.al2` is the custom-runtime base these layers attach to. Do not hand-author `layers:` ARNs — the shorthand resolves the correct, version-pinned Bref layer for you. See `runtimes-and-functions.md` for memory/timeout guidance per runtime.

## Internal consistency checklist

Before deploying, confirm the cross-references inside the file resolve:

- `SQS_QUEUE: ${construct:jobs.queueUrl}` references a construct named **`jobs`** that exists under `constructs:`. Rename one and you must rename both.
- Every `runtime:` value (`php-84-fpm`, `php-84`, `php-84-console`) is a real Bref 3.x layer — the `./vendor/bref/bref` plugin must be listed under `plugins:` for them to resolve.
- `serverless-lift` is under `plugins:` because the `jobs` construct (`type: queue`) is a lift construct.
- `ASSET_URL` and `AWS_REGION` come from `${env:...}` — they must be set in the deployer's shell (or CI) at deploy time.
- `APP_KEY` and `DATABASE_URL` resolve from SSM (`/app/APP_KEY`, `/app/DATABASE_URL`) — the parameters must exist before deploy.

## Anti-patterns

- **One Lambda for everything.** Do not route HTTP, queue, and console through a single function. The three runtimes (`php-84-fpm` / `php-84` / `php-84-console`) are different layers for different lifecycles; collapsing them breaks FPM or the queue handler.
- **A `queue:work` daemon.** There is no long-running worker on Lambda. The `jobs` construct's event-source mapping invokes `QueueHandler` per message. Adding `queue:work` does nothing and wastes invocations.
- **Hardcoding the SQS queue URL.** Use `${construct:jobs.queueUrl}`; the account-scoped URL only exists after the queue is created.
- **Committing secrets into `environment`.** `APP_KEY` and `DATABASE_URL` come from `${ssm:/app/...}`, never inline literals. See `secrets-ssm.md`.
- **Putting the app in a VPC** to "reach the database." The managed PostgreSQL + TimescaleDB host is reached over the public internet (`sslmode=require`); a VPC adds NAT cost and ENI cold starts for no benefit here. See `postgres-timescale-connection.md`.
- **`web` timeout > 29 s.** API Gateway HTTP API caps the integration at 29 s; a higher Lambda timeout cannot be reached synchronously. Offload long work to the queue or scheduler.
- **Unbounded `web` concurrency in production.** Without `reservedConcurrency`, a traffic spike opens unbounded PostgreSQL connections (no RDS Proxy without a VPC). Cap it.
- **`x86_64` (or mixed) architecture.** Set `arm64` once at the provider level for the ~20% saving; mixing architectures across functions is a packaging foot-gun.
- **Serving `public/` assets from the function.** The Lambda FS is read-only except `/tmp`; assets go to S3 + CloudFront (`storage-s3-cloudfront.md`), not the web Lambda.
- **Hand-authoring `layers:` ARNs.** Use the Bref 3.x `runtime:` shorthand; the plugin pins the correct layer version.