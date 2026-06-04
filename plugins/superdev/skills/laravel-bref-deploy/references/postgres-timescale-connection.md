# PostgreSQL + TimescaleDB Connection (Lambda / Bref)

How to reach a **managed PostgreSQL + TimescaleDB host over the public internet** from AWS Lambda — **no VPC, no NAT gateway, no RDS Proxy**. This is the deploy-time perspective; the application-layer details (stock `pgsql` driver, hypertables, UUID PKs, reference-field model) live in the build skill's [`postgres-timescale-eloquent.md`](../../laravel-enterprise-backend/references/postgres-timescale-eloquent.md).

> **(Was CockroachDB in ≤v1.5.)** The host is now a managed Postgres+Timescale instance (Timescale Cloud or self-managed). The wire protocol is plain Postgres; nothing here is engine-specific beyond the host requirement below.

---

## The host: managed Postgres + TimescaleDB over the public internet

The Laravel app on Bref connects to a **managed PostgreSQL server with the TimescaleDB extension**, reached over the public internet on the standard Postgres port `5432`. Two host shapes qualify:

- **Timescale Cloud** — a managed Postgres+Timescale service with a public hostname per service.
- **Self-managed Postgres+Timescale** — your own Postgres server (EC2, another cloud, on-prem) with the extension installed, exposed over TLS.

**Host requirement — the extension is non-negotiable.** The full tier uses **hypertables, native compression, and retention policies** for `audit_logs` (see `postgres-timescale-eloquent.md`). Those features require the TimescaleDB extension and its **TSL** (Timescale License) capabilities. A plain managed Postgres without the extension cannot create hypertables or run `add_compression_policy` / `add_retention_policy`.

> **Neon is NOT a target for this tier.** Neon is plain managed Postgres — it does **not** ship the TimescaleDB extension, so it cannot create hypertables and cannot run compression or retention policies. If `CREATE EXTENSION timescaledb` fails on first migrate, the host is unsuitable; move to Timescale Cloud or a self-managed Postgres+Timescale server.

---

## Why no VPC — and why that matters on Lambda

The default instinct for "Lambda needs a database" is to put both inside a VPC, then add RDS Proxy. A managed Postgres+Timescale host reachable over the public internet makes that the wrong choice:

| Concern | VPC path | Public-internet path (our choice) |
|---|---|---|
| **Cost** | NAT Gateway ~$32/mo + per-GB data charge + ENI attachment fees | $0 extra — the host is reachable over TLS on the open internet |
| **Cold-start latency** | VPC ENI attachment adds 1–10 s to the first-ever cold start per AZ | No ENI — cold start stays at ~250 ms p99 |
| **Connection pooling** | RDS Proxy multiplexes connections, but it only runs inside a VPC | No RDS Proxy (no VPC) — handled by bounded reserved concurrency instead |
| **TLS** | Usually added manually | `sslmode=require` over the public internet — always on |
| **Complexity** | Subnets, security groups, route tables, VPC endpoints for SQS/SSM | None — standard Bref deploy, no extra AWS resources |

The managed host exposes a **public hostname** (`<service>.tsdb.cloud.timescale.com` on Timescale Cloud, or your own DNS for a self-managed box). All traffic is TLS-encrypted. No VPC is needed or recommended for this stack.

---

## DSN format and SSL

The whole connection — host, port, database, credentials, and TLS mode — is carried in a single `DATABASE_URL` stored in **AWS SSM Parameter Store** (see `secrets-ssm.md`). Nothing is hard-coded in `serverless.yml` or committed to source.

```bash
# Format (stored in SSM as /app/DATABASE_URL)
DATABASE_URL="postgresql://<user>:<password>@<service>.tsdb.cloud.timescale.com:5432/<database>?sslmode=require"
```

Key parts:

| Part | Value | Purpose |
|---|---|---|
| Port | `5432` | Standard Postgres wire port — TimescaleDB is just an extension, not a separate protocol |
| Database name | `<database>` | A normal Postgres database (e.g. `tsdb`) — no routing prefix |
| `sslmode` | `require` | Encrypts the connection over the public internet |

`sslmode=require` encrypts the link without pinning a CA. If the host publishes a CA bundle and you want full server-identity verification, raise it to `verify-full` and add `&sslrootcert=/var/task/certs/ca.crt`, bundling the public CA cert into the Lambda package at that path (`/var/task` is where Lambda extracts the deployment). `require` is the baseline for this tier; `verify-full` is the hardening upgrade.

### `config/database.php` connection block

When `DATABASE_URL` is set, Laravel parses the URL and uses the embedded values; the discrete `DB_*` variables become fallbacks for local dev. It is an ordinary Postgres connection — no driver options, no prepared-statement workaround:

```php
// config/database.php — 'connections' => [ 'pgsql' => [...] ]
'pgsql' => [
    'driver'         => 'pgsql',
    'url'            => env('DATABASE_URL'),           // full DSN from SSM at deploy time
    'host'           => env('DB_HOST', '127.0.0.1'),  // fallback for local dev
    'port'           => env('DB_PORT', '5432'),
    'database'       => env('DB_DATABASE'),
    'username'       => env('DB_USERNAME'),
    'password'       => env('DB_PASSWORD'),
    'charset'        => 'utf8',
    'prefix'         => '',
    'prefix_indexes' => true,
    'search_path'    => 'public',
    'sslmode'        => env('DB_SSLMODE', 'require'),  // managed host over the public internet
],
```

