"""Build superdev.zip from plugins/superdev/, or check an existing archive against the tree.

    python tools/build_zip.py [--out PATH] [--check]

The archive is deterministic: entries are sorted by path, carry a fixed timestamp and fixed
permissions, are named superdev/<path inside plugins/superdev> with forward slashes, and hold text
files with LF line endings. --check builds the archive into a temporary file and compares it with the
existing one entry by entry (names and bytes, not archive bytes, which differ between zlib builds).
Python 3.9 or newer, standard library only.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "superdev"
SKIPPED_DIRS = {"__pycache__"}
SKIPPED_NAMES = {".DS_Store", "Thumbs.db"}
TEXT_SUFFIXES = {".md", ".json", ".mjs", ".js", ".sh", ".py", ".txt", ".yml", ".yaml", ".toml"}


def expected_entries() -> dict[str, bytes]:
    """Entry name to content for every file of the tree, in archive order (sorted by POSIX path)."""
    entries: dict[str, bytes] = {}
    for path in sorted(PLUGIN.rglob("*"), key=lambda p: p.relative_to(PLUGIN).as_posix()):
        relative = path.relative_to(PLUGIN)
        if not path.is_file() or path.name in SKIPPED_NAMES or SKIPPED_DIRS & set(relative.parts):
            continue
        data = path.read_bytes()
        entries[f"superdev/{relative.as_posix()}"] = data.replace(b"\r\n", b"\n") if path.suffix in TEXT_SUFFIXES else data
    return entries


def build(out: Path) -> int:
    entries = expected_entries()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    return len(entries)


def check(existing: Path) -> int:
    if not existing.is_file():
        print(f"{existing} does not exist; build it with: python tools/build_zip.py")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        build(Path(tmp) / "superdev.zip")
        with zipfile.ZipFile(Path(tmp) / "superdev.zip") as fresh, zipfile.ZipFile(existing) as old:
            built = {i.filename: fresh.read(i) for i in fresh.infolist()}
            found = {i.filename: old.read(i) for i in old.infolist()}
    problems = [f"missing from the archive: {n}" for n in built if n not in found]
    problems += [f"not in the tree: {n}" for n in found if n not in built]
    problems += [f"content differs: {n}" for n in built if n in found and built[n] != found[n]]
    print("\n".join(problems) if problems else f"{existing.name} matches plugins/superdev")
    if problems:
        print(f"{existing.name} is out of date ({len(problems)} difference(s)); rebuild it with: python tools/build_zip.py")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build superdev.zip from plugins/superdev/ or check it against the tree.")
    parser.add_argument("--out", type=Path, default=ROOT / "superdev.zip",
                        help="archive to write, or to compare with when --check is given (default: superdev.zip at the repository root)")
    parser.add_argument("--check", action="store_true", help="compare the existing archive with the tree; exit 1 on any difference")
    args = parser.parse_args(argv)
    if not PLUGIN.is_dir():
        print(f"{PLUGIN} not found", file=sys.stderr)
        return 2
    if args.check:
        return check(args.out)
    print(f"wrote {args.out}: {build(args.out)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
