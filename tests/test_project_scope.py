"""Project-scope tests: nothing installs superdev outside the project, and the installer behaves.

Run: python -m unittest discover -s tests -v

The installer tests run install-superdev.sh with a real bash and a fake `claude`. Where no real bash
can read the script, the class is skipped and the skip reason says why. On Windows the bash on PATH
is usually the WSL launcher, which cannot read Windows paths; Git Bash is looked for explicitly.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "superdev"
INSTALLER = ROOT / "install-superdev.sh"
INSTALL_DOCS = (
    ROOT / "README.md",
    ROOT / "INSTALL.md",
    ROOT / "CODEX.md",
    PLUGIN_ROOT / "README.md",
    INSTALLER,
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


def write_lf(path: Path, text: str) -> None:
    """Write a script with LF line endings on every platform (a CR in a shebang line breaks it)."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def active_superdev_files() -> list[Path]:
    files = list(INSTALL_DOCS)
    files += [p for p in PLUGIN_ROOT.rglob("*") if p.is_file() and p.suffix in {".md", ".json", ".sh"}]
    return sorted(set(files))


class ProjectScopeStaticTests(unittest.TestCase):
    def test_no_global_superdev_paths(self) -> None:
        violations = [
            f"{path.relative_to(ROOT)}: {label}: {pattern}"
            for path in active_superdev_files()
            for label, pattern in FORBIDDEN_GLOBAL_PATTERNS.items()
            if pattern in read_text(path)
        ]
        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_install_surfaces_do_not_target_global_claude_settings(self) -> None:
        patterns = ("~/.claude/plugins/", "~/.claude/settings.json", "installed globally", "Install anywhere")
        violations = [f"{path.relative_to(ROOT)}: {p}" for path in INSTALL_DOCS for p in patterns if p in read_text(path)]
        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_all_superdev_claude_commands_declare_scope(self) -> None:
        command = re.compile(r"(?:claude\s+)?/?plugin\s+(?:marketplace\s+add|install|uninstall|enable|disable).*superdev", re.I)
        violations: list[str] = []
        commands: list[str] = []
        for path in INSTALL_DOCS:
            for number, line in enumerate(read_text(path).splitlines(), start=1):
                if not command.search(line):
                    continue
                commands.append(line.strip())
                if "uninstall" in line and "--scope user" in line:
                    continue  # moving a user-scope install is documented
                if "--scope project" not in line:
                    violations.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
        self.assertTrue(commands, "no superdev installation command found in the install documents")
        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_required_project_install_commands_are_documented(self) -> None:
        combined = "\n".join(read_text(path) for path in INSTALL_DOCS)
        for needle in (
            "claude plugin marketplace add boparaiamrit/superdev --scope project",
            "claude plugin install superdev@superdev --scope project",
            ".agents/plugins/marketplace.json",
        ):
            self.assertIn(needle, combined)

    def test_archive_has_no_global_paths(self) -> None:
        archive_path = ROOT / "superdev.zip"
        self.assertTrue(archive_path.is_file(), "superdev.zip is missing; build it with python tools/build_zip.py")
        violations: list[str] = []
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if info.is_dir() or Path(info.filename).suffix not in {".md", ".json", ".sh"}:
                    continue
                text = archive.read(info).decode("utf-8")
                violations += [f"{info.filename}: {label}: {p}" for label, p in FORBIDDEN_GLOBAL_PATTERNS.items() if p in text]
        self.assertEqual([], violations, "\n" + "\n".join(violations))


class BashHost:
    """A bash that can run the installer: its executable, the installer's path as that bash reads it, and PATH additions."""

    def __init__(self, exe: str, script: str, extra_path: list[str]) -> None:
        self.exe, self.script, self.extra_path = exe, script, extra_path


WSL_LAUNCHER = re.compile(r"[\\/](?:windows[\\/]system32|windowsapps)[\\/]", re.I)


def bash_candidates() -> list[str]:
    """Executables that may be a real bash. On Windows the launcher of WSL is left out (it cannot read Windows paths)."""
    found = [shutil.which("bash")] if shutil.which("bash") else []
    if os.name == "nt":
        roots: list[Path] = []
        git = shutil.which("git")
        if git:
            roots += list(Path(git).resolve().parents)[1:3]  # <Git>/cmd/git.exe and <Git>/mingw64/bin/git.exe
        for variable, sub in (("ProgramFiles", "Git"), ("ProgramFiles(x86)", "Git"), ("LOCALAPPDATA", "Programs/Git")):
            if os.environ.get(variable):
                roots.append(Path(os.environ[variable]) / sub)
        found += [str(root / rel) for root in roots for rel in ("bin/bash.exe", "usr/bin/bash.exe") if (root / rel).is_file()]
        found = [exe for exe in found if not WSL_LAUNCHER.search(exe)]
    return list(dict.fromkeys(found))


