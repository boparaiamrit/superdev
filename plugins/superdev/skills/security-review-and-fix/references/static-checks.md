# Static checks

Read this in step 2, and `## Dependencies` in step 4. `static-auditor` and `dependency-auditor` run these checks on the committed tree and report each as a finding with its evidence, or under `## Clean checks`. The sweeps that `verify-done.mjs` already runs (suppressions since `base_commit`, raw markup, placeholders) are cited from its output, not repeated. The last column is the severity a failing check gets, on the scale in [artifacts.md](../../superdev-build/references/artifacts.md). The rules BE-, SEC- and NUI- are the ones the build followed; this file only says how to find a breach.

## Checks

### Access and scope

| Check | How | If it fails |
|---|---|---|
| Every route declares access; the public ones are the plan's | a route without an access attribute does not compile (hard rule 6); the public routes in `navree routes --json` equal the public list in `EXECUTION_PLAN.md` `## Access` | `Major`; `Blocker` when the route reads or writes workspace or personal data |
| Workspace data is scoped | each model of a workspace module has `workspace` in `#[model(..)]`; controllers carry `#[guard(InWorkspace::guard())]`; queries go through `WorkspaceRepo`; no unscoped query in a handler or a job (hard rule 10, rules BE-2 to BE-4) | `Blocker` |
| Database-level scoping | PostgreSQL and TimescaleDB: each workspace table's migration contains `RlsPolicy`. SQLite and MySQL: no raw statement on a workspace table lacks the workspace predicate (hard rule 11) | `Major` |
| Records, lists and updates are checked | record routes use `#[can(.., from = "id")]`, lists take `Accessible<M, Read>`, updates call `check_fields`; code compares permission keys, never role names (rule BE-5) | `Blocker` for a missing check; `Major` for role names |
| Escalation guards | nobody grants a permission they do not hold, changes their own role or disables themselves; a workspace keeps one `owner` (rule SEC-8) | `Blocker` |
| End users hold no staff permission | staff keys are global grants; end users have workspace roles only; `helm.view` goes to staff roles only (rule SEC-9) | `Blocker` |

### Input and output

| Check | How | If it fails |
|---|---|---|
| Every body and query is validated | each `Json<` and `Query<` argument is wrapped in `Valid<..>`; review each `skip` for a field that needs a rule | `Major` |
| No mass assignment | no request type is deserialised straight into a model; every written field is named; a field the caller's role may not set (workspace id, role, status, balance) is not in the request type | `Blocker` when such a field can be set; `Major` otherwise |
| No SQL built from strings | raw statements with interpolated values | `Blocker` |
| Posted options are checked | Navree UI forms check a posted option with `all_pickable` (rule NUI-4) | `Major` |
| No raw HTML output | Navree UI: nothing hard rule 14 forbids, and its raw building blocks only for the three uses it allows, in files a gap row names (cite the `Navree UI raw markup` and `Navree UI gap rows` checks and the render check of the gate); text from people reaches `SafeHtml::trusted` only after it is cleaned; on Next.js `dangerouslySetInnerHTML` takes only sanitised input | `Blocker` for unsanitised user data in markup; `Major` otherwise |
| Errors reveal no internals | no SQL, path or stack trace in a `message`; no `message` built from the text of a database or I/O error (`navree-errors-and-responses`) | `Major` |
| Uploads | `store_upload` with `UploadRules`; upload responses keyed (required since 1.2.1); a directory per workspace (`navree-storage`) | `Major` |
| Outgoing HTTP | the client's SSRF guard is on; no user-supplied URL is fetched with it off | `Blocker` for a user-supplied URL with the guard off; `Major` otherwise |
| Incoming webhooks are verified | every incoming webhook route passes through the verification of `navree-webhooks` | `Blocker` |

### Audit, logs and secrets

| Check | How | If it fails |
|---|---|---|
| Sensitive writes are audited | `AuditModule` is registered (hard rule 12); sensitive routes carry `#[audit(action = ..)]`; mass updates and raw statements call `uow.record_change`; `audit:prune` is scheduled | `Major` |
| No secret in source, git or TOML | `git ls-files .env` prints nothing; search the tree, and the history with `git log --all --oneline -G '<pattern>'`, for secret shapes: `-----BEGIN`, `AKIA` followed by 16 capitals or digits, `ghp_`, `sk_live_`, `sk-ant-`, and JWT shapes (`eyJ..` dot `eyJ..`); no quoted value for a key named `key`, `secret`, `password` or `token` in `config/`; `navree config:show --origin` shows each secret coming from `.env` or the environment (hard rule 9) | `Blocker` for a live secret in git or source; `Major` for a default value in TOML |
| No secret or personal data in logs and audit metadata | search logging calls and audit metadata for tokens, passwords, e-mail addresses and phone numbers; secrets are wrapped in `Secret<T>` (rule SEC-13) | `Major` |
| Only intended variables reach the browser | `NEXT_PUBLIC_` variables hold nothing secret | `Blocker` for a secret |
| Demo data stays out of production | demo seeders refuse production without `--force` and no deploy file passes it; the Navree UI kit's demo account (`harpreet.singh@example.com`, development and tests only) is in no production path: search source and seeders for the address | `Blocker` |

### Sessions, tokens and sign-in

