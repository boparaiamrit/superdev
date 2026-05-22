# Verbatim copy rules

The `design-source-mirror` agent follows these rules without exception.

## Allowed during copy

- Skip OS metadata files: `.DS_Store`, `Thumbs.db`, `desktop.ini`, `__MACOSX/`
- Follow symlinks (`cp -RL`) so the mirror is self-contained
- Preserve file permissions and timestamps (`cp -p`)
- Create intermediate directories as needed

## FORBIDDEN during copy

- ❌ Renaming files (even normalizing case)
- ❌ Reformatting HTML / "prettifying" with Prettier
- ❌ Linting / fixing CSS warnings
- ❌ Bundling / minifying JS or CSS
- ❌ Converting image formats (`.jpg` → `.webp`, raster → SVG)
- ❌ Stripping HTML comments — they may be design notes
- ❌ Removing inline styles "since we'll use Tailwind anyway"
- ❌ Normalizing line endings (CRLF ↔ LF)
- ❌ Re-encoding text files (UTF-8 BOM ↔ no BOM)

## Verification

After copy, the byte-for-byte invariant is verified with:

```bash
diff -r <source> apps/web/src/design-source/
# Exit code 0 = identical
# Any output = failed copy; diagnose
```

If `diff -r` is unavailable (Windows native), use:

```bash
# Compute checksums of every file, compare
( cd <source> && find . -type f -exec sha256sum {} \; | sort ) > /tmp/src.sha
( cd apps/web/src/design-source && find . -type f -exec sha256sum {} \; | sort ) > /tmp/mirror.sha
diff /tmp/src.sha /tmp/mirror.sha
```

## What happens if the source has issues?

The source HTML may have:
- ❌ Hardcoded `http://localhost:3000/...` absolute URLs
- ❌ Bare `<script>` tags expecting global libraries
- ❌ Inline JavaScript with errors
- ❌ Browser-specific CSS

**You do NOT fix these.** You preserve them. The user explicitly wants the source preserved as-is.

If a source defect prevents the mirror from rendering correctly (e.g. broken JS that makes the page blank), surface it as a finding:

```
Mirror at /companies renders blank because design-source/companies.html line 14
references missing script 'companies-init.js'. NOT modifying. Surface to user
for direction.
```

Let the user decide: provide the missing asset, mark it as a known issue, or
authorize a documented exception (which goes in DESIGN_DEVIATIONS.md).
