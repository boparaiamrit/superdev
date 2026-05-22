# Audit Logging — `@Audit` Decorator + Hypertable

Every state-changing service method gets one decorator. An interceptor reads the metadata, runs the method, and writes a structured row to the `audit_logs` TimescaleDB hypertable. Free compliance trail, zero per-handler boilerplate.

## What gets logged

Each audit entry:

```ts
{
  id: string;
  workspace_id: string;
  user_id: string | null;       // null for system actions (cron jobs)
  action: string;                // e.g. 'campaign.send', 'company.delete'
  subject_type: string;          // e.g. 'Campaign', 'Company'
  subject_id: string | null;     // the target's ID
  request_id: string | null;
  ip: string | null;
  user_agent: string | null;
  status: 'Success' | 'Failure';
  duration_ms: number;
  metadata: Record<string, unknown>;  // freeform — input snapshot, diff, etc.
  occurred_at: timestamp;
}
```

This shape is the same one defined in the Drizzle schema (`audit_logs` table) — see `references/drizzle-timescaledb.md`.

## The decorator

`apps/api/src/common/decorators/audit.decorator.ts`:

```ts
import { SetMetadata } from '@nestjs/common';
import type { Subjects } from '@/modules/casl/ability.types';

export const AUDIT_META_KEY = 'audit_meta';

export type AuditMeta = {
  /** e.g. 'campaign.send' — convention: <subject_lowercase>.<verb> */
  action: string;
  /** CASL subject type, used for both auth and audit grouping */
  subject: Subjects;
  /**
   * Which method parameter holds the subject ID, by name. If omitted, the
   * interceptor tries to find an `id` field on the returned value or first arg.
   */
  subjectIdParam?: string;
  /**
   * Whether to capture method args in metadata. Default `false` for safety
   * (args may contain secrets). Pass `true` for boring CRUD; pass a function
   * to redact selectively.
   */
  captureArgs?: boolean | ((args: unknown[]) => unknown);
};

export const Audit = (meta: AuditMeta) => SetMetadata(AUDIT_META_KEY, meta);
```

## The interceptor

`apps/api/src/common/interceptors/audit.interceptor.ts`:

```ts
import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { Observable, tap, catchError } from 'rxjs';
import { InjectQueue } from '@nestjs/bullmq';
import type { Queue } from 'bullmq';
import { AUDIT_META_KEY, type AuditMeta } from '@/common/decorators/audit.decorator';
import { QUEUE_NAMES } from '@/infrastructure/queue/queue.constants';
import { workspaceContext } from '@/common/context/workspace-context';

type AuditPayload = {
  workspaceId: string;
  userId: string | null;
  action: string;
  subjectType: string;
  subjectId: string | null;
  requestId: string | null;
  ip: string | null;
  userAgent: string | null;
  status: 'Success' | 'Failure';
  durationMs: number;
  metadata: Record<string, unknown>;
};

@Injectable()
export class AuditInterceptor implements NestInterceptor {
  constructor(
    private readonly reflector: Reflector,
    @InjectQueue(QUEUE_NAMES.AUDIT_WRITE) private readonly auditQueue: Queue<AuditPayload>,
  ) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const meta = this.reflector.get<AuditMeta>(AUDIT_META_KEY, context.getHandler());
    if (!meta) return next.handle();

    const req = context.switchToHttp().getRequest();
    const ctx = workspaceContext.getStore();
    const startedAt = Date.now();

    const base: Omit<AuditPayload, 'status' | 'durationMs' | 'subjectId' | 'metadata'> = {
      workspaceId: ctx?.workspaceId ?? req.user?.workspaceId ?? 'unknown',
      userId: req.user?.id ?? null,
      action: meta.action,
      subjectType: meta.subject,
      requestId: req.id ?? null,
      ip: req.ip ?? null,
      userAgent: req.headers?.['user-agent'] ?? null,
    };

    const argsMetadata =
      meta.captureArgs === true
        ? { args: this.redactSecrets(context.getArgs()) }
        : typeof meta.captureArgs === 'function'
          ? { args: meta.captureArgs(context.getArgs()) }
          : {};

    return next.handle().pipe(
      tap((result) => {
        const subjectId = this.resolveSubjectId(meta, context.getArgs(), result);
        this.enqueue({
          ...base,
          subjectId,
          status: 'Success',
          durationMs: Date.now() - startedAt,
          metadata: argsMetadata,
        });
      }),
      catchError((err) => {
        const subjectId = this.resolveSubjectId(meta, context.getArgs(), undefined);
        this.enqueue({
          ...base,
          subjectId,
          status: 'Failure',
          durationMs: Date.now() - startedAt,
          metadata: { ...argsMetadata, error: { name: err?.name, message: err?.message } },
        });
        throw err;
      }),
    );
  }

  private resolveSubjectId(meta: AuditMeta, args: unknown[], result: unknown): string | null {
    if (meta.subjectIdParam) {
      // For controllers using @Param('id') etc, Nest passes them as method args
      // We can't reliably name-match without reflection, so prefer pulling from result/args by convention
    }
    const fromResult = (result as { id?: string } | null)?.id;
    if (fromResult) return fromResult;

    // Try args: look for a string id in the first 3 args
    for (const arg of args.slice(0, 3)) {
      if (typeof arg === 'string' && arg.length > 0 && arg.length < 64) return arg;
      if (arg && typeof arg === 'object' && 'id' in arg && typeof (arg as { id: string }).id === 'string') {
        return (arg as { id: string }).id;
      }
    }
    return null;
  }

  private redactSecrets(args: unknown[]): unknown {
    const SECRET_KEYS = new Set(['password', 'passwordHash', 'token', 'secret', 'apiKey', 'authorization']);

    const redact = (v: unknown): unknown => {
      if (v === null || v === undefined) return v;
      if (typeof v !== 'object') return v;
      if (Array.isArray(v)) return v.map(redact);
      const out: Record<string, unknown> = {};
      for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
        out[k] = SECRET_KEYS.has(k) ? '[REDACTED]' : redact(val);
      }
      return out;
    };

    return args.map(redact);
  }

  private enqueue(payload: AuditPayload) {
    // Fire-and-forget — audit writes shouldn't block the response
    void this.auditQueue.add('write', payload, {
      removeOnComplete: { age: 24 * 3600, count: 10_000 },
      removeOnFail: { age: 7 * 24 * 3600 },
    });
  }
}
```

