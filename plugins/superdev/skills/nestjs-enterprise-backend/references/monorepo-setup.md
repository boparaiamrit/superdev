# Monorepo Setup

Set up the pnpm workspace + Turborepo monorepo that hosts `apps/web`, `apps/api`, and `packages/contracts`. Read first in Phase 3, before scaffolding the Nest.js app.

## Goal structure

```
<workspace>/
├── apps/
│   ├── web/              ← Next.js frontend (design-to-nextjs skill)
│   └── api/              ← Nest.js backend (this skill)
├── packages/
│   ├── contracts/        ← Zod schemas + view types — shared
│   ├── tsconfig/         ← Shared tsconfig presets
│   └── eslint-config/    ← Shared ESLint config
├── .gitignore
├── package.json          ← Workspace root
├── pnpm-workspace.yaml
├── turbo.json
└── tsconfig.json         ← Project references root
```

## Step 1 — Initialize root

```bash
mkdir <workspace> && cd <workspace>
git init
pnpm init
```

Edit root `package.json`:

```json
{
  "name": "<workspace>",
  "private": true,
  "version": "0.0.0",
  "scripts": {
    "build": "turbo run build",
    "dev": "turbo run dev",
    "lint": "turbo run lint",
    "typecheck": "turbo run typecheck",
    "test": "turbo run test",
    "format": "prettier --write .",
    "clean": "turbo run clean && rm -rf node_modules"
  },
  "devDependencies": {
    "turbo": "^2.0.0",
    "prettier": "^3.2.0",
    "typescript": "^5.4.0"
  },
  "packageManager": "pnpm@9.0.0",
  "engines": {
    "node": ">=20"
  }
}
```

## Step 2 — Workspace config

`pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

## Step 3 — Turbo config

`turbo.json`:

```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "typecheck": {
      "dependsOn": ["^build"]
    },
    "test": {
      "dependsOn": ["^build"],
      "outputs": ["coverage/**"]
    },
    "clean": {
      "cache": false
    }
  }
}
```

`dependsOn: ["^build"]` means: before `apps/api` builds, build all its `packages/*` dependencies. This is critical for `packages/contracts` to be available.

## Step 4 — Shared tsconfig preset

```bash
mkdir -p packages/tsconfig
cd packages/tsconfig
```

`packages/tsconfig/package.json`:

```json
{
  "name": "@<scope>/tsconfig",
  "version": "0.0.0",
  "private": true,
  "files": ["base.json", "node.json", "nextjs.json", "react-library.json"]
}
```

`packages/tsconfig/base.json`:

```json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true
  }
}
```

`packages/tsconfig/node.json`:

```json
{
  "extends": "./base.json",
  "compilerOptions": {
    "lib": ["ES2022"],
    "module": "CommonJS",
    "moduleResolution": "Node",
    "target": "ES2022",
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true,
    "experimentalDecorators": true,
    "emitDecoratorMetadata": true
  }
}
```

`packages/tsconfig/nextjs.json`:

```json
{
  "extends": "./base.json",
  "compilerOptions": {
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "jsx": "preserve",
    "noEmit": true,
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "src/**/*.ts", "src/**/*.tsx", ".next/types/**/*.ts"]
}
```

`packages/tsconfig/react-library.json`:

```json
{
  "extends": "./base.json",
  "compilerOptions": {
    "lib": ["DOM", "ES2022"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "target": "ES2022",
    "outDir": "dist",
    "declaration": true,
    "declarationMap": true
  }
}
```

## Step 5 — Shared ESLint config

```bash
mkdir -p packages/eslint-config
```

`packages/eslint-config/package.json`:

```json
{
  "name": "@<scope>/eslint-config",
  "version": "0.0.0",
  "private": true,
  "files": ["base.js", "node.js", "nextjs.js"],
  "dependencies": {
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "eslint-config-prettier": "^9.0.0"
  }
}
```

`packages/eslint-config/base.js`:

```js
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
  plugins: ['@typescript-eslint'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier',
  ],
  rules: {
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    '@typescript-eslint/consistent-type-imports': ['error', { prefer: 'type-imports' }],
    '@typescript-eslint/no-explicit-any': 'error',
    'no-console': ['warn', { allow: ['warn', 'error'] }],
  },
  ignorePatterns: ['dist', 'build', '.next', 'node_modules', '*.config.*'],
};
```

## Step 6 — Shared contracts package

This is the most important shared package — Zod schemas + view types used by both frontend and backend.

```bash
mkdir -p packages/contracts/src
```

`packages/contracts/package.json`:

```json
{
  "name": "@<scope>/contracts",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    },
    "./*": {
      "types": "./dist/*.d.ts",
      "import": "./dist/*.js"
    }
  },
  "files": ["dist"],
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "typecheck": "tsc --noEmit",
    "lint": "eslint src",
    "clean": "rm -rf dist"
  },
  "dependencies": {
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@<scope>/tsconfig": "workspace:*",
    "@<scope>/eslint-config": "workspace:*",
    "typescript": "^5.4.0",
    "eslint": "^8.57.0"
  }
}
```

`packages/contracts/tsconfig.json`:

```json
{
  "extends": "@<scope>/tsconfig/base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true,
    "declarationMap": true,
    "module": "ESNext",
    "target": "ES2022",
    "moduleResolution": "Bundler"
  },
  "include": ["src/**/*.ts"]
}
```

`packages/contracts/src/index.ts`:

```ts
export * from './pagination';
export * from './errors';
export * from './companies';
export * from './contacts';
export * from './campaigns';
// ... etc per module
```

`packages/contracts/src/pagination.ts`:

```ts
import { z } from 'zod';

