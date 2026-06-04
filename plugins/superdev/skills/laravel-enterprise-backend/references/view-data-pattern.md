# View Data Pattern

The discipline that enforces the "no `?.` or `??` on the frontend" contract. Every list/detail endpoint runs Eloquent models through an **API Resource** (`Illuminate\Http\Resources\Json\JsonResource`) that produces the rich, view-ready response shape published in the hand-written TS contract. Read this in Phase 5 — every module needs a fully-populated Resource presenter.

The mechanics of API Resources (class skeleton, `collection()`, the hand-written `packages/contracts` / `resources/js/types` TS shape, and the Pest contract test) live in `api-resources.md`. This file covers the **view-shape rules** — what must be present, how counts/labels/unions are built inside `toArray()`, and how the no-null contract is verified.

> Migration note: the presenter was a `spatie/laravel-data` `Data` class in ≤v1.5; from v1.6 it is a plain Eloquent API Resource. The view-shape discipline below is unchanged.

## The contract

1. The controller/action eager-loads relations and calls `withCount()` on the Eloquent query
2. It wraps the model in the Resource — `new CompanyResource($company)` (or `CompanyResource::collection($paginator)`)
3. The Resource's `toArray()` builds a fully-populated view shape — never the model or a plain array

The frontend renders `company.counts.contacts` directly. No optional chains. No nullish coalescing. The Resource has already built every label, every count, every discriminated-union variant before the response leaves PHP.

## Why a Resource, not an inline transform in the controller

Three reasons:

1. **Testability** — `(new CompanyResource($model))->toArray(request())` is a pure mapping over a loaded model. Tests pass an Eloquent factory model, assert the view shape.
2. **Composition** — list responses, detail responses, and nested includes (e.g. `campaign.contacts[i]` via `ContactResource::collection(...)`) all reuse the same Resource.
3. **Discipline** — moving the transformation into a named Resource makes it impossible to "forget" and accidentally return a raw Eloquent model from a controller.

## View-shape rules (non-negotiable)

### 1. Eager-load relations and `withCount()` before wrapping in the Resource

Always resolve counts at the query level so the Resource receives concrete integers. Never compute counts from a lazy-loaded collection inside `toArray()` — that is an N+1 waiting to happen.

```php
// controller / action
$company = Company::query()
    ->withCount(['contacts', 'leads as open_leads_count', 'deals as won_deals_count'])
    ->with(['lastActivityLog'])
    ->findOrFail($id);   // 404 if missing or filtered by the BelongsToWorkspace scope

return new CompanyResource($company);
```

The `_count` magic attributes are integers when `withCount()` was called, or absent when it was not. Default to `0` explicitly inside `toArray()` with `(int) ($this->contacts_count ?? 0)` — never let a count reach the frontend as `null`.

> Reference-field model (v1.6): `contacts`/`leads`/`deals` are ordinary `hasMany` relations declared for read enrichment. There are no DB-level FK constraints — eager-loading, `withCount`, and joins still work on stock Postgres. See `postgres-timescale-eloquent.md`.

### 2. Counts are always integers, never null

Build the `counts` sub-object inside `toArray()`, casting each magic attribute and defaulting to `0`:

```php
'counts' => [
    'contacts'   => (int) ($this->contacts_count ?? 0),   // withCount(); 0 if not loaded
    'open_leads' => (int) ($this->open_leads_count ?? 0),
    'won_deals'  => (int) ($this->won_deals_count ?? 0),
],
```

The hand-written TS types this as `counts: { contacts: number; open_leads: number; won_deals: number }` — all required, none optional. See `api-resources.md` for the contract file and the Pest test that locks it.

### 3. Discriminated-union `kind` payloads

Every polymorphic sub-shape uses a `kind` string that is a Title Case value — matching the enum pattern used everywhere in this stack. The frontend switches on `kind` and accesses only the fields defined for that variant. Build the union inside the Resource; the frontend never derives it.

