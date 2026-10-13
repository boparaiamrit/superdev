"""Integrity tests for the superdev plugin (post-conductor-removal end-state).

Run: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import re
import subprocess
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "superdev"
SKILLS = PLUGIN / "skills"
AGENTS = PLUGIN / "agents"

TEXT_SUFFIXES = {".md", ".json", ".sh", ".mjs", ".py"}


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def plugin_text_files() -> list[Path]:
    return sorted(p for p in PLUGIN.rglob("*") if p.is_file() and p.suffix in TEXT_SUFFIXES)


def frontmatter(p: Path) -> dict[str, str]:
    text = read(p)
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    assert m, f"{p} has no YAML frontmatter"
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "-")):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


class ConductorRemovedTests(unittest.TestCase):
    def test_orchestrator_skill_gone_build_skill_present(self) -> None:
        self.assertFalse((SKILLS / "prd-design-build-orchestrator").exists(),
                         "conductor skill must be removed")
        self.assertTrue((SKILLS / "superdev-build" / "SKILL.md").exists(),
                        "lean superdev-build skill must replace it")

    def test_no_install_or_extraction_machinery(self) -> None:
        leftovers = [str(p.relative_to(PLUGIN)) for p in PLUGIN.rglob("install-*-agents.sh")]
        for name in ("qa-agents.md", "security-agents.md", "migration-agents.md", "extract-agent.py"):
            leftovers += [str(p.relative_to(PLUGIN)) for p in PLUGIN.rglob(name)]
        self.assertEqual([], leftovers)

    def test_no_bash_hooks(self) -> None:
        self.assertFalse((PLUGIN / "hooks").exists(),
                         "bash hook machinery must be removed (explicit verify replaces it)")
        self.assertTrue((PLUGIN / "scripts" / "verify-done.mjs").exists())

    def test_no_conductor_or_global_path_references(self) -> None:
        bad: list[str] = []
        for p in plugin_text_files() + [ROOT / "README.md", ROOT / "CODEX.md", ROOT / "INSTALL.md"]:
            if not p.exists():
                continue
            t = read(p)
            for needle in ("prd-design-build-orchestrator", "~/.claude/skills",
                           ".superdev-orchestrating", "CLAUDE_PLUGIN_DIR",
                           "install-core-agents", "install-qa-agents",
                           "install-security-agents", "install-migration-agents"):
                if needle in t:
                    bad.append(f"{p.relative_to(ROOT)}: {needle}")
        self.assertEqual([], bad, "\n" + "\n".join(bad[:30]))

    def test_verify_script_parses(self) -> None:
        script = PLUGIN / "scripts" / "verify-done.mjs"
        res = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
        self.assertEqual(0, res.returncode, res.stderr)


class StructureTests(unittest.TestCase):
    def test_skill_frontmatter_names_match_dirs(self) -> None:
        for d in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
            fm = frontmatter(d / "SKILL.md")
            self.assertEqual(d.name, fm.get("name"), f"{d.name}/SKILL.md name mismatch")
            self.assertTrue(fm.get("description"), f"{d.name} missing description")

    def test_agent_frontmatter_names_match_files(self) -> None:
        for p in sorted(AGENTS.glob("*.md")):
            fm = frontmatter(p)
            self.assertEqual(p.stem, fm.get("name"), f"{p.name} name mismatch")

    def test_relative_links_in_skills_resolve(self) -> None:
        broken: list[str] = []
        for skill_md in SKILLS.rglob("SKILL.md"):
            for target in re.findall(r"\]\(([^)]+)\)", read(skill_md)):
                target = target.split("#")[0].strip()
                if not target or target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                if not (skill_md.parent / target).resolve().exists():
                    broken.append(f"{skill_md.relative_to(ROOT)} -> {target}")
        self.assertEqual([], broken, "\n" + "\n".join(broken[:30]))

    def test_manifests_agree_and_counts_match_disk(self) -> None:
        claude_manifest = json.loads(read(PLUGIN / ".claude-plugin" / "plugin.json"))
        codex_manifest = json.loads(read(PLUGIN / ".codex-plugin" / "plugin.json"))
        self.assertEqual(claude_manifest["version"], codex_manifest["version"])
        n_skills = len([p for p in SKILLS.iterdir() if p.is_dir()])
        n_agents = len(list(AGENTS.glob("*.md")))
        for label, text in (("claude plugin.json", claude_manifest["description"]),
                            ("codex plugin.json", codex_manifest["description"]),
                            ("README.md", read(ROOT / "README.md")),
                            ("plugin README.md", read(PLUGIN / "README.md"))):
            ms = re.search(r"(\d+)\s+skills", text)
            ma = re.search(r"(\d+)\s+(?:specialized\s+)?(?:sub)?agents", text)
            self.assertIsNotNone(ms, f"{label}: no skill count stated")
            self.assertIsNotNone(ma, f"{label}: no agent count stated")
            self.assertEqual(n_skills, int(ms.group(1)), f"{label}: skill count stale")
            self.assertEqual(n_agents, int(ma.group(1)), f"{label}: agent count stale")

    def test_zip_matches_plugin_tree(self) -> None:
        zpath = ROOT / "superdev.zip"
        self.assertTrue(zpath.exists())
        with zipfile.ZipFile(zpath) as z:
            names = {n.replace("\\", "/").lstrip("./") for n in z.namelist() if not n.endswith("/")}
        on_disk = {str(p.relative_to(PLUGIN)).replace("\\", "/")
                   for p in PLUGIN.rglob("*") if p.is_file()}
        # zip may use a top-level folder prefix; normalize by stripping it if present
        if names and not names & on_disk:
            prefix = sorted(names)[0].split("/")[0] + "/"
            names = {n[len(prefix):] if n.startswith(prefix) else n for n in names}
        self.assertEqual(on_disk, names,
                         f"zip drift: only-disk={sorted(on_disk - names)[:10]} only-zip={sorted(names - on_disk)[:10]}")


class HardLearnedRulesTests(unittest.TestCase):
    def test_nestjs_recipes_do_not_teach_patch_nestjs_swagger(self) -> None:
        # Mentions in warnings are fine; an executable call or import is not.
        call = re.compile(r"^\s*patchNestJsSwagger\(\);|import\s*\{[^}]*patchNestJsSwagger", re.M)
        offenders = [str(p.relative_to(ROOT)) for p in (SKILLS / "nestjs-enterprise-backend").rglob("*.md")
                     if call.search(read(p))]
        self.assertEqual([], offenders)

    def test_hard_rules_cover_the_recurring_failures(self) -> None:
        hard = read(SKILLS / "superdev-build" / "references" / "hard-rules.md")
        for needle in ("node apps/api/dist/main.js", "patchNestJsSwagger", "CommonJS",
                       "audit_log", "base-nova", "contracts"):
            self.assertIn(needle, hard, f"hard-rules.md must cover: {needle}")


if __name__ == "__main__":
    unittest.main()