def posix_path(exe: str, path: Path) -> str | None:
    """The path as the given bash reads it (cygpath in Git Bash; unchanged on Linux and macOS)."""
    if os.name != "nt":
        return path.as_posix()
    res = subprocess.run([exe, "-c", 'cygpath -u "$1"', "_", str(path)], capture_output=True, text=True, timeout=60)
    return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else None


def find_bash(shim_dir: Path) -> BashHost | str:
    """A working BashHost, or the reason there is none. On Windows a `python3` shim stands in when Git Bash has no usable one."""
    candidates = bash_candidates()
    if not candidates:
        return ("no real bash found: the bash on PATH is the WSL launcher, which cannot read Windows paths "
                "(install Git for Windows to run the installer tests)" if os.name == "nt" else "bash is not on PATH")
    reasons: list[str] = []
    for exe in candidates:
        script = posix_path(exe, INSTALLER)
        if script is None:
            reasons.append(f"{exe}: cannot convert the installer path")
            continue
        shim_target = posix_path(exe, Path(sys.executable)) if os.name == "nt" else None
        for extra in ([], [str(shim_dir)]) if shim_target else ([],):
            if extra:
                write_lf(shim_dir / "python3", f'#!/bin/sh\nexec "{shim_target}" "$@"\n')
            env = {**os.environ, "PATH": os.pathsep.join([*extra, os.environ["PATH"]])}
            probe = subprocess.run([exe, "-c", 'test -f "$1" && python3 -c "import json, pathlib" && command -v git', "_", script],
                                   capture_output=True, text=True, env=env, timeout=120)
            if probe.returncode == 0:
                return BashHost(exe, script, extra)
        reasons.append(f"{exe}: cannot read the installer, or has no usable python3 or git")
    return "; ".join(reasons)


