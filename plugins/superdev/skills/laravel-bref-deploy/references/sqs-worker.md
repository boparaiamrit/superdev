# SQS Worker — Bref `QueueHandler` + serverless-lift `queue` Construct

The infrastructure side of async work. The `serverless-lift` `queue` construct provisions an SQS queue **and** its Dead Letter Queue, and wires a worker Lambda that runs Bref's `QueueHandler`. AWS invokes the worker when messages arrive — there is **no `queue:work` daemon**. Read during Phase 3 (SQS + scheduler).

> App-side companion: `laravel-enterprise-backend/references/sqs-queues.md` owns the job classes, dispatch, idempotency guards, and `failed()` handlers. This file owns the `serverless.yml` wiring, the runtime, the DLQ, and the alarms. Read them together.

## Mental model

```text
Laravel app            AWS                          Worker Lambda
-----------            ---                          -------------
Job::dispatch()  --->  SQS queue (lift 'queue')     php-84 runtime
                       │  on failure after N tries  Bref\LaravelBridge\Queue\QueueHandler
                       └─> DLQ ───> CloudWatch alarm decodes the SQS message,
                                                    runs the Laravel job, ACKs on success
```

Three locked facts:

1. **`serverless-lift` `queue` construct** creates the SQS queue + DLQ + the event-source mapping to the worker Lambda. One construct = one queue + one DLQ.
2. **Worker runtime is `php-84`** (the plain event runtime — *not* `php-84-fpm`, which is for HTTP, and *not* `php-84-console`, which is for Artisan).
3. **Handler is `Bref\LaravelBridge\Queue\QueueHandler`** — shipped by `bref/laravel-bridge`. It receives the raw SQS event, hydrates the Laravel job, and executes it inside the framework.

No Horizon. No `queue:work`. No database queue driver (CockroachDB has no `SKIP LOCKED`). SQS only.

## The `queue` construct in `serverless.yml`

```yaml
plugins:
  - ./vendor/bref/bref
  - serverless-lift

constructs:
  jobs:
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84            # plain event runtime — NOT fpm, NOT console
      timeout: 60                # seconds — matches the 60 s job contract
    # serverless-lift defaults applied automatically:
    #   maxRetries: 3            (attempts before a message goes to the DLQ)
    #   alarm: <none unless set> (see "CloudWatch alarms" below)
```

`type: queue` is the entire infrastructure declaration. On `osls deploy` it expands to:

- an **SQS queue** (`jobs`),
- a **Dead Letter Queue** (`jobs-dlq`) with a redrive policy,
- the **Lambda event-source mapping** that triggers the `worker` function on new messages,
- the IAM permissions for the worker to consume the queue.

You do not write any of that by hand — that is the point of the construct.

## Wiring the app to the queue

The construct exposes its queue URL as `${construct:jobs.queueUrl}`. Inject it as `SQS_QUEUE` so Laravel dispatches to the queue the construct just created:

```yaml
provider:
  environment:
    QUEUE_CONNECTION: sqs
    SQS_QUEUE: ${construct:jobs.queueUrl}   # the real URL, resolved at deploy time
```

On the app side `config/queue.php` already reads `SQS_QUEUE` (see `sqs-queues.md`). The `prefix` + `queue` name there form the URL locally; on Lambda the construct overrides it with the live URL above. **Never hardcode the queue URL** — let the construct resolve it so the same `serverless.yml` works across stages.

## Why `php-84`, not the other runtimes

| Function | Runtime | Why |
|---|---|---|
| `web` | `php-84-fpm` | HTTP via FPM, serves `public/index.php` behind API Gateway `httpApi`. |
| **`worker`** | **`php-84`** | **Plain event runtime; the SQS payload is the Lambda event, decoded by `QueueHandler`.** |
| `artisan` | `php-84-console` | Composite of the `php-84` layer + a console layer; runs one-off commands and the scheduler. |

Putting the worker on `php-84-fpm` would be wrong — there is no HTTP request. Putting web and worker in one function violates the "one Lambda per concern" rule and couples their scaling and memory.

