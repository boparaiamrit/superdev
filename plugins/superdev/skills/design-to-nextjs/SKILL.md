---
name: design-to-nextjs
description: Use when a design or a design digest must become a Next.js front end of a Navree API (navree new --ui next, or the saas kit), or when a screen of such a front end is built or changed at step 6 of a superdev build. Covers inventory, tokens, the module plan, the BFF and generated types, lists, forms, real time, states and the browser proof.
---

# Design to Next.js

This skill turns a design, or `DESIGN_DIGEST.md`, into the screens of a Next.js front end that talks
to a Navree API it does not own. The front end shows what the API answers: the API decides who is
signed in, what each person may do and which input is valid. It applies when `STACK.md` has
`front_end: next`; for `front_end: navree` use
[design-to-navree-ui](../design-to-navree-ui/SKILL.md). Steps 1 and 2 run once, before the first
module's screens. Step 3 is part of the build's plan. Steps 4 and 5 run for each module at step 6.4
of the build.

## Navree skills to read

Navree's skills are installed in the app by `navree skills:install`. Read the one a step needs
before doing it; this skill gives the order of work and the rules, they give the framework facts.

| Navree skill | Holds |
|---|---|
| `navree-frontend-next` | the BFF, sign-in, server components, lists and real time, with `@navree/next`, `@navree/client` and `@navree/theme` |
| `navree-openapi` | the OpenAPI document and the typed client |
| `navree-new-app` | `navree new` and its options, and `navree dev` |
| `navree-workspaces` | how the API scopes data to a workspace |
| `navree-browser-testing` | browser tests of an app, with Chrome over CDP |

## What the app already has

- `navree new <name> --ui next` writes a small app in `web/`: `lib/navree.ts` (`createNavree()`),
  the BFF route `app/api/[...path]/route.ts`, `proxy.ts` and a login page. `--kit saas` writes the
  full app: shadcn/ui source in `components/ui` with `components.json`, TanStack Query,
  react-hook-form, abilities, real time, `app/(auth)/`, `app/(app)/w/[workspace]/`, `lib/api/` (the
  client, the generated schema and error helpers) and Playwright journeys in `web/e2e`. `--ui next`
  without the kit ships no component kit, no workspace routes and no `lint` or `test` script: the
  main agent adds shadcn/ui at step 6.4 of the first module, before its first screen, so that rule
  NX-8 holds, adds the two scripts, and records both in the plan. A product with workspaces takes
  `--kit saas` at step 1.
- The minimal app also serves Navree's own sign-in pages (`AuthPages`). Record in the plan which
  sign-in the product's people use, the web app's login page or those pages, so QA sweeps that one.
- `@navree/next` exports `createNavree`, `DataTable`, `Pagination`, `useListQuery`, `useOperation`,
  `WorkspaceProvider`, `useWorkspace` and `applyFieldErrors`; it has no form or chart components.
  `@navree/client` is the typed fetch client; `@navree/theme` holds the CSS tokens.
- The code `navree new` writes is the app's own code (rule BLD-7). Read what the kit does before
  replacing it.
- Sign-in across the two: the login page posts to `/api/auth/login`, then to `/api/auth/2fa/verify`.
  The BFF forwards every `/api` call to the API with `Authorization: Bearer`, keeps the access token
  in the `navree_at` cookie and the refresh token in `navree_rt` (both `HttpOnly; SameSite=Lax`) and
  refreshes one request at a time per refresh token. A non-GET request from another origin gets
  `403 invalid_origin`. The API needs no CSRF token in this setup.
- `navree dev` starts the web dev server too; `--no-web` skips it.

## Steps

1. **Inventory.** Map each screen of `DESIGN_DIGEST.md` (`D-n`) to a module (`M-n`) and to a row of
   that module's contract `## Screens` (route, built from, states, design). A screen the contract
   lacks is added to the contract by the main agent (rule BLD-2), never invented in code. Whether to
   translate the design or keep a prototype as built is decided by the table in
   [design-preservation](../design-preservation/SKILL.md); here the design is the visual
   specification, not the markup to copy.
