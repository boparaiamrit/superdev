# Security suites

The committed suites that prove the controls of [security-foundation](../SKILL.md) (rule SEC-1): what each covers and how to write them. Each is a Rust integration test file under `tests/`, run with `cargo test --test <name>`. Its line goes into `STACK.md` `## Suites` the day the file is created, so `verify-done.mjs --suites` and the QA gate run it.

## The suites

| File | When | Covers |
|---|---|---|
| `tests/security.rs` | every app with sign-in, from step 4 | wrong password and unknown account answer alike; throttles with `Retry-After`; each event of SEC-2 for each kind of client the app has (a browser session is a guest at its next request; a token client's refresh is refused and a reused refresh token ends the family); a second-factor challenge for every role SEC-5 lists; CSRF on cookie sessions (403 `csrf_token_mismatch`); a malformed bearer token on a public route (401); blocked accounts; uploads; incoming webhooks; the body of a forced 500; an audit entry after a write |
| `tests/access.rs` | from the first module with routes | the role matrix from the contracts; record checks; `check_fields` (403 `forbidden_fields`); step-up; escalation guards; masks and reveal; end users refused on staff routes; staff accounts hold their roles after `navree migrate:fresh --seed` |
| `tests/isolation.rs` | from the first workspace module | one isolation suite (`app.isolation_suite`, typed by the module) per module the plan marks `workspace`, with its factory and a create body (`navree-module-conformity`), plus the tests of rules BE-2 and BE-3 |
| `tests/money.rs` | when the plan has balances or payments | hard rules 22 and 23 and the cases of [money-and-ledgers.md](money-and-ledgers.md) |
| `tests/live.rs` | when the plan has live topics | hard rule 24 and the cases of [live-updates.md](live-updates.md), with `send_stream()` |

A module's own tests, one per row of its contract's tables (hard rule 5), stay with the module; these files hold what crosses modules.

## Real-database runs

Tests run in process with `TestApp` on a fresh SQLite file each (`navree-testing`). Row-level security, locks and parallel spends need the app's own database: mark those tests `#[navree::test(database = "postgres")]` (the MySQL form is in `navree-testing`). They run when `NAVREE_TEST_POSTGRES_URL` or `NAVREE_TEST_MYSQL_URL` is set, which `verify-done.mjs --suites` does from `STACK.md` `test_database_url`. Without it they return early with a notice and count as passed, so the proof of hard rules 11 and 22 is a `--suites` run, never a plain `cargo test`.

## Writing rules

- Boot with the test helpers, never with `ConfigSources::defaults()`, which reads the developer's `.env`. The API kit's `tests/support/mod.rs` shows the helpers (`boot`, `sign_in`, `in_workspace`); a minimal app writes its own there, starting with `#![allow(dead_code)]`, the one suppression hard rule 15 allows, since each suite uses only some of them.
- Sign in once per role per suite and reuse the token: sign-in routes are throttled.
- Never weaken a control to pass. Only tests that are not about limits may set `http.per_ip_rate_limit` to null (`Value::Null`); a test about limits waits for `Retry-After`.
- Use the seeded accounts that no other agent is driving (rule BE-14), and label the records a test creates.
- A test that changes shared state (a block, a revoked session, a second factor turned on, a permission removed) does it on an account of its own, or restores it even when an assertion fails.
- Assert statuses and `code`s, never `message` (hard rule 8); after a refused write, assert that the database did not change (hard rule 5).
- Call `app.shutdown().await` at the end of every test (Windows needs it).