Extract the union into a private builder so `toArray()` stays readable:

```php
// app/Domains/Companies/Http/Resources/CompanyResource.php
namespace App\Domains\Companies\Http\Resources;

use Carbon\CarbonInterface;
use Illuminate\Http\Resources\Json\JsonResource;

class CompanyResource extends JsonResource
{
    public function toArray($request): array
    {
        return [
            'id'       => $this->id,
            'name'     => $this->name,
            'domain'   => $this->domain,        // nullable: explicit, never omitted
            'industry' => $this->industry->value, // Title-Case enum value = label
            'counts' => [
                'contacts'   => (int) ($this->contacts_count ?? 0),
                'open_leads' => (int) ($this->open_leads_count ?? 0),
                'won_deals'  => (int) ($this->won_deals_count ?? 0),
            ],
            'last_activity' => $this->lastActivityPayload(), // discriminated union { kind, ... }
            'created_at' => $this->created_at->toIso8601String(),
            'updated_at' => $this->updated_at->toIso8601String(),
        ];
    }

    /**
     * Build the last_activity discriminated union. Every branch returns the same
     * key set so the shape is uniform; only `kind` varies in meaning downstream.
     */
    private function lastActivityPayload(): array
    {
        $log = $this->lastActivityLog; // pre-loaded via ->with(['lastActivityLog'])

        if (! $log) {
            return ['kind' => 'None', 'at' => null, 'label' => null,
                'subject' => null, 'preview' => null, 'amount_label' => null];
        }

        $at = $log->occurred_at->toIso8601String();

        return match ($log->type) {
            'Email Sent' => [
                'kind'    => 'Email Sent',
                'at'      => $at,
                'label'   => "Sent \"{$log->subject}\" " . $this->relativeTime($log->occurred_at),
                'subject' => $log->subject,
                'preview' => null,
                'amount_label' => null,
            ],
            'Email Received' => [
                'kind'    => 'Email Received',
                'at'      => $at,
                'label'   => 'Replied ' . $this->relativeTime($log->occurred_at),
                'subject' => null,
                'preview' => $log->preview,
                'amount_label' => null,
            ],
            'Deal Won' => [
                'kind'    => 'Deal Won',
                'at'      => $at,
                'label'   => 'Won deal — ' . $this->formatMoney($log->amount_cents, $log->currency)
                    . ' ' . $this->relativeTime($log->occurred_at),
                'subject' => null,
                'preview' => null,
                'amount_label' => $this->formatMoney($log->amount_cents, $log->currency),
            ],
            default => ['kind' => 'None', 'at' => null, 'label' => null,
                'subject' => null, 'preview' => null, 'amount_label' => null],
        };
    }

    private function relativeTime(CarbonInterface $d): string
    {
        $seconds = now()->diffInSeconds($d);
        if ($seconds < 60)     return 'just now';
        if ($seconds < 3600)   return floor($seconds / 60) . 'm ago';
        if ($seconds < 86400)  return floor($seconds / 3600) . 'h ago';
        if ($seconds < 604800) return floor($seconds / 86400) . 'd ago';
        return $d->format('M j');
    }

    private function formatMoney(int $cents, string $currency): string
    {
        return '$' . number_format($cents / 100, 2);
    }
}
```

Notice:
- Every `kind` variant is handled, including `'None'` when there is no activity.
- Labels are built server-side. The frontend renders `last_activity.label` and is done.
- Fields that do not apply to a given `kind` are still present as `null` (rule 4 below) — the key set is identical across branches.

### 4. Nullable is explicit; fields are never missing

The hand-written TS contract reflects the Resource `toArray()` exactly. A `null` field is typed `string | null`; a field that is simply absent from `toArray()` would be missing from the contract — and the Pest contract test in `api-resources.md` would fail.

Rule: **every field that exists in the view shape must be present in every response, even if its value is `null`.** Omitting optional fields and having the frontend guard with `?.` violates the contract.

