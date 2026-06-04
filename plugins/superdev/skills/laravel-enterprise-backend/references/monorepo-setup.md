# Monorepo Setup (Laravel)

Set up the pnpm workspace + Turborepo monorepo that hosts `apps/web`, `apps/api` (Laravel), and `packages/contracts`. Read first in Phase 3, before scaffolding the Laravel app. The key difference from the Nest.js setup: `apps/api` is a **Composer/PHP project, not a pnpm package**. Turbo does not manage it. `packages/contracts` is a **hand-authored TS package** that both sides keep in lockstep with the API Resources — the Pest contract test is the guard (see `api-resources.md`). For the Inertia monolith, types live in `resources/js/types/` instead (see `design-to-laravel.md`).

## Goal structure

```
<workspace>/
├── apps/
│   ├── web/                 ← Next.js frontend (design-to-nextjs skill; pnpm workspace package)
│   └── api/                 ← Laravel 13 backend (composer.json; NOT a pnpm package)
│       ├── app/
│       ├── config/
│       ├── database/
│       ├── routes/
│       ├── tests/
│       └── composer.json
├── packages/
│   ├── contracts/           ← Hand-authored TS types; kept in lockstep with API Resources
│   ├── tsconfig/            ← Shared tsconfig presets
│   └── eslint-config/       ← Shared ESLint config
├── docker-compose.yml       ← Postgres + TimescaleDB for local dev
├── .gitignore
├── package.json             ← Workspace root (pnpm)
├── pnpm-workspace.yaml
└── turbo.json
```

`apps/api` intentionally sits at the same path as the Nest.js counterpart so every sibling skill's `apps/api` path assumption holds. It is kept out of `pnpm-workspace.yaml` — pnpm has nothing to manage there.

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

No `"contracts"` script here — there is no code-generation step. TS types in `packages/contracts` are hand-authored; run `pnpm install` and build normally.

## Step 2 — Workspace config

`pnpm-workspace.yaml` — **`apps/api` is deliberately omitted**; it has no `package.json` managed by pnpm:

```yaml
packages:
  - "apps/web"
  - "packages/*"
```

`apps/web` is listed explicitly (not `apps/*`) so the wildcard does not accidentally try to parse `apps/api/composer.json` as a Node package.

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

Key points:

- No `"contracts"` task — no codegen pipeline exists. `packages/contracts` has no `build` script (nothing to compile); `apps/web` imports directly from source `.ts` files at compile time.
- `"build"` depends on `"^build"` so any upstream packages with a build step finish before `apps/web` TypeScript runs; `packages/contracts` is type-only and participates only via typecheck.

## Step 4 — Shared tsconfig preset

```bash
mkdir -p packages/tsconfig
```

`packages/tsconfig/package.json`:

```json
{
  "name": "@<scope>/tsconfig",
  "version": "0.0.0",
  "private": true,
  "files": ["base.json", "nextjs.json"]
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
  "files": ["base.js", "nextjs.js"],
  "dependencies": {
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "eslint-config-prettier": "^9.0.0"
  }
}
```

## Step 6 — Contracts package (hand-authored)

This is the most important shared package. In the Laravel stack the source of truth lives in the **API Resource `toArray()` shape**. Types in `packages/contracts/src/<feature>.ts` are authored by hand and kept in lockstep with those Resources. A Pest contract test (`tests/Feature/<Feature>ContractTest.php`) in `apps/api` guards the pairing — see `api-resources.md`.

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
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "exports": {
    ".": "./src/index.ts",
    "./*": "./src/*.ts"
  },
  "scripts": {
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "@<scope>/tsconfig": "workspace:*",
    "typescript": "^5.4.0"
  }
}
```

`packages/contracts/tsconfig.json`:

```json
{
  "extends": "@<scope>/tsconfig/base.json",
  "compilerOptions": {
    "noEmit": true,
    "rootDir": "src",
    "module": "ESNext",
    "target": "ES2022",
    "moduleResolution": "Bundler"
  },
  "include": ["src/**/*.ts"]
}
```

The package does **not** have a `build` script — there is nothing to compile. `apps/web` imports directly from source (type-only at compile time).

### Authoring contracts

Each feature gets its own file. Types mirror the API Resource's `toArray()` shape exactly. No Zod, no runtime validation — these are pure TS interfaces/type aliases consumed by `apps/web`.

`packages/contracts/src/index.ts`:

```ts
export * from './companies'
export * from './contacts'
export * from './pagination'
// ... add per feature
```

`packages/contracts/src/companies.ts`:

```ts
// Hand-authored — mirrors CompanyResource::toArray() exactly.
// When toArray() changes, update this file and the Pest contract test in the same commit.

export type Industry = 'Technology' | 'Healthcare' | 'Finance' | 'Logistics' | 'Other'

export interface CompanyCounts {
  contacts: number
  open_leads: number
}

export type LastActivity =
  | { kind: 'None' }
  | { kind: 'Email Sent'; at: string; label: string }

