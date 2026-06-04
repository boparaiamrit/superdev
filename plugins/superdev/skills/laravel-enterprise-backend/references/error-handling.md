# Error Handling

How errors are caught, normalized, and returned. Read in Phase 3 (bootstrap setup) and Phase 5 (per-module error throwing).

## The normalized error envelope

Every error response — regardless of origin — has this shape:

```json
{
  "code": "COMPANY_NOT_FOUND",
  "message": "Company not found",
  "details": null,
  "request_id": "req_01HXYZ"
}
```

The frontend's `ApiError` class (from the design-to-nextjs skill) parses this exact shape. The `code` field is a stable string the frontend can match on; `message` is for humans; `details` is structured data (typically field-level validation errors).

This contract is **non-negotiable** — every error path returns this shape, including framework errors (404 on unknown routes), validation errors, and uncaught exceptions.

## Error codes

The backend owns the authoritative list of error codes. The same codes used in the Nest.js variant are reused here — they are hand-written in `packages/contracts/src/errors.ts` for the frontend and mirrored in a PHP enum for use in backend logic.

**PHP error codes enum** (`app/Support/ErrorCode.php`):

```php
<?php

namespace App\Support;

enum ErrorCode: string
{
    // Generic
    case ValidationFailed       = 'VALIDATION_FAILED';
    case NotFound               = 'NOT_FOUND';
    case Duplicate              = 'DUPLICATE';
    case Unauthorized           = 'UNAUTHORIZED';
    case Forbidden              = 'FORBIDDEN';
    case RateLimited            = 'RATE_LIMITED';
    case InternalError          = 'INTERNAL_ERROR';
    case BadRequest             = 'BAD_REQUEST';
    case Conflict               = 'CONFLICT';
    case Unavailable            = 'UNAVAILABLE';

    // Database
    case ForeignKeyViolation    = 'FOREIGN_KEY_VIOLATION';
    case MissingField           = 'MISSING_FIELD';
    case CheckViolation         = 'CHECK_VIOLATION';
    case Deadlock               = 'DEADLOCK';
    case QueryTimeout           = 'QUERY_TIMEOUT';
    case DbError                = 'DB_ERROR';

    // Domain-specific (add per feature; match the Nest errors.ts keys)
    case MailboxNotWarmed       = 'MAILBOX_NOT_WARMED';
    case DomainNotVerified      = 'DOMAIN_NOT_VERIFIED';
    case CampaignAlreadySent    = 'CAMPAIGN_ALREADY_SENT';
    case InsufficientCredits    = 'INSUFFICIENT_CREDITS';
}
```

These code strings are identical to the `ERROR_CODES` object in the Nest skill's `packages/contracts/src/errors.ts` — the frontend switches on the same values regardless of which backend is running.

## Global exception handling in `bootstrap/app.php`

Wire the exception handler in `bootstrap/app.php` using `->withExceptions()`:

```php
// bootstrap/app.php
use App\Http\Middleware\ResolveWorkspace;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        api: __DIR__.'/../routes/api.php',
        health: '/api/v1/health',
    )
    ->withMiddleware(function (Middleware $middleware) {
        $middleware->api(append: [
            ResolveWorkspace::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions) {
        $exceptions->render(function (\Throwable $e, Request $request) {
            if ($request->expectsJson()) {
                return app(\App\Exceptions\Handler::class)->renderJson($e, $request);
            }
        });
    })
    ->create();
```

## The exception handler

`app/Exceptions/Handler.php`:

