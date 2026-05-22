# Inventory Checklist (Phase 1)

What `security-inventory` extracts and the format of `SECURITY_INVENTORY.md`.

## SECURITY_INVENTORY.md template

```markdown
# Security Inventory

> Generated: <ISO 8601>
> Repo: <git remote URL if available>
> SHA: <git rev-parse HEAD>

## Monorepo apps

| Path | Type | Public-facing | Notes |
|---|---|---|---|
| apps/api | Nest.js backend | Yes (REST API) | Port 3001 |
| apps/web | Next.js frontend | Yes (browser) | Port 3000 |
| packages/contracts | Shared schemas | No | Internal package |
| packages/tsconfig | TS presets | No | |
| packages/eslint-config | Lint config | No | |

## Backend endpoints

For each `@Controller` method:

| Method | Route | Guards | Audit | Body type | Workspace-scoped data |
|---|---|---|---|---|---|
| POST | /auth/login | @Public, @Throttle(5/60s) | — | LoginDto | No |
| POST | /auth/refresh | @Public | — | (cookie) | No |
| GET | /companies | @CheckAbility(read Company) | — | CompanyFiltersDto | Yes |
| POST | /companies | @CheckAbility(create Company) | @Audit company.create | CreateCompanyDto | Yes |
| PATCH | /companies/:id | @CheckAbility(update Company) | @Audit company.update | UpdateCompanyDto | Yes |
| DELETE | /companies/:id | @CheckAbility(delete Company) | @Audit company.delete | — | Yes |
| ... | | | | | |

**Endpoints WITHOUT auth guard or @Public marker:** <list — should be empty>

**Endpoints touching workspace-scoped data WITHOUT @CheckAbility:** <list — should be empty>

**Mutation endpoints WITHOUT @Audit:** <list>

## Frontend routes

| Route | File | Auth | Component type | Mutates |
|---|---|---|---|---|
| / | app/page.tsx | required | Server | No |
| /login | app/(auth)/login/page.tsx | public | Client | Yes (POST /auth/login) |
| /companies | app/companies/page.tsx | required | Server | No |
| /companies/[id] | app/companies/[id]/page.tsx | required | Server | No |
| /api/mock/[...path] | app/api/mock/[...path]/route.ts | (route handler) | — | Demo mode only |
| ... | | | | |

**Routes with NEXT_PUBLIC_API_MODE check:** <should include /api/mock>

## Drizzle schema

For each table:

| Table | Workspace-scoped | Hypertable | Sensitive fields | Indexes |
|---|---|---|---|---|
| workspaces | (root) | No | — | (id) |
| users | No (linked) | No | `password_hash` | (email unique) |
| companies | Yes | No | — | (workspace_id, created_at) |
| email_sent | Yes | YES | — | (workspace_id, sent_at) |
| audit_logs | Yes | YES | `metadata` may contain sensitive | (workspace_id, occurred_at) |
| ... | | | | |

**Workspace-scoped tables without a `workspace_id` FK constraint:** <should be empty>

## External integrations

| Service | Auth model | Cred env var | Inbound webhook | Outbound caller |
|---|---|---|---|---|
| InboxKit | Bearer + X-Workspace-Id | `INBOXKIT_BEARER`, `INBOXKIT_WORKSPACE_ID` | /v1/webhooks/inboxkit | apps/api/src/modules/mailboxes/clients/inboxkit.client.ts |
| Anthropic | API key | `ANTHROPIC_API_KEY` | — | apps/api/src/modules/ai/clients/anthropic.client.ts |
| ... | | | | |

## Auth surface

- **Access token TTL:** `JWT_ACCESS_TTL` env var, default `15m`
- **Refresh token TTL:** `JWT_REFRESH_TTL`, default `30d`
- **Access secret env:** `JWT_ACCESS_SECRET` (min length per env schema: 32)
- **Refresh secret env:** `JWT_REFRESH_SECRET` (min length per env schema: 32)
- **Password hashing:** argon2 (file: `apps/api/src/modules/auth/auth.service.ts`)
- **Refresh storage:** httpOnly cookie, path `/v1/auth`, sameSite strict, secure in prod
- **Refresh rotation:** Single-use, tracked in Redis with key `refresh:<jti>`

## CASL ability map

(Extracted from `apps/api/src/modules/casl/ability.factory.ts`)

| Role | Action × Subject permissions |
|---|---|
| Admin | manage all, except: delete Workspace |
| Operator | read all; create/update Company Contact Campaign EmailDraft Lead Deal; send Campaign; cannot delete (except own drafts); cannot read AuditLog |
| Pipeline | read Company Contact Lead Deal; update Lead Deal |
| Viewer | read Company Contact Campaign Lead Deal |

## Infrastructure (Docker)

(Extracted from root `docker-compose.yml`)

| Service | Image | Exposed port | Volume | Healthcheck |
|---|---|---|---|---|
| postgres | timescale/timescaledb:latest-pg17 | 5432 (127.0.0.1) | postgres_data | pg_isready |
| redis | redis:7-alpine | 6379 (127.0.0.1) | redis_data | redis-cli ping |
| mailpit | axllent/mailpit:latest | 1025, 8025 | — | (none) |
| minio | minio/minio:latest | 9000, 9001 | minio_data | (none) |

**Services with default passwords on exposed ports:** <list>
**Services exposed without 127.0.0.1 binding:** <list — should be empty in prod compose>

## Environment variables

From `.env.example` files:

| Variable | App | Purpose | Sensitive? |
|---|---|---|---|
| DATABASE_URL | api | Postgres connection | Yes |
| REDIS_URL | api | Redis connection | No (no creds in URL by default) |
| JWT_ACCESS_SECRET | api | Sign access tokens | YES |
| JWT_REFRESH_SECRET | api | Sign refresh tokens | YES |
| INBOXKIT_BEARER | api | InboxKit Bearer token | YES |
| ANTHROPIC_API_KEY | api | Claude API key | YES |
| NEXT_PUBLIC_API_MODE | web | demo / production | No |
| NEXT_PUBLIC_API_BASE_URL | web | API URL in prod mode | No |
| ... | | | |

**`process.env.X` accesses outside the typed config module:** <list — should be empty>

**Sensitive vars with no env-schema validation (min length, format):** <list>

## Secrets on disk

Files matching secret patterns:

- `.env` — should be gitignored (verify: `git check-ignore .env` returns 0)
- `.env.local` — should be gitignored
- `.env.example` — committed; values must be placeholders only
- `*.pem`, `*.key`, `service-account*.json` — should not exist in repo

**Files matching key patterns committed to git:** <list — should be empty>

**`.gitignore` coverage:**

- [ ] `.env` ignored
- [ ] `.env.*` ignored (except `.env.example`)
- [ ] `*.pem`, `*.key` ignored
- [ ] `node_modules` ignored
- [ ] `.next` ignored
- [ ] `dist`, `build` ignored

## NOTES

Anything you noticed that doesn't fit the categories above. For example:

- Custom middleware that does auth in a non-standard way
- Endpoints that mention "internal use only" in comments — verify access control
- Files with `TODO security` or `FIXME` markers
```

