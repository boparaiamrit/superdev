# Dependency Audit Checklist (Phase 4)

What `dependency-auditor` runs to catch CVEs, supply-chain risks, and license issues.

## Prerequisites

```bash
pnpm install --frozen-lockfile
# If this fails, the lockfile is stale — finding #1 right there
```

A fresh `node_modules` keyed to the lockfile is required; otherwise `pnpm audit` audits whatever happens to be installed locally, which may differ from production.

## 1. pnpm audit — production deps

```bash
pnpm audit --prod --audit-level low --json > /tmp/audit-prod.json 2>&1 || true
cat /tmp/audit-prod.json | jq '.advisories'
```

Each advisory is a finding. Map severity:

| `pnpm audit` severity | This skill's severity |
|---|---|
| critical | **Critical** |
| high | **High** |
| moderate | **Medium** |
| low | **Low** |
| info | **Info** |

For each advisory, the finding includes:

```
### S-P-<N> [<severity>] — CVE: <CVE-ID> in <package> via <path>

- **Category:** Dependency CVE
- **Package:** <name>@<version>
- **Advisory:** <URL>
- **Affected paths:** <how it's used in our code, if discoverable>
- **Patched in:** <version> — or `no fix yet`
- **Recommendation:**
  - If patched: `pnpm update <package>` (or, for transitive deps, add a `pnpm.overrides` entry)
  - If no fix: monitor + document risk in SECURITY_FIX_PLAN.md "deferred" section
```

## 2. pnpm audit — dev deps

```bash
pnpm audit --dev --audit-level low --json > /tmp/audit-dev.json 2>&1 || true
```

CVEs in dev deps (build tools, test runners, linters) are less acute. Downgrade severity one level:

| `pnpm audit` severity | This skill's severity (devDep) |
|---|---|
| critical | High |
| high | Medium |
| moderate | Low |
| low | Info |
| info | Info |

Exception: a CVE in a tool that executes during install (postinstall scripts) is back to its raw severity — it ran on someone's machine.

## 3. Lockfile checks

### 3.1 — Lockfile present and committed

```bash
test -f pnpm-lock.yaml && echo "lockfile present" || echo "MISSING"
git check-ignore pnpm-lock.yaml 2>/dev/null && echo "GITIGNORED (bad)" || echo "tracked"
```

**Findings:**
- Missing lockfile → **Critical** (every install is non-reproducible)
- Lockfile in `.gitignore` → **Critical**

### 3.2 — Lockfile fresh (matches package.json)

```bash
pnpm install --lockfile-only --dry-run 2>&1 | tee /tmp/lockfile-check.txt
grep -q "Lockfile is up to date" /tmp/lockfile-check.txt && echo "fresh" || echo "STALE"
```

A stale lockfile means production runs different versions than developers' machines.

**Severity:** **Medium**.

### 3.3 — No `workspace:*` deps outside the workspace

For monorepo packages, `"@<scope>/contracts": "workspace:*"` is correct. But if a public/published package has `"workspace:*"`, the publish step will fail or worse, publish a broken package.

```bash
grep -rn "workspace:\\*" packages/*/package.json
# Verify each is for an internal dep only
```

## 4. Version specifier hygiene

### 4.1 — No `"*"` or `"latest"` in any package.json

```bash
grep -rEn '"\\^?(\\*|latest|x|x\\.x\\.x)"' \
  apps/*/package.json packages/*/package.json package.json
```

Each hit:

- In `dependencies` (production) → **Medium**
- In `devDependencies` → **Low**

### 4.2 — No `git+` or `file:` protocol

```bash
grep -rEn '"\\s*(git\\+|file:)' \
  apps/*/package.json packages/*/package.json package.json
```

`file:` and `git+ssh://` deps mean some code in production isn't covered by `pnpm audit` and may not be reproducible.

**Severity:** **Medium** unless explicitly approved (internal vendored fork).

### 4.3 — No floating major versions on critical deps

Critical runtime deps (`@nestjs/*`, `drizzle-orm`, `postgres`, `bullmq`, `argon2`, `nextjs`, `react`) should pin to a major-minor at minimum:

```bash
grep -E '"(@nestjs/|drizzle-orm|postgres|bullmq|argon2|next|react)"' \
  apps/*/package.json | grep -E '"\\^?\\d+"'  # ^X (major-only)
```

`"^14"` allows any 14.x → fine for stable libs. `"*"` or `""` is what we're against.

## 5. Dev vs prod separation

### 5.1 — Test/build tools in production deps

Common mistakes:

```bash
# These should be in devDependencies, not dependencies
for pkg in vitest jest @testing-library mocha @types/ prettier eslint tsx \
           drizzle-kit @nestjs/cli typescript; do
  jq --arg pkg "$pkg" \
    '.dependencies | to_entries | map(select(.key | startswith($pkg)))' \
    apps/*/package.json packages/*/package.json
done
```

**Severity:** **Low** (bloat + supply-chain surface, not a direct security issue).

### 5.2 — `@types/*` in production deps

```bash
jq '.dependencies | keys[] | select(startswith("@types/"))' \
  apps/*/package.json packages/*/package.json
```

`@types/*` packages have no runtime; in production deps they just bloat the install.

**Severity:** **Low**.

## 6. License audit (optional)

If `license-checker` or similar is installable:

```bash
pnpm dlx license-checker-rseidelsohn --production --summary
```

Look for:

- GPL-2.0, GPL-3.0, AGPL-* in production deps — incompatible with most commercial use
- SSPL (MongoDB) — restrictive on hosted services
- Unknown / unlicensed → red flag
- "UNLICENSED" without explicit license field → assume worst case

**Severity:**
- GPL/AGPL in prod (and project isn't GPL-compatible) → **High**
- SSPL in prod (if hosting as a service) → **High**
- Unknown license → **Medium**

## 7. Supply-chain hygiene

### 7.1 — postinstall / preinstall scripts

```bash
# Scan installed packages for postinstall scripts
find node_modules -maxdepth 4 -name "package.json" -exec grep -l '"postinstall"\\|"preinstall"' {} \; \
  | head -30
```

Each script runs on install. Review the top-level ones (e.g., direct deps) — anything unusual is a finding.

**Severity:** **Info** unless something obviously malicious; then **Critical**.

### 7.2 — Optional: OSV scanner

If `osv-scanner` is installed:

```bash
osv-scanner --lockfile=pnpm-lock.yaml --format=json > /tmp/osv.json
jq '.results[]' /tmp/osv.json
```

OSV catches CVEs that aren't yet in npm's advisory database. Severity mapping same as pnpm audit.

### 7.3 — Typosquats and look-alikes

Heuristic — direct deps with names that look like popular packages:

```bash
# List direct prod deps
jq '.dependencies | keys[]' apps/*/package.json packages/*/package.json | sort -u
```

The auditor reviews the list. Suspicious entries:

- Look-alike names (`expres` vs `express`, `react-dom` vs `reactdom`)
- Recently-published packages with few downloads (cross-reference npm)
- Packages with no GitHub link

**Severity:** **High** when a typosquat is confirmed; **Info** when "looks unfamiliar, verify."

## 8. `.npmrc` / `.pnpmrc` hygiene

```bash
cat .npmrc 2>/dev/null
cat .pnpmrc 2>/dev/null
```

Watch for:

- `registry=` pointing to a private registry without auth-token referenced via env (token in plaintext is **Critical**)
- `unsafe-perm=true` or similar permissive flags

## Finding output

For each finding, append to `SECURITY_FINDINGS.md`:

```
### S-P-<N> [<severity>] — <title>

- **Category:** <CVE | Lockfile | Version | License | Supply chain | npmrc>
- **Package / file:** <package@version or path>
- **Evidence:**
  ```
  <pnpm audit output excerpt or grep result>
  ```
- **Why it matters:** <impact in plain English>
- **Recommendation:**
  - If CVE with fix: `pnpm update <pkg>` or `pnpm.overrides` entry
  - If no fix: defer + monitor + document
  - If license issue: replace dep or restructure architecture
  - If lockfile: `pnpm install --lockfile-only` and commit
- **Acceptance criteria:** <how to verify the fix landed — typically `pnpm audit --prod` returns clean>
```

## Re-run after fixes

After Phase 6 applies dep fixes:

```bash
pnpm install
pnpm audit --prod --audit-level low
```

The output should be empty (or only contain Info-level entries the user explicitly accepted). If High/Critical advisories remain, the fix didn't land.

## What to skip

- **Banner CVEs in `audit` output for packages we don't actually use** — sometimes a CVE is "via" a transitive path that never executes in our code. The agent shouldn't try to determine this; just flag and let the user accept-or-fix.
- **CVEs in `@types/*`** — type-only deps don't run; mark as Info.

## Acceptance criteria for the audit phase

- `pnpm audit --prod --audit-level high` returns zero high+critical CVEs (or all are deferred with documentation)
- `pnpm-lock.yaml` present, tracked, fresh
- Zero `"*"` / `"latest"` versions in production deps
- License scan run, no unresolved GPL/AGPL in production
- No typosquats or suspicious unverified packages
