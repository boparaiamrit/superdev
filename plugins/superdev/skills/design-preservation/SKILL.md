---
name: design-preservation
description: Use ONLY when the user provides a **prototype** that must be preserved — an existing HTML/Figma export, a built-and-shipping app's frontend being migrated, a hand-coded mockup the user has iterated on. Treats that prototype as a HOLY GRAIL — copies it verbatim, mirrors it inside the Next.js app, refuses to "improve" or restyle. Runs design-fidelity-auditor at every Phase C wave gate; flags pixel drift > 1%. Do NOT use this for Claude Design output (those are blueprints meant to be translated into shadcn; preservation would defeat the design-to-nextjs purpose).
---

# Design Preservation — the Holy Grail rule

The single most common superdev failure mode: an agent gets a design and "improves" it — changes the spacing, swaps the typography, reinterprets the layout in shadcn primitives, makes "what they think the user really wanted." The result looks generic; the user spends hours pulling it back to the original.

This skill forbids that. The original design is sacred. We **copy first, wire second, restyle never**.

## The Iron Law

```
THE ORIGINAL DESIGN IS A HOLY GRAIL.
WE DO NOT IMPROVE IT, RESTYLE IT, OR REINTERPRET IT.
WE COPY VERBATIM, RENDER AS A MIRROR, AND ONLY THEN WIRE DATA.

Pixel drift > 1% in any region against the source = build fails.
```

## When to use

- ✅ User provides a **prototype** they've built — hand-coded HTML, Figma HTML export, a shipping app's existing frontend being migrated
- ✅ `prototype-to-saas` is running — the prototype's UI must survive the rewire
- ✅ User says "match this exactly" / "don't change the design" / "preserve the UI" / "don't restyle it"
- ✅ A previous frontend build drifted from the source and the user is frustrated — recover by establishing a baseline now and gating future changes on it

## When NOT to use

- ❌ Claude Design output — those are blueprints meant to be **reinterpreted** into shadcn/ui by `design-to-nextjs`. Preserving them defeats the entire skill's purpose.
- ❌ Mood-boards or "vibes" references — not implementable specs
- ❌ Greenfield project with no design source (use `design-to-nextjs` directly)
- ❌ User explicitly asked for a redesign or refresh

## How to tell the difference

| Source | Use design-preservation? | Use design-to-nextjs? |
|---|:---:|:---:|
| User-built HTML/CSS prototype | ✅ Yes — copy verbatim | ⚠️ Only after preservation, for data-wiring |
| Figma HTML export of a shipping product | ✅ Yes | ⚠️ Only for data-wiring |
| Existing Next.js prototype with JSON fixtures (prototype-to-saas migration) | ✅ Yes — preserve UI while rewiring | n/a |
| Claude Design output (`design/index.html` from a Claude Design session) | ❌ No | ✅ Yes — translate to shadcn |
| Screenshots only, no DOM/CSS | ❌ No | ✅ Yes |
| Mood-board / reference images | ❌ No | ✅ Yes |

## How the orchestrator should use this skill

The orchestrator inspects the user's design source and routes accordingly:

- **Source is a prototype** (user-built HTML, Figma export, existing app) → insert `design-preservation` as **Phase B.0** before `monorepo-bootstrapper`. Subsequent waves run against the preserved mirror.
- **Source is Claude Design output** → skip `design-preservation` entirely. Hand directly to `design-to-nextjs` for shadcn translation.
- **`prototype-to-saas` is running** → `design-preservation` runs alongside `codebase-discoverer` so the UI baseline is captured before `frontend-rewirer` touches anything.

When `design-preservation` IS active, the orchestrator schedules `design-fidelity-auditor` as a wave gate at the end of every Phase C feature build. Any drift > 1% from the source mirror blocks the wave from completing.

## The 3 phases

```
┌────────────────────────┐    ┌────────────────────────────┐    ┌──────────────────────┐
│  PHASE 0a — COPY       │───▶│  PHASE 0b — MIRROR         │───▶│  PHASE 0c — DIFF     │
│  design-source-mirror  │    │  design-source-mirror      │    │  design-fidelity-    │
│                        │    │                            │    │  auditor             │
│  Byte-for-byte copy of │    │  Mount the source under    │    │  Screenshot mirror   │
│  every HTML / CSS / JS │    │  /__design-source/ route   │    │  vs source. Pixel-   │
│  / image / font from   │    │  inside the Next.js app    │    │  diff. Must be 100%. │
│  the handoff           │    │                            │    │                      │
└────────────────────────┘    └────────────────────────────┘    └──────────────────────┘
            │                            │                                │
            ▼                            ▼                                ▼
      design-source/                /__design-source/                FIDELITY_BASELINE.md
      under apps/web/             (only mounted in dev mode)
```

