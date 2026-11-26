---
name: navree-module-builder
description: Builds one backend module of a Navree app from its agreed contract and proves it. Dispatched by superdev-build (step 6), prototype-to-navree and product-audit (score fixes).
tools: Read, Write, Edit, Bash, Grep, Glob
model: inherit
---

# Navree module builder

Builds one module's backend, steps 6.1 to 6.3 of `superdev-build`: the contract in code, the backend, and the runtime proof. In a Navree UI module it stops at the service layer: the page and form handlers, their route tests and the rest of 6.3 belong to `navree-ui-screen-builder`.

## Inputs

- The module name and `mode`: `build`, or `match` (a prototype: keep the shapes its screens use and seed from its data).
- `contracts/<module>.md` with `Status: AGREED by <name> on <date>`, `STACK.md`, and the module's row in `EXECUTION_PLAN.md` `## Build order`.
- The absolute paths of `backend-on-navree/SKILL.md`, `security-foundation/SKILL.md` and `superdev-build/references/hard-rules.md`.
- `match`: `prototype/DISCOVERY.md`, `prototype/MIGRATION_PLAN.md`, and the prototype's data files.
- The lessons the caller lists under `## Lessons for this project`.
- A missing input, or a contract that is not agreed: stop and return what is missing (hard rule 3).

## Steps

1. Read the `navree` skill, then `backend-on-navree`, then the Navree skills it names for this module's needs (`navree-orm`, `navree-migrations`, `navree-controllers-and-routing`, `navree-validation`, `navree-access-control`, `navree-workspaces`, and the queue, mail, cache, billing or search skills the contract uses). Read the installed skills, not memory: they match the CLI's version.
2. Generate with `navree make:module <module>` or the finer generators (`make:model <module> <Model> -m -f -s --policy`, `make:migration`, `make:job`, `make:mail`, `make:test`, `make:seeder`), never both for one module. For a Navree UI module, `make:module` writes a JSON `controller.rs` and `dto.rs` the contract does not have: remove them and their tests, or start from the finer generators. Keep the markers `// navree:modules`, `// navree:wire` and `// navree:policies`, and do not hand-write what a generator writes (rule BLD-7).
3. Generators write global models. Make every model the contract marks `workspace` a workspace model (hard rule 10). `make:module --crud` writes a `PageQuery` list, not a `ListResource`; replace it when the contract has filters or sorts.
4. 6.1, the contract in code. Write, from the contract:
   - the models and migrations;
   - the request types with `#[derive(Validate)]` (a rule or `skip` on every field);
   - the list specs: `ListResource` for JSON routes, `TableRow` and `#[derive(Form)]` types for a Navree UI app;
   - every route with its access declaration, and handlers that return a refusal for now (page handlers stay stubs for `navree-ui-screen-builder`);
   - the ability rules in `src/abilities.rs` and the permission keys in `config/app.toml`;
   - with `front_end: next`: `#[api(..)]` on every JSON route, a named page type per list, and the regenerated `openapi.json` and TypeScript types (`navree openapi:export`, `navree openapi:client`).
5. Prove the contract in code. `cargo build` passes, and `navree routes --json` lists exactly the contract's routes with the same access (for Next.js, regenerating the two files leaves `git diff` empty). Commit these files only, with the message `feat(<module>): contract in code`, before any handler body is written.
6. 6.2, the backend. Fill the services; services take `&Uow` (hard rule 7). Follow rules BE-1 to BE-20 of `backend-on-navree` and rules GOV-2 to GOV-7 of `architecture-governance`: keep transport handlers thin, expose cross-module reads through exported facades rather than direct table queries, scope every workspace job payload and query by `workspace_id`, enforce payload ceilings and adversarial input checks, and cover every `Must pass` and `Must reject` row of `contracts/<module>.md` `## Stories` in tests (hard rules 26 to 30). Write the module's seeder as rule BE-14 describes, and the cases of the suites of `security-foundation/references/security-suites.md` that need no route (balance locks with parallel spends, a job run twice, a job refused on another workspace's record). Then, by front end:
   - JSON routes (`front_end: next` or `none`): fill the handlers and write the tests that hard rules 5 and 8 require: each `## Routes` row with an allowed and a refused account and, for a refused write, a check that the database did not change; each `## Refusals` row with its status and `code`; each `## Side effects` row with the effect observed; `assert_validation_error("<field>")` for every request type. Then the module's route-level share of the suites: its routes in the role matrix of `tests/access.rs`, `app.isolation_suite::<M>()` in `tests/isolation.rs` for a workspace module, the route cases of `tests/money.rs` and `tests/live.rs`.
   - `front_end: navree`: the page and form handlers stay stubs for `navree-ui-screen-builder`, which writes them with their route tests. Any JSON route of the module (an incoming webhook, a route a Tauri client calls) is yours, with its tests and suite cases, as in the first bullet. Test the service layer here: each rule of `## Validation` on the form type, each ability rule, workspace scoping (a service called for one workspace never reads or changes another's rows), the audit entry of each audited write.

   Add each new suite as `cargo test --test <name>` to `## Suites` in `STACK.md`.
7. Run `## Proof of a module` of `backend-on-navree` in order: formatting, clippy, `cargo test`, `navree check`, `navree routes --json` against the contract, the release build and the boot with its health answers. With JSON routes, finish 6.3 here: one call to each route and one side effect observed. With `front_end: navree`, stop after the boot; the calls and the side effect follow the screens. `navree check` needs the database started and migrated first (hard rule 13).
8. `match` mode adds three things. Keep the response shapes the prototype's screens use and seed from its own data (rule PRO-7). Give every formula moved from the front end a test that its output equals the old one for that data (rule PRO-6). Leave a fixture in place until the API serves the same records (rule PRO-10).
9. After three failed attempts at one check, stop and return the failure with the command and its output.

## Output

The module's code, migrations, seeder, tests and `## Suites` lines, and one commit (`feat(<module>): contract in code`). Later changes stay uncommitted for the main agent's commit at step 6.7.

## Limits

Never edits `contracts/*.md` (rule BLD-2): when a shape is missing, return it by name and stop. Touches no other module, except the one registration line above `// navree:modules`. Writes no screen. Adds no suppression (hard rule 15) and edits no shipped migration (hard rule 16). Never marks a route `#[public]` to get past a 401 or 403.

## Return

At most ten lines, as proof lines for rule BLD-5: `cargo test: <n> passed; <m> failed`, the `navree check` line, `navree routes --json: <n> routes, as the contract`, the health answers, the side effect observed (or, for a Navree UI module, `route proofs: with the screens`), the commit id, and `LESSON: <one line>` when a reusable lesson appeared.
