# Scaffolding the Next.js Project

Run this in Phase 4. Goal: a runnable Next.js app with all dependencies, providers, and base files in place. Before any feature code is added, `pnpm dev` should render a blank page cleanly.

## Step 1 — Create the Next.js app

```bash
pnpm create next-app@latest my-app
```

Answer the prompts:

| Question | Answer |
|---|---|
| TypeScript? | Yes |
| ESLint? | Yes |
| Tailwind CSS? | Yes |
| `src/` directory? | Yes |
| App Router? | Yes |
| Customize default import alias? | Yes → `@/*` |
| Turbopack? | Yes |

```bash
cd my-app
```

## Step 2 — Install runtime dependencies

```bash
pnpm add \
  @tanstack/react-query \
  @tanstack/react-query-devtools \
  @tanstack/react-table \
  zustand \
  zod \
  react-hook-form \
  @hookform/resolvers \
  lucide-react \
  clsx \
  tailwind-merge \
  class-variance-authority \
  date-fns \
  sonner
```

What each does:
- `@tanstack/react-query` + devtools — all server state
- `@tanstack/react-table` — every data table
- `zustand` — client/UI state
- `zod` — runtime validation
- `react-hook-form` + `@hookform/resolvers` — form state + Zod resolver
- `lucide-react` — icons
- `clsx` + `tailwind-merge` — `cn()` helper (deduplicates Tailwind classes)
- `class-variance-authority` — typed variant API for components (used by shadcn)
- `date-fns` — date formatting
- `sonner` — toast notifications

## Step 3 — Install dev dependencies

```bash
pnpm add -D \
  @types/node \
  prettier \
  prettier-plugin-tailwindcss \
  eslint-config-prettier
```

Optional but recommended:

```bash
pnpm add -D husky lint-staged
pnpm dlx husky init
```

## Step 4 — Initialize shadcn/ui

```bash
pnpm dlx shadcn@latest init
```

Answer the prompts:

| Question | Answer |
|---|---|
| Style | New York (cleaner) or Default |
| Base color | Match the brand (Slate is a safe default) |
| CSS variables | Yes |

Then add EVERY primitive plus the sidebar block — feature modules in Phase 5 should never need to install new UI components:

```bash
pnpm dlx shadcn@latest add \
  button input label textarea select checkbox radio-group switch slider \
  dialog sheet drawer popover hover-card tooltip alert-dialog \
  dropdown-menu context-menu menubar navigation-menu command \
  form table card badge avatar skeleton separator scroll-area tabs accordion \
  toast sonner alert progress \
  calendar date-picker \
  sidebar \
  breadcrumb pagination chart
```

Why install everything up front rather than per-module?

- Feature modules run **in parallel** in the orchestrator's Phase C. Two modules running `shadcn add` at the same time would race on the lockfile.
- `sidebar` in particular is non-default — if you skip it, the layout author will reach for a hand-rolled `<aside>` and the `ui-auditor` will flag it.
- The components are source files you own; unused ones don't ship to the client bundle (tree-shaken). The disk cost is negligible.

After install, verify:

```bash
ls src/components/ui/ | wc -l           # ≥ 30
test -f src/components/ui/sidebar.tsx   # must exist
test -f components.json                 # shadcn config
test -f src/lib/utils.ts                # cn() helper
```

## Step 5 — Replace `tailwind.config.ts` and create `tokens.ts`

Use the Phase 2 output. Drop in the `tailwind.config.ts` and create `src/styles/tokens.ts`. See `references/token-extraction.md` for the templates.

## Step 6 — Set up the four base files

### `src/lib/utils.ts`

```ts
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

shadcn drops this in automatically — confirm it exists.

### `src/lib/query-client.ts`

```ts
import { QueryClient } from '@tanstack/react-query';

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Server-rendered, so don't refetch on mount by default
        staleTime: 60_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

export function getQueryClient() {
  if (typeof window === 'undefined') {
    // Server: always make a new client
    return makeQueryClient();
  }
  // Browser: reuse the same client across renders
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}
```

### `src/lib/api-client.ts`

```ts
import { z } from 'zod';
import { API_BASE } from './env';

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
    this.name = 'ApiError';
  }
}

