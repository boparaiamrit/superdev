---
name: design-preservation
description: Use when the operator brings a prototype that must be kept as built (hand-coded HTML, a design-tool HTML export, or the front end of a product moving to Navree) rather than a design to translate. Copies it verbatim, baselines its pages, and checks every built screen against it with one drift threshold.
---

# Design preservation

This skill keeps a prototype the operator built as the reference for every screen rebuilt from
it. It copies the prototype unchanged into the app, captures each of its pages, and compares every
built screen with those captures, region by region, against one drift threshold (rule PRE-3).
Steps 1 to 3 run at step 3 (Plan) of `superdev-build`; step 4 runs at step 6.5 of every module.

## Preserve or translate

| The source | What to do |
|---|---|
| A prototype the operator built (hand-coded HTML and CSS, or an app they iterated on) | Preserve: this skill |
| A design-tool HTML export of a product that ships | Preserve: this skill |
| The front end of a product moving to Navree | Preserve: this skill, with [prototype-to-navree](../prototype-to-navree/SKILL.md) |
| A design-tool blueprint meant to be translated, screenshots, a mood board, or a request for a redesign | Translate: [design-to-navree-ui](../design-to-navree-ui/SKILL.md) for `front_end: navree`, [design-to-nextjs](../design-to-nextjs/SKILL.md) for `front_end: next` |

When the source fits no row clearly, ask the operator and record the answer with their name and
the date (rule BLD-6).

## Steps

1. Copy the prototype byte for byte into `design/source/`, with its folder structure, leaving out
   only OS metadata (`.DS_Store`, `Thumbs.db`, `desktop.ini`, `__MACOSX/`). Before committing,
   add the line `design/source/** -text` to the app's `.gitattributes` so git never changes the
   copy's line endings. Run the copy check of [references/drift-check.md](references/drift-check.md)
   and put its result line in the commit message.
2. Serve `design/source/` with any static file server bound to `127.0.0.1`, never through the app.
   Open every page once; a page that does not render as the operator sees it goes to step 6.
3. Dispatch `visual-diff-auditor` in `baseline` mode, target `design`, with the served URL, every
   `.html` page under `design/source/` and the absolute paths of this file and
   `references/drift-check.md` (rule BLD-4). It captures every page at the widths of rule PRE-3 into
   `design/baseline/<page>/<width>.png`. Commit the baseline.
4. At step 6.5 of every module, dispatch `visual-diff-auditor` in `compare` mode, target `design`,
   with the running app's URL, the module's page routes, an account that sees them and the same
   reference path. Each contract's `## Screens` row names, in its `Design` column, the page under
   `design/source/` the screen rebuilds. The auditor writes `design/DRIFT.md`; the module's
   screens are not proved while one of their regions is `FAIL` or `NOT RUN`.
5. A region over the threshold is fixed and compared again, or the operator records it as a
   deviation in `design/DEVIATIONS.md` (rule PRE-4). Show the operator the diff image of every
   region you propose as a deviation, in one batch per module.
6. A defect in the source (a missing file, a `localhost` address, a broken script, a page that
   renders blank) is reported to the operator with the file and line, and the copy keeps it
   (rule PRE-5); the operator fixes the source and the copy is taken again, or accepts the page in `ACCEPTANCES.md`.

## On Navree UI

The prototype is the visual reference, not the markup. `navree-design-to-ui` calls such a screen
Keep, and Keep never means copying the design's markup: every screen is built from components
(rule NUI-1). The prototype's exact colours, type, spacing and radius go into the theme (rule
NUI-7), its fonts and images through `AppFont` and `AppImage`. Navree UI is dark by default:
compare in the prototype's colour mode (`Mode::Light`, or `Mode::System` with the browser's colour
scheme set to the prototype's).

The threshold stays the one of rule PRE-3, and a hand-built prototype rarely meets it with Navree
UI's components: the shell (its sidebar, type and spacing) alone moves most header, navigation and
`main` regions. Expect deviations, and say so to the operator at step 3. A prototype that must stay
close to the pixel is a reason to choose a Next.js front end, which keeps its markup. A region that
cannot reach the threshold with Navree UI's components is handled in this order:

1. The theme: a token a custom theme can set (check `navree-ui` for which) takes the prototype's
   exact value, never the nearest built-in one.
2. The gap rule, when the difference is a component Navree UI lacks: hard rule 14, applied as
   [design-to-navree-ui](../design-to-navree-ui/SKILL.md) describes (compose it, or record an
   `N-n` and ship the nearest component the operator agrees to).
3. A deviation for what still differs (the nearest component's shape, a colour `Theme::custom`
   refuses because its text fails WCAG AA, a spacing no token carries), accepted by the operator
   in `ACCEPTANCES.md`, with the measured drift recorded beside it (rule PRE-4).

Copying the prototype's markup, styles or scripts into a page is never the fix (hard rule 14).

## On Next.js

Wrap, don't replace. Keep the prototype's markup, class names and stylesheet, and make them
dynamic: a static part becomes a component that renders the same elements with the same classes
and takes its text and items as props; data arrives through the BFF and the generated types
([design-to-nextjs](../design-to-nextjs/SKILL.md)). The kept stylesheet is the design's part of
the tokens layer of rule NX-9. Where a style must be rewritten, use the exact value (13 px
stays 13 px, an opacity of 0.87 stays 0.87, an inline style stays inline), never the nearest
token of the component kit. Swapping a prototype element for a kit component that looks different
is a deviation (rule PRE-4), not a refactor.

## Rules

- **PRE-1** Copy first, build second, restyle never: no reformatting, renaming, minifying or
  cleanup in `design/source/`.
- **PRE-2** Built screens are compared with the served copy in `design/source/`, never with files
  elsewhere.
- **PRE-3** One drift threshold for the whole plugin, stated only here and measured as
  [references/drift-check.md](references/drift-check.md) describes: a page region fails when more
  than 1% of its pixels differ after a 5% colour fuzz, at 1440 and 390 px. `frontend-structure`
  refactors use the same threshold.
- **PRE-4** A deviation exists only as a row in `design/DEVIATIONS.md` with page, region, reason,
  accepted drift and the `ACC-n` of the operator's acceptance.
- **PRE-5** A defect in the source (missing file, `localhost` address, broken script) is reported
  to the operator, never fixed in the copy.

## Reference files

| File | Read it |
|---|---|
| [references/drift-check.md](references/drift-check.md) | at steps 1, 3, 4 and 5: the copy check, the capture conditions, regions and masks, the compare command, and the formats of `design/DRIFT.md` and `design/DEVIATIONS.md` |
