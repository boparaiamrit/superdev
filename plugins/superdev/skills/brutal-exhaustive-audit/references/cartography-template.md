# MAP.md template

The `repo-cartographer` produces this format. Downstream auditors tick the boxes as they verify items.

```markdown
# Repo map — <commit hash> — <UTC timestamp>

## Source commands
- Frontend routes: `find apps/web/src/app -name 'page.tsx' -o -name 'route.ts' | sort`
- Backend endpoints: `grep -rn "@(Get|Post|Patch|Put|Delete)(" apps/api/src/modules/`
- Components: `find apps/web/src/components -name '*.tsx' | sort`
- Drizzle tables: `grep -rn "pgTable(" apps/api/src/db/schema/`
- Zod schemas: `grep -rn "z.object(" packages/contracts/src/`

## Frontend routes (<N> total)

- [ ] /
- [ ] /login
- [ ] /companies
- [ ] /companies/[id]
- [ ] …

## Backend endpoints (<N> total)

- [ ] GET    /v1/companies           → apps/api/src/modules/companies/companies.controller.ts:24
- [ ] POST   /v1/companies           → apps/api/src/modules/companies/companies.controller.ts:34
- [ ] …

## Components (<N> total)

- [ ] CompanyCard            → apps/web/src/components/company-card.tsx
- [ ] CompanyTable           → apps/web/src/components/company-table.tsx
- [ ] …

## Drizzle tables (<N> total)

- [ ] companies              → apps/api/src/db/schema/companies.ts
- [ ] deals                  → apps/api/src/db/schema/deals.ts
- [ ] …

## Zod schemas (<N> total)

- [ ] companyViewSchema      → packages/contracts/src/companies.ts
- [ ] companyCreateSchema    → packages/contracts/src/companies.ts
- [ ] …
```

## Diff against previous audit

After producing MAP.md, compare against `.claude/memory/superdev-learned/last-audit-counts.md` (written by previous synthesizer). If the count of any section DROPPED, raise it as a finding — something was deleted between audits and may be unintentional.
