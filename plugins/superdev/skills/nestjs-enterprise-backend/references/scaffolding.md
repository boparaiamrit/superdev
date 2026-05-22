# Scaffolding `apps/api`

Run this in Phase 3, after `references/monorepo-setup.md` has set up the workspace + `packages/contracts`. Goal: a Nest.js app booting with all infrastructure in place, Drizzle migrated, `/health` returning green.

## Step 1 — Create the app

From the monorepo root:

```bash
mkdir -p apps/api && cd apps/api
pnpm dlx @nestjs/cli new . --strict --package-manager pnpm --skip-git
```

Override `apps/api/package.json` afterward to use workspace deps:

```json
{
  "name": "@<scope>/api",
  "version": "0.0.0",
  "private": true,
  "scripts": {
    "build": "nest build",
    "start:dev": "PROCESS_MODE=api nest start --watch",
    "worker:dev": "PROCESS_MODE=worker tsx watch src/worker.ts",
    "start:prod": "PROCESS_MODE=api node dist/main.js",
    "worker:prod": "PROCESS_MODE=worker node dist/worker.js",
    "typecheck": "tsc --noEmit",
    "lint": "eslint \"src/**/*.ts\" --fix",
    "test": "jest",
    "test:e2e": "jest --config ./test/jest-e2e.json",
    "db:generate": "drizzle-kit generate",
    "db:migrate": "tsx src/db/migrate.ts",
    "db:custom": "tsx src/db/apply-custom.ts",
    "db:seed": "tsx src/db/seed.ts",
    "db:studio": "drizzle-kit studio"
  },
  "dependencies": {
    "@<scope>/contracts": "workspace:*"
  },
  "devDependencies": {
    "@<scope>/tsconfig": "workspace:*",
    "@<scope>/eslint-config": "workspace:*"
  }
}
```

## Step 2 — Install runtime dependencies

```bash
pnpm add \
  @nestjs/config \
  @nestjs/jwt \
  @nestjs/passport \
  @nestjs/swagger \
  @nestjs/terminus \
  @nestjs/throttler \
  @nestjs/bullmq \
  @nestjs/cache-manager \
  bullmq \
  ioredis \
  drizzle-orm \
  postgres \
  @paralleldrive/cuid2 \
  @casl/ability \
  cache-manager \
  cache-manager-redis-yet \
  argon2 \
  passport \
  passport-jwt \
  pino \
  nestjs-pino \
  pino-http \
  pino-pretty \
  nestjs-zod \
  zod \
  date-fns \
  ms \
  @willsoto/nestjs-prometheus \
  prom-client \
  helmet \
  cookie-parser
```

## Step 3 — Install dev dependencies

```bash
pnpm add -D \
  drizzle-kit \
  tsx \
  @types/passport-jwt \
  @types/cookie-parser \
  @types/ms
```

## Step 4 — Docker Compose for local services

> **Monorepo note:** When this skill runs inside the `prd-design-build-orchestrator`, the `docker-compose.yml` lives at the **monorepo root**, not inside `apps/api/`. The `monorepo-bootstrapper` agent owns it. The compose content shown below is the same — just placed one level up. All infra deps (Postgres+Timescale, Redis, and any project-specific extras like Mailpit or MinIO) live in that single root-level file.

`apps/api/docker-compose.yml` (standalone skill use) / `docker-compose.yml` at root (monorepo use):

```yaml
services:
  postgres:
    image: timescale/timescaledb:latest-pg17
    container_name: <workspace>_postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: <app>_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: <workspace>_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD-SHELL", "redis-cli ping | grep PONG"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  postgres_data:
  redis_data:
```

Boot: `docker compose up -d`.

`timescale/timescaledb:latest-pg17` is Postgres 17 with the TimescaleDB extension pre-installed. The `CREATE EXTENSION` call is in `src/db/apply-custom.ts`.

## Step 5 — Env schema

`apps/api/src/infrastructure/config/env.schema.ts`:

```ts
import { z } from 'zod';

export const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'staging', 'production']).default('development'),
  PROCESS_MODE: z.enum(['api', 'worker']).default('api'),
  PORT: z.coerce.number().int().positive().default(3001),
  API_PREFIX: z.string().default('v1'),

  // Database
  DATABASE_URL: z.string().url(),

  // Redis
  REDIS_URL: z.string().url().default('redis://localhost:6379'),
  REDIS_DB_CACHE: z.coerce.number().int().min(0).max(15).default(0),
  REDIS_DB_QUEUE: z.coerce.number().int().min(0).max(15).default(1),

  // JWT
  JWT_ACCESS_SECRET: z.string().min(32),
  JWT_ACCESS_TTL: z.string().default('15m'),
  JWT_REFRESH_SECRET: z.string().min(32),
  JWT_REFRESH_TTL: z.string().default('30d'),

  // CORS
  CORS_ORIGIN: z.string().default('http://localhost:3000'),

  // Integrations
  INBOXKIT_BEARER: z.string().optional(),
  INBOXKIT_WORKSPACE_ID: z.string().optional(),
  ANTHROPIC_API_KEY: z.string().optional(),
});

export type Env = z.infer<typeof envSchema>;
```

## Step 6 — Config module

`apps/api/src/infrastructure/config/config.module.ts`:

```ts
import { Global, Module } from '@nestjs/common';
import { ConfigModule as NestConfigModule } from '@nestjs/config';
import { envSchema } from './env.schema';
import { TypedConfigService } from './config.service';

@Global()
@Module({
  imports: [
    NestConfigModule.forRoot({
      isGlobal: true,
      validate: (raw) => {
        const parsed = envSchema.safeParse(raw);
        if (!parsed.success) {
          console.error('❌ Invalid environment variables:', parsed.error.flatten().fieldErrors);
          process.exit(1);
        }
        return parsed.data;
      },
    }),
  ],
  providers: [TypedConfigService],
  exports: [TypedConfigService],
})
export class ConfigModule {}
```

`apps/api/src/infrastructure/config/config.service.ts`:

```ts
import { Injectable } from '@nestjs/common';
import { ConfigService as NestConfigService } from '@nestjs/config';
import type { Env } from './env.schema';

@Injectable()
export class TypedConfigService {
  constructor(private readonly nest: NestConfigService<Env, true>) {}

  get<K extends keyof Env>(key: K): Env[K] {
    return this.nest.get(key, { infer: true });
  }
}
```

`process.env.X` is forbidden everywhere except this module. Inject `TypedConfigService`.

## Step 7 — Drizzle setup

`apps/api/drizzle.config.ts`:

```ts
import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  schema: './src/db/schema/index.ts',
  out: './drizzle',
  dialect: 'postgresql',
  dbCredentials: { url: process.env.DATABASE_URL! },
  casing: 'snake_case',
  verbose: true,
  strict: true,
});
```

`apps/api/src/db/client.ts`:

```ts
import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema';

const queryClient = postgres(process.env.DATABASE_URL!, {
  max: 20,
  idle_timeout: 30,
  connect_timeout: 10,
});

export const db = drizzle(queryClient, { schema, casing: 'snake_case' });
export type Db = typeof db;
```

`apps/api/src/infrastructure/drizzle/drizzle.constants.ts`:

```ts
export const DRIZZLE_DB = Symbol('DRIZZLE_DB');
```

`apps/api/src/infrastructure/drizzle/drizzle.module.ts`:

```ts
import { Global, Module } from '@nestjs/common';
import { DRIZZLE_DB } from './drizzle.constants';
import { db } from '@/db/client';

@Global()
@Module({
  providers: [{ provide: DRIZZLE_DB, useValue: db }],
  exports: [DRIZZLE_DB],
})
export class DrizzleModule {}
```

`apps/api/src/db/schema/index.ts` starts as empty re-exports — feature schemas are added in Phase 5.

```ts
// Empty for now — populated as feature modules are built
export {};
```

## Step 8 — Logger, Cache, Queue modules

Logger module (`nestjs-pino`-based, with workspace + request context) — see `references/observability.md`.

