# API Resources + hand-written contract (presenter + TS shape)

This is the **most important** reference in the skill. It is the Laravel analogue of the Nest.js `view-presenter.md` + the contracts section of `monorepo-setup.md`. Read it in Phase 5 — every module produces at least one **Eloquent API Resource** (`Illuminate\Http\Resources\Json\JsonResource`), and that Resource is the response presenter. Its wire shape is mirrored by a **hand-written** TypeScript type that the frontend imports, and a Pest **contract test** keeps the two in lockstep.

> (Was `spatie/laravel-data` + `typescript:transform` in ≤v1.5.) The presenter is now a plain API Resource and the TS contract is authored by hand — no codegen, no extra packages.

## The contract

In the Nest.js stack, `packages/contracts` holds **hand-written Zod** and both apps import it. The Laravel stack uses the same direction — **hand-written TypeScript is the published contract** — but PHP owns the *runtime* shape:

1. An Eloquent **API Resource** (`CompanyResource`) describes the exact, view-ready response shape. This is the presenter — it replaces the Nest `toView()` method.
2. A **hand-written** TS type (`CompanyView` in `packages/contracts/src/companies.ts` for decoupled Next.js, or `resources/js/types/companies.ts` for Inertia) describes the same shape for the frontend.
3. A **Pest contract test** asserts `CompanyResource::toArray()` matches the documented keys/types, so the Resource can never silently drift from the TS.

The frontend renders `company.last_activity.label` directly. No `?.`. No `??`. The Resource has already built every label, every count, every discriminated-union variant, and converted every date to an ISO string before the response leaves PHP.

There is no transform step and no `generated.ts`. The two artifacts (Resource + TS) are kept honest by the contract test, not by a generator.

## No install

API Resources ship with the framework — there is nothing to `composer require`. Generate one with:

```bash
php artisan make:resource Companies/CompanyResource
```

