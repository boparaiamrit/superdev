---
name: superdev-build
description: Use when building a product from a PRD (and a design or a prototype) as a Navree app, from an empty folder to a released, verified app, or when resuming such a build. Runs the ten steps in order, writes the plan and each module's contract to disk before code, and proves every step.
---

# Superdev build

Superdev is the order of work, the files written to disk, the rules and the proof each step needs to take a product from a brief and a design to a released, verified Navree app. Navree's own skills hold the framework facts: when a step needs one, read the Navree skill this file names, starting with the `navree` skill, which indexes the rest. Run the steps below in order. A step is finished when its proof is on disk, and the next step starts only then.

## Before you start

- Read [the hard rules](references/hard-rules.md) once. The steps cite them by number.
- If the app already exists and has `.claude/memory/superdev-learned/INDEX.md`, read it and the lessons it lists that apply to this build ([superdev-self-learning](../superdev-self-learning/SKILL.md)).
- To resume a build, read `STACK.md` and the `## Build order` table of `EXECUTION_PLAN.md`, and continue at the first step or module that has no proof.
- When the host supports MCP servers, you may connect Navigator, Navree's server for coding agents: `claude mcp add navree -- navree mcp`.
- A Navree skill the host has not loaded is read from the app's `.claude/skills/<skill>/SKILL.md` (Codex: `.agents/skills/<skill>/SKILL.md`).
- When you dispatch an agent, pass absolute paths built from `${CLAUDE_PLUGIN_ROOT}` (rule BLD-4). In Codex, `${CLAUDE_PLUGIN_ROOT}` stands for the `plugins/superdev` folder the plugin was installed from.

## Step 1. Navree and the app

- **Do:** confirm the Navree CLI; for a new app, agree the `navree new` line with the operator, create the app, install Navree's skills and superdev in it, and commit; for an existing Navree app, install Navree's skills and commit (items 10 and 11). Then write `STACK.md`, copy the brief and commit. For a new app, dispatch `navree-app-bootstrapper` in mode `create` with the agreed line, or run its steps yourself.
- **Writes:** the app tree, Navree's skills in `.claude/skills/` and `.agents/skills/`, the first commit (its id is `base_commit`), then `STACK.md`, `docs/brief/` and the `.gitignore` lines in a second commit.
- **Proof:** `navree --version` prints `navree <navree_version>` as written in `STACK.md`; `.claude/skills/navree/SKILL.md` and `.agents/skills/navree/SKILL.md` exist; `git log --oneline` shows the `base_commit` commit and the commit that adds `STACK.md`.

