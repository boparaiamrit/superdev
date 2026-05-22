# Token Extraction from Claude Design HTML

This procedure extracts design tokens (colors, typography, spacing, radii, shadows, motion) from the Claude Design output into a Tailwind config + a `tokens.ts` file. Run this in Phase 2 before any feature code is written.

## Why this matters

Claude Design produces HTML with inline Tailwind-like utility classes and inline styles. If you copy that HTML into components without extracting tokens, you'll have hex codes scattered across the codebase. The first time the brand changes (or you add dark mode, or a designer comes in), you'll regret it. Extract once, reference forever.

## What to extract

```
Tokens to extract:
├── Colors        — every unique color value, clustered by semantic role
├── Typography    — font families, sizes, weights, line-heights
├── Spacing       — only arbitrary values used consistently (most can use Tailwind defaults)
├── Radii         — border-radius values
├── Shadows       — every box-shadow
├── Breakpoints   — usually defaults; extract if design uses custom ones
└── Motion        — transition durations and easings, @keyframes definitions
```

## Step-by-step extraction

### Step 1 — Pull every color out of the HTML

Search the design HTML for color values. They appear in three forms:

```html
<!-- Form 1: arbitrary Tailwind class -->
<div class="bg-[#1a2b3c] text-[hsl(220_30%_15%)]">

<!-- Form 2: standard Tailwind class -->
<div class="bg-slate-900 text-zinc-50">

<!-- Form 3: inline style -->
<div style="background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%)">

<!-- Form 4: CSS variables in <style> blocks -->
<style>
  :root { --brand-primary: #4f46e5; --surface-1: #fafafa; }
</style>
```

Collect everything. Deduplicate. Convert all to HSL or OKLCH (OKLCH is preferred for color accuracy across dark mode).

### Step 2 — Cluster colors by purpose

A typical product has these color roles:

```
brand        — primary brand color, plus 50–900 scale
accent       — secondary accent (often used for highlights, badges)
surface      — page background, card background, elevated surface (3 levels usually)
foreground   — text colors at various contrast levels
border       — divider, input border, focus ring
status       — success, warning, error, info (each with a foreground + background pair)
```

Map every extracted color to one of these roles. If a color doesn't fit, ask whether it's noise (one-off from the design) or a missed token.

### Step 3 — Name semantically

NEVER name colors by hex (`color1`, `gray3`). Always name by role:

```ts
// ✅ semantic
brand.500
surface.muted
text.primary
border.subtle
status.success.foreground

// ❌ syntactic
gray3
color1
primary  // ambiguous — primary text or primary brand?
```

### Step 4 — Build the Tailwind config

Use the template below. Fill in the extracted values.

### Step 5 — Build `src/styles/tokens.ts`

The same values, exported as TS constants for use in JS contexts (Framer Motion variants, chart colors, etc.). Single source of truth: Tailwind config reads from `tokens.ts`.

### Step 6 — Build `globals.css`

CSS custom properties for tokens that need to flip in dark mode.

---

## Templates

### `src/styles/tokens.ts`

