# Error Handling

How errors are caught, normalized, and returned. Read in Phase 3 (filter setup) and Phase 5 (per-module error throwing).

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

The frontend's `ApiError` class (from the design-to-nextjs skill) parses this exact shape. The `code` field is a stable string the frontend can match on; `message` is for humans; `details` is structured data (typically Zod field errors).

This contract is **non-negotiable** — every error path returns this shape, including framework errors (404 on unknown routes), validation errors, and uncaught exceptions.

## The global exception filter

`src/common/filters/all-exceptions.filter.ts`:

```ts
import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import { ZodError } from 'zod';
import { ZodValidationException } from 'nestjs-zod';
import { Logger } from 'nestjs-pino';
import type { Response, Request } from 'express';

type ErrorBody = {
  code: string;
  message: string;
  details: unknown;
  request_id: string;
};

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  constructor(private readonly logger: Logger) {}

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();
    const requestId = (request.headers['x-request-id'] as string) ?? (request as any).id ?? 'unknown';

    const { status, body } = this.normalize(exception, requestId);

    // Log 5xx as errors, 4xx as warnings, 401/403 silently
    if (status >= 500) {
      this.logger.error({ err: exception, requestId, body }, 'Unhandled exception');
    } else if (status >= 400 && ![401, 403, 404].includes(status)) {
      this.logger.warn({ requestId, body }, 'Client error');
    }

    response.status(status).json(body);
  }

  private normalize(exception: unknown, requestId: string): { status: number; body: ErrorBody } {
    // 1. Zod validation errors
    if (exception instanceof ZodValidationException) {
      const zErr = exception.getZodError();
      return {
        status: HttpStatus.BAD_REQUEST,
        body: {
          code: 'VALIDATION_FAILED',
          message: 'Request validation failed',
          details: zErr.flatten(),
          request_id: requestId,
        },
      };
    }

    // 2. Nest HttpException (NotFoundException, ConflictException, etc.)
    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      const res = exception.getResponse();
      const message = typeof res === 'string' ? res : (res as any).message ?? exception.message;
      const code = typeof res === 'object' && (res as any).code
        ? (res as any).code
        : this.statusToCode(status);

      return {
        status,
        body: {
          code,
          message: Array.isArray(message) ? message.join('; ') : message,
          details: typeof res === 'object' ? (res as any).details ?? null : null,
          request_id: requestId,
        },
      };
    }

    // 3. Postgres errors (surfaced through Drizzle via postgres-js)
    if (this.isPostgresError(exception)) {
      return this.normalizePostgres(exception, requestId);
    }

    // 4. Zod schema parse failures outside the request pipeline (e.g., a presenter contract violation)
    if (exception instanceof ZodError) {
      return {
        status: HttpStatus.INTERNAL_SERVER_ERROR,
        body: {
          code: 'CONTRACT_VIOLATION',
          message: 'Server response did not match contract',
          details: process.env.NODE_ENV === 'production' ? null : exception.flatten(),
          request_id: requestId,
        },
      };
    }

    // 5. Everything else — treat as 500
    const isError = exception instanceof Error;
    return {
      status: HttpStatus.INTERNAL_SERVER_ERROR,
      body: {
        code: 'INTERNAL_ERROR',
        message: 'An unexpected error occurred',
        details: process.env.NODE_ENV === 'production'
          ? null
          : { message: isError ? exception.message : String(exception) },
        request_id: requestId,
      },
    };
  }

  private isPostgresError(err: unknown): err is { code: string; constraint?: string; column?: string; table?: string; detail?: string; message: string } {
    return (
      typeof err === 'object' &&
      err !== null &&
      'code' in err &&
      typeof (err as { code: unknown }).code === 'string' &&
      /^\d{5}$|^P\d{4}$/.test((err as { code: string }).code) === false &&
      // postgres-js errors carry a 5-char SQLSTATE-like code
      (err as { code: string }).code.length === 5
    );
  }

  private normalizePostgres(
    err: { code: string; constraint?: string; column?: string; table?: string; detail?: string; message: string },
    requestId: string,
  ): { status: number; body: ErrorBody } {
    // SQLSTATE reference: https://www.postgresql.org/docs/current/errcodes-appendix.html
    switch (err.code) {
      case '23505':  // unique_violation
        return {
          status: HttpStatus.CONFLICT,
          body: {
            code: 'DUPLICATE',
            message: 'A record with these values already exists',
            details: { constraint: err.constraint, table: err.table },
            request_id: requestId,
          },
        };
      case '23503':  // foreign_key_violation
        return {
          status: HttpStatus.BAD_REQUEST,
          body: {
            code: 'FOREIGN_KEY_VIOLATION',
            message: 'Referenced record does not exist',
            details: { constraint: err.constraint, table: err.table },
            request_id: requestId,
          },
        };
      case '23502':  // not_null_violation
        return {
          status: HttpStatus.BAD_REQUEST,
          body: {
            code: 'MISSING_FIELD',
            message: `Required field missing: ${err.column ?? 'unknown'}`,
            details: { column: err.column, table: err.table },
            request_id: requestId,
          },
        };
      case '23514':  // check_violation
        return {
          status: HttpStatus.BAD_REQUEST,
          body: {
            code: 'CHECK_VIOLATION',
            message: 'Value violates a database constraint',
            details: { constraint: err.constraint },
            request_id: requestId,
          },
        };
      case '40P01':  // deadlock_detected
        return {
          status: HttpStatus.CONFLICT,
          body: {
            code: 'DEADLOCK',
            message: 'Conflicting concurrent operation — please retry',
            details: null,
            request_id: requestId,
          },
        };
      case '57014':  // query_canceled (statement_timeout)
        return {
          status: HttpStatus.GATEWAY_TIMEOUT,
          body: {
            code: 'QUERY_TIMEOUT',
            message: 'Database query timed out',
            details: null,
            request_id: requestId,
          },
        };
      default:
        return {
          status: HttpStatus.INTERNAL_SERVER_ERROR,
          body: {
            code: 'DB_ERROR',
            message: 'Database error',
            details: process.env.NODE_ENV === 'production' ? null : { sqlstate: err.code, message: err.message },
            request_id: requestId,
          },
        };
    }
  }

  private statusToCode(status: number): string {
    const map: Record<number, string> = {
      400: 'BAD_REQUEST',
      401: 'UNAUTHORIZED',
      403: 'FORBIDDEN',
      404: 'NOT_FOUND',
      409: 'CONFLICT',
      422: 'UNPROCESSABLE_ENTITY',
      429: 'RATE_LIMITED',
      500: 'INTERNAL_ERROR',
      503: 'UNAVAILABLE',
    };
    return map[status] ?? `HTTP_${status}`;
  }
}
```

