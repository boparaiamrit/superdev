# laravel-data Contracts (Data-as-presenter + TS emit)

This is the **most important** reference in the skill. It is the Laravel analogue of the Nest.js `view-presenter.md` + the contracts section of `monorepo-setup.md`. Read it in Phase 5 — every module produces at least one `Data` class, and that class is simultaneously the response presenter AND the upstream contract that generates the frontend's TypeScript types.

## The contract

In the Nest.js stack, `packages/contracts` holds **hand-written Zod** and both apps import it. In the Laravel stack the direction is **reversed**: PHP is the upstream source of truth, and the backend cannot import TypeScript.

1. A `spatie/laravel-data` `Data` class describes the exact, view-ready response shape (this is the presenter — it replaces the Nest `toView()` method).
2. `php artisan typescript:transform` reads every `#[TypeScript]`-marked `Data` class and emits a `.ts` file into `packages/contracts/src`.
3. The Next.js app (built by `design-to-nextjs`) imports the **generated types only** — no runtime Zod, no re-validation.

The frontend renders `company.last_activity.label` directly. No `?.`. No `??`. The `Data` class has already built every label, every count, every discriminated-union variant, and converted every date to an ISO string. **One class is both the presenter and the contract** — there is no second artifact to keep in sync.

> Laravel equivalent of the Nest.js stack: the `CompaniesPresenter` class + the hand-written `companies.ts` Zod schema in `packages/contracts` collapse into a **single** `CompanyData` class. The transform regenerates the TS; you never hand-write it.

## Install + config

```bash
composer require spatie/laravel-data spatie/laravel-typescript-transformer
php artisan vendor:publish --provider="Spatie\LaravelData\LaravelDataServiceProvider"
php artisan vendor:publish --tag=typescript-transformer-config
```

```php
// config/typescript-transformer.php — key settings
'auto_discover_types' => [ app_path() ],

'collectors' => [
    Spatie\LaravelData\Support\TypeScriptTransformer\DataTypeScriptCollector::class,
],

'transformers' => [
    Spatie\LaravelData\Support\TypeScriptTransformer\DataTypeScriptTransformer::class,
],

// Emit into the monorepo shared contracts package consumed by apps/web.
// apps/api lives at <workspace>/apps/api, so '../../packages/contracts' from base_path():
'output_file' => base_path('../../packages/contracts/src/generated.ts'),
```

Run the emit:

```bash
php artisan typescript:transform
```

This writes a single `packages/contracts/src/generated.ts` containing one TS type per `#[TypeScript]` `Data` class and one TS union per backed enum it references. `apps/web` imports from that file (or a re-export barrel) exactly as it imported the old Zod types.

## A view Data class (the presenter)

The `Data` class is fully populated — every field is built explicitly in `fromModel()`. Counts default to `0` server-side, dates are ISO 8601 strings, enums are Title-Case PHP enums, and the "last activity" payload is a discriminated union whose `kind` is on the wire.

```php
// app/Domains/Companies/Data/CompanyData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\TypeScriptTransformer\Attributes\TypeScript;
use App\Domains\Companies\Enums\Industry;

#[TypeScript]
class CompanyData extends Data
{
    public function __construct(
        public string $id,
        public string $name,
        public ?string $domain,            // nullable is EXPLICIT; never "optional/missing"
        public Industry $industry,         // Title Case PHP enum -> TS union, value = label
        public CompanyCountsData $counts,  // always present, defaulted to 0 server-side
        public LastActivityData $last_activity, // discriminated union, kind is Title Case
        public string $created_at,         // ISO 8601 string, not a Carbon instance
        public string $updated_at,
    ) {}

    public static function fromModel(\App\Domains\Companies\Models\Company $c): self
    {
        return new self(
            id: $c->id,
            name: $c->name,
            domain: $c->domain,
            industry: $c->industry,
            counts: new CompanyCountsData(
                contacts: (int) ($c->contacts_count ?? 0),
                open_leads: (int) ($c->open_leads_count ?? 0),
                won_deals: (int) ($c->won_deals_count ?? 0),
            ),
            last_activity: LastActivityData::fromModel($c),
            created_at: $c->created_at->toIso8601String(),
            updated_at: $c->updated_at->toIso8601String(),
        );
    }
}
```

The nested counts object is its own `#[TypeScript]` `Data` class so it emits a named TS type:

```php
// app/Domains/Companies/Data/CompanyCountsData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\TypeScriptTransformer\Attributes\TypeScript;

#[TypeScript]
class CompanyCountsData extends Data
{
    public function __construct(
        public int $contacts,
        public int $open_leads,
        public int $won_deals,
    ) {}
}
```

### Discriminated union (the `last_activity` shape)

A discriminated union is modelled as a `Data` class whose `kind` is a Title-Case string and whose other fields vary by branch. `kind` is always present (the empty case is `'None'`), so the frontend can `switch (company.last_activity.kind)` with no null check. The branch labels are computed server-side.

