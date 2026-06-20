# SQS Queues — Jobs, Dispatch, Idempotency, DLQ

How to structure async work and scheduled commands on SQS. The app-side companion to the deployer's `sqs-worker.md`. Read in Phase 6.

## Mental model

On Bref serverless there is no long-running `queue:work` daemon and no Horizon. The queue layer is:

1. **Jobs** — PHP classes implementing `ShouldQueue`; the app **dispatches** them to SQS.
2. **Worker Lambda** — a separate `php-84` function running `Bref\LaravelBridge\Queue\QueueHandler`; AWS triggers it when messages arrive. Configured in the deployer skill (`laravel-bref-deploy/references/sqs-worker.md`).
3. **Crons** — Laravel scheduler entries in `routes/console.php`; EventBridge fires `schedule:run` every minute on the console Lambda (see `laravel-bref-deploy/references/scheduler-eventbridge.md`).

SQS delivers at-least-once. Every job must be **idempotent**. No Redis. No Horizon.

Laravel equivalent of BullMQ: `QUEUE_CONNECTION=sqs` + `aws/aws-sdk-php` + Bref `QueueHandler`. No `queue:work` needed.

> **Why SQS and not the database queue driver?** On real Postgres the `database` driver is technically viable — `SKIP LOCKED` works, and there is no longer any DB-level blocker. SQS is still the right choice here because Bref Lambda cannot run a long-lived `queue:work` daemon. SQS integrates natively with Lambda event-source mappings: AWS invokes the worker function per message batch, no polling process required.

## Install

```bash
composer require aws/aws-sdk-php
```

`aws/aws-sdk-php` is the only runtime dependency needed. No Laravel-specific SQS package; the framework ships SQS support in the `Illuminate\Queue\SqsQueue` driver.

> Package-size note: `aws/aws-sdk-php` is large. After installing, audit `vendor/` size and use `--no-dev` on deploy. The deployer skill's `deploy-checklist.md` covers keeping the package under 250 MB.

## Configuration

### `.env.example`

```bash
QUEUE_CONNECTION=sqs
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
SQS_PREFIX=https://sqs.us-east-1.amazonaws.com/123456789012
SQS_QUEUE=default
# On Lambda the worker reads SQS_QUEUE from ${construct:jobs.queueUrl} (set in serverless.yml)
# No REDIS_* variables — not used
```

### `config/queue.php` — SQS connection block

```php
// config/queue.php
'default' => env('QUEUE_CONNECTION', 'sqs'),

'connections' => [

    'sqs' => [
        'driver'      => 'sqs',
        'key'         => env('AWS_ACCESS_KEY_ID'),
        'secret'      => env('AWS_SECRET_ACCESS_KEY'),
        'prefix'      => env('SQS_PREFIX', 'https://sqs.us-east-1.amazonaws.com/your-account-id'),
        'queue'        => env('SQS_QUEUE', 'default'),
        'suffix'       => env('SQS_SUFFIX'),
        'region'       => env('AWS_DEFAULT_REGION', 'us-east-1'),
        'after_commit' => false,
    ],

],
```

The `prefix` + `queue` name together form the full queue URL that AWS needs. On Lambda, the deployer's `serverless-lift` construct injects the real URL via `SQS_QUEUE=${construct:jobs.queueUrl}`.

## Queue name constants

Centralise queue names so dispatch and the worker reference the same string.

```php
// app/Queue/QueueNames.php
namespace App\Queue;

final class QueueNames
{
    const DEFAULT       = 'default';
    const AUDIT         = 'audit';       // AuditWrite jobs — see audit-attribute.md
    const EMAIL_SEND    = 'email-send';
    const AI_GENERATE   = 'ai-generate';
    const IMPORT_CSV    = 'import-csv';
    const WEBHOOK       = 'webhook-dispatch';
}
```

Multiple SQS queues require a corresponding construct in `serverless.yml` (one `type: queue` per logical queue). The deployer skill manages that wiring; this file covers the app side.

## Writing a job

Jobs implement `ShouldQueue` and use the standard Laravel traits.