```php
// WRONG — field is conditionally present; frontend must use ?.preview
if ($log?->preview) {
    $payload['preview'] = $log->preview;
}

// CORRECT — field is always present; null when not applicable
'preview' => $log?->preview ?? null,
```

Do not use `$this->whenLoaded()` / `$this->when()` for fields the contract declares as required — those make the key conditionally absent, which is exactly the `?.`-forcing behavior this discipline forbids. Eager-load up front (rule 1) and emit the field unconditionally.

### 5. Dates are ISO 8601 strings

Carbon instances must be converted at the boundary. Use `->toIso8601String()` (includes timezone offset) or `->toDateString()` for date-only values. Never return a Carbon object directly — Laravel will serialize it, but the format is framework-defined, not contract-defined.

```php
'created_at' => $this->created_at->toIso8601String(),
'updated_at' => $this->updated_at->toIso8601String(),
```

### 6. Never return a model or plain array from a controller

```php
// WRONG — raw model leaks DB structure; frontend has no type contract
return response()->json($company);

// WRONG — plain array loses the published TS contract entirely
return response()->json($company->toArray());

// CORRECT — the Resource is the response; Eloquent is an implementation detail
return new CompanyResource($company);
```

## Controller using the Resource presenter

The presenter is wired at the controller boundary. List endpoints use `::collection()` on a paginator (the Resource maps each item; pagination meta is preserved):

```php
// app/Domains/Companies/Http/Controllers/CompanyController.php
namespace App\Domains\Companies\Http\Controllers;

use App\Domains\Companies\Http\Resources\CompanyResource;
use App\Domains\Companies\Models\Company;

final class CompanyController
{
    public function index()
    {
        return CompanyResource::collection(
            Company::query()
                ->withCount(['contacts', 'leads as open_leads_count', 'deals as won_deals_count'])
                ->with(['lastActivityLog'])
                ->paginate()   // scoped by BelongsToWorkspace; never returns cross-workspace rows
        );
    }

    public function show(string $id)
    {
        $company = Company::query()
            ->withCount(['contacts', 'leads as open_leads_count', 'deals as won_deals_count'])
            ->with(['lastActivityLog'])
            ->findOrFail($id); // 404 if missing or filtered by the workspace scope

        return new CompanyResource($company);
    }
}
```

Write actions reload with counts/relations before wrapping, so `toArray()` has everything it needs:

```php
// app/Domains/Companies/Actions/CreateCompanyAction.php
namespace App\Domains\Companies\Actions;

use App\Audit\AuditManager;
use App\Domains\Companies\Http\Resources\CompanyResource;
use App\Domains\Companies\Models\Company;
use Illuminate\Support\Facades\DB;

final class CreateCompanyAction
{
    public function __construct(private AuditManager $audit) {}

    public function execute(array $attributes): CompanyResource
    {
        return $this->audit->run('company.create', 'Company', function () use ($attributes) {
            $company = DB::transaction(fn () => Company::create($attributes));

            // Reload with counts/relations so toArray() is fully populated
            $company->loadCount(['contacts', 'leads as open_leads_count', 'deals as won_deals_count'])
                ->load('lastActivityLog');

            return new CompanyResource($company);
        });
    }
}
```

Every endpoint that returns data wraps the model in a Resource. No exceptions. Validation of the input array is handled by a FormRequest (see `validation.md`); the audit wrapper and a plain `DB::transaction()` are standard Postgres semantics (see `audit-attribute.md`).

## Pest test — the presenter no-null contract

This test is mandatory for every module. It proves the Resource's `toArray()` carries the required keys, that counts are integers, that the discriminated union has a string `kind`, and that no required field is `null`.