| Check | How | If it fails |
|---|---|---|
| Sign-up is closed unless the PRD asks | `auth.registration = false`; the access-token lifetime is at most 900 s; every custom sign-in ends with `AuthService::sign_in` (hard rule 21) | `Major` |
| Blocking and revocation | each event of hard rule 21 ends a browser session at once and refuses a token client's refresh at once, and the access-token lifetime stays short (rules SEC-2 and SEC-3; check `navree-auth` for how sessions and refresh tokens are ended) | `Major`; `Blocker` when a blocked account keeps a session or can still refresh |
| Sign-in methods | passkeys, magic links, emailed codes, social sign-in and single sign-on are switched on only when the PRD asks; with passkeys on, `rp_id` and `origins` name only the app's own origin | `Major` |
| Throttles on the sensitive routes | sign-in, code and refresh routes carry `#[throttle(limit, per)]`; `http.per_ip_rate_limit` is not null in production; `http.trusted_proxies` lists the BFF or proxy (rule SEC-4) | `Major` |
| Second factor and step-up | `auth.two_factor.required_for` lists each staff role that reveals personal data or moves money; reveal, permission and money routes carry `#[recent_auth(minutes = 10)]` and `#[not_while_impersonating]` (rules SEC-5 and SEC-6) | `Major` |
| No token in browser storage | Next.js tokens live only in the BFF's `HttpOnly` cookies; no `localStorage` write holds a token name; a Tauri client uses the OS keystore | `Blocker` |
| CORS, CSRF and headers | exact CORS origins; cookie sessions keep CSRF on and Helm is not in `session.csrf_except`; security headers on (the list is in `navree-security-checklist`); HTTPS in production | `Blocker` for Helm in `session.csrf_except`; `Major` otherwise |

### Staff, money and live updates

| Check | How | If it fails |
|---|---|---|
| Personal data is masked | staff lists remove columns with `TableQuery::without_columns` (`#[col(hidden)]` is not a permission); reveal is its own permission on an audited route; searching by contact needs the reveal permission; exports are masked (rule SEC-10) | `Blocker` when a role without reveal sees personal data; `Major` when a reveal is not audited |
| Balances and money routes | each balance change takes a per-account lock inside the unit of work; each money-moving route is idempotent (hard rules 22 and 23) | `Blocker` |
| Live topics | topics carry ids and types only and are scoped by workspace and permission; no nudge inside a request that may roll back; workers broadcast through `dyn Broadcaster` (hard rule 24) | `Major`; `Blocker` when a topic carries another workspace's data |

### Deploy files and clients

| Check | How | If it fails |
|---|---|---|
| Deploy files | no default password and no public database port; `.navree/dock/compose.yaml` is for local development and is not deployed; `navree config:check --env production` exits 0, with `database.migrate_on_boot = false`, `session.secure = true`, a `mail.transport` other than `log` and `observe.metrics_token` set; `/metrics` is denied at the proxy (hard rule 16) | `Blocker` for a default password or a public database port; `Major` otherwise |
| Tauri shell | the checks of [security.md](../../design-to-tauri/references/security.md); cite the Tauri checks of `verify-done.mjs` (hard rule 25) | as in that file |

## Searching a Navree app

- `navree routes --json` lists every route with its access, throttle, guards and audit action.
- `navree config:show --origin` shows where each configuration value comes from.
- `git ls-files .env` prints nothing, and `git ls-files` lists no key file (`*.pem`, `*.key`).
- Search `src/` for `#[public]` (compare with the plan), for `Json<` and `Query<` handler arguments not wrapped in `Valid<`, for `#[allow(` and `#[expect(` added since `base_commit`, and for models in workspace modules without `workspace` in `#[model(..)]`.
- For raw statements and the HTTP client's SSRF switch, read `navree-database` and `navree-cache-and-http-client` for the API names, then search for them.

## Searching a Next.js front end

Search `web/` for `localStorage` near token names, `dangerouslySetInnerHTML`, secrets behind `NEXT_PUBLIC_`, client components that call `NAVREE_API_URL` directly instead of going through the BFF, and `createNavree()` inside a request handler (it is created once).

## Dependencies

Run in the app root and in `web/` when `front_end: next`. A tool that is not installed makes its check `NOT RUN`, never a pass.

| Check | How | If it fails |
|---|---|---|
| Rust lockfile | `Cargo.lock` is committed and not ignored (`git ls-files Cargo.lock`) | `Major` |
| Rust advisories | `cargo audit` and `cargo deny check` | an advisory the app is exposed to, through a route an untrusted caller can reach: `Blocker`; in a build-time or test-only crate: `Minor`; otherwise `Major` |
| Rust sources | no git or path dependency, except a Navree checkout recorded in `STACK.md` (a CLI installed from a clone writes one) | `Major` |
| Next.js lockfile | the lockfile of the package manager in `web/` is committed (`pnpm-lock.yaml` for the SaaS kit) | `Major` |
| Next.js advisories | `pnpm audit --prod` (or the package manager's equivalent), with the same severity rule as Rust | as for Rust advisories |
| Next.js ranges and sources | no `latest` or `*` range, no git dependency, no test tool in `dependencies` | `Minor` |
| Registry settings | `.npmrc` and `.cargo/config.toml` hold no plaintext token | `Blocker` |
| Licences | `cargo deny check licenses` when a policy file exists; a licence scan of the `web/` production dependencies | `Minor`; `Major` for a licence the operator has said is not allowed |
