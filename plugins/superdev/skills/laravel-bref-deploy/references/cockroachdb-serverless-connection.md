# CockroachDB Serverless Connection (Lambda / Bref)

How to reach **CockroachDB serverless over the public internet** from AWS Lambda — **no VPC, no NAT gateway, no RDS Proxy**. This is the deploy-time perspective; the application-layer details (UUID PKs, `40001` retry, additive migrations) live in the build skill's [`cockroachdb-eloquent.md`](../../laravel-enterprise-backend/references/cockroachdb-eloquent.md).

---

## Why no VPC — and why that matters on Lambda

The default instinct for "Lambda needs a database" is to put both inside a VPC, then use RDS Proxy. CockroachDB serverless makes that the wrong choice:

| Concern | VPC path | Public-internet path (our choice) |
|---|---|---|
| **Cost** | NAT Gateway ~$32/mo + per-GB data charge + ENI attachment fees | $0 extra — CockroachDB Cloud is reachable over TLS on the open internet |
| **Cold-start latency** | VPC ENI attachment adds 1–10 s to the first-ever cold start per AZ | No ENI — cold start stays at ~250 ms p99 |
| **RDS Proxy** | Required in a VPC to multiplex connections | Unavailable (no VPC) — handled by bounded reserved concurrency instead |
| **TLS** | Usually added manually | Enforced by CockroachDB Cloud (`sslmode=verify-full`) — not optional |
| **Complexity** | Subnets, security groups, route tables, VPC endpoints for SQS/SSM | None — standard Bref deploy, no extra AWS resources |

CockroachDB Cloud exposes a **public hostname** per serverless cluster (`<cluster-id>.<region>.cockroachlabs.cloud:26257`). All traffic is TLS-encrypted and the cluster routing id is embedded in the database name. No VPC is needed or recommended for this stack.

---

## DSN format and SSL

The entire connection — host, port, cluster routing id, database, credentials, TLS mode, and CA certificate — is carried in a single `DATABASE_URL` stored in **AWS SSM Parameter Store** (see `secrets-ssm.md`). Nothing is hard-coded in `serverless.yml` or committed to source.

```bash
# Format (stored in SSM as /app/DATABASE_URL)
DATABASE_URL="postgresql://<user>:<password>@<cluster-id>.<region>.cockroachlabs.cloud:26257/<cluster-id>.defaultdb?sslmode=verify-full&sslrootcert=/var/task/certs/ca.crt"
```

Key parts:

| Part | Value | Purpose |
|---|---|---|
| Port | `26257` | CockroachDB's Postgres-wire port (not 5432) |
| Database name | `<cluster-id>.defaultdb` | The **cluster routing id** is the prefix — this is how CockroachDB Cloud routes serverless tenants |
| `sslmode` | `verify-full` | Verifies both the server's hostname and the full CA chain |
| `sslrootcert` | `/var/task/certs/ca.crt` | Path to the CockroachDB CA cert bundled into the Lambda deployment package |

### Bundling the CA certificate

The CockroachDB CA certificate must be present in the Lambda runtime. Bundle it into the project so Bref packages it:

```bash
# Download the CockroachDB Cloud CA certificate (one-time per project)
mkdir -p certs
curl -o certs/ca.crt "https://cockroachlabs.cloud/clusters/<cluster-id>/cert"
```

Reference it at the fixed `/var/task/certs/ca.crt` path in `DATABASE_URL` — `/var/task` is where Lambda extracts the deployment package. Commit `certs/ca.crt` to the repo (it is a public CA cert, not a secret).

### `config/database.php` connection block

When `DATABASE_URL` is set, Laravel parses the URL and uses the embedded values. The discrete `DB_*` variables become fallbacks for local dev. The only deploy-specific addition is `PDO::PGSQL_ATTR_DISABLE_PREPARES`:

```php
// config/database.php — 'connections' => [ 'pgsql' => [...] ]
'pgsql' => [
    'driver'         => 'pgsql',
    'url'            => env('DATABASE_URL'),          // full DSN from SSM at deploy time
    'host'           => env('DB_HOST', '127.0.0.1'),  // fallback for local dev
    'port'           => env('DB_PORT', '26257'),
    'database'       => env('DB_DATABASE', 'defaultdb'),
    'username'       => env('DB_USERNAME'),
    'password'       => env('DB_PASSWORD'),
    'charset'        => 'utf8',
    'prefix'         => '',
    'prefix_indexes' => true,
    'search_path'    => 'public',
    'sslmode'        => env('DB_SSLMODE', 'verify-full'),
    'options'        => array_filter([
        \PDO::PGSQL_ATTR_DISABLE_PREPARES => true,    // safer with CRDB connection routing
    ]),
],
```

`PDO::PGSQL_ATTR_DISABLE_PREPARES => true` tells PDO to send queries as simple protocol messages instead of using named prepared statements. This is the safer mode with CockroachDB's pgwire routing layer.

