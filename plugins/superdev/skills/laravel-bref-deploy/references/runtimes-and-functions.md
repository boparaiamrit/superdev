# Runtimes and Functions

The three Bref 3.x Lambda functions that run a Laravel backend, what each one does, and how to tune them. Read in Phase 2 (configure functions) before writing `serverless.yml`.

## The three functions at a glance

```
web      runtime php-84-fpm     httpApi event → FPM → public/index.php
worker   runtime php-84         Bref\LaravelBridge\Queue\QueueHandler ← SQS (serverless-lift queue)
artisan  runtime php-84-console one-off commands + EventBridge rate(1 minute) → schedule:run
```

Each function uses a different Bref 3.x `runtime:` shorthand key. These map to pre-built AWS Lambda layers published by Bref. You reference them by shorthand — never by raw ARN — because Bref's plugin resolves the layer ARN for your region and architecture automatically.

## Bref 3.x runtime keys

| `runtime:` value | What it provides | Use for |
|---|---|---|
| `php-84-fpm` | PHP 8.4 + PHP-FPM process manager | HTTP requests (`httpApi` event) |
| `php-84` | PHP 8.4 runtime (event-based, no FPM) | SQS queue worker, one-off event handlers |
| `php-84-console` | PHP 8.4 + console layer (Symfony Console bridge) | Artisan commands, scheduler |

`php-84-console` is a composite of the `php-84` runtime layer **plus** a dedicated console layer. Bref resolves both when you set `runtime: php-84-console`; you do not declare them separately.

> These are the **Bref 3.x simplified runtime keys** — not raw ARN strings. The `./vendor/bref/bref` Serverless plugin expands each key to the correct versioned layer ARN for your `provider.region` and `provider.architecture`. Never hard-code an ARN; always use the shorthand.

## `web` — the HTTP function

Handles every `httpApi` request. FPM boots the PHP process and keeps it warm across requests in the same invocation, making the response-per-request cost much lower than a single-invoke PHP runtime would be.

```yaml
# serverless.yml
functions:
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28            # API Gateway / httpApi max is 29 s; stay just under
    memorySize: 1024       # minimum recommended; see memory guidance below
    events:
      - httpApi: '*'
```

**Handler.** `public/index.php` is Laravel's front controller. FPM receives the Lambda event, translates it to a standard FastCGI request, and hands it to `public/index.php`. You do not change this entrypoint.

**Timeout.** API Gateway's integration timeout is 29 seconds. Set `timeout: 28` on the web function so Lambda times out slightly before the gateway cuts the connection, giving you a clean Lambda error rather than an ambiguous gateway 504.

**Reserved concurrency.** Managed PostgreSQL has per-host connection limits. Under a sudden traffic spike, each concurrent Lambda invocation opens its own connection. To prevent connection fan-out from exhausting the managed PostgreSQL connection pool, set `reservedConcurrency` on the web function:

```yaml
functions:
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28
    memorySize: 1024
    reservedConcurrency: 20   # tune based on managed PostgreSQL connection limit; see postgres-timescale-connection.md
    events:
      - httpApi: '*'
```

There is no RDS Proxy available without a VPC, so bounded concurrency is the primary connection-count control. Start at 20 and raise after load testing. See `references/postgres-timescale-connection.md` for the full connection-limit discussion.

## `worker` — the SQS queue function

Processes SQS messages using Bref's `QueueHandler`. AWS triggers this function automatically when messages arrive in the queue — there is no `queue:work` daemon, no Horizon, no Redis.

The worker is declared as a **serverless-lift `queue` construct**, not a plain function, because `serverless-lift` creates the SQS queue, the DLQ, the event source mapping, and the CloudWatch DLQ alarm in one block:

```yaml
# serverless.yml
constructs:
  jobs:
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 60          # keep all jobs under 60 s; SQS visibility timeout must match
```

**Handler.** `Bref\LaravelBridge\Queue\QueueHandler` is the bridge class from `bref/laravel-bridge`. It receives the SQS event payload, deserializes the queued job, and calls `handle()`. You never write this handler yourself — it is provided by the bridge package.

