# BullMQ — Queues, Workers, Crons

How to structure async work, scheduled jobs, rate limiting, and the worker process. Read in Phase 6.

## Mental model

BullMQ replaces three traditional tools in one package:

1. **Job queues** — `email-send`, `ai-generate`, `import-csv`
2. **Repeatable jobs (crons)** — `daily-rollup-send-metrics @ 02:00 UTC`
3. **Workers** — the processes that consume both

All runs on Redis. The API process **produces** jobs. The worker process **consumes** them. Two separate processes — never run workers in the API process in production.

## Queue name constants

`apps/api/src/infrastructure/queue/queue.constants.ts`:

```ts
export const QUEUE_NAMES = {
  EMAIL_SEND:        'email-send',
  EMAIL_RECEIVE:     'email-receive',
  AI_GENERATE:       'ai-generate',
  AUDIT_WRITE:       'audit-write',
  IMPORT_CSV:        'import-csv',
  WEBHOOK_DISPATCH:  'webhook-dispatch',

  // Crons live in their own queue for clarity
  SCHEDULED_TASKS:   'scheduled-tasks',
} as const;

export type QueueName = (typeof QUEUE_NAMES)[keyof typeof QUEUE_NAMES];
```

## Registering queues

`apps/api/src/infrastructure/queue/queue.module.ts` already sets up the BullMQ root with default options (see `scaffolding.md`). Each feature module registers the queues it produces:

```ts
// modules/email/email.module.ts
import { BullModule } from '@nestjs/bullmq';
import { QUEUE_NAMES } from '@/infrastructure/queue/queue.constants';

@Module({
  imports: [
    BullModule.registerQueue({ name: QUEUE_NAMES.EMAIL_SEND }),
    BullModule.registerQueue({ name: QUEUE_NAMES.EMAIL_RECEIVE }),
  ],
  // ...
})
export class EmailModule {}
```

## Producer pattern

Producers live in feature services. They `add` jobs to queues.

```ts
// modules/campaigns/campaigns.service.ts
import { Inject, Injectable } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import type { Queue } from 'bullmq';
import { QUEUE_NAMES } from '@/infrastructure/queue/queue.constants';

type SendCampaignJobData = {
  workspaceId: string;
  campaignId: string;
  draftId: string;
  mailboxId: string;
  contactId: string;
  scheduledAt: string;
};

@Injectable()
export class CampaignsService {
  constructor(
    @InjectQueue(QUEUE_NAMES.EMAIL_SEND) private readonly emailSendQueue: Queue<SendCampaignJobData>,
  ) {}

  @Audit({ action: 'campaign.send', subject: 'Campaign' })
  async send(workspaceId: string, campaignId: string) {
    const drafts = await this.repo.listDraftsForCampaign(workspaceId, campaignId);

    const jobs = drafts.map((draft) => ({
      name: 'send-one',
      data: {
        workspaceId,
        campaignId,
        draftId: draft.id,
        mailboxId: draft.mailboxId,
        contactId: draft.contactId,
        scheduledAt: new Date().toISOString(),
      },
      opts: {
        // Idempotency: re-enqueueing the same draft is a no-op
        jobId: `send:${draft.id}`,
        // Stagger sends to respect per-mailbox rate limits
        delay: this.computeDelay(draft.mailboxId),
        attempts: 5,
        backoff: { type: 'exponential', delay: 60_000 },
      },
    }));

    await this.emailSendQueue.addBulk(jobs);
    return { enqueued: jobs.length };
  }

  private computeDelay(mailboxId: string): number {
    // Track per-mailbox cursor in Redis to enforce inter-send gaps
    // (See "Rate limiting" below for a richer approach)
    return 0;
  }
}
```

**Idempotent job IDs.** Passing `jobId` makes BullMQ deduplicate. Re-enqueueing the same `send:draft_123` returns the existing job instead of creating a duplicate. This is the cleanest defense against retry-storm double-sends.

## Worker pattern

Workers are decorated classes that extend `WorkerHost`. They register once per queue and Nest's DI provides services.

