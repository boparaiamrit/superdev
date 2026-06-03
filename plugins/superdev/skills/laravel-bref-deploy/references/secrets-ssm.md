# Secrets via AWS SSM Parameter Store

How to store and inject Laravel environment secrets on Bref/Lambda using AWS Systems Manager (SSM) Parameter Store. Read in Phase 5 (secrets), referenced by `serverless-yml.md` for the `${ssm:/app/...}` syntax.

## Why SSM, not `.env` on Lambda

`.env` files must never be committed. On Lambda there is no server to `scp` a file to — the function package is immutable after deploy. SSM Parameter Store is:

- **Free** for the Standard tier (up to 10,000 parameters, 4 KB per value, unlimited `GetParameter` API calls at standard throughput)
- **Already integrated** with `osls` (OSS Serverless) — `${ssm:/path}` resolves at deploy time with no extra plugin
- **Auditable** — every read and write is logged in CloudTrail
- **Versioned** — you can roll back to a previous value without redeploying

The two injection modes are:

| Mode | When value is resolved | How | Use when |
|---|---|---|---|
| Deploy-time | During `osls deploy` | `${ssm:/app/KEY}` in `serverless.yml` `environment:` | Most secrets (APP_KEY, DATABASE_URL, AWS keys) |
| Runtime | First access inside the Lambda invocation | `bref-ssm:/app/KEY` prefix in `serverless.yml` + `bref/secrets-loader` | Secrets that rotate between deploys without redeploying; SecureString values that `${ssm:}` cannot decrypt at deploy time |

Start with deploy-time resolution. Switch to runtime only if you need zero-downtime secret rotation without redeploying.

## What lives in SSM

Store every secret that must not be committed:

| Parameter path | Laravel env var | Notes |
|---|---|---|
| `/app/APP_KEY` | `APP_KEY` | Base64 encryption key — generate once, never rotate unless forced |
| `/app/DATABASE_URL` | `DATABASE_URL` | Full CockroachDB serverless DSN including cluster routing and SSL cert path |
| `/app/AWS_ACCESS_KEY_ID` | `AWS_ACCESS_KEY_ID` | IAM key for SQS / S3 access (if not using Lambda role) |
| `/app/AWS_SECRET_ACCESS_KEY` | `AWS_SECRET_ACCESS_KEY` | Paired with above |
| `/app/AWS_REGION` | `AWS_DEFAULT_REGION` | Optional — region is often an env var, not a secret, but SSM keeps it consistent |

Do **not** put non-secret config (e.g., `CACHE_STORE=database`, `QUEUE_CONNECTION=sqs`, `APP_ENV=production`) in SSM — those go directly in `serverless.yml` `environment:` as plaintext. Reserve SSM for values that would cause harm if exposed.

On Lambda the `web` function's execution role grants it `ssm:GetParameter` for `/app/*`. Grant the narrowest IAM path prefix possible.

## Deploy-time injection (`${ssm:/app/...}`)

This is the default mode. `osls deploy` calls the SSM API before packaging; the resolved values are baked into the Lambda function's environment variables. No Lambda code changes needed.

```yaml
# serverless.yml — provider.environment block (excerpt)
provider:
  environment:
    APP_KEY:      ${ssm:/app/APP_KEY}
    DATABASE_URL: ${ssm:/app/DATABASE_URL}
    AWS_ACCESS_KEY_ID:     ${ssm:/app/AWS_ACCESS_KEY_ID}
    AWS_SECRET_ACCESS_KEY: ${ssm:/app/AWS_SECRET_ACCESS_KEY}
    # Non-secret config lives here, not in SSM:
    APP_ENV:          production
    CACHE_STORE:      database
    SESSION_DRIVER:   database
    QUEUE_CONNECTION: sqs
    SQS_QUEUE:        ${construct:jobs.queueUrl}
    FILESYSTEM_DISK:  s3
    ASSET_URL:        ${env:ASSET_URL}
```

The deploying IAM principal (your CI/CD user or local dev credentials) needs `ssm:GetParameter` and `ssm:GetParameters` on the `/app/` path at deploy time. The Lambda execution role does **not** need SSM access when using deploy-time resolution — the values are already in the environment.