export interface CompanyView {
  id: string
  name: string
  domain: string | null       // always present, never omitted — no ?. needed on the frontend
  industry: Industry
  counts: CompanyCounts
  last_activity: LastActivity
  created_at: string
  updated_at: string
}
```

`packages/contracts/src/pagination.ts`:

```ts
export interface PaginatedResponse<T> {
  data: T[]
  current_page: number
  per_page: number
  total: number
  last_page: number
}
```

### Committing contract files

Commit `packages/contracts/src/*.ts` to the repository. When a Resource `toArray()` changes, the contract file update and the Pest contract test fix land in the **same commit** as the PHP change. Reviewers see the contract diff alongside the Resource diff in every pull request.

## Step 7 — Wire apps/web to contracts

In `apps/web/package.json`:

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

`apps/api` does **not** appear here — it has no pnpm dependency on the contracts package. Direction is one-way: PHP upstream shapes the API; TS downstream reflects it. The backend cannot import TS.

After editing `apps/web/package.json`:

```bash
pnpm install
```

## Step 8 — Local dev: Postgres + TimescaleDB via Docker Compose

`docker-compose.yml` at the workspace root provides a Postgres + TimescaleDB container for local dev parity with the self-managed production host.

```yaml
version: "3.9"

services:
  postgres:
    image: timescale/timescaledb:latest-pg17
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

Start it:

```bash
docker compose up -d postgres
```

`apps/api/.env` for local dev:

```
DB_CONNECTION=pgsql
DB_HOST=127.0.0.1
DB_PORT=5432
DB_DATABASE=app
DB_USERNAME=app
DB_PASSWORD=secret
DB_SSLMODE=disable
```

`sslmode=disable` is acceptable against the local container. In production (self-managed host over the public internet) use `sslmode=require`.

Run migrations — the first migration enables the TimescaleDB extension:

```bash
cd apps/api && php artisan migrate
```

## Step 9 — Root .gitignore

```gitignore
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

# Laravel Boost — generated AI-tooling files (gitignored; team overrides in .ai/guidelines/*)
apps/api/.mcp.json
apps/api/CLAUDE.md
apps/api/AGENTS.md
apps/api/.ai/
apps/api/boost.json

# Laravel framework
apps/api/vendor/
apps/api/storage/framework/cache/
apps/api/storage/framework/sessions/
apps/api/storage/framework/testing/
apps/api/storage/framework/views/
apps/api/storage/logs/
apps/api/bootstrap/cache/
```

`packages/contracts/src/*.ts` are committed source — do not add them to `.gitignore`.

## Step 10 — Verify the setup

```bash
# 1. Install JS deps
pnpm install

# 2. Start local Postgres + TimescaleDB
docker compose up -d postgres

# 3. Run Laravel migrations (enables TimescaleDB extension + creates hypertables)
cd apps/api && php artisan migrate && cd ../..

# 4. Run the Pest contract tests to confirm Resources match declared TS shapes
cd apps/api && php artisan test --filter=ContractTest && cd ../..

# 5. Typecheck the monorepo (contracts + web)
pnpm turbo typecheck

# 6. Build the whole monorepo
pnpm turbo build
```

If `packages/contracts` typechecks and `apps/web` resolves its `@<scope>/contracts` imports, the wiring is correct.

## How this differs from the Nest.js monorepo setup

| Aspect | Nest.js | Laravel |
|---|---|---|
| `apps/api` in pnpm workspace | Yes — it's a Node package | **No** — Composer project; excluded from `pnpm-workspace.yaml` |
| Contract source of truth | Hand-authored Zod schemas in `packages/contracts/src/` | **Hand-authored TS interfaces** in `packages/contracts/src/<feature>.ts`; kept in lockstep with API Resource `toArray()` |
| Contract generation | No generation step; authored manually | **No generation step** — authored manually, guarded by Pest contract test |
| Turbo `contracts` task | Not present | **Not present** — no codegen; `^build` dependency chain suffices |
| Runtime validation | Yes — Zod schemas used in both apps | **No** — types only at compile time; validation is server-side via FormRequests |
| `packages/contracts` build script | Yes (`tsc`) | **No** — nothing to compile; direct TS import |
| Contract guard | TypeScript compiler + Zod parse at runtime | **Pest contract test** (`CompanyContractTest`) locks `toArray()` to the documented shape |
| Local database | Docker: Postgres 17 + TimescaleDB + Redis | **Docker: Postgres 17 + TimescaleDB** (TimescaleDB image; no Redis needed for local dev) |

## Anti-patterns

- Adding `apps/api` to `pnpm-workspace.yaml`. pnpm will fail trying to parse `composer.json` as a Node manifest.
- Hand-editing `packages/contracts/src/*.ts` without updating the corresponding API Resource (or vice versa). The Pest contract test will catch the mismatch, but the fix must be atomic.
- Skipping the Pest contract test when adding or changing a Resource field. Run `php artisan test --filter=ContractTest` before committing; the TS contract file update must land in the same commit as the PHP change.
- Using `apps/*` in `pnpm-workspace.yaml` instead of listing `apps/web` explicitly. A wildcard will try to scan `apps/api` and may surface confusing errors.
- Adding a `contracts` Turbo task that shells out to an artisan command. There is no generation step in this stack; the normal `^build` chain is sufficient.
- Setting `sslmode=disable` in a production `.env`. Only valid against local containers; the self-managed host requires `sslmode=require`.