```ts
// modules/email/workers/email-send.worker.ts
import { Inject, Logger } from '@nestjs/common';
import { Processor, WorkerHost, OnWorkerEvent } from '@nestjs/bullmq';
import type { Job } from 'bullmq';
import { QUEUE_NAMES } from '@/infrastructure/queue/queue.constants';
import { EmailSenderService } from '../services/email-sender.service';
import { MailboxesService } from '@/modules/mailboxes/mailboxes.service';

type SendJobData = { /* same as producer's type */ };

@Processor(QUEUE_NAMES.EMAIL_SEND, {
  concurrency: 5,
  limiter: { max: 100, duration: 60_000 },  // global queue rate limit: 100 jobs/min
})
export class EmailSendWorker extends WorkerHost {
  private readonly logger = new Logger(EmailSendWorker.name);

  constructor(
    private readonly sender: EmailSenderService,
    private readonly mailboxes: MailboxesService,
  ) {
    super();
  }

  async process(job: Job<SendJobData>): Promise<void> {
    const { workspaceId, draftId, mailboxId, contactId } = job.data;

    // Enforce per-mailbox rate limit (track in Redis with cache-manager)
    const allowed = await this.mailboxes.tryConsumeSendCredit(mailboxId);
    if (!allowed) {
      // Re-schedule with delay; don't fail
      throw new Error('Mailbox rate limit hit'); // BullMQ will retry with backoff
    }

    await job.updateProgress(10);
    const draft = await this.sender.loadDraft(workspaceId, draftId);
    await job.updateProgress(40);

    const result = await this.sender.send(workspaceId, mailboxId, draft);
    await job.updateProgress(90);

    await this.sender.recordSent(workspaceId, {
      draftId,
      mailboxId,
      contactId,
      messageId: result.messageId,
      threadId: result.threadId,
      subject: draft.subject,
    });
    await job.updateProgress(100);
  }

  @OnWorkerEvent('completed')
  onCompleted(job: Job<SendJobData>) {
    this.logger.log({ jobId: job.id, draftId: job.data.draftId }, 'Send completed');
  }

  @OnWorkerEvent('failed')
  onFailed(job: Job<SendJobData> | undefined, err: Error) {
    this.logger.error({ jobId: job?.id, err: err.message }, 'Send failed');
    // Alerting hook: send to Slack/PagerDuty if attempts exhausted
    if (job && job.attemptsMade >= (job.opts.attempts ?? 1)) {
      // ... alert
    }
  }

  @OnWorkerEvent('stalled')
  onStalled(jobId: string) {
    this.logger.warn({ jobId }, 'Send stalled — worker likely crashed mid-job');
  }
}
```

### Where the worker lives in the module graph

Workers are registered in their feature module, but **only instantiated when the process is the worker process**. Use the `PROCESS_MODE` env var:

```ts
// modules/email/email.module.ts
import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { EmailController } from './email.controller';
import { EmailService } from './email.service';
import { EmailSendWorker } from './workers/email-send.worker';

const isWorker = process.env.PROCESS_MODE === 'worker';

@Module({
  controllers: isWorker ? [] : [EmailController],
  providers: [
    EmailService,
    ...(isWorker ? [EmailSendWorker] : []),
  ],
})
export class EmailModule {}
```

The API process never instantiates the worker (which would cause double-consumption). The worker process never registers controllers (which would expose duplicate HTTP routes if `main.ts` accidentally ran the worker module).

## Crons (repeatable jobs)

Crons are jobs that BullMQ re-enqueues on a schedule. Register them at module bootstrap.

```ts
// modules/scheduled-tasks/scheduled-tasks.module.ts
import { Module, OnApplicationBootstrap } from '@nestjs/common';
import { BullModule, InjectQueue } from '@nestjs/bullmq';
import type { Queue } from 'bullmq';
import { QUEUE_NAMES } from '@/infrastructure/queue/queue.constants';
import { WarmupStatusPollWorker } from './workers/warmup-status-poll.worker';
import { DailyRollupWorker } from './workers/daily-rollup.worker';
import { SlaWarningWorker } from './workers/sla-warning.worker';
// ...

const isWorker = process.env.PROCESS_MODE === 'worker';

@Module({
  imports: [BullModule.registerQueue({ name: QUEUE_NAMES.SCHEDULED_TASKS })],
  providers: isWorker
    ? [WarmupStatusPollWorker, DailyRollupWorker, SlaWarningWorker]
    : [],
})
export class ScheduledTasksModule implements OnApplicationBootstrap {
  constructor(@InjectQueue(QUEUE_NAMES.SCHEDULED_TASKS) private readonly queue: Queue) {}

  async onApplicationBootstrap() {
    // Register cron schedules — idempotent; safe to run on every boot
    await this.queue.upsertJobScheduler('warmup-status-poll', { pattern: '*/5 * * * *' }, { name: 'poll' });
    await this.queue.upsertJobScheduler('daily-rollup',       { pattern: '0 2 * * *' },   { name: 'rollup' });
    await this.queue.upsertJobScheduler('sla-warning-leads',  { pattern: '0 * * * *' },   { name: 'sla-check' });
    await this.queue.upsertJobScheduler('dns-health-check',   { pattern: '*/30 * * * *' },{ name: 'dns-check' });
    await this.queue.upsertJobScheduler('cleanup-drafts',     { pattern: '0 3 * * *' },   { name: 'cleanup' });
  }
}
```

The single worker for this queue dispatches by job name:

```ts
@Processor(QUEUE_NAMES.SCHEDULED_TASKS, { concurrency: 3 })
export class ScheduledTasksWorker extends WorkerHost {
  constructor(
    private readonly warmup: WarmupService,
    private readonly rollup: RollupService,
    private readonly sla: SlaService,
    private readonly dns: DnsHealthService,
    private readonly drafts: DraftCleanupService,
  ) {
    super();
  }

  async process(job: Job): Promise<void> {
    switch (job.name) {
      case 'poll':      return this.warmup.pollAll();
      case 'rollup':    return this.rollup.rollUpYesterday();
      case 'sla-check': return this.sla.warnStaleLeads();
      case 'dns-check': return this.dns.checkAllDomains();
      case 'cleanup':   return this.drafts.cleanupExpired();
      default:
        throw new Error(`Unknown scheduled job: ${job.name}`);
    }
  }
}
```