## Runtime injection (`bref-ssm:` + `bref/secrets-loader`)

For secrets that rotate between deploys without redeploying (e.g., a rotating API key), or for SecureString parameters that the deploy-time `${ssm:}` resolver cannot decrypt (e.g., KMS key access not granted to the deploying user), use Bref's secrets loader.

Install:

```bash
composer require bref/secrets-loader
```

In `serverless.yml`, prefix the SSM path with `bref-ssm:` instead of using the deploy-time `${ssm:}` variable syntax:

```yaml
# serverless.yml — runtime-resolved secrets use bref-ssm: prefix
provider:
  environment:
    APP_KEY:      bref-ssm:/app/APP_KEY
    DATABASE_URL: bref-ssm:/app/DATABASE_URL
```

At the top of `public/index.php` (before bootstrapping Laravel), load the secrets:

```php
<?php
// public/index.php — add before the require-autoloader block
if (isset($_SERVER['LAMBDA_TASK_ROOT'])) {
    (new \Bref\Secrets\Secrets())->loadSecretEnvironmentVariables();
}

define('LARAVEL_START', microtime(true));
require __DIR__.'/../vendor/autoload.php';
// ... rest of index.php
```

The loader calls `ssm:GetParameters` in a single batched API call on cold start, then caches the values for the lifetime of the warm Lambda container. The Lambda execution role must have `ssm:GetParameter` for `/app/*`.

> **Cold-start cost:** the SSM batch call adds ~20–60 ms to cold starts depending on parameter count. Keep the number of `bref-ssm:` parameters small (< 10). Non-rotating secrets should use deploy-time `${ssm:...}` instead.

## Generating and storing APP_KEY

Never commit `APP_KEY`. Generate it once and store it in SSM before the first deploy.

```bash
# Step 1: generate the key (outputs: base64:...)
php artisan key:generate --show

# Step 2: store it in SSM as a SecureString
aws ssm put-parameter \
  --name "/app/APP_KEY" \
  --value "base64:YOUR_GENERATED_KEY_HERE" \
  --type "SecureString" \
  --region us-east-1

# Verify it was stored correctly
aws ssm get-parameter \
  --name "/app/APP_KEY" \
  --with-decryption \
  --query "Parameter.Value" \
  --output text
```

Do not run `php artisan key:generate` without `--show` — the plain `key:generate` command writes directly to `.env`, which on Lambda may not exist and is never the source of truth.

## Storing the DATABASE_URL

CockroachDB serverless uses a DSN that includes cluster routing and SSL mode. It contains the password in plaintext — it must be a SecureString in SSM.

```bash
# Full CockroachDB serverless DSN format:
# postgresql://<user>:<password>@<host>:26257/<cluster>.<database>?sslmode=verify-full

aws ssm put-parameter \
  --name "/app/DATABASE_URL" \
  --value "postgresql://app_user:s3cr3t@free-tier.aws-us-east-1.cockroachlabs.cloud:26257/clustername.defaultdb?sslmode=verify-full" \
  --type "SecureString" \
  --region us-east-1
```

In `config/database.php` the `pgsql` connection reads `DATABASE_URL` via `env('DATABASE_URL')`. Laravel's `Illuminate\Database\Connectors\PostgresConnector` parses the URL automatically — no manual DSN parsing needed.

## Storing AWS credentials (if not using a Lambda role)

The preferred approach is an **IAM execution role** attached to the Lambda function — no static credentials needed. `osls` wires this automatically: it creates a role with `sqs:*` and `s3:*` permissions scoped to your resources.

If you must use static credentials (e.g., a CI deployment to an account without role assumption):

```bash
aws ssm put-parameter \
  --name "/app/AWS_ACCESS_KEY_ID" \
  --value "AKIAIOSFODNN7EXAMPLE" \
  --type "SecureString" \
  --region us-east-1

aws ssm put-parameter \
  --name "/app/AWS_SECRET_ACCESS_KEY" \
  --value "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" \
  --type "SecureString" \
  --region us-east-1
```