```php
<?php

namespace App\Exceptions;

use App\Support\ErrorCode;
use Illuminate\Auth\Access\AuthorizationException;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpKernel\Exception\HttpException;
use Throwable;

final class Handler
{
    public function renderJson(Throwable $e, Request $request): JsonResponse
    {
        $requestId = $request->header('X-Request-Id', 'unknown');

        ['status' => $status, 'body' => $body] = $this->normalize($e, $requestId);

        // Log 5xx as errors; 4xx (except 401/403/404) as warnings; 401/403/404 silently
        if ($status >= 500) {
            Log::error('Unhandled exception', [
                'exception'  => $e,
                'request_id' => $requestId,
                'body'       => $body,
            ]);
        } elseif ($status >= 400 && ! in_array($status, [401, 403, 404])) {
            Log::warning('Client error', [
                'request_id' => $requestId,
                'body'       => $body,
            ]);
        }

        return response()->json($body, $status);
    }

    /** @return array{status: int, body: array{code: string, message: string, details: mixed, request_id: string}} */
    private function normalize(Throwable $e, string $requestId): array
    {
        // 1. Laravel validation — 422
        if ($e instanceof ValidationException) {
            return [
                'status' => 422,
                'body'   => [
                    'code'       => ErrorCode::ValidationFailed->value,
                    'message'    => 'Request validation failed',
                    'details'    => $e->errors(),
                    'request_id' => $requestId,
                ],
            ];
        }

        // 2. Eloquent model-not-found — 404 (cross-workspace existence not leaked)
        if ($e instanceof ModelNotFoundException) {
            return [
                'status' => 404,
                'body'   => [
                    'code'       => ErrorCode::NotFound->value,
                    'message'    => 'Resource not found',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ];
        }

        // 3. Authorization — 403
        if ($e instanceof AuthorizationException) {
            return [
                'status' => 403,
                'body'   => [
                    'code'       => ErrorCode::Forbidden->value,
                    'message'    => 'Insufficient permissions',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ];
        }

        // 4. Authentication — 401
        if ($e instanceof AuthenticationException) {
            return [
                'status' => 401,
                'body'   => [
                    'code'       => ErrorCode::Unauthorized->value,
                    'message'    => 'Unauthenticated',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ];
        }

        // 5. Domain exceptions that carry a typed code (see "Domain exceptions" below)
        if ($e instanceof DomainException) {
            return [
                'status' => $e->getHttpStatus(),
                'body'   => [
                    'code'       => $e->getErrorCode()->value,
                    'message'    => $e->getMessage(),
                    'details'    => $e->getDetails(),
                    'request_id' => $requestId,
                ],
            ];
        }

        // 6. Symfony/Laravel HTTP exceptions (NotFoundHttpException, etc.)
        if ($e instanceof HttpException) {
            $status = $e->getStatusCode();
            return [
                'status' => $status,
                'body'   => [
                    'code'       => $this->statusToCode($status),
                    'message'    => $e->getMessage() ?: $this->statusMessage($status),
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ];
        }

        // 7. PDO / database errors
        if ($e instanceof \PDOException) {
            return $this->normalizePdo($e, $requestId);
        }

        // 8. Everything else — 500
        return [
            'status' => 500,
            'body'   => [
                'code'       => ErrorCode::InternalError->value,
                'message'    => 'An unexpected error occurred',
                'details'    => app()->isProduction()
                    ? null
                    : ['message' => $e->getMessage()],
                'request_id' => $requestId,
            ],
        ];
    }

    /** @return array{status: int, body: array{code: string, message: string, details: mixed, request_id: string}} */
    private function normalizePdo(\PDOException $e, string $requestId): array
    {
        // SQLSTATE codes: https://www.postgresql.org/docs/current/errcodes-appendix.html
        $sqlstate = $e->getCode();

        return match ($sqlstate) {
            '23505' => [   // unique_violation
                'status' => 409,
                'body'   => [
                    'code'       => ErrorCode::Duplicate->value,
                    'message'    => 'A record with these values already exists',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ],
            '23503' => [   // foreign_key_violation
                'status' => 400,
                'body'   => [
                    'code'       => ErrorCode::ForeignKeyViolation->value,
                    'message'    => 'Referenced record does not exist',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ],
            '23502' => [   // not_null_violation
                'status' => 400,
                'body'   => [
                    'code'       => ErrorCode::MissingField->value,
                    'message'    => 'Required field missing',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ],
            '23514' => [   // check_violation
                'status' => 400,
                'body'   => [
                    'code'       => ErrorCode::CheckViolation->value,
                    'message'    => 'Value violates a database constraint',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ],
            '40P01' => [   // deadlock_detected
                'status' => 409,
                'body'   => [
                    'code'       => ErrorCode::Deadlock->value,
                    'message'    => 'Conflicting concurrent operation — please retry',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ],
            '57014' => [   // query_canceled (statement_timeout)
                'status' => 504,
                'body'   => [
                    'code'       => ErrorCode::QueryTimeout->value,
                    'message'    => 'Database query timed out',
                    'details'    => null,
                    'request_id' => $requestId,
                ],
            ],
            default => [
                'status' => 500,
                'body'   => [
                    'code'       => ErrorCode::DbError->value,
                    'message'    => 'Database error',
                    'details'    => app()->isProduction()
                        ? null
                        : ['sqlstate' => $sqlstate, 'message' => $e->getMessage()],
                    'request_id' => $requestId,
                ],
            ],
        };
    }

    private function statusToCode(int $status): string
    {
        return match ($status) {
            400 => ErrorCode::BadRequest->value,
            401 => ErrorCode::Unauthorized->value,
            403 => ErrorCode::Forbidden->value,
            404 => ErrorCode::NotFound->value,
            409 => ErrorCode::Conflict->value,
            422 => ErrorCode::ValidationFailed->value,
            429 => ErrorCode::RateLimited->value,
            503 => ErrorCode::Unavailable->value,
            default => "HTTP_{$status}",
        };
    }

    private function statusMessage(int $status): string
    {
        return match ($status) {
            400 => 'Bad request',
            401 => 'Unauthenticated',
            403 => 'Insufficient permissions',
            404 => 'Resource not found',
            409 => 'Conflict',
            422 => 'Unprocessable entity',
            429 => 'Too many requests',
            503 => 'Service unavailable',
            default => 'HTTP error',
        };
    }
}
```

## Domain exceptions

For errors that don't map to a generic HTTP status, define domain exceptions that carry a typed `ErrorCode`:

```php
// app/Exceptions/DomainException.php
namespace App\Exceptions;

use App\Support\ErrorCode;
use RuntimeException;

class DomainException extends RuntimeException
{
    public function __construct(
        private readonly ErrorCode $errorCode,
        string $message,
        private readonly mixed $details = null,
        private readonly int $httpStatus = 422,
    ) {
        parent::__construct($message);
    }

    public function getErrorCode(): ErrorCode { return $this->errorCode; }
    public function getDetails(): mixed       { return $this->details; }
    public function getHttpStatus(): int      { return $this->httpStatus; }
}
```

Usage in a service:

```php
// app/Domains/Campaigns/Actions/SendCampaign.php
use App\Exceptions\DomainException;
use App\Support\ErrorCode;

if (! $campaign->mailbox->isWarmedUp()) {
    throw new DomainException(
        errorCode:  ErrorCode::MailboxNotWarmed,
        message:    'Cannot send from a mailbox that has not completed warmup',
        details:    ['mailbox_id' => $campaign->mailbox_id],
        httpStatus: 422,
    );
}
```

The `code` field flows through to the frontend, where it can show context-aware UI ("Your mailbox is still warming up — click here to see status").

## Status mapping rules

| Scenario | HTTP status | code |
|---|---|---|
| `findOrFail()` on another workspace's record | **404** | `NOT_FOUND` |
| `#[Authorize]` / policy returns false | **403** | `FORBIDDEN` |
| Missing `Authorization` header / expired token | **401** | `UNAUTHORIZED` |
| `Illuminate\Validation\ValidationException` (from a FormRequest) | **422** | `VALIDATION_FAILED` |
| Unique constraint violated (`23505`) | **409** | `DUPLICATE` |
| Domain rule violation (MailboxNotWarmed, etc.) | **422** | _(typed domain code)_ |
| Uncaught `\Throwable` | **500** | `INTERNAL_ERROR` |

**The 404 for cross-workspace reads is intentional.** The global `BelongsToWorkspace` scope silently filters out records belonging to other workspaces before the query runs. `findOrFail()` then throws `ModelNotFoundException`, which maps to 404. The caller cannot distinguish "does not exist" from "belongs to another tenant" — existence is not leaked. See `references/multitenancy-global-scope.md` for the scope implementation and the mandatory Pest test.

## Throwing errors from services

Use the built-in exception classes for common cases — they are already mapped by the handler:

```php
// Eloquent 404 — thrown automatically by findOrFail(); call it directly when needed:
Company::findOrFail($id);   // throws ModelNotFoundException → handler maps to 404 NOT_FOUND

// Authorization — thrown automatically by #[Authorize]; call it directly when needed:
abort_if(! $user->can('company.update'), 403);  // throws HttpException → handler maps to 403 FORBIDDEN

// Domain rule violation — use DomainException for typed codes:
use App\Exceptions\DomainException;
use App\Support\ErrorCode;

throw new DomainException(
    errorCode:  ErrorCode::NotFound,
    message:    'Company not found',
    httpStatus: 404,
);
```

Prefer `findOrFail()` and `#[Authorize]` over manual throws — the handler normalizes them automatically.

## Validation error shape

Laravel's validator (FormRequest) includes field-level errors in `errors()`, surfaced as `details`. The frontend can render them inline:

```json
{
  "code": "VALIDATION_FAILED",
  "message": "Request validation failed",
  "details": {
    "name": ["The name field is required."],
    "industry": ["The selected industry is invalid."]
  },
  "request_id": "req_01HXYZ"
}
```

See `references/validation.md` for the FormRequest setup that produces this output.

## Production safety

In production (`APP_ENV=production`), `details` on 5xx responses is always `null` — stack traces and internal messages never reach the client. They go to stderr → CloudWatch via Monolog JSON. In local/testing environments `details` includes the raw exception message for faster debugging.

Never include stack traces in responses. Log them only.

```php
// config/logging.php — JSON stderr for CloudWatch (Lambda)
'stack' => [
    'driver'            => 'monolog',
    'handler'           => \Monolog\Handler\StreamHandler::class,
    'with'              => ['stream' => 'php://stderr'],
    'formatter'         => \Monolog\Formatter\JsonFormatter::class,
    'formatter_with'    => [],
    'level'             => env('LOG_LEVEL', 'debug'),
],
```

## Anti-patterns

- Bare `throw new \Exception(...)` — produces unhelpful 500 responses. Throw a typed exception or `DomainException`.
- Swallowing exceptions in services with `try/catch` and returning `null`. Let them propagate; the handler normalizes.
- Putting `message` directly into the response without a `code`. The frontend cannot switch on `message` (it's human text, not stable).
- Returning 200 with `{ 'error': ... }` in the body. Use the correct HTTP status; frontend tooling expects it.
- Logging 401/403/404 noisily. They are normal traffic; log at debug or skip entirely.
- Leaking the model class name in 404 messages when a cross-workspace read fails. The handler returns a generic "Resource not found" to avoid tenant enumeration.
- Skipping the JSON content-type check — non-API routes (health endpoint, etc.) should not hit the JSON handler.
