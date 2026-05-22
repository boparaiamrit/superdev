# Dynamic Audit Checklist (Phase 3)

Runtime probes against a live stack. The `dynamic-auditor` agent runs these via `curl` + `jq`. Static analysis can't see runtime behavior — this catches the differences between "intended" and "actual."

## Prerequisites

Before probing, verify the stack is up:

```bash
docker compose ps --format json | jq -e 'all(.Health == "healthy" or (.Health == "" and .State == "running"))'
curl -fsS http://localhost:3001/v1/readiness > /dev/null && echo "API up" || echo "API DOWN"
```

If anything's down, **halt** — probing a half-running system produces meaningless findings.

## Test fixtures

The dynamic-auditor needs:

- Two workspace IDs (create via signup endpoint, or use a seed script)
- One user per role in each workspace (Admin, Operator, Pipeline, Viewer)
- Access tokens for each user

Capture into shell variables for the probes:

```bash
# Workspace A, all four roles
TOKEN_A_ADMIN=$(curl -s -X POST http://localhost:3001/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin-a@example.com","password":"<test_password>"}' \
  | jq -r '.accessToken')

TOKEN_A_OPERATOR=$(curl -s ... | jq -r '.accessToken')
# ... etc

# Workspace B, admin
TOKEN_B_ADMIN=$(curl -s ... | jq -r '.accessToken')

API=http://localhost:3001/v1
```

If no seed script exists, the orchestrator should add one before running this audit — flag as a precondition gap.

## Probe categories

### 1. Cross-workspace isolation

The single most important runtime test.

```bash
# Create a company in workspace A
COMPANY_A=$(curl -s -X POST $API/companies \
  -H "Authorization: Bearer $TOKEN_A_ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Test Co","domain":"test.example","industry":"Technology"}' \
  | jq -r '.id')

# Try to read it as workspace B's admin
STATUS=$(curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer $TOKEN_B_ADMIN" \
  $API/companies/$COMPANY_A)

# Expected: 404 (not 403, not 200)
[[ "$STATUS" == "404" ]] && echo "✓ Isolation holds" || echo "✗ ISOLATION BROKEN ($STATUS)"
```

Repeat for: contacts, campaigns, mailboxes, leads, deals, audit logs.

**Findings:**
- 200 response → **Critical** (data leak)
- 403 response → **High** (leaks existence)
- 404 response → ✓ clean

### 2. Auth enforcement

For each authed endpoint:

```bash
# No token
STATUS_NONE=$(curl -s -o /dev/null -w '%{http_code}' $API/companies)
[[ "$STATUS_NONE" == "401" ]] || echo "✗ Missing auth: $STATUS_NONE"

# Malformed token
STATUS_BAD=$(curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer not-a-real-jwt" \
  $API/companies)
[[ "$STATUS_BAD" == "401" ]] || echo "✗ Accepts malformed: $STATUS_BAD"

# Expired token (use a pre-generated expired one, or modify the JWT exp claim)
STATUS_EXPIRED=$(curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer $EXPIRED_TOKEN" \
  $API/companies)
[[ "$STATUS_EXPIRED" == "401" ]] || echo "✗ Accepts expired: $STATUS_EXPIRED"

# Wrong signature (modify the last byte of a real token)
WRONG_SIG="${TOKEN_A_ADMIN}X"
STATUS_WRONG_SIG=$(curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer $WRONG_SIG" \
  $API/companies)
[[ "$STATUS_WRONG_SIG" == "401" ]] || echo "✗ Accepts wrong-sig: $STATUS_WRONG_SIG"
```

**Findings:** Any non-401 = **Critical**.

### 3. CASL role enforcement matrix

For each role × subject × action triple in `SECURITY_INVENTORY.md`'s ability map, probe and verify the expected status code.

Example matrix (extract from inventory):

| Role | Read Company | Create Company | Delete Company | Read AuditLog |
|---|---|---|---|---|
| Admin | 200 | 201 | 204 | 200 |
| Operator | 200 | 201 | 403 | 403 |
| Pipeline | 200 | 403 | 403 | 403 |
| Viewer | 200 | 403 | 403 | 403 |