2. **Tokens.** Take colours, type scale, spacing, radius and shadow from `DESIGN_DIGEST.md`
   `## Tokens` and cluster them by role: brand, accent, surface, foreground, border, and status
   pairs with a foreground and a background. Name them by role, never by value. They form one layer
   on top of `@navree/theme`: find where the kit keeps its theme (the stylesheet the root layout
   imports, and `components.json`), read `navree-frontend-next` for how `@navree/theme` is
   overridden, keep the kit's own variable names and add the design's values under names of their
   own. When there is no design, keep `@navree/theme`'s tokens and skip this step.
3. **Module plan.** Before any screen code, show the operator each module's folder
   (`web/modules/<module>`, laid out per [frontend-structure](../frontend-structure/SKILL.md)) and
   its routes under `web/app`, the shared layer (shell and shared components) and the tokens. Record
   them in `EXECUTION_PLAN.md` `## Modules`, below the table: one line per `M-n` with its folder and
   routes, and one `Shared:` line for the shared layer
   ([artifacts.md](../superdev-build/references/artifacts.md) shows the lines); the operator's
   confirmation of the plan (hard rule 2) covers them.
4. **Per module, at step 6.4.** The main agent, or `nextjs-module-builder` in `build` mode, builds
   one module at a time (rule BLD-1), in this order:
   - Types. The module's contract in code is committed (6.1). Run `navree openapi:export` and
     `navree openapi:client` with the paths of `STACK.md` `openapi` and `api_types` (the SaaS kit:
     `pnpm gen:api`) and commit both outputs (hard rule 17). The generated types are the contract;
     screens import nothing else.
   - Data hooks in `modules/<module>/hooks/`, over the typed client.
   - Lists: `useListQuery` with `DataTable` and `Pagination`, using the parameters of the contract's
     `## Lists` table (`filter[<field>]`, `sort`, `search`, `page`, `per_page`), never private
     names.
   - Forms: the kit's form library, fields and rules from the contract's `## Validation` table, API
     field errors onto the fields with `applyFieldErrors` (rule NX-3). Every input has a label and
     every icon-only control a name.
   - Live regions: subscribe as `navree-frontend-next` describes and refetch what is on screen when
     told (rule NX-14).
   - Components, then the route files that compose them. The design usually shows only the populated
     state: invent the other states from its visual language and list them in the contract's
     `States` column (rule NX-10).
5. **Proof.** Run the list in `## Proof of a screen` and record each result line in
   `EXECUTION_PLAN.md` `## Build order` (rule BLD-5).

## Rules

- **NX-1** The browser never holds a token and never calls Navree directly: every call goes through
  the BFF at `/api/**`; only the real-time socket skips it (rule NX-14). `createNavree()` is called
  once, in `lib/navree.ts`, never per request, and the BFF is never copied into the app.
- **NX-2** Response types come only from the generated `schema.d.ts` (`navree openapi:client`): no
  hand-written response type or response schema. A list screen imports the contract's named page
  type, because `Page<T>` has no schema of its own. Regenerate and commit both generated files after
  any route or type change (hard rule 17).
- **NX-3** Branch on the error `code`, never on `message`. The field errors of the API's 400
  `errors` go onto the form with `applyFieldErrors`. A check in the browser (the SaaS kit uses zod)
  only repeats a rule of the contract's `## Validation` table to answer faster and adds no rule of
  its own; the API's answer always wins. Check `navree-frontend-next` at build time for the kit's
  form pattern and follow it.
- **NX-4** The UI hides what `GET /api/me/abilities` denies and branches on no role name; the API
  still checks every request, so a hidden control is convenience, not protection (rule SEC-7).
- **NX-5** Lists keep their state in the URL through `useListQuery`; filtering, sorting and paging
  happen in the API, never over a page already fetched.
- **NX-6** The workspace comes from the `/w/<slug>/` URL and travels as `X-Workspace` in the SaaS
  kit (`WorkspaceProvider`, `useWorkspace`); it is not kept in client state of its own. An app
  without the kit that has workspaces: check `navree-frontend-next` and `navree-workspaces` for how
  the BFF passes the workspace, and record the method in the plan.
