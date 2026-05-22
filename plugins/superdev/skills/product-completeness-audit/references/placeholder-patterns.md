# Placeholder patterns to grep for

Copy-paste targets the `placeholder-hunter` runs. Extend per-stack as needed.

## Universal

```bash
grep -rn -E "TODO|FIXME|XXX|HACK|WIP" apps packages
grep -rni "lorem ipsum|placeholder|coming soon|not implemented|todo:" apps
```

## TypeScript / React

```bash
# console handlers
grep -rnE "on[A-Z]\w+=\{?\s*\(\)\s*=>\s*console\." apps/web/src
# alert handlers
grep -rnE "on[A-Z]\w+=\{?\s*\(\)\s*=>\s*alert\(" apps/web/src
# noop preventDefault-only forms
grep -rnE "onSubmit=\{?\s*\(e\)\s*=>\s*e\.preventDefault\(\)\s*\}" apps/web/src
# return-null components
grep -rnE "function\s+\w+\([^)]*\)\s*\{\s*return\s+null;?\s*\}" apps/web/src
# inline arrays as data sources
grep -rnE "const\s+(mock|fake|sample|dummy)\w*\s*=" apps/web/src
# useState with seed
grep -rnE "useState\(\s*\[\s*\{" apps/web/src
```

## Backend (Nest.js / Express)

```bash
# Stubbed controllers
grep -rnE "throw\s+new\s+(NotImplementedException|Error)\(['\"].*not implemented" apps/api/src
# Hardcoded returns
grep -rnE "return\s+\{\s*(success|ok|data):\s*(true|null|\[\])\s*\}" apps/api/src/modules
# Commented-out persistence
grep -rnE "//\s*(await|return)\s+(this\.)?db\." apps/api/src
```

## DB / migrations

```bash
# Tables without indexes (likely incomplete)
grep -rnE "pgTable\(['\"]\w+['\"]\s*,\s*\{[^}]*\}\s*\)" apps/api/src/db/schema | head -20
# Look for tables with > 3 columns and zero index() calls in their file
```

## False-positive guidance

- `TODO` in a published changelog entry — fine, doesn't ship as code
- `placeholder` as the `placeholder=` prop on an input — fine, it's UI text intentionally
- `mockData` in a test file or `__tests__/` dir — fine
- The hunter doesn't filter — it surfaces everything; the synthesizer / human decides