Probe script:

```bash
probe() {
  local role=$1 method=$2 path=$3 expected=$4 token_var="TOKEN_A_${role^^}"
  local token=${!token_var}
  local actual
  actual=$(curl -s -o /dev/null -w '%{http_code}' -X "$method" \
    -H "Authorization: Bearer $token" \
    "$API$path")
  if [[ "$actual" == "$expected" ]]; then
    echo "✓ $role $method $path → $actual"
  else
    echo "✗ $role $method $path → $actual (expected $expected)"
  fi
}

probe OPERATOR GET    /companies        200
probe VIEWER   POST   /companies        403
probe VIEWER   DELETE /companies/foo    403
# ... etc
```

**Findings:** Any mismatch = **High** (Critical if Viewer can mutate or Pipeline can delete data).

### 4. Rate limits

Auth endpoints:

```bash
# Hammer /auth/login with bad creds — should 429 quickly
for i in $(seq 1 20); do
  STATUS=$(curl -s -o /dev/null -w '%{http_code}' -X POST $API/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"x@y.com","password":"wrong"}')
  echo "Request $i: $STATUS"
  [[ "$STATUS" == "429" ]] && break
done

# A 429 should have appeared by request 6 or 7 if @Throttle({ limit: 5 })
```

**Findings:**
- 429 within first 10 requests → ✓ clean
- 429 only after default global throttle (~100) → **Medium** (auth-specific throttle missing)
- No 429 at all → **High** (no throttle)

### 5. Security headers

```bash
# Inspect a public route
curl -sI $API/health > /tmp/headers.txt
cat /tmp/headers.txt
```

Required headers:

| Header | Expected |
|---|---|
| `Strict-Transport-Security` | `max-age=15552000; includeSubDomains` or longer |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` or `SAMEORIGIN` |
| `Content-Security-Policy` | Non-empty |
| `Referrer-Policy` | `no-referrer` or `strict-origin-when-cross-origin` |
| `X-Powered-By` | **absent** (Express leaks this by default) |
| `Server` | absent or generic |

**Findings:**
- Missing CSP → **Medium**
- Missing HSTS → **Medium** (only relevant in HTTPS prod; flag for prod)
- Missing X-Content-Type-Options → **Low**
- Present `X-Powered-By` → **Low**

### 6. Cookie inspection

```bash
# Login and capture Set-Cookie header
curl -sI -X POST $API/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin-a@example.com","password":"<test_password>"}' \
  | grep -i "set-cookie:"
```

Expected attributes on the refresh-token cookie:

- `HttpOnly`
- `Secure` (omitted in dev over plain HTTP — verify prod build)
- `SameSite=Strict` (or Lax with justification)
- `Path=/v1/auth` (narrow scope) or `Path=/`
- `Max-Age` set (not session-only)

**Findings:**
- Missing `HttpOnly` → **High** (XSS-readable)
- Missing `Secure` in prod → **High**
- `SameSite=None` without strong CSRF defense → **Medium**

### 7. Error response leakage

Set `NODE_ENV=production` in the running API (kill and restart). Then trigger errors:

```bash
# Trigger 404
curl -s $API/nonexistent | jq
# Expect: { code: "NOT_FOUND", message: "...", details: null, request_id: "..." }
# Bad: stack trace, internal path, route map

# Trigger 500 (e.g., malformed payload that the controller throws on)
curl -s -X POST $API/companies \
  -H "Authorization: Bearer $TOKEN_A_ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"name":""}' | jq

# Trigger DB constraint error (e.g., duplicate)
curl -s -X POST $API/companies \
  -H "Authorization: Bearer $TOKEN_A_ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Dupe","domain":"dupe.example","industry":"Other"}'
# Then repeat the same call
```

**Findings:**
- `stack` field present in any response → **Medium**
- DB column names / Postgres internals in 500 response → **Medium**
- Filesystem paths in error → **Low**
- Generic envelope with no internals → ✓ clean

### 8. Mock route in production

```bash
# Rebuild frontend in production mode
(cd apps/web && NEXT_PUBLIC_API_MODE=production pnpm build)

