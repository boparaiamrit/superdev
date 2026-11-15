# Fix plan format

Read this in step 5. `SECURITY_REPORT.md` is the one file that records the review, the triage and the fixes. The main agent writes it with the operator. A report never contains a secret: name the file, the line and at most the first four characters.

## Triage order

1. Each `Blocker`, one at a time: the operator chooses to fix it or to accept it, and writes the acceptance in `ACCEPTANCES.md` if they accept.
2. Each `Major`: fixed by default; the operator may accept it in `ACCEPTANCES.md`.
3. `Minor` findings: shown as a count per file. The operator picks which to fix now; the rest stay `open` with an owner.

Within a severity, exposure comes first: a fault on a public route before one behind sign-in, and that before one on a staff-only screen. A fix that others depend on (a shared guard, a configuration value) comes before them. Severity is not priority.

The owner of a finding is `fix-applier` when the fix is a code change in named files. Three kinds of fix are the operator's: rotating a leaked secret at its issuer, a major version upgrade, and infrastructure (DNS, firewall, proxy). Removing a secret from git history rewrites the history and needs the operator's agreement.

A finding becomes `fixed` only when the check that found it passes again. It becomes `accepted ACC-n` only when the operator has written entry `ACC-n` in `ACCEPTANCES.md`; the report cites the id and copies no sentence (rule BLD-6).

## SECURITY_REPORT.md

```markdown
# Security Report

Commit: 3f2a9c1
Date: 2026-11-26

## Surface

38 routes (4 public), 12 models (9 in a workspace), 3 jobs, 1 schedule; clients web and admin (from security/repo-cartographer.md).

## Findings

| ID | Severity | Where | Evidence | Fix | Owner | State |
|---|---|---|---|---|---|---|
| S-1 | Blocker | src/modules/customers/controller.rs:31 | a token of Sharma Textiles, Pune read a customer of Sandhu Traders, Ludhiana through `GET /api/v1/customers/{id}`: 200 (security/dynamic-auditor/customer-read.txt) | use `from = "id"` in the `#[can]` rule and query through `WorkspaceRepo` | fix-applier | open |
| S-2 | Major | config/env/production.toml | `APP_ENV=production navree config:check --env production` exits 1: `session.secure` is false | set `session.secure = true` | fix-applier | fixed |
| S-3 | Blocker | .env | a live payment key (starts `sk_l`) was committed in a1b2c3d | rotate the key at the provider, then remove it from the tree | Meera Sharma | open |

## Fix plan

| Order | Finding | Who | Check after the fix |
|---|---|---|---|
| 1 | S-3 | Meera Sharma | the old key is refused by the provider; `git ls-files .env` prints nothing |
| 2 | S-1 | fix-applier | the probe "Another workspace's record" gives 404; `cargo test --test isolation` passes |
| 3 | S-2 | fix-applier | `APP_ENV=production navree config:check --env production` exits 0 |

### Only the operator can do

S-3: rotate the key at the payment provider, then tell the main agent so that the check can run.

### Accepted by the operator

None. An accepted finding is listed here as the finding and the entry of `ACCEPTANCES.md` that accepts it, for example `S-5: ACC-1`.

## Clean checks

- Every route declares access; the 4 public routes equal the plan's list (`<target>/release/<binary> routes --json`, 38 routes).
- Every body and query is wrapped in `Valid<..>`.

## Probes not run

- Row-level security role: NOT RUN, the database role could not be queried from this host. ACC-2
```

`## Findings` states are `open`, `fixed` or `accepted ACC-n`. After the last fix, re-run the static and dynamic steps for what changed and list the result under `## Clean checks`.
