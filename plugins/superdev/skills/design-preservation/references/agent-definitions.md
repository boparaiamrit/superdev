# design-preservation — dispatch reference

## Phase 0a + 0b — design-source-mirror

```
Use the design-source-mirror agent.

Source: <path to user's prototype/Figma export/etc.>
Destination: apps/web/src/design-source/

Copy byte-for-byte (verify with diff -r). Skip OS metadata only. Do NOT
reformat, prettify, lint, or "improve" any file.

After copy: mount /__design-source/ route (dev-only). Smoke test that every
HTML file renders identically to the source when opened directly.
```

## Phase 0c — design-fidelity-auditor (baseline capture)

```
Use the design-fidelity-auditor agent in BASELINE mode.

For every page in apps/web/src/design-source/, open it in Playwright at
desktop (1280×800), tablet (768×1024), and mobile (375×667). Screenshot
to design-baseline/<page-slug>/<viewport>.png.

Produce FIDELITY_BASELINE.md listing every page+viewport pair captured.
This is the source of truth for all subsequent checkpoint audits.
```

## Module checkpoint — design-fidelity-auditor (drift check)

Run after every frontend agent in the current group finishes:

```
Use the design-fidelity-auditor agent.

Inputs:
- design-baseline/ (from Phase 0c)
- DESIGN_DEVIATIONS.md (user-approved exceptions, if any)
- The list of routes built in this group: <list>

For each route × viewport:
- Build the app in production-build mode
- Screenshot via Playwright
- Pixel-diff against the baseline
- Compute drift% globally and per region (header / sidebar / main / footer)

Produce DESIGN_DRIFT_<feature>.md. Verdict PASS if all routes ≤ 1% drift
(or approved). Verdict FAIL otherwise — the main agent must re-dispatch
frontend-rewirer / frontend-module-builder with the diff images.

Write recurring drift causes to .claude/memory/superdev-learned/design-drift-patterns.md.
```
