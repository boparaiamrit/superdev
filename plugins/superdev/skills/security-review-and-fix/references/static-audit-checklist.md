# Static Audit Checklist (Phase 2)

The complete grep playbook for `static-auditor`. Each check is a category, a command, a pattern interpretation, and a severity.

Run every check unless explicitly skipped. The default severity per check appears below; promote upward (never downward) based on context.

## 1. Tenancy bypass

### 1.1 — Workspace-scoped tables queried without `tenantDb`

```bash
# Find every Drizzle query on workspace-scoped tables
grep -rn "from(\(companies\|contacts\|campaigns\|mailboxes\|leads\|deals\|email_sent\|email_received\|audit_logs\))" \
  apps/api/src --include="*.ts" -E
```

For each hit, check whether the same statement uses `tenantDb(...).scope(...)`:

```bash
# Find db.select/insert/update/delete calls touching scoped tables WITHOUT tenantDb in nearby context
grep -rn -B2 -A2 "db\.\(select\|insert\|update\|delete\)" apps/api/src/modules \
  | grep -B4 "from(\(companies\|contacts\|campaigns\|mailboxes\|leads\|deals\))" \
  | grep -L "tenantDb\|scope("
```

**Severity:** Critical. Tenancy bypass is the worst-case data leak in multi-tenant SaaS.

### 1.2 — `db.execute(sql\`...\`)` with workspace-scoped tables

```bash
grep -rn "db\.execute\|sql\`" apps/api/src --include="*.ts" \
  | grep -E "companies|contacts|campaigns|mailboxes|leads|deals|email_sent"
```

Raw SQL on workspace-scoped tables MUST include an explicit `workspace_id = ${workspaceId}` filter. Manually inspect each result.

**Severity:** Critical.

## 2. AuthZ — every endpoint must have @CheckAbility or @Public

### 2.1 — Controller methods missing both decorators

```bash
# Find every HTTP handler decorator
grep -rn -A4 "@\\(Get\\|Post\\|Patch\\|Put\\|Delete\\)" apps/api/src/modules \
  --include="*.controller.ts" \
  | grep -B1 -A1 "^\s*\\(public \\)\\?async\\? \\w" \
  > /tmp/handlers.txt

# Cross-check: find handlers with NO @CheckAbility or @Public in 4 lines above
```

The reliable approach: for each handler method, the four lines above MUST contain `@CheckAbility(` or `@Public(`. The static-auditor agent loops through each match and confirms.

**Severity:** Critical when the endpoint touches data (handler reads/writes DB). High when it's metadata-only (e.g., `/health` — but /health should be @Public anyway).

### 2.2 — `@Public` on data endpoints

```bash
grep -rn -B2 "@Public" apps/api/src/modules --include="*.controller.ts" \
  | grep -B1 "@\\(Get\\|Post\\|Patch\\|Put\\|Delete\\)"
```

Inspect each: is it genuinely public (auth, signup, health)? Or accidentally exposing data?

**Severity:** Critical for data endpoints; Info for legitimate public endpoints.

## 3. AuthN — auth implementation strength

### 3.1 — JWT secret length validation

```bash
grep -n "JWT_ACCESS_SECRET\|JWT_REFRESH_SECRET" apps/api/src/infrastructure/config/env.schema.ts
```

Both secrets MUST have `.min(32)` in the Zod schema. Anything less is brute-forceable.

**Severity:** High if missing or `<32`.

### 3.2 — Password hashing

```bash
grep -rn "bcrypt\|md5\|sha1\b\|crypto\.createHash" apps/api/src --include="*.ts"
grep -rn "argon2" apps/api/src --include="*.ts"
```

Expected: argon2 in `auth.service.ts`. Anything else for password hashing is wrong.

**Severity:** Critical for plain bcrypt with low cost, md5, or sha1; otherwise High.

### 3.3 — Access vs refresh secret separation

The same `process.env.JWT_SECRET` (one secret for both access and refresh) is a smell. Verify two separate env vars.

```bash
grep -rn "JWT_SECRET\b" apps/api/src --include="*.ts" \
  | grep -v "JWT_ACCESS_SECRET\|JWT_REFRESH_SECRET"
```

Hits = uses of a unified secret = finding.

**Severity:** High.

### 3.4 — Refresh token single-use

Look for refresh-token rotation logic:

```bash
grep -rn "refresh.*jti\|refresh:.*cache\.del\|refresh.*rotation" apps/api/src --include="*.ts"
```