`php-84` and `php-84-console` are Bref 3.x runtime shorthands (`runtime:` key) for the underlying layers; do not name the raw layer ARNs.

## The 60-second job contract

The construct sets the SQS `VisibilityTimeout` and the worker `timeout` to **60 s** by default. If a job does not finish in 60 s, SQS makes the message visible again and a second Lambda picks it up — double processing.

- Keep every job **under 60 s**. Lambda's hard ceiling is 15 minutes, but the queue contract is 60 s — design to it.
- For genuinely long work, fan out into smaller jobs (parent dispatches children) or move it to a scheduled `artisan` command (see `scheduler-eventbridge.md`).
- The job-side fan-out and chunking patterns live in `sqs-queues.md`.

If you raise the worker `timeout`, raise the SQS visibility timeout to match — they must stay in lockstep, and AWS requires the queue's visibility timeout to be at least the function timeout.

## Idempotency is mandatory

SQS is **at-least-once**: a message can be delivered more than once (timeout redrive, cold-start restart, partial-batch retry). Every job's `handle()` must be safe to run twice. The guard patterns — natural idempotency, an idempotency/dedupe table, and the stable `$jobId` property — are documented app-side in `sqs-queues.md`. The infrastructure cannot dedupe for you; the construct uses a standard (not FIFO) queue.

## DLQ + CloudWatch alarms (no Horizon dashboard)

There is no Horizon. Observability is the DLQ plus CloudWatch.

The construct creates the DLQ automatically. After a message exhausts `maxRetries` it lands on `jobs-dlq`. Add an alarm so a non-empty DLQ pages someone:

```yaml
constructs:
  jobs:
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 60
    maxRetries: 3
    alarm: ops@example.com        # serverless-lift creates an SNS topic + a DLQ alarm
```

Setting `alarm:` makes serverless-lift provision an SNS topic and a CloudWatch alarm on the DLQ's `ApproximateNumberOfMessagesVisible` — any message on the DLQ triggers a notification. For finer control (custom thresholds, multiple metrics), define the alarm explicitly in `resources:`:

```yaml
resources:
  Resources:
    JobsDlqDepthAlarm:
      Type: AWS::CloudWatch::Alarm
      Properties:
        AlarmName: ${self:service}-${sls:stage}-jobs-dlq-depth
        Namespace: AWS/SQS
        MetricName: ApproximateNumberOfMessagesVisible
        Dimensions:
          - Name: QueueName
            Value: ${construct:jobs.queueName}-dlq
        Statistic: Sum
        Period: 60
        EvaluationPeriods: 1
        Threshold: 1               # any message on the DLQ is an incident
        ComparisonOperator: GreaterThanOrEqualToThreshold
        TreatMissingData: notBreaching
```

Inspect failures with **CloudWatch Logs Insights** over the worker function's log group — logs are JSON (Monolog `stderr`), so you can query by `action`, `workspace_id`, or `error`. The job's `failed()` method (app-side) writes the permanent-failure log line that you query here.

To replay DLQ messages after a fix, use the SQS console's **Start DLQ redrive** or `aws sqs` to move messages back to the source queue.

## Multiple queues

Most apps need more than one queue (e.g. `audit` separated from `default` so an audit spike never delays user-facing work — see `sqs-queues.md`). Two approaches:

### Option A — one construct per queue (recommended for isolation)

Each logical queue is its own `type: queue` construct, giving each its own DLQ, its own alarm, and independent worker scaling:

```yaml
constructs:
  jobs:                          # default / business jobs
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 60
    alarm: ops@example.com
  audit:                         # AuditWrite jobs — high volume, isolated
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 30
    maxRetries: 5
    alarm: ops@example.com
```

The worker handler can be the **same** `QueueHandler` for both — `bref/laravel-bridge` reads the SQS event's source queue and runs whatever job was serialized into the message. Dispatch routes messages to the right queue via the construct URL. Expose each URL as an env var the app maps to a queue name:

```yaml
provider:
  environment:
    SQS_QUEUE: ${construct:jobs.queueUrl}          # default
    SQS_QUEUE_AUDIT: ${construct:audit.queueUrl}    # audit
```

Trade-off: each construct is a separate Lambda + queue + DLQ — more infrastructure, more isolation, independent alarms and concurrency.

### Option B — one queue, job-class routing (Laravel 13 `Queue::route`)

Keep a single SQS construct and let Laravel route jobs to logical queue names by class. Laravel 13 adds `Queue::route()` for declaring per-job-class queue assignment in one place (e.g. in a service provider's `boot()`):

```php
// app/Providers/QueueServiceProvider.php (boot)
use Illuminate\Support\Facades\Queue;

Queue::route(\App\Jobs\AuditWrite::class, 'audit');
Queue::route(\App\Jobs\SendCampaignEmail::class, 'email-send');
// jobs without an explicit route fall back to the connection's default queue
```

This removes per-call `->onQueue(...)` and centralizes routing — but with a **single** SQS construct, every "queue name" is logical: messages still land on one physical SQS queue and one DLQ unless you also create the matching constructs. Use Option A when you need physical isolation (separate DLQs/alarms/scaling); use Option B when one physical queue is acceptable and you only want clean per-class organization.

> A logical queue name only becomes a separate physical SQS queue when a matching construct exists. Routing a job to `'audit'` with no `audit` construct sends it to the default queue under that name — fine for organization, but it shares the default queue's DLQ and alarm.

## Reserved concurrency for the worker

Workers open database connections too. Under a burst, the worker fans out exactly like the web function and can exhaust CockroachDB serverless connections (there is no RDS Proxy without a VPC — see `cockroachdb-serverless-connection.md`). Bound the worker's reserved concurrency so the queue drains at a safe rate:

```yaml
constructs:
  jobs:
    type: queue
    worker:
      handler: Bref\LaravelBridge\Queue\QueueHandler
      runtime: php-84
      timeout: 60
      reservedConcurrency: 5     # cap simultaneous workers -> bounded DB connections
```

Tune the cap against your CockroachDB connection budget and the queue's acceptable drain latency.

## Verifying the worker after deploy

1. Dispatch a test job from the `artisan` function: `osls bref:cli --args="tinker --execute=\"App\Jobs\Ping::dispatch()\""` (or a small command).
2. Confirm the SQS `jobs` queue shows messages received and then drained to zero.
3. Tail the worker log group in CloudWatch — expect a JSON line per processed job.
4. Force a failure and confirm the message lands on `jobs-dlq` and the alarm fires.

The full ordered deploy steps live in `deploy-checklist.md`.

## Anti-patterns

- **`queue:work` on Lambda.** There is no daemon. The construct's event-source mapping triggers the worker; a daemon would just idle and time out.
- **Horizon.** It requires Redis and a long-running process — the stack has neither. Use the DLQ + CloudWatch.
- **Worker on `php-84-fpm` or `php-84-console`.** The worker is an event handler: use the plain `php-84` runtime with `QueueHandler`.
- **Web and worker in one function.** Couples scaling, memory, and timeout. Keep three functions: web (`php-84-fpm`), worker (`php-84`), artisan (`php-84-console`).
- **Jobs longer than 60 s.** SQS redelivers and you double-process. Fan out, or move the work to a scheduled console command.
- **No DLQ alarm.** Without `alarm:` or an explicit CloudWatch alarm, failed jobs pile up on the DLQ silently.
- **Hardcoding the queue URL.** Use `${construct:<name>.queueUrl}` so the same file works across stages and accounts.
- **Database queue driver.** CockroachDB lacks `SKIP LOCKED`; the DB-queue driver will not work correctly. SQS only.
- **Unbounded worker concurrency.** A burst opens unbounded DB connections. Set `reservedConcurrency` on the worker.
- **A logical-only "queue" expected to have its own DLQ.** Routing to a queue name without a matching construct shares the default queue's DLQ and alarm. Create a construct per queue that needs isolation.
