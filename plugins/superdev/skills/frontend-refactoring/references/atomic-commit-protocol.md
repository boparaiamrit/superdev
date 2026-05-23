# Atomic commit protocol

The contract `atomic-module-converter` follows. The whole conversion lives in ONE commit on a feature branch; failure rolls back the entire commit.

## Pre-flight (all must hold or refuse to start)

```bash
# 1. Plan exists and is approved
test -f CONVERSION_PLAN.md
grep -q '^STATUS: APPROVED$' CONVERSION_PLAN.md

# 2. Baseline exists
test -d baseline/<feature>

# 3. Working tree is clean
test -z "$(git status --porcelain)"

# 4. Not on main / master / production
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
case "$BRANCH" in main|master|prod|production)
  echo "Refusing to convert from $BRANCH directly. Switch to a working branch first."
  exit 1 ;;
esac

# 5. Save pre-conversion SHA for rollback
git rev-parse HEAD > .conversion-pre-sha
echo "Pre-conversion SHA: $(cat .conversion-pre-sha)"
```

## Create the feature branch

```bash
git checkout -b "refactor/<feature>-decompose"
```

If branch already exists (previous failed attempt left it behind):

```bash
git branch -D "refactor/<feature>-decompose" 2>/dev/null
git checkout -b "refactor/<feature>-decompose"
```

## Execute the plan in order

Follow `CONVERSION_PLAN.md`'s "Atomic-execute order" section EXACTLY:

```
1. Stores      → Write file
2. Hooks       → Write file
3. Leaf comps  → Write file
4. Mid comps   → Write file
5. Wizard      → Write files
6. Pages       → Write file
7. Imports     → Edit files
8. Deletes     → Remove files
9. Typecheck   → Run
```

After each file write, do NOT commit. The whole thing is one commit at the end.

## Typecheck before commit

```bash
cd apps/web && (
  if   [ -f ../../bun.lockb ] || [ -f ../../bun.lock ]; then PM=bun
  elif [ -f ../../pnpm-lock.yaml ];                     then PM=pnpm
  elif [ -f ../../yarn.lock ];                          then PM=yarn
  else                                                       PM=npm
  fi
  $PM run typecheck 2>/dev/null \
    || $PM run type-check 2>/dev/null \
    || $PM run check-types 2>/dev/null \
    || npx -y tsc --noEmit
) || TYPECHECK_FAILED=1
```

If `TYPECHECK_FAILED=1` → ROLLBACK (see next section). Do NOT attempt mid-conversion fixes; the plan was incomplete and needs to re-run.

## Commit (one commit, with body referencing the plan)

```bash
git add -A
git commit -m "$(cat <<EOF
refactor(<feature>): decompose into modular structure

Per CONVERSION_PLAN.md.

- Split <old-file>.tsx (N lines) into pages/ + components/ + stores/ + hooks/
- Extracted <N> state values to Zustand stores
- Wrapped <M> drawers/modals/popovers in shadcn Portal primitives
- Split <K>-step wizard into per-step files under components/create-wizard/
- Updated <P> external consumer imports
- Deleted <Q> old fat files

Behavior contract preserved per BEHAVIOR_BASELINE.md.
To be verified by conversion-verifier (Phase 5).

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

## Rollback protocol

If typecheck fails OR Phase 5 verifier returns REJECT:

```bash
PRE_SHA="$(cat .conversion-pre-sha)"
ORIGINAL_BRANCH="$(git reflog | grep "checkout: moving from .* to refactor/<feature>-decompose" | head -1 | sed 's/.*moving from \([^ ]*\) to.*/\1/')"
ORIGINAL_BRANCH="${ORIGINAL_BRANCH:-main}"

# Save evidence before destroying the branch
mkdir -p .conversion-rejected-$(date +%s)
cp -r current/<feature> .conversion-rejected-$(date +%s)/ 2>/dev/null
cp BEHAVIOR_BASELINE.md CONVERSION_PLAN.md .conversion-rejected-$(date +%s)/ 2>/dev/null

# Roll back
git reset --hard "$PRE_SHA"
git checkout "$ORIGINAL_BRANCH"
git branch -D "refactor/<feature>-decompose"
rm -f .conversion-pre-sha
```

The evidence directory survives — the user (and the re-planner) can inspect exactly what diverged.

## What "atomic" excludes

The atomic commit does NOT include:

- ❌ Other modules' files (cross-module changes are separate dispatches)
- ❌ Dependency bumps (mention in plan, user does separately)
- ❌ shadcn primitives in `apps/web/src/components/ui/*` (vendored)
- ❌ Lint / format-only changes ("while I'm here" cleanup)
- ❌ Test files (test rewriting is its own task — preserve existing tests; if they fail post-conversion, that's the verifier's signal)

If the plan included any of the above, the planner did the wrong thing — surface to the user.

## Branch lifecycle

| State | What's true |
|---|---|
| Before Phase 4 | On original branch, working tree clean, plan + baseline exist |
| Mid Phase 4 (writing files) | On `refactor/<feature>-decompose`, working tree dirty, NO commit yet |
| End of Phase 4 (after typecheck PASS) | One commit on `refactor/<feature>-decompose` |
| Mid Phase 5 (verifying) | Same as above; Playwright running |
| End of Phase 5 PASS | Branch ready to merge; user reviews + merges |
| End of Phase 5 REJECT | Branch deleted; original branch restored; .conversion-rejected-<ts>/ has evidence |

## Why one commit (not many)

The convention `git revert <SHA>` should completely undo the conversion. With ten commits ("stores", "hooks", "wizard", "imports", "delete old", ...) the user has to revert all ten in order, and a half-revert leaves broken state. One commit = one revert = clean undo.

It also means PR review is the entire conversion in one diff — the reviewer sees the whole picture, including the deleted old files alongside the new ones. The relationship between old code and new code is preserved in the patch.