export const paginatedResponseSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    data: z.array(itemSchema),
    total: z.number().int().nonnegative(),
    page: z.number().int().positive(),
    per_page: z.number().int().positive(),
  });

export const paginationParamsSchema = z.object({
  page: z.coerce.number().int().positive().default(1),
  per_page: z.coerce.number().int().positive().max(100).default(20),
});

export type PaginationParams = z.infer<typeof paginationParamsSchema>;
```

`packages/contracts/src/errors.ts`:

```ts
import { z } from 'zod';

export const errorResponseSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.unknown().nullable(),
  request_id: z.string(),
});

export type ErrorResponse = z.infer<typeof errorResponseSchema>;

export const ERROR_CODES = {
  VALIDATION_FAILED: 'VALIDATION_FAILED',
  NOT_FOUND: 'NOT_FOUND',
  DUPLICATE: 'DUPLICATE',
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  RATE_LIMITED: 'RATE_LIMITED',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  MAILBOX_NOT_WARMED: 'MAILBOX_NOT_WARMED',
  DOMAIN_NOT_VERIFIED: 'DOMAIN_NOT_VERIFIED',
  CAMPAIGN_ALREADY_SENT: 'CAMPAIGN_ALREADY_SENT',
  INSUFFICIENT_CREDITS: 'INSUFFICIENT_CREDITS',
} as const;

export type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];
```

Build it:

```bash
cd packages/contracts && pnpm install && pnpm build
```

## Step 7 — Root tsconfig (project references)

`tsconfig.json` at the root:

```json
{
  "files": [],
  "references": [
    { "path": "./packages/tsconfig" },
    { "path": "./packages/eslint-config" },
    { "path": "./packages/contracts" },
    { "path": "./apps/api" },
    { "path": "./apps/web" }
  ]
}
```

This enables editor-wide go-to-definition across the monorepo.

## Step 8 — Root `.gitignore`

```
# Dependencies
node_modules
.pnpm-store

# Build outputs
dist
build
.next
.turbo

# Env
.env
.env.local
.env.*.local
!.env.example

# Logs
*.log
npm-debug.log*
pnpm-debug.log*

