# View Data Pattern

The discipline that enforces the "no `?.` or `??` on the frontend" contract. Every action/service method runs Eloquent models through a `Data` class that produces the rich, view-ready response shape defined in `packages/contracts`. Read this in Phase 5 — every module needs a fully-populated Data presenter.

The mechanics of `spatie/laravel-data` (class definition, `typescript:transform` emit, TS type generation) live in `laravel-data-contracts.md`. This file covers the **view-shape rules** — what must be present, how counts/labels/unions are built, and how the no-null contract is verified.

## The contract

1. Action/service eager-loads relations and calls `withCount()` on the Eloquent query
2. Action calls `CompanyData::fromModel($model)` → gets a fully-populated Data object
3. Controller returns the Data object — never the model or a plain array

The frontend renders `company.counts.contacts` directly. No optional chains. No nullish coalescing. The Data class has already built every label, every count, every discriminated-union variant before the response leaves PHP.

## Why a Data class, not a service method

Three reasons:

1. **Testability** — `CompanyData::fromModel()` is a pure static factory. Unit tests pass Eloquent model fixtures, assert the view shape.
2. **Composition** — list responses, detail responses, and nested includes (e.g. `campaign.contacts[i]`) all reuse the same Data class.
3. **Discipline** — moving the transformation to a named class makes it impossible to "forget" and accidentally return a raw Eloquent model from an action.

## View-shape rules (non-negotiable)

### 1. Eager-load relations and `withCount()` before passing to `fromModel()`

Always resolve counts at the query level so the Data class receives concrete integers. Never compute counts from a lazy-loaded collection inside `fromModel()`.

```php
// action / service
$company = Company::query()
    ->withCount(['contacts', 'openLeads as open_leads_count', 'wonDeals as won_deals_count'])
    ->with(['lastActivityLog'])
    ->findOrFail($id);

return CompanyData::fromModel($company);
```

The `_count` magic attributes are integers when `withCount()` was called, or absent when it was not. Default to `0` explicitly inside `fromModel()` with the null-coalescing cast `(int) ($model->contacts_count ?? 0)` — never leave the count nullable in the Data class.

### 2. Counts are always integers, never null

```php
// CompanyCountsData.php
#[TypeScript]
class CompanyCountsData extends Data
{
    public function __construct(
        public int $contacts,    // always int; defaults to 0 if withCount() was not called
        public int $open_leads,
        public int $won_deals,
    ) {}
}
```

Inside `fromModel()`:

```php
counts: new CompanyCountsData(
    contacts:   (int) ($model->contacts_count ?? 0),
    open_leads: (int) ($model->open_leads_count ?? 0),
    won_deals:  (int) ($model->won_deals_count ?? 0),
),
```

### 3. Discriminated-union `kind` payloads

Every polymorphic sub-shape uses a `kind` string that is a Title Case value — matching the enum pattern used everywhere in this stack. The frontend switches on `kind` and accesses only the fields defined for that variant. Build the union in the Data class; the frontend never derives it.

```php
// app/Domains/Companies/Data/LastActivityData.php
#[TypeScript]
class LastActivityData extends Data
{
    public function __construct(
        public string $kind,    // 'None' | 'Email Sent' | 'Email Received' | 'Deal Won'
        public ?string $at,
        public ?string $label,
        public ?string $subject,   // only when kind = 'Email Sent'
        public ?string $preview,   // only when kind = 'Email Received'
        public ?string $amount_label, // only when kind = 'Deal Won'
    ) {}

    public static function fromModel(\App\Domains\Companies\Models\Company $company): self
    {
        $log = $company->lastActivityLog; // pre-loaded via ->with(['lastActivityLog'])

        if (! $log) {
            return new self(kind: 'None', at: null, label: null,
                subject: null, preview: null, amount_label: null);
        }

        $at = $log->occurred_at->toIso8601String();

        return match ($log->type) {
            'Email Sent' => new self(
                kind: 'Email Sent',
                at: $at,
                label: "Sent \"{$log->subject}\" " . self::relativeTime($log->occurred_at),
                subject: $log->subject,
                preview: null,
                amount_label: null,
            ),
            'Email Received' => new self(
                kind: 'Email Received',
                at: $at,
                label: 'Replied ' . self::relativeTime($log->occurred_at),
                subject: null,
                preview: $log->preview,
                amount_label: null,
            ),
            'Deal Won' => new self(
                kind: 'Deal Won',
                at: $at,
                label: 'Won deal — ' . self::formatMoney($log->amount_cents, $log->currency)
                    . ' ' . self::relativeTime($log->occurred_at),
                subject: null,
                preview: null,
                amount_label: self::formatMoney($log->amount_cents, $log->currency),
            ),
            default => new self(kind: 'None', at: null, label: null,
                subject: null, preview: null, amount_label: null),
        };
    }

    private static function relativeTime(\Carbon\Carbon $d): string
    {
        $seconds = now()->diffInSeconds($d);
        if ($seconds < 60)       return 'just now';
        if ($seconds < 3600)     return floor($seconds / 60) . 'm ago';
        if ($seconds < 86400)    return floor($seconds / 3600) . 'h ago';
        if ($seconds < 604800)   return floor($seconds / 86400) . 'd ago';
        return $d->format('M j');
    }

    private static function formatMoney(int $cents, string $currency): string
    {
        return '$' . number_format($cents / 100, 2);
    }
}
```

