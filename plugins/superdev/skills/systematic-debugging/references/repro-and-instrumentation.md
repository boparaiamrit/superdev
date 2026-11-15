# Reproduction and instrumentation

Read this when writing `REPRO.md` (phase 1) and when adding diagnostics in phases 2 and 3. A reproduction records the exact input, the expected output, the observed output and the data it needs (rule DBG-2).

## Reproduction recipes

### An HTTP request

Record the request (method, path, headers other than the token, body), the response (status, headers, body) verbatim, and the database state before and after, read with a read-only query: Navigator's `query_database` when it is connected, or a database client against the `database.url` that `navree config:show --origin` shows. Sign in as a seeded account and never paste a real token into `REPRO.md`.

```sh
curl -i -X POST http://127.0.0.1:8080/api/v1/invoices -H "Authorization: Bearer $TOKEN" -H "X-Workspace: sandhu-traders" -H "Content-Type: application/json" -d '{"number":"INV-0042","amount_paise":10000000}'
```

### A browser failure

Write one Playwright test of fewer than 30 lines in `debug/<slug>/`: sign in through the real form as a seeded account, take the steps, and assert with `Expected:` and `Observed:` comments. For a Navree UI page, also save the response HTML, because the fault may be in what the server sent and not in the page.

### A failing test

Run it alone with `cargo test <name> -- --exact`, five times in a shell loop, and record how many runs fail. Five of five is deterministic. One to four is intermittent: find out when it fails (test order, parallel tests, time of day) before looking for a cause. Tests run on SQLite unless `NAVREE_TEST_POSTGRES_URL` or `NAVREE_TEST_MYSQL_URL` is set, so set it when the app runs on PostgreSQL or MySQL.

### A race

Widen the window behind a flag: a delay read from an environment variable that exists only in the instrumented build (rule DBG-4). If the failure then appears every time, the cause is an unprotected critical section, and `ROOT_CAUSE.md` names the defect class as a race. For a balance the missing piece is the per-account lock of hard rule 22.

### Works locally, fails in CI

Compare these, in this order: the Rust toolchain (`rust-version` in `Cargo.toml`; Navree needs 1.95 or newer) against the CI's; the `.env` file (a test booted with `ConfigSources::defaults()` reads the developer's file, and CI has none); the database (SQLite against the real-database URL); the operating system (on Windows, `app.shutdown().await`); the order and parallelism of tests. Reproduce with the CI's toolchain: `cargo +<version> test`.

### A leak

Record the resident memory of the process, call one route 1,000 times, record it again, and repeat three times. The reproduction is the numbers, as growth per 1,000 calls. A rise that continues across the repeats is a leak; a rise that stops is a cache filling.

### A failure only in production

There is no minimal reproduction, so the timeline is the reproduction. For the failing request record the `X-Request-Id`, the time in IST, the log lines with that id, the matching entry in Lighthouse at `/_lighthouse`, the commit of the release, the migrations applied (`navree migrate:status`) and the configuration with secrets redacted (`navree config:show --origin`).

## Instrumentation

Diagnostics observe and do not change behaviour (rule DBG-4). Every one is removed before `fix-applier` runs, and the fix commit contains none.

- **Log lines.** Add temporary lines at the entry and exit of the suspect function with its input and result, through the app's logger. Raise levels in configuration (`navree-config`); `RUST_LOG` is not read. Quote the output in `ROOT_CAUSE.md`, then remove the lines.
- **Queries.** Turn on query logging for one session and count the statements per request. Check `navree-database` for how.
- **Bisecting.** `git bisect start`, `git bisect bad HEAD`, `git bisect good <commit>`, then `git bisect run cargo test <name>` and `git bisect reset`. The commit it names is evidence for `ROOT_CAUSE.md`.
- **Browser trace.** Start Playwright tracing before the failing flow (`context.tracing.start({ screenshots: true, snapshots: true })`) and stop it into `debug/<slug>/trace.zip`. The trace shows every request and every change to the page.
- **CPU profile.** Build the release binary with debug symbols (`CARGO_PROFILE_RELEASE_DEBUG=true cargo build --release`) and run the host's sampling profiler against it. The hottest function is a suspect, not a cause.
- **Debuggers.** A debugger or inspector listens on `127.0.0.1` only. Never bind one to every network interface: it has no authentication.
