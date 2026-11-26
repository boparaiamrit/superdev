"""Integrity tests for the superdev plugin: names, counts, frontmatter, hard rules, vocabulary, links, package.

Run: python -m unittest discover -s tests -v

Names are typed here (they are the contract); counts are read from disk. Files are read as UTF-8 and
their line endings are made LF, so the tests give the same result on Linux, macOS and Windows.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "superdev"
SKILLS = PLUGIN / "skills"
AGENTS = PLUGIN / "agents"
SCRIPT = PLUGIN / "scripts" / "verify-done.mjs"
HARD_RULES = SKILLS / "superdev-build" / "references" / "hard-rules.md"
CLAUDE_MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
CODEX_MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
CLAUDE_MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
CODEX_MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"

EXPECTED_SKILLS = {
    "superdev-build", "superdev-done", "superdev-self-learning", "architecture-governance", "backend-on-navree",
    "security-foundation", "design-to-navree-ui", "design-preservation", "design-to-nextjs", "frontend-structure",
    "prototype-to-navree", "design-to-tauri", "security-review-and-fix", "product-audit", "product-qa",
    "systematic-debugging",
}
EXPECTED_REFERENCES = {
    "superdev-build": {"artifacts.md", "hard-rules.md", "deploy-checklist.md"},
    "superdev-done": set(),
    "superdev-self-learning": {"memory-entry-format.md"},
    "architecture-governance": {"scaling-and-workers.md", "stories-and-srp.md"},
    "backend-on-navree": set(),
    "security-foundation": {"staff-and-personal-data.md", "money-and-ledgers.md", "live-updates.md", "security-suites.md"},
    "design-to-navree-ui": set(),
    "design-preservation": {"drift-check.md"},
    "design-to-nextjs": set(),
    "frontend-structure": {"refactor-plan.md"},
    "prototype-to-navree": {"prototype-artifacts.md"},
    "design-to-tauri": {"security.md", "device-qa.md"},
    "security-review-and-fix": {"static-checks.md", "dynamic-probes.md", "fix-plan-format.md"},
    "product-audit": {"rubric.md", "completeness-checks.md"},
    "product-qa": {"coverage-matrix.md", "ui-sweeps.md", "explore-checklist.md"},
    "systematic-debugging": {"repro-and-instrumentation.md"},
}
EXPECTED_AGENTS = {
    "a11y-contrast-auditor", "bug-reproducer", "codebase-discoverer", "data-source-auditor", "dependency-auditor",
    "design-inventory", "dynamic-auditor", "fix-applier", "gap-auditor", "hypothesis-tester", "journey-walker",
    "lesson-writer", "link-crawler", "migration-planner", "mobile-qa-tester", "module-readiness-rater",
    "module-structure-auditor", "money-integrity-prober", "navree-app-bootstrapper", "navree-module-builder",
    "navree-ui-screen-builder", "nextjs-module-builder", "placeholder-hunter", "plan-architect", "prd-analyst",
    "qa-consistency-checker", "qa-environment", "qa-flow-tester", "qa-performance-prober", "realtime-prober",
    "refactor-planner", "regression-verifier", "repo-cartographer", "role-matrix-tester", "root-cause-investigator",
    "schema-reverse-engineer", "seed-data-architect", "static-auditor", "tenancy-isolation-tester", "ui-auditor",
    "visual-diff-auditor",
}
EXPECTED_HARD_RULES = 30
GATE_AGENTS = (
    "qa-flow-tester", "link-crawler", "a11y-contrast-auditor", "qa-consistency-checker", "role-matrix-tester",
    "money-integrity-prober", "realtime-prober", "mobile-qa-tester", "qa-performance-prober",
)
NAVREE_SKILLS = {
    "navree", "navree-new-app", "navree-modules-and-di", "navree-controllers-and-routing", "navree-validation",
    "navree-errors-and-responses", "navree-orm", "navree-migrations", "navree-database", "navree-auth",
    "navree-access-control", "navree-queues-and-scheduling", "navree-events-and-broadcasting",
    "navree-mail-and-notifications", "navree-mail-delivery", "navree-inbound-mail", "navree-notification-channels",
    "navree-notification-preferences", "navree-storage", "navree-cache-and-http-client", "navree-openapi",
    "navree-frontend-next", "navree-frontend-nuxt", "navree-config", "navree-testing", "navree-cli-generators",
    "navree-deployment", "navree-security-checklist", "navree-jose", "navree-module-conformity", "navree-workspaces",
    "navree-time-zones", "navree-billing", "navree-lighthouse", "navree-fleet", "navree-dock", "navree-harbor",
    "navree-social", "navree-sso", "navree-oauth", "navree-webhooks", "navree-integrations", "navree-directory",
    "navree-custom-domains", "navree-flags", "navree-settings", "navree-search", "navree-telemetry", "navree-graphql",
    "navree-grpc", "navree-mcp", "navree-ai", "navree-redis", "navree-logbook", "navree-microservices", "navree-helm",
    "navree-navigator", "navree-i18n", "navree-browser-testing", "navree-performance", "navree-documents",
    "navree-media", "navree-sheets", "navree-workflows", "navree-reverse-engineering", "navree-design-to-ui",
    "navree-ui", "navree-native", "navree-native-design", "navree-native-apple", "navree-native-android",
}
REMOVED_SKILLS = (
    "nestjs-enterprise-backend", "laravel-enterprise-backend", "design-to-laravel", "laravel-bref-deploy",
    "frontend-modular-architecture", "frontend-refactoring", "prototype-to-saas", "brutal-exhaustive-audit",
    "product-completeness-audit", "production-readiness-audit", "exploratory-qa", "release-qa-gate",
)
REMOVED_AGENTS = (
    # deleted
    "laravel-module-builder", "inertia-module-builder", "atomic-module-converter", "audit-synthesizer",
    "backend-extractor", "backend-module-builder", "contracts-author", "conversion-verifier", "data-flow-tracer",
    "design-source-mirror", "edge-case-prober", "flow-walker", "frontend-module-builder", "frontend-rewirer",
    "integration-tester", "module-behavior-snapshotter", "monorepo-bootstrapper", "portal-correctness-auditor",
    "route-completeness-checker", "route-walker", "security-fixer", "security-inventory", "wiring-auditor",
    # old names of renamed agents
    "data-flow-real-vs-mock", "learn-from-frustration", "module-conversion-planner", "design-fidelity-auditor",
)
OLD_ARTIFACTS = (
    "AUDIT.md", "SECURITY_INVENTORY.md", "SECURITY_FINDINGS.md", "SECURITY_FIX_PLAN.md", "READINESS.md",
    "READINESS_CHECKLIST.md", "COMPLETENESS_REPORT.md", "QA_ENVIRONMENT.md", "QA_CONSISTENCY.md", "QA_PERFORMANCE.md",
    "MAP.md", "INVENTORY.md", "CONVERSION_PLAN.md", "EXTRACTED_CONTRACTS.md", "FIDELITY_BASELINE.md", "SEED.md",
    "last-audit-counts.md", "packages/contracts", "db:fresh", "test:security", "test:contract",
)
# `db:seed` is also Navree's own command (navree db:seed); only its use as a package script is old.
OLD_PACKAGE_SEED = re.compile(r'(?:\b(?:pnpm|npm|yarn|bun)(?: run)? db:seed\b|"db:seed"\s*:)')
OLD_STACK = re.compile(
    r"NestJS|Nest\.js|nestjs|Laravel|Inertia|Bref|Sanctum|Eloquent|Fortify|Drizzle|CASL|BullMQ|Zustand|"
    r"patchNestJsSwagger|Turborepo|InboxKit|Acme|Meridian"
)
RULE_PREFIXES = "BLD GOV BE SEC NUI PRE NX FS PRO TAU SR AUD QA DBG LRN".split()
AGENT_TOOLS = {"Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebFetch"}
OUTSIDE_NAVREE_SKILLS = {"superdev-build", "superdev-done", "superdev-self-learning"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def plugin_text_files() -> list[Path]:
    return sorted(p for p in PLUGIN.rglob("*")
                  if p.is_file() and p.suffix in {".md", ".json", ".mjs"} and "__pycache__" not in p.parts)


def doc_files() -> list[Path]:
    return [p for p in (ROOT / "README.md", ROOT / "INSTALL.md", ROOT / "CODEX.md", CLAUDE_MARKETPLACE, CODEX_MARKETPLACE) if p.exists()]


def scanned() -> list[Path]:
    return plugin_text_files() + doc_files()


def skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS.iterdir() if p.is_dir())


def agent_files() -> list[Path]:
    return sorted(AGENTS.glob("*.md"))


def frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    """Top-level `key: value` pairs of the frontmatter, and every other line (continuations, indented lines)."""
    m = re.match(r"---\n(.*?)\n---\n", read(path), re.S)
    assert m, f"{path.relative_to(ROOT)} has no frontmatter"
    keys: dict[str, str] = {}
    other: list[str] = []
    for line in m.group(1).split("\n"):
        km = re.match(r"([A-Za-z0-9_-]+):(?: (.*))?$", line)
        if km:
            keys[km.group(1)] = (km.group(2) or "").strip()
        else:
            other.append(line)
    return keys, other


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def yaml_problems(block: str) -> list[str]:
    """Why a flat frontmatter block is not valid YAML, or [] when it is.

    The built-in rules cover the failures a plain `key: value` header can have: a colon followed by a space
    inside a plain value ("mapping values are not allowed here"), a ` #` that starts a comment, a value that
    starts with a YAML indicator, a malformed quoted value, a duplicate key, or a line that is not a key. When
    PyYAML is installed its parser must accept the block too and read every value as text.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for line in block.split("\n"):
        m = re.match(r"([A-Za-z0-9_-]+):(?: (.*))?$", line)
        if not m:
            problems.append(f"not a key: value line: {line[:60]!r}")
            continue
        key, value = m.group(1), (m.group(2) or "").strip()
        if key in seen:
            problems.append(f"duplicate key {key}")
        seen.add(key)
        if value[:1] == '"' and not re.fullmatch(r'"(?:[^"\\]|\\.)*"\s*(?:#.*)?', value):
            problems.append(f"{key}: malformed double-quoted value")
        elif value[:1] == "'" and not re.fullmatch(r"'(?:[^']|'')*'\s*(?:#.*)?", value):
            problems.append(f"{key}: malformed single-quoted value")
        elif value[:1] not in {'"', "'"}:
            if value[:1] in set("[]{},&*!|>%@`#"):
                problems.append(f"{key}: a plain value cannot start with {value[:1]!r}")
            if ": " in value or value.endswith(":"):
                problems.append(f"{key}: a colon followed by a space inside a plain value (mapping values are not allowed here)")
            if " #" in value:
                problems.append(f"{key}: ' #' starts a comment inside a plain value")
    try:
        import yaml
    except ImportError:
        return problems
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as error:
        return problems + [f"PyYAML: {str(error).splitlines()[0]}"]
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        problems.append("PyYAML: every value must be read as text")
    return problems