**Timeout.** The SQS `VisibilityTimeout` defaults to 60 seconds in the `serverless-lift` `queue` construct. If `handle()` does not return within the visibility window, SQS makes the message visible again for another attempt. Keep every job under 60 seconds. For longer work, fan out to multiple jobs. See `laravel-enterprise-backend/references/sqs-queues.md` for fan-out patterns.

**Memory.** 512 MB is a reasonable starting point for the worker. Jobs that do heavy data processing may benefit from 1024 MB. Increase if you observe OOM errors in CloudWatch.

**Environment wiring.** The lift construct exposes the queue URL as `${construct:jobs.queueUrl}`. Set this in the provider environment block so the app can dispatch to the correct queue without hard-coding the URL:

```yaml
provider:
  environment:
    QUEUE_CONNECTION: sqs
    SQS_QUEUE: ${construct:jobs.queueUrl}
```

## `artisan` — the console function

Runs Artisan commands and hosts the Laravel scheduler. EventBridge fires it on `rate(1 minute)` to invoke `schedule:run`; one-off admin commands are invoked via `osls bref:cli` at the command line.

```yaml
# serverless.yml
functions:
  artisan:
    handler: artisan
    runtime: php-84-console
    timeout: 720           # 12 minutes; long enough for migrations, prune jobs, reports
    events:
      - schedule:
          rate: rate(1 minute)
          input: '"schedule:run"'   # the string Laravel's scheduler dispatcher expects
```

**Handler.** `artisan` is the Laravel CLI entrypoint file at the project root. The console layer translates the Lambda event payload into a CLI invocation of `php artisan <command>`. When EventBridge fires with `input: '"schedule:run"'`, the runtime calls `php artisan schedule:run`.

**Timeout.** 720 seconds (12 minutes). Scheduled commands must finish within this window, with margin before Lambda's absolute 15-minute cap. Keep individual scheduled commands fast (under 30 seconds) — heavy work belongs in SQS jobs dispatched from within the command.

**One-off commands.** Invoke Artisan directly from your local terminal via the OSS Serverless CLI:

```bash
# Run a migration against the live Lambda environment
osls bref:cli --args="migrate --force"

# Run a custom command
osls bref:cli --args="audit:prune --dry-run"

# Flush cache
osls bref:cli --args="cache:clear"
```

With Bref Cloud:

```bash
bref cli --args="migrate --force"
```

## Memory guidance

| Function | Minimum | Recommended | When to raise |
|---|---|---|---|
| `web` | 512 MB | **1024 MB** | Response times > 300 ms p50; OOM errors; image/PDF processing |
| `worker` | 256 MB | 512 MB | OOM; large dataset jobs; LLM API calls with big context |
| `artisan` | 256 MB | 512 MB | Heavy report generation; CSV exports; batch migrations |

The `web` function is the most memory-sensitive because FPM boots the full Laravel application for every cold start and keeps it in memory across warm invocations. Starting at 1024 MB gives the application room to breathe and reduces cold-start duration. Lambda billing is proportional to `memorySize × duration`, so higher memory can actually be cheaper if it shortens wall-clock time enough.

## ARM64 (Graviton2) — ~20% cost reduction

Set `architecture: arm64` at the provider level to run all functions on Graviton2. Bref publishes layers for both `x86_64` and `arm64`; the plugin selects the correct layer automatically.

```yaml
provider:
  name: aws
  runtime: provided.al2
  architecture: arm64     # Graviton2; ~20% cheaper than x86_64 at the same memory
```

This applies to all three functions. There is no per-function architecture override needed. ARM64 is the recommended default for all new deployments.

## Cold-start budget (~250 ms p99)

A Bref PHP-FPM cold start — a new Lambda container being initialized — is roughly **250 ms at p99** under 1024 MB. This includes:

1. Lambda container initialization and runtime layer loading
2. FPM process startup and bootstrap
3. Laravel application boot (service providers, config loading, route registration)
4. First-request FPM dispatch

