# Extraction Patterns (Phase 2)

How `schema-reverse-engineer` converts implicit shapes (JSON + TS interfaces + component usage) into explicit Zod contracts.

## The translation table

For each field observed in fixtures, decide its Zod shape using this hierarchy:

### 1. Required vs nullable vs default

| Observed in fixtures | Used in components | Contract shape |
|---|---|---|
| Present in 100% of records | Rendered directly (no `?.`) | Required: `z.string()` / `z.number()` |
| Present in >90% but not 100% | Rendered with `?? '—'` | `z.string().nullable()` if "no value" is a real state, otherwise `z.string().default('')` |
| Present in <50% | Often `?.` | Probably a discriminated union; see below |
| Numeric, sometimes 0, sometimes absent | Rendered as count | `z.number().default(0)` — NEVER `.optional()` per view-shape contract |
| String, varies between formats | Different rendering per case | Discriminated union |

### 2. Strings → enums

If a string field has a small set of distinct values across all records:

```ts
// JSON:
[
  { industry: 'tech' },
  { industry: 'healthcare' },
  { industry: 'finance' },
  { industry: 'tech' },
  // ... 47 records total, 5 distinct values
]

// Contract (Title Case re-cased):
export const industrySchema = z.enum(['Technology', 'Healthcare', 'Finance', 'Logistics', 'Other']);

// EXTRACTED_CONTRACTS.md note:
// "Industry: source JSON uses lowercase (tech, healthcare, ...). Seed script maps to Title Case."
```

The seed script handles the re-casing one time; new data from the API is always Title Case.

### 3. Variations → discriminated unions

A field that renders differently based on shape signals a discriminated union, not an optional:

```ts
// JSON (prototype):
[
  { last_activity: null },                                        // some records
  { last_activity: { type: 'email_sent', at: '2024-...', subject: '...' } },
  { last_activity: { type: 'email_received', at: '...', preview: '...' } },
  { last_activity: { type: 'deal_won', at: '...', amount: 50000 } },
]

// Contract (Title Case kinds):
export const lastActivitySchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('None') }),
  z.object({
    kind: z.literal('Email Sent'),
    at: z.string().datetime(),
    subject: z.string(),
    label: z.string(),
  }),
  z.object({
    kind: z.literal('Email Received'),
    at: z.string().datetime(),
    preview: z.string(),
    label: z.string(),
  }),
  z.object({
    kind: z.literal('Deal Won'),
    at: z.string().datetime(),
    amount_label: z.string(),
    label: z.string(),
  }),
]);

// Note in EXTRACTED_CONTRACTS.md:
// - JSON null → kind: 'None'
// - JSON type field 'email_sent' → kind: 'Email Sent'
// - amount: 50000 → amount_label: '$50,000.00' (formatted server-side, view-shape contract)
// - new label field per branch: backend formats human-readable summary
```

### 4. Computed-on-client → moved to view shape

If a component computes a derived value from raw fields, the future contract includes both:

```tsx
// Component (current):
const growthPct = ((company.headcount - company.headcount_12mo_ago) / company.headcount_12mo_ago) * 100;
const growthLabel = `${growthPct > 0 ? '+' : ''}${growthPct.toFixed(1)}% YoY`;

// Future contract:
headcount: z.object({
  current: z.number().int().nonnegative(),
  twelve_months_ago: z.number().int().nonnegative(),
  delta_pct: z.number(),                              // computed server-side
  growth_signal: z.object({
    kind: z.enum(['Growing', 'Stable', 'Declining']), // computed server-side
    label: z.string(),                                // formatted server-side
  }),
}),

// Component (after rewiring):
<span>{company.headcount.growth_signal.label}</span>
```

The backend presenter computes everything; the component renders the prepared values. No `?.`, no `??`, no math in JSX.

### 5. Dates

| Source | Contract |
|---|---|
| `"2024-03-15T14:30:00Z"` (ISO string) | `z.string().datetime()` |
| `"2024-03-15"` (date only) | `z.string().date()` (Zod v3.23+) or `z.string().regex(/^\d{4}-\d{2}-\d{2}$/)` |
| `1710512400000` (epoch ms) | Flag for migration; new contract is ISO. Seed converts. |
| `Date` object in TS interface | `z.string().datetime()` — wire format is string |

### 6. Nested objects

```ts
// JSON:
{
  address: {
    street: '123 Main St',
    city: 'Gurugram',
    country: 'IN',
  }
}

// Contract: literal nested object, no special handling
export const addressSchema = z.object({
  street: z.string(),
  city: z.string(),
  country: z.string().length(2), // ISO country code if it's always 2 chars
});

export const personSchema = z.object({
  // ...
  address: addressSchema.nullable(), // if not every record has address
});
```

### 7. Arrays

```ts
// JSON:
{ tags: ['vip', 'enterprise', 'q4-target'] }

// Contract:
tags: z.array(z.string()), // default empty array on the wire
// or with known tag set:
tagSchema: z.enum(['Vip', 'Enterprise', 'Q4-Target', ...]),  // Title Case
tags: z.array(tagSchema),
```

