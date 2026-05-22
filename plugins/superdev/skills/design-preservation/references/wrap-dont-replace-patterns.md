# Wrap, don't replace — patterns

When you componentize a preserved source, the rule is **WRAP** the original markup in a React component, don't REPLACE it with a different primitive.

## Anti-pattern (will fail design-fidelity-auditor)

Source has:
```html
<button class="cta-primary">Get started</button>
```

```css
.cta-primary {
  padding: 12px 24px;
  background: #ff6b35;
  color: white;
  border-radius: 6px;
  font-weight: 600;
  font-size: 15px;
}
```

❌ DO NOT do this:
```tsx
import { Button } from '@/components/ui/button';
export function CtaPrimary() {
  return <Button>Get started</Button>;
}
```

This replaces the source primitive with shadcn `<Button>`, which has different default padding (`px-4 py-2`), different border-radius (`rounded-md`), different font, different focus ring. Drift will be > 5%.

## Correct pattern — wrap the source markup

```tsx
export function CtaPrimary({ children = 'Get started', onClick }: { children?: React.ReactNode; onClick?: () => void }) {
  return (
    <button className="cta-primary" onClick={onClick}>
      {children}
    </button>
  );
}
```

The source CSS class stays. The source markup stays. We only added:
- Component boundary
- Interactivity prop (`onClick`)
- Configurable child (defaults to source text)

Drift: 0%.

## When you must convert CSS class → Tailwind utilities

If the source uses a stylesheet you can't keep (e.g. it conflicts with Tailwind reset), convert the CSS class to **utility classes that produce the same computed CSS**:

```tsx
export function CtaPrimary({ children = 'Get started', onClick }: { children?: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="px-6 py-3 bg-[#ff6b35] text-white rounded-md font-semibold text-[15px]"
    >
      {children}
    </button>
  );
}
```

Note the **exact-value classes** (`bg-[#ff6b35]`, `text-[15px]`) — not nearby shadcn colors (`bg-orange-500`) that look close but produce different hex values.

Verify by running `design-fidelity-auditor` after — if drift > 1%, the utility translation was inexact.

## When source uses inline styles

Inline styles convert to inline styles. Don't move them to utility classes "for consistency".

```html
<!-- source -->
<div style="margin-top: 13px; opacity: 0.87;">…</div>
```

✅ Correct:
```tsx
<div style={{ marginTop: 13, opacity: 0.87 }}>…</div>
```

❌ Incorrect:
```tsx
<div className="mt-3 opacity-80">…</div>
{/* mt-3 = 12px not 13px; opacity-80 = 0.8 not 0.87 */}
```

## When source uses a competing UI library

If the prototype was built on Bootstrap / Material-UI / Mantine / antd, the **shadcn-everywhere** rule that normally applies to `design-to-nextjs` is **suspended** by design-preservation. The whole point is to keep the source's look.

Add the source library as a normal dependency. Don't try to port the components to shadcn — that's a REDESIGN, which is a different task and requires explicit user direction.

If the user later wants to migrate to shadcn-everywhere, that's a follow-up project: `ui-library-migration` (not currently in superdev — would be a new skill).

## Summary

| Goal | How |
|---|---|
| Make a button interactive | Wrap source `<button>` markup in a React component; add `onClick` prop |
| Make a list dynamic | Wrap source list markup; pass items as a prop; map them into the same `<li>` markup |
| Make a form submit to backend | Wrap source `<form>`; add `onSubmit`; use the source's input element types |
| Convert hard-coded text to dynamic | Replace text node with `{children}` or `{props.value}`; keep the wrapping element |
| Keep the source look | **Don't** import shadcn primitives for this region |