```php
// tests/Feature/Companies/CompanyResourceTest.php
use App\Domains\Companies\Http\Resources\CompanyResource;
use App\Domains\Companies\Models\Company;

it('CompanyResource toArray has required keys, no null on required fields', function () {
    $company = Company::factory()->create();
    $array = (new CompanyResource(
        $company->loadCount(['contacts', 'leads as open_leads_count', 'deals as won_deals_count'])
                ->load('lastActivityLog')
    ))->toArray(request());

    expect($array)->toHaveKeys([
        'id', 'name', 'domain', 'industry', 'counts', 'last_activity', 'created_at', 'updated_at',
    ]);

    // counts default to 0 and are integers
    expect($array['counts']['contacts'])->toBeInt()
        ->and($array['counts']['open_leads'])->toBeInt()
        ->and($array['counts']['won_deals'])->toBeInt();

    // discriminated union always carries a string kind
    expect($array['last_activity']['kind'])->toBeString();

    // required fields are never null (domain is intentionally nullable, so exclude it)
    foreach (['id', 'name', 'industry', 'counts', 'last_activity', 'created_at', 'updated_at'] as $key) {
        expect($array[$key])->not->toBeNull();
    }
    expect($array['created_at'])->toBeString();
});
```

Pair this with the published-contract test from `api-resources.md` (which asserts `toArray()` matches the hand-written TS shape), plus the cross-workspace 404 and authz-negative tests from `multitenancy-global-scope.md`. Together they form the minimum Pest suite for every module.

## Cross-module data composition

A campaign view might include a `mailbox` summary owned by the Mailboxes domain. Two patterns:

1. **Nested Resource** — the Campaigns query eager-loads `mailbox` via `->with(['mailbox'])`, then `CampaignResource::toArray()` embeds `new MailboxResource($this->mailbox)` (or `(new MailboxResource(...))->toArray($request)` for a plain sub-array). This is the default.
2. **Resolved value** — the Campaigns action resolves a `MailboxResource` from its own domain and passes the already-loaded model into the Campaigns query result before wrapping.

Default to (1) for clarity; switch to (2) when the eager-load is awkward. In both cases the Campaigns Resource assembles the final shape — the frontend never sees the raw join.

```php
// Nested Resource inside CampaignResource::toArray()
return [
    'id'   => $this->id,
    'name' => $this->name,
    'counts' => [
        'recipients' => (int) ($this->recipients_count ?? 0),
        'opened'     => (int) ($this->opened_count ?? 0),
    ],
    // mailbox is its own Resource — eager-loaded via ->with(['mailbox'])
    'mailbox' => (new MailboxResource($this->mailbox))->toArray($request),
    'created_at' => $this->created_at->toIso8601String(),
    'updated_at' => $this->updated_at->toIso8601String(),
];
```

Keep each Resource focused on its own model. A parent Resource composes child Resources; it does not reach into another domain's columns directly.

## Anti-patterns

- Returning a raw Eloquent model from a controller or action (`return $company;` / `response()->json($company)`). The whole pattern exists to prevent this — wrap it in a Resource.
- Spreading the model into the response (`['...' => $this->resource->toArray()]` or `array_merge($this->resource->getAttributes(), [...])`). Field-by-field construction in `toArray()` is intentional — it surfaces missed transformations.
- Building view labels in the controller. Controllers eager-load and wrap; the Resource owns every label, count, and union.
- Skipping the presenter no-null Pest test (and the contract test in `api-resources.md`). That is how contract drift is caught before it reaches the frontend.
- Using `$this->when()` / `$this->whenLoaded()` for fields the contract declares required. Conditional keys force the frontend back to `?.`. Eager-load up front and emit the field unconditionally.
- Making a field nullable in the shape and then omitting it for some `kind`. If a field is `null` only for a particular variant, still emit it as `null` — never drop the key.
- Lazy-loading relations inside `toArray()`. The query layer owns the loading (`with`/`withCount`); the Resource owns the mapping. A lazy access in `toArray()` is an N+1 across a collection.
- Letting the frontend compute things the backend can compute. If both sides need "growing vs declining", the backend computes once and the frontend renders `last_activity.label` directly.
