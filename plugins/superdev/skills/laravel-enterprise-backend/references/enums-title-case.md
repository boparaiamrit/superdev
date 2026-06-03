# Enums — Title Case (DB = wire = UI label)

Every enum, status, stage, role, tag, or discriminator stored or transmitted as a string is in **Title Case**. The database column value equals the JSON wire value equals the UI display label. There is no `Str::title()`, no `strtoupper()`, no `_LABELS` map, no snake_case-to-display conversion anywhere in the codebase.

---

## PHP string-backed enums

Use PHP 8.1 string-backed enums. The case name is PascalCase; the backing value is the Title Case string (spaces are legal and intentional).

```php
// app/Domains/Companies/Enums/Industry.php
namespace App\Domains\Companies\Enums;

enum Industry: string
{
    case Technology = 'Technology';
    case Healthcare = 'Healthcare';
    case Finance    = 'Finance';
    case Logistics  = 'Logistics';
    case Other      = 'Other';
}
```

```php
// app/Domains/Deals/Enums/Stage.php
namespace App\Domains\Deals\Enums;

enum Stage: string
{
    case New          = 'New';
    case Qualified    = 'Qualified';
    case ProposalSent = 'Proposal Sent';   // case name PascalCase, value Title Case with spaces
    case Negotiation  = 'Negotiation';
    case Won          = 'Won';
    case Lost         = 'Lost';
}
```

The `->value` property is the canonical string in every context: database write, JSON response, query filter. Nothing converts it.

---

## Eloquent model casts

Register the enum in the model's `casts()` method. Eloquent reads the column as the enum instance on the way in and writes `->value` on the way out automatically.

```php
// app/Domains/Companies/Models/Company.php
use App\Domains\Companies\Enums\Industry;

class Company extends Model
{
    use HasUuidPrimaryKey, BelongsToWorkspace;

    protected $fillable = ['name', 'domain', 'industry', 'workspace_id'];

    // value IS the wire/UI label — no label maps, no toUpperCase
    protected function casts(): array
    {
        return [
            'industry' => Industry::class,
        ];
    }
}
```

```php
// app/Domains/Deals/Models/Deal.php
use App\Domains\Deals\Enums\Stage;

class Deal extends Model
{
    use HasUuidPrimaryKey, BelongsToWorkspace;

    protected function casts(): array
    {
        return [
            'stage' => Stage::class,
        ];
    }
}
```

---

## Good vs Bad

| Pattern | Verdict | Why |
|---|---|---|
| `'Technology'`, `'Proposal Sent'`, `'Email Sent'` | **Good** | Value IS the label. No conversion anywhere. |
| `'active'`, `'proposal_sent'` | **Bad** | Snake/lowercase; frontend must capitalize. |
| `'ADMIN'`, `'PROPOSAL_SENT'` | **Bad** | SCREAMING_SNAKE; frontend must title-case. |
| `{ value: 'tech', label: 'Technology' }` | **Bad** | Dual-field hack; the value IS the label — use `'Technology'` directly. |
| `INDUSTRY_LABELS = ['technology' => 'Technology']` | **Bad** | The label map that Title Case eliminates. |
| `Str::title($enum->value)` | **Bad** | Runtime conversion — means the stored value is wrong. |
| `strtoupper($enum->value)` | **Bad** | Runtime conversion — means the stored value is wrong. |

---

## What this changes

- **PHP enum backing values are Title Case strings.** `'Proposal Sent'`, `'In Progress'`, `'Email Sent'`. Spaces are legal in PHP string enums, JSON, and PostgreSQL `STRING` columns.
- **Eloquent `casts()` reads/writes the enum via `->value` automatically.** No manual serialization.
- **The `spatie/laravel-data` Data class passes the enum directly.** `public Industry $industry` serializes to `"industry": "Technology"` in the JSON response — the value is the label.
- **Query filters use the enum directly.** `Company::where('industry', Industry::Technology)` or `->where('industry', Industry::Technology->value)`. No lowercase conversion.
- **Spaces are legal.** `"In Progress"`, `"Proposal Sent"`, `"Email Sent"` — TypeScript string literal types, JSON, and `STRING` columns all preserve them.
- **Numeric ranges stay as ranges.** `"1-10"`, `"51-200"`, `"1000+"` — render naturally, no conversion needed.
- **Discriminator `kind` fields in discriminated unions are Title Case too.** `last_activity: { kind: 'Email Sent', at, label }` — `kind` travels on the wire, so it follows the rule. PHP `match` statements still work: `match($activity->kind->value) { 'Email Sent' => ... }`.
- **The label-map pattern collapses for simple enums.** Where you would have `INDUSTRY_LABELS = ['tech' => 'Technology']` and `['value' => 'tech', 'label' => 'Technology']`, you now just have `'Technology'`. One string, no map.
- **Complex enums keep `{ kind, label }` structure** — when a label needs computed context (`growth_signal.label = "+12% YoY"`), the structure stays, but `kind` is Title Case.
- **Storage is case-sensitive.** `Company::where('industry', 'Technology')` works; `Company::where('industry', 'technology')` does not match. The enum backing value IS the canonical value; everything else conforms.

