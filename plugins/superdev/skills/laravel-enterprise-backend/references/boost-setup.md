# Laravel Boost — AI Tooling Setup

Configure Laravel Boost so Claude Code has version-matched guidelines, skills, and an MCP server for the `apps/api` Laravel project. Run this once in Phase 3, right after the base scaffold (`references/scaffolding.md`), before authoring any feature modules.

Boost is a **dev-only** tool. It never ships to production — it is excluded from the Bref deploy package by being in `require-dev` and by the `.gitignore` rules below.

---

## Step 1 — Install

From `apps/api/`:

```bash
composer require laravel/boost --dev
```

Boost resolves the correct documentation version from your `composer.json` `require.laravel/framework` constraint. No version pin is needed on the Boost package itself.

---

## Step 2 — Run the installer

```bash
php artisan boost:install
```

The interactive prompt asks which features to enable. Enable all three:

```text
 Which Boost features would you like to enable?
 ┌──────────────────────┬────────────┐
 │  Guidelines          │ ✓ enabled  │
 │  Skills              │ ✓ enabled  │
 │  MCP                 │ ✓ enabled  │
 └──────────────────────┴────────────┘
```

What this generates (all gitignored — see Step 4):

| Generated path | Purpose |
|---|---|
| `.mcp.json` | MCP server registration for local IDE tooling |
| `CLAUDE.md` | Claude Code context injected at the start of every session |
| `AGENTS.md` | Agent context for other AI tools (Codex, etc.) |
| `.ai/` | Guidelines, skills, and boost metadata directory |
| `.ai/boost.json` | Boost version-lock manifest |

---

## Step 3 — Register the MCP server with Claude Code

The MCP server starts the Boost HTTP bridge so Claude Code can call `php artisan` commands, read app context, and use the version-matched Laravel skills.

Start the server (runs in the foreground — keep it running or use a background process manager):

```bash
php artisan boost:mcp
```

Register it with Claude Code (run once per developer machine):

```bash
claude mcp add -s local -t stdio laravel-boost php artisan boost:mcp
```

Flag meanings:
- `-s local` — local scope (stored in `~/.claude/mcp.json`, not committed)
- `-t stdio` — transport type: standard I/O (the server communicates via stdin/stdout)
- `laravel-boost` — the name used to reference this server inside Claude sessions
- `php artisan boost:mcp` — the command Claude Code spawns on demand

Verify registration:

```bash
claude mcp list
# laravel-boost  php artisan boost:mcp  (local)
```

Within a Claude Code session you can confirm the server is active:

```text
/mcp
# laravel-boost: connected
```

---

## Step 4 — Gitignore the generated files

Add these entries to `apps/api/.gitignore`. The generated files are developer-local and must not be committed — they contain machine paths and will diverge between team members.

```gitignore
# Laravel Boost — generated, developer-local, never commit
.mcp.json
CLAUDE.md
AGENTS.md
.ai/*/
boost.json
```

The glob `.ai/*/` excludes all generated subdirectories (guidelines/skills/metadata auto-written by `boost:install` and `boost:update`). The only exception is `.ai/guidelines/` content that your **team** authors intentionally (see Step 5).

---

## Step 5 — Team conventions in `.ai/guidelines/`

The `.ai/guidelines/` directory is where your team stores persistent conventions that supplement the auto-generated Boost guidelines. Unlike the generated files, these are **committed** and evolve with the codebase.

Suggested starter files:

```text
apps/api/.ai/guidelines/
├── domain-conventions.md     ← app/Domains/<Feature>/ layout, naming rules
├── data-presenter-rules.md   ← never return a model; always return an API Resource
├── audit-rules.md            ← every mutation must use AuditManager::run()
├── enum-rules.md             ← Title Case string-backed enums, no _LABELS maps
└── workspace-isolation.md    ← BelongsToWorkspace on every tenant model
```

These files surface inside Claude Code sessions via the `CLAUDE.md` Boost injects. Because the generated `CLAUDE.md` and `.ai/*` are gitignored, track the team convention files explicitly in `.gitignore` (un-exclude them):

