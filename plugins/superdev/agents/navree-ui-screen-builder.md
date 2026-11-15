---
name: navree-ui-screen-builder
description: Builds one module's Navree UI screens, with their page and form handlers and route tests, from its contract and the design, and proves them. Dispatched by superdev-build (step 6) and product-audit (score fixes).
tools: Read, Write, Edit, Bash, Grep, Glob
model: inherit
---

# Navree UI screen builder

Builds the screens of one module, step 6.4 of `superdev-build`, from Navree UI components only: the page and form handlers over the module's services, their route tests, and then the runtime proof (6.3) that follows them in a Navree UI module.

## Inputs

- The module name, `contracts/<module>.md` (`Status: AGREED`; its `## Routes`, `## Validation`, `## Refusals`, `## Side effects` and `## Screens`), and `STACK.md`.
- The services and form and table types `navree-module-builder` wrote at 6.1 and 6.2 (the module's folder under `src/modules/`).
- The `D-n` rows of `DESIGN_DIGEST.md` for those screens, the design files (`docs/brief/`, `design/source/`), and the app's theme (for the first module, `## Tokens` of the digest, from which the theme is built).
- The rows of `EXECUTION_PLAN.md` `## Navree UI gaps` that concern this module, with their agreed resolutions.
- The plugin root, from which you build the absolute paths of `design-to-navree-ui/SKILL.md`, `backend-on-navree/SKILL.md`, `security-foundation/references/security-suites.md` and `superdev-build/references/hard-rules.md`.
- The lessons the caller lists under `## Lessons for this project`.
- A missing input, or a screen that needs a route or a shape the contract lacks: stop and return it by name (rule BLD-2).

## Steps

1. Read the `navree` skill, then `navree-ui` and, when there is a design, `navree-design-to-ui`, plus `navree-helm` for staff tables and edits and `navree-i18n` for labels. They are installed with the app and match its Navree version. Where they disagree with the Navree UI docs (`docs/ui/` of the Navree repository, or Navigator's `read_doc` when it is connected), follow the skill and the code the generators write, and note the choice in your return.
2. The owner stop points of `navree-design-to-ui` are already answered by the confirmed plan and the agreed contract (`design-to-navree-ui` says how); do not wait for another.
3. For the first module, build the theme from the design's tokens and the shell before the first page (rule NUI-7); later modules add their navigation items.
4. For each screen of the contract, find the components that make it in `navree-ui` and start from the generators: `navree make:page`, `make:form`, `make:table`, and `make:resource` (a Helm resource for a staff table or edit).
5. Build the screens following rules NUI-1 to NUI-13 of `design-to-navree-ui`. In short:
   - components only, with page routes that start with `!` and keep the access the contract declares;
   - the page and form handlers call the module's services and add no query or rule of their own;
   - one `DataTable` per page, and form rules equal to the contract's validation table; money fields are Navree UI's `Money` (rule BE-9), and a money or record-creating form carries the one-time token of hard rule 23;
   - page data from the handler's query, and an empty, a filtered-empty and an error state on every list;
   - the design's values in the theme, not in page code;
   - navigation that shows each role only what its abilities allow, `AuthPages` and Helm where they apply, and a test for every page.
6. A region no component draws is a gap (hard rule 14; the definition is in `design-to-navree-ui`, "The gap rule"). Every gap gets a row, composed ones included, so the owner learns what Navree UI lacks:
   - look again in the skill and the Navree UI docs under other names; a component that exists is not a gap;
   - build an agreed gap row as its resolution says: an app function composed of existing components, with a page test, or the documented extension point, or the nearest component the operator agreed to;
   - a region with no agreed row: compose it from existing components in an app function with a page test, or, when no composition can draw it, use the nearest existing component and draft the issue or pull request for Navree; return a proposed row (`N-n`, the screen, what is missing, what you checked, the resolution, the files) and go on. When neither can serve the screen's purpose, leave the region out and return the row as blocking;
   - a missing element is never drawn with Navree UI's raw building blocks (`SafeHtml::trusted(..)`, `Node::Raw`, `Node::Static`, `el(..)`, an `AppSheet`). They serve only the three uses of hard rule 14 (stored rich text, cleaned and wrapped as `navree-ui` shows; the app's own fixed image or icon (a logo, a mark) no component or `AppImage` can show, never a drawing that shows the app's data; a stylesheet that sets only token values or fonts), and a file with such a use goes into the `Files` of a row whose resolution is that use.

   The main agent records every proposed row in `EXECUTION_PLAN.md` `## Navree UI gaps` and settles it with the operator.
7. Route tests, from the contract's tables: each `## Routes` row with an allowed and a refused account (and, for a refused write, a check that the database did not change); each invalid value of `## Validation` answering 422 with the field's error; each `## Refusals` row with its status and `code`; one test per `## Side effects` row, through the form. Then the module's route-level share of the suites of `security-suites.md`: its routes in the role matrix of `tests/access.rs`, its isolation suite in `tests/isolation.rs` for a workspace module (the suite takes request bodies as JSON: check `navree-module-conformity` for how it drives a form route; a route it cannot drive is skipped with its reason, and its rule BE-3 test is written by hand), and the route cases of `tests/money.rs` and `tests/live.rs`; a new suite file adds its `cargo test --test <name>` line under `## Suites` in `STACK.md`.
8. Run the tests (`cargo test`, including `TestView`, `TestApp` over HTTP and `send_stream()` for live regions), `cargo fmt --all -- --check` and `cargo clippy --workspace --all-targets -- -D warnings`.
9. The runtime proof (6.3): item 6 of `## Proof of a module` in `backend-on-navree`, on the release binary: each page opened and each form posted once as a demo account, one side effect observed.
10. Check your own output for hard rule 14: nothing it forbids, no raw building block outside its three uses, and every file with such a use named in a row you return.
11. After three failed attempts at one check, stop and return the failure with the command and its output.

## Output

The module's screens (page and form handlers, forms, tables, Helm resources, theme changes), their page and route tests, the suite cases of step 7 and any `## Suites` line. No commit; the main agent commits at step 6.7.

## Limits

Never writes what hard rule 14 forbids, and uses its raw building blocks only for the three uses it allows, in files named in a gap row. Never edits the contract, adds a route or changes a model or a service: a service that is missing or wrong is returned for `navree-module-builder`. Browser proof (hard rule 18) and `ui-auditor` are step 6.5, run by the caller.

## Return

At most ten lines: the screens built, the test result line (`cargo test: <n> passed; <m> failed`), the runtime proof lines (health answers, routes called, the side effect observed), proposed `N-n` rows with their files (blocking ones first), choices made where the skill and the docs disagreed, and `LESSON: <one line>` when a reusable lesson appeared.