---

## STRING columns — not native PG enum types

Store all enum columns as `STRING` (PostgreSQL `varchar`/`text`), not as native PostgreSQL `ENUM` types.

```php
// migration — STRING column, not PG native enum
Schema::create('companies', function (Blueprint $table) {
    $table->uuid('id')->primary()->default(DB::raw('gen_random_uuid()'));
    $table->string('industry');   // STRING — not $table->enum('industry', [...])
    // ...
});

Schema::create('deals', function (Blueprint $table) {
    $table->uuid('id')->primary()->default(DB::raw('gen_random_uuid()'));
    $table->string('stage');      // STRING — not a native PG enum type
    // ...
});
```

**Rationale:** Native PostgreSQL `ENUM` types require a separate `ALTER TYPE … ADD VALUE` migration every time a new case is added, and CockroachDB cross-type-cast behavior around native enums adds friction. `STRING` columns sidestep this entirely. Validation is PHP-layer (the enum cast rejects invalid values at hydration; laravel-data rejects invalid inputs at the request layer). The canonical value set lives in the PHP enum — one place, no DDL coordination needed.

---

## TypeScript emit via `typescript:transform`

When `php artisan typescript:transform` runs, `spatie/laravel-typescript-transformer` emits a TypeScript union type from each PHP enum that carries the `#[TypeScript]` attribute (or is auto-discovered through `CompanyData`'s typed properties).

```php
// Mark the enum for TS emission (or let the Data class pull it automatically)
use Spatie\TypeScriptTransformer\Attributes\TypeScript;

#[TypeScript]
enum Industry: string
{
    case Technology = 'Technology';
    case Healthcare = 'Healthcare';
    case Finance    = 'Finance';
    case Logistics  = 'Logistics';
    case Other      = 'Other';
}
```

The emitted output in `packages/contracts/src/generated.ts` is:

```ts
export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other';
export type Stage = 'New' | 'Qualified' | 'Proposal Sent' | 'Negotiation' | 'Won' | 'Lost';
```

This is identical to what the old Zod enum approach produced: `z.enum(['Technology', 'Healthcare', ...])` inferred the same string-literal union. The Next.js frontend uses these generated types directly — no Zod runtime parsing, no conversion, the value is the label.

See `laravel-data-contracts.md` for the full `typescript:transform` wiring and the Turbo `contracts` task that runs the transform before every web build.

---

## Anti-patterns

The following patterns are **banned**. If you encounter them in existing code, treat them as bugs.

```php
// BANNED: lowercase/snake values — FE must capitalize
$status = 'active';
$stage  = 'proposal_sent';

// BANNED: SCREAMING_SNAKE values — FE must title-case
$role = 'ADMIN';
$stage = 'PROPOSAL_SENT';

// BANNED: _LABELS map — the value IS the label; the map is redundant
const INDUSTRY_LABELS = [
    'technology' => 'Technology',
    'healthcare'  => 'Healthcare',
];

// BANNED: Str::title() on enum data — means the stored value is wrong
$label = Str::title($company->industry->value);

// BANNED: strtoupper() on enum data — means the stored value is wrong
$key = strtoupper($deal->stage->value);

// BANNED: dual-field value/label object for simple enums
return ['value' => 'tech', 'label' => 'Technology'];

// BANNED: native PG enum type in migrations — use STRING
$table->enum('industry', ['Technology', 'Healthcare']);  // use $table->string() instead
```
