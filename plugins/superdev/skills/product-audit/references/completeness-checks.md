# Completeness checks

Read this for completeness mode and for pass 1 of score mode. The `no placeholder content` check of `verify-done.mjs` (its `--help` lists it) already finds plain-text placeholders, `todo!(` and `unimplemented!(`. The agents here find what a pattern cannot judge.

## Placeholder patterns

| Where | What to look for |
|---|---|
| Text on a screen | lorem ipsum, "coming soon", "not implemented", "TODO", a count or price that is the same on every record |
| Rust handlers and services | a handler that returns a literal success without calling a service or repository; a database write left in a comment; one fixed error message for every failure |
| Navree UI | a `Submit` arm that answers with a redirect or toast without storing; a `DataTable` built from an inline list instead of a `TableQuery` loaded over a model query; a chart whose series are literal numbers; a `Region` whose source answers a fixed fragment; a link or button whose `href` is `#` |
| Next.js | a handler that only logs or alerts; an array used as data inside a component (`useState` seeded with objects, a constant named `mock`, `fake` or `sample`); an import from a fixtures folder in production code; a route handler that returns fixed JSON |
| Kit leftovers | a route of `navree routes --json` that no contract and no Navree module owns. The starter's parts are the examples (the `customers` example module and the `users` profile API of the Navree UI starter, `Housekeeping`, `projects` in the `saas` and `api` kits); a route is judged by who owns it, never by a module's name, which the product's own module may share |

False positives to skip: a `placeholder` attribute on an input or `#[form(placeholder = ..)]`; files under `tests/`; changelogs, `docs/`, `design/` and `qa/`; sample records inside seeders (the seed is where sample data belongs; a handler is not).

A placeholder or stub on a main path is `Major`; off the main paths it is `Minor`. A control that shows success while nothing is stored is `Blocker` (data loss). A kit leftover is `Minor`, and `Major` when a role can reach it.

## Control grades

| Grade | Meaning |
|---|---|
| `WIRED` | the control stores or reads through the real route or service, waits for the answer, shows the result, shows an error when the answer is an error, and the change is visible in the database |
| `STUB` | it logs, alerts, shows a message without a request, changes local state for something that should persist, or has a TODO in its body |
| `NO-OP` | it does nothing: an empty handler, a form that only cancels the default action, a handler bound to nothing |

Navigation-only controls are `WIRED` when the target exists and shows real data. A control that opens a dialog is `WIRED` when the dialog's own actions are. An export or download is `WIRED` when a file with real rows arrives, and `STUB` when a "download started" message appears and no file does.

On Navree UI, a form is `WIRED` when its `Submit` arm calls a service that writes, its `Rejected` arm shows the errors under the fields (the 422 answer) and the row is in the database after the redirect. On Next.js, a mutation is `WIRED` when it goes through the BFF to the API, shows the API's errors by `code` and refreshes what it changed.

## Data sources

| Class | Meaning |
|---|---|
| `REAL` | every value comes from a query over the database: the handler's query on Navree UI, a call through the BFF to the API on Next.js |
| `MOCKED` | the screen reads a literal, a fixture or local state |
| `HYBRID` | the screen is real but some value is not: a literal count, a total that is a constant, a field filled with a default, a label map that hides the stored value |

`HYBRID` is the class that looks real, so confirm each screen in a browser: change the row through the app or a database client, reload, and see whether the screen changes. A `HYBRID` screen is a `Major` finding (rule AUD-4).

## The verdict

| Verdict | When |
|---|---|
| `PRODUCT` | every screen is `REAL`, every control is `WIRED`, and every top journey persists |
| `DEMO` | a top journey cannot be completed with data from the database, or a main-path screen is `MOCKED` |
| `HYBRID` | every top journey completes, but a screen off the main paths is `MOCKED` or `HYBRID`, or a control is `STUB` or `NO-OP` |

The report states the verdict, lists the screens and controls behind it, and gives each finding its severity and owner. A top journey is one of the 3 to 5 taken from the acceptance criteria of `EXECUTION_PLAN.md`; it persists when data created in one step is visible after a reload and after signing out and in, and the database shows it.
