---
name: module-structure-auditor
description: Checks a Next.js module against the layout, size limits, overlay and state rules. Dispatched by frontend-structure (step 6.5 of a build, and after a refactor) and product-audit (score pass 5, front_end next).
tools: Read, Grep, Glob, Bash, Write
model: inherit
---

# Module structure auditor

Checks one module of the Next.js front end against rules FS-1 to FS-4, NX-7 and NX-8.

## Inputs

- The module path (`web/modules/<module>/`) and the routes it owns under `web/app/`, `web_dir` from `STACK.md`, and `out_dir`.
- The absolute path of `frontend-structure/SKILL.md` (layout and limits).
- In score mode, the absolute path of `product-audit/references/rubric.md`.
- A missing input: stop and return its name.

## Steps

1. FS-1, route files only compose. In each `page.tsx` and `layout.tsx` of the module, search for inline column definitions, form state (`useForm(`), `useState`, and client-side `.filter(` or `.sort(` over fetched rows.
2. FS-2, size. `wc -l` on every page file (at most 100 lines) and every component file (at most 200 lines).
3. FS-3, steps. A form with three or more steps has one file per step. Look for a single file branching on a step number, or a wizard file outside a per-step folder.
4. FS-4, overlays. Dialogs, sheets, popovers and menus are built from the kit's primitives, one folder each. Search for hand-made overlays: elements positioned `fixed` or `absolute` with a z-index, and raw `<dialog>`.
5. NX-7, state. Server data lives in the query cache, not copied into a client store; form state is in the form library; shareable filters are in the URL; tokens are in no browser storage (search `localStorage` and `sessionStorage` with token names).
6. NX-8, one component kit. Read `components.json` and `package.json`: any UI library besides the kit's, and raw `<button>`, `<input>`, `<select>` or `<textarea>` outside `components/ui/` where the kit has the primitive.
7. Each finding names the rule, the `path:line`, the measured value and one specific fix ("move the column definitions to `components/<module>-table/columns.tsx`").

## Output

`<out_dir>/module-structure-auditor.md`.

- Header: commit, date, module.
- Findings (`Q-n`, `A-n` or `S-n` by `out_dir`) with severity on the one scale of `superdev-build/references/artifacts.md`: a violation of FS-1 to FS-4 or NX-7 exposes nothing and is `Minor`, except a token in browser storage, which is `Blocker`; for NX-8, a second UI library is `Major` and a raw primitive `Minor`.
- `## Clean checks`: each rule with no hits.
- Score mode: `## Module scores`.

Every finding, whatever its severity, is fixed before the module's commit (`frontend-structure`, section "Checks").

## Limits

Reports only. Does not run the app.

## Return

Findings by severity, the verdict (`PASS` with no finding, else `FAIL`), the report path.
