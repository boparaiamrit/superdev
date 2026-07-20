from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "superdev"
INSTALL_DOCS = (
    ROOT / "README.md",
    ROOT / "INSTALL.md",
    ROOT / "CODEX.md",
    PLUGIN_ROOT / "README.md",
    ROOT / "install-superdev.sh",
)
FORBIDDEN_GLOBAL_PATTERNS = {
    "global skill path": "~/.claude/skills",
    "HOME-variable global skill path": "${HOME}/.claude/skills",
    "unbraced HOME global skill path": "$HOME/.claude/skills",
    "global plugin target": "~/.claude/plugins/superdev",
    "HOME-variable global plugin target": "${HOME}/.claude/plugins/superdev",
    "unbraced HOME global plugin target": "$HOME/.claude/plugins/superdev",
    "obsolete plugin root": "CLAUDE_PLUGIN_DIR",
    "global lesson file": "~/.claude/CLAUDE.md",
    "personal Codex marketplace": "~/.agents/plugins/marketplace.json",
    "personal Codex plugin directory": "~/.codex/plugins",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def active_superdev_files() -> list[Path]:
    files = list(INSTALL_DOCS)
    for path in PLUGIN_ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".sh"}:
            files.append(path)
    return sorted(set(files))


class ProjectScopeStaticTests(unittest.TestCase):
    def test_no_global_superdev_paths(self) -> None:
        violations: list[str] = []
        for path in active_superdev_files():
            text = read_text(path)
            for label, pattern in FORBIDDEN_GLOBAL_PATTERNS.items():
                if pattern in text:
                    violations.append(f"{path.relative_to(ROOT)}: {label}: {pattern}")

        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_install_surfaces_do_not_target_global_claude_settings(self) -> None:
        violations: list[str] = []
        for path in INSTALL_DOCS:
            text = read_text(path)
            for pattern in (
                "~/.claude/plugins/",
                "~/.claude/settings.json",
                "installed globally",
                "Install anywhere",
            ):
                if pattern in text:
                    violations.append(f"{path.relative_to(ROOT)}: {pattern}")

        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_all_superdev_claude_commands_declare_scope(self) -> None:
        command_pattern = re.compile(
            r"(?:claude\s+)?/?plugin\s+(?:marketplace\s+add|install|uninstall|enable|disable).*superdev",
            re.IGNORECASE,
        )
        violations: list[str] = []
        commands: list[str] = []

        for path in INSTALL_DOCS:
            for line_number, line in enumerate(read_text(path).splitlines(), start=1):
                if not command_pattern.search(line):
                    continue
                commands.append(line.strip())
                if "uninstall" in line and "--scope user" in line:
                    continue
                if "--scope project" not in line:
                    violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")

        self.assertTrue(commands, "No Superdev Claude installation commands were found")
        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_required_project_install_commands_are_documented(self) -> None:
        combined = "\n".join(read_text(path) for path in INSTALL_DOCS)
        self.assertIn(
            "claude plugin marketplace add boparaiamrit/superdev --scope project",
            combined,
        )
        self.assertIn(
            "claude plugin install superdev@superdev --scope project",
            combined,
        )
        self.assertIn(".agents/plugins/marketplace.json", combined)

    def test_current_inventory_is_documented_by_source(self) -> None:
        skills = list((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
        agents = list((PLUGIN_ROOT / "agents").glob("*.md"))
        self.assertEqual(16, len(skills))
        self.assertEqual(51, len(agents))

    def test_skill_descriptions_avoid_reserved_angle_brackets(self) -> None:
        violations: list[str] = []
        for skill_path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md"):
            frontmatter = read_text(skill_path).split("---", maxsplit=2)[1]
            description = next(
                line.removeprefix("description:").strip()
                for line in frontmatter.splitlines()
                if line.startswith("description:")
            )
            if "<" in description or ">" in description:
                violations.append(str(skill_path.relative_to(ROOT)))

        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_archive_matches_plugin_tree_and_has_no_global_paths(self) -> None:
        archive_path = ROOT / "superdev.zip"
        expected = {
            f"superdev/{path.relative_to(PLUGIN_ROOT).as_posix()}"
            for path in PLUGIN_ROOT.rglob("*")
            if path.is_file()
        }

        with zipfile.ZipFile(archive_path) as archive:
            actual = {name for name in archive.namelist() if not name.endswith("/")}
            self.assertEqual(expected, actual)
            violations: list[str] = []
            for info in archive.infolist():
                if info.is_dir() or Path(info.filename).suffix not in {".md", ".json", ".sh"}:
                    continue
                text = archive.read(info).decode("utf-8")
                for label, pattern in FORBIDDEN_GLOBAL_PATTERNS.items():
                    if pattern in text:
                        violations.append(f"{info.filename}: {label}: {pattern}")

        self.assertEqual([], violations, "\n" + "\n".join(violations))


class ProjectScopeInstallerTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.project = self.base / "project"
        self.project.mkdir()
        subprocess.run(
            ["git", "init", "-q"],
            cwd=self.project,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.outside = self.base / "outside"
        self.outside.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.fake_bin = self.base / "bin"
        self.fake_bin.mkdir()
        self.log_path = self.base / "claude.log"
        self._write_fake_claude()

        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": f"{self.fake_bin}{os.pathsep}{self.env['PATH']}",
                "HOME": str(self.home),
                "FAKE_CLAUDE_LOG": str(self.log_path),
            }
        )

    def _write_fake_claude(self) -> None:
        fake = self.fake_bin / "claude"
        fake.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")

settings_path = Path.cwd() / ".claude" / "settings.json"

def load_settings():
    if not settings_path.exists():
        return {}
    return json.loads(settings_path.read_text(encoding="utf-8"))

def save_settings(settings):
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\\n", encoding="utf-8")

if args[:3] == ["plugin", "marketplace", "add"]:
    settings = load_settings()
    settings.setdefault("extraKnownMarketplaces", {})["superdev"] = {
        "source": {"source": "github", "repo": "boparaiamrit/superdev"}
    }
    save_settings(settings)
elif args[:2] == ["plugin", "install"]:
    settings = load_settings()
    settings.setdefault("enabledPlugins", {})["superdev@superdev"] = True
    save_settings(settings)
elif args[:3] == ["plugin", "list", "--json"]:
    print(json.dumps({"plugins": [{"id": "superdev@superdev", "scope": "project"}]}))
elif args[:2] == ["plugin", "uninstall"]:
    settings = load_settings()
    settings.setdefault("enabledPlugins", {}).pop("superdev@superdev", None)
    save_settings(settings)
elif args == ["--version"]:
    print("2.1.212")
""",
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

    def run_installer(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(ROOT / "install-superdev.sh"), *args],
            cwd=cwd or self.project,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

    def logged_commands(self) -> list[list[str]]:
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text().splitlines()]

    def assert_home_untouched(self) -> None:
        self.assertEqual([], list(self.home.iterdir()))

    def test_install_uses_project_scope(self) -> None:
        result = self.run_installer()

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            [
                "plugin",
                "marketplace",
                "add",
                "boparaiamrit/superdev",
                "--scope",
                "project",
            ],
            self.logged_commands(),
        )
        self.assertIn(
            ["plugin", "install", "superdev@superdev", "--scope", "project"],
            self.logged_commands(),
        )
        settings = json.loads((self.project / ".claude" / "settings.json").read_text())
        self.assertIs(settings["enabledPlugins"]["superdev@superdev"], True)
        self.assert_home_untouched()

    def test_uninstall_uses_project_scope(self) -> None:
        settings_dir = self.project / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"superdev@superdev": True}}),
            encoding="utf-8",
        )

        result = self.run_installer("--uninstall")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            ["plugin", "uninstall", "superdev@superdev", "--scope", "project"],
            self.logged_commands(),
        )
        self.assert_home_untouched()

    def test_verify_checks_project_install(self) -> None:
        settings_dir = self.project / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"superdev@superdev": True}}),
            encoding="utf-8",
        )

        result = self.run_installer("--verify")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(["plugin", "list", "--json"], self.logged_commands())
        self.assert_home_untouched()

    def test_enable_teams_preserves_project_settings(self) -> None:
        settings_dir = self.project / ".claude"
        settings_dir.mkdir()
        settings_path = settings_dir / "settings.json"
        settings_path.write_text(
            json.dumps({"permissions": {"allow": ["Read"]}}),
            encoding="utf-8",
        )

        result = self.run_installer("--enable-teams")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        settings = json.loads(settings_path.read_text())
        self.assertEqual({"allow": ["Read"]}, settings["permissions"])
        self.assertEqual("1", settings["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"])
        self.assert_home_untouched()

    def test_invalid_project_settings_are_not_overwritten(self) -> None:
        settings_dir = self.project / ".claude"
        settings_dir.mkdir()
        settings_path = settings_dir / "settings.json"
        original = "{invalid json\n"
        settings_path.write_text(original, encoding="utf-8")

        result = self.run_installer("--enable-teams")

        self.assertNotEqual(0, result.returncode)
        self.assertEqual(original, settings_path.read_text(encoding="utf-8"))
        self.assert_home_untouched()

    def test_installer_refuses_to_run_outside_git_project(self) -> None:
        result = self.run_installer(cwd=self.outside)

        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], self.logged_commands())
        self.assert_home_untouched()

    def test_auxiliary_agent_installers_use_bundled_project_sources(self) -> None:
        installers = {
            "exploratory-qa/references/install-qa-agents.sh": 4,
            "prd-design-build-orchestrator/references/install-core-agents.sh": 10,
            "prototype-to-saas/references/install-migration-agents.sh": 5,
            "security-review-and-fix/references/install-security-agents.sh": 5,
        }

        for relative_path, expected_count in installers.items():
            with self.subTest(installer=relative_path):
                project = self.base / Path(relative_path).stem
                project.mkdir()
                result = subprocess.run(
                    ["bash", str(PLUGIN_ROOT / "skills" / relative_path)],
                    cwd=project,
                    env=self.env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )

                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                installed_agents = list((project / ".claude" / "agents").glob("*.md"))
                self.assertEqual(expected_count, len(installed_agents))

        self.assert_home_untouched()


if __name__ == "__main__":
    unittest.main()