Empty array (`[]`) is the default for "no tags" — never `.optional()`.

## The input vs view distinction

For every entity, derive TWO schemas:

```ts
// VIEW shape — what GET /companies/:id returns and the FE renders
export const companyViewSchema = z.object({
  id: z.string(),
  name: z.string(),
  domain: z.string().nullable(),
  industry: industrySchema,                    // Title Case
  size_bucket: sizeBucketSchema,
  headcount: z.object({
    current: z.number(),
    twelve_months_ago: z.number(),
    delta_pct: z.number(),
    growth_signal: z.object({ kind: growthSignalKindSchema, label: z.string() }),
  }),
  counts: z.object({
    contacts: z.number().int().nonnegative(),
    open_leads: z.number().int().nonnegative(),
    won_deals: z.number().int().nonnegative(),
  }),
  last_activity: lastActivitySchema,
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

// INPUT shape — what POST /companies accepts
export const createCompanySchema = z.object({
  name: z.string().min(1).max(120),
  domain: z.string().regex(/^[a-z0-9.-]+\.[a-z]{2,}$/i).nullable(),
  industry: industrySchema,
});

// UPDATE shape — partial of input
export const updateCompanySchema = createCompanySchema.partial();
```

The view shape is what the FE currently builds from raw fixtures (after the rewirer's transformations). The input shape is what forms already send (or will send post-rewire). Don't conflate them.

## Drift recording in EXTRACTED_CONTRACTS.md

For each entity, after declaring the schema, record evidence:

```markdown
### Company

**Sources:**
- `src/data/companies.json` (47 records) — primary
- `src/data/companies-sample.json` (5 records) — possibly stale; 2 fields differ
- `src/types/company.ts` — TS interface; missing fields `headcount_12mo_ago` and `last_activity`

**Schema:** (paste contract here)

**Drift findings:**

- **D-1 [Medium] — TS interface incomplete.** `src/types/company.ts` doesn't declare `headcount_12mo_ago` or `last_activity`, but both appear in JSON and are rendered in `list.tsx`. Component uses `as any` casts. Recommendation: replace interface with `z.infer<typeof companyViewSchema>` from `@<scope>/contracts/companies`.

- **D-2 [Low] — Sample fixture stale.** `companies-sample.json` has `industry: 'tech'` (lowercase) but `companies.json` has uppercase too. Recommendation: use `companies.json` as seed source; delete sample.

- **D-3 [Medium] — `last_active` vs `last_activity`.** `companies.json` has `last_active: "2024-03-15T..."` (just a timestamp). `list.tsx` renders `company.last_activity.label` (a rich object). The component depends on a richer shape than the data provides. Recommendation: contract declares the rich `last_activity` discriminated union; seed populates from `last_active` for backward compat (only `None` and `Email Sent` kinds — backend continues enriching from event tables).

**Compute candidates (move to backend):**
- `headcount.delta_pct` — currently computed in `list.tsx:42`
- `headcount.growth_signal` — currently computed in `list.tsx:48`
- `counts.contacts` — currently computed via `contacts.filter(c => c.company_id === id).length` across all contacts
- `counts.open_leads` — currently computed via `leads.filter(...).length`
- `counts.won_deals` — same

**Title Case re-castings needed (seed script):**
- `industry`: `tech` → `Technology`, `healthcare` → `Healthcare`, `finance` → `Finance`, `logistics` → `Logistics`, `other` → `Other`
```

The downstream agents (especially `backend-extractor` for the seed script) read these notes.

## When NOT to apply view-shape contract

If a field is genuinely optional in the data model (e.g., a `notes` field where empty means "the user hasn't written notes"), `.nullable()` with `null` as the explicit value is correct. The rule against `.optional()` is to prevent JSON's "field absent vs field present-with-null" ambiguity from leaking to the FE — both end up as `null` in the contract, and the component renders `{notes ?? ''}` or shows an empty `<textarea>` when null.

The cases where `.nullable()` is right:
- `domain` for a company that legitimately has none
- `phone` for a contact that legitimately has none
- `assigned_to_user_id` for a lead with no owner
- `last_email_received_at` until they actually receive one

The cases where it's wrong (use default/discriminated union instead):
- `counts.contacts` — always a number, default 0
- `last_activity` — always a kind, default `{ kind: 'None' }`
- `tags` — always an array, default `[]`

## Anti-patterns

- **Treating TS interfaces as authoritative.** They often lie.
- **Faithfully translating JSON optionality to `.optional()`.** Apply the view-shape contract; nullable or default or discriminated union.
- **Lowercase enum values.** Always re-case to Title Case in the contract. Seed script handles the historical mapping.
- **Defining "input" schema from view schema via `.partial()`** without checking what forms actually send. The form might validate richer rules (min length, regex); derive from the form, not the view.
- **Inventing fields.** If the FE doesn't render it and the JSON doesn't have it, don't add it speculatively.
