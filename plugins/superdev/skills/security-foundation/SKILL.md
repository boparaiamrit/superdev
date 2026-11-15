---
name: security-foundation
description: Use when an app has sign-in, staff, roles and permissions, personal data, money or balances, or live updates, at step 4 of a superdev build and whenever a module adds a sign-in method, a permission, a payment path, a balance, a contact field or a live topic. Lists each control, what Navree provides, what the app still builds, and the committed test that proves it.
---

# Security foundation

This skill says which security controls every build implements, at step 4 (the foundation) and then in every module: what Navree provides for each, what the app still builds, and the committed test that proves it. `security-review-and-fix` checks the result at step 7; this skill builds it. Navree's own list of what to check before shipping is the `navree-security-checklist` skill; read it, with `navree-auth`, `navree-access-control` and `navree-workspaces`, before step 4. Backend rules (BE-1 to BE-16) are in [backend-on-navree](../backend-on-navree/SKILL.md); a hard rule cited by number is in [hard-rules.md](../superdev-build/references/hard-rules.md).

## Proof rule

**SEC-1** A control exists when a committed test exercises it: `TestApp` over HTTP, or the running app for the real-database and browser suites. An attribute, a config line or a guard is not proof. The suites and how to write them are in [references/security-suites.md](references/security-suites.md).
Proof: every row of `## Controls` that the plan's `## Security` section lists has its test, and the test's file is a line of `STACK.md` `## Suites`.

## At step 4

The plan's `## Security` section (written at step 3) lists the rows of `## Controls` that apply, the personal-data fields to mask, the balances and the live topics. Before the first feature module, the foundation gets:

1. `AuditModule` registered and `audit:prune` scheduled; the minimal app's root registers neither (hard rule 12).
2. `auth.registration = false` unless the PRD has sign-up.
3. For token clients, the access-token lifetime left at 900 s or shorter (hard rule 21; the setting is in `navree-auth`).
4. `auth.two_factor.required_for` listing every staff role that can reveal personal data, change permissions or move money (SEC-5).
5. Global staff roles, their keys and the staff accounts that hold them, created by the demo seeder (rule BE-14), and workspace roles with their keys in `config/app.toml` (`[workspace.roles.<role>]`, `permissions = [..]`), per [references/staff-and-personal-data.md](references/staff-and-personal-data.md).
6. The ability rules in `src/abilities.rs`, each with a unit test (rule BE-5).
7. Stricter throttles on the sign-in, code and refresh routes (SEC-4).
8. `http.trusted_proxies` naming the proxy or BFF in front of the app, so the client address is real.
9. Exact CORS origins (the setting is in `navree-security-checklist`, headers group).
10. `session.secure` set to `true` in the production configuration (hard rule 16).
11. The first suite, `tests/security.rs`, and its line `cargo test --test security` in `STACK.md` `## Suites`.

The step's proof is the one `superdev-build` gives for step 4.

## In every module

A module carries its share of these controls in its contract and its tests. Each addition goes into a suite of [references/security-suites.md](references/security-suites.md), and the plan's `## Security` section is updated.

| The module adds | Declared in | Test |
|---|---|---|
| permission keys | the contract's `## Abilities and permissions`; the workspace roles that hold them in `config/app.toml`, the staff roles that hold them in the demo seeder and the release step (rule BE-14) | `tests/access.rs`: the role matrix gains the module's routes |
| masked fields | the contract's `## Models` and the resource structs (SEC-10) | `tests/access.rs`: no seeded contact value in a response to a role without reveal |
| step-up routes | the contract's `## Routes` (SEC-6) | `tests/access.rs` |
| idempotent routes | the contract's `## Routes` and `## Refusals` (hard rule 23) | `tests/money.rs` |
| ledger writes | the contract's `## Side effects`; the reconciliation's checks (SEC-11) | `tests/money.rs` |
| live topics | the contract's `## Side effects` (SEC-12) | `tests/live.rs` |
| uploads, incoming webhooks | the contract's `## Routes` | `tests/security.rs` |

