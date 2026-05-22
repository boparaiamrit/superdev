# Auth + Tenancy + CASL

How to implement JWT auth, workspace-scoped tenancy, and CASL-based authorization. Read in Phase 4.

## The model

Every authenticated request carries:

1. **User identity** (from JWT)
2. **Workspace context** (resolved into AsyncLocalStorage so `tenantDb()` can use it)
3. **Abilities** (a CASL `Ability` instance, built per-request from user's roles + workspace)

Authorization happens in three layers:

- **`JwtAuthGuard`** — verifies the token, sets `req.user`
- **`WorkspaceContextInterceptor`** — resolves workspace, sets `req.workspace`, enters AsyncLocalStorage
- **`PoliciesGuard`** + **`@CheckAbility()`** — checks CASL ability before the handler runs

Below all of that, the `tenantDb()` wrapper enforces `workspace_id` on every query as defense-in-depth.

## CASL setup

```bash
cd apps/api
pnpm add @casl/ability
```

### Subjects and actions

Define what can be acted on, and what actions are possible:

`apps/api/src/modules/casl/ability.types.ts`:

```ts
export type Action = 'manage' | 'read' | 'create' | 'update' | 'delete' | 'send' | 'export';

export type Subjects =
  | 'Workspace' | 'User' | 'Company' | 'Contact' | 'Campaign' | 'Mailbox'
  | 'Lead' | 'Deal' | 'EmailDraft' | 'AuditLog' | 'all';

import type { MongoAbility } from '@casl/ability';
export type AppAbility = MongoAbility<[Action, Subjects]>;
```

`manage` is CASL's wildcard for "any action". `all` is the wildcard subject.

### Ability factory

`apps/api/src/modules/casl/ability.factory.ts`:

```ts
import { Injectable } from '@nestjs/common';
import { AbilityBuilder, createMongoAbility } from '@casl/ability';
import type { AppAbility } from './ability.types';
import type { Role } from '@/db/schema/enums';

type AuthedUser = {
  id: string;
  workspaceId: string;
  roles: Role[];
};

@Injectable()
export class AbilityFactory {
  createForUser(user: AuthedUser): AppAbility {
    const { can, cannot, build } = new AbilityBuilder<AppAbility>(createMongoAbility);

    if (user.roles.includes('Admin')) {
      // Admins can manage everything
      can('manage', 'all');
      // ...except some things are explicitly locked even for admins
      cannot('delete', 'Workspace');
    } else if (user.roles.includes('Operator')) {
      can('read', 'all');
      can(['create', 'update'], ['Company', 'Contact', 'Campaign', 'EmailDraft', 'Lead', 'Deal']);
      can('send', 'Campaign');
      cannot(['create', 'delete'], 'Mailbox');
      cannot('delete', ['Campaign', 'Company']);
      cannot('read', 'AuditLog');
    } else if (user.roles.includes('Pipeline')) {
      can('read', ['Company', 'Contact', 'Lead', 'Deal']);
      can('update', ['Lead', 'Deal']);
    } else if (user.roles.includes('Viewer')) {
      can('read', ['Company', 'Contact', 'Campaign', 'Lead', 'Deal']);
    }

    return build({
      // Don't let CASL detect subject type by class instance — we pass strings
      detectSubjectType: (item) => (item as { __subject?: Subjects }).__subject ?? (item as any),
    });
  }
}
```

Conditions (row-level rules) can be added when needed:

```ts
// Example: a user can only update Leads they own
can('update', 'Lead', { ownerId: user.id });
```

CASL's `Mongo`-style conditions match against object fields, so when you check `ability.can('update', leadInstance)`, it inspects the lead's `ownerId`.

## Guards and decorators

### `@CheckAbility()` decorator

`apps/api/src/common/decorators/check-ability.decorator.ts`:

```ts
import { SetMetadata } from '@nestjs/common';
import type { Action, Subjects } from '@/modules/casl/ability.types';

export const CHECK_ABILITY_KEY = 'check_ability';

export type AbilityRule = { action: Action; subject: Subjects };

export const CheckAbility = (...rules: AbilityRule[]) =>
  SetMetadata(CHECK_ABILITY_KEY, rules);
```

### `PoliciesGuard`

`apps/api/src/common/guards/policies.guard.ts`:

```ts
import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { CHECK_ABILITY_KEY, type AbilityRule } from '@/common/decorators/check-ability.decorator';
import { AbilityFactory } from '@/modules/casl/ability.factory';

@Injectable()
export class PoliciesGuard implements CanActivate {
  constructor(
    private readonly reflector: Reflector,
    private readonly abilities: AbilityFactory,
  ) {}

  canActivate(context: ExecutionContext): boolean {
    const rules = this.reflector.getAllAndOverride<AbilityRule[]>(CHECK_ABILITY_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (!rules || rules.length === 0) return true;

    const req = context.switchToHttp().getRequest();
    if (!req.user) throw new ForbiddenException('No user context');

    const ability = this.abilities.createForUser(req.user);
    req.ability = ability;   // expose for service-level checks

    for (const rule of rules) {
      if (!ability.can(rule.action, rule.subject)) {
        throw new ForbiddenException(`Cannot ${rule.action} ${rule.subject}`);
      }
    }
    return true;
  }
}
```

Wire globally in `app.module.ts`:

```ts
import { APP_GUARD } from '@nestjs/core';

@Module({
  providers: [
    { provide: APP_GUARD, useClass: JwtAuthGuard },
    { provide: APP_GUARD, useClass: PoliciesGuard },
  ],
})
export class AppModule {}
```

Order matters: JWT runs first (sets `req.user`), then Policies.

### Usage in controllers

```ts
@Controller('companies')
export class CompaniesController {
  @Get()
  @CheckAbility({ action: 'read', subject: 'Company' })
  list(@CurrentWorkspace() ws, @Query() filters: CompanyFiltersDto) { /* ... */ }

  @Post()
  @CheckAbility({ action: 'create', subject: 'Company' })
  create(@CurrentWorkspace() ws, @Body() input: CreateCompanyDto) { /* ... */ }

  @Delete(':id')
  @CheckAbility({ action: 'delete', subject: 'Company' })
  delete(@CurrentWorkspace() ws, @Param('id') id: string) { /* ... */ }
}
```

For row-level rules (e.g., "can update leads you own"), check the ability against the loaded instance in the service:

```ts
async update(workspaceId: string, id: string, input: UpdateLeadInput, ability: AppAbility) {
  const lead = await this.repo.findById(workspaceId, id);
  if (!lead) throw new NotFoundException();

  // Check row-level rule
  if (!ability.can('update', { ...lead, __subject: 'Lead' })) {
    throw new ForbiddenException('Cannot update this lead');
  }

  // ... proceed
}
```

Inject the ability via decorator:

```ts
// apps/api/src/common/decorators/current-ability.decorator.ts
import { createParamDecorator, ExecutionContext } from '@nestjs/common';
export const CurrentAbility = createParamDecorator(
  (_data, ctx: ExecutionContext) => ctx.switchToHttp().getRequest().ability,
);
```

```ts
update(@CurrentWorkspace() ws, @CurrentAbility() ability, @Param('id') id, @Body() input) {
  return this.leads.update(ws.id, id, input, ability);
}
```

## Workspace context (AsyncLocalStorage)

`tenantDb()` reads the workspace ID from AsyncLocalStorage so feature services don't need to thread it through every helper.

`apps/api/src/common/context/workspace-context.ts`:

```ts
import { AsyncLocalStorage } from 'node:async_hooks';

type WorkspaceContext = {
  workspaceId: string;
  userId: string;
  requestId: string;
};

export const workspaceContext = new AsyncLocalStorage<WorkspaceContext>();

export const getWorkspaceContext = (): WorkspaceContext => {
  const ctx = workspaceContext.getStore();
  if (!ctx) throw new Error('Workspace context not set');
  return ctx;
};
```

`WorkspaceContextInterceptor`:

```ts
// apps/api/src/common/interceptors/workspace-context.interceptor.ts
import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from '@nestjs/common';
import { Observable } from 'rxjs';
import { workspaceContext } from '@/common/context/workspace-context';

@Injectable()
export class WorkspaceContextInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const req = context.switchToHttp().getRequest();
    if (!req.user) return next.handle();

    const ctx = {
      workspaceId: req.user.workspaceId,
      userId: req.user.id,
      requestId: req.id ?? 'unknown',
    };
    req.workspace = { id: ctx.workspaceId };

    return new Observable((observer) => {
      workspaceContext.run(ctx, () => {
        next.handle().subscribe(observer);
      });
    });
  }
}
```

Wire globally:

```ts
import { APP_INTERCEPTOR } from '@nestjs/core';

providers: [
  { provide: APP_INTERCEPTOR, useClass: WorkspaceContextInterceptor },
]
```

Now anywhere in a service, `getWorkspaceContext().workspaceId` works — but still prefer passing `workspaceId` explicitly in service method signatures. AsyncLocalStorage is a backstop for things like `tenantDb()` and the audit logger that span many layers.

## JWT setup

### Token issuance

Same as before — see SKILL.md for the model. Access token (15 min) in Authorization header; refresh token (30 days) in httpOnly cookie, rotated on every refresh.

`apps/api/src/modules/auth/token.service.ts`:

```ts
import { Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { CacheService } from '@/infrastructure/cache/cache.service';
import { TypedConfigService } from '@/infrastructure/config/config.service';
import { randomUUID } from 'node:crypto';
import ms from 'ms';
import type { Role } from '@/db/schema/enums';

@Injectable()
export class TokenService {
  constructor(
    private readonly jwt: JwtService,
    private readonly cache: CacheService,
    private readonly config: TypedConfigService,
  ) {}

  async issue(userId: string, email: string, workspaceId: string, roles: Role[]) {
    const accessTtl = ms(this.config.get('JWT_ACCESS_TTL')) / 1000;
    const refreshTtl = ms(this.config.get('JWT_REFRESH_TTL')) / 1000;
    const refreshJti = randomUUID();

    const accessToken = await this.jwt.signAsync(
      { sub: userId, email, workspaceId, roles, jti: randomUUID() },
      { secret: this.config.get('JWT_ACCESS_SECRET'), expiresIn: accessTtl },
    );

    const refreshToken = await this.jwt.signAsync(
      { sub: userId, workspaceId, jti: refreshJti },
      { secret: this.config.get('JWT_REFRESH_SECRET'), expiresIn: refreshTtl },
    );

    await this.cache.set(`refresh:${refreshJti}`, { userId, workspaceId }, refreshTtl * 1000);

    return { accessToken, refreshToken, accessExpiresIn: accessTtl };
  }

  async rotate(refreshToken: string) {
    let payload: { sub: string; workspaceId: string; jti: string };
    try {
      payload = await this.jwt.verifyAsync(refreshToken, {
        secret: this.config.get('JWT_REFRESH_SECRET'),
      });
    } catch {
      throw new UnauthorizedException('Invalid refresh token');
    }

    const stored = await this.cache.get<{ userId: string; workspaceId: string }>(
      `refresh:${payload.jti}`,
    );
    if (!stored) throw new UnauthorizedException('Refresh token revoked or expired');

    await this.cache.del(`refresh:${payload.jti}`); // single-use

    // Re-fetch user; roles may have changed since last issuance
    const user = await this.repo.findById(payload.sub);
    return this.issue(user.id, user.email, user.workspaceId, user.roles);
  }

  async revoke(refreshToken: string) {
    try {
      const payload: any = await this.jwt.verifyAsync(refreshToken, {
        secret: this.config.get('JWT_REFRESH_SECRET'),
      });
      await this.cache.del(`refresh:${payload.jti}`);
    } catch { /* swallow */ }
  }
}
```

### JWT strategy

```ts
// apps/api/src/modules/auth/strategies/jwt.strategy.ts
import { Injectable } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { TypedConfigService } from '@/infrastructure/config/config.service';
import type { Role } from '@/db/schema/enums';

type Payload = { sub: string; email: string; workspaceId: string; roles: Role[]; jti: string };

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(config: TypedConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: config.get('JWT_ACCESS_SECRET'),
    });
  }

  async validate(payload: Payload) {
    return {
      id: payload.sub,
      email: payload.email,
      workspaceId: payload.workspaceId,
      roles: payload.roles,
    };
  }
}
```

### Decorators

```ts
// @Public — bypass JwtAuthGuard
import { SetMetadata } from '@nestjs/common';
export const IS_PUBLIC_KEY = 'isPublic';
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);

// @CurrentUser, @CurrentWorkspace, @CurrentAbility — param decorators
// (see earlier sections)
```

`JwtAuthGuard` reads `IS_PUBLIC_KEY`:

```ts
import { ExecutionContext, Injectable } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { Reflector } from '@nestjs/core';
import { IS_PUBLIC_KEY } from '@/common/decorators/public.decorator';

@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  constructor(private reflector: Reflector) { super(); }

  canActivate(context: ExecutionContext) {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(), context.getClass(),
    ]);
    return isPublic ? true : super.canActivate(context);
  }
}
```

## Critical test: cross-workspace isolation

Write before any feature module ships:

```ts
describe('Workspace isolation', () => {
  it('returns 404 (not 200, not 403) when reading another workspaces resource', async () => {
    const wsA = await createWorkspace('A');
    const wsB = await createWorkspace('B');
    const userA = await createUser('a@example.com', wsA.id, ['Admin']);
    const userB = await createUser('b@example.com', wsB.id, ['Admin']);

    const companyA = await createCompany(wsA.id, 'Acme');
    const tokenB = await login('b@example.com');

    const res = await request(app)
      .get(`/v1/companies/${companyA.id}`)
      .set('Authorization', `Bearer ${tokenB}`);

    expect(res.status).toBe(404);  // existence not leaked
  });

  it('CASL: viewer cannot create a company', async () => {
    const ws = await createWorkspace('A');
    const viewer = await createUser('v@example.com', ws.id, ['Viewer']);
    const token = await login('v@example.com');

    const res = await request(app)
      .post('/v1/companies')
      .set('Authorization', `Bearer ${token}`)
      .send({ name: 'X', domain: 'x.com', industry: 'technology' });

    expect(res.status).toBe(403);
    expect(res.body.code).toBe('FORBIDDEN');
  });
});
```

Both must pass before any other feature work.

## Anti-patterns

- ❌ Hand-rolling role checks: `if (user.roles.includes('Admin'))`. Use CASL.
- ❌ Skipping `@CheckAbility` on "obviously safe" endpoints. Apply consistently — explicit > implicit.
- ❌ Storing the access token in localStorage. Use httpOnly cookie for refresh, memory for access.
- ❌ Long-lived access tokens. 15 minutes is the sweet spot.
- ❌ Verifying tokens in services. Guards do that. Services trust `req.user`.
- ❌ Letting users assign their own roles. Roles are admin-assigned only.
- ❌ Using a single JWT secret for access and refresh. Separate secrets limit blast radius.
- ❌ Forgetting the cross-workspace test. THE test that proves tenancy works.