Expected: `await cache.del(\`refresh:${payload.jti}\`)` immediately after verification, before issuing new tokens.

**Severity:** High if absent.

## 4. SQL injection

### 4.1 — `sql.raw()` with non-literal

```bash
grep -rn "sql\.raw(" apps/api/src --include="*.ts"
```

`sql.raw()` accepts unescaped strings. Inspect each: the argument MUST be a literal string. ANY variable interpolation is a finding.

**Severity:** Critical.

### 4.2 — Template-string SQL with interpolation

```bash
grep -rn 'sql`[^`]*\${' apps/api/src --include="*.ts"
```

Drizzle's `sql\`SELECT ... ${var}\`` is parameterized — safe. But the agent should inspect each: variables come from controlled sources (typed args, not user input via headers/body directly without validation).

**Severity:** Medium for unaudited; downgrade to Info if the interpolated value is itself a Drizzle column reference.

## 5. Input validation

### 5.1 — `@Body() x: any`

```bash
grep -rn "@Body\|@Query\|@Param" apps/api/src --include="*.controller.ts" \
  | grep -E ":\s*any\b|:\s*unknown\b|@Body\(\)\s*\w+\s*$"
```

Every `@Body()` should bind to a DTO class. `: any` skips Zod validation.

**Severity:** High for `@Body()`, Medium for `@Query()`/`@Param()`.

### 5.2 — ZodValidationPipe global

```bash
grep -n "ZodValidationPipe\|useGlobalPipes" apps/api/src/main.ts
```

Expected: `app.useGlobalPipes(new ZodValidationPipe())`. Absent = no validation.

**Severity:** Critical.

## 6. Audit logging

### 6.1 — Mutation methods without `@Audit`

```bash
# Find service methods that look like mutations (create/update/delete/send)
grep -rn -B2 "async \\(create\\|update\\|delete\\|send\\|publish\\|archive\\|restore\\|approve\\|reject\\|invite\\|revoke\\)" \
  apps/api/src/modules --include="*.service.ts" \
  | grep -v "@Audit"
```

Cross-reference: each mutation needs `@Audit({ action: '<subject>.<verb>', subject: '<Subject>' })`.

**Severity:** Medium (compliance gap; not directly exploitable).

## 7. Secrets in repo

### 7.1 — Common secret-shaped patterns

```bash
# Anthropic
grep -rEn "sk-ant-[a-zA-Z0-9_-]{40,}" . \
  --include="*.ts" --include="*.tsx" --include="*.js" \
  --include="*.json" --include="*.md" --include="*.env*" \
  --exclude-dir=node_modules --exclude-dir=.git

# OpenAI
grep -rEn "sk-[a-zA-Z0-9]{20,}" . \
  --include="*.ts" --include="*.tsx" --include="*.js" \
  --include="*.json" --include="*.md" --include="*.env*" \
  --exclude-dir=node_modules --exclude-dir=.git

# AWS
grep -rEn "AKIA[0-9A-Z]{16}" . --exclude-dir=node_modules --exclude-dir=.git

# GitHub
grep -rEn "gh[pousr]_[a-zA-Z0-9]{36,}" . --exclude-dir=node_modules --exclude-dir=.git

# Stripe
grep -rEn "sk_(live|test)_[a-zA-Z0-9]{24,}" . --exclude-dir=node_modules --exclude-dir=.git

# Generic JWT-shaped strings
grep -rEn "eyJ[A-Za-z0-9_-]{20,}\\.eyJ[A-Za-z0-9_-]{20,}" . \
  --include="*.ts" --include="*.tsx" --include="*.md" \
  --exclude-dir=node_modules --exclude-dir=.git
```

`.env.example` should have placeholder values only. `.env` should be gitignored.

**Severity:** Critical for any hit outside `.env.example` placeholders or test fixtures with clearly-fake values.

### 7.2 — `.env` in git

```bash
git ls-files | grep -E "^\\.env$|^\\.env\\.local$|^\\.env\\.production$"
```

Any hit is Critical.

### 7.3 — Private key files

```bash
git ls-files | grep -E "\\.(pem|key)$|service-account.*\\.json$|google-credentials"
```

Any hit is Critical.

## 8. Rate limiting

### 8.1 — ThrottlerGuard registered globally

```bash
grep -n "ThrottlerGuard\|ThrottlerModule" apps/api/src/app.module.ts
```

Expected: both. `ThrottlerModule.forRoot([{ ttl, limit }])` AND `APP_GUARD` provider for `ThrottlerGuard`.

**Severity:** High if absent.

### 8.2 — Auth endpoints have stricter throttle

```bash
grep -rn "@Throttle" apps/api/src/modules/auth --include="*.controller.ts"
```

Expected: `@Throttle({ default: { limit: 5, ttl: 60_000 } })` or similar on `/login`, `/signup`, `/refresh`, `/forgot-password`.

**Severity:** High if global throttle only (auth endpoints abused at scale = credential stuffing).

## 9. Mass assignment

### 9.1 — Spreading input into Drizzle inserts/updates

```bash
grep -rn "\\.values({\\s*\\.\\.\\.input\\|\\.set({\\s*\\.\\.\\.input" apps/api/src --include="*.ts"
```

`{ ...input, workspaceId }` is fine because Zod-validated input excludes extra fields (Zod strips unknown keys by default, but only with `.strict()` — verify). Without strict parsing, an attacker adding `{ workspaceId: 'other-ws' }` to the body could write across tenants.

**Severity:** High if any unvalidated spread; Medium if `Zod.strict()` is on by default.

### 9.2 — `as any` casts in Drizzle calls

```bash
grep -rn "\\.values(.*as any\\)\\|\\.set(.*as any\\)" apps/api/src --include="*.ts"
```

**Severity:** High.

## 10. XSS

### 10.1 — `dangerouslySetInnerHTML` without sanitization

```bash
grep -rn "dangerouslySetInnerHTML" apps/web/src --include="*.tsx" --include="*.ts"
```

For each hit, check 5 lines above and below for a sanitizer (`DOMPurify`, `sanitize-html`). No sanitizer = finding.

**Severity:** High.

### 10.2 — `eval()`, `Function()`, `new Function()`

```bash
grep -rn "\\beval(\\|new Function(" apps/web/src apps/api/src --include="*.ts" --include="*.tsx"
```

**Severity:** Critical if present in production code paths.

## 11. Token storage (frontend)

### 11.1 — `localStorage.setItem` with token-shaped keys

```bash
grep -rn "localStorage\\.setItem\\|localStorage\\.getItem" apps/web/src --include="*.ts" --include="*.tsx" \
  | grep -iE "token|jwt|refresh|access|auth|bearer"
```

Tokens in localStorage are XSS-readable.

**Severity:** High.

### 11.2 — `document.cookie` writes for auth tokens

```bash
grep -rn "document\\.cookie\\s*=" apps/web/src --include="*.ts" --include="*.tsx"
```

Cookies should be set by the backend with httpOnly. Frontend `document.cookie` writes can't set httpOnly.

**Severity:** High if writing auth tokens.

## 12. CORS

### 12.1 — Wildcard origin with credentials

```bash
grep -n "enableCors\\|cors" apps/api/src/main.ts
```

Expected: explicit allowlist from `CORS_ORIGIN.split(',')`. Find:

```bash
grep -rn "origin:\\s*['\"]\\*['\"]\\|origin:\\s*true" apps/api/src --include="*.ts"
```

Hit with `credentials: true` = High (browsers reject this combo, but the attempt indicates broken config).

**Severity:** High.

## 13. Helmet

### 13.1 — `app.use(helmet())`

```bash
grep -n "helmet" apps/api/src/main.ts
```

Expected: imported and applied. Absent = no security headers added.

**Severity:** Medium.

### 13.2 — CSP configured

```bash
grep -rn "Content-Security-Policy\\|contentSecurityPolicy" apps/api/src apps/web/src --include="*.ts"
```

Helmet's default CSP is restrictive; verify it's not disabled with `contentSecurityPolicy: false`.

**Severity:** Medium if disabled.

## 14. Cookies

### 14.1 — Refresh cookie attributes

```bash
grep -rn "res\\.cookie\\|setRefreshCookie" apps/api/src/modules/auth --include="*.ts"
```

Inspect each: must include `httpOnly: true`, `secure: <prod check>`, `sameSite: 'strict'` or `'lax'`. Missing any = finding.

**Severity:** High for missing httpOnly; Medium for missing secure (in dev OK but prod check must exist).

## 15. Mock route in production (frontend)

### 15.1 — `/api/mock` reachable when API_MODE != demo

```bash
cat apps/web/src/app/api/mock/[...path]/route.ts | grep -i "api_mode\\|mode\\|env\\|demo"
```

Expected: early return with 404 when not in demo mode:

```ts
if (process.env.NEXT_PUBLIC_API_MODE !== 'demo') {
  return new NextResponse('Not Found', { status: 404 });
}
```

Absent = mock routes ship to production.

**Severity:** High (exposes fake data, hides real API errors).

## 16. Webhook signatures

### 16.1 — Inbound webhook handlers verify HMAC

```bash
grep -rn "@Controller.*webhooks" apps/api/src --include="*.controller.ts"
```

For each webhook controller, inspect: the handler MUST verify a signature header (`X-Signature`, `X-Hub-Signature-256`, `X-Webhook-Signature`, etc.) using a shared secret. Acceptance without verification = forgeable webhooks.

**Severity:** High.

## 17. Docker hardening

### 17.1 — Default passwords on exposed services in prod compose

```bash
grep -n "POSTGRES_PASSWORD: postgres\\|MINIO_ROOT_PASSWORD: minioadmin" docker-compose.yml docker-compose.prod.yml 2>/dev/null
```

Dev compose with `postgres/postgres` is fine; prod compose with same is Critical.

**Severity:** Critical if in prod compose, Info if dev only.

### 17.2 — Ports exposed without 127.0.0.1 binding (prod)

```bash
grep -n "\"\\([0-9]\\{4\\}\\):" docker-compose.prod.yml 2>/dev/null
```

`"5432:5432"` exposes on 0.0.0.0 — public. `"127.0.0.1:5432:5432"` is dev-safe. Prod compose should bind to localhost only or omit the port (use Docker network).

**Severity:** High in prod compose.

### 17.3 — Image pinning

```bash
grep -n "image:.*:latest" docker-compose.yml
```

`:latest` is non-reproducible. Pin to a specific tag (`pg17`, `7-alpine`) or digest (`@sha256:...`).

**Severity:** Low for dev compose, Medium for prod compose.

### 17.4 — `restart: unless-stopped` present

Every service should have a restart policy. Crashed services without restart silently disappear.

**Severity:** Low.

## 18. Error response leakage

### 18.1 — Filter strips internals in production

```bash
grep -n "NODE_ENV.*production\\|process\\.env\\.NODE_ENV" apps/api/src/common/filters
```

Expected: the global exception filter checks `NODE_ENV === 'production'` and returns `null` or sanitized details. If `details: error.message` is always set, internal info leaks.

**Severity:** Medium.

## 19. Logging hygiene

### 19.1 — Secrets in log statements

```bash
grep -rn "logger\\.\\(info\\|warn\\|error\\|debug\\)" apps/api/src --include="*.ts" \
  | grep -iE "password|token|secret|api[_-]?key|authorization"
```

Inspect each — context might be benign (logging "no token" as a debug message) but logging actual token values is a finding.

**Severity:** High if confirmed token-value logging; Medium for suspicious cases needing review.

### 19.2 — Audit interceptor redaction

```bash
grep -n "SECRET_KEYS\\|redact" apps/api/src/common/interceptors/audit.interceptor.ts
```

Expected: a redaction set filtering keys like `password`, `token`, `secret`, `apiKey`, `authorization`. Missing = audit logs may include sensitive request bodies.

**Severity:** High.

## 20. Frontend env exposure

### 20.1 — Non-PUBLIC env vars referenced in client code

```bash
grep -rn "process\\.env\\." apps/web/src --include="*.ts" --include="*.tsx" \
  | grep -v "NEXT_PUBLIC_"
```

Only `NEXT_PUBLIC_*` vars are sent to the browser. Non-public vars referenced in client code don't error — they evaluate to `undefined`, hiding broken logic.

**Severity:** Medium (broken behavior more than security, but signals confused boundaries).

## Finding format

Each finding the static-auditor writes:

```
### S-S-<N> [<Critical|High|Medium|Low|Info>] — <title>

- **Category:** <#>
- **File:** `<relative path>:<line>`
- **Evidence:**
  ```<lang>
  <≤6 lines>
  ```
- **Why it matters:** <one or two sentences>
- **Recommendation:** <specific change with file:line if multi-file>
```

## "Clean" section

At the end of `SECURITY_FINDINGS.md`, the static-auditor adds:

```
## Clean checks (no findings)

✅ §3.1 JWT secret length validation
✅ §3.2 Password hashing (argon2 used)
✅ §10.2 No eval / new Function
... etc
```

Positive evidence matters — it tells the user which categories are confirmed safe vs. unchecked.