1. When `navree --version` fails, install the CLI with `cargo install navree-cli` (hard rule 1). A project on one of the stacks superdev 2.1.0 served (it has `nest-cli.json` or `artisan` at its root) is not built here: stop and point the operator to superdev 2.1.0 (`claude plugin marketplace add boparaiamrit/superdev#v2.1.0 --scope project`).
2. A new app: ask the operator these questions and write down the answers. Front end: `navree` (Navree UI, drawn on the server; the default), `next` (Next.js on the Navree API) or `none` (the API alone). Kit: none (the minimal app; the default), `saas` (API and Next.js front end) or `api` (API alone); a product with workspaces and a Next.js front end takes `--kit saas`, which brings the workspace routes, `X-Workspace` and a component kit. Database: `timescaledb` (the default), `postgres`, `mysql` or `sqlite`. App name: lower-case letters, digits, `-` and `_`.
3. The CLI refuses `--ui navree` with any kit, `--ui next` with `--kit api`, and any kit with `--database mysql` or `--database sqlite`; settle these with the operator before running anything. The `micro` kit is not used. `navree-new-app` has the options.
4. Run the line from the folder this session started in, which holds the brief: `navree new <name>` creates `<name>/` there, which must be missing or empty, and commits nothing. It runs `git init` only when `<name>/` is not already inside a repository. So when `git -C <name> rev-parse --show-toplevel` does not print the `<name>/` folder itself, the app sits in an enclosing repository. If that repository holds only the brief, make the app a repository of its own: `git init` in `<name>/`, and `<name>/` added to the enclosing `.gitignore`. If it holds other code (a team's monorepo), first ask the operator whether to track the app in it or give it its own repository, and record the answer. From then on, work in `<name>/`, the app root.
5. Run `navree skills:install` before any other edit. Edit `AGENTS.md`, never `CLAUDE.md`, and never the Navree skill folders (hard rule 17).
6. A new app: the starter brings working example code. Read the app's `AGENTS.md` and `git ls-files src tests`, and list what the starter brings that the product does not name: an example module, workspaces (`WorkspaceModule`, `[workspace]` in `config/app.toml`), a home page, demo accounts, example tests. For each, decide with the operator whether the product keeps it, renames it or removes it, and write their answers down (rule BLD-6). `plan-architect` records the list and the answers under `## Open items` at step 3, and step 4 removes what was decided, as its first commit: a generator never overwrites a file that is there, so a starter module with the product's own name blocks `navree make:module`.
7. Superdev is installed per project, so install it in the app too, and ask the operator to open later sessions of this build in the app root. From the app root: `claude plugin marketplace add boparaiamrit/superdev --scope project`, then `claude plugin install superdev@superdev --scope project`. In Codex, copy `.agents/plugins/marketplace.json` and `plugins/superdev/` from the folder this session started in. With neither `claude` nor `codex` on this host, set `CLAUDE_PLUGIN_ROOT` to the folder `plugins/superdev` of a checkout, and record that superdev is not installed in the app with the comment line that [artifacts.md](references/artifacts.md) gives, so that every later session sets it again.
8. Commit, in the app's repository (or the enclosing one, when the operator chose to track the app there), the generated app, the installed skills and what item 7 added, with `.env` left out of git (hard rule 9); this first commit's id is `base_commit`. `navree new` does not run Cargo, so there is no `Cargo.lock` yet: step 4 commits it.
9. Write `STACK.md` per [artifacts.md](references/artifacts.md) (`clients: web` until step 3), copy the PRD and the design files unchanged into `docs/brief/`, add `qa/*/`, `audit/*/` and `security/*/` to `.gitignore` (they ignore the evidence sub-folders; the reports beside them are committed, as [artifacts.md](references/artifacts.md) lists), and commit. A CLI installed from a clone makes the app depend on that checkout by path; record it with the comment line that [artifacts.md](references/artifacts.md) gives.
10. An existing Navree app: the session starts in its root, where superdev is installed; skip items 2 to 4 and 6 to 8. Commit the operator's uncommitted work first, with their agreement. Run `navree skills:install` and commit what it changed; that commit, or `HEAD` when nothing changed, is `base_commit`, so the sweeps judge only what the build adds. In `STACK.md`, leave `new_command` empty and read the other keys from the app, then confirm them with the operator: `front_end` is `next` with a `web/` front end, `navree` with Navree UI screens under `src/ui/`, else `none`; `kit` is `saas` (with `web/`) or `api` (without) when `src/platform.rs` exists, else `none`; `database` from `database.url` in `config/app.toml` (`postgres://` is `timescaledb` unless `dock.toml` says `timescaledb = false`). The installed skills describe the CLI's version: when the `navree` version in the app's `Cargo.toml` differs from it, settle with the operator which one changes, before step 2.
11. For an existing app, the PRD may cover only the change. The plan lists the modules this build adds or changes; an existing module gets a contract (step 5) when the build first changes it, and the modules it does not touch get none.

## Step 2. Digests

- **Do:** extract the PRD and the design into two digests, separately and without decisions. Dispatch `prd-analyst` and `design-inventory` with the files in `docs/brief/`.
- **Writes:** `PRD_DIGEST.md`, `DESIGN_DIGEST.md` (without a design, the plan says so in one line instead).
- **Proof:** both files have every heading of their format in [artifacts.md](references/artifacts.md).

A digest records what its source says, with the section or screen it came from. What the source leaves open goes under `## Questions`; the digest does not choose.

## Step 3. Plan

- **Do:** dispatch `gap-auditor` to list where the PRD and the design disagree; put each finding to the operator and write their decisions; dispatch `plan-architect` to write the plan; complete `clients` in `STACK.md`; show the operator the summary (modules, build order, access, open items) and wait for their answer.
- **Writes:** `GAPS.md`, `EXECUTION_PLAN.md`, `STACK.md` (`clients`).
- **Proof:** `EXECUTION_PLAN.md` has the line `Status: CONFIRMED by <operator> on <YYYY-MM-DD>`, written after the operator said so, committed before any module code (hard rule 2).

- `GAPS.md` `## Decisions` holds the operator's words with their name and the date (rule BLD-6); `plan-architect` reads the decisions, not the findings. A revision of the plan follows rule BLD-3.
- Without a design there is nothing to compare: skip `gap-auditor` and write `GAPS.md` with `None.` under `## Findings` and `## Decisions`.
- `plan-architect` also gets the list of what the starter brings and the operator's answers (step 1, item 6), and records them as one item under `## Open items`; step 4 does what they say.
- The plan's `## Security` section lists the rows of the controls table in [security-foundation](../security-foundation/SKILL.md) that apply, the personal-data fields to mask, the balances and the live topics.
- `clients`: `web` always; `admin` when the PRD has staff work (staff are defined in [security-foundation](../security-foundation/SKILL.md): people of the company that operates the product, never its users); a Tauri client when the PRD asks for a phone or desktop app, once the questions in [design-to-tauri](../design-to-tauri/SKILL.md) are answered.
- Screens are planned here. `front_end: navree`: phases 1 to 4 of `navree-design-to-ui` as [design-to-navree-ui](../design-to-navree-ui/SKILL.md) maps them. Every gap the design mapping finds goes into `## Navree UI gaps` now, and the operator agrees all of them once, with the plan (hard rule 14); a gap found later, during a module, is recorded and the module goes on (design-to-navree-ui, "The gap rule"). `front_end: next`: step 3 of [design-to-nextjs](../design-to-nextjs/SKILL.md), the module plan, recorded under `## Modules`.
- A prototype or an older product as the source: run steps 1 to 3 of [prototype-to-navree](../prototype-to-navree/SKILL.md) here and, for a prototype the operator built, steps 1 to 3 of [design-preservation](../design-preservation/SKILL.md), before `plan-architect`; it then takes the modules, their order and the seed plan from the approved `prototype/MIGRATION_PLAN.md`.

## Step 4. Foundation

- **Do:** remove what the starter brings that the product does not keep; start the local services and migrate; lay the security foundation; write the demo seed; write the first suite; build the release path of the roles and of the first account. Dispatch `navree-app-bootstrapper` in mode `foundation`, and `seed-data-architect`.
- **Writes:** foundation code, seeders, the data migration of the roles and the console command of the first account, `tests/security.rs` and its line under `## Suites` in `STACK.md`, the `## Demo accounts` table of `EXECUTION_PLAN.md`, the app's `README.md` and `AGENTS.md`, `Cargo.lock`.
- **Proof:** `cargo fmt --all -- --check` and `cargo clippy --workspace --all-targets -- -D warnings` exit 0; `cargo build --release`; the binary started with `serve` answers `GET /health/live` with `{"status":"up"}`, `GET /health/ready` with 200 and `GET /` with anything but 404; each demo account signs in; `cargo test --test security` and `navree check` pass; the case "a migrated empty database has the roles" passes.

1. A new app: the first commit of the step removes what the operator decided at step 1, item 6, and the plan's `## Open items` records: the example module and its tests, the registrations in `src/app.rs`, the sections of `config/app.toml`, the demo account the starter made. A product with no workspaces also removes `WorkspaceModule`, the `[workspace]` section and the workspace parts of the shell. Then rewrite the layout, screens and conventions that `README.md` and `AGENTS.md` describe to the app that is left (`CLAUDE.md` imports `AGENTS.md`, so a stale file steers every later session), and commit that with the removal.
2. Start the database (`navree dock up` for TimescaleDB and PostgreSQL; MySQL runs on a server you provide at `database.url`; SQLite needs nothing), then `navree migrate`.
3. The foundation: [security-foundation](../security-foundation/SKILL.md), section "At step 4".
4. The demo seed: rule BE-14 of [backend-on-navree](../backend-on-navree/SKILL.md). At this step it holds one account per role (more only when the operator names parallel QA agents or phone runs, and then you pass their number to `seed-data-architect`; otherwise none), the global staff roles with their grants and the staff who hold them, and the workspaces the product has; each module's seeder adds its rows at step 6. A product with no workspaces has no second workspace and no overlapping names: say so in the plan's `## Access`. `seed-data-architect` returns the accounts table; copy it into `## Demo accounts` (emails, roles, workspaces; the development password stays in the seeder).
5. The release path of the roles and of the first account: rule BE-14. Build the data migration of the roles and their permission keys, and the console command of the app that makes the first account; the deploy checklist runs both.
6. `tests/security.rs`, and the line `- cargo test --test security` under `## Suites` in `STACK.md`; it holds the case "a migrated empty database has the roles" ([security-suites.md](../security-foundation/references/security-suites.md)).
7. `test_database_url` must name a database the real-database tests may use; check `navree-testing` for whether the tests create it.
8. The product's first address is owned: `GET !/` lands on the product's first screen, or redirects to it, and has a row in the plan's `## Access` (a signed-in person and a guest each get an answer that is not a 404). The plan's list of public routes is copied from the release binary (`<target>/release/<binary> routes --json`), which `verify-done.mjs` compares with it (hard rule 6).
9. The proof: the binary is the release build of hard rule 4 (the boot check of `verify-done.mjs` gives the same proof, and asks for `GET /`); a demo account signs in through the sign-in page or the sign-in route that `navree routes --json` lists; `navree check` needs its configuration and a migrated database (hard rule 13); fmt and clippy are run as in `## Proof of a module` of [backend-on-navree](../backend-on-navree/SKILL.md). Then commit `Cargo.lock` with the step's last commit: the first cargo run wrote it, and an application commits its lock file.

## Step 5. Contracts

- **Do:** write the contract of every module, in build order, before any module code; the operator agrees each one.
- **Writes:** `contracts/<module>.md` for every module.
- **Proof:** each file has `Status: AGREED by <operator> on <YYYY-MM-DD>`.

- What a contract is on Navree, and its format: [artifacts.md](references/artifacts.md), section `contracts/<module>.md`.
- The main agent writes and changes every contract (rule BLD-2, hard rule 3). Drafts from `prototype-to-navree` (`Status: DRAFT`) are completed here, never taken as agreed.
- Each `D-n` screen of `DESIGN_DIGEST.md` becomes a row of one contract's `## Screens`. A screen that Navree draws itself (the sign-in pages) and the shell are rows of the first module's contract, marked as such: no module owns their routes. Commit the agreed contracts.

## Step 6. Modules

- **Do:** build the modules one at a time in the plan's build order (rule BLD-1), each through 6.1 to 6.7 below. Dispatch `navree-module-builder` for 6.1 and 6.2, `navree-ui-screen-builder` or `nextjs-module-builder` for 6.4, and `ui-auditor` (with `module-structure-auditor` for Next.js) at 6.5; who meets 6.3 and 6.6 depends on the front end (below).
- **Writes:** module code and tests, lines under `## Suites` in `STACK.md`, the module's row in the `## Build order` table of `EXECUTION_PLAN.md`.
- **Proof:** per module: `navree routes --json` lists exactly the contract's routes with their access; `cargo test`; the release binary boots and the module's routes answer as the contract says; one side effect observed (row, audit entry, job, live nudge); every screen opened in a real browser with zero console errors.

Who proves what. Whoever writes a route's handler writes its route tests. With `front_end: next` or `none`, the module's routes are JSON routes: `navree-module-builder` does 6.1 to 6.3 and the module's suites, and the screens follow. With `front_end: navree`, they are pages and form posts, whose handlers are screen code: `navree-module-builder` does 6.1 and 6.2 at the service layer (models, migrations, queries, validation, ability rules, services and their tests, workspace scoping and audit entries included); `navree-ui-screen-builder` then writes the page and form handlers with their route tests and the module's route-level suites (6.4, 6.6) and runs 6.3 after them; the browser proof (6.5) comes last.

- **6.1 Contract in code:** the module's first commit, `feat(<module>): contract in code`, made by `navree-module-builder` before any handler body or screen code (hard rule 3); a Navree UI module's page and form routes carry their access declarations and stub handlers. Proof: `cargo build`; `navree routes --json` matches the contract's route table; with `front_end: next`, `openapi.json` and the TypeScript types regenerated and committed (hard rule 17).
- **6.2 Backend:** [backend-on-navree](../backend-on-navree/SKILL.md), section "A module, in order". Proof: `cargo test`.
- **6.3 Runtime proof:** start the release binary (hard rule 4), call each route of the module once as a demo account (for a Navree UI module, after 6.4: open each page and post each form, by the recipe of "Runtime proof without a browser" in [design-to-navree-ui](../design-to-navree-ui/SKILL.md)), and observe one side effect (hard rule 5).
- **6.4 Screens:** `front_end: navree`: [design-to-navree-ui](../design-to-navree-ui/SKILL.md); `front_end: next`: [design-to-nextjs](../design-to-nextjs/SKILL.md), laid out per [frontend-structure](../frontend-structure/SKILL.md), and with `--ui next` and no kit the main agent adds shadcn/ui at the first module (rule NX-8); `front_end: none`: no screens. When `clients` has a Tauri client, its screens for the module follow [design-to-tauri](../design-to-tauri/SKILL.md).
- **6.5 Browser proof:** every screen of the module in a real browser at 1440 and 390 px wide with zero console errors (hard rule 18); `ui-auditor` (`out_dir: audit`) in mode `navree` or `next` reports no `Blocker` or `Major`; with `front_end: next`, `module-structure-auditor` per [frontend-structure](../frontend-structure/SKILL.md) leaves no finding open; a preserved prototype is compared per step 4 of [design-preservation](../design-preservation/SKILL.md); Tauri screens on a device (hard rule 25).
- **6.6 Suites:** the module's share of the committed suites, per section "In every module" of [security-foundation](../security-foundation/SKILL.md) (`tests/access.rs`, and `tests/isolation.rs`, `tests/money.rs` and `tests/live.rs` when they apply). `navree-module-builder` writes the module's seeder (rule BE-14) and the cases that need no route (balance locks, a job run twice); the cases that go through a route are written by whoever writes the route's handler, as above. A new suite file adds its `cargo test --test <name>` line under `## Suites`. Proof: `cargo test` after the screens.
- **6.7 Commit and lessons:** the main agent makes the module's last commit (backend, screens, suites); write the module's row in `## Build order` (rule BLD-5); write a lesson when a correction or a failed check taught one.

Anything that fails goes to [systematic-debugging](../systematic-debugging/SKILL.md): fix the cause and add no suppression (hard rule 15).

## Step 7. Audits

- **Do:** run [security-review-and-fix](../security-review-and-fix/SKILL.md) when the product has sign-in, staff, personal data or money (that is, nearly always), then [product-audit](../product-audit/SKILL.md) in `completeness` mode; add `score` mode when the operator asks for readiness scores, and `inventory` mode on request.
- **Writes:** `SECURITY_REPORT.md`, `AUDIT_REPORT.md`, the agents' reports under `security/` and `audit/`.
- **Proof:** no open `Blocker` or `Major` finding, except one whose state is `accepted ACC-n` with `ACC-n` an entry of the operator's `ACCEPTANCES.md`; `verify-done.mjs --strict` reads both reports.

Both audits run against the current commit; a fix goes through the skill that found the problem, which runs its check again. Commit the reports. A finding that only the operator can accept is returned to them as a question (rule BLD-6); the agents never write the acceptance.

## Step 8. QA gate

- **Do:** run [product-qa](../product-qa/SKILL.md) in gate mode on a fresh seed (`navree migrate:fresh --seed`). Its explore mode may run before the gate.
- **Writes:** `QA_COVERAGE.md`, the agents' reports under `qa/`.
- **Proof:** `QA_COVERAGE.md` has no `FAIL` and no `NOT RUN` (and no `PASS (server)`) without an `ACC-n` that is an entry of the operator's `ACCEPTANCES.md`; `verify-done.mjs --strict` reads it.

The gate is the last check before deployment. Only the operator accepts a `NOT RUN`, in `ACCEPTANCES.md` (rule BLD-6). Commit `QA_COVERAGE.md`.

## Step 9. Deployment

- **Do:** only when the operator asks, deploy with Navree's `navree-deployment` skill (and `navree-harbor` for `navree deploy`), item by item through [the deploy checklist](references/deploy-checklist.md).
- **Writes:** `DEPLOY.md`.
- **Proof:** `navree deploy` printed `Released <id>` (Harbor), or the documented processes are up; the public `GET /health/ready` answers 200; the post-deploy checks in `DEPLOY.md` are `PASS`.

## Step 10. Done

- **Do:** run the done check on the last commit that changes code and record the build's lessons.
- **Writes:** `qa/verify-done.txt`, lessons in `.claude/memory/superdev-learned/`.
- **Proof:** `node ${CLAUDE_PLUGIN_ROOT}/scripts/verify-done.mjs --suites --strict` exits 0 and its last line is `DONE`, on the last commit that changes code, and steps 7 and 8 are clean on that commit (the run reads their reports and `ACCEPTANCES.md`).

- Before the run, search `README.md` and `AGENTS.md` for the names the app no longer has (the removed example module, `WorkspaceModule`, the starter's demo account: the list of step 1, item 6): `git grep -n -i -E '<names>' -- README.md AGENTS.md` prints nothing.
- Start the database (`navree dock up` for TimescaleDB and PostgreSQL; SQLite needs nothing): each suite boots its own app ([superdev-done](../superdev-done/SKILL.md)). The run is long on a fresh `target/`: run it detached, as `superdev-done` shows.
- Save the output as `qa/verify-done.txt` and commit it after the run, in a commit that changes nothing else: the run is on the code commit before it, and that commit is the one it vouches for. Reset the data with `navree migrate:fresh --seed` as the last command ([product-qa](../product-qa/SKILL.md), gate step 12).
- A code change after the gate re-opens steps 8 and 10.

## Rules of the flow

- **BLD-1** One module at a time. Never build the backend and the screens of a contract made in the same step in parallel; a builder agent gets one module per dispatch.
- **BLD-2** One owner of contracts: the main agent writes and changes `contracts/*.md`; an agent that needs a change says so in its return and stops.
- **BLD-3** A plan revision edits `GAPS.md` `## Decisions` first, then regenerates `EXECUTION_PLAN.md`, then asks for confirmation again.
- **BLD-4** Agents receive absolute paths (plugin root, app root, files) and their `out_dir`; if the host cannot dispatch an agent type (Codex), the main agent reads the agent file and runs its procedure itself.
- **BLD-5** A module's proofs are recorded in `EXECUTION_PLAN.md` `## Build order`, columns `Module | Status | Commit | Proof`, where `Proof` quotes the result lines (for example `cargo test: 41 passed; 0 failed`, `GET /health/ready 200`). `Status` is `PASS` only when 6.1 to 6.6 all have a proof. When the browser proof (6.5) cannot run on this host, the row reads `PASS (6.5 NOT RUN, ACC-n)`, with `ACC-n` an entry of `ACCEPTANCES.md`; without that entry it is `NOT RUN`.
- **BLD-6** Operator answers are written with the operator's name and the date, quoted exactly as given, never paraphrased into a decision the operator did not make. An acceptance is an entry of `ACCEPTANCES.md`, the operator's own file ([artifacts.md](references/artifacts.md)): the main agent and every dispatched agent never create or edit it and never write a sentence the operator did not say, in any file. When an acceptance is needed, the agent stops and returns the question to the operator; a report cites an accepted item by its `ACC-n` and copies no sentence.
- **BLD-7** Code generated by `navree new` and `navree make:*` is the app's own code: keep the generator markers (`// navree:modules`, `// navree:wire`, `// navree:policies`) and prefer the generator over hand-writing a file it makes (`navree-cli-generators`).

## Reference files

| File | Read it |
|---|---|
| [references/hard-rules.md](references/hard-rules.md) | once at the start of a build, and when a step cites a rule |
| [references/artifacts.md](references/artifacts.md) | before writing `STACK.md`, a digest, `GAPS.md`, `EXECUTION_PLAN.md` or a contract; for the severity scale, ids, status words and output folders every skill uses |
| [references/deploy-checklist.md](references/deploy-checklist.md) | at step 9 |