---

## Connection fan-out under Lambda concurrency

Lambda is stateless — every concurrent invocation opens its own PHP-FPM process with its own database connection. At 100 concurrent `web` function invocations, that is up to 100 simultaneous connections. CockroachDB serverless has a connection limit tied to the tier; exhausting it returns a connection-refused error.

There is **no RDS Proxy without a VPC**. The mitigation is **bounded reserved concurrency** on the `web` function.

### Setting reserved concurrency

In `serverless.yml`, add `reservedConcurrency` to the `web` function:

```yaml
functions:
  web:
    handler: public/index.php
    runtime: php-84-fpm
    timeout: 28
    memorySize: 1024
    reservedConcurrency: 20        # tune per CockroachDB plan connection limit
    events:
      - httpApi: '*'
```

Guidance:
- **CockroachDB serverless free tier** allows ~30 connections. Start with `reservedConcurrency: 20` to leave headroom for migrations, the artisan function, and local dev.
- **Paid tiers** scale connections with compute — raise the reserved concurrency to match (e.g. `50` for a plan with 60+ connection slots).
- The `artisan` (console/scheduler) function fires at most once per minute (EventBridge `rate(1 minute)`) and its concurrency stays near 1 — it does not need a separate cap. The `worker` (SQS) function can scale with queue depth; set `reservedConcurrency` on the worker construct too if the worker makes DB calls — see `sqs-worker.md` for details.
- Load-test before launch: run the deploy-checklist's smoke test under realistic concurrency and watch the CockroachDB Cloud "Active connections" dashboard.

### Why not PgBouncer

PgBouncer in transaction-pooling mode would reduce Lambda-to-DB connections. It requires a persistent host (EC2 or an ECS task), which reintroduces cost and operational complexity. For a serverless-first, free-tier target this trade-off is not worthwhile. CockroachDB serverless's own connection management (combined with bounded concurrency) is the right solution at this scale.

---

## `serverless.yml` environment block (deploy-side)

These variables should be present in the `provider.environment` section. `DATABASE_URL` comes from SSM at deploy time; the others are derived from it:

```yaml
provider:
  environment:
    DATABASE_URL: ${ssm:/app/DATABASE_URL}    # full DSN; cluster routing + TLS embedded
    DB_SSLMODE: verify-full                   # explicit; also in the URL but belt-and-suspenders
    # DB_HOST / DB_DATABASE are NOT needed when DATABASE_URL is set
```

Do not set `DB_HOST`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD` separately when the full `DATABASE_URL` is present — the URL takes precedence and the discrete vars become noise.

---

## Local dev vs production

| Environment | Connection |
|---|---|
| **Local dev** | Docker single-node CockroachDB (`docker-compose.yml`) on `localhost:26257`, `sslmode=disable` or a self-signed cert. `DATABASE_URL` in `.env` points at the container. No CA cert required. |
| **Lambda (prod/staging)** | Public CockroachDB Cloud endpoint. `DATABASE_URL` resolved from SSM. CA cert at `/var/task/certs/ca.crt`. `sslmode=verify-full`. |

The local single-node container is defined in the build skill's `monorepo-setup.md`. The schema is identical — the only difference is TLS and the cluster routing prefix in the database name.

---

## Anti-patterns

- **Putting Lambda in a VPC to reach CockroachDB.** CockroachDB Cloud is reachable over the public internet with full TLS. A VPC adds NAT costs, ENI cold-start latency, and requires RDS Proxy (which requires a VPC — a circular dependency). Avoid it entirely.
- **Omitting `sslmode=verify-full` in production.** `disable` or `require` (no verification) allow MITM attacks on the connection. Always use `verify-full` for CockroachDB Cloud.
- **Hard-coding the cluster id in `serverless.yml` or source code.** The cluster id belongs in the `DATABASE_URL` stored in SSM. It changes if you recreate the cluster.
- **Skipping `reservedConcurrency` on the `web` function.** Without it, a traffic spike can open hundreds of simultaneous DB connections and exhaust the serverless connection limit, causing cascading failures.
- **Setting `reservedConcurrency` too low.** If it equals 0, Lambda returns 429 to every request. Start at 20, load-test, and tune upward.
- **Committing `DATABASE_URL` or DB credentials.** Always store them in SSM (`/app/DATABASE_URL`) and inject via `${ssm:/app/DATABASE_URL}` at deploy time or `bref-ssm:` at runtime.
- **Using a third-party CockroachDB Laravel driver.** The stock `pgsql` connection works. See `cockroachdb-eloquent.md` for the full rationale.
- **Not bundling `certs/ca.crt`.** If the CA cert is absent at runtime, PHP's PDO will fail TLS handshake with a "certificate verify failed" error. Bundle the public CA cert in the project.
