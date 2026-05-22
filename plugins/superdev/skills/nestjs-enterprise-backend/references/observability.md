# Observability

Logging, metrics, health, tracing. Read in Phase 3 (initial wiring) and at production-readiness review.

## Logging — Pino with workspace + request context

Pino is already configured in scaffolding via `nestjs-pino`. The defaults:

- JSON output in production, pretty-printed in dev
- `pino-http` middleware adds a `req.id` to every request
- `genReqId` honors an inbound `x-request-id` header, generates UUID otherwise

### Adding workspace and user context

Augment the `LoggerModule` to enrich every log line with workspace + user IDs:

`apps/api/src/infrastructure/logger/logger.module.ts`:

```ts
import { Module } from '@nestjs/common';
import { LoggerModule as PinoLoggerModule } from 'nestjs-pino';
import { randomUUID } from 'node:crypto';

@Module({
  imports: [
    PinoLoggerModule.forRoot({
      pinoHttp: {
        level: process.env.NODE_ENV === 'production' ? 'info' : 'debug',
        genReqId: (req) => (req.headers['x-request-id'] as string) ?? randomUUID(),
        autoLogging: {
          ignore: (req) => req.url === '/health' || req.url === '/metrics',
        },
        customProps: (req: any) => ({
          requestId: req.id,
          workspaceId: req.user?.workspaceId ?? null,
          userId: req.user?.id ?? null,
        }),
        serializers: {
          req: (req) => ({ id: req.id, method: req.method, url: req.url }),
          res: (res) => ({ statusCode: res.statusCode }),
          err: (err) => ({ name: err.name, message: err.message, stack: err.stack, code: err.code }),
        },
        transport:
          process.env.NODE_ENV === 'production'
            ? undefined
            : { target: 'pino-pretty', options: { singleLine: true, colorize: true } },
      },
    }),
  ],
})
export class LoggerModule {}
```

`customProps` runs per-request, so every log line emitted during a request automatically carries `workspaceId`, `userId`, `requestId`. Filter logs in Datadog/Logflare/whatever by `workspaceId="ws_X"` to debug one tenant in isolation.

### Using the logger in services

Inject `PinoLogger`:

```ts
import { Injectable } from '@nestjs/common';
import { PinoLogger, InjectPinoLogger } from 'nestjs-pino';

@Injectable()
export class CampaignsService {
  constructor(@InjectPinoLogger(CampaignsService.name) private readonly logger: PinoLogger) {}

  async send(workspaceId: string, campaignId: string) {
    this.logger.info({ campaignId }, 'Send started');
    try {
      const result = await this.doSend(workspaceId, campaignId);
      this.logger.info({ campaignId, jobsEnqueued: result.enqueued }, 'Send queued');
      return result;
    } catch (err) {
      this.logger.error({ err, campaignId }, 'Send failed');
      throw err;
    }
  }
}
```