## Controls

| Control | What Navree provides | What the app still does | Test |
|---|---|---|---|
| Password sign-in, access and refresh tokens | `AuthModule`: Argon2id, an HS256 access token of 900 s, refresh tokens that rotate, reuse revokes the family (`navree-auth`) | SEC-2; sign-up off unless the PRD asks | token clients: `tests/security.rs`: a reused refresh token is refused and the family ends |
| Browser sessions | Navree UI: `SessionModule` with CSRF protection; sign-out, ending a session from another device, a password change or reset and signing out everywhere end the session at once (`navree-auth`); Next.js: the BFF keeps tokens in `HttpOnly` cookies and refuses a non-GET from a foreign origin with 403 `invalid_origin` (`navree-frontend-next`) | `session.secure` on in production (step 4, item 10); never a token in `localStorage` or a readable cookie | `tests/security.rs`: a form post without the CSRF token answers 403 `csrf_token_mismatch`; after sign-out the same cookie's next request is a guest |
| Stale tokens | an invalid bearer token is 401 on every route, public ones too (`navree-auth`) | clients drop a stale token before calling sign-in or the probes | `tests/security.rs`: a malformed token on a public route answers 401 |
| Blocked accounts | no block feature is documented (`navree-auth`) | SEC-3 | `tests/security.rs` |
| Rate limits | 600 requests a minute per IP; `#[throttle(limit, per)]` per route; only `Retry-After` is sent, no `X-RateLimit-*` headers; `too_many_login_attempts`; counters per process unless `http.rate_limit_store = "redis"` (`navree-controllers-and-routing`, `navree-redis`) | SEC-4 | `tests/security.rs`: 429 with `Retry-After` |
| Second factor | TOTP and recovery codes, enforced per role with `auth.two_factor.required_for` (`navree-auth`) | SEC-5 | `tests/security.rs`: a sign-in as a listed staff role returns a challenge |
| Passkeys, magic links, emailed codes, social sign-in, single sign-on | `[auth.passkeys]` with `rp_id` and `origins`, `auth.magic_link.enabled`, `auth.otp.enabled`, the feature `social`, `SsoModule` (`navree-auth`, `navree-social`, `navree-sso`) | turn on only what the PRD asks; passkey `rp_id` and `origins` exact | QA gate, in a browser |
| Step-up | `#[recent_auth(minutes = 10)]`, `#[not_while_impersonating]` (`navree-auth`) | SEC-6 | `tests/access.rs` |
| Custom sign-in and API keys | no built-in API keys (add a `Strategy`); every custom sign-in ends with `AuthService::sign_in` (`navree-auth`) | build them only when the PRD needs them | `tests/security.rs` |
| Route access, records, lists, fields | `#[can]`, `Accessible`, `check_fields` (403 `forbidden_fields`) (`navree-access-control`) | hard rule 6; rule BE-5 | `tests/access.rs` |
| Roles and permission keys | global roles (`AccessModule`, whose super-admin role is `admin`); workspace roles `owner`, `admin`, `member`, `viewer` with keys from config (`navree-access-control`, `navree-workspaces`) | SEC-7, SEC-9 | `tests/access.rs`: the role matrix from the contracts |
| Escalation guards | not provided | SEC-8 | `tests/access.rs` |
| Staff panel | Helm at `/admin`, which asks the app's abilities (`navree-helm`) | `helm.view` only for staff roles; never put Helm in `session.csrf_except` | QA gate role sweep |
| Masked personal data | a column removed by permission with `TableQuery::without_columns` (`#[col(hidden)]` is not a permission); audit entries in the request's transaction with `record_in` (`navree-ui`, `navree-security-checklist`) | SEC-10 | `tests/access.rs` |
| Audit log | `AuditModule`; no tamper protection, no export or forwarding (`navree-security-checklist`) | hard rule 12; a PRD that needs tamper evidence or an export records an open item `O-n` | `tests/security.rs`: a write, then its entry |
| Workspace isolation | scoping, row-level security on PostgreSQL only, isolation suites (`navree-workspaces`, `navree-module-conformity`) | hard rules 10 and 11 | `tests/isolation.rs` |
| Balances | nothing | hard rule 22; [money-and-ledgers.md](references/money-and-ledgers.md) | `tests/money.rs` |
| Idempotency | nothing for incoming requests | hard rule 23 | `tests/money.rs` |
| Payments | `navree-billing` (opt-in feature `billing`): Stripe and Paddle, and their webhooks | SEC-11 | `tests/money.rs` |
| Live updates | `RealtimeModule`; a nudge in a unit of work waits for the commit; workers broadcast through `dyn Broadcaster` (`navree-events-and-broadcasting`) | hard rule 24; SEC-12 | `tests/live.rs` |
| Headers, CORS, HTTPS | the headers group of `navree-security-checklist` | SEC-13 | `dynamic-auditor` |
| Secrets | `.env` and `APP_*` variables only, `Secret<T>`, `navree config:check` (`navree-config`) | hard rule 9 | `navree config:check --env production` exits 0 |
| Uploads | `store_upload` with `UploadRules`; keyed upload responses, required since 1.2.1 (`navree-storage`) | a directory per workspace | `tests/security.rs`: an upload outside the rules is refused |
| Outgoing HTTP | the HTTP client's SSRF guard (`navree-cache-and-http-client`) | keep the guard on | `static-auditor` |
| Incoming webhooks | verified incoming webhooks (`navree-webhooks`) | every incoming webhook goes through it | `tests/security.rs`: an unsigned payload is refused |
| Errors and logs | one error shape; keeping internals out of messages is the app's job (`navree-errors-and-responses`) | SEC-13 | `tests/security.rs`: a forced 500 has `code` `internal_error` and no internals |
| Metrics | `/metrics` is public unless `observe.metrics_token` is set (`navree-deployment`) | set the token; deny `/metrics` at the proxy | the [deploy checklist](../superdev-build/references/deploy-checklist.md) |
| Dependencies | the checklist says to scan them (`navree-security-checklist`) | `security-review-and-fix` | `dependency-auditor` |