```php
// app/Domains/Companies/Data/LastActivityData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\TypeScriptTransformer\Attributes\TypeScript;

#[TypeScript]
class LastActivityData extends Data
{
    public function __construct(
        public string $kind,            // 'None' | 'Email Sent' | 'Email Received' | 'Deal Won'
        public ?string $at = null,      // ISO 8601 string when present
        public ?string $label = null,   // computed server-side: "Sent “Quick question” 2h ago"
        public ?string $subject = null,
        public ?string $preview = null,
        public ?string $amount_label = null,
    ) {}

    public static function fromModel(\App\Domains\Companies\Models\Company $c): self
    {
        $row = $c->last_activity;       // already eager-loaded by the repository/query
        if (! $row) {
            return new self(kind: 'None');
        }

        $at = $row->occurred_at->toIso8601String();
        $relative = $row->occurred_at->diffForHumans();

        return match ($row->kind->value) {
            'Email Sent' => new self(
                kind: 'Email Sent', at: $at, subject: $row->subject,
                label: "Sent “{$row->subject}” {$relative}",
            ),
            'Email Received' => new self(
                kind: 'Email Received', at: $at, preview: $row->preview,
                label: "Replied {$relative}",
            ),
            'Deal Won' => new self(
                kind: 'Deal Won', at: $at,
                amount_label: $row->amount_label,
                label: "Won deal — {$row->amount_label} {$relative}",
            ),
        };
    }
}
```

What to notice (same discipline as the Nest presenter):

- Every field of `CompanyData` is built explicitly — no spread of the raw model.
- Counts are cast to `int` and default to `0`, never `null`/undefined.
- The discriminated union has a branch for every variation, including `None`.
- Labels are constructed server-side. The frontend renders `last_activity.label` and is done.
- Carbon dates are converted to ISO 8601 strings at the boundary.

For the deeper "why fully-populated" rules and the mandatory no-null Pest test, see `view-data-pattern.md`.

## Controller returns the Data class (never the model)

A controller method returns a `Data` object or a typed collection of them — **never** an Eloquent model and **never** a raw array. `Data::collect(...)` with `PaginatedDataCollection` produces the paginated wire shape (`data` / `meta` / `links`) and keeps the response type discoverable by the transformer.

```php
// app/Domains/Companies/Http/CompanyController.php
return CompanyData::collect(
    Company::query()
        ->withCount(['contacts', 'openLeads as open_leads_count', 'wonDeals as won_deals_count'])
        ->paginate(),
    \Spatie\LaravelData\PaginatedDataCollection::class,
);
```

For a single resource the controller returns `CompanyData::fromModel($company)` directly. `findOrFail()` (combined with the workspace global scope) yields a 404 for cross-workspace reads — see `multitenancy-global-scope.md`.

## Turbo wiring (transform runs before the web build)

The frontend build must not start until `generated.ts` is fresh. A Turbo `contracts` task shells out to `php artisan typescript:transform`, and `apps/web`'s build `dependsOn` it. The full wiring (root `package.json` script, `turbo.json` task, whether to commit `generated.ts`) lives in **`monorepo-setup.md`** — read it for the exact config. The short version:

```json
// turbo.json (excerpt) — full version in monorepo-setup.md
"tasks": {
  "contracts": { "cache": false },
  "build": { "dependsOn": ["^build", "contracts"] }
}
```

## Title-Case enum → TS union

A PHP 8.1 string-backed enum whose **value equals the UI label** emits a TS string-literal union identical to the old Zod `z.enum([...])` output — DB value = wire value = UI label, with zero conversion code. The full enum rules and anti-patterns live in **`enums-title-case.md`**; the contract-relevant part is just that the value is the label:

```php
// app/Domains/Companies/Enums/Industry.php  (full treatment in enums-title-case.md)
enum Industry: string {
    case Technology = 'Technology';
    case Healthcare = 'Healthcare';
    case Finance    = 'Finance';
    case Logistics  = 'Logistics';
    case Other      = 'Other';
}
```

`php artisan typescript:transform` emits:

```ts
// packages/contracts/src/generated.ts (generated — DO NOT EDIT)
export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other';

export type CompanyData = {
    id: string;
    name: string;
    domain: string | null;
    industry: Industry;
    counts: CompanyCountsData;
    last_activity: LastActivityData;
    created_at: string;
    updated_at: string;
};
```

The frontend renders `<Badge>{company.industry}</Badge>` — the value IS the label. No `INDUSTRY_LABELS` map anywhere.

## Anti-patterns

- ❌ **Returning an Eloquent model or a raw array** from a controller/action. The whole skill is about not doing this. Models leak DB column names, lazy-load relations, serialize Carbon inconsistently, and bypass the contract entirely. Always return a `Data` object or a `Data` collection.
- ❌ **Optional-by-omission fields** (`#[Optional]` / properties that are sometimes absent) standing in for "no value." That is the laravel-data equivalent of Zod `.optional()` the contracts skill forbids. Make the field explicitly nullable (`?string`), default it server-side (counts → `0`), or model it as a discriminated-union branch. The frontend must never need `?.`.
- ❌ **Hand-editing `packages/contracts/src/generated.ts`** (or any transformer output). It is regenerated on every `typescript:transform` and your edits will vanish. Change the `Data` class / enum in PHP and re-run the transform. Treat `generated.ts` as build output.
- ❌ **Computing labels / formatting on the frontend.** If both sides need "growing vs declining" or a money string, the backend computes it once in `fromModel()` and ships the finished `label`. The frontend renders it. (Same rule as the Nest presenter.)
- ❌ **Authoring Zod by hand in `packages/contracts`** on the Laravel stack. That is the Nest.js path. Here the `Data` class is the single source; the transform produces the types. Frontend uses generated types only — no runtime Zod.
