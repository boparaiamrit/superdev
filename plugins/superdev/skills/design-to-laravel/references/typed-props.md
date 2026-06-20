# Typed Props — Hand-Written Types in `resources/js/types/`

Inertia pages receive their data as **props** from the controller's `Inertia::render`. Those props have to be typed somewhere, and in the Laravel React starter kit that "somewhere" is **hand-written TypeScript in `resources/js/types/`** — the starter-kit convention. This reference is the contract for how to write those types and the discipline that keeps the page code clean.

## The core discipline: no `?.`, no `??` on prop fields

The single rule that makes Inertia pages pleasant to read:

> **The controller guarantees the shape. The page consumes it without defensive access.**

Concretely, in a page you should never write `company?.name`, `company.domain ?? '—'` *as a way to paper over an unknown shape*, or `counts?.contacts`. Every field a page reads is **present and typed** because the controller put it there. If a value can be absent, that absence is modeled **explicitly** in the type (`domain: string | null`, or a discriminated union), and you handle the explicit case — you do not guess with optional chaining.

This is the same "view-shape" contract the Next.js path enforces, with one difference noted at the bottom: there it is machine-generated; here it is a **discipline on hand-written types** (spec D4).

## The canonical example

```ts
// resources/js/types/companies.ts
export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'
export interface CompanyView {
  id: string
  name: string
  domain: string | null            // explicit null, never "missing"
  industry: Industry               // value IS the label
  counts: { contacts: number; open_leads: number; won_deals: number }  // default 0 server-side
  last_activity: { kind: 'None' } | { kind: 'Email Sent'; at: string; label: string }
  created_at: string               // ISO 8601
}
export interface Paginated<T> { data: T[]; total: number; page: number; per_page: number }
```

Read that type alongside the page that consumes it (`claude-design-to-inertia.md` worked example): every field the page touches is in the interface, every variant is discriminated, every count is a number. No `?.` appears in the page because none is needed.

## The rules, one by one

### 1. Every field present and typed

A prop field that the page reads must exist on the interface with a concrete type. No `any`, no implicit `undefined`. If the controller can omit a field on some renders, that is a different shape — model it as a union or split the type, do not make the field optional-by-accident.

```ts
// ✅ the page can read view.name, view.industry, view.counts.contacts with zero guards
interface CompanyView {
  id: string
  name: string
  industry: Industry
  counts: { contacts: number; open_leads: number; won_deals: number }
}
```

### 2. Nullable is explicit, never "optional-by-omission"

There are two different ideas people blur together:

- `domain: string | null` — "this field is always sent; sometimes its value is null." Correct for nullable data.
- `domain?: string` — "this field might not be on the object at all." This invites `?.` and means the page can't trust the shape. Avoid it for view props.

```ts
// ✅ always present, value may be null — page renders the null branch explicitly
domain: string | null

// ❌ may be missing — forces company.domain?.toUpperCase() defensiveness
domain?: string
```

In the page, handle the explicit null without `??`-as-a-shrug:

```tsx
<div>{company.domain === null ? 'No domain' : company.domain}</div>
```

### 3. Counts are numbers, defaulted server-side

A count is a `number`, never `number | null` and never `number | undefined`. The controller uses `withCount(...)` / coalesces to `0` so the wire value is always a real number. The page renders `{c.counts.contacts}` directly.

```ts
counts: { contacts: number; open_leads: number; won_deals: number }  // 0, not null, when empty
```

```tsx
<div>{c.counts.contacts} contacts</div>   {/* no ?., no ?? — it's always a number */}
```

### 4. Discriminated unions for variants

When a field has shape-bearing variants (a "last activity" that is either nothing or an email with a timestamp), model it as a **discriminated union** on a `kind` tag — not a bag of optional fields. The page switches on `kind` and TypeScript narrows the rest.

```ts
last_activity:
  | { kind: 'None' }
  | { kind: 'Email Sent'; at: string; label: string }
```

```tsx
{company.last_activity.kind === 'None'
  ? <span className="text-muted-foreground">No activity</span>
  : <span>{company.last_activity.label}</span>}   {/* `label` only exists on this branch */}
```

This beats `{ at?: string; label?: string }` precisely because the union makes the illegal state (`label` set but `at` missing) unrepresentable, and removes every `?.`.

### 5. ISO 8601 date strings

Dates cross the wire as **ISO 8601 strings**, typed `string` (there is no `Date` over JSON). Format at the edge with `Intl`/`toLocaleString` inside the component; do not type a prop as `Date`.