## Rules

SEC-1 is the proof rule above.

**SEC-2** Every event that ends someone's access (sign-out, sign-out everywhere, a revoked device, a block, a disabled staff member, a password change or reset) ends it as hard rule 21 says for each kind of client the app has. The app wires each event Navree does not end by itself (a block, a disabled staff member) to the call that ends the person's sessions and refresh-token families (check `navree-auth`: account flows, sessions); a token client that needs access to end at once records an open item `O-n` and keeps the lifetime short.
Proof: `tests/security.rs`, one test per event and kind of client, as hard rule 21's Verify line says.

**SEC-3** Blocking an account needs a reason, ends every session and refresh-token family at once (SEC-2), and tells the person the reason when they sign in or refresh; "blocked" is shown only after the first factor succeeds, so the answer never confirms that an account exists. Navree documents no block feature: check `navree-auth` (account flows, sessions) at build time and build it as a status that sign-in and refresh check; the block ends the sessions and families in the same unit of work and mails the person.
Proof: `tests/security.rs`: after a block the person's browser session is a guest at its next request and a refresh is refused at once (for the clients the app has); a sign-in with the right password returns the reason; a sign-in with a wrong password answers like any wrong password.

**SEC-4** The sign-in, code and refresh routes have stricter limits than the global one (check `navree-auth` for the limits Navree's own routes carry and how to tighten them; `#[throttle(limit, per)]` on the app's routes). The per-IP limit is never switched off in production, and `http.trusted_proxies` makes the client address real. An unknown account and a wrong password answer with the same status, `code` and words, in the same time. Tests wait for `Retry-After` and never raise a limit to pass.
Proof: `tests/security.rs`: repeated sign-ins get 429 `too_many_login_attempts` with `Retry-After`; an unknown email and a wrong password get identical bodies, and the median times of five attempts each are within a factor of 2.