The same `pgsql` block is shared with the build skill — see `postgres-timescale-eloquent.md`. No `cluster` param, no third-party package, no `PDO::PGSQL_ATTR_DISABLE_PREPARES` workaround: standard Postgres semantics (sequences, joins, `SKIP LOCKED`, real transactions) all work.

---

## Connection fan-out under Lambda concurrency

Lambda is stateless — every concurrent invocation runs its own PHP-FPM process with its own database connection. At 100 concurrent `web` invocations that is up to 100 simultaneous connections. A managed Postgres+Timescale host has a `max_connections` ceiling tied to its plan/instance size; exhausting it returns "too many connections" and requests start failing.

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
    reservedConcurrency: 20        # cap concurrent web Lambdas -> caps DB connections
    events:
      - httpApi: '*'
```

Guidance:
- **Small managed instances** allow on the order of 25–100 connections. Start with `reservedConcurrency: 20` to leave headroom for migrations, the `artisan` function, the SQS worker, and local dev.
- **Larger instances** scale `max_connections` with RAM — raise the reserved concurrency to match (e.g. `50` for a host with 100+ connection slots), keeping a buffer.
- The `artisan` (console/scheduler) function fires at most once per minute (EventBridge `rate(1 minute)`) and its concurrency stays near 1 — it does not need a separate cap. The SQS `worker` function fans out the same way; if the worker makes DB calls, set `reservedConcurrency` on the worker construct too — see `sqs-worker.md`.
- The sum of every function's reserved concurrency that opens a DB connection (`web` + `worker` + `artisan`) must stay under the host's `max_connections` minus a maintenance buffer.
- Load-test before launch: run the deploy-checklist smoke test under realistic concurrency and watch the host's active-connections metric.

### Why not PgBouncer

PgBouncer in transaction-pooling mode would reduce Lambda-to-DB connections, but it requires a persistent host (EC2 or an ECS task), which reintroduces cost and operational complexity — and, if placed in front of the DB, often a VPC. For a serverless-first target, bounded concurrency against the managed host's own connection limit is the right trade-off at this scale. (Timescale Cloud also offers a built-in connection pooler; enable it on the service and point `DATABASE_URL` at the pooler endpoint if you outgrow bounded concurrency — still no VPC required.)

---

## `serverless.yml` environment block (deploy-side)

These variables belong in `provider.environment`. `DATABASE_URL` comes from SSM at deploy time; `DB_SSLMODE` is explicit belt-and-suspenders:

```yaml
provider:
  environment:
    DATABASE_URL: ${ssm:/app/DATABASE_URL}    # managed PostgreSQL + TimescaleDB DSN (sslmode embedded)
    DB_SSLMODE: require                        # explicit; also in the URL
    # DB_HOST / DB_DATABASE / DB_USERNAME / DB_PASSWORD are NOT needed when DATABASE_URL is set
```

Do not set `DB_HOST`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD` separately when the full `DATABASE_URL` is present — the URL takes precedence and the discrete vars become noise. See `serverless-yml.md` for the full provider block.

---

## Local dev vs production

| Environment | Connection |
|---|---|
| **Local dev** | Docker single-node Postgres+Timescale (`timescale/timescaledb` image via `docker-compose.yml`) on `localhost:5432`, `sslmode=disable`. `DATABASE_URL` in `.env` points at the container. No TLS, no SSM. |
| **Lambda (prod/staging)** | Public managed Postgres+Timescale endpoint. `DATABASE_URL` resolved from SSM. `sslmode=require` (or `verify-full` if hardened). |

Run the local container from the `timescale/timescaledb` image so the extension is available — the first migration's `CREATE EXTENSION IF NOT EXISTS timescaledb` then succeeds locally exactly as it does in production. The local container is defined in the build skill's `monorepo-setup.md`. The schema is identical — the only difference is TLS.

---

## Anti-patterns

- **Putting Lambda in a VPC to reach the database.** A managed Postgres+Timescale host is reachable over the public internet with TLS. A VPC adds NAT costs, ENI cold-start latency, and pulls in RDS Proxy (which itself requires a VPC). Avoid it entirely.
- **Assuming Neon (or any plain Postgres) supports compression/retention.** Neon does **not** ship the TimescaleDB extension — no hypertables, no `add_compression_policy`, no `add_retention_policy`. It is not a target for this tier. Verify `CREATE EXTENSION timescaledb` succeeds on the chosen host before committing to it.
- **Omitting `sslmode` in production.** Plain `disable` sends credentials and data in cleartext over the public internet. Use `require` as the baseline; `verify-full` (with a bundled CA cert) to also pin server identity.
- **Skipping `reservedConcurrency` on the `web` function.** Without it, a traffic spike opens hundreds of simultaneous connections and trips the host's `max_connections`, causing cascading failures.
- **Setting `reservedConcurrency` to 0.** That throttles the function to zero — Lambda returns 429 to every request. Start at 20, load-test, and tune upward.
- **Letting `web` + `worker` + `artisan` reserved concurrency exceed `max_connections`.** Budget the connection ceiling across every function that opens a DB connection, with a maintenance buffer.
- **Committing `DATABASE_URL` or DB credentials.** Store them in SSM (`/app/DATABASE_URL`) and inject via `${ssm:/app/DATABASE_URL}` at deploy time or `bref-ssm:` at runtime — see `secrets-ssm.md`.
- **Reaching for a third-party / forked database driver.** The stock `pgsql` connection works against any managed Postgres+Timescale host. See `postgres-timescale-eloquent.md` for the full rationale.