```ts
created_at: string   // "2026-06-04T14:32:00Z"
last_activity: { kind: 'Email Sent'; at: string; label: string }
```

```tsx
<time dateTime={c.created_at}>{new Date(c.created_at).toLocaleDateString()}</time>
```

### 6. Title-Case enum values render directly — no label maps

Enum unions carry **Title-Case values that are also the display label**. The page renders `{c.industry}` directly; there is no `INDUSTRY_LABELS[c.industry]` map and no `?.` lookup.

```ts
export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'
```

```tsx
<div className="text-muted-foreground">{c.industry}</div>   {/* the value IS the label */}
```

### 7. Pagination is a generic wrapper

Index pages get a `Paginated<T>`. Type it once, reuse everywhere. The page reads `companies.data`, `companies.total`, etc. — all present, all typed.

```ts
export interface Paginated<T> { data: T[]; total: number; page: number; per_page: number }
```

```tsx
export default function CompaniesIndex({ companies }: { companies: Paginated<CompanyView> }) {
  return <div>{companies.data.map((c) => /* ... */)}</div>
}
```

> The example uses a lean `{ data, total, page, per_page }` shape that the controller maps from Laravel's paginator. If you pass the raw `LengthAwarePaginator` JSON instead, type the *actual* keys it serializes (`current_page`, `last_page`, `links`, ...) — the rule is the same: type what the controller really sends, exhaustively, with no `?.`.

## Wiring types to a page

Import the type and annotate the page's props inline. The page is the only consumer; keep the types next to the feature they serve.

```tsx
import type { CompanyView, Paginated } from '@/types/companies'

export default function CompaniesIndex({ companies }: { companies: Paginated<CompanyView> }) {
  // companies.data is CompanyView[] — fully typed, no guards needed
}
```

For shared, app-wide props (the `auth` object shared via `HandleInertiaRequests`), put the type in `resources/js/types/index.ts` so every page can read `usePage().props.auth` typed (see `auth-fortify-permissions.md`).

## The D4 trade-off: keep types in lockstep with the controller

This is the deliberate divergence from the decoupled Next.js path, and you must respect it:

| | Decoupled Next.js path | **This Inertia path (D4)** |
|---|---|---|
| Source of the FE type | **Hand-written** TS in `packages/contracts` (from API Resources) | **Hand-written** in `resources/js/types/` |
| Guarantee | Machine-checked — codegen keeps FE in sync with the DTO | **Discipline** — a human keeps the type in sync with `Inertia::render` |
| Drift risk | Build breaks if the DTO changes | Type silently lies if the controller's shape changes |

Because there is **no codegen** here, the hand-written type and the controller's `Inertia::render` array are two halves of one contract that can drift apart. The mitigations:

- **Write them together.** When a controller method's render shape changes, update the matching `resources/js/types/<feature>.ts` in the same change. The `inertia-module-builder` agent owns both halves of a feature for exactly this reason — types → controller render → page, in lockstep.
- **`npm run build` is the typecheck.** A page that reads a field not on the interface fails the TS build. That catches the page→type direction; it does **not** catch the controller→type direction (the controller is PHP).
- **Review for the PHP↔TS match.** The skill's review pass diffs the `Inertia::render([...])` keys against the interface fields and flags any `?.` / `??` on prop fields as a smell that the type is wrong (it's modeling absence the controller should have eliminated). Note the backend shapes the payload with an **Eloquent API Resource**; the hand-written type is the FE contract here.

## Anti-patterns

- **`?.` / `??` on prop fields in a page.** The tell that the type is loose. Tighten the type (`string | null`, a discriminated union, a defaulted number) and handle the case explicitly instead of optional-chaining past it.
- **`field?: T` optional-by-omission** when you mean `field: T | null`. Optional invites defensive access and breaks the "controller guarantees the shape" contract.
- **`counts?: {...}` or `number | null` for a count.** Counts default to `0` server-side; they are always present numbers.
- **A bag of optional fields instead of a discriminated union** (`{ at?: string; label?: string }`). Use `{ kind: ... }` variants so illegal states are unrepresentable and no `?.` is needed.
- **Typing a date as `Date`.** JSON has no `Date`; props are ISO `string`. Parse/format at the component edge.
- **Label maps for enums** (`INDUSTRY_LABELS[c.industry]`). Title-Case enum values are their own labels — render directly.
- **`any` / untyped props** (`function Page({ companies }: { companies: any })`). Defeats the whole contract; the build can no longer protect you.
- **Editing the type without editing the controller (or vice-versa).** They are one contract — change both in the same pass or the type starts lying.
