# Dynamic probes

Read this in step 3. `dynamic-auditor` runs these probes against the running release binary on a fresh seed (`navree migrate:fresh --seed`), with two workspaces (for example Sandhu Traders, Ludhiana and Sharma Textiles, Pune) and one seeded account per role from `EXECUTION_PLAN.md` `## Demo accounts`. The evidence of each probe is the request, the status and an excerpt of the response, saved under `security/dynamic-auditor/`. A probe that could not run goes under `## Probes not run` (rule SR-5). The last column is the severity a failing probe gets, on the scale in [artifacts.md](../../superdev-build/references/artifacts.md).

## Setup

1. `GET /health/live` answers `{"status":"up"}` and `GET /health/ready` answers 200. If either fails, stop.
2. Sign in once per account the way the app's people do. A Navree UI app: through its sign-in page, keeping the session cookie and the CSRF token; its probes post the app's forms, not JSON routes. A token client: through the sign-in route (`navree routes --json` lists it; a Next.js app signs in through the BFF's `/api/auth/login`), keeping the bearer token; tokens last 900 s by default, so sign in again when a probe gets an unexpected 401. A probe that names a kind of client the app does not have is left out, not reported.
3. The sign-in throttle probe runs last, with an unknown e-mail address, and nothing signs in again until `Retry-After` has passed.
4. The probes marked "production configuration" run after restarting the binary with that configuration. The data from the seed stays in place.

## Probes

| Probe | How | Expected | If not |
|---|---|---|---|
| Another workspace's record | read, change and delete a record of workspace B signed in as a member of workspace A (the kits name the workspace in the `X-Workspace` header) | 404 with the same body as an id that does not exist; the record is unchanged afterwards. A non-workspace model answers 403 for another user's record; accept that only when the contract records it (rule BE-3) | the record or its data returned or changed: `Blocker`; a 403 or a different body, which shows the record exists: `Major` |
| A workspace the caller is not in | send `X-Workspace` naming a workspace the caller does not belong to, then none, then an unknown one | 403 `not_a_member`; 400 `workspace_required`; 404 | data returned: `Blocker`; another answer: `Minor` |
| Bad bearer tokens | call a protected route (`GET /api/auth/me`, which every Navree app has, a Navree UI app included) and a public route with a missing, malformed, expired and wrong-signature token | 401 on every route, public ones included | a 200 on a protected route: `Blocker`; a 200 on a public route: `Minor` |
| Bad body | post an empty body and a body of the wrong type to a JSON route; for a Navree UI app, post each form empty and with wrong values | JSON: 400 `validation_failed` naming the field, never 422; a Navree UI form: 422 with the errors under the fields (hard rule 8) | a record stored: `Major`; another status: `Minor` |
| Oversized payload and deep JSON | send a JSON body larger than the contract ceiling (default 64 KB) and a JSON object nested deeper than 16 levels to a write route (hard rule 29) | 413 for oversized body; 400 `validation_failed` for deep nesting; no crash or hang | a 200 or 500, or a record stored: `Major` |
| Script and URI in plain text | submit `<script>alert(1)</script>` and `javascript:alert(1)` in plain-text fields, and `__proto__` or `constructor` keys on Next.js BFF JSON routes (hard rule 29) | 400 `validation_failed` (JSON) or 422 (Navree UI form); nothing executable stored or rendered | executable markup or script rendered: `Blocker`; stored without rejection: `Major` |
| Unbounded page size and bad cursor | call list routes with `per_page=101` and cursor streams with a malformed cursor token (rule BE-7, hard rule 29) | 400 `validation_failed` | full table returned or 500: `Major` |
| Hierarchy cycle | on any model with a parent or manager reference, submit `parent_id = id` and an `A -> B -> A` cycle (hard rule 29) | 400 or 409 with its contract error `code`; existing links unchanged | cycle stored or server hangs: `Major` |
| Sign-in throttle | repeat sign-in with a wrong password for an unknown address | 429 with `Retry-After` and `code` `too_many_login_attempts`; no `X-RateLimit-*` headers are expected | no 429 within 30 attempts: `Major` |
| Security headers | read the headers of a page and of an API response | `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` and `Strict-Transport-Security` present on both, the ones Navree sends (`navree-security-checklist`, headers group); no `Server` or `X-Powered-By` header, and no header naming the framework or its version | a missing header of the five: `Major` |
| Cookie flags | read `Set-Cookie` after sign-in (the session cookie of a Navree UI app; `navree_at` and `navree_rt` of a Next.js app) | `HttpOnly`; `Secure` under the production configuration; `SameSite` set | `Major` |
| CSRF | post a form without the token to a cookie-session app; send a non-GET request through the BFF with a foreign `Origin` | 403 `csrf_token_mismatch`; 403 `invalid_origin` | `Blocker` |
| CORS | send a preflight request from a foreign origin | the foreign origin is not allowed | `Major` |
| A forced 500 | cause one unhandled error without editing the app, for example by switching off a service one route depends on | status 500, `code` `internal_error`, no SQL, path or stack trace in the body, and an `X-Request-Id` header | `Major` |
| Redirect parameters | pass an absolute URL of another site in each `redirect` or `return` parameter | the app redirects only to its own paths | `Major` |
| Incoming webhooks | send an unsigned and a wrongly signed payload to each incoming webhook route | refused with 401 or 403 | `Blocker` |
| Staff panel and monitoring | request `/admin` signed out and as a role without `helm.view`; request `/_lighthouse` signed out; request `/_logbook` on the release binary | refused or sent to sign-in; `/_logbook` not served (it is a debug-build tool; check `navree-logbook` for what a release build answers) and Lighthouse reachable only by the people the plan names (check `navree-lighthouse`) | a page that shows data to the wrong person: `Blocker`; otherwise `Major` |
| Metrics (production configuration) | `GET /metrics` without the token | refused | `Major` |
| OpenAPI (production configuration) | `GET /api/openapi.json` and `GET /api/docs` | off unless the plan wants them, and public only on purpose | an unplanned public document: `Major` |
| Second factor | sign in with the password only, as a staff account whose role is in `auth.two_factor.required_for` | a second-factor challenge, not a session | `Major` |
| Sign-out | sign out (and, where the product has them, end a session from another device and block an account); then, for a browser session, request a page with the same cookie, and for a token client, use the refresh token | as hard rule 21 says: the session's next request is a guest; the refresh is refused at once (the access token lives until it expires) | a session that still works, or a refresh that works: `Blocker` |
| Refresh-token reuse (token clients) | use a rotated refresh token a second time | refused, and the newest refresh token of that session is refused too | `Blocker` |
| Row-level security role (PostgreSQL and TimescaleDB) | as the app's database role run `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user` | `f` and `f` (hard rule 11) | `Major` |

## Probes not run

End the report with a section listing each probe that could not run and why: a second workspace missing from the seed, the app unreachable, a production configuration not available. These are `NOT RUN`, not findings (rule SR-5). Like every `NOT RUN` in superdev, each blocks until the operator accepts it in `ACCEPTANCES.md`, and its line then ends with the `ACC-n`.
