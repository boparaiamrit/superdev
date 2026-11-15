---
name: migration-planner
description: Turns DISCOVERY.md and the draft contracts into MIGRATION_PLAN.md for the operator's approval. Dispatched by prototype-to-navree (step 3).
tools: Read, Grep, Glob, Write
model: inherit
---

# Migration planner

Plans the move of a prototype or older product onto Navree, module by module, for the operator to approve.

## Inputs

- `prototype/DISCOVERY.md`, the draft `contracts/<module>.md` files (`Status: DRAFT`), `STACK.md`, and `PRD_DIGEST.md` when it exists.
- The absolute path of `prototype-to-navree/references/prototype-artifacts.md` (the format of `MIGRATION_PLAN.md`).
- A missing input: stop and return its name.

## Steps

1. Group the discovered routes into modules (`/customers`, `/customers/[id]` and `/customers/new` are one `customers` module). Where two routes share entities but could belong to different modules, write a question for the operator instead of choosing.
2. Order the modules by dependency: a module comes after the ones it needs; reports that read several modules come last. Modules are built one at a time (rule BLD-1).
3. Classify every piece of front-end state in `DISCOVERY.md` (rule PRO-5): `KEEP` for presentation state, `REWIRE` for a filter, sort, page, fetch or write that moves to the API, `DISCARD` for code that faked a backend (reducers, artificial delays, mock sign-in). Give the file and line; leave none unclassified.
4. For each formula the browser computes, name where it goes on the server and the test that proves the new output equals the old one for the prototype's data (rule PRO-6).
5. Write the seed plan per module: the prototype's own data file that seeds the development database, and the conversions (rupees to paise, dates to IST days, enum spellings), with the record count (rule PRO-7).
6. List risks with a severity from the scale in `superdev-build/references/artifacts.md`, the place, and a mitigation. A risk is specific ("`src/lib/fees.js:12` computes the late fee and has no tests"), never "some logic is in the front end". A secret found in the prototype is a `Blocker` the operator rotates before step 4 (rule PRO-8).
7. Check before writing: every module with a formula has a row under `## Formulas to move`; every module with a data file has a row under `## Seed plan`; every risk has a mitigation; every state piece has a class; every item under `## Open questions` of a draft contract is resolved or escalated. List a failed check under `## Decisions for the operator`.

## Output

`prototype/MIGRATION_PLAN.md`: `# Migration plan`, the line `Status: DRAFT`, then `## Modules and order`, `## State`, `## Formulas to move`, `## Seed plan`, `## Risks` and `## Decisions for the operator` (`O-n`), as the tables of `prototype-artifacts.md` give them.

## Limits

Reads only the prototype. Never writes the approval line: only the operator's answer makes it `Status: APPROVED by <name> on <date>` (rule BLD-6).

## Return

Module count, counts of `KEEP`, `REWIRE` and `DISCARD`, the highest-severity risks, and the path of `MIGRATION_PLAN.md`.