**Important:** crons need a `@Audit({ action: 'system.<task>', subject: 'all' })` decorator on each service method — or call the audit writer directly — so scheduled actions are traceable too.

## Rate limiting patterns

### Global queue rate limit (BullMQ built-in)

```ts
@Processor(QUEUE_NAMES.AI_GENERATE, {
  concurrency: 3,
  limiter: { max: 30, duration: 60_000 },  // 30 jobs per minute, queue-wide
})
```

### Per-key rate limit (e.g., per-workspace)

BullMQ doesn't have native per-key limits. Implement with a token-bucket in Redis:

```ts
// modules/ai/ai-rate-limiter.service.ts
import { Inject, Injectable } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from '@/infrastructure/cache/cache.constants';

@Injectable()
export class AiRateLimiter {
  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Returns true if the workspace has budget; consumes one unit.
   * Bucket: 10 generations per minute per workspace.
   */
  async tryConsume(workspaceId: string): Promise<boolean> {
    const key = `rl:ai:${workspaceId}`;
    const max = 10;
    const windowMs = 60_000;

    const current = await this.redis.incr(key);
    if (current === 1) {
      await this.redis.pexpire(key, windowMs);
    }
    return current <= max;
  }
}
```

In the worker:

```ts
async process(job: Job<AiGenerateJobData>) {
  const allowed = await this.limiter.tryConsume(job.data.workspaceId);
  if (!allowed) {
    // Defer rather than fail
    await job.moveToDelayed(Date.now() + 30_000);
    return;
  }
  // ... do work
}
```

### Per-mailbox sending limit

For email, the mailbox itself usually exposes a daily quota. Track per-mailbox counters in Redis with a rolling 24h window. Same pattern as above, different bucket key.

## Job priorities

Use `priority` (lower number = higher priority) when some jobs must jump the queue:

```ts
await this.emailSendQueue.add('send-one', data, {
  priority: isInitialReply ? 1 : 10,  // replies go first
  jobId: `send:${draft.id}`,
});
```

## Dead-letter handling

After `attempts` exhausted, BullMQ marks the job `failed`. A second queue serves as the dead-letter:

```ts
// In the failed event handler
@OnWorkerEvent('failed')
async onFailed(job: Job | undefined, err: Error) {
  if (!job || job.attemptsMade < (job.opts.attempts ?? 1)) return;

  // Permanent failure — move to dead-letter queue for manual inspection
  await this.deadLetterQueue.add('failed-send', {
    originalQueue: QUEUE_NAMES.EMAIL_SEND,
    originalJobId: job.id,
    data: job.data,
    error: { name: err.name, message: err.message },
    failedAt: new Date().toISOString(),
  });

  // Alert
  this.alerts.send({ severity: 'high', message: `Send failed permanently: ${err.message}` });
}
```

## Worker process bootstrap

`apps/api/src/worker.ts` (already shown in scaffolding):

```ts
import { NestFactory } from '@nestjs/core';
import { Logger } from 'nestjs-pino';
import { AppModule } from './app.module';

async function bootstrap() {
  process.env.PROCESS_MODE = 'worker';
  const app = await NestFactory.createApplicationContext(AppModule, { bufferLogs: true });
  app.useLogger(app.get(Logger));

  // Graceful shutdown — let in-flight jobs finish
  process.on('SIGTERM', async () => {
    await app.close();
    process.exit(0);
  });
  process.on('SIGINT', async () => {
    await app.close();
    process.exit(0);
  });

  console.log('Worker started; consuming queues');
}

bootstrap();
```

In production, deploy `main.ts` and `worker.ts` as separate processes (e.g., on Render/Railway: a `web` service + a `worker` service from the same image, different start commands).

## Observability

Each queue gets:

- A Prometheus counter for completed/failed jobs (label: queue name, status)
- A histogram for job duration
- A gauge for queue depth (sampled every 30s)

See `references/observability.md`.

## Anti-patterns

- ❌ Running workers in the API process. Slow jobs OOM the API; one shared event loop.
- ❌ Synchronous heavy work in a controller. Enqueue and return 202.
- ❌ No `jobId` for idempotent operations. Retry storms cause double-sends.
- ❌ No retry limits. Jobs retry forever; redis fills up.
- ❌ No dead-letter handling. Failures vanish silently.
- ❌ Hardcoding cron expressions in services. Centralize in `ScheduledTasksModule` so the schedule is auditable in one place.
- ❌ Worker without `@OnWorkerEvent('failed')`. Failures go unlogged.
- ❌ Inline rate-limit math everywhere. Centralize in a `RateLimiter` service per concern.
- ❌ Forgetting `@Audit` on cron handlers. Scheduled actions need audit trails too.