Cache module (`cache-manager` + Redis on DB 0) — see `references/caching.md`.

Queue module (BullMQ root config on Redis DB 1) — see `references/bullmq-queues.md`.

The shapes are standard; all three are referenced in the root `app.module.ts`.

## Step 9 — Common (guards, decorators, filters, interceptors)

Build out:
- `JwtAuthGuard`, `PoliciesGuard` — see `references/auth-casl.md`
- `WorkspaceContextInterceptor`, `AuditInterceptor` — see `references/audit-logging.md`
- `AllExceptionsFilter` — see `references/error-handling.md`
- Decorators: `@Public`, `@CurrentUser`, `@CurrentWorkspace`, `@CurrentAbility`, `@CheckAbility`, `@Audit`

## Step 10 — Root module

`apps/api/src/app.module.ts`:

```ts
import { Module } from '@nestjs/common';
import { APP_GUARD, APP_INTERCEPTOR, APP_FILTER } from '@nestjs/core';

import { ConfigModule } from './infrastructure/config/config.module';
import { LoggerModule } from './infrastructure/logger/logger.module';
import { DrizzleModule } from './infrastructure/drizzle/drizzle.module';
import { CacheModule } from './infrastructure/cache/cache.module';
import { QueueModule } from './infrastructure/queue/queue.module';
import { HealthModule } from './infrastructure/health/health.module';

import { CaslModule } from './modules/casl/casl.module';
import { AuditModule } from './modules/audit/audit.module';

import { JwtAuthGuard } from './common/guards/jwt-auth.guard';
import { PoliciesGuard } from './common/guards/policies.guard';
import { WorkspaceContextInterceptor } from './common/interceptors/workspace-context.interceptor';
import { AuditInterceptor } from './common/interceptors/audit.interceptor';
import { AllExceptionsFilter } from './common/filters/all-exceptions.filter';

import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler';
import { PrometheusModule } from '@willsoto/nestjs-prometheus';
import { metricsProviders } from './infrastructure/metrics/metrics.providers';

// Feature modules — populated in Phase 5
// import { AuthModule } from './modules/auth/auth.module';
// import { CompaniesModule } from './modules/companies/companies.module';
// ...

@Module({
  imports: [
    ConfigModule,
    LoggerModule,
    DrizzleModule,
    CacheModule,
    QueueModule,
    HealthModule,
    CaslModule,
    AuditModule,
    ThrottlerModule.forRoot([{ ttl: 60_000, limit: 100 }]),
    PrometheusModule.register(),
    // AuthModule, CompaniesModule, ...
  ],
  providers: [
    ...metricsProviders,
    { provide: APP_GUARD, useClass: ThrottlerGuard },
    { provide: APP_GUARD, useClass: JwtAuthGuard },
    { provide: APP_GUARD, useClass: PoliciesGuard },
    { provide: APP_INTERCEPTOR, useClass: WorkspaceContextInterceptor },
    { provide: APP_INTERCEPTOR, useClass: AuditInterceptor },
    { provide: APP_FILTER, useClass: AllExceptionsFilter },
  ],
})
export class AppModule {}
```

Guard order matters: `ThrottlerGuard` first (cheap), then `JwtAuthGuard` (sets `req.user`), then `PoliciesGuard` (uses `req.user` to build ability). Interceptors run inside guards: `WorkspaceContextInterceptor` sets workspace context after auth; `AuditInterceptor` reads `@Audit` metadata.

## Step 11 — API entrypoint

`apps/api/src/main.ts`:

```ts
import { NestFactory } from '@nestjs/core';
import { ZodValidationPipe, patchNestJsSwagger } from 'nestjs-zod';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { Logger } from 'nestjs-pino';
import helmet from 'helmet';
import cookieParser from 'cookie-parser';
import { AppModule } from './app.module';
import { TypedConfigService } from './infrastructure/config/config.service';

async function bootstrap() {
  patchNestJsSwagger();

  const app = await NestFactory.create(AppModule, { bufferLogs: true });
  const config = app.get(TypedConfigService);

  app.useLogger(app.get(Logger));
  app.use(helmet());
  app.use(cookieParser());
  app.enableCors({ origin: config.get('CORS_ORIGIN').split(','), credentials: true });
  app.setGlobalPrefix(config.get('API_PREFIX'));
  app.useGlobalPipes(new ZodValidationPipe());

  const docConfig = new DocumentBuilder()
    .setTitle('<APP_NAME> API').setVersion('1.0').addBearerAuth().build();
  SwaggerModule.setup('docs', app, SwaggerModule.createDocument(app, docConfig));

  const port = config.get('PORT');
  await app.listen(port);
  console.log(`API listening on :${port}/${config.get('API_PREFIX')}`);
}

bootstrap();
```

## Step 12 — Worker entrypoint

`apps/api/src/worker.ts`:

```ts
import { NestFactory } from '@nestjs/core';
import { Logger } from 'nestjs-pino';
import { AppModule } from './app.module';

async function bootstrap() {
  process.env.PROCESS_MODE = 'worker';

  const app = await NestFactory.createApplicationContext(AppModule, { bufferLogs: true });
  app.useLogger(app.get(Logger));

  const shutdown = async () => {
    await app.close();
    process.exit(0);
  };
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  console.log('Worker started; consuming queues');
}

bootstrap();
```

Workers are conditionally registered in feature modules based on `process.env.PROCESS_MODE` — see `references/bullmq-queues.md`.

## Step 13 — Migration runner

`apps/api/src/db/migrate.ts`:

```ts
import { drizzle } from 'drizzle-orm/postgres-js';
import { migrate } from 'drizzle-orm/postgres-js/migrator';
import postgres from 'postgres';

const sql = postgres(process.env.DATABASE_URL!, { max: 1 });
const db = drizzle(sql);

await migrate(db, { migrationsFolder: './drizzle' });
await sql.end();
console.log('Migrations applied');
```

`apps/api/src/db/apply-custom.ts` (idempotent custom SQL for Timescale features) — see `references/drizzle-timescaledb.md`.

## Step 14 — Verify

```bash
docker compose up -d
pnpm db:generate                # generate first migration (empty schema for now)
pnpm db:migrate
pnpm db:custom                  # creates extensions
pnpm start:dev
```

Expected output:

```
[Nest] LOG  ConfigModule dependencies initialized
[Nest] LOG  LoggerModule dependencies initialized
[Nest] LOG  DrizzleModule dependencies initialized
[Nest] LOG  CacheModule dependencies initialized
[Nest] LOG  QueueModule dependencies initialized
API listening on :3001/v1
```

Test:

```bash
curl http://localhost:3001/v1/health
# {"status":"ok"}

curl http://localhost:3001/v1/readiness
# {"status":"ok","info":{"database":{"status":"up"},"redis":{"status":"up"}},...}

curl http://localhost:3001/v1/metrics
# Prometheus format
```

All green → proceed to Phase 4 (auth + CASL + audit) and Phase 5 (feature modules).

## Final scaffolding state

```
apps/api/
├── package.json
├── tsconfig.json
├── drizzle.config.ts
├── docker-compose.yml
├── drizzle/
│   ├── 0000_init.sql
│   └── custom/
└── src/
    ├── main.ts
    ├── worker.ts
    ├── app.module.ts
    ├── db/
    │   ├── client.ts
    │   ├── tenant-db.ts
    │   ├── migrate.ts
    │   ├── apply-custom.ts
    │   └── schema/
    │       └── index.ts        ← empty for now
    ├── infrastructure/
    │   ├── config/
    │   ├── logger/
    │   ├── drizzle/
    │   ├── cache/
    │   ├── queue/
    │   ├── health/
    │   └── metrics/
    ├── common/
    │   ├── guards/
    │   ├── decorators/
    │   ├── interceptors/
    │   ├── filters/
    │   └── context/
    └── modules/
        ├── casl/
        ├── audit/
        └── (feature modules added in Phase 5)
```