- **NX-7** Server data lives in the query cache (TanStack Query in the kit), form state in the form
  library, shareable filters in the URL, and UI state in the component, or in one module store (a
  context with a reducer, or the state library already in `web/package.json`) when siblings share
  it. Server data is never copied into a client store; tokens are never stored in the browser.
- **NX-8** One component kit: the shadcn/ui source in `components/ui`. Before composing a primitive,
  read `components.json` and one existing use to see which primitive library backs it, because
  libraries differ in how their parts compose. A primitive the kit lacks is added from shadcn's
  registry for that style; no second UI library, and no raw `button`, `input`, `select`, `textarea`
  or `dialog` where the kit has the primitive.
- **NX-9** One tokens layer: `@navree/theme` tokens plus the design's values under their own names.
  A search of `web/` for colour literals (`#` and 3 to 8 hex digits, `rgb(`, `hsl(`, `oklch(`)
  outside that layer finds none.
- **NX-10** Every data view has loading (a skeleton of the populated layout), error with retry,
  empty with the next action, and filtered-empty with "clear filters".
- **NX-11** The web app's environment is the kit's `.env.example` (`NAVREE_API_URL` and the
  real-time settings). Navree's documentation and the SaaS kit name the real-time variables
  differently; the kit's names are `NEXT_PUBLIC_REALTIME_*`, so read the kit's file, not the
  documentation. The app's own variables are read in one file that checks them when the app starts
  and names the one that is missing.
- **NX-12** Whether a session is valid is the API's call. The app does not decode, check or refresh
  a token; `proxy.ts` sends a browser without a session to sign-in. For what the BFF does when a
  refresh is refused, read `navree-frontend-next` and follow it.
- **NX-13** Node.js 22 or newer: Navree's installation page says 22, `navree-new-app` says 20.9 and
  the `@navree/*` packages declare 20 or newer, so 22 satisfies all three.
- **NX-14** The real-time WebSocket goes from the browser straight to Navree's server, authorized
  through the BFF's `/broadcasting/auth`. A live region refetches what is on screen; it does not
  build screen state from an event's payload (rule SEC-12).

## Proof of a screen

Run in this order, in `web/` (the `web_dir` of `STACK.md`) with the API running on seeded data
(`navree migrate:fresh --seed`):

1. `pnpm run typecheck` and `pnpm run build` exit 0.
2. The contract drift check: regenerate with `navree openapi:export` and `navree openapi:client`;
   `git diff` shows nothing (`verify-done.mjs`, check `API contract drift`).
3. The module's journey: the Playwright journey in `web/e2e` (SaaS kit; read `package.json` for the
   script that runs it), or a Rust browser test (`navree browser:install`, then
   `cargo test --test browser`; check `navree-browser-testing` for the setup).
4. Every route of the module opened in a real browser at 1440 and 390 px, signed in as each demo
   account that can reach it and as one that cannot, with zero console errors (hard rule 18). The
   account that cannot sees the API's refusal, not a blank page.
5. `ui-auditor` in `next` mode (rules NX-8 and NX-9), and `module-structure-auditor` per
   [frontend-structure](../frontend-structure/SKILL.md), section "Checks".
6. No mock path. The app has no demo mode, no fixture files and no mock route; it runs on the real
   API with the seed (rule BE-14 of [backend-on-navree](../backend-on-navree/SKILL.md)). These
   checks show it:
   - `verify-done.mjs`, check `no placeholder content`, fails on `mockData`, `fakeUsers` and
     `placeholder data` under `web/app`, `web/components`, `web/lib` and `web/modules`, and on any
     file in a folder named `mocks` or `fixtures` there.
   - A search of `web/` for `NEXT_PUBLIC_API_MODE` and `/api/mock` finds nothing.
   - In the browser run of step 4, each list's data arrives in a request to `/api/**` and changes
     after a write and a reload. `data-source-auditor` repeats the trace in `product-audit`.
