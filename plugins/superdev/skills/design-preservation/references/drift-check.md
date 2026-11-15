# Drift check

How a built screen is compared with the prototype page it preserves, and the formats of
`design/DRIFT.md` and `design/DEVIATIONS.md`. `<page>` is the page's path under `design/source/`
without `.html`, with `/` written as `-` (`invoices/list.html` is `invoices-list`).

## Capture conditions

Both captures of a pair (the baseline and the built screen) are full-page screenshots taken at the
same width, in the same colour mode and the same browser build (its name and version go into
`DRIFT.md`), after the fonts have loaded (`document.fonts.ready`) and with
`prefers-reduced-motion: reduce` emulated. The app shows the records the prototype shows (seeded
from the prototype's data, rule PRO-7), signed in as the person the prototype shows.

## Regions and masks

A region is a rectangle taken from the baseline: the box of the page's header, navigation (`nav`
or the sidebar), `main` and footer where the page has them, else the whole page. The same
rectangle is cut from both captures; one that runs past the end of the built screen's capture is
`FAIL` with drift 100. Timestamps, ids, live counters and anything else that changes between two
loads are covered with the same flat rectangle in both captures before the compare
(`magick <capture> -fill gray50 -draw "rectangle <x0>,<y0> <x1>,<y1>" <masked>`), and each mask is
listed under the `DRIFT.md` table.

## Compare

With ImageMagick 7 (on ImageMagick 6, `magick` is `convert` and `magick compare` is `compare`):

```text
magick <capture> -crop <w>x<h>+<x>+<y> +repage <region>.png
magick compare -metric AE -fuzz <fuzz>% <baseline region>.png <built region>.png <diff>.png
```

`<fuzz>` is the colour fuzz of rule PRE-3. `-metric AE` prints on stderr the number of pixels that differ by more than the fuzz; take the
first number printed. `compare` exits 1 when the images differ (not an error) and 2 on an error.
The region's drift is that number divided by the region's pixels (w × h), as a percentage with two
decimals. A region over the threshold of rule PRE-3 ([design-preservation](../SKILL.md)) is
`FAIL`, unless a row of `DEVIATIONS.md` accepts at least that drift for the same page and region.

## `design/DRIFT.md`

Written by `visual-diff-auditor` at each compare (captures and diff images under
`design/visual-diff-auditor/<page>/`); a run replaces the rows of the pages it compared. `Result`
is `PASS`, `FAIL` or `NOT RUN` (not captured, reason under the table; blocks until accepted).

```markdown
# Design drift
Commit: 3f2a9c1, browser Chromium <version>

| Page | Width | Mode | Region | Drift % | Result | Diff image |
|---|---|---|---|---|---|---|
| invoices-list | 390 | light | header | 3.10 | FAIL | design/visual-diff-auditor/invoices-list/390-header.png |

Masks: invoices-list, 1440, rectangle 1180,96 1400,120, the "Updated 10:42 IST" line.
```

## `design/DEVIATIONS.md`

Written by the operator, or by the main agent quoting the operator's message (rule BLD-6); no
agent adds a row on its own.

| Page | Region | Reason | Accepted drift | Approved by | Date |
|---|---|---|---|---|---|
| invoices-list | header | the Navree UI top bar replaces the prototype's header bar | 4.0% at 1440, 6.5% at 390 | Meera Sharma | 2026-11-20 |

## Copy check

```text
python -X utf8 -c "import hashlib,pathlib,sys;r=pathlib.Path(sys.argv[1]);s={'.DS_Store','Thumbs.db','desktop.ini'};[print(hashlib.sha256((r/f).read_bytes()).hexdigest(),f) for f in sorted(p.relative_to(r).as_posix() for p in r.rglob('*') if p.is_file() and p.name not in s and '__MACOSX' not in p.parts)]" <folder>
```

This prints the SHA-256 of every file under a folder, sorted by path, without OS metadata. Run it
on the prototype's folder and on `design/source/`, each into a file outside the app; exit 0 and no
output from `git diff --no-index --exit-code <source list> <copy list>` is `PASS` (result line
`copy check: PASS, <n> files`). Python 3 and git are all it needs, on Linux, macOS and Windows.