Notice:
- Every `kind` variant is handled, including `'None'` when there is no activity.
- Labels are built server-side. The frontend renders `last_activity.label` and is done.
- Fields that do not apply to a given `kind` are `null` — **but they are declared `?string` not omitted** (rule 4 below).

### 4. Nullable is explicit; fields are never missing

The TypeScript type emitted by `typescript:transform` reflects the PHP property types exactly. A field declared `?string` becomes `string | null` in TypeScript. A field that is simply absent from the constructor would not appear in the emitted type — and the frontend build would catch it.

Rule: **every field that exists in the view shape must be present in every response, even if its value is `null`.** Omitting optional fields and having the frontend guard with `?.` violates the contract.

```php
// WRONG — field is conditionally present; frontend must use ?.preview
if ($log?->preview) {
    $data['preview'] = $log->preview;
}

// CORRECT — field is always present; null when not applicable
preview: $log?->preview ?? null,
```

### 5. Dates are ISO 8601 strings

Carbon instances must be converted at the boundary. Use `->toIso8601String()` (includes timezone offset) or `->toDateTimeString()` for date-only values. Never return a Carbon object directly — `spatie/laravel-data` serializes them, but the format is framework-defined, not contract-defined.

```php
created_at: $model->created_at->toIso8601String(),
updated_at: $model->updated_at->toIso8601String(),
```

### 6. Never return a model or plain array from a controller

```php
// WRONG — raw model leaks DB structure; frontend has no type contract
return response()->json($company);

// WRONG — plain array loses the TypeScript contract entirely
return response()->json($company->toArray());

// CORRECT — Data class is the response; Eloquent is an implementation detail
return CompanyData::fromModel($company);
```

## Full `fromModel()` example

```php
// app/Domains/Companies/Data/CompanyData.php
namespace App\Domains\Companies\Data;

use Spatie\LaravelData\Data;
use Spatie\TypeScriptTransformer\Attributes\TypeScript;
use App\Domains\Companies\Enums\Industry;
use App\Domains\Companies\Models\Company;

#[TypeScript]
class CompanyData extends Data
{
    public function __construct(
        public string  $id,
        public string  $name,
        public ?string $domain,           // nullable: explicit, not missing
        public Industry $industry,        // Title Case enum → TS union
        public CompanyCountsData $counts, // always present; counts default to 0
        public LastActivityData $last_activity, // discriminated union
        public string  $created_at,       // ISO 8601 string
        public string  $updated_at,
    ) {}

    public static function fromModel(Company $company): self
    {
        return new self(
            id:            $company->id,
            name:          $company->name,
            domain:        $company->domain,
            industry:      $company->industry,
            counts:        new CompanyCountsData(
                contacts:   (int) ($company->contacts_count ?? 0),
                open_leads: (int) ($company->open_leads_count ?? 0),
                won_deals:  (int) ($company->won_deals_count ?? 0),
            ),
            last_activity: LastActivityData::fromModel($company),
            created_at:    $company->created_at->toIso8601String(),
            updated_at:    $company->updated_at->toIso8601String(),
        );
    }
}
```

Notice:
- Every field in `CompanyData` is built field-by-field. No `->toArray()` spread.
- Counts default to `0`, never `null`.
- The `last_activity` discriminated union covers all variants including `'None'`.
- Labels are constructed inside the Data class. The frontend renders and is done.
- Carbon instances are converted to ISO strings at the boundary.

## Action using the Data presenter