```ts
// Single source of truth for design tokens.
// Tailwind config and runtime code both read from here.

export const colors = {
  brand: {
    50:  'hsl(220 100% 97%)',
    100: 'hsl(220 100% 94%)',
    200: 'hsl(220 100% 88%)',
    300: 'hsl(220 100% 78%)',
    400: 'hsl(220 100% 65%)',
    500: 'hsl(220 100% 50%)',   // primary
    600: 'hsl(220 100% 42%)',
    700: 'hsl(220 100% 34%)',
    800: 'hsl(220 100% 26%)',
    900: 'hsl(220 100% 18%)',
    950: 'hsl(220 100% 10%)',
  },
  accent: { /* ... */ },
  surface: {
    DEFAULT: 'hsl(0 0% 100%)',
    muted:   'hsl(220 14% 96%)',
    raised:  'hsl(0 0% 100%)',
    sunken:  'hsl(220 14% 98%)',
  },
  text: {
    primary:   'hsl(220 30% 10%)',
    secondary: 'hsl(220 15% 35%)',
    muted:     'hsl(220 10% 55%)',
    inverted:  'hsl(0 0% 100%)',
  },
  border: {
    DEFAULT: 'hsl(220 13% 91%)',
    subtle:  'hsl(220 13% 95%)',
    strong:  'hsl(220 13% 80%)',
    focus:   'hsl(220 100% 50%)',
  },
  status: {
    success: { fg: 'hsl(142 76% 26%)', bg: 'hsl(142 76% 95%)' },
    warning: { fg: 'hsl(38 92% 36%)',  bg: 'hsl(38 92% 95%)'  },
    error:   { fg: 'hsl(0 84% 40%)',   bg: 'hsl(0 84% 96%)'   },
    info:    { fg: 'hsl(217 91% 40%)', bg: 'hsl(217 91% 96%)' },
  },
} as const;

export const fontFamily = {
  sans: ['Inter', 'system-ui', 'sans-serif'],
  mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
  display: ['Cal Sans', 'Inter', 'sans-serif'],
} as const;

export const fontSize = {
  xs:   ['0.75rem',  { lineHeight: '1rem' }],
  sm:   ['0.875rem', { lineHeight: '1.25rem' }],
  base: ['1rem',     { lineHeight: '1.5rem' }],
  lg:   ['1.125rem', { lineHeight: '1.75rem' }],
  xl:   ['1.25rem',  { lineHeight: '1.75rem' }],
  '2xl':['1.5rem',   { lineHeight: '2rem' }],
  '3xl':['1.875rem', { lineHeight: '2.25rem' }],
  '4xl':['2.25rem',  { lineHeight: '2.5rem' }],
  '5xl':['3rem',     { lineHeight: '1.1' }],
  '6xl':['3.75rem',  { lineHeight: '1.1' }],
} as const;

export const borderRadius = {
  none: '0',
  sm:   '0.25rem',
  DEFAULT: '0.5rem',
  md:   '0.5rem',
  lg:   '0.75rem',
  xl:   '1rem',
  '2xl':'1.5rem',
  full: '9999px',
} as const;

export const boxShadow = {
  sm:    '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  DEFAULT: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  md:    '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  lg:    '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  xl:    '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
} as const;

export const duration = {
  fast:   '150ms',
  base:   '200ms',
  slow:   '300ms',
  slower: '500ms',
} as const;

export const easing = {
  out:   'cubic-bezier(0.16, 1, 0.3, 1)',
  inOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
} as const;
```

### `tailwind.config.ts`

```ts
import type { Config } from 'tailwindcss';
import { colors, fontFamily, fontSize, borderRadius, boxShadow, duration, easing } from './src/styles/tokens';

const config: Config = {
  darkMode: ['class'],
  content: [
    './src/app/**/*.{ts,tsx}',
    './src/components/**/*.{ts,tsx}',
    './src/modules/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors,
      fontFamily,
      fontSize,
      borderRadius,
      boxShadow,
      transitionDuration: duration,
      transitionTimingFunction: easing,
      keyframes: {
        // Add any @keyframes extracted from the design here
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      animation: {
        'fade-in':  'fade-in 200ms cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-up': 'slide-up 200ms cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
};

export default config;
```

### `src/app/globals.css`