```php
// app/Jobs/SendCampaignEmail.php
namespace App\Jobs;

use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use App\Queue\QueueNames;

class SendCampaignEmail implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    /**
     * Idempotency key — derived from the unique business entity so re-dispatching
     * the same draft is safe under at-least-once delivery.
     */
    public string $jobId;

    /**
     * Maximum attempts before the job is sent to the DLQ.
     * Keep well under the 15-minute Lambda cap (see "Time budget" below).
     */
    public int $tries = 5;

    /**
     * Exponential backoff: 1s, 2s, 4s, 8s, 16s.
     */
    public array $backoff = [1, 2, 4, 8, 16];

    public function __construct(
        public readonly string $workspaceId,
        public readonly string $campaignId,
        public readonly string $draftId,
        public readonly string $mailboxId,
        public readonly string $contactId,
    ) {
        // Stable job ID derived from the business entity.
        // If this exact message is delivered twice, handle() is idempotent (see below).
        $this->jobId = "send:{$this->draftId}";
    }

    public function handle(): void
    {
        // Idempotency guard: if the draft was already sent, bail cleanly.
        if (\App\Models\SentEmail::where('draft_id', $this->draftId)->exists()) {
            return;
        }

        app(\App\Services\EmailSenderService::class)->send(
            workspaceId: $this->workspaceId,
            draftId:     $this->draftId,
            mailboxId:   $this->mailboxId,
            contactId:   $this->contactId,
        );
    }
}
```

## Dispatching jobs

```php
// From a service — dispatch to a named queue
use App\Jobs\SendCampaignEmail;
use App\Queue\QueueNames;

SendCampaignEmail::dispatch(
    workspaceId: $workspace->id,
    campaignId:  $campaign->id,
    draftId:     $draft->id,
    mailboxId:   $draft->mailbox_id,
    contactId:   $draft->contact_id,
)->onQueue(QueueNames::EMAIL_SEND);

// Bulk dispatch — build a batch array then dispatch each
// (SQS does not support BullMQ-style addBulk; use a loop or Bus::batch)
$jobs = $drafts->map(fn ($d) => new SendCampaignEmail(
    workspaceId: $workspaceId,
    campaignId:  $campaignId,
    draftId:     $d->id,
    mailboxId:   $d->mailbox_id,
    contactId:   $d->contact_id,
));

Bus::batch($jobs)->onQueue(QueueNames::EMAIL_SEND)->dispatch();
```

## Idempotency — at-least-once delivery

SQS guarantees at-least-once delivery. A message may be received more than once (e.g., after a timeout or a Lambda cold-start restart). Every job must be safe to run twice.

Three patterns in order of preference:

**1. Natural idempotency (best):** the operation is a pure insert keyed on a business ID. If the row already exists, `INSERT … ON CONFLICT DO NOTHING` or a guard check at the top of `handle()`.

**2. Idempotency table (reliable):** insert a deduplication key before doing work; skip if it already exists.

```php
// app/Jobs/ImportCsvRow.php — idempotency via a dedupe record
public function handle(): void
{
    $key = "import:{$this->importId}:row:{$this->rowIndex}";

    $inserted = \DB::table('job_deduplication')
        ->insertOrIgnore(['key' => $key, 'processed_at' => now()]);

    if ($inserted === 0) {
        return; // already processed
    }

    // ... do the actual import work
}
```

**3. Stable `$jobId` property (lightweight):** set a deterministic `$jobId` on the job object. Laravel serialises it into the SQS message; the `QueueHandler` uses it to detect exact-duplicate messages in the same Lambda invocation. This does not deduplicate across separate SQS deliveries — combine with one of the patterns above for true idempotency.

## Time budget — jobs must finish in < 60 s

The SQS `VisibilityTimeout` for the Bref-managed queue is 60 s. If `handle()` does not return within that window, SQS makes the message visible again and another Lambda picks it up. Lambda itself can run for up to 15 minutes, but the queue contract is 60 s.

Rules:
- Break large fan-out work into smaller jobs dispatched from within a parent job (chain or batch).
- Stream-process large files in chunks; never load a full dataset into memory.
- Set explicit HTTP timeouts on any outbound API call (< 30 s).
- If a task genuinely requires more time, use the artisan console Lambda with a dedicated EventBridge trigger instead of an SQS job.

```php
// app/Jobs/ProcessLargeImport.php — fan-out pattern
public function handle(): void
{
    // Each chunk becomes its own small job
    \App\Models\ImportRow::where('import_id', $this->importId)
        ->where('processed', false)
        ->chunkById(100, function ($rows) {
            foreach ($rows as $row) {
                ImportCsvRow::dispatch($this->importId, $row->index, $row->data)
                    ->onQueue(QueueNames::IMPORT_CSV);
            }
        });
}
```

## The `audit` queue

`AuditWrite` jobs are dispatched on the dedicated `audit` queue (see `audit-attribute.md`):