When using an execution role, omit `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from `serverless.yml` entirely — the Lambda SDK picks up credentials from the role metadata service automatically.

## IAM permissions summary

Two principals need SSM access:

| Principal | Needs | Scope | When |
|---|---|---|---|
| Deploying IAM user/role (CI or local) | `ssm:GetParameter`, `ssm:GetParameters` | `arn:aws:ssm:<region>:<account>:parameter/app/*` | During `osls deploy` (deploy-time resolution) |
| Lambda execution role | `ssm:GetParameter` | `arn:aws:ssm:<region>:<account>:parameter/app/*` | At runtime (only needed for `bref-ssm:` runtime mode) |

In `serverless.yml`, grant the Lambda role via `iamRoleStatements`:

```yaml
# serverless.yml — only needed when using bref-ssm: runtime mode
provider:
  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - ssm:GetParameter
            - ssm:GetParameters
          Resource:
            - arn:aws:ssm:${aws:region}:${aws:accountId}:parameter/app/*
```

For deploy-time `${ssm:...}` only, this block is **not required** — the deployment user's credentials fetch the values before the Lambda role is relevant.

## Local development

On a local machine Laravel still reads from `.env`. The SSM values live in `.env.example` as empty placeholders; every developer fills in their own local values without touching production SSM.

```ini
# .env.example — local overrides; production values are in SSM
APP_KEY=                # run: php artisan key:generate (writes to .env directly, fine locally)
DATABASE_URL=           # local CockroachDB via docker-compose: postgresql://root@localhost:26257/defaultdb?sslmode=disable
AWS_ACCESS_KEY_ID=      # local dev AWS profile or empty for queue emulation
AWS_SECRET_ACCESS_KEY=
```

Never commit a real `.env` file. Add `.env` to `.gitignore` (Laravel does this by default). The `.env.example` has empty values so the repo documents what is required without leaking anything.

For local queue testing without AWS credentials, set `QUEUE_CONNECTION=sync` in `.env` so jobs run synchronously in the same process — no SQS account needed during development.

## Staging vs production parameters

Use the stage as a namespace prefix:

```
/app/prod/APP_KEY
/app/prod/DATABASE_URL
/app/staging/APP_KEY
/app/staging/DATABASE_URL
```

Update `serverless.yml` to use the stage variable:

```yaml
# serverless.yml — stage-namespaced SSM paths
provider:
  environment:
    APP_KEY:      ${ssm:/app/${sls:stage}/APP_KEY}
    DATABASE_URL: ${ssm:/app/${sls:stage}/DATABASE_URL}
```

Deploy to staging with `osls deploy --stage staging`; deploy to production with `osls deploy --stage prod`. The two stages are fully isolated — no shared secrets.

## Anti-patterns

- **Committing `.env` with real secrets.** Not just a bad practice — it permanently exposes credentials in git history even after deletion. Use `git-secrets` or `truffleHog` in CI to catch accidental commits.
- **Hardcoding secrets in `serverless.yml` as plaintext strings.** The `serverless.yml` is committed; any value written there literally is in the repo forever.
- **Using `php artisan key:generate` without `--show` on a server.** On Lambda there is no writable `.env` to update. Always use `--show` to get the value, then store it in SSM manually.
- **Using `bref-ssm:` for every variable.** Each SSM call on cold start adds latency. Use runtime mode only for secrets that genuinely rotate between deploys. Static config (cache driver, queue connection) belongs in `serverless.yml` environment as plaintext.
- **One SSM path for all stages.** Staging and production must be independent namespaces (`/app/prod/` vs `/app/staging/`). A staging deploy touching production SSM paths is an incident waiting to happen.
- **Lambda execution role with `ssm:GetParameter` on `*`.** Scope the resource ARN to `/app/*` (or `/app/${stage}/*`). Overly broad SSM permissions allow the function to read other teams' secrets if they share the same AWS account.
- **Rotating APP_KEY without a migration plan.** All existing encrypted values (sessions, cookies, encrypted model fields) become unreadable. If rotation is required: keep the old key as `APP_PREVIOUS_KEY`, decrypt with old, re-encrypt with new, then remove the old key. Document this as an operational procedure, not a routine rotation.
