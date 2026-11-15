# Deploy checklist

Step 9 of a build, run only when the operator asks for a deploy. Go through the sections in order; each item names its proof. Navree's `navree-deployment` skill holds the release build, processes, proxies and health checks, and `navree-harbor` holds `navree deploy`. Record what was run and every result in `DEPLOY.md` (format at the end).

## Before

- [ ] The operator asked for a deploy and chose the target: Harbor (`navree harbor:init`, `navree harbor:secrets set APP_KEY --generate`, `navree harbor:provision`, then `navree deploy`; servers on Ubuntu 22.04 or 24.04 with SSH as root), a container image (`navree build:image`), or processes set up by hand per `navree-deployment`. Proof: the operator's words and the target in `DEPLOY.md`.
- [ ] `navree config:check --env production` exits 0 on the production configuration. Proof: the exit code in `DEPLOY.md`. An app on SQLite: the check refuses a SQLite URL in production; settle with the operator how the app runs there (check `navree-deployment`) and record it.
- [ ] Production settings: `database.migrate_on_boot = false`, `session.secure = true`, `mail.transport` not `log`, `http.trusted_proxies` set to the proxy, `observe.metrics_token` set and `/metrics` denied at the proxy, `app.url` the real public origin (hard rule 20); on TimescaleDB, `APP_SCHEMA__TIMESCALEDB=require`. Proof: the matching lines of `navree config:show --origin`.
- [ ] The OpenAPI document and its docs UI are off in production unless the operator wants them; when on, they are public, so they are on only by decision. Proof: `GET /api/openapi.json` answers as decided.
- [ ] Secrets come from `.env`, the environment or Harbor's secrets, never from TOML (hard rule 9), and every process reads the same `APP_KEY`. Proof: `navree config:show --origin` on each server.
- [ ] Database backups are encrypted, and a restore has been tested. Proof: the date and result of the last tested restore in `DEPLOY.md`.
- [ ] The global staff roles, their grants and the staff accounts' roles are made by a release step or a data migration, never by the demo seeder (rule BE-14). Proof: one staff account signs in on production with its role.

## Processes

- [ ] `<binary> serve`, `<binary> queue:work` and `<binary> schedule:work` (or `<binary> schedule:run` from cron every minute) run as separate processes, from the directory that holds the binary, `config/app.toml` and a writable `storage/`. Proof: the service status of each.
- [ ] The queue driver is `database` or `redis`: a `memory` queue is per process, so a separate `queue:work` sees nothing. Proof: `navree config:show --origin`.
- [ ] The proxy passes WebSocket upgrades for `/app/` when the app has live updates. Proof: a live update reaches an open page through the proxy.
- [ ] With several servers or processes: `http.rate_limit_store = "redis"` and `realtime.backplane = "redis"`; a BFF on several processes has sticky sessions (hard rule 21); uploads on a disk that is not local (`navree-storage`). Proof: the settings, and one upload read back from a second server.
- [ ] Database pool size and TLS to the database: check `navree-database` and `navree-deployment`, and record the values chosen. Proof: the values in `DEPLOY.md`.

## Migrations

- [ ] Migrations are a release step, never at start: `./<binary> migrate`, then restart the processes (`navree deploy` runs `migrate` itself). Proof: the release log.
- [ ] `navree deploy:rollback` does not undo migrations, so every migration in the release is additive (hard rule 16). Proof: the rule's `git diff --name-status` check.

## Not in production

- [ ] Logbook (`/_logbook`) belongs to debug builds. Proof: the release build does not serve it.
- [ ] Navigator (`navree mcp`) is a development tool and does not run on a server. Proof: the process list.
- [ ] Demo seeders refuse production: `navree db:seed` stops there without `--force`, and nobody passes it. Proof: no demo account of `EXECUTION_PLAN.md` signs in on production.

## After

- [ ] The public `GET /health/ready` answers 200 (`navree deploy` printed `Released <id>` for Harbor).
- [ ] Sign-in works for one account per role, with accounts the operator provides.
- [ ] A job is processed: an action that queues one completes, and `./<binary> queue:failed` lists nothing new.
- [ ] The scheduler ran: its log, or a new row in `schedule_runs`.
- [ ] A stored file is served back.
- [ ] Logs carry the request id (`X-Request-Id`) and no secret, token or personal data.
- [ ] Lighthouse at `/_lighthouse` is reachable by staff only; check `navree-lighthouse` for how its access is set.
- [ ] `audit:prune` is scheduled (hard rule 12).

Each item of this section is a row of `DEPLOY.md` `## Checks` with `PASS`, `FAIL` or `NOT RUN`; a `NOT RUN` needs the operator's acceptance.

## DEPLOY.md

```markdown
# Deploy

Target: Harbor, two servers (Ubuntu 24.04)
Commit: 9c41e07
Date: 2026-12-02 18:30 IST
Release: <the id navree deploy printed>

## Commands run
- navree config:check --env production (exit 0)
- navree deploy (Released <id> in ...)

## Settings
- Database pool size and TLS: <values and where they are set>

## Checks
| Check | Status | Evidence |
|---|---|---|
| GET /health/ready | PASS | 200 at 18:41 IST |
| Sign-in per role | PASS | owner, member and support accounts at 18:44 IST |
| Lighthouse staff only | NOT RUN | accepted by Meera Sharma on 2026-12-02: no staff account yet |
```