**SEC-5** Two-factor is required for every staff role that can reveal personal data, change permissions or move money: `auth.two_factor.required_for` lists them (`navree-auth`). Turning a second factor on or off, or making new recovery codes, sends the person a security notice ([references/live-updates.md](references/live-updates.md)).
Proof: `tests/security.rs`: a password sign-in as each listed role returns a second-factor challenge, not tokens; the notice is found with the `array` mail transport.

**SEC-6** Revealing personal data, changing permissions or roles, adjusting money and changing a second factor need a recent sign-in and refuse impersonation sessions: `#[recent_auth(minutes = 10)]` and `#[not_while_impersonating]` on the app's routes that do so; for Navree's own two-factor routes, check `navree-auth` for the step-up they already require.
Proof: `tests/access.rs`: each such route refuses a session signed in more than 10 minutes earlier and an impersonation session, with the status and `code` that `navree-auth` documents, recorded in the contract's `## Refusals`.

**SEC-7** Roles bundle permission keys; code checks keys and abilities, never role names (rule BE-5). Screens hide what the rules deny (rules NUI-8 and NX-4) and the server still checks every request.
Proof: `tests/access.rs`: the role matrix, every route of every contract against every role, with the status the contract gives.

**SEC-8** Nobody grants a permission they do not hold, changes their own role or disables themselves; a workspace always keeps one `owner`, checked in the request's unit of work under a lock so that two owners cannot demote each other at once; a permission change notifies the person. Navree provides none of these guards. Their statuses, codes and tests are in [references/staff-and-personal-data.md](references/staff-and-personal-data.md).
Proof: `tests/access.rs`: each guard is refused with its status and `code`.

**SEC-9** End users never hold staff permissions. Staff-only keys are granted to global staff roles, which only staff accounts hold (the seeder creates the roles, grants and holders in development, a release step in production: rule BE-14); end users get workspace roles only, and no workspace role holds a staff-only key.
Proof: `tests/access.rs`: a workspace `owner` is refused on every staff route; no `[workspace.roles.*]` section of `config/app.toml` lists a key that the plan marks staff-only.

**SEC-10** Personal data is masked by default and revealed on purpose: masks in every list and detail, reveal as its own permission and route audited in the same transaction, contact search only with the reveal permission, exports masked, no contact data in URLs. The mask formats, the reveal flow and the tests are in [references/staff-and-personal-data.md](references/staff-and-personal-data.md).
Proof: the `tests/access.rs` cases of that reference.

**SEC-11** Ledgers, lots, payments and the reconciliation follow [references/money-and-ledgers.md](references/money-and-ledgers.md), with hard rules 22 and 23.
Proof: the `tests/money.rs` cases of that reference.

**SEC-12** Live topics carry ids and types only, are scoped by workspace and by permission, and follow [references/live-updates.md](references/live-updates.md) with hard rule 24.
Proof: `tests/live.rs`: a member of another workspace and a role without the topic's permission receive nothing.

**SEC-13** Hardening: exact CORS origins; security headers on; HTTPS in production; cookie sessions keep CSRF on; `/metrics` protected by `observe.metrics_token` and denied at the proxy; no SQL, paths or stack traces in error messages; no secrets, tokens or personal data in logs or audit metadata; outgoing HTTP keeps the SSRF guard; row-level security runs under an ordinary database role (hard rule 11). `navree-security-checklist` holds the switches.
Proof: the `dynamic-auditor` probes of `security-review-and-fix` pass, and `navree config:check --env production` exits 0 on the deploy configuration.

## Reference files

| File | Read when |
|---|---|
| [references/staff-and-personal-data.md](references/staff-and-personal-data.md) | planning roles and permission keys (step 3), the foundation (step 4), and any module with staff screens, contact fields or exports |
| [references/money-and-ledgers.md](references/money-and-ledgers.md) | any balance, purchase, payment, refund or credit adjustment |
| [references/live-updates.md](references/live-updates.md) | any live region, real-time channel or notification |
| [references/security-suites.md](references/security-suites.md) | writing or extending a committed suite |
