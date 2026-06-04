# Forms with Inertia `useForm`

How to handle form submission, validation errors, and loading state in the Laravel + Inertia React monolith. Inertia's `useForm` is the single answer for every create/edit form — no third-party form library, no manual `fetch`.

---

## The core pattern

`useForm` from `@inertiajs/react` initialises form data, submits to a Laravel route, and surfaces server-validation errors automatically in `form.errors`. The controller validates via a `FormRequest` (or `laravel-data`'s validation pipeline); any failed validation returns the standard Inertia error bag, which lands in `form.errors` keyed by field name.

```tsx
import { useForm } from '@inertiajs/react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export default function CompanyCreate() {
  const form = useForm({ name: '', industry: 'Technology' })

  return (
    <form onSubmit={(e) => { e.preventDefault(); form.post('/companies') }}>
      <Input
        value={form.data.name}
        onChange={(e) => form.setData('name', e.target.value)}
      />
      {form.errors.name && <p className="text-destructive text-sm">{form.errors.name}</p>}
      <Button disabled={form.processing}>Create</Button>
    </form>
  )
}
```

Key facts:

- `form.data` — the current field values (typed from the initial object you pass `useForm`).
- `form.setData(field, value)` — updates one field; pass the field name as a string literal.
- `form.post(url)` / `form.put(url)` / `form.delete(url)` — submits via Inertia; CSRF is handled automatically.
- `form.errors` — an object keyed by field name, populated from Laravel's `$errors` bag after a failed `FormRequest` validation. No extra wiring needed.
- `form.processing` — `true` while the request is in flight; use it to disable the submit button.

---

## Full create-form example with shadcn primitives

Use shadcn `Input`, `Label`, `Select`, and `Button` throughout. Never reach for a raw `<input>` or `<select>`.

```tsx
// resources/js/pages/companies/create.tsx
import { useForm } from '@inertiajs/react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import AppLayout from '@/layouts/app-layout'
import type { Industry } from '@/types/companies'

const INDUSTRIES: Industry[] = [
  'Technology',
  'Healthcare',
  'Finance',
  'Logistics',
  'Other',
]

export default function CompanyCreate() {
  const form = useForm<{ name: string; industry: Industry }>({
    name: '',
    industry: 'Technology',
  })

  function submit(e: React.FormEvent) {
    e.preventDefault()
    form.post('/companies')
  }

  return (
    <AppLayout>
      <h1 className="text-2xl font-semibold mb-6">New company</h1>

      <form onSubmit={submit} className="space-y-4 max-w-md">
        <div className="space-y-1.5">
          <Label htmlFor="name">Company name</Label>
          <Input
            id="name"
            value={form.data.name}
            onChange={(e) => form.setData('name', e.target.value)}
            placeholder="Acme Corp"
          />
          {form.errors.name && (
            <p className="text-destructive text-sm">{form.errors.name}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="industry">Industry</Label>
          <Select
            value={form.data.industry}
            onValueChange={(v) => form.setData('industry', v as Industry)}
          >
            <SelectTrigger id="industry">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {INDUSTRIES.map((ind) => (
                <SelectItem key={ind} value={ind}>
                  {ind}{/* Title-Case enum value IS the label — no map needed */}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {form.errors.industry && (
            <p className="text-destructive text-sm">{form.errors.industry}</p>
          )}
        </div>

        <Button type="submit" disabled={form.processing}>
          {form.processing ? 'Creating…' : 'Create company'}
        </Button>
      </form>
    </AppLayout>
  )
}
```

The enum values render directly as labels. `Industry` is declared in `resources/js/types/companies.ts` as a string union of Title-Case values (see `typed-props.md`).

---

## Edit-form pattern

For edit pages, seed `useForm` with the existing record's values from Inertia props. Use `form.put` or `form.patch`.

```tsx
// resources/js/pages/companies/edit.tsx
import { useForm } from '@inertiajs/react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import AppLayout from '@/layouts/app-layout'
import type { CompanyView } from '@/types/companies'

export default function CompanyEdit({ company }: { company: CompanyView }) {
  const form = useForm({
    name: company.name,
    industry: company.industry,
  })

  return (
    <AppLayout>
      <form
        onSubmit={(e) => { e.preventDefault(); form.put(`/companies/${company.id}`) }}
        className="space-y-4 max-w-md"
      >
        <Input
          value={form.data.name}
          onChange={(e) => form.setData('name', e.target.value)}
        />
        {form.errors.name && (
          <p className="text-destructive text-sm">{form.errors.name}</p>
        )}

        <Button type="submit" disabled={form.processing}>Save changes</Button>
      </form>
    </AppLayout>
  )
}
```

`company` arrives as a typed Inertia prop — no `?.` on any field (the controller guarantees the shape).

---

## Server validation errors: how they surface

Laravel's `FormRequest` (or `laravel-data` validation) returns a `422` with the validation error bag when validation fails. Inertia intercepts that response and populates `form.errors` automatically — the page does **not** hard-reload. The React component re-renders with the error messages in place.

Backend side, a typical `FormRequest`:

```php
// app/Http/Requests/StoreCompanyRequest.php
class StoreCompanyRequest extends FormRequest
{
    public function rules(): array
    {
        return [
            'name'     => ['required', 'string', 'max:120'],
            'industry' => ['required', Rule::in(['Technology','Healthcare','Finance','Logistics','Other'])],
        ];
    }
}
```

And the controller stores via that request:

```php
// app/Domains/Company/Http/CompanyController.php
#[Authorize('create', Company::class)]
public function store(StoreCompanyRequest $request): RedirectResponse
{
    $company = Company::create($request->validated());

    return to_route('companies.show', $company)
        ->with('flash.success', 'Company created.');
}
```

If validation fails, Laravel redirects back automatically. Inertia catches the redirect, re-renders the create page, and `form.errors` is populated. No manual error-handling code is needed on the frontend.

---

## Fortify auth pages: reuse as-is

The Laravel React starter kit ships Fortify-scaffolded auth pages in `resources/js/pages/auth/`:

```
resources/js/pages/auth/
├── login.tsx
├── register.tsx
├── forgot-password.tsx
├── reset-password.tsx
├── verify-email.tsx
└── confirm-password.tsx
```

These pages are already wired with `useForm` against the Fortify routes. **Do not re-translate them from the Claude Design output** unless the design explicitly specifies custom auth screens (e.g. a branded, non-standard login page that meaningfully diverges from the starter-kit default).

When the design does require custom auth screens:

1. Keep the same `useForm` calls and route targets (`/login`, `/register`, etc.) — only change the visual layout.
2. Reuse the starter-kit's auth layout variants (simple / card / split) from `resources/js/layouts/auth/` rather than building a new layout from scratch.
3. Apply token-based Tailwind classes and shadcn primitives, same as any other page.

---

## Partial reload after a successful mutation

After `form.post` / `form.put` succeeds, the controller typically redirects to a `GET` route (Post/Redirect/Get pattern). Inertia follows the redirect and renders the target page with fresh props. No manual cache invalidation is needed — the redirect does it.

If you need to refresh a subset of props on the *current* page without a full navigation (e.g. updating a count badge after an inline action), use `router.reload`:

```tsx
import { router } from '@inertiajs/react'

// refresh only 'companies' and 'stats' props, leave others stale
router.reload({ only: ['companies', 'stats'] })
```

---

## Anti-patterns

### Using React Hook Form + fetch

```tsx
// WRONG — do not do this in the Inertia monolith
import { useForm } from 'react-hook-form'

const { register, handleSubmit } = useForm()
const onSubmit = handleSubmit(async (data) => {
  await fetch('/api/companies', { method: 'POST', body: JSON.stringify(data) })
})
```

This bypasses Inertia entirely: CSRF is not handled, server validation errors do not surface in `form.errors`, and you end up building a duplicate API layer that does not exist in the Inertia monolith. Use `useForm` from `@inertiajs/react`.

### Manual fetch posting

```tsx
// WRONG — do not do this
async function handleSubmit(e) {
  e.preventDefault()
  const res = await fetch('/companies', { method: 'POST', body: new FormData(e.target) })
  const json = await res.json()
}
```

Same problems: Inertia's error-surfacing, CSRF, and redirect-following are all bypassed.

### Reaching for TanStack Query for mutations

TanStack Query (`useMutation`) is not installed in the Inertia starter kit and is not the Inertia pattern. `useForm` + `form.post/put/delete` covers every mutation.

### Optional-chaining prop fields

```tsx
// WRONG — do not use ?. on Inertia prop fields
{company?.name}
{form.data?.industry}
```

Inertia prop fields are always present when the page renders (the controller guarantees the shape). The `?.` operator signals that a field might be absent — that is a discipline violation on typed props. Declare prop types exhaustively in `resources/js/types/` instead (see `typed-props.md`).

---

## Quick-reference checklist

- [ ] `useForm` imported from `@inertiajs/react`, not `react-hook-form`
- [ ] `form.post` / `form.put` / `form.delete` used for submission — no `fetch`
- [ ] Every field error rendered from `form.errors.<field>` with `text-destructive`
- [ ] Submit button disabled on `form.processing`
- [ ] shadcn `Input`, `Label`, `Select`, `Button` — no raw HTML form elements
- [ ] Title-Case enum values rendered directly, no label lookup maps
- [ ] No `?.` on `form.data.<field>` or Inertia prop fields
- [ ] Auth pages (`resources/js/pages/auth/`) left as-is unless design specifies custom screens