# Start the prod build
(cd apps/web && NEXT_PUBLIC_API_MODE=production pnpm start &)
WEB_PID=$!
sleep 5

# Request the mock route
STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/mock/companies)
[[ "$STATUS" == "404" ]] && echo "✓ Mock disabled in prod" || echo "✗ Mock LEAKED ($STATUS)"

kill $WEB_PID
```

**Findings:**
- 200 with mock data → **High** (fake data in prod hides real bugs)
- 500 → **Medium** (broken — still a leak but obvious)
- 404 → ✓ clean

### 9. Webhook signature bypass

For each inbound webhook endpoint from inventory:

```bash
# Send unsigned payload to webhook receiver
STATUS=$(curl -s -o /dev/null -w '%{http_code}' \
  -X POST $API/webhooks/inboxkit \
  -H 'Content-Type: application/json' \
  -d '{"event":"warmup.complete","mailboxId":"fake"}')

[[ "$STATUS" == "401" || "$STATUS" == "403" ]] && echo "✓ Rejects unsigned" \
  || echo "✗ Accepts unsigned: $STATUS"
```

**Findings:**
- 200/202 on unsigned payload → **High** (forgeable webhooks)
- 400 (malformed) is ambiguous — try a fully-formed but unsigned payload
- 401/403 → ✓ clean

### 10. CORS preflight

```bash
# Preflight from a forbidden origin
curl -s -I -X OPTIONS $API/companies \
  -H "Origin: https://evil.example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Authorization"

# Should NOT include `Access-Control-Allow-Origin: https://evil.example.com`
# Should NOT include `Access-Control-Allow-Origin: *` when credentials are involved
```

**Findings:**
- Forbidden origin receives `Access-Control-Allow-Origin: <that origin>` → **High**
- `*` with `Access-Control-Allow-Credentials: true` → **High** (browser will reject, but config is wrong)

### 11. CSRF on state-changing endpoints (cookie-authed)

If any endpoint authenticates by cookie (not Bearer header), CSRF is a concern. Pure-Bearer APIs are immune.

```bash
# Send a state-changing request with a stolen-looking referer / no origin
curl -s -X POST $API/companies \
  --cookie "refresh_token=$REFRESH_COOKIE" \
  -H "Origin: https://evil.example.com" \
  -H 'Content-Type: application/json' \
  -d '{"name":"CSRF","domain":"csrf.example","industry":"Other"}'
```

For Bearer-authed APIs: only `/auth/refresh` uses the cookie. Verify that refresh is the only cookie-authed endpoint and that it can't trigger non-auth state changes.

**Findings:**
- Cookie-authed mutation succeeds from foreign origin → **High**

### 12. Open redirect

```bash
# If the app has any redirect handler (e.g., /auth/callback?redirect_uri=...)
curl -s -I "$API/auth/callback?state=x&redirect_uri=https://evil.example.com" \
  | grep -i "location:"
```

**Findings:**
- Redirects to attacker-controlled URL → **High**
- Redirects to allowlisted URL only → ✓ clean

## Finding format

Same as static-auditor:

```
### S-D-<N> [<severity>] — <title>

- **Category:** <#>
- **Probe:** <command>
- **Expected:** <code or behavior>
- **Actual:** <code or behavior>
- **Evidence:**
  ```
  <captured output>
  ```
- **Why it matters:** <one or two sentences>
- **Recommendation:** <specific change>
```

## What to do if probes can't run

If the agent can't probe (no seed script, missing test credentials, stack won't start in prod-NODE_ENV), it writes:

```
## PROBES NOT RUN

- §1 cross-workspace: no seed script available — needs test fixtures for workspace A + B with admin users
- §8 mock route: prod build failed — needs NEXT_PUBLIC_API_BASE_URL set
```

The orchestrator surfaces these to the user. They're not findings, they're gaps — the audit is incomplete until they're resolved.