Conventions:
- First arg is an object of context fields, second is the human message
- Use `err` key for errors (pino's default serializer picks it up)
- Don't include `workspaceId` or `userId` — automatic via `customProps`

### Log levels

- **`error`** — caught exception, failed integration, anything PagerDuty-worthy
- **`warn`** — rate limit hit, retry exhausted, deprecation, slow query
- **`info`** — major lifecycle events (send started, campaign created)
- **`debug`** — verbose state for local debugging; disabled in prod
- **`trace`** — never used in app code

## Metrics — Prometheus

Already installed in scaffolding (`@willsoto/nestjs-prometheus`). Mount `/metrics`:

`apps/api/src/main.ts`:

```ts
// PrometheusModule.register() is in app.module.ts; the route auto-mounts at /metrics
```

### Default metrics

`prom-client` ships defaults: `process_cpu_seconds_total`, `nodejs_eventloop_lag_seconds`, `http_requests_total`, etc. Already on.

### Custom application metrics

Define counters/histograms per concern. Inject and increment in services.

`apps/api/src/infrastructure/metrics/metrics.providers.ts`:

```ts
import { makeCounterProvider, makeHistogramProvider, makeGaugeProvider } from '@willsoto/nestjs-prometheus';

export const metricsProviders = [
  makeCounterProvider({
    name: 'email_sent_total',
    help: 'Emails sent successfully',
    labelNames: ['workspace_id', 'mailbox_id', 'campaign_id'],
  }),
  makeCounterProvider({
    name: 'email_send_failed_total',
    help: 'Email send failures',
    labelNames: ['workspace_id', 'mailbox_id', 'reason'],
  }),
  makeHistogramProvider({
    name: 'job_duration_seconds',
    help: 'BullMQ job duration',
    labelNames: ['queue', 'status'],
    buckets: [0.05, 0.1, 0.5, 1, 2, 5, 10, 30, 60, 120],
  }),
  makeGaugeProvider({
    name: 'queue_depth',
    help: 'BullMQ queue depth (sampled)',
    labelNames: ['queue', 'state'],   // waiting | active | delayed | failed
  }),
  makeCounterProvider({
    name: 'ai_generations_total',
    help: 'AI generation invocations',
    labelNames: ['workspace_id', 'model', 'status'],
  }),
];
```

Register in `app.module.ts`:

```ts
import { metricsProviders } from '@/infrastructure/metrics/metrics.providers';

@Module({
  providers: [...metricsProviders],
})
```

Inject and use:

```ts
import { InjectMetric } from '@willsoto/nestjs-prometheus';
import type { Counter, Histogram } from 'prom-client';

@Injectable()
export class EmailSenderService {
  constructor(
    @InjectMetric('email_sent_total') private readonly sentCounter: Counter,
    @InjectMetric('email_send_failed_total') private readonly failCounter: Counter,
  ) {}

  async send(input: SendInput) {
    try {
      // ... do send
      this.sentCounter.inc({
        workspace_id: input.workspaceId,
        mailbox_id: input.mailboxId,
        campaign_id: input.campaignId ?? 'manual',
      });
    } catch (err) {
      this.failCounter.inc({
        workspace_id: input.workspaceId,
        mailbox_id: input.mailboxId,
        reason: this.classifyError(err),
      });
      throw err;
    }
  }
}
```

### Cardinality caution

Each unique label-value combination is a separate Prometheus time-series. **Do not** put `userId`, `requestId`, or `campaignId` in labels if they're high-cardinality. Workspace ID is usually fine (tens to thousands); user ID is not (tens of thousands to millions).

If you need per-entity counters, write them to a Postgres table or Redis hash, not Prometheus.

### Sampling queue depth

A periodic job samples queue state and updates gauges:

```ts
// modules/observability/queue-metrics.cron.ts
@Injectable()
export class QueueMetricsCron {
  constructor(
    @InjectMetric('queue_depth') private readonly depthGauge: Gauge,
    @InjectQueue(QUEUE_NAMES.EMAIL_SEND) private readonly emailSend: Queue,
    // ... inject every queue
  ) {}

  @Cron('*/30 * * * * *')   // every 30 seconds
  async sampleAll() {
    await this.sample('email-send', this.emailSend);
    // ...
  }

  private async sample(name: string, queue: Queue) {
    const counts = await queue.getJobCounts('waiting', 'active', 'delayed', 'failed');
    this.depthGauge.set({ queue: name, state: 'waiting' }, counts.waiting);
    this.depthGauge.set({ queue: name, state: 'active' },  counts.active);
    this.depthGauge.set({ queue: name, state: 'delayed' }, counts.delayed);
    this.depthGauge.set({ queue: name, state: 'failed' },  counts.failed);
  }
}
```

## Health and readiness

`@nestjs/terminus` powers `/health` (liveness) and `/readiness` (load-balancer readiness):

```ts
// apps/api/src/infrastructure/health/health.controller.ts
import { Controller, Get, Inject } from '@nestjs/common';
import { HealthCheck, HealthCheckService, HealthIndicatorResult } from '@nestjs/terminus';
import { Public } from '@/common/decorators/public.decorator';
import { DRIZZLE_DB } from '@/infrastructure/drizzle/drizzle.constants';
import type { Db } from '@/db/client';
import { sql } from 'drizzle-orm';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from '@/infrastructure/cache/cache.constants';

@Controller()
export class HealthController {
  constructor(
    private readonly health: HealthCheckService,
    @Inject(DRIZZLE_DB) private readonly db: Db,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  @Public()
  @Get('health')
  @HealthCheck()
  liveness() {
    // Just "is the process alive"
    return this.health.check([async () => ({ alive: { status: 'up' } }) as HealthIndicatorResult]);
  }

  @Public()
  @Get('readiness')
  @HealthCheck()
  readiness() {
    return this.health.check([
      async () => {
        try {
          await this.db.execute(sql`SELECT 1`);
          return { database: { status: 'up' } } as HealthIndicatorResult;
        } catch (e) {
          return { database: { status: 'down', error: (e as Error).message } } as HealthIndicatorResult;
        }
      },
      async () => {
        try {
          const pong = await this.redis.ping();
          return { redis: { status: pong === 'PONG' ? 'up' : 'down' } } as HealthIndicatorResult;
        } catch (e) {
          return { redis: { status: 'down', error: (e as Error).message } } as HealthIndicatorResult;
        }
      },
    ]);
  }
}
```

`/health` returns 200 if the process is alive. `/readiness` returns 200 only when DB + Redis + any other critical dep are reachable. Configure your load balancer to use `/readiness` for traffic gating, `/health` for restart decisions.

## Tracing (optional but recommended for production)

OpenTelemetry can be added later without code changes:

```bash
pnpm add @opentelemetry/sdk-node @opentelemetry/auto-instrumentations-node
```

`apps/api/src/tracing.ts`:

```ts
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';

const sdk = new NodeSDK({
  instrumentations: [getNodeAutoInstrumentations({
    '@opentelemetry/instrumentation-fs': { enabled: false },
  })],
});

sdk.start();
```

Import first in `main.ts`:

```ts
import './tracing';
import { NestFactory } from '@nestjs/core';
// ...
```

Auto-instrumentation covers HTTP, Postgres (via postgres-js), Redis, BullMQ producers/consumers. Export to your tracing backend (Tempo, Honeycomb, etc.) via standard OTEL_EXPORTER env vars.

## Logging the audit log too

The `@Audit` decorator already writes structured audit rows to `audit_logs`. **Do not also log them** — that's two systems answering the same question. The audit hypertable is the system of record; Pino logs are operational telemetry.

If you need to find an audit event in logs, search Pino by `requestId` — it'll appear via the AuditInterceptor's logging.

## Production checklist

- [ ] `/health` and `/readiness` both reachable; readiness fails when DB or Redis down
- [ ] `/metrics` exposes default + custom metrics
- [ ] Pino emits JSON in production
- [ ] Every log line has `requestId` and (when authenticated) `workspaceId`
- [ ] Queue depth gauge samples every 30s
- [ ] At least one alert configured (e.g., "queue waiting > 1000 for 5 min")
- [ ] Slow query log enabled on Postgres (`log_min_duration_statement = 1000`)
- [ ] Sentry or equivalent for unhandled exceptions
- [ ] OpenTelemetry tracing pipeline running (or explicitly deferred)

## Anti-patterns

- ❌ Console.log anywhere in code. Use the injected logger.
- ❌ String interpolation in log messages — `this.logger.info(\`User ${id} did X\`)`. Use structured fields: `this.logger.info({ userId: id }, 'User did X')`.
- ❌ High-cardinality labels in Prometheus (userId, requestId, ID-shaped strings).
- ❌ Liveness probes that check DB. A DB hiccup shouldn't restart the API.
- ❌ Health endpoints under auth. Make them `@Public()`; load balancers don't have JWTs.
- ❌ Logging request bodies verbatim. They may contain PII or secrets.
- ❌ Skipping queue-depth alerts. Silent queues fill silently until they OOM Redis.