## Extraction tips

### Finding endpoints

```bash
grep -rn "@Controller\|@Get\|@Post\|@Patch\|@Put\|@Delete" apps/api/src/modules --include="*.controller.ts"
grep -rn "@CheckAbility\|@Public\|@Audit\|@Throttle" apps/api/src/modules --include="*.controller.ts"
```

Cross-reference: every handler should have either `@CheckAbility` OR `@Public`.

### Finding frontend routes

```bash
find apps/web/src/app -name "page.tsx" -o -name "route.ts" | sort
```

For each, inspect the file header for `'use client'` directive and whether auth is enforced.

### Finding Drizzle tables and workspace scoping

```bash
grep -rn "pgTable\|workspaceId" apps/api/src/db/schema
```

A table without `workspaceId` AND not in the `[workspaces, users, sessions, refresh_tokens]` allowlist is suspicious.

### Finding external HTTP calls

```bash
grep -rn "fetch(\|axios\|got\|undici" apps/api/src --include="*.ts"
```

Each result is a potential external integration; document its auth model.

### Finding env var accesses

```bash
grep -rn "process\.env\." apps/api/src apps/web/src --include="*.ts" --include="*.tsx" \
  | grep -v "/infrastructure/config/" \
  | grep -v "/lib/env.ts"
```

Each hit is a violation of "only the config module reads process.env" — find and inventory.

### Finding CASL ability rules

```bash
grep -n "can\|cannot" apps/api/src/modules/casl/ability.factory.ts
```

Walk the result and build the role × action × subject matrix.

## What this inventory is FOR

It exists so subsequent agents (`static-auditor`, `dynamic-auditor`, `dependency-auditor`) and the human reviewer have a canonical reference for:

- Which endpoints SHOULD be auth-required (compare to what static-auditor finds)
- Which tables SHOULD be workspace-filtered (compare to what static-auditor finds)
- Which env vars SHOULD have validation (compare to env schema)
- Which Docker services SHOULD be locked down (compare to compose)

The inventory is descriptive. Findings come later. If the inventory itself reveals issues (e.g., a route exists with no auth guard at all), flag those in a `## IMMEDIATE FLAGS` section at the bottom — these are pre-audit-phase emergencies.
