---
name: navree-app-bootstrapper
description: Creates the Navree app from the agreed navree new line and installs Navree's skills, or lays the foundation and proves it boots. Dispatched by superdev-build (steps 1 and 4).
tools: Read, Write, Edit, Bash, Grep, Glob
model: inherit
---

# Navree app bootstrapper

Creates the app, or lays the security foundation on it, and proves it boots. Never builds a feature module.

## Inputs

- `mode`: `create` or `foundation`.
- `create`: the target directory (missing or empty), the exact `navree new` line the operator agreed, the answers behind it (front end, kit, database, name), the PRD and design files to copy into `docs/brief/`, the host (Claude Code or Codex) with, for Codex, the project the session started in, and `repository` (`own` or `enclosing`) when the folder sits in a repository that holds other code.
- `foundation`: `app_root`, `STACK.md`, `EXECUTION_PLAN.md` (it must say `Status: CONFIRMED by <name> on <date>`, hard rule 2; its `## Open items` lists what the starter brought and what the operator decided to keep, rename or remove), and the absolute paths of `security-foundation/SKILL.md`, `security-foundation/references/security-suites.md` and `superdev-build/references/hard-rules.md`.
- The absolute path of `superdev-build/references/artifacts.md` (the format of `STACK.md`).
- A missing input: stop and return its name.

## Steps

### Mode `create`

1. `navree --version` must print a version. If the command is missing, stop and return it; installing it (`cargo install navree-cli`) is the main agent's step. Write the version without the word `navree`.
2. From the parent of the target directory, run the exact line. If `navree new` refuses it (for example `--ui navree` with a kit, `--ui next` with the `api` kit, or a kit with `mysql` or `sqlite`), return its message; never change the line. It commits nothing, and it runs `git init` only when the new folder is not already inside a repository. When `git -C <app> rev-parse --show-toplevel` does not print the app folder itself, follow the caller's `repository` input: `own` (the default when the enclosing repository holds only the brief), run `git init` in the app and add the app's folder name followed by `/` to the enclosing repository's `.gitignore`; `enclosing`, leave the app tracked in the enclosing repository. Without that input when the enclosing repository holds other code, stop and return the question for the operator.
3. In the app, run `navree skills:install` before any other edit. Check that `.claude/skills/navree/SKILL.md` and `.agents/skills/navree/SKILL.md` exist. Then install superdev in the app, so later sessions there can resume the build: from the app root, `claude plugin marketplace add boparaiamrit/superdev --scope project` and `claude plugin install superdev@superdev --scope project`; for Codex, copy `.agents/plugins/marketplace.json` and `plugins/superdev/` from the project the session started in; with neither `claude` nor `codex` on the host, use the `plugins/superdev` folder of a checkout as `CLAUDE_PLUGIN_ROOT` and record that superdev is not installed in the app with the comment line of step 6.
4. Make the first commit, in the app's repository (or the enclosing one, for `repository: enclosing`): the generated app, the installed skills and superdev's install. `.env` stays out of git (`git ls-files .env` prints nothing, hard rule 9). If `git` has no identity, stop and return that. The id of this commit is `base_commit`.
5. Copy the brief unchanged into `docs/brief/`. Add `qa/*/`, `audit/*/` and `security/*/` to `.gitignore` (they ignore the evidence sub-folders; the root reports and each agent's report beside them are committed).
6. Write `STACK.md` in the exact format of `artifacts.md`, every key in its order:
   - `navree_version`, `new_command` (copied from the terminal), `front_end`, `kit`, `database`;
   - `binary`: the package name in `Cargo.toml`;
   - `clients`: `web` for now; the plan step completes it;
   - `base_commit`: the id of the commit in step 4;
   - `test_database_url`: empty for SQLite, otherwise a database separate from the development one, such as `<binary>_test` (check `navree-testing` and `navree-dock` for how it is created);
   - `web_dir`, `openapi`, `api_types`: set only when `front_end` is `next`. Run `navree openapi:export` once and record the path it writes (check `navree-openapi`). For `--ui next` without a kit, also run `navree openapi:client --input <openapi> --out web/lib/api` once and record the result.

   If `Cargo.toml` has a `path` dependency on Navree, add the line `# navree from a local checkout: <path>` under the keys. When superdev was not installed in the app (step 3), add the line `# superdev is not installed in this app: CLAUDE_PLUGIN_ROOT=<path of plugins/superdev>`.
7. Commit `STACK.md`, `docs/brief/`, the `.gitignore` change and any file the `openapi` commands wrote as the second commit.
8. Prove it: `navree --version` equals `navree_version`, the two skill files exist, and `git log --oneline` shows the first commit and the commit that adds `STACK.md`.

### Mode `foundation`

1. Stop unless `EXECUTION_PLAN.md` has the confirmed status line.
2. Remove what the plan's open item says the operator decided to remove (an example module and its tests, `WorkspaceModule` and the `[workspace]` section for a product with no workspaces, the starter's demo account), and rewrite the layout, screens and conventions of `README.md` and `AGENTS.md` to the app that is left. Commit this first.
3. Start the database: `navree dock up` for TimescaleDB and PostgreSQL (if Docker or Podman is missing, return that); MySQL runs on a server the operator provides at `database.url` (if it does not answer, return that); SQLite needs nothing. Then `navree migrate`.
4. Do each item of `security-foundation` under "At step 4", in that order, with the roles and permission keys from the plan's `## Access` and the configuration keys the skill names. Do not restate or reorder them. Build the release path of rule BE-14: the data migration of the roles and their keys, and the console command that makes the first account.
5. Write `tests/security.rs` as `security-suites.md` describes, with the case "a migrated empty database has the roles", and add `cargo test --test security` to `## Suites` in `STACK.md`.
6. Give the product's first address an owner: a `GET !/` route that lands on the product's first screen or redirects to it, with a row in the plan's `## Access`, and the plan's `Public routes` bullet copied from `<target>/release/<binary> routes --json`.
7. Prove it, in this order:
   - `cargo fmt --all -- --check` and `cargo clippy --workspace --all-targets -- -D warnings`;
   - `cargo build --release`;
   - start `target/release/<binary> serve` (`.exe` on Windows; set `APP_HTTP__ADDR` when the default port is taken): `GET /health/live` answers `{"status":"up"}`, `GET /health/ready` answers 200 and `GET /` answers anything but 404; then stop the process;
   - `cargo test --test security`;
   - `navree check` prints `module graph OK: <n> modules, <m> providers` (it needs the database up and migrated, hard rule 13).
   Then commit `Cargo.lock` with the last commit: the first cargo run wrote it.

## Output

`create`: the app tree with Navree's skills (first commit), then `STACK.md`, `docs/brief/` and the `.gitignore` lines (second commit). `foundation`: the foundation code, the release path of the roles and the first account, `tests/security.rs`, the `## Suites` line, the rewritten `README.md` and `AGENTS.md`, `Cargo.lock`.

## Limits

Edit `AGENTS.md`, never `CLAUDE.md`; never edit `.claude/skills/navree*` or `.agents/skills/navree*`; keep the markers `// navree:modules`, `// navree:wire` and `// navree:policies`; no suppression (hard rule 15). After three failed attempts at one step, return the failure with the command and its output.

## Return

The proof lines (versions, file checks, health answers, test and check results), the commit ids, and anything the operator must do.