```php
// app/Domains/Companies/Actions/GetCompanyAction.php
namespace App\Domains\Companies\Actions;

use App\Domains\Companies\Data\CompanyData;
use App\Domains\Companies\Models\Company;

final class GetCompanyAction
{
    public function execute(string $id): CompanyData
    {
        $company = Company::query()
            ->withCount(['contacts', 'openLeads as open_leads_count', 'wonDeals as won_deals_count'])
            ->with(['lastActivityLog'])
            ->findOrFail($id);  // 404 if not found or filtered by BelongsToWorkspace scope

        return CompanyData::fromModel($company);
    }
}
```

```php
// app/Domains/Companies/Actions/CreateCompanyAction.php
namespace App\Domains\Companies\Actions;

use App\Audit\AuditManager;
use App\Domains\Companies\Data\CompanyData;
use App\Domains\Companies\Data\CreateCompanyData;
use App\Domains\Companies\Models\Company;
use App\Support\CockroachRetry;

final class CreateCompanyAction
{
    public function __construct(private AuditManager $audit) {}

    public function execute(CreateCompanyData $input): CompanyData
    {
        return $this->audit->run('company.create', 'Company', function () use ($input) {
            $company = CockroachRetry::transaction(
                fn () => Company::create($input->toArray())
            );
            // Reload with counts/relations so fromModel() has everything it needs
            $company->loadCount(['contacts', 'openLeads as open_leads_count', 'wonDeals as won_deals_count']);
            return CompanyData::fromModel($company);
        });
    }
}
```

Every method that returns data calls `fromModel()`. No exceptions.

## Pest test — the no-null contract

This test is mandatory for every module. It proves the Data class satisfies the contract for the required fields.

```php
// tests/Feature/Companies/CompanyDataTest.php
it('company data contains no nulls for required fields and matches the contract', function () {
    $company = Company::factory()->create();
    $data = CompanyData::fromModel($company->loadCount('contacts'))->toArray();
    expect($data)->not->toContain(null)             // spot-check required keys
        ->and($data['counts']['contacts'])->toBeInt()
        ->and($data['last_activity']['kind'])->toBeString();
});
```

Pair this with the cross-workspace 404 and authz-negative tests from `multitenancy-global-scope.md`. The three together form the minimum Pest suite for every module.

## Cross-module data composition

A campaign view might include a `mailbox` summary owned by the Mailboxes domain. Two patterns:

1. **Service-level composition** — the Campaigns action calls `MailboxData::fromModel($campaign->mailbox)` and passes it into `CampaignData::fromModel()` as a resolved value. This is the default.
2. **Eager-load + map** — the Campaigns query eager-loads `mailbox` via `->with(['mailbox'])`, then `CampaignData::fromModel()` calls `MailboxData::fromModel($campaign->mailbox)` internally.

Default to (1) for clarity; switch to (2) when the eager-load is simpler than an additional service call. In both cases, the Campaigns action assembles the final `CampaignData` shape — the frontend never sees the raw join.

```php
// Pattern 1: service-level composition
final class GetCampaignAction
{
    public function execute(string $id): CampaignData
    {
        $campaign = Campaign::query()
            ->withCount(['recipients', 'openedEmails as opened_count'])
            ->findOrFail($id);

        // Fetch the mailbox summary from its own domain
        $mailboxData = MailboxData::fromModel(
            Mailbox::findOrFail($campaign->mailbox_id)
        );

        return CampaignData::fromModel($campaign, $mailboxData);
    }
}
```

Note: cross-domain Data composition happens at the **action/service layer**, not inside `fromModel()` of the parent class. Keep each `fromModel()` focused on its own model's data.

## Anti-patterns

- Returning a raw Eloquent model from an action or controller. The whole pattern exists to prevent this.
- Spreading `$model->toArray()` into the response. Field-by-field construction is intentional — it surfaces missed transformations.
- Building view labels in the controller. Controllers call the action and return the Data object; they do not transform data.
- Skipping the no-null Pest test. That is how contract drift is caught before it reaches the frontend.
- Making a field `?string` and then not setting it when the object would otherwise be complete. If the field is `null` only for a particular `kind`, keep the `?string` type but always populate it (as `null`) — never omit it from the constructor call.
- Lazy-loading relations inside `fromModel()`. The query layer owns the loading; the Data class owns the mapping.
- Letting the frontend compute things the backend can compute. If both sides need "growing vs declining", the backend computes once and the frontend renders `last_activity.label` directly.