shadcn's `init` writes a baseline `globals.css` with its standard CSS variables (`--background`, `--foreground`, `--primary`, etc.). Keep those names — every shadcn primitive references them. Layer brand-specific tokens on top under different names so the two don't collide.

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* === shadcn standard variables — DO NOT rename === */
    /* Components in src/components/ui/* read these by name. */
    --background:              0 0% 100%;
    --foreground:              220 30% 10%;
    --card:                    0 0% 100%;
    --card-foreground:         220 30% 10%;
    --popover:                 0 0% 100%;
    --popover-foreground:      220 30% 10%;
    --primary:                 220 100% 50%;          /* match brand-500 */
    --primary-foreground:      0 0% 100%;
    --secondary:               220 14% 96%;
    --secondary-foreground:    220 30% 10%;
    --muted:                   220 14% 96%;
    --muted-foreground:        220 15% 35%;
    --accent:                  220 14% 96%;
    --accent-foreground:       220 30% 10%;
    --destructive:             0 84% 60%;
    --destructive-foreground:  0 0% 100%;
    --border:                  220 13% 91%;
    --input:                   220 13% 91%;
    --ring:                    220 100% 50%;
    --radius:                  0.5rem;

    /* Sidebar block uses its own scoped variables — also leave these as shadcn ships them: */
    --sidebar-background:          0 0% 98%;
    --sidebar-foreground:          220 5% 26%;
    --sidebar-primary:             220 100% 50%;
    --sidebar-primary-foreground:  0 0% 98%;
    --sidebar-accent:              220 14% 96%;
    --sidebar-accent-foreground:   220 5% 10%;
    --sidebar-border:              220 13% 91%;
    --sidebar-ring:                220 100% 50%;

    /* === Brand extensions — used in tokens.ts and tailwind.config.ts === */
    /* These don't collide with shadcn names. Reference them via custom
       Tailwind utilities (bg-brand-500, etc.) for design-specific accents. */
    --brand-50:   220 100% 97%;
    --brand-100:  220 100% 94%;
    --brand-200:  220 100% 88%;
    --brand-300:  220 100% 78%;
    --brand-400:  220 100% 65%;
    --brand-500:  220 100% 50%;
    --brand-600:  220 100% 42%;
    --brand-700:  220 100% 34%;
    --brand-800:  220 100% 26%;
    --brand-900:  220 100% 18%;
  }

  .dark {
    --background:              220 30% 10%;
    --foreground:              0 0% 98%;
    --card:                    220 30% 12%;
    --card-foreground:         0 0% 98%;
    --popover:                 220 30% 12%;
    --popover-foreground:      0 0% 98%;
    --primary:                 220 100% 60%;
    --primary-foreground:      220 30% 10%;
    --secondary:               220 30% 16%;
    --secondary-foreground:    0 0% 98%;
    --muted:                   220 30% 16%;
    --muted-foreground:        220 10% 70%;
    --accent:                  220 30% 16%;
    --accent-foreground:       0 0% 98%;
    --destructive:             0 70% 50%;
    --destructive-foreground:  0 0% 98%;
    --border:                  220 30% 20%;
    --input:                   220 30% 20%;
    --ring:                    220 100% 60%;

    --sidebar-background:          220 30% 10%;
    --sidebar-foreground:          220 5% 96%;
    --sidebar-primary:             220 100% 60%;
    --sidebar-primary-foreground:  0 0% 100%;
    --sidebar-accent:              220 30% 16%;
    --sidebar-accent-foreground:   220 5% 96%;
    --sidebar-border:              220 30% 20%;
    --sidebar-ring:                220 100% 60%;
  }

  * {
    @apply border-border;
  }

  body {
    @apply bg-background text-foreground font-sans antialiased;
  }
}
```

Note the format: **HSL channels only** (`220 100% 50%`), not `hsl(220, 100%, 50%)`. shadcn components wrap them in `hsl(var(--primary))` themselves. Tailwind's color config does the same:

```ts
// tailwind.config.ts — relevant excerpt
theme: {
  extend: {
    colors: {
      // shadcn names — Tailwind wraps the channels in hsl()
      background:  'hsl(var(--background))',
      foreground:  'hsl(var(--foreground))',
      primary: {
        DEFAULT: 'hsl(var(--primary))',
        foreground: 'hsl(var(--primary-foreground))',
      },
      // ... all shadcn names
      // brand extensions:
      brand: {
        50:  'hsl(var(--brand-50))',
        100: 'hsl(var(--brand-100))',
        // ... through 900
      },
    },
  },
},
```

With this setup, every shadcn primitive works as-shipped (it reads `--primary`, `--background`, etc.), and brand-specific accents are available via `bg-brand-500` / `text-brand-600` for hero sections and the like.

## Mapping inline classes from Claude Design to tokens

When you see Claude Design output like this:

```html
<div class="bg-[#4f46e5] text-white p-4 rounded-[12px] shadow-[0_4px_12px_rgba(0,0,0,0.08)]">
```

Map it to token-based classes:

```tsx
<div className="bg-brand-500 text-text-inverted p-4 rounded-lg shadow-md">
```

The arbitrary-value classes (`bg-[#4f46e5]`) are the signal that token extraction is needed. After Phase 2, no component should contain arbitrary-value classes for colors, radii, or shadows. Spacing arbitrary values (`mt-[13px]`) are acceptable if rare; if you see them more than 3 times, add to the spacing scale.

## Quick sanity check

Before declaring Phase 2 done, grep:

```bash
# Should return zero results in module/component code
grep -rE 'bg-\[#|text-\[#|border-\[#|shadow-\[' src/modules src/components/shared
```

If any hits come back, those are missed tokens. Add them to `tokens.ts`, then update the components.