type RequestOptions<TSchema extends z.ZodTypeAny> = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  schema: TSchema;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  searchParams?: Record<string, string | number | boolean | undefined>;
};

export async function apiRequest<TSchema extends z.ZodTypeAny>(
  path: string,
  options: RequestOptions<TSchema>,
): Promise<z.infer<TSchema>> {
  const { method = 'GET', body, schema, signal, headers = {}, searchParams } = options;

  let url = `${API_BASE}${path}`;
  if (searchParams) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(searchParams)) {
      if (v !== undefined) sp.set(k, String(v));
    }
    const qs = sp.toString();
    if (qs) url += (url.includes('?') ? '&' : '?') + qs;
  }

  const response = await fetch(url, {
    method,
    signal,
    headers: { 'Content-Type': 'application/json', ...headers },
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'include',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorBody.code ?? 'UNKNOWN',
      errorBody.message ?? response.statusText,
      errorBody.details,
    );
  }

  if (response.status === 204) return schema.parse(undefined);

  const data = await response.json();
  const parsed = schema.safeParse(data);

  if (!parsed.success) {
    console.error('API response failed schema validation', parsed.error);
    throw new ApiError(500, 'SCHEMA_MISMATCH', 'API response did not match expected schema', parsed.error);
  }

  return parsed.data;
}
```

This wrapper is non-negotiable: every API call goes through it, every response is Zod-validated, and `API_BASE` automatically routes to `/api/mock` (demo) or the real backend (production) based on env.

### `src/app/providers.tsx`

```tsx
'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'sonner';
import { getQueryClient } from '@/lib/query-client';

export function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster richColors closeButton position="top-right" />
      {process.env.NODE_ENV === 'development' && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
```

### `src/app/layout.tsx`

```tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Providers } from './providers';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });

export const metadata: Metadata = {
  title: '<APP_NAME>',
  description: 'Outbound lead generation & CRM',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-surface font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

### `src/lib/env.ts`

```ts
import { z } from 'zod';

const envSchema = z.object({
  NEXT_PUBLIC_API_MODE: z.enum(['demo', 'production']).default('demo'),
  NEXT_PUBLIC_API_BASE_URL: z.string().url().optional(),
  NEXT_PUBLIC_APP_URL: z.string().url().default('http://localhost:3000'),
});

const parsed = envSchema.safeParse({
  NEXT_PUBLIC_API_MODE: process.env.NEXT_PUBLIC_API_MODE,
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
});

if (!parsed.success) {
  console.error('Invalid env:', parsed.error.flatten().fieldErrors);
  throw new Error('Environment validation failed');
}

export const env = parsed.data;

export const API_BASE =
  env.NEXT_PUBLIC_API_MODE === 'demo'
    ? '/api/mock'
    : (env.NEXT_PUBLIC_API_BASE_URL ??
        (() => { throw new Error('NEXT_PUBLIC_API_BASE_URL is required when API_MODE=production'); })());

export const IS_DEMO = env.NEXT_PUBLIC_API_MODE === 'demo';
```

Don't access `process.env` directly in app code — go through `env.ts` so missing vars fail at boot, not at runtime. `API_BASE` is the only thing that changes between demo and production — every fetch uses it.

## Step 7 — Path aliases

Edit `tsconfig.json` to add module-level aliases:

```jsonc
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@/components/*": ["./src/components/*"],
      "@/modules/*": ["./src/modules/*"],
      "@/lib/*": ["./src/lib/*"],
      "@/hooks/*": ["./src/hooks/*"],
      "@/stores/*": ["./src/stores/*"],
      "@/styles/*": ["./src/styles/*"],
      "@/types/*": ["./src/types/*"]
    },
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true
  }
}
```

`noUncheckedIndexedAccess` is critical for enterprise — it forces you to handle `undefined` from array/object access, catching bugs at compile time.

## Step 8 — ESLint + Prettier

`.eslintrc.json`:

```json
{
  "extends": ["next/core-web-vitals", "next/typescript", "prettier"],
  "rules": {
    "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
    "@typescript-eslint/consistent-type-imports": ["error", { "prefer": "type-imports" }],
    "react/jsx-curly-brace-presence": ["error", "never"]
  }
}
```

`.prettierrc`:

```json
{
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "plugins": ["prettier-plugin-tailwindcss"]
}
```

## Step 9 — Empty module folders + mocks scaffold

```bash
mkdir -p src/{modules,components/{ui,shared},hooks,stores,styles,types,mocks}
mkdir -p src/app/api/mock/\[...path\]
touch src/styles/.gitkeep src/hooks/.gitkeep src/stores/.gitkeep src/types/.gitkeep
```

Create the demo-mode Route Handler at `src/app/api/mock/[...path]/route.ts` — full implementation in `references/dual-mode-adapter.md`. This is what makes demo mode work; without it, `NEXT_PUBLIC_API_MODE=demo` returns 404 on every call.

For each planned module from Phase 3, create the module skeleton AND the mocks folder:

```bash
for module in auth workspace companies contacts campaigns inbox pipeline analytics; do
  mkdir -p "src/modules/$module/components" "src/modules/$module/hooks"
  touch "src/modules/$module/index.ts" \
        "src/modules/$module/types.ts" \
        "src/modules/$module/schemas.ts" \
        "src/modules/$module/api.ts" \
        "src/modules/$module/query-keys.ts"
  mkdir -p "src/mocks/$module"
done
```

Then create the `.env.example` file at the project root:

```bash
# .env.example
NEXT_PUBLIC_API_MODE=demo
# Required only when NEXT_PUBLIC_API_BASE_URL is set or API_MODE=production:
# NEXT_PUBLIC_API_BASE_URL=http://localhost:3001/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

And `.env.local` for local dev defaults:

```bash
# .env.local (gitignored)
NEXT_PUBLIC_API_MODE=demo
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Step 10 — Add scripts

`package.json` scripts section:

```json
{
  "scripts": {
    "dev": "next dev --turbo",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "format": "prettier --write \"src/**/*.{ts,tsx,css,md}\"",
    "format:check": "prettier --check \"src/**/*.{ts,tsx,css,md}\"",
    "validate:fixtures": "tsx scripts/validate-fixtures.ts"
  }
}
```

Install `tsx` as a dev dep for the fixture-validation script:

```bash
pnpm add -D tsx
```

Implementation of `scripts/validate-fixtures.ts` is in `references/dual-mode-adapter.md`.

## Step 11 — Verify the app boots

```bash
pnpm dev
```

Visit `http://localhost:3000`. The default Next.js homepage should render (or your replacement). If anything errors, fix it before moving on. Common gotchas:

- Tailwind not picking up styles → check `content` paths in `tailwind.config.ts`
- `cn()` import errors → check `src/lib/utils.ts` exists and the path alias resolves
- Provider not wrapping → check `app/layout.tsx` imports `Providers`

## Final scaffolding state

```
my-app/
├── .env.example
├── .eslintrc.json
├── .prettierrc
├── components.json
├── next.config.mjs
├── package.json
├── postcss.config.js
├── tailwind.config.ts
├── tsconfig.json
└── src/
    ├── app/
    │   ├── layout.tsx
    │   ├── providers.tsx
    │   └── page.tsx
    ├── components/
    │   ├── ui/             ← shadcn primitives
    │   └── shared/         ← empty for now
    ├── modules/
    │   ├── auth/           ← skeleton files
    │   ├── companies/      ← skeleton files
    │   └── ...
    ├── lib/
    │   ├── api-client.ts
    │   ├── env.ts
    │   ├── query-client.ts
    │   └── utils.ts
    ├── hooks/              ← empty
    ├── stores/             ← empty
    ├── styles/
    │   ├── globals.css
    │   └── tokens.ts
    └── types/              ← empty
```

Now Phase 5 (module generation) can begin.