Factors that push cold starts higher:
- Memory below 1024 MB (CPU is proportional to memory on Lambda)
- Large `vendor/` directory (Bref loads the autoloader; more files = more I/O)
- Many service providers or complex boot logic in `AppServiceProvider`
- Eager-loading heavy singleton services that could be lazy

To keep cold starts within the ~250 ms budget:
- Keep the deploy package under 250 MB (see `references/deploy-checklist.md`)
- Use ARM64 (faster boot for the same memory allocation)
- Defer heavy service-provider registrations with `$this->app->bind()` instead of `$this->app->singleton()` where the service is rarely used
- Remove unused packages and dev-only code from the production vendor directory

### Optional: provisioned concurrency

If the ~250 ms cold-start budget is unacceptable for your SLA, enable **provisioned concurrency** on the `web` function. Provisioned concurrency keeps a set number of Lambda instances initialized and warm at all times — cold starts for those instances become effectively zero.

```yaml
# serverless.yml — add under the web function
functions:
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28
    memorySize: 1024
    provisionedConcurrency: 2    # keeps 2 warm instances; tune to your traffic baseline
    events:
      - httpApi: '*'
```

Trade-offs:
- **Cost.** Provisioned concurrency is billed continuously whether or not the instances handle requests. At 2 × 1024 MB the cost is roughly $15–20/mo depending on region — weigh this against cold-start impact on your UX.
- **Free-tier target.** For the free-tier / low-traffic target this skill addresses, provisioned concurrency is optional. The ~250 ms p99 cold-start is acceptable for most SaaS APIs where sessions are short and requests are interactive.
- **Alternative: keep-warm pings.** A cheap alternative to provisioned concurrency is an EventBridge rule that fires every 5 minutes with a synthetic health-check request. This does not guarantee zero cold starts but reduces their frequency significantly without the continuous cost.

## Complete function block (reference)

The full `functions:` + `constructs:` block for all three functions, ready to paste into `serverless.yml`:

```yaml
functions:
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28
    memorySize: 1024
    reservedConcurrency: 20
    events:
      - httpApi: '*'

  artisan:
    handler: artisan
    runtime: php-84-console
    timeout: 720
    events:
      - schedule:
          rate: rate(1 minute)
          input: '"schedule:run"'

constructs:
  jobs:
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 60
```

The `web` and `artisan` functions appear under `functions:`; the `worker` appears under `constructs:` because `serverless-lift` manages its SQS plumbing (queue URL, DLQ, event-source mapping). Do not move the worker into `functions:` — it would lose the lift-managed SQS wiring.

## Anti-patterns

- **Using `php-84-fpm` for the worker.** FPM is a process manager for HTTP — it adds unnecessary overhead and expects a CGI request, not an SQS event. The worker must use `php-84`.
- **Using `php-84` for the web function.** The plain event runtime does not include FPM. `public/index.php` requires a FastCGI environment. Use `php-84-fpm`.
- **Hard-coding layer ARNs.** Layer ARNs are region- and architecture-specific and change with every Bref release. Always use the shorthand `runtime:` key and let the Bref plugin resolve the ARN.
- **Setting `timeout` above 29 s on `web`.** API Gateway's httpApi integration timeout is 29 seconds. A Lambda timeout above that means Lambda might still be running when the gateway has already returned a 504 to the client.
- **Running a `queue:work` daemon.** Lambda functions are stateless and short-lived. There is no persistent process. The SQS event source mapping in `serverless-lift` handles invocation automatically.
- **Skipping `reservedConcurrency` on `web`.** Without it, a traffic spike can open hundreds of simultaneous DB connections and exhaust managed PostgreSQL's connection limit. Bound concurrency first, then raise it based on load-test results.
- **Setting `memorySize` below 1024 MB on `web`.** Lower memory means proportionally less CPU. Cold starts get longer and warm requests get slower. 1024 MB is the recommended floor for the FPM web function.
- **Invoking one-off Artisan commands by hitting the HTTP endpoint.** Use `osls bref:cli --args="..."` (or `bref cli --args="..."` for Bref Cloud) to invoke Artisan on the console Lambda directly. HTTP endpoints are for the application, not for ops commands.
