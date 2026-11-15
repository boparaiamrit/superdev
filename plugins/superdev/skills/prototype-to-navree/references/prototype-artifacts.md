# Prototype artifacts

Three kinds of file come out of [prototype-to-navree](../SKILL.md): `prototype/DISCOVERY.md`, the
draft contracts and `prototype/MIGRATION_PLAN.md`. The samples below describe an invoicing prototype
with customers and invoices. Counts come from the files, never from estimates; a number that was not
counted is not written.

## prototype/DISCOVERY.md

Written by `codebase-discoverer` from a read-only pass. It records what is there, with `path:line`
for each fact, and does not say what anything should become.

```markdown
# Discovery

Source: <folder>, <stack>, <commit id or "not a repository">
Read on: <YYYY-MM-DD>
Navree outputs used: <outputs of navree-reverse-engineering that were used, or "none">

## Screens and routes
| Route | File | What it shows | Data it reads |
|---|---|---|---|
| /customers | src/pages/Customers.jsx:1 | customers table with a search box | data/customers.json |

## Data files and their shapes
| File | Records | Fields and how many records carry each | Notes |
|---|---|---|---|
| data/customers.json | <n> | name (<n>), city (<n>), phone (<n>) | two files hold customers with different fields; both shapes are listed |

## Writes done in the browser
Each button or form that changes data: the file:line, what it changes in memory and what it would send to a server.

## Computations done in the browser
Each formula, filter, sort, total or label built in the front end: file:line and the inputs it uses.

## Sign-in as built
How the prototype signs a person in, what it stores and where, and what differs per person or role.

## Integrations
Each outside service the code calls or imports, and whether the call works today.

## Secrets found
- src/lib/pay.js:8: a payment gateway key in source. rotate before step 4

## Data hard-coded in components
Each component with an inline list of records (more than five), with the file:line and the fields.
```

Rules for the file: facts only; two data files with different shapes are both recorded; a screen
with no data behind it is recorded as such ("/settings: layout only"); a secret's value is never
copied into the file; the secret scan covers source, `.env` files and JSON, and every hit is a line
under `## Secrets found` marked `rotate before step 4`.

## Draft contracts

`schema-reverse-engineer` writes `contracts/<module>.md` with `Status: DRAFT`, in the format of
[artifact formats](../../superdev-build/references/artifacts.md). Rules PRO-2 to PRO-4 apply, and:

- For each field, count how many records carry it. Present in every record: required. Present in
  some: nullable, a default, or a separate variant; the count goes in `## Open questions` when it
  decides.
- A field with few distinct values across many records is an enum: list the values the data holds,
  stored as strings (rule BE-8). Mixed spellings of one value (`sent`, `Sent`) are an open question.
- Amounts become integers in paise in a field ending `_paise` (rule BE-9), and a screen shows them
  as ₹ 1,00,000. Dates become `NaiveDate` or `DateTime<Utc>`, shown in IST.
- A value the screen computes (a total, a change, a label) is a response field the server computes;
  its formula goes to `## Formulas to move` in the migration plan.
- A form's request type follows the form's inputs, not the shape of the list's row; the response and
  the request are two shapes.
- Types, data and screens that disagree: one bullet each under `## Open questions`, with the
  file:line of each side.

## prototype/MIGRATION_PLAN.md

Written by `migration-planner` from `DISCOVERY.md` and the drafts. The operator reads it before any
module is built.

```markdown
# Migration plan

Status: DRAFT

## Modules and order
| Order | Module | Screens | Data files | Depends on |
|---|---|---|---|---|
| 1 | customers | /customers, /customers/:id | data/customers.json | none |
| 2 | invoices | /invoices, /invoices/:id | data/invoices.json | customers |

## State
| Piece | File:line | Class | Note |
|---|---|---|---|
| the customers list held in a state hook | src/pages/Customers.jsx:22 | `DISCARD` | the screen reads the list query |
| text in the search box | src/pages/Customers.jsx:24 | `KEEP` | sent to the list as `search` |
| filter, sort and slice of the array | src/pages/Customers.jsx:28 | `REWIRE` | becomes list parameters |

## Formulas to move
| Formula | File:line | Goes to | Equivalence test |
|---|---|---|---|
| late fee on an overdue invoice | src/lib/fees.js:12 | the invoices service | runs every invoice in data/invoices.json through old and new code and asserts equal fees |

## Seed plan
| Module | Source file | Conversions | Records |
|---|---|---|---|
| invoices | data/invoices.json | rupees to `amount_paise` (₹ 1,00,000 is 10000000); dates to IST days; status spellings to the contract's | <n> |

## Risks
| Risk | Where | Severity | Mitigation |
|---|---|---|---|
| A payment gateway key is in source | src/lib/pay.js:8 | `Blocker` | the operator rotates it before step 4; the new key lives in `.env` |
| The late-fee formula has no tests | src/lib/fees.js:12 | `Major` | the equivalence test above |

## Decisions for the operator
- O-1: a "Templates" item is in the sidebar and has no page. In the first release or left out? The operator's answer is quoted here with their name and the date.
```

Status line: `Status: DRAFT`, then `Status: APPROVED by <name> on <YYYY-MM-DD>` (for example
`Status: APPROVED by Harpreet Sandhu on 2026-11-20`). Severity words are the scale of
`artifacts.md`: `Blocker`, `Major`, `Minor`, `Note`. Every module with a formula has a row under
`## Formulas to move`; every module with a data file has a row under `## Seed plan`; every risk has
a mitigation.