(Place it under the feature's `Http/Resources/` directory — see `module-structure.md`.)

## The API Resource (the presenter)

The Resource's `toArray()` is fully explicit — every field is built by hand. Counts default to `0` server-side, dates are ISO 8601 strings, enums are Title-Case PHP enums (value = label), and the "last activity" payload is a discriminated union whose `kind` is on the wire.

```php
// app/Domains/Companies/Http/Resources/CompanyResource.php
namespace App\Domains\Companies\Http\Resources;

use Illuminate\Http\Resources\Json\JsonResource;

class CompanyResource extends JsonResource
{
    public function toArray($request): array
    {
        return [
            'id' => $this->id,
            'name' => $this->name,
            'domain' => $this->domain,                 // nullable EXPLICIT — never omitted
            'industry' => $this->industry,             // Title-Case enum; value = UI label
            'counts' => [
                'contacts'   => (int) ($this->contacts_count ?? 0),   // withCount(); default 0
                'open_leads' => (int) ($this->open_leads_count ?? 0),
                'won_deals'  => (int) ($this->won_deals_count ?? 0),
            ],
            'last_activity' => $this->lastActivityPayload(), // discriminated union { kind, ... }
            'created_at' => $this->created_at->toIso8601String(),
            'updated_at' => $this->updated_at->toIso8601String(),
        ];
    }
}
```

A few things to notice (the same discipline as the Nest presenter):

- Every field is listed by hand — there is **no** `parent::toArray()`, no spread of the raw model, no whitelisting of columns. Field-by-field surfaces missed transformations.
- Counts are cast to `int` and default to `0`, never `null`/undefined.
- `$this->industry` is a Title-Case PHP enum whose value equals the UI label (`enums-title-case.md`). Laravel serialises a backed enum to its scalar value, so the wire string is the label — no `INDUSTRY_LABELS` map anywhere.
- Carbon dates are converted to ISO 8601 strings at the boundary.

### Discriminated union (the `last_activity` shape)

Model variants as a discriminated union: a `kind` (Title-Case string) plus branch-specific fields. `kind` is **always** present — the empty case is `'None'` — so the frontend can `switch (company.last_activity.kind)` with no null check. Labels are computed server-side.

```php
// app/Domains/Companies/Http/Resources/CompanyResource.php (continued)
private function lastActivityPayload(): array
{
    $row = $this->last_activity;          // eager-loaded by the query (see below)
    if (! $row) {
        return ['kind' => 'None'];
    }

    $at = $row->occurred_at->toIso8601String();
    $relative = $row->occurred_at->diffForHumans();

    return match ($row->kind->value) {
        'Email Sent' => [
            'kind' => 'Email Sent',
            'at' => $at,
            'subject' => $row->subject,
            'label' => "Sent “{$row->subject}” {$relative}",
        ],
        'Email Received' => [
            'kind' => 'Email Received',
            'at' => $at,
            'preview' => $row->preview,
            'label' => "Replied {$relative}",
        ],
        'Deal Won' => [
            'kind' => 'Deal Won',
            'at' => $at,
            'amount_label' => $row->amount_label,
            'label' => "Won deal — {$row->amount_label} {$relative}",
        ],
    };
}
```

What to notice:

- The union has a branch for **every** variation, including `None`.
- Labels are constructed server-side. The frontend renders `last_activity.label` and is done.
- Each branch carries only the fields that branch needs — the TS union (below) mirrors this exactly.

For the deeper "why fully-populated" rules and the mandatory no-null Pest test, see `view-data-pattern.md`.

## Controller returns the Resource (never the model)

A controller method returns a `Resource` or `Resource::collection(...)` — **never** an Eloquent model and **never** a raw array. Eager-load relations and call `withCount()` **before** wrapping, so the Resource receives concrete integers and pre-loaded relations.

```php
// app/Domains/Companies/Http/CompanyController.php
public function index()
{
    return CompanyResource::collection(
        Company::query()
            ->withCount(['contacts', 'leads as open_leads_count', 'deals as won_deals_count'])
            ->with(['lastActivityLog'])
            ->paginate()
    );
}

public function show(string $id)
{
    return new CompanyResource(
        Company::query()
            ->withCount(['contacts', 'leads as open_leads_count', 'deals as won_deals_count'])
            ->with(['lastActivityLog'])
            ->findOrFail($id)               // workspace global scope → cross-workspace 404
    );
}
```

`CompanyResource::collection(...->paginate())` produces the paginated wire shape (`data` / `meta` / `links`) automatically. `findOrFail()`, combined with the `BelongsToWorkspace` global scope, yields a 404 for cross-workspace reads — see `multitenancy-global-scope.md`.

> **Reference-field model:** the `with`/`withCount` relations above are declared on the model for read enrichment only. The underlying columns (`workspace_id`, `company_id`) are plain reference columns with **no** DB-level FK constraint — joins and eager-loading still work on real Postgres. See `postgres-timescale-eloquent.md`.

## The hand-written TS contract

The frontend imports a hand-written type that mirrors `toArray()` field-for-field. Same file for both stacks, different location:

- **Decoupled Next.js:** `packages/contracts/src/companies.ts` (consumed via `@<scope>/contracts/companies`).
- **Inertia:** `resources/js/types/companies.ts`.

```ts
// packages/contracts/src/companies.ts  (decoupled Next.js)
// resources/js/types/companies.ts       (Inertia) — identical body
export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'

export type LastActivity =
  | { kind: 'None' }
  | { kind: 'Email Sent'; at: string; subject: string; label: string }
  | { kind: 'Email Received'; at: string; preview: string; label: string }
  | { kind: 'Deal Won'; at: string; amount_label: string; label: string }

export interface CompanyView {
  id: string
  name: string
  domain: string | null
  industry: Industry
  counts: { contacts: number; open_leads: number; won_deals: number }
  last_activity: LastActivity
  created_at: string
  updated_at: string
}
```

This TS is the **published contract**. The frontend uses these types only — no runtime validation, no re-derivation of labels. `domain` is `string | null` (explicit), `counts` are always present numbers, and `last_activity` is a discriminated union the frontend narrows by `kind`.

The Title-Case PHP enum and the TS string-literal union must stay identical (DB value = wire value = UI label). The enum rules and anti-patterns live in `enums-title-case.md`; the contract-relevant part is just that the value IS the label, so the union members read like UI text.

## The contract test (the guard)

A Pest test pins `CompanyResource::toArray()` to the documented shape. This is what replaces a codegen pipeline: when someone adds, renames, or drops a field in the Resource without updating the TS (or vice versa), this test fails and forces the two back into sync.

```php
// tests/Feature/CompanyContractTest.php (Pest) — locks the Resource to the published contract
it('CompanyResource matches the published contract shape', function () {
    $company = Company::factory()->create();

    $array = (new CompanyResource(
        $company->loadCount(['contacts', 'leads as open_leads_count', 'deals as won_deals_count'])
    ))->toArray(request());

    expect($array)
        ->toHaveKeys(['id', 'name', 'domain', 'industry', 'counts', 'last_activity', 'created_at', 'updated_at'])
        ->and($array['counts'])->toHaveKeys(['contacts', 'open_leads', 'won_deals'])
        ->and($array['counts']['contacts'])->toBeInt()
        ->and($array['counts']['open_leads'])->toBeInt()
        ->and($array['last_activity']['kind'])->toBeString()
        ->and($array['created_at'])->toBeString();

    // Spot-check: required (non-nullable) fields are never serialised as null.
    expect(json_encode($array))->not->toContain('null,');
});
```

The same test doubles as the no-null check from `view-data-pattern.md`: counts come back as integers (defaulted to `0`), `last_activity.kind` is always a string, and required fields never serialise as `null`. Keep the `toHaveKeys` list and the TS interface fields identical — that pairing is the contract.

## Anti-patterns

- ❌ **Returning an Eloquent model or a raw array** from a controller/action. The whole skill is about not doing this. Models leak DB column names, lazy-load relations, serialise Carbon inconsistently, and bypass the contract entirely. Always return a `Resource` or `Resource::collection(...)`.
- ❌ **Optional-by-omission fields** — a key that is sometimes present, sometimes absent (e.g. conditional `when()` on a field the contract marks required). That forces `?.`/`??` on the frontend. Make the field explicitly nullable (`'domain' => $this->domain`), default it server-side (counts → `0`), or model it as a discriminated-union branch. The frontend must never need `?.`.
- ❌ **Computing labels / formatting on the frontend.** If both sides need "growing vs declining" or a money string, the backend builds it once in `toArray()`/`lastActivityPayload()` and ships the finished `label`. The frontend renders it. (Same rule as the Nest presenter.)
- ❌ **The Resource drifting from the hand-written TS without a contract test.** The TS is hand-authored, so nothing regenerates it — the Pest contract test is the *only* thing keeping `toArray()` and `CompanyView` aligned. Every Resource that backs a published shape needs one; never add/rename a field on one side without the other and a green test.
- ❌ **`parent::toArray()` or spreading the model** (`return [...$this->resource->toArray()]`). Field-by-field is intentional — it surfaces missed transformations and stops new DB columns leaking onto the wire.
- ❌ **Resolving counts inside `toArray()`** (`$this->contacts()->count()`). That is an N+1 per row. Call `withCount()` on the query in the controller; `toArray()` only reads the `*_count` attribute and defaults it to `0`.