class ProjectScopeInstallerTests(unittest.TestCase):
    maxDiff = None
    host: BashHost

    @classmethod
    def setUpClass(cls) -> None:
        cls.shim_dir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.shim_dir.cleanup)
        found = find_bash(Path(cls.shim_dir.name))
        if isinstance(found, str):
            raise unittest.SkipTest(found)
        cls.host = found

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.project = self.base / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True, capture_output=True, text=True)
        self.outside = self.base / "outside"
        self.outside.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.fake_bin = self.base / "bin"
        self.fake_bin.mkdir()
        self.log_path = self.base / "claude.log"
        self._write_fake_claude()
        path = os.pathsep.join([str(self.fake_bin), *self.host.extra_path, os.environ["PATH"]])
        self.env = {**os.environ, "PATH": path, "HOME": str(self.home), "FAKE_CLAUDE_LOG": str(self.log_path)}

    def _write_fake_claude(self) -> None:
        fake = self.fake_bin / "claude"
        write_lf(
            fake,
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
    default = json.dumps({"plugins": [{"id": "superdev@superdev", "scope": "project"}]})
    print(os.environ.get("FAKE_CLAUDE_LIST") or default)
elif args[:2] == ["plugin", "uninstall"]:
    settings = load_settings()
    settings.setdefault("enabledPlugins", {}).pop("superdev@superdev", None)
    save_settings(settings)
elif args == ["--version"]:
    print("2.1.212")
""",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

    def run_installer(self, *args: str, cwd: Path | None = None, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.host.exe, self.host.script, *args],
            cwd=cwd or self.project,
            env={**self.env, **env},
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=300,
        )

    def logged_commands(self) -> list[list[str]]:
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines()]

    def enable_in_settings(self) -> Path:
        settings_dir = self.project / ".claude"
        settings_dir.mkdir()
        path = settings_dir / "settings.json"
        path.write_text(json.dumps({"enabledPlugins": {"superdev@superdev": True}}), encoding="utf-8")
        return path

    def assert_home_untouched(self) -> None:
        self.assertEqual([], list(self.home.iterdir()))

    def assert_plain_status(self, result: subprocess.CompletedProcess[str]) -> None:
        """Status lines read [*], [ok] and [error]; no tick or cross marks."""
        self.assertFalse({"✓", "✗", "✔", "✘"} & set(result.stdout + result.stderr))

    def test_install_uses_project_scope(self) -> None:
        result = self.run_installer()

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assert_plain_status(result)
        self.assertIn("[ok] Superdev is enabled for project", result.stdout)
        self.assertIn(["plugin", "marketplace", "add", "boparaiamrit/superdev", "--scope", "project"], self.logged_commands())
        self.assertIn(["plugin", "install", "superdev@superdev", "--scope", "project"], self.logged_commands())
        settings = json.loads((self.project / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIs(settings["enabledPlugins"]["superdev@superdev"], True)
        self.assert_home_untouched()

    def test_from_a_subfolder_the_project_is_the_repository_root(self) -> None:
        app = self.project / "apps" / "shop"
        app.mkdir(parents=True)

        result = self.run_installer(cwd=app)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue((self.project / ".claude" / "settings.json").is_file())
        self.assertFalse((app / ".claude").exists())
        self.assert_home_untouched()

    def test_here_makes_the_folder_it_is_run_from_the_project(self) -> None:
        """An app that is one folder of a larger repository is its own Claude Code project."""
        app = self.project / "apps" / "shop"
        app.mkdir(parents=True)

        result = self.run_installer("--here", cwd=app)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assert_plain_status(result)
        settings = json.loads((app / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIs(settings["enabledPlugins"]["superdev@superdev"], True)
        self.assertFalse((self.project / ".claude").exists(), "nothing is written at the repository's root")
        self.assertIn(["plugin", "install", "superdev@superdev", "--scope", "project"], self.logged_commands())

        verified = self.run_installer("--here", "--verify", cwd=app)
        self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)
        self.assertIn("[ok] Superdev is enabled for project", verified.stdout)

        removed = self.run_installer("--here", "--uninstall", cwd=app)
        self.assertEqual(0, removed.returncode, removed.stdout + removed.stderr)
        settings = json.loads((app / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("superdev@superdev", settings["enabledPlugins"])
        self.assert_home_untouched()

    def test_here_outside_a_git_project_is_refused(self) -> None:
        result = self.run_installer("--here", cwd=self.outside)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("[error] Run this command from inside the target Git project.", result.stderr)
        self.assertEqual([], self.logged_commands())
        self.assert_home_untouched()

    def test_uninstall_uses_project_scope(self) -> None:
        self.enable_in_settings()

        result = self.run_installer("--uninstall")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assert_plain_status(result)
        self.assertIn("[ok] Superdev was removed from project scope", result.stdout)
        self.assertIn(["plugin", "uninstall", "superdev@superdev", "--scope", "project"], self.logged_commands())
        self.assert_home_untouched()

    def test_verify_checks_project_install(self) -> None:
        self.enable_in_settings()

        result = self.run_installer("--verify")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("[ok] Superdev is enabled for project", result.stdout)
        self.assertIn(["plugin", "list", "--json"], self.logged_commands())
        self.assert_home_untouched()

    def test_verify_needs_the_exact_plugin_id_in_the_plugin_list(self) -> None:
        self.enable_in_settings()
        def listed(plugin_id: str) -> str:
            return json.dumps({"plugins": [{"id": plugin_id, "scope": "project"}]})

        for name, plugin_id in (("another plugin that mentions superdev", "superdev-extras@elsewhere"),
                                ("an id that only starts with the exact one", "superdev@superdev-extras"),
                                ("an id that only ends with the exact one", "x-superdev@superdev")):
            with self.subTest(listed=name):
                result = self.run_installer("--verify", FAKE_CLAUDE_LIST=listed(plugin_id))
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("did not report superdev@superdev", result.stderr)
                self.assertNotIn("[ok]", result.stdout)
        result = self.run_installer("--verify", FAKE_CLAUDE_LIST=listed("superdev@superdev"))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_help_lists_the_options_without_a_project_and_without_the_removed_flag(self) -> None:
        result = self.run_installer("--help", cwd=self.outside)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        for option in ("--here", "--verify", "--uninstall", "--help"):
            self.assertIn(option, result.stdout)
        self.assertNotIn("--enable-teams", result.stdout)
        self.assertEqual([], self.logged_commands())

    def test_the_removed_agent_teams_flag_is_refused(self) -> None:
        result = self.run_installer("--enable-teams")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("[error] Unknown option: --enable-teams", result.stderr)
        self.assertFalse((self.project / ".claude" / "settings.json").exists())
        self.assertEqual([], self.logged_commands())

    def test_invalid_project_settings_are_not_overwritten(self) -> None:
        settings_dir = self.project / ".claude"
        settings_dir.mkdir()
        settings_path = settings_dir / "settings.json"
        original = "{invalid json\n"
        settings_path.write_bytes(original.encode("utf-8"))

        result = self.run_installer()

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Invalid project settings", result.stderr)
        self.assertEqual(original, settings_path.read_bytes().decode("utf-8"))
        self.assertEqual([], self.logged_commands())
        self.assert_home_untouched()

    def test_installer_refuses_to_run_outside_git_project(self) -> None:
        result = self.run_installer(cwd=self.outside)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("[error] Run this command from inside the target Git project.", result.stderr)
        self.assert_plain_status(result)
        self.assertEqual([], self.logged_commands())
        self.assert_home_untouched()


if __name__ == "__main__":
    unittest.main()
