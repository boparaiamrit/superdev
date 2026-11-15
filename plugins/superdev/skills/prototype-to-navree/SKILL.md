---
name: prototype-to-navree
description: Use when an existing prototype or older product (a front end with fixtures as its backend, or an app on another stack) must become a Navree app without losing what its users see. Inventories it read-only, drafts each module's contract from its real data, plans the move with the operator, then rebuilds it module by module through superdev-build.
---

# Prototype to Navree

This skill moves an existing prototype or older product to a Navree app without losing what its
users see. The prototype can be a front end whose backend is fixtures and browser code, or a whole
app on another stack. Steps 1 to 3 only read it and write plans; the build then goes through
[superdev-build](../superdev-build/SKILL.md). Steps 1 to 3 run at step 3 of the build, inside the
app that step 1 of the build created, with the prototype's folder copied into `docs/brief/`.

## Navree skill

`navree-reverse-engineering` turns an old product into specs, tasks and tests, then into a Navree
app. Read it first. Check at build time what it writes and where, feed its specs into steps 2 and 3
of the build (the digests and the plan), and say in `prototype/DISCOVERY.md` which of its outputs
were used.

## Steps

1. **Discovery, read-only.** `codebase-discoverer` writes `prototype/DISCOVERY.md` per
   [prototype-artifacts](references/prototype-artifacts.md). The prototype is read and never run or
   edited (rule PRO-1). Every real secret found is listed under `## Secrets found`, and the operator
   rotates it before step 4 of the build (rule PRO-8).
2. **Shapes.** `schema-reverse-engineer` reads `DISCOVERY.md` and the data files and writes a draft
   `contracts/<module>.md` for each module, with `Status: DRAFT`, in the format of
   [artifact formats](../superdev-build/references/artifacts.md) (rules PRO-2 to PRO-4). Every
   disagreement between types, data and screens goes to the draft's `## Open questions`.
3. **Plan.** `migration-planner` reads `DISCOVERY.md` and the drafts and writes
   `prototype/MIGRATION_PLAN.md`. The operator approves it: the status line becomes
   `Status: APPROVED by <name> on <YYYY-MM-DD>` (rule BLD-6). That approval covers the module order,
   the state classification, the formulas to move and the seed plan; it does not replace the
   `CONFIRMED` line that `EXECUTION_PLAN.md` still needs (hard rule 2).
4. **The build.** If the operator started here and no build is under way, start `superdev-build` at
   its step 1; it calls steps 1 to 3 above at its step 3. If the build called this skill, return to
   the rest of the build's step 3: `plan-architect` writes `EXECUTION_PLAN.md`, taking its modules,
   order and seed plan from the approved `MIGRATION_PLAN.md`, and the operator confirms it. The
   contracts at step 5 start from the drafts: the main agent finalises
   them and the operator agrees them (hard rule 3). `navree-module-builder` runs in `match` mode: it
   keeps the shapes the prototype's screens use and seeds the development database from the
   prototype's own data (rule PRO-7; the seeder rules are rule BE-14 of
   [backend-on-navree](../backend-on-navree/SKILL.md)).
5. **Screens.** Each module's screens follow its backend, one module at a time.
   - Navree UI: rebuilt from Navree UI components with the prototype as the visual reference
     ([design-to-navree-ui](../design-to-navree-ui/SKILL.md);
     [design-preservation](../design-preservation/SKILL.md) when the operator built the prototype).
   - A Next.js prototype going to a Next.js front end: `nextjs-module-builder` in `rewire` mode,
     after `frontend-structure` has split any module over the limits of rule FS-2 (the builder
     refuses such a file). A rewire changes data flow and nothing in the markup or classes (rule
     PRO-9): fixture imports become calls through the generated client (rule NX-2); filtering,
     sorting and paging that ran over an array become list query parameters (rule NX-5); writes that
     changed an array in memory become requests to the contract's routes; the code classified
     `DISCARD` is deleted.
   - Any other prototype stack: the screens are built new with
     [design-to-nextjs](../design-to-nextjs/SKILL.md) or `design-to-navree-ui`, taking the prototype
     as the design.

## Rules

- **PRO-1** Steps 1 to 3 only read; the prototype keeps running unchanged.
- **PRO-2** Types in the old code are hints; the data files and how the screens use them are the
  facts. Every disagreement is written in the draft contract's `## Open questions` with its
  evidence.
- **PRO-3** No invented fields: a field that neither the screens show nor the data holds is left
  out.
- **PRO-4** A field present in every record is required; otherwise the contract says nullable,
  default or a separate variant, and a count of the records that carry it is the evidence.
- **PRO-5** Every piece of front-end state is classified `KEEP` (presentation), `REWIRE` (filter,
  sort, page, fetch or write, which move to the API) or `DISCARD` (code that faked a backend:
  reducers, artificial delays, mock sign-in).
- **PRO-6** A formula found in the front end moves to the server with a test that proves the new
  output equals the old one for the prototype's data.
- **PRO-7** The development database is seeded from the prototype's own data; the conversions (money
  to paise, dates, enum spellings) are listed in the migration plan's `## Seed plan`.
- **PRO-8** A real secret found in the prototype is rotated by the operator before step 4 of the
  build.
- **PRO-9** Change data flow, not visuals; never change the UI library and the data flow in the same
  commit.
- **PRO-10** A fixture is removed only after the API serves the same records: the module's proof in
  `EXECUTION_PLAN.md` `## Build order` quotes the comparison (record count and the fields of one
  record, fixture against API response).

## Reference files

| File | Read when |
|---|---|
| [references/prototype-artifacts.md](references/prototype-artifacts.md) | `codebase-discoverer` and `migration-planner` write their files; the operator reads the plan |
