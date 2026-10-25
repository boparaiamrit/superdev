"""Integrity tests for the superdev plugin (post-conductor-removal end-state).

Run: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import re
import shutil
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

    @unittest.skipUnless(shutil.which("node"), "node not on PATH in this environment")
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
                       "audit_log", "base-nova", "contracts", "pg_advisory_xact_lock",
                       "Idempotency-Key", "same transaction", "adb", "session row"):
            self.assertIn(needle, hard, f"hard-rules.md must cover: {needle}")


class PublicGuidanceTests(unittest.TestCase):
    def test_hard_rules_have_scope_and_verification(self) -> None:
        hard = read(SKILLS / "superdev-build" / "references" / "hard-rules.md")
        rules = re.findall(r"^### (\d+)\. (.*?)(?=^### |^## |\Z)", hard, re.M | re.S)
        self.assertEqual(list(range(1, 19)), [int(number) for number, _ in rules])
        for number, rule in rules:
            with self.subTest(rule=number):
                self.assertIn("**Scope:**", rule)
                self.assertIn("**Verify:**", rule)

    def test_public_guidance_has_no_case_study_attribution(self) -> None:
        paths = [ROOT / "README.md", PLUGIN / "README.md", ROOT / "CHANGELOG.md",
                 SKILLS / "superdev-build" / "SKILL.md",
                 SKILLS / "superdev-build" / "references" / "hard-rules.md",
                 SKILLS / "superdev-self-learning" / "SKILL.md"]
        attribution = re.compile(
            r"projects built with it\s*\(|learned on [A-Z][\w-]+|"
            r"\b\d+ (?:unit|audit decorators)|\bWave \d+,", re.M)
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(attribution.search(read(path)))

    def test_hard_rule_domains_are_generic(self) -> None:
        hard = read(SKILLS / "superdev-build" / "references" / "hard-rules.md")
        domains = re.findall(r"\b(?:[a-z0-9-]+\.)+(?:com|org|net|io)\b", hard, re.I)
        for domain in domains:
            self.assertIn(domain.lower(), {"example.com", "example.org", "example.net"})


class ClientsSecurityQaTests(unittest.TestCase):
    """v2.1: Tauri clients, the build-time security layer, and the release QA gate."""

    NEW_SKILLS = ("design-to-tauri", "security-foundation", "release-qa-gate")
    NEW_AGENTS = ("mobile-qa-tester", "a11y-contrast-auditor", "role-matrix-tester",
                  "money-integrity-prober", "realtime-prober", "link-crawler")

    def test_new_skills_and_agents_exist(self) -> None:
        for name in self.NEW_SKILLS:
            with self.subTest(skill=name):
                fm = frontmatter(SKILLS / name / "SKILL.md")
                self.assertTrue(fm["description"].startswith("Use when"),
                                f"{name}: description must state when to use it")
        for name in self.NEW_AGENTS:
            with self.subTest(agent=name):
                self.assertTrue((AGENTS / f"{name}.md").exists())

    def test_build_skill_wires_clients_security_and_qa(self) -> None:
        build = read(SKILLS / "superdev-build" / "SKILL.md")
        for needle in ("design-to-tauri", "security-foundation", "release-qa-gate", "clients", "--suites"):
            self.assertIn(needle, build, f"superdev-build must reference {needle}")

    def test_security_foundation_covers_the_controls(self) -> None:
        refs = SKILLS / "security-foundation" / "references"
        text = "\n".join(read(p) for p in refs.glob("*.md"))
        for needle in ("every request", "reuse", "recovery codes", "WebAuthn", "masked",
                       "escalation", "pg_advisory_xact_lock", "Idempotency-Key", "pg_notify",
                       "test:security"):
            self.assertIn(needle, text, f"security-foundation must cover: {needle}")

    def test_release_gate_requires_cited_evidence(self) -> None:
        gate = read(SKILLS / "release-qa-gate" / "SKILL.md")
        for needle in ("QA_COVERAGE.md", "NOT RUN", "contrast", "dead", "role", "device", "--strict", "db:fresh"):
            self.assertIn(needle, gate)

    def test_release_gate_names_an_owner_for_every_dimension(self) -> None:
        gate = read(SKILLS / "release-qa-gate" / "SKILL.md")
        for agent in (*self.NEW_AGENTS, "qa-flow-tester", "qa-consistency-checker", "qa-performance-prober"):
            with self.subTest(agent=agent):
                self.assertIn(f"`{agent}`", gate)
                self.assertTrue((AGENTS / f"{agent}.md").exists())

    def test_build_defines_the_fresh_seed_the_gate_uses(self) -> None:
        build = read(SKILLS / "superdev-build" / "SKILL.md")
        for needle in ("db:seed", "db:fresh", "--strict"):
            self.assertIn(needle, build)

    def test_stack_recipes_defer_identity_to_security_foundation(self) -> None:
        for path in (SKILLS / "nestjs-enterprise-backend" / "references" / "auth-casl.md",
                     SKILLS / "nestjs-enterprise-backend" / "SKILL.md",
                     SKILLS / "laravel-enterprise-backend" / "SKILL.md",
                     SKILLS / "design-to-nextjs" / "SKILL.md"):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("security-foundation", read(path))


@unittest.skipUnless(shutil.which("node"), "node not on PATH in this environment")
class VerifyDoneTauriTests(unittest.TestCase):
    """Behavioural: the shell checks fail an open Tauri config and pass a locked-down one."""

    LOCKED_CONF = {"app": {"security": {"csp": {"default-src": "'self'"}}}}
    STRIPPED_CARGO = '[dependencies]\ntauri = { version = "2", features = [] }\n\n[profile.release]\nstrip = true\n'

    def run_on(self, conf: dict, capability: dict, cargo: str, *extra: str) -> subprocess.CompletedProcess[str]:
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = Path(tmp.name) / "apps" / "mobile"
        tauri = app / "src-tauri"
        (tauri / "capabilities").mkdir(parents=True)
        (app / "package.json").write_text('{"name": "mobile", "scripts": {}}', encoding="utf-8")
        (tauri / "tauri.conf.json").write_text(json.dumps(conf), encoding="utf-8")
        (tauri / "capabilities" / "default.json").write_text(json.dumps(capability), encoding="utf-8")
        (tauri / "Cargo.toml").write_text(cargo, encoding="utf-8")
        return subprocess.run(["node", str(PLUGIN / "scripts" / "verify-done.mjs"), "--root", tmp.name,
                               "--skip-build", "--skip-boot", *extra],
                              capture_output=True, text=True, encoding="utf-8", timeout=120)

    @staticmethod
    def http(*urls: str) -> dict:
        return {"identifier": "default",
                "permissions": [{"identifier": "http:default", "allow": [{"url": u} for u in urls]}]}

    def test_open_shell_fails(self) -> None:
        res = self.run_on({"app": {"security": {"csp": None}}},
                          {"permissions": [{"identifier": "http:default", "allow": [{"url": "https://*"}]}]},
                          '[dependencies]\ntauri = { version = "2", features = ["devtools"] }\n')
        self.assertEqual(1, res.returncode, res.stdout)
        for needle in ("CSP", "HTTP capability scope", "devtools"):
            self.assertIn(needle, res.stdout)

    def test_locked_down_shell_passes(self) -> None:
        res = self.run_on({"app": {"security": {"csp": {"default-src": "'self'"}}}},
                          {"permissions": [{"identifier": "http:default", "allow": [{"url": "https://api.example.com/*"}]}]},
                          '[dependencies]\ntauri = { version = "2", features = [] }\n')
        self.assertEqual(0, res.returncode, res.stdout)
        self.assertIn("CSP set", res.stdout)

    def test_host_wildcards_and_remote_cleartext_fail(self) -> None:
        for url in ("https://*.example.com/*", "http://*:4100/*", "*"):
            with self.subTest(url=url):
                res = self.run_on(self.LOCKED_CONF, self.http(url), self.STRIPPED_CARGO)
                self.assertEqual(1, res.returncode, res.stdout)
                self.assertIn("[FAIL]", res.stdout)
        res = self.run_on(self.LOCKED_CONF, self.http("http://api.example.com/*"), self.STRIPPED_CARGO)
        self.assertEqual(1, res.returncode, res.stdout)
        self.assertIn("cleartext API origin", res.stdout)

    def test_opener_scope_may_use_https_wildcard(self) -> None:
        cap = self.http("https://api.example.com/*")
        cap["permissions"].append({"identifier": "opener:allow-open-url", "allow": [{"url": "https://*"}]})
        res = self.run_on(self.LOCKED_CONF, cap, self.STRIPPED_CARGO)
        self.assertEqual(0, res.returncode, res.stdout)

    def test_csp_without_default_src_or_with_any_origin_fails(self) -> None:
        for csp in ({}, {"script-src": "'self'"}, "default-src 'self'; connect-src 'self' https:"):
            with self.subTest(csp=csp):
                res = self.run_on({"app": {"security": {"csp": csp}}}, self.http("https://api.example.com/*"),
                                  self.STRIPPED_CARGO)
                self.assertEqual(1, res.returncode, res.stdout)
                self.assertIn("CSP", res.stdout)

    def test_devtools_in_a_dependency_table_fails(self) -> None:
        res = self.run_on(self.LOCKED_CONF, self.http("https://api.example.com/*"),
                          '[dependencies.tauri]\nversion = "2"\nfeatures = ["devtools"]\n')
        self.assertEqual(1, res.returncode, res.stdout)
        self.assertIn("devtools", res.stdout)

    def test_debug_origins_in_release_warn_and_fail_strict(self) -> None:
        cap = self.http("https://api.example.com/*", "http://10.0.2.2:4100/*")
        res = self.run_on(self.LOCKED_CONF, cap, self.STRIPPED_CARGO)
        self.assertEqual(0, res.returncode, res.stdout)
        self.assertIn("[WARN]", res.stdout)
        self.assertIn("not a release claim", res.stdout)
        strict = self.run_on(self.LOCKED_CONF, cap, self.STRIPPED_CARGO, "--strict")
        self.assertEqual(1, strict.returncode, strict.stdout)
        self.assertIn("NOT DONE (--strict)", strict.stdout)

    def test_debug_origins_outside_the_release_set_are_fine(self) -> None:
        conf = {"app": {"security": {"csp": {"default-src": "'self'"}, "capabilities": ["release-only"]}}}
        cap = self.http("http://10.0.2.2:4100/*")  # identifier "default" is not in the release list
        res = self.run_on(conf, cap, self.STRIPPED_CARGO)
        self.assertEqual(0, res.returncode, res.stdout)
        self.assertNotIn("debug origins", res.stdout)


if __name__ == "__main__":
    unittest.main()