```php
// From AuditManager — dispatched automatically; never dispatch AuditWrite directly
\App\Jobs\AuditWrite::dispatch($row)->onQueue(QueueNames::AUDIT);
```

Keep the audit queue separate from business queues so a spike in auditing never delays user-facing operations. The deployer skill provisions a separate SQS construct for it.

## Failed jobs and the DLQ

When a job exhausts all attempts (`$tries`) or throws a non-retryable exception, it lands on the **Dead Letter Queue** (DLQ). The deployer's `serverless-lift` construct creates the DLQ automatically — one DLQ per `type: queue` construct.

On the app side, implement `failed()` to log the permanent failure:

```php
// app/Jobs/SendCampaignEmail.php
public function failed(\Throwable $exception): void
{
    \Log::error('SendCampaignEmail permanently failed', [
        'draft_id'    => $this->draftId,
        'workspace_id'=> $this->workspaceId,
        'error'       => $exception->getMessage(),
    ]);

    // Optionally notify ops (Slack, PagerDuty) if the job is business-critical
}
```

CloudWatch alarms on the DLQ `ApproximateNumberOfMessagesVisible` metric are configured in the deployer skill. There is no Horizon dashboard; use CloudWatch Logs Insights to inspect failures.

To mark a job as permanently failed without retrying (e.g., a validation failure that can never succeed):

```php
public function handle(): void
{
    if (! $this->isValid()) {
        $this->fail(new \RuntimeException('Unrecoverable validation failure'));
        return;
    }
    // ...
}
```

## Crons — Laravel scheduler via EventBridge

Cron schedules live in `routes/console.php`, not in jobs. EventBridge fires the artisan console Lambda with `schedule:run` every minute.

```php
// routes/console.php
use Illuminate\Support\Facades\Schedule;

// Daily rollup metrics
Schedule::command('metrics:rollup')->dailyAt('02:00')->withoutOverlapping();

// SLA warnings for stale leads
Schedule::command('leads:warn-stale')->hourly()->withoutOverlapping();

// DNS health checks
Schedule::command('domains:check-dns')->everyThirtyMinutes()->withoutOverlapping();
```

Rules for scheduled commands:
- Always use `->withoutOverlapping()` — EventBridge fires every minute; the command must not run concurrently with itself if it takes > 1 minute.
- Keep each command under 12 minutes (Lambda artisan timeout is 720 s in the deployer's `serverless.yml`).
- If a command dispatches further SQS jobs, keep the command itself fast (< 30 s) — the heavy work belongs in the jobs.
- Scheduled commands that mutate data should go through `AuditManager` so actions are traceable (see `audit-attribute.md`).

Cross-reference: `laravel-bref-deploy/references/scheduler-eventbridge.md` for the EventBridge + console-Lambda wiring.

## Typical queues in a CRM-style app

| Queue constant | Purpose | `$tries` | Notes |
|---|---|---|---|
| `default` | General-purpose fallback | 3 | Catch-all |
| `audit` | `AuditWrite` rows | 5 | High-volume; separate from business queues |
| `email-send` | Transactional / campaign emails | 5 | Idempotent on `draft_id` |
| `ai-generate` | LLM API calls | 3 | Long tail latency; monitor DLQ closely |
| `import-csv` | Row-level import chunks | 3 | Fan-out from a parent job |
| `webhook-dispatch` | Outbound webhooks | 5 | Exponential backoff; idempotent on `event_id` |

## Anti-patterns

- Running `queue:work` on Lambda. SQS jobs are triggered by the event source mapping in `serverless.yml`; there is no daemon.
- Horizon. It requires Redis, which the stack does not use.
- Jobs that run longer than 60 s. SQS will redeliver the message and cause double-processing. Fan out instead.
- No idempotency guard. At-least-once delivery means `handle()` will occasionally run twice — always guard with a business-key check or an idempotency table.
- No `failed()` method. Permanent failures vanish silently without it.
- Dispatching `AuditWrite` directly from a controller. It must flow through `AuditManager::run()` so timing, workspace context, and `Success`/`Failure` status are captured correctly.
- Forgetting `->onQueue(...)` on dispatch. Without it the job goes to the queue named in `SQS_QUEUE` (the `default` queue) even if a dedicated queue exists for that job type.
- Hardcoding queue names as strings. Use `QueueNames` constants so queue names are auditable in one place.
- Cron schedules registered as BullMQ-style repeatable jobs. Laravel crons belong in `routes/console.php`; the EventBridge trigger in the deployer skill handles the tick.