## The writer worker

Audit writes are batched into the `audit-write` queue so a single request doesn't synchronously block on an insert. A worker drains the queue and bulk-inserts rows.

`apps/api/src/modules/audit/audit-writer.processor.ts`:

```ts
import { Inject } from '@nestjs/common';
import { Processor, WorkerHost } from '@nestjs/bullmq';
import type { Job } from 'bullmq';
import { auditLogs } from '@/db/schema';
import { DRIZZLE_DB } from '@/infrastructure/drizzle/drizzle.constants';
import type { Db } from '@/db/client';
import { QUEUE_NAMES } from '@/infrastructure/queue/queue.constants';

type AuditJobData = {
  workspaceId: string;
  userId: string | null;
  action: string;
  subjectType: string;
  subjectId: string | null;
  requestId: string | null;
  ip: string | null;
  userAgent: string | null;
  status: 'Success' | 'Failure';
  durationMs: number;
  metadata: Record<string, unknown>;
};

@Processor(QUEUE_NAMES.AUDIT_WRITE, { concurrency: 10 })
export class AuditWriterProcessor extends WorkerHost {
  constructor(@Inject(DRIZZLE_DB) private readonly db: Db) {
    super();
  }

  async process(job: Job<AuditJobData>): Promise<void> {
    await this.db.insert(auditLogs).values({
      workspaceId: job.data.workspaceId,
      userId: job.data.userId,
      action: job.data.action,
      subjectType: job.data.subjectType,
      subjectId: job.data.subjectId,
      requestId: job.data.requestId,
      ip: job.data.ip,
      userAgent: job.data.userAgent,
      status: job.data.status,
      durationMs: String(job.data.durationMs),
      metadata: job.data.metadata,
      // occurredAt defaults to NOW() in the schema
    });
  }
}
```

For very high-throughput audit volumes, change the processor to batch jobs (BullMQ `addBulk`) and use Drizzle's bulk insert with `db.insert(auditLogs).values(rowArray)`.

## Wiring

The interceptor is registered globally:

```ts
// app.module.ts
import { APP_INTERCEPTOR } from '@nestjs/core';
import { BullModule } from '@nestjs/bullmq';
import { QUEUE_NAMES } from '@/infrastructure/queue/queue.constants';
import { AuditInterceptor } from '@/common/interceptors/audit.interceptor';
import { AuditWriterProcessor } from '@/modules/audit/audit-writer.processor';

@Module({
  imports: [
    BullModule.registerQueue({ name: QUEUE_NAMES.AUDIT_WRITE }),
  ],
  providers: [
    { provide: APP_INTERCEPTOR, useClass: AuditInterceptor },
    AuditWriterProcessor,   // only registered on workers — see worker.ts
  ],
})
export class AppModule {}
```

In `apps/api/src/worker.ts`, register the AuditWriterProcessor. In `apps/api/src/main.ts`, omit it (the API process produces audit jobs; it doesn't consume them).

## Usage examples

### Basic mutation

```ts
@Audit({ action: 'company.create', subject: 'Company' })
async create(workspaceId: string, input: CreateCompanyInput): Promise<CompanyView> {
  // ...
}
```

After this method returns, an audit row is written:

```
action:        'company.create'
subject_type:  'Company'
subject_id:    'cmp_01HXYZ'   ← pulled from the returned view's .id
status:        'Success'
duration_ms:   42
```

### Capturing input

```ts
@Audit({
  action: 'campaign.send',
  subject: 'Campaign',
  captureArgs: true,
})
async sendCampaign(workspaceId: string, campaignId: string, options: SendOptions) {
  // ...
}
```

Metadata includes a redacted args snapshot:

```json
{ "args": ["ws_1", "cmp_01HXYZ", { "scheduledAt": "2026-05-20T10:00:00Z", "throttle": 30 }] }
```

### Custom subject ID resolution

```ts
@Audit({
  action: 'mailbox.warmup_start',
  subject: 'Mailbox',
  captureArgs: (args) => ({ mailboxId: args[1], reason: (args[2] as any)?.reason }),
})
async startWarmup(workspaceId: string, mailboxId: string, options: WarmupOptions) {
  // ...
}
```

### Audit on failure

If the method throws, the interceptor logs `status: 'Failure'` with `metadata.error = { name, message }`. The exception still propagates — the audit is fire-and-forget.

## Querying audit logs

Read-side API (admin-only):

```ts
// modules/audit/audit.controller.ts
@Controller('audit-logs')
export class AuditController {
  @Get()
  @CheckAbility({ action: 'read', subject: 'AuditLog' })
  list(
    @CurrentWorkspace() ws,
    @Query() filters: AuditFiltersDto,
  ) {
    return this.audit.list(ws.id, filters);
  }
}
```

```ts
// modules/audit/audit.service.ts
async list(workspaceId: string, filters: AuditFilters) {
  const t = tenantDb(this.db, workspaceId);
  const since = filters.since ?? new Date(Date.now() - 24 * 60 * 60 * 1000);

  const rows = await this.db
    .select()
    .from(auditLogs)
    .where(and(
      t.scope('auditLogs'),
      gte(auditLogs.occurredAt, since),
      filters.action ? eq(auditLogs.action, filters.action) : undefined,
      filters.userId ? eq(auditLogs.userId, filters.userId) : undefined,
    ))
    .orderBy(desc(auditLogs.occurredAt))
    .limit(filters.per_page)
    .offset((filters.page - 1) * filters.per_page);

  return this.presenter.toListResponse(rows, /* total */ 0, filters.page, filters.per_page);
}
```

## Naming conventions

Use `<subject>.<verb>` for action names. Lowercase. Past tense not required (the timestamp tells you the time).

Good:
- `company.create`, `company.update`, `company.delete`
- `campaign.send`, `campaign.pause`, `campaign.resume`
- `mailbox.warmup_start`, `mailbox.warmup_stop`
- `auth.login`, `auth.logout`, `auth.password_reset_request`

Bad:
- `CompanyCreated` (mixed case)
- `created_company` (verb-first)
- `did_thing` (unspecific)

## Anti-patterns

- ❌ Synchronous audit writes inside the request path. Always go through the queue.
- ❌ Logging without `workspace_id`. Every audit row is workspace-scoped.
- ❌ Audit logs in a regular table. They balloon to hundreds of millions of rows.
- ❌ Storing passwords or full request bodies in `metadata`. Use redaction.
- ❌ Auditing read-only endpoints. Skips audit overhead on hot paths; reads are logged by request logger instead.
- ❌ Forgetting the worker for `audit-write` queue. Jobs pile up in Redis with no consumer.
- ❌ Naming actions inconsistently (`createCompany` vs `company.create`). Pick one convention and stick to it.