Wire it globally in `main.ts`:

```ts
app.useGlobalFilters(new AllExceptionsFilter(app.get(Logger)));
```

## Throwing typed errors from services

Use Nest's built-in exceptions for common cases:

```ts
import {
  NotFoundException,
  ConflictException,
  ForbiddenException,
  BadRequestException,
  UnauthorizedException,
} from '@nestjs/common';

throw new NotFoundException('Company not found');
throw new ConflictException('Domain already in use');
throw new ForbiddenException('Insufficient permissions');
```

These map to standard HTTP statuses. The global filter handles the rest.

## Domain-specific exceptions

For errors that don't map to standard HTTP exceptions, create domain exceptions:

```ts
// src/modules/email/errors/mailbox-not-warmed.exception.ts
import { HttpException, HttpStatus } from '@nestjs/common';

export class MailboxNotWarmedException extends HttpException {
  constructor(mailboxId: string) {
    super(
      {
        code: 'MAILBOX_NOT_WARMED',
        message: 'Cannot send from a mailbox that has not completed warmup',
        details: { mailbox_id: mailboxId },
      },
      HttpStatus.UNPROCESSABLE_ENTITY,
    );
  }
}
```

The `code` field flows through to the frontend, where it can show context-aware UI ("Your mailbox is still warming up — click here to see status").

## Standard error codes the frontend can rely on

Maintained in `packages/contracts/src/errors.ts` (see `references/monorepo-setup.md`). The frontend imports `ERROR_CODES` from `@<scope>/contracts` and switches on the `code` field to render context-aware UI ("Your mailbox is still warming up — click to see status").

## Validation: production-mode error secrets

The filter strips internal details in production (Prisma error messages, exception messages) because they can leak schema info. In dev they're included so debugging is easy.

Critical: never include stack traces in responses. They go to logs only.

## Anti-patterns

- ❌ Bare `throw new Error(...)` — produces unhelpful 500 responses. Throw a typed exception.
- ❌ Swallowing errors in services with try/catch and returning `null`. Let them propagate; the filter normalizes.
- ❌ Putting `message` directly into the response without a `code`. The frontend can't switch on `message` (it's localized).
- ❌ Multiple filters with overlapping `@Catch()` types. One global filter; if you need module-specific behavior, add cases inside it.
- ❌ Returning 200 with `{ error: ... }` in the body. Use the right HTTP status; frontend tooling expects it.
- ❌ Logging 401/403 noisily. They're normal traffic (someone hit an endpoint without a token); log at debug or skip.
