# Scaling, worker selection and module hierarchy

Read this at step 3 (`plan-architect`) and whenever adding a background job, high-volume list or cross-module integration.

## Scaling tiers (rule GOV-1)

Record the target tier in `EXECUTION_PLAN.md` `## Scaling and workers` so migrations, queries and queues match the real data shape from day one.

| Tier | Users | Rows per table | Database and indexes | Pagination | Cache | Workers |
|---|---|---|---|---|---|---|
| `T1` Startup | 1 to 10,000 | Under 100k | Single PostgreSQL or TimescaleDB primary; composite `(workspace_id, ..)` B-tree indexes for every filter and sort (rule BE-16) | Offset (`per_page <= 100`, rule BE-7) for admin tables; keyset cursor for audit and event streams | Opt-in workspace-keyed cache (rule BE-13); never cache auth, writes or audit | Single `<binary> queue:work` process with database or redis driver (rule BE-10) |
| `T2` Growth | 10,000 to 250,000 | 100k to 10M | Primary plus read replica for heavy analytics; TimescaleDB chunk compression and time-range predicates (rule BE-16) | Keyset cursor paging on all event, audit and large directory lists (`navree-database`) | Redis cache with write invalidation and CDN immutable static assets | Separate worker queues by latency class (transactional mail, bulk imports, batch scoring) so bulk jobs never starve interactive mail |
| `T3` Enterprise | 250,000+ | 10M+ | Regional pods with isolated databases, connection pooling and per-workspace rate limits | Keyset cursors plus TimescaleDB continuous aggregates for dashboards | Regional Redis clusters behind the reverse proxy | Autoscaled stateless worker groups plus isolated processes for heavy CPU or media jobs |

## Worker and execution selection matrix (rule GOV-2)

Pick the execution class from the workload's latency, failure mode and isolation needs rather than guessing.

| Execution class | Use when | Refuse when | Workspace isolation rule | Idempotency and retry |
|---|---|---|---|---|
| `sync-http` | Interactive CRUD, validation and indexed lookups finishing under 250 ms | External SMTP, OAuth or webhook calls, CSV imports over 50 rows, bulk updates over 500 ids or heavy CPU | HTTP auth plus `CurrentWorkspace` and workspace model scope (rules BE-2, BE-3, BE-4) | Idempotency key or one-time form token on money or record creation (hard rule 23) |
| `async-queue` | Imports, directory sync, bulk mutations over 500 ids, outgoing mail and webhooks, batch scoring (`navree-queues-and-scheduling`) | Caller needs the final computed record inline before continuing (return 202 with a job id instead) | Worker runs outside HTTP guards: job payload carries `workspace_id` and every query scopes by it explicitly (rule BE-17, hard rule 27) | Safe to run twice (hard rule 7, rule BE-10); 3 attempts with backoff 1 s to 300 s, then `queue:failed` |
| `scheduled-cron` | Daily digests, delta syncs, nightly reconciliation and pruning (`ScheduleModule`) | An event can trigger the work immediately when data changes | Iterate workspaces explicitly and open one unit of work per workspace; never mix workspaces in one transaction | Safe to run twice; track last completed workspace-local day to catch up missed runs (rules BE-11, BE-15) |
| `isolated-worker` | Heavy CPU, headless PDF or document rendering, media processing, attachment scanning | Ordinary database updates | Zero shared mutable state between runs; enforce memory and timeout limits | At most 2 retries on process crash, then dead-letter and alert |
| `sse-stream` | Streaming AI responses, live sync progress, real-time workspace feeds (`navree-events-and-broadcasting`) | Request/response mutations | Check session, permission and workspace membership on stream handshake; drop subscription on disconnect | Reconnect with last event id; carry ids only and publish after commit (hard rule 24, rule SEC-12) |

### Worker tenant-isolation proof

Every workspace job in `src/modules/<module>/jobs/` needs a committed test that:

1. Seeds workspace A and workspace B with overlapping records (rule BE-14).
2. Runs the job payload for workspace A while targeting or passing a record id from workspace B.
3. Asserts workspace B's rows did not change and no data from workspace B was read, mailed or broadcast.
4. Runs the same job payload twice and asserts one side effect (rule BE-10).

## Four-tier acyclic module hierarchy (rule GOV-5)

Every module in `EXECUTION_PLAN.md` `## Modules` belongs to one tier (`0` to `3`). Dependencies point only to the same tier or a lower tier.

| Tier | Layer | Typical modules | Allowed dependencies |
|---|---|---|---|
| `0` | Kernel and platform foundation | Auth, workspaces, access control, audit log, settings, mail and queue foundation | Tier 0 only |
| `1` | Core identity and shared libraries | Customers, recipients, people directory, shared templates or catalogs | Tiers 0 and 1 |
| `2` | Domain execution engines | Invoices, campaigns, orders, training, billing, announcements | Tiers 0, 1 and 2 |
| `3` | Intelligence, automation and reporting | Workflows, activity feeds, executive reports, AI assistants | Tiers 0, 1, 2 and 3 |

### Cross-module integration laws (rules GOV-5, BE-18)

- **Downward calls use public facades:** a higher-tier module calls an exported service trait or facade registered by the lower-tier module (`navree-modules-and-di`). It never queries the lower-tier module's database table or model directly.
- **Upward notifications use domain events:** a lower-tier module never imports a higher-tier module. When a tier-1 or tier-2 action must inform a tier-3 module (such as an activity feed, workflow trigger or report rollup), emit a typed domain event (`navree-events-and-broadcasting`) after the transaction commits.
- **Zero cycles and valid build order:** `EXECUTION_PLAN.md` `## Modules` must form a directed acyclic graph with no lower-tier module depending on a higher-tier module, and `## Build order` must place every dependency before the module that depends on it. `verify-done.mjs` (`module dependency graph`) checks all three mechanically.