def markdown_links(text: str) -> list[str]:
    """Link targets of a Markdown text, ignoring fenced code and inline code."""
    text = re.sub(r"^[ \t]*(```|~~~).*?^[ \t]*\1[^\n]*$", "", text, flags=re.S | re.M)
    text = re.sub(r"`[^`\n]*`", "", text)
    return [m.group(1).strip("<>") for m in re.finditer(r"\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text)]


def hard_rules() -> list[tuple[int, str]]:
    text = read(HARD_RULES)
    return [(int(n), body) for n, body in re.findall(r"^### (\d+)\. (.*?)(?=^### |^## |\Z)", text, re.M | re.S)]


def name_pattern(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")


class StructureTests(unittest.TestCase):
    def test_skill_directories_equal_the_expected_set(self) -> None:
        self.assertEqual(EXPECTED_SKILLS, {p.name for p in skill_dirs()})
        for name in EXPECTED_SKILLS:
            self.assertTrue((SKILLS / name / "SKILL.md").is_file(), f"{name}/SKILL.md")

    def test_every_frontmatter_block_is_valid_yaml(self) -> None:
        blocks = {md: re.match(r"---\n(.*?)\n---\n", read(md), re.S) for md in sorted(PLUGIN.rglob("*.md")) if read(md).startswith("---\n")}
        self.assertGreaterEqual(len(blocks), len(EXPECTED_SKILLS) + len(EXPECTED_AGENTS))
        for md, m in blocks.items():
            with self.subTest(file=rel(md)):
                self.assertIsNotNone(m, "the frontmatter block is never closed")
                self.assertEqual([], yaml_problems(m.group(1)))

    def test_the_yaml_check_refuses_what_breaks_a_header(self) -> None:
        good = "name: x\ndescription: Use when a, b and c. Dispatched by y (step 2).\ntools: Read, Grep\nmodel: inherit"
        self.assertEqual([], yaml_problems(good))
        for bad in ("description: Use when it is: a trap", "description: Use when it ends with:", "description: Use when a #hash comment",
                    "description: [a, b", 'description: "open', "description: *alias", "description one\nname: x", "name: x\nname: y"):
            with self.subTest(block=bad):
                self.assertNotEqual([], yaml_problems(bad))

    def test_link_extraction_skips_code_spans_and_fenced_blocks(self) -> None:
        text = "See [a](a.md) and `[b](b.md)`.\n\n```\n[c](c.md)\n```\n\n  ~~~md\n[d](d.md)\n  ~~~\n\n[e](e.md#top)\n"
        self.assertEqual(["a.md", "e.md#top"], markdown_links(text))

    def test_skill_frontmatter(self) -> None:
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                keys, other = frontmatter(d / "SKILL.md")
                self.assertEqual({"name", "description"}, set(keys), "exactly the keys name and description")
                self.assertEqual(d.name, keys["name"])
                description = keys["description"]
                self.assertEqual([], other, "the description is one line")
                self.assertNotIn(description, {">", "|", ">-", "|-"}, "the description is one line")
                self.assertTrue(description.startswith("Use when"), description)
                self.assertLessEqual(len(description), 500)
                self.assertFalse({"<", ">"} & set(description), "no angle brackets in a description")

    def test_reference_files_equal_the_expected_set_and_are_linked(self) -> None:
        for name, expected in EXPECTED_REFERENCES.items():
            with self.subTest(skill=name):
                folder = SKILLS / name
                refs = folder / "references"
                actual = {p.name for p in refs.rglob("*") if p.is_file()} if refs.exists() else set()
                self.assertEqual(expected, actual)
                self.assertEqual({"SKILL.md"} | ({"references"} if expected else set()), {p.name for p in folder.iterdir()},
                                 "a skill folder holds SKILL.md and references/ only")
                linked = {(folder / target.split("#")[0]).resolve() for target in markdown_links(read(folder / "SKILL.md"))
                          if not target.startswith(("http://", "https://", "#", "mailto:"))}
                for ref in expected:
                    self.assertIn((refs / ref).resolve(), linked, f"SKILL.md links references/{ref}")

    def test_agents_equal_the_expected_set(self) -> None:
        self.assertEqual(EXPECTED_AGENTS, {p.stem for p in agent_files()})
        self.assertEqual([], [p.name for p in AGENTS.iterdir() if p.suffix != ".md"])

    def test_agent_frontmatter_and_sections(self) -> None:
        for path in agent_files():
            with self.subTest(agent=path.stem):
                keys, other = frontmatter(path)
                self.assertEqual({"name", "description", "tools", "model"}, set(keys), "exactly name, description, tools and model")
                self.assertEqual([], other, "name, description, tools and model are one line each")
                self.assertEqual(path.stem, keys["name"])
                self.assertEqual("inherit", keys["model"])
                tools = [t.strip() for t in keys["tools"].split(",")]
                self.assertTrue(tools and set(tools) <= AGENT_TOOLS, f"tools {tools}")
                description = keys["description"]
                self.assertLessEqual(len(description.split()), 60, "a description is at most 60 words")
                self.assertFalse({"<", ">"} & set(description))
                self.assertIn("Dispatched by", description)
                self.assertTrue(re.split(r"(?<=\.) ", description)[-1].startswith("Dispatched by"),
                                "the description ends with its Dispatched by sentence")
                text = read(path)
                headings = [h for h in re.findall(r"^## (.+)$", text, re.M) if h in {"Inputs", "Steps", "Output", "Limits", "Return"}]
                self.assertIn(headings, (["Inputs", "Steps", "Output", "Return"], ["Inputs", "Steps", "Output", "Limits", "Return"]),
                              "the sections are Inputs, Steps, Output, an optional Limits, Return")
                self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text, "callers pass absolute paths to agents")

    def test_every_agent_is_named_in_backticks_by_a_skill(self) -> None:
        skills_text = "\n".join(read(p) for p in SKILLS.rglob("*.md"))
        for name in sorted(EXPECTED_AGENTS):
            with self.subTest(agent=name):
                self.assertIn(f"`{name}`", skills_text, "nothing dispatches this agent")

    def test_an_agent_that_names_an_output_file_can_write_it(self) -> None:
        for path in agent_files():
            with self.subTest(agent=path.stem):
                output = re.search(r"^## Output\n(.*?)(?=^## |\Z)", read(path), re.M | re.S)
                self.assertIsNotNone(output)
                if re.search(r"[\w./<>{}-]+\.(?:md|txt|json)\b", output.group(1)):
                    keys, _ = frontmatter(path)
                    self.assertIn("Write", [t.strip() for t in keys["tools"].split(",")])

    def test_relative_links_resolve(self) -> None:
        broken: list[str] = []
        for md in sorted(PLUGIN.rglob("*.md")):
            for target in markdown_links(read(md)):
                target = target.split("#")[0]
                if not target or target.startswith(("http://", "https://", "mailto:")) or "${" in target:
                    continue
                if not (md.parent / target).resolve().exists():
                    broken.append(f"{rel(md)} -> {target}")
        self.assertEqual([], broken, "\n" + "\n".join(broken[:30]))

    def test_plugin_layout(self) -> None:
        self.assertFalse((PLUGIN / "hooks").exists(), "the plugin has no hooks")
        self.assertTrue(SCRIPT.is_file())
        self.assertEqual({".claude-plugin", ".codex-plugin", "README.md", "agents", "scripts", "skills"},
                         {p.name for p in PLUGIN.iterdir()})
        self.assertEqual(["verify-done.mjs"], [p.name for p in (PLUGIN / "scripts").iterdir()])
        self.assertFalse((ROOT / "docs" / "superpowers").exists())

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH; the syntax check of verify-done.mjs needs it")
    def test_verify_script_parses(self) -> None:
        res = subprocess.run(["node", "--check", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(0, res.returncode, res.stderr)


class VersionAndCountTests(unittest.TestCase):
    def changelog_version(self) -> str:
        m = re.search(r"^## v(\d+\.\d+\.\d+) — ", read(ROOT / "CHANGELOG.md"), re.M)
        self.assertIsNotNone(m, "CHANGELOG.md starts with a heading `## vX.Y.Z — date`")
        return m.group(1)

    def test_versions_agree(self) -> None:
        version = self.changelog_version()
        self.assertEqual(version, json.loads(read(CLAUDE_MANIFEST))["version"])
        self.assertEqual(version, json.loads(read(CODEX_MANIFEST))["version"])
        self.assertEqual(version, json.loads(read(CLAUDE_MARKETPLACE))["plugins"][0]["version"])
        self.assertIn(version, read(ROOT / "README.md"))
        self.assertIn(version, "\n".join(read(SCRIPT).split("\n")[:5]), "the header of verify-done.mjs names the version")

    def count_texts(self) -> dict[str, str]:
        claude, codex, market = (json.loads(read(p)) for p in (CLAUDE_MANIFEST, CODEX_MANIFEST, CLAUDE_MARKETPLACE))
        texts = {rel(p): read(p) for p in (ROOT / "README.md", PLUGIN / "README.md", ROOT / "INSTALL.md", ROOT / "CODEX.md")}
        texts["claude plugin.json description"] = claude["description"]
        texts["codex plugin.json description"] = codex["description"]
        texts["codex interface.longDescription"] = codex["interface"]["longDescription"]
        texts["marketplace description"] = market["description"]
        texts["marketplace plugins[0].description"] = market["plugins"][0]["description"]
        return texts

    def test_counts_written_in_documents_equal_the_counts_on_disk(self) -> None:
        skills, agents, rules = len(skill_dirs()), len(agent_files()), len(hard_rules())
        for label, text in self.count_texts().items():
            with self.subTest(text=label):
                for pattern, expected in ((r"(\d+)\s+skills\b", skills), (r"(\d+)\s+agents\b", agents), (r"(\d+)\s+hard rules\b", rules)):
                    for found in re.findall(pattern, text):
                        self.assertEqual(expected, int(found), f"{found} stated, {expected} on disk ({pattern})")

    def test_the_main_documents_state_the_skill_and_agent_counts(self) -> None:
        texts = self.count_texts()
        for label in ("README.md", "plugins/superdev/README.md", "claude plugin.json description"):
            with self.subTest(text=label):
                self.assertTrue(re.search(r"\d+\s+skills\b", texts[label]), "no skill count")
                self.assertTrue(re.search(r"\d+\s+agents\b", texts[label]), "no agent count")

    def test_documents_list_every_skill_and_agent(self) -> None:
        readme, plugin_readme = read(ROOT / "README.md"), read(PLUGIN / "README.md")
        for name in sorted(EXPECTED_SKILLS):
            self.assertIn(name, readme, f"README.md lists the skill {name}")
        for name in sorted(EXPECTED_AGENTS):
            self.assertIn(name, plugin_readme, f"plugins/superdev/README.md lists the agent {name}")


class HardRulesTests(unittest.TestCase):
    def test_rules_are_numbered_without_gaps_with_scope_and_verify(self) -> None:
        rules = hard_rules()
        self.assertEqual(list(range(1, EXPECTED_HARD_RULES + 1)), [n for n, _ in rules])
        for number, body in rules:
            with self.subTest(rule=number):
                self.assertIn("**Scope:**", body)
                self.assertIn("**Verify:**", body)

    def test_domains_are_example_domains(self) -> None:
        for m in re.finditer(r"\b(?:[a-z0-9-]+\.)+(?:com|org|net|io)\b", read(HARD_RULES), re.I):
            self.assertRegex(m.group(0).lower(), r"(?:^|\.)example\.(?:com|org|net|io)$", m.group(0))

    def test_rules_cover_the_traps(self) -> None:
        text = read(HARD_RULES)
        needles = (
            "navree skills:install", "navree new", "#[public]", "&Uow", "validation_failed", "422", "APP_*",
            "config/app.toml", ".env", "#[model(workspace)]", "RlsPolicy", "SQLite", "MySQL", "AuditModule",
            "navree check", "navree migrate", "navree dock up", "Navree UI gaps", "migrate_on_boot", "openapi:export",
            "Idempotency-Key", "pg_advisory_xact_lock", "send_stream()", "adb", "base_commit",
        )
        for needle in needles:
            self.assertIn(needle, text, f"hard-rules.md must cover {needle}")

    def test_rule_ids_are_defined_once_and_every_citation_is_defined(self) -> None:
        prefixes = "|".join(RULE_PREFIXES)
        defined: dict[str, list[str]] = {}
        text_by_file = {rel(p): read(p) for p in plugin_text_files()}
        for name, text in text_by_file.items():
            for m in re.finditer(rf"\*\*({prefixes})-(\d+)\*\*", text):
                defined.setdefault(f"{m.group(1)}-{m.group(2)}", []).append(name)
        self.assertEqual({}, {k: v for k, v in defined.items() if len(v) != 1}, "each rule id is defined exactly once")
        cited = {(m.group(0), name) for name, text in text_by_file.items() for m in re.finditer(rf"\b(?:{prefixes})-\d+\b", text)}
        self.assertEqual([], sorted(f"{name}: {rule_id}" for rule_id, name in cited if rule_id not in defined))
        count = len(hard_rules())
        too_high = []
        for name, text in text_by_file.items():
            for m in re.finditer(r"hard rules? (\d+(?:(?:,| and| or| to|, and)? \d+)*)", text, re.I):
                too_high += [f"{name}: {n}" for n in map(int, re.findall(r"\d+", m.group(1))) if n > count]
        self.assertEqual([], too_high, "a cited hard rule does not exist")


class BuildSkillTests(unittest.TestCase):
    def test_superdev_build_has_ten_steps_in_order_and_names_the_key_commands(self) -> None:
        text = read(SKILLS / "superdev-build" / "SKILL.md")
        self.assertEqual(list(range(1, 11)), [int(n) for n in re.findall(r"^## Step (\d+)\. ", text, re.M)])
        for needle in ("navree skills:install", "STACK.md", "contracts/", "navree migrate:fresh --seed",
                       "verify-done.mjs --suites --strict", "${CLAUDE_PLUGIN_ROOT}"):
            self.assertIn(needle, text)

    def test_the_qa_gate_names_its_owners_and_its_statuses(self) -> None:
        gate = read(SKILLS / "product-qa" / "SKILL.md")
        for needle in ("QA_COVERAGE.md", "NOT RUN"):
            self.assertIn(needle, gate)
        for agent in GATE_AGENTS:
            with self.subTest(agent=agent):
                self.assertIn(f"`{agent}`", gate)
                self.assertTrue((AGENTS / f"{agent}.md").is_file())

    def test_security_foundation_names_the_committed_suites(self) -> None:
        folder = SKILLS / "security-foundation"
        text = "\n".join(read(p) for p in [folder / "SKILL.md", *sorted((folder / "references").glob("*.md"))])
        for suite in ("tests/security.rs", "tests/access.rs", "tests/isolation.rs", "tests/money.rs", "tests/live.rs"):
            self.assertIn(suite, text)

    def test_architecture_governance_covers_scaling_workers_hierarchy_srp_and_stories(self) -> None:
        folder = SKILLS / "architecture-governance"
        text = "\n".join(read(p) for p in [folder / "SKILL.md", *sorted((folder / "references").glob("*.md"))])
        for needle in ("GOV-1", "GOV-8", "sync-http", "async-queue", "scheduled-cron", "isolated-worker",
                       "sse-stream", "module dependency graph", "contract stories", "Must pass", "Must reject",
                       "413", "__proto__"):
            self.assertIn(needle, text, f"architecture-governance must cover {needle}")

    def test_navree_skill_names_are_real_and_every_skill_uses_one(self) -> None:
        agent_names = {p.stem for p in agent_files()}
        unknown = []
        for path in plugin_text_files():
            for token in re.findall(r"`(navree-[a-z0-9-]+)`", read(path)):
                if token not in NAVREE_SKILLS and token not in agent_names:
                    unknown.append(f"{rel(path)}: {token}")
        self.assertEqual([], unknown, "a backticked navree-* name is neither a Navree skill nor a superdev agent")
        for d in skill_dirs():
            if d.name in OUTSIDE_NAVREE_SKILLS:
                continue
            with self.subTest(skill=d.name):
                used = {t for p in d.rglob("*.md") for t in re.findall(r"`(navree(?:-[a-z0-9-]+)?)`", read(p)) if t in NAVREE_SKILLS}
                self.assertTrue(used, "the skill names no Navree skill")


class VocabularyTests(unittest.TestCase):
    def test_status_and_severity_words(self) -> None:
        severity = "Critical|High|Medium|Low|Info"
        banned = [
            ("[SKIP]", re.compile(r"\[SKIP\]")), ("[WARN]", re.compile(r"\[WARN\]")), ("N/A", re.compile(r"N/A")),
            ("P0 to P3", re.compile(r"\bP[0-3]\b")), ("old status word", re.compile(r"\b(?:GRACEFUL|DEGRADED|BROKEN)\b")),
            ("old severity in a table cell", re.compile(rf"\|\s*(?:{severity})\s*\|")),
            ("old severity after the word severity", re.compile(rf"(?i:severity).{{0,40}}\b(?:{severity})\b")),
        ]
        found = [f"{rel(p)}: {name}" for p in scanned() for name, pattern in banned if pattern.search(read(p))]
        self.assertEqual([], found)

    def test_no_filler(self) -> None:
        insensitive = re.compile(r"brutal|holy grail|iron law|world-class|non-negotiable|no exceptions", re.I)
        exact = re.compile(r"CRITICAL|MANDATORY")
        role_play = re.compile(r"^You are\b", re.M)
        symbols = re.compile("[☀-➿\U0001f300-\U0001faff]")
        found = []
        for p in scanned():
            text = read(p)
            for name, pattern in (("filler word", insensitive), ("capital filler", exact), ("role-play opening", role_play), ("emoji or symbol", symbols)):
                m = pattern.search(text)
                if m:
                    found.append(f"{rel(p)}: {name}: {m.group(0)!r}")
        self.assertEqual([], found)

    def test_removed_names_appear_nowhere_in_the_plugin_or_its_documents(self) -> None:
        patterns = [(n, name_pattern(n)) for n in REMOVED_SKILLS + REMOVED_AGENTS + OLD_ARTIFACTS]
        patterns.append(("db:seed as a package script", OLD_PACKAGE_SEED))
        found = []
        for p in scanned():
            text = read(p)
            found += [f"{rel(p)}: {name}" for name, pattern in patterns if pattern.search(text)]
        self.assertEqual([], found)

    def test_old_stack_names_appear_only_where_version_2_1_0_is_named(self) -> None:
        found = []
        for p in scanned():
            lines = read(p).split("\n")
            for i, line in enumerate(lines):
                if not OLD_STACK.search(line):
                    continue
                allowed = False
                if p.name in {"README.md", "INSTALL.md"} and p.parent == ROOT:
                    next_line = next((n for n in lines[i + 1:] if n.strip()), "")
                    allowed = "2.1.0" in line or (line.startswith("#") and "2.1.0" in next_line)
                if not allowed:
                    found.append(f"{rel(p)}:{i + 1}: {line.strip()[:80]}")
        self.assertEqual([], found)


class PackageTests(unittest.TestCase):
    def test_the_committed_archive_matches_the_tree(self) -> None:
        tool = ROOT / "tools" / "build_zip.py"
        self.assertTrue(tool.is_file())
        res = subprocess.run([sys.executable, str(tool), "--check"], capture_output=True, text=True, encoding="utf-8",
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(0, res.returncode, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