# IDE
.vscode/*
!.vscode/extensions.json
!.vscode/settings.json
.idea

# OS
.DS_Store
Thumbs.db

# TypeScript build info
*.tsbuildinfo
```

## Step 9 — Wire into the apps

In `apps/api/package.json` (created by the scaffolding step):

```json
{
  "dependencies": {
    "@<scope>/contracts": "workspace:*"
  },
  "devDependencies": {
    "@<scope>/tsconfig": "workspace:*",
    "@<scope>/eslint-config": "workspace:*"
  }
}
```

In `apps/web/package.json` (created by design-to-nextjs scaffolding):

```json
{
  "dependencies": {
    "@<scope>/contracts": "workspace:*"
  },
  "devDependencies": {
    "@<scope>/tsconfig": "workspace:*",
    "@<scope>/eslint-config": "workspace:*"
  }
}
```

After adding, run `pnpm install` at the root.

## Step 10 — Verify

```bash
pnpm install
pnpm turbo build
```

If `@<scope>/contracts` builds first and both apps pick it up, you're done. Add a feature schema (e.g., `companies.ts`) to `packages/contracts/src/`, import from both `apps/api` and `apps/web`, and confirm imports resolve.

## Authoring shared contracts

Every Zod schema and view type for a feature lives in `packages/contracts/src/<feature>.ts`. Both apps import from `@<scope>/contracts/<feature>`.

```ts
// packages/contracts/src/companies.ts
import { z } from 'zod';
import { paginatedResponseSchema } from './pagination';

// All enums are Title Case — DB value = wire value = UI label, no conversion code anywhere.
export const industrySchema = z.enum(['Technology', 'Healthcare', 'Finance', 'Logistics', 'Other']);
export type Industry = z.infer<typeof industrySchema>;

export const sizeBucketSchema = z.enum(['1-10', '11-50', '51-200', '201-1000', '1000+']);
export type SizeBucket = z.infer<typeof sizeBucketSchema>;

export const growthSignalKindSchema = z.enum(['Growing', 'Stable', 'Declining']);
export type GrowthSignalKind = z.infer<typeof growthSignalKindSchema>;

// VIEW shape — what the API returns and the FE renders
export const companyViewSchema = z.object({
  id: z.string(),
  name: z.string(),
  domain: z.string().nullable(),
  // Simple enum: value IS the display label, render <Badge>{company.industry}</Badge>
  industry: industrySchema,
  // Numeric ranges render naturally; just append unit at the render site if needed
  size_bucket: sizeBucketSchema,
  headcount: z.object({
    current: z.number().int().nonnegative(),
    twelve_months_ago: z.number().int().nonnegative(),
    delta_pct: z.number(),
    // Complex enum: kind is Title Case, label carries computed context ("+12% YoY")
    growth_signal: z.object({
      kind: growthSignalKindSchema,
      label: z.string(),
    }),
  }),
  counts: z.object({
    contacts: z.number().int().nonnegative(),
    open_leads: z.number().int().nonnegative(),
    won_deals: z.number().int().nonnegative(),
  }),
  // Discriminator kinds are Title Case too — they're on the wire
  last_activity: z.discriminatedUnion('kind', [
    z.object({ kind: z.literal('None') }),
    z.object({ kind: z.literal('Email Sent'),     at: z.string().datetime(), subject: z.string(), label: z.string() }),
    z.object({ kind: z.literal('Email Received'), at: z.string().datetime(), preview: z.string(), label: z.string() }),
    z.object({ kind: z.literal('Deal Won'),       at: z.string().datetime(), amount_label: z.string(), label: z.string() }),
  ]),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export type CompanyView = z.infer<typeof companyViewSchema>;

export const companyListResponseSchema = paginatedResponseSchema(companyViewSchema);
export type CompanyListResponse = z.infer<typeof companyListResponseSchema>;

// INPUT shapes — what the API accepts
export const createCompanySchema = z.object({
  name: z.string().min(1).max(120),
  domain: z.string().regex(/^[a-z0-9.-]+\.[a-z]{2,}$/i).nullable(),
  industry: industrySchema,
});

export const updateCompanySchema = createCompanySchema.partial();

export type CreateCompanyInput = z.infer<typeof createCompanySchema>;
export type UpdateCompanyInput = z.infer<typeof updateCompanySchema>;
```

Notice what's there and what's gone:

- **No `INDUSTRY_LABELS` map.** The enum value IS the label. The frontend renders `<Badge>{company.industry}</Badge>` directly.
- **No `industry: { value, label }` wrapper.** That dual-field pattern only made sense when values were snake_case. With Title Case, one string does both jobs.
- **Spaces in discriminator kinds** (`'Email Sent'`, `'Deal Won'`). Legal TS string literals, legal JSON, legal Postgres enum values. Frontend pattern-matches with `case 'Email Sent':`.
- **`growth_signal` keeps `{ kind, label }`** because `label` carries the computed delta (`"+12% YoY"`) that depends on the row's data, not a static map. The static `kind` is rendered when you want a generic badge; the contextual `label` is rendered when you want the full readout.

## Anti-patterns

- ❌ Duplicating schemas across apps. The whole point of the monorepo is one source.
- ❌ Forgetting `workspace:*` in dependency declarations — apps will resolve from npm, not the workspace.
- ❌ Building apps before `packages/contracts`. `dependsOn: ["^build"]` handles this; don't fight it.
- ❌ Adding `.optional()` to view schema fields. Make it `.nullable()` or default it or use a union.
- ❌ Computing labels on the frontend. Build them in the presenter.