```gitignore
# Laravel Boost — generated, developer-local, never commit
.mcp.json
CLAUDE.md
AGENTS.md
.ai/*/
boost.json

# Team conventions — commit these
!.ai/guidelines/
```

Example team convention (`.ai/guidelines/data-presenter-rules.md`):

```markdown
# Data Presenter Rules

- Every controller response MUST return an Eloquent API Resource (`JsonResource`), never a raw
  Eloquent model or plain array.
- Use `CompanyResource::make($model)` (or the relevant feature Resource class).
- Nullable fields are declared explicitly in `toArray()` — never omitted from the output.
- Keep the hand-written TS contract in lockstep with your API Resources (no codegen); update
  `packages/contracts/src/<feature>.ts` (decoupled) or `resources/js/types/` (Inertia) by hand
  and run the Pest contract test to verify the shape.
```

---

## Step 6 — Update Boost after adding packages

Whenever you add a `composer require` package that Boost has built-in knowledge for (e.g., `spatie/laravel-permission`, `laravel/sanctum`), run:

```bash
php artisan boost:update --discover
```

`--discover` tells Boost to scan `composer.json` and pull in updated guidelines and skills for any newly recognised packages. Run this after every significant `composer require` session, not just after major upgrades.

Workflow integration — add it to the scaffolding checklist in `references/scaffolding.md` and note it in the Phase 3 steps:

```bash
# After: composer require laravel/sanctum spatie/laravel-permission aws/aws-sdk-php
php artisan boost:update --discover
```

---

## Step 7 — Verify

```bash
# Confirm Boost commands are registered
php artisan list boost

# Expected output includes:
#   boost:install
#   boost:mcp
#   boost:update
```

Inside a Claude Code session, ask:

```text
What Laravel version does this project use?
```

Claude should answer from the Boost-injected context rather than guessing from its training data. If the answer is wrong, re-run `boost:update --discover` and confirm the MCP server is connected.

---

## Production safety

Boost is declared in `require-dev` and Bref's deploy pipeline never installs dev dependencies:

```bash
# deploy-time composer install (no --dev)
composer install --no-dev --optimize-autoloader
```

Because `laravel/boost` is never in `vendor/` on the deployed Lambda, neither `php artisan boost:mcp` nor any Boost-generated file can run or exist in production. The gitignored files (`.mcp.json`, `CLAUDE.md`, etc.) are also absent from the deploy package by definition.

Do NOT move `laravel/boost` to `require` (non-dev). If a CI step accidentally runs `composer install` with `--dev` in a production-bound image, add an explicit Bref `exclude` in `serverless.yml` as a belt-and-suspenders guard:

```yaml
# serverless.yml — belt-and-suspenders exclusion (should already be unreachable via --no-dev)
package:
  patterns:
    - '!vendor/laravel/boost/**'
    - '!.ai/**'
    - '!CLAUDE.md'
    - '!AGENTS.md'
    - '!.mcp.json'
```

---

## Anti-patterns

- **Committing `.mcp.json` or `CLAUDE.md`.** These contain absolute local paths and machine-specific settings. Every developer regenerates them with `boost:install`.
- **Committing `.ai/*/` wholesale then hand-editing the generated files.** Generated content gets overwritten on `boost:update`. Own your conventions in `.ai/guidelines/` (committed) and leave the rest gitignored.
- **Skipping `boost:update --discover` after `composer require`.** Boost's guidelines for `spatie/laravel-permission` and Sanctum are only activated once Boost knows those packages are present.
- **Moving `laravel/boost` to `require`.** It bloats the deploy package, introduces dev tooling into production, and breaks the principle that `php artisan boost:mcp` should only be reachable in development environments.
- **Registering the MCP server with `-s project` scope.** Project-scoped MCP registration writes `.claude/settings.json`, which may end up committed. Use `-s local` so the registration lives in `~/.claude/` and is never accidentally pushed.