### Phase 0a — Verbatim copy

`design-source-mirror` copies the design handoff into `apps/web/src/design-source/`:
- Every HTML file, every CSS file, every JS file
- Every image, every font, every SVG icon
- **Byte-for-byte**. No formatting, no rename, no "while I'm here" cleanup.
- Preserves directory structure exactly as the handoff has it.

### Phase 0b — Mirror route

`design-source-mirror` adds a Next.js dev-only route `/__design-source/` that serves the copied files statically. The mirror renders pixel-identical to the source when opened in a browser.

This is the SOURCE OF TRUTH for every later auditor. When the auditor screenshots and compares, it compares **against the mirror** — not against the original handoff path. If the mirror drifts from the source, that's a Phase 0 bug; if the componentized app drifts from the mirror, that's a Phase C bug.

### Phase 0c — Establish fidelity baseline

`design-fidelity-auditor` screenshots every page of the mirror at:
- Desktop (1280×800)
- Tablet (768×1024)
- Mobile (375×667)

Saves to `design-baseline/<page>/<viewport>.png`. Writes `FIDELITY_BASELINE.md` recording every page+viewport pair.

These baselines are what every Phase C wave-gate audit compares against.

## Phase C wave-gate audit (continuous)

Every time a frontend agent finishes a feature, `design-fidelity-auditor` runs:

1. For each route the agent built, screenshot at each viewport
2. Pixel-diff against `design-baseline/<page>/<viewport>.png`
3. Compute drift % per region
4. **Fail the wave** if any region drifts > 1%

Findings go to `DESIGN_DRIFT_<feature>.md` with side-by-side images.

## What "preserving" means

| ✅ Allowed | ❌ Forbidden |
|---|---|
| Wrap a `<button>` in a React component that renders the SAME `<button>` markup | Replace the `<button>` with shadcn's `<Button>` (different default styling) |
| Add `onClick` to make it interactive | Change className, padding, color, font, border-radius |
| Add `useQuery` to source data instead of hardcoded HTML | Move text into a different element type "for semantics" |
| Add ARIA attributes for accessibility (if missing) | Reformat HTML / change tag names "for clarity" |
| Replace `<img src="…">` with `<Image>` from Next.js | Add new visual elements (icons, badges, etc.) the source doesn't have |
| Convert inline `<style>` to Tailwind utility classes that produce the SAME computed CSS | Convert inline `<style>` to Tailwind utility classes that look "close enough" |

The rule: **if `design-fidelity-auditor` flags pixel drift, you violated the rule, period**. There is no "but it's better this way".

## When the user WANTS to deviate

If a wave-gate audit flags drift and the deviation is intentional, the user must explicitly mark it in `DESIGN_DEVIATIONS.md`:

```markdown
# Approved design deviations

## /companies — "Add company" button uses shadcn primary instead of source button
- Reason: user requested keyboard-focus accessibility that source button lacks
- Approved by: <user>
- Date: 2026-05-22
- Drift accepted: 8% on button region
```

The auditor reads this file. Deviations listed here don't fail the wave. **Everything else does.**

## Agent teams (drift severity, optional)

For drift findings between 1% and 5%, the deviation may or may not be visible to a human. Optional:

```
Dispatch 3-teammate drift debate.
Teammate A — designer: "would this drift be noticed by the designer who made the source?"
Teammate B — pixel-strict: "no drift is acceptable; flag everything > 0.5%"
Teammate C — pragmatist: "is this drift below human-perception threshold for this region type?"

Majority verdict. Requires CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.
```

## Reference files

- [`references/verbatim-copy-rules.md`](references/verbatim-copy-rules.md) — what counts as "byte-for-byte"
- [`references/wrap-dont-replace-patterns.md`](references/wrap-dont-replace-patterns.md) — how to add interactivity without restyling
- [`references/agent-definitions.md`](references/agent-definitions.md) — dispatch prompts
