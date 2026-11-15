"""Behavioural tests of plugins/superdev/scripts/verify-done.mjs on small temporary projects.

Run: python -m unittest discover -s tests -v

Every test builds its own project folder (optionally a git repository) and removes it again. The runs get a
PATH that holds only node, git and npm, so a fixture never starts the cargo or navree of the machine it runs on.
Where a test needs navree or cargo to answer, tests/fake_tools.cjs stands in for them inside the script's own
process (see that file); a stand-in answers `navree --version`, so a whole run can be green. The whole module is
skipped without node 18 or newer.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "superdev" / "scripts" / "verify-done.mjs"
FAKE_TOOLS = Path(__file__).resolve().parent / "fake_tools.cjs"
GIT_FLAGS = ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]
SKIP = ["--skip-build", "--skip-boot"]
FLAGS = ["--root", "--skip-build", "--skip-boot", "--health-url", "--suites", "--api-url", "--base", "--strict", "--help"]
CHECK_LABELS = [
    "STACK.md", "navree CLI", "navree skills installed", "cargo fmt", "cargo clippy", "cargo test", "navree check",
    "navree config:check", "public routes", "release build", "boot (release binary + health)", "API contract drift",
    "Navree UI raw markup", "Navree UI gap rows", "no new suppressions since", "no placeholder content", "suites: app running",
]
STACK_DEFAULTS = {
    "navree_version": "1.2.2",
    "new_command": "navree new ledgerly --database timescaledb",
    "front_end": "navree",
    "kit": "none",
    "database": "timescaledb",
    "binary": "ledgerly",
    "clients": "web",
    "base_commit": "",
    "test_database_url": "postgres://navree:navree@127.0.0.1:5432/ledgerly_test",
    "web_dir": "",
    "openapi": "",
    "api_types": "",
}
# What navree and cargo answer in a healthy app.
GREEN = {
    "navree --version": {"stdout": "navree 1.2.2\n"},
    "cargo fmt --all -- --check": {},
    "cargo clippy --workspace --all-targets -- -D warnings": {},
    "cargo test --workspace": {"stdout": "running 2 tests\ntest result: ok. 2 passed; 0 failed\n"},
    "navree check": {"stdout": "module graph OK: 1 modules, 2 providers\n"},
    "navree config:check": {},
    "navree routes --json": {"stdout": "[]\n"},
    "cargo build --release": {},
}
SKILL_FILES = {".claude/skills/navree/SKILL.md": "navree\n", ".agents/skills/navree/SKILL.md": "navree\n"}
PLAN = (
    "# Execution Plan\nStatus: CONFIRMED by Meera Sharma on 2026-11-18\n"
    "## Access\n- Public routes: `GET /health/live`, `GET /health/ready`, `GET /sign-in`.\n"
    "## Navree UI gaps\nNone.\n## Open items\nNone.\n"
)
GAP_MESSAGE = "not named in the Files column of any row of the gap table"
HEALTH_SERVER = (
    'const http = require("http");\n'
    'const [host, port] = process.env.APP_HTTP__ADDR.split(":");\n'
    "http.createServer((req, res) => {\n"
    '  if (req.url === "/health/live") res.end(\'{ "status": "up" }\');\n'
    '  else if (req.url === "/health/ready") res.end("ok");\n'
    "  else { res.statusCode = 404; res.end(); }\n"
    "}).listen(Number(port), host);\n"
)


def node_major() -> int:
    node = shutil.which("node")
    if not node:
        return 0
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    return int(re.match(r"v(\d+)", out).group(1)) if re.match(r"v(\d+)", out) else 0


needs_node = unittest.skipUnless(node_major() >= 18, "node 18 or newer is not on PATH; the verify-done tests need it")
needs_git = unittest.skipUnless(shutil.which("git"), "git is not on PATH")
needs_npm = unittest.skipUnless(shutil.which("npm"), "npm is not on PATH")


def stack_text(suites: tuple[str, ...] = (), omit: tuple[str, ...] = (), **overrides: str) -> str:
    values = {**STACK_DEFAULTS, **overrides}
    lines = ["# Stack", ""] + [f"{k}: {v}" for k, v in values.items() if k not in omit]
    return "\n".join(lines + ["", "## Suites", ""] + [f"- {s}" for s in suites]) + "\n"


def plan_with_gap(files: str) -> str:
    row = f"| N-1 | Customers (D-1) | a balance badge | `navree-ui` badges | composed from Badge | {files} | Meera Sharma, 2026-11-20 |\n"
    return PLAN.replace("## Navree UI gaps\nNone.\n", "## Navree UI gaps\n| N | Screen | Missing | Checked | Resolution | Files | Agreed by |\n|---|---|---|---|---|---|---|\n" + row)


def tool_path() -> str:
    dirs: list[str] = []
    for tool in ("node", "git", "npm"):
        found = shutil.which(tool)
        if found and str(Path(found).parent) not in dirs:
            dirs.append(str(Path(found).parent))
    return os.pathsep.join(dirs)


def status_of(output: str, label: str) -> str | None:
    """The status printed for the first check whose label starts with `label`."""
    m = re.search(rf"^ \[(PASS|FAIL|NOT RUN)\] {re.escape(label)}", output, re.M)
    return m.group(1) if m else None


def detail_of(output: str, label: str) -> str:
    """The indented detail lines under the first check whose label starts with `label`."""
    m = re.search(rf"^ \[(?:PASS|FAIL|NOT RUN)\] {re.escape(label)}[^\n]*\n((?:      .*\n)*)", output, re.M)
    return m.group(1) if m else ""


class Project:
    """A temporary app folder that removes itself when the test ends."""

    tools: dict | None = None

    def __init__(self, test: unittest.TestCase) -> None:
        self.test = test
        tmp = tempfile.TemporaryDirectory(prefix="superdev-vd-")
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *GIT_FLAGS, *args], cwd=self.root, capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def init_git(self) -> None:
        self.git("init", "-q")

    def commit(self, message: str = "commit") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "--short", "HEAD")

    def run(self, *flags: str, tools: dict | None = None) -> subprocess.CompletedProcess[str]:
        """Runs the script on this folder; `tools` (default: the project's own) says what navree and cargo answer."""
        answers = self.tools if tools is None else tools
        tools_file = None
        if answers is not None:
            aux = tempfile.TemporaryDirectory(prefix="superdev-vd-tools-")
            self.test.addCleanup(aux.cleanup)
            tools_file = Path(aux.name) / "tools.json"
            tools_file.write_text(json.dumps(answers), encoding="utf-8")
        return run_script("--root", str(self.root), *flags, tools_file=tools_file)

    def copy_node_as_binary(self, serve_js: str) -> None:
        """A copy of node stands in for the release binary: `<binary> serve` runs serve.js from the app root."""
        self.write("serve.js", serve_js)
        exe = self.root / "target" / "release" / ("ledgerly.exe" if os.name == "nt" else "ledgerly")
        exe.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(shutil.which("node"), exe)


def run_script(*args: str, tools_file: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PATH": tool_path()}
    if tools_file is not None:
        preload = FAKE_TOOLS.as_posix()
        option = f'--require="{preload}"' if " " in preload else f"--require={preload}"
        env["NODE_OPTIONS"] = f"{env.get('NODE_OPTIONS', '')} {option}".strip()
        env["FAKE_TOOLS"] = str(tools_file)
    return subprocess.run(["node", str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)


def repo(test: unittest.TestCase, base_files: dict[str, str] | None = None, **stack: str) -> tuple[Project, str]:
    """A git repository whose first commit is the base (skills, plan and the given files); STACK.md names it."""
    p = Project(test)
    p.init_git()
    for rel, text in {".gitignore": "target/\n", "README.md": "app\n", "EXECUTION_PLAN.md": PLAN, "src/main.rs": "fn main() {}\n",
                      **SKILL_FILES, **(base_files or {})}.items():
        p.write(rel, text)
    base = p.commit("base")
    p.write("STACK.md", stack_text(**{"base_commit": base, **stack}))
    p.tools = GREEN
    return p, base


def start_health_server() -> tuple[ThreadingHTTPServer, str]:
    class Health(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (name fixed by the base class)
            self.send_response(200 if self.path == "/health/ready" else 404)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def free_url() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{s.getsockname()[1]}"


@needs_node
class UsageTests(unittest.TestCase):
    def test_help_prints_every_flag_and_check_and_exits_0(self) -> None:
        res = run_script("--help")
        self.assertEqual(0, res.returncode, res.stderr)
        for text in FLAGS + CHECK_LABELS:
            self.assertIn(text, res.stdout)

    def test_help_says_what_the_flags_and_the_drift_check_do(self) -> None:
        out = run_script("--help").stdout
        self.assertRegex(out, r"--health-url URL\s+for --suites")
        self.assertIn("the boot check always probes the binary it started", out)
        self.assertRegex(out, r"openapi:export and openapi:client REWRITE the document and the types in the working tree")
        self.assertIn("git diff --exit-code HEAD", out)
        self.assertIn("must start with cargo test", out)

    def test_help_describes_the_navree_ui_checks_as_hard_rules_14_and_6_do(self) -> None:
        # The wording of hard rule 14's Verify line and of rule 6's: the files, the folders left out, the table rows.
        out = " ".join(run_script("--help").stdout.split())
        for text in ("every Rust file of the app (outside target/, plugins/, .claude/, .agents/ and tests/ folders",
                     "uses SafeHtml, Node::Raw, Node::Static, el or AppSheet",
                     "every .css file added or changed since the base",
                     "is named in the Files of a table row of EXECUTION_PLAN.md ## Navree UI gaps; prose does not name a file",
                     "no style, class or on* attribute in a tag (quoted or not)",
                     "named as `METHOD path` in backticks in EXECUTION_PLAN.md ## Access",
                     "oxlint-disable", "an ESLint or oxlint rule set to off or 0", "clippy.toml allow-* or *-threshold key"):
            self.assertIn(text, out)

    def test_unknown_flags_and_missing_values_exit_2(self) -> None:
        for args in (["--bogus"], ["stray"], ["--root"], ["--base", "--strict"], ["--api-url"]):
            with self.subTest(args=args):
                res = run_script(*args)
                self.assertEqual(2, res.returncode, res.stdout)
                self.assertIn("Usage: node verify-done.mjs", res.stderr)
        res = run_script("--root", str(ROOT / "no-such-folder"))
        self.assertEqual(2, res.returncode)

    def test_the_script_parses(self) -> None:
        res = subprocess.run(["node", "--check", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(0, res.returncode, res.stderr)


@needs_node
@needs_git
class StackTests(unittest.TestCase):
    def test_a_folder_without_stack_md_fails_and_never_prints_done(self) -> None:
        p = Project(self)
        for files in ({}, {"docs/brief/prd.md": "A PRD\n"}):  # an empty folder, and the brief folder
            for flags in ((), ("--strict",)):
                with self.subTest(files=list(files), flags=flags):
                    for rel, text in files.items():
                        p.write(rel, text)
                    res = p.run(*flags)
                    self.assertEqual(1, res.returncode, res.stdout)
                    self.assertEqual("FAIL", status_of(res.stdout, "STACK.md"))
                    self.assertIn("stack: not read", res.stdout)
                    self.assertIn("NOT DONE", res.stdout)
                    self.assertNotRegex(res.stdout, r"(?m)^DONE")
                    for label in ("navree CLI", "cargo test", "Navree UI raw markup", "public routes"):
                        self.assertIsNone(status_of(res.stdout, label), label)

    def test_a_value_outside_its_set_fails(self) -> None:
        for key, value in (("front_end", "vue"), ("kit", "micro"), ("database", "oracle"), ("clients", "web, tv")):
            with self.subTest(key=key):
                p = Project(self)
                p.write("STACK.md", stack_text(**{key: value}))
                res = p.run(*SKIP)
                self.assertEqual(1, res.returncode, res.stdout)
                self.assertEqual("FAIL", status_of(res.stdout, "STACK.md"))
                self.assertIn(key, detail_of(res.stdout, "STACK.md"))
                self.assertIn("stack: invalid", res.stdout)
                self.assertIsNone(status_of(res.stdout, "navree CLI"), "a failed STACK.md stops the checks that depend on it")

    def test_missing_keys_are_named_and_next_needs_its_paths(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text(omit=("binary", "base_commit")))
        res = p.run(*SKIP)
        self.assertIn("missing key(s): binary, base_commit", res.stdout)
        p = Project(self)
        p.write("STACK.md", stack_text(front_end="next", kit="saas"))
        self.assertIn("front_end: next needs a value for web_dir, openapi, api_types", p.run(*SKIP).stdout)

    def test_an_empty_new_command_is_valid_and_the_other_keys_keep_their_rules(self) -> None:
        # The build started from a Navree app that existed already: there is no `navree new` line to copy.
        p = Project(self)
        p.write("STACK.md", stack_text(new_command=""))
        res = p.run(*SKIP)
        self.assertEqual("PASS", status_of(res.stdout, "STACK.md"), res.stdout)
        self.assertIn("stack: front_end=navree", res.stdout)
        for omit, empty, expected in ((("new_command",), {}, "missing key(s): new_command"),
                                      ((), {"binary": ""}, "empty value(s): binary"),
                                      ((), {"navree_version": ""}, "empty value(s): navree_version")):
            with self.subTest(omit=omit, empty=empty):
                p = Project(self)
                p.write("STACK.md", stack_text(omit=omit, **empty))
                self.assertIn(expected, p.run(*SKIP).stdout)

    def test_a_real_database_needs_a_test_database_url(self) -> None:
        for database in ("timescaledb", "postgres", "mysql"):
            with self.subTest(database=database):
                p = Project(self)
                p.write("STACK.md", stack_text(database=database, test_database_url=""))
                res = p.run(*SKIP)
                self.assertEqual("FAIL", status_of(res.stdout, "STACK.md"), res.stdout)
                self.assertIn("test_database_url is empty", detail_of(res.stdout, "STACK.md"))
                self.assertEqual(1, res.returncode)
                self.assertIsNone(status_of(res.stdout, "navree CLI"))
        for database, url in (("sqlite", ""), ("sqlite", "sqlite://storage/x.db"), ("postgres", "postgres://t")):
            with self.subTest(database=database, url=url):
                p = Project(self)
                p.write("STACK.md", stack_text(database=database, test_database_url=url))
                self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "STACK.md"))

    def test_a_valid_stack_is_read_with_comment_lines_and_crlf(self) -> None:
        p = Project(self)
        text = stack_text().replace("front_end: navree\n", "front_end: navree\n# navree from a local checkout: C:/src/navree\n")
        (p.root / "STACK.md").write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        res = p.run(*SKIP)
        self.assertEqual("PASS", status_of(res.stdout, "STACK.md"), res.stdout)
        self.assertIn("stack: front_end=navree database=timescaledb binary=ledgerly (STACK.md)", res.stdout)

    def test_installed_skills_are_checked_on_disk(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text())
        self.assertEqual("FAIL", status_of(p.run(*SKIP).stdout, "navree skills installed"))
        p.write(".claude/skills/navree/SKILL.md", "x\n")
        self.assertEqual("FAIL", status_of(p.run(*SKIP).stdout, "navree skills installed"))
        p.write(".agents/skills/navree/SKILL.md", "x\n")
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "navree skills installed"))

    def test_skip_flags_report_not_run(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text())
        out = p.run(*SKIP).stdout
        self.assertEqual("NOT RUN", status_of(out, "release build"))
        self.assertEqual("NOT RUN", status_of(out, "boot (release binary + health)"))
        self.assertIn("skipped by flag", out)

    def test_a_failing_navree_check_says_how_to_start_the_database(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text())
        out = p.run(*SKIP, tools={**GREEN, "navree check": {"exit": 1, "stderr": "database unreachable\n"}}).stdout
        detail = detail_of(out, "navree check")
        self.assertEqual("FAIL", status_of(out, "navree check"))
        self.assertIn("database unreachable", detail)
        self.assertIn("navree dock up for TimescaleDB and PostgreSQL; MySQL runs on a server you provide", detail)
        self.assertTrue(detail.rstrip().endswith("(hard rule 13)."), detail)


@needs_node
@needs_git
class GreenTests(unittest.TestCase):
    """A whole healthy app, and what turns it from done into not done."""

    def green_app(self, **stack: str) -> Project:
        p, _ = repo(self, {"serve.js": HEALTH_SERVER}, database="sqlite", test_database_url="", **stack)
        p.copy_node_as_binary(HEALTH_SERVER)
        return p

    def test_a_complete_app_is_done_with_and_without_strict(self) -> None:
        p = self.green_app()
        for flags in ((), ("--strict",)):
            res = p.run(*flags)
            self.assertEqual(0, res.returncode, res.stdout)
            self.assertIn("DONE — all live checks green. Browser, role and device evidence", res.stdout)
            self.assertNotIn("not a release claim", res.stdout)
            for label in ("navree CLI", "cargo test", "public routes", "release build", "boot (release binary + health)",
                          "Navree UI raw markup", "Navree UI gap rows", "no new suppressions since", "no placeholder content"):
                self.assertEqual("PASS", status_of(res.stdout, label), label)

    def test_one_warning_or_one_check_not_run_is_done_without_strict_and_not_done_with_it(self) -> None:
        p = self.green_app()
        p.write("clients/mobile/src-tauri/tauri.conf.json", json.dumps({"app": {"security": {"csp": {"default-src": "'self'"}}}}))
        p.write("clients/mobile/src-tauri/capabilities/default.json", json.dumps(
            {"identifier": "default", "permissions": [{"identifier": "http:default", "allow": [{"url": "http://10.0.2.2:4100/*"}]}]}))
        p.write("clients/mobile/src-tauri/Cargo.toml", '[dependencies]\ntauri = { version = "2" }\n\n[profile.release]\nstrip = true\n')
        loose = p.run()
        self.assertEqual(0, loose.returncode, loose.stdout)
        self.assertIn("with 1 warning(s) and 0 check(s) not run, so not a release claim", loose.stdout)
        strict = p.run("--strict")
        self.assertEqual(1, strict.returncode, strict.stdout)
        self.assertIn("NOT DONE (--strict) — 1 warning(s) and 0 check(s) not run.", strict.stdout)
        no_plan = self.green_app()
        (no_plan.root / "EXECUTION_PLAN.md").unlink()
        self.assertEqual("NOT RUN", status_of(no_plan.run().stdout, "public routes"))
        strict = no_plan.run("--strict")
        self.assertEqual(1, strict.returncode, strict.stdout)
        self.assertIn("NOT DONE (--strict) — 0 warning(s) and 1 check(s) not run.", strict.stdout)

    def test_skipped_build_and_boot_leave_a_run_that_is_not_a_release_claim(self) -> None:
        p = self.green_app()
        res = p.run(*SKIP)
        self.assertEqual(0, res.returncode, res.stdout)
        self.assertIn("with 0 warning(s) and 2 check(s) not run, so not a release claim", res.stdout)
        self.assertEqual(1, p.run(*SKIP, "--strict").returncode)

    def test_a_failing_check_makes_it_not_done(self) -> None:
        p = self.green_app()
        res = p.run(tools={**GREEN, "cargo test --workspace": {"exit": 101, "stdout": "test result: FAILED. 1 passed; 1 failed\n"}})
        self.assertEqual(1, res.returncode, res.stdout)
        self.assertEqual("FAIL", status_of(res.stdout, "cargo test"))
        self.assertIn("NOT DONE — 1 failing check(s).", res.stdout)


@needs_node
@needs_git
class SweepTests(unittest.TestCase):
    """The suppression, raw-markup, gap-row and placeholder sweeps."""

    def repo(self, base_files: dict[str, str] | None = None, **stack: str) -> tuple[Project, str]:
        return repo(self, base_files, **stack)

    def suppression(self, p: Project) -> str | None:
        return status_of(p.run(*SKIP).stdout, "no new suppressions since")

    def test_a_suppression_committed_after_the_base_fails(self) -> None:
        p, _ = self.repo()
        p.write("src/lib.rs", "#[allow(dead_code)]\nfn unused() {}\n")
        p.commit("add lib")
        res = p.run(*SKIP)
        self.assertEqual("FAIL", status_of(res.stdout, "no new suppressions since"), res.stdout)
        self.assertIn("src/lib.rs:1: #[allow(dead_code)]", res.stdout)
        self.assertEqual(1, res.returncode)

    def test_the_same_line_in_the_base_commit_passes(self) -> None:
        p, _ = self.repo({"src/lib.rs": "#[allow(dead_code)]\nfn unused() {}\n", "Cargo.toml": '[lints.rust]\nunused = "allow"\n'})
        p.write("src/other.rs", "fn used() {}\n")
        p.write("Cargo.toml", '[lints.rust]\nunused = "allow"\n[package]\nname = "x"\n')
        p.commit("clean change")
        res = p.run(*SKIP)
        self.assertEqual("PASS", status_of(res.stdout, "no new suppressions since"))
        self.assertEqual(0, res.returncode, res.stdout)

    def test_every_suppression_form_fails(self) -> None:
        forms = {
            "src/a.rs": "#![allow(unused)]\n",
            "src/b.rs": "#[expect(dead_code)]\nfn f() {}\n",
            "src/c.rs": "#[cfg_attr(test, allow(dead_code))]\nfn f() {}\n",
            "src/d.rs": "#![cfg_attr(not(test), expect(unused))]\n",
            "web/a.ts": "// eslint-disable-next-line no-console\n",
            "web/b.tsx": "// @ts-ignore\nconst x = 1;\n",
            "web/c.js": "/* @ts-nocheck */\n",
            "web/d.ts": "const value = input as any;\n",
            "web/e.mjs": "// @ts-expect-error\n",
            "web/f.tsx": "export default (props as any).title;\n",
            "web/g.ts": "// oxlint-disable-next-line no-explicit-any\nconst x = 1;\n",
            "web/h.tsx": "/* oxlint-disable */\n",
            "web/i.mjs": "// oxlint-disable-line no-console\n",
        }
        p, _ = self.repo()
        for rel, text in forms.items():
            with self.subTest(file=rel):
                p.write(rel, text)
                p.commit(rel)
                self.assertIn(f"{rel}:1:", p.run(*SKIP).stdout)
                p.git("rm", "-q", "-f", rel)
                p.commit(f"remove {rel}")

    def test_a_lint_turned_off_in_configuration_fails(self) -> None:
        forms = {
            "Cargo.toml": '[package]\nname = "x"\n\n[lints.rust]\nunused = "allow"\n',
            "Cargo.toml#inline": '[lints.clippy]\nall = { level = "allow", priority = -1 }\n',
            "member/Cargo.toml": '[workspace.lints.rust]\ndead_code = "allow"\n',
            "Cargo.toml#dotted": 'lints.rust.unused = "allow"\n',
            ".cargo/config.toml": '[build]\nrustflags = ["-A", "dead_code"]\n',
            ".cargo/config.toml#joined": '[build]\nrustflags = ["-Adead_code"]\n',
            ".cargo/config.toml#lines": '[build]\nrustflags = [\n  "-A",\n  "unused",\n]\n',
            ".cargo/config": 'rustflags = ["--allow", "unused"]\n',
            "clippy.toml": 'msrv = "1.95"\nallow-unwrap-in-tests = true\n',
            "clippy.toml#threshold": 'cognitive-complexity-threshold = 40\n',
            "clippy.toml#args": 'too-many-arguments-threshold = 9\n',
            ".clippy.toml": 'allow-expect-in-tests = true\n',
            "web/.oxlintrc.json": '{\n  "rules": {\n    "no-console": "off"\n  }\n}\n',
            "web/.oxlintrc.json#list": '{\n  "rules": {\n    "no-explicit-any": ["off"]\n  }\n}\n',
            "web/.oxlintrc.json#allow": '{\n  "rules": {\n    "eqeqeq": "allow"\n  }\n}\n',
            "web/.oxlintrc.json#zero": '{\n  "categories": {\n    "correctness": 0\n  }\n}\n',
            "web/eslint.config.mjs": 'export default [{ rules: {\n  "no-console": "off",\n} }];\n',
            "web/eslint.config.js": "module.exports = [{ rules: {\n  semi: 0,\n} }];\n",
            "web/.eslintrc.json": '{\n  "rules": {\n    "@typescript-eslint/no-explicit-any": ["off"]\n  }\n}\n',
            "web/tsconfig.json": '{\n  "compilerOptions": {\n    "strict": false\n  }\n}\n',
            "clients/mobile/tsconfig.app.json": '{ "compilerOptions": {\n"strict" : false } }\n',
        }
        p, _ = self.repo()
        for key, text in forms.items():
            rel = key.split("#")[0]
            with self.subTest(file=key):
                p.write(rel, text)
                self.assertEqual("FAIL", self.suppression(p), "untracked")
                p.commit(key)
                out = p.run(*SKIP).stdout
                self.assertEqual("FAIL", status_of(out, "no new suppressions since"), out)
                self.assertIn(f"{rel}:", out)
                p.git("rm", "-q", "-f", rel)
                p.commit(f"remove {key}")

    def test_configuration_that_keeps_every_lint_on_passes(self) -> None:
        files = {
            "Cargo.toml": '[package]\nname = "x"\ndescription = "allow"\n\n[lints.rust]\nunused = "warn"\n\n[lints.clippy]\nall = { level = "deny", priority = -1 }\n',
            ".cargo/config.toml": '[build]\nrustflags = ["-D", "warnings"]\n[target.x86_64-linux-gnu]\nlinker = "gcc"\n',
            "web/eslint.config.mjs": 'export default [{ rules: {\n  "no-console": "error",\n  "max-lines": ["error", { max: 300 }],\n  "x": 0.5,\n} }];\n',
            "web/tsconfig.json": '{\n  "compilerOptions": {\n    "strict": true,\n    "noEmit": false\n  }\n}\n',
            "web/.oxlintrc.json": '{\n  "categories": { "correctness": "error" },\n  "rules": {\n    "no-console": "warn",\n    "eqeqeq": ["error", "always"]\n  }\n}\n',
            "docs/clippy.toml.md": "about clippy.toml\n",
        }
        p, _ = self.repo()
        for rel, text in files.items():
            p.write(rel, text)
        out = p.run(*SKIP).stdout
        self.assertEqual("PASS", status_of(out, "no new suppressions since"), out)

    def test_a_clippy_toml_fails_only_when_it_loosens_a_lint(self) -> None:
        # A clippy.toml that only tightens, such as a disallowed method that enforces a rule of the plugin, is fine.
        passes = {
            "msrv": 'msrv = "1.95"\n',
            "disallowed-methods": 'disallowed-methods = [{ path = "chrono::Utc::now", reason = "use the zone of the person" }]\n',
            "disallowed-types": 'disallowed-types = ["std::collections::HashMap"]\n',
            "disallowed-macros": 'disallowed-macros = [\n  "std::dbg",\n]\n',
            "mixed": 'msrv = "1.95"\ndisallowed-names = ["foo"]\ndoc-valid-idents = ["GSTIN"]\n',
        }
        for name, text in passes.items():
            with self.subTest(file=name):
                p, _ = self.repo()
                p.write("clippy.toml", text)
                self.assertEqual("PASS", self.suppression(p), "untracked")
                p.commit("add")
                self.assertEqual("PASS", self.suppression(p), "committed")
        fails = {
            "allow-": 'msrv = "1.95"\nallow-unwrap-in-tests = true\n',
            "allow-print": "allow-print-in-tests = true\n",
            "threshold": "type-complexity-threshold = 500\n",
            "indented": "  cognitive-complexity-threshold = 40\n",
        }
        for name, text in fails.items():
            with self.subTest(file=name):
                p, _ = self.repo()
                p.write(".clippy.toml", text)
                out = p.run(*SKIP).stdout
                self.assertEqual("FAIL", status_of(out, "no new suppressions since"), out)
                self.assertIn(".clippy.toml:", out)
        p, _ = self.repo({"clippy.toml": 'msrv = "1.95"\n'})
        p.write("clippy.toml", 'msrv = "1.95"\ncognitive-complexity-threshold = 40\n')
        self.assertEqual("FAIL", self.suppression(p), "a threshold added to an existing clippy.toml")

    def test_a_lint_setting_that_is_already_in_the_base_is_not_new(self) -> None:
        p, _ = self.repo({"Cargo.toml": '[lints.rust]\nunused = "allow"\n', "clippy.toml": 'msrv = "1.95"\n',
                          "web/tsconfig.json": '{\n  "strict": false\n}\n'})
        p.write("Cargo.toml", '[lints.rust]\nunused = "allow"\n\n[package]\nname = "x"\n')
        p.write("web/tsconfig.json", '{\n  "noEmit": true,\n  "strict": false\n}\n')
        p.write("clippy.toml", 'msrv = "1.96"\n')  # changed, not added
        self.assertEqual("PASS", self.suppression(p))

    def test_the_support_module_may_allow_dead_code_as_its_first_attribute_and_nothing_else(self) -> None:
        # Hard rule 15: each suite is a test binary of its own, so the shared helpers go unused in some of them.
        p, _ = self.repo()
        p.write("tests/support/mod.rs", "#![allow(dead_code)]\npub fn helper() {}\n")
        self.assertEqual("PASS", self.suppression(p))
        p.write("tests/support/mod.rs", "// helpers shared by the suites\n\n#![allow(dead_code)]\npub fn helper() {}\n")
        self.assertEqual("PASS", self.suppression(p))
        p.commit("support")
        self.assertEqual("PASS", self.suppression(p))
        refused = {
            "tests/support/mod.rs": ["#![deny(missing_docs)]\n#![allow(dead_code)]\n", "#![allow(dead_code, unused)]\n",
                                     "#[allow(dead_code)]\npub fn helper() {}\n", "pub fn helper() {}\n#![allow(dead_code)]\n"],
            "tests/security.rs": ["#![allow(dead_code)]\n"],
            "tests/support/other.rs": ["#![allow(dead_code)]\n"],
            "src/support/mod.rs": ["#![allow(dead_code)]\n"],
        }
        allowed = "#![allow(dead_code)]\npub fn helper() {}\n"
        for rel, texts in refused.items():
            for text in texts:
                with self.subTest(file=rel, text=text):
                    p.write(rel, text)
                    self.assertEqual("FAIL", self.suppression(p))
                    if rel == "tests/support/mod.rs":
                        p.write(rel, allowed)  # back to the one allowed form
                    else:
                        (p.root / rel).unlink()

    def test_as_any_counts_only_in_typescript_code(self) -> None:
        p, _ = self.repo()
        p.write("web/prose.ts", '// sign in as any role\nconst label = "log in as any user";\nconst tpl = `works as any`;\n/*\n * as any\n */\nconst ok = 1;\n')
        p.write("src/doc.rs", "/// treat it as any other value\n// as any\nfn f() {}\n")
        p.write("web/plain.js", "const a = b; // as any\n")
        self.assertEqual("PASS", self.suppression(p))
        p.write("web/code.ts", "const label = 'x'; const y = z as any; // fine\n")
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "no new suppressions since"))
        self.assertIn("web/code.ts:1:", out)
        self.assertNotIn("web/prose.ts", out)

    def test_a_suppression_added_to_a_tracked_file_without_a_commit_fails(self) -> None:
        p, _ = self.repo()
        p.write("src/main.rs", "fn main() {}\n#[allow(unused)]\nfn g() {}\n")
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "no new suppressions since"))
        self.assertIn("src/main.rs:2:", out)

    def test_a_suppression_fails_whether_untracked_staged_or_committed(self) -> None:
        p, _ = self.repo()
        p.write("src/lib.rs", "#[allow(dead_code)]\nfn unused() {}\n")  # untracked
        self.assertEqual("FAIL", self.suppression(p))
        p.git("add", "-A")  # staged
        self.assertEqual("FAIL", self.suppression(p))
        p.commit("add lib")  # committed
        self.assertEqual("FAIL", self.suppression(p))

    def test_generated_and_tool_folders_are_not_swept(self) -> None:
        p, _ = self.repo(front_end="none", api_types="web/lib/api/schema.d.ts")
        p.write("web/lib/api/schema.d.ts", "export type A = B as any;\n")
        p.write(".claude/skills/x/run.js", "// eslint-disable\n")
        p.write("node_modules/x/index.js", "// eslint-disable\n")
        p.write("target/gen.rs", "#[allow(dead_code)]\n")
        p.write("docs/notes.md", "#[allow(dead_code)] in prose\n")
        self.assertEqual("PASS", self.suppression(p))

    def test_the_plugin_and_a_verbatim_prototype_copy_are_not_swept(self) -> None:
        # A copied prototype may hold suppressions and must not be edited; in Codex the plugin sits inside the app.
        p, _ = self.repo()
        p.write("plugins/superdev/scripts/verify-done.mjs", "// eslint-disable-next-line\n")
        p.write("design/source/app.ts", "// @ts-ignore\nconst a = b as any;\n")
        p.write("docs/brief/prototype.tsx", "/* eslint-disable */\n")
        p.write("design/source/tsconfig.json", '{ "strict": false }\n')
        p.write("plugins/superdev/clippy.toml", "x = 1\n")
        self.assertEqual("PASS", self.suppression(p))  # untracked
        p.commit("copy the prototype")
        self.assertEqual("PASS", self.suppression(p))  # committed

    def test_only_the_named_folders_at_the_root_are_left_out_of_the_suppression_sweep(self) -> None:
        for rel in ("src/plugins/loader.rs", "design/sources/app.ts", "design/app.ts", "docs/briefs/a.ts", "docs/a.ts", "web/plugins/x.ts"):
            with self.subTest(file=rel):
                p, _ = self.repo()
                p.write(rel, "#[allow(dead_code)] // eslint-disable\n")
                p.commit("add")
                self.assertEqual("FAIL", self.suppression(p))

    def test_the_base_comes_from_the_flag_or_stack_and_is_not_guessed(self) -> None:
        p, base = self.repo(base_commit="")
        p.write("src/lib.rs", "#[allow(dead_code)]\n")
        out = p.run(*SKIP).stdout
        self.assertEqual("NOT RUN", status_of(out, "no new suppressions since"))
        self.assertIn("no base: set base_commit in STACK.md or pass --base", out)
        self.assertEqual("FAIL", status_of(p.run(*SKIP, "--base", base).stdout, "no new suppressions since"))
        out = p.run(*SKIP, "--base", "no-such-ref").stdout
        self.assertEqual("NOT RUN", status_of(out, "no new suppressions since"))
        self.assertIn("is not a commit", out)

    def test_outside_a_git_repository_the_suppression_check_is_not_run(self) -> None:
        p = Project(self)
        p.write("src/lib.rs", "#[allow(dead_code)]\n")
        p.write("STACK.md", stack_text(base_commit="abc1234"))
        out = p.run(*SKIP).stdout
        self.assertEqual("NOT RUN", status_of(out, "no new suppressions since"))
        self.assertIn("not a git repository", out)

    def test_raw_markup_in_a_navree_ui_source_fails(self) -> None:
        samples = {
            "script": 'let page = "<script>alert(1)</script>";\n',
            "style element": 'let page = "<style>a{}</style>";\n',
            "style attribute": 'let page = "<p style=\\"color:red\\">x</p>";\n',
            "class attribute": 'let page = "<div class=\\"ring\\">x</div>";\n',
            "event attribute": 'let page = "<button onclick=\\"go()\\">x</button>";\n',
        }
        for name, text in samples.items():
            with self.subTest(sample=name):
                p, _ = self.repo()
                p.write("src/ui/page.rs", text)
                out = p.run(*SKIP).stdout
                self.assertEqual("FAIL", status_of(out, "Navree UI raw markup"), out)
                self.assertIn("src/ui/page.rs:1:", out)
                self.assertIn("hard rule 14", out)

    def test_unquoted_attributes_in_a_tag_are_raw_markup(self) -> None:
        # The reader's case D: the quotes were left out.
        samples = {
            "style and onclick": 'fn f() { SafeHtml::trusted("<b style=color:red onclick=go()>due</b>"); }\n',
            "class": 'let page = "<p class=ring>x</p>";\n',
            "onclick alone": 'let page = "<a onclick=go()>x</a>";\n',
            "spaces around the equals sign": 'let page = "<td style = x>";\n',
            "tag with a dash": 'let page = "<my-tag class=a>";\n',
            "upper case": 'let page = "<DIV CLASS=a>";\n',
            "an attribute string of its own": 'let attrs = " class=\\"ring\\"";\n',
        }
        for name, text in samples.items():
            with self.subTest(sample=name):
                p, _ = self.repo()
                p.write("src/ui/badge.rs", text)
                out = p.run(*SKIP).stdout
                self.assertEqual("FAIL", status_of(out, "Navree UI raw markup"), out)
                self.assertIn("src/ui/badge.rs:1:", out)

    def test_ordinary_rust_is_not_raw_markup(self) -> None:
        p, _ = self.repo()
        p.write("src/ui/plain.rs", (
            "use std::collections::HashMap;\n"
            "pub struct Page<T> { rows: Vec<Option<T>> }\n"
            "impl<T> Page<T> {\n"
            "    pub fn once(&self) -> usize { let style = 1; let class = 2; style + class }\n"
            "}\n"
            "pub fn count(a: &HashMap<String, u32>) -> u32 { let one = 1; if one < 2 { one } else { 0 } }\n"
            "pub fn convert<T: Default>(class: T) -> T { let onclick = class; onclick }\n"
        ))
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))

    def test_raw_markup_judges_only_what_the_build_added_when_there_is_a_base(self) -> None:
        legacy = 'fn old() -> &\'static str { "<div class=\\"old\\"><style>a{}</style></div>" }\n'
        p, _ = self.repo({"src/legacy.rs": legacy})
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"), "markup written before the build is not judged")
        p.write("src/legacy.rs", legacy + "fn fine() {}\n")
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"), "an unrelated line added to the file")
        p.write("src/legacy.rs", legacy + 'fn new() -> &\'static str { "<span style=\\"x\\">" }\n')
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "Navree UI raw markup"))
        self.assertIn("src/legacy.rs:2:", out)
        self.assertNotIn("src/legacy.rs:1:", out)
        p.commit("add")
        self.assertEqual("FAIL", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))

    def test_raw_markup_reads_all_of_src_without_a_base(self) -> None:
        p, _ = self.repo({"src/legacy.rs": 'fn old() -> &\'static str { "<style>a{}</style>" }\n'}, base_commit="")
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "Navree UI raw markup"), out)
        self.assertIn("src/legacy.rs:1:", out)
        p.write("src/legacy.rs", "fn old() {}\n")
        out = p.run(*SKIP).stdout
        self.assertEqual("PASS", status_of(out, "Navree UI raw markup"))
        self.assertIn("warning: no base, so all of src/ was read", out)

    def test_raw_markup_skips_comments_tests_and_mail(self) -> None:
        p, _ = self.repo()
        p.write("src/ui/notes.rs", "// a <script> tag is never written here\nfn page() {}\n")
        p.write("src/tests/page.rs", 'let html = "<script>";\n')
        p.write("src/mail/welcome.rs", 'let html = "<style>a{}</style>";\n')
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))

    def test_a_loose_script_or_html_script_added_since_the_base_fails(self) -> None:
        for rel, text in (("src/assets/x.js", "let a = 1;\n"), ("scripts/run.mjs", "export {};\n"), ("public/index.html", "<script src=a.js></script>\n")):
            with self.subTest(file=rel):
                p, _ = self.repo()
                p.write(rel, text)
                self.assertEqual("FAIL", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))
                p.commit("add")
                self.assertEqual("FAIL", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))
        p, _ = self.repo()
        for rel in ("web/app.js", "clients/a/b.mjs", "tests/e2e.js", "design/source/x.html", "docs/x.html"):
            p.write(rel, "<script>1</script>\n" if rel.endswith(".html") else "let a = 1;\n")
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))

    def test_scripts_under_plugins_are_allowed_but_only_at_the_root(self) -> None:
        # In Codex the plugin's own files, verify-done.mjs among them, sit inside the app.
        p, _ = self.repo()
        p.write("plugins/superdev/scripts/verify-done.mjs", "export {};\n")
        p.write("plugins/superdev/scripts/other.js", "let a = 1;\n")
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))
        p.commit("add the plugin")
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))
        p.write("src/plugins/loader.js", "let a = 1;\n")
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "Navree UI raw markup"))
        self.assertIn("src/plugins/loader.js:1:", out)

    def test_a_clean_tree_passes_and_without_a_base_the_pass_carries_a_warning(self) -> None:
        p, _ = self.repo()
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "Navree UI raw markup"))
        p.write("STACK.md", stack_text(base_commit=""))
        out = p.run(*SKIP).stdout
        self.assertEqual("PASS", status_of(out, "Navree UI raw markup"))
        self.assertIn("warning: no base, so all of src/ was read", out)
        self.assertEqual(1, p.run(*SKIP, "--strict").returncode)

    def test_raw_markup_and_gap_rows_are_checked_only_for_navree_ui(self) -> None:
        for front_end in ("none", "next"):
            p, _ = self.repo({"src/main.rs": 'let a = "<script>"; el("div");\n'}, front_end=front_end, web_dir="web",
                             openapi="openapi.json", api_types="web/lib/api/schema.d.ts")
            out = p.run(*SKIP).stdout
            self.assertIsNone(status_of(out, "Navree UI raw markup"), front_end)
            self.assertIsNone(status_of(out, "Navree UI gap rows"), front_end)

    def gap_status(self, p: Project) -> tuple[str | None, str]:
        out = p.run(*SKIP).stdout
        return status_of(out, "Navree UI gap rows"), out

    def test_a_building_block_in_a_file_no_gap_row_names_fails(self) -> None:
        blocks = {
            "SafeHtml::trusted": "let a = SafeHtml::trusted(html);\n",
            "Node::Raw": "let a = Node::Raw(text);\n",
            "Node::Static": "let a = Node::Static(text);\n",
            "el": 'let a = el("div").child(x);\n',
            "AppSheet": 'let sheet = AppSheet::new("balance.css");\n',
        }
        for name, text in blocks.items():
            with self.subTest(block=name):
                p, _ = self.repo()
                p.write("src/ui/balance.rs", "fn first() {}\n" + text)
                status, out = self.gap_status(p)
                self.assertEqual("FAIL", status, out)
                self.assertIn("src/ui/balance.rs:2:", out)
                self.assertIn(GAP_MESSAGE, out)
                self.assertEqual(1, p.run(*SKIP).returncode)
                p.write("EXECUTION_PLAN.md", plan_with_gap("`src/ui/balance.rs`"))
                self.assertEqual("PASS", self.gap_status(p)[0])
                p.commit("named")
                self.assertEqual("PASS", self.gap_status(p)[0])

    def test_an_app_stylesheet_added_or_changed_since_the_base_needs_a_gap_row(self) -> None:
        p, _ = self.repo({"src/ui/theme.css": ":root { --brand: #1f6f5c; }\n"})
        self.assertEqual("PASS", self.gap_status(p)[0], "a stylesheet that is in the base is not new")
        p.write("src/ui/balance.css", ".badge { border: 1px solid; }\n")
        status, out = self.gap_status(p)
        self.assertEqual("FAIL", status, out)
        self.assertIn("src/ui/balance.css:1: an app stylesheet", out)
        p.write("EXECUTION_PLAN.md", plan_with_gap("`src/ui/balance.css`"))
        self.assertEqual("PASS", self.gap_status(p)[0])
        p.write("src/ui/theme.css", ":root { --brand: #000000; }\n")  # changed, not added
        status, out = self.gap_status(p)
        self.assertEqual("FAIL", status)
        self.assertIn("src/ui/theme.css:1:", out)
        p.commit("change the theme")
        self.assertEqual("FAIL", self.gap_status(p)[0])

    def test_stylesheets_of_the_web_and_tool_folders_need_no_gap_row(self) -> None:
        p, _ = self.repo()
        for rel in ("web/app.css", "clients/m/src/a.css", "design/source/x.css", "docs/a.css", "qa/a.css", "audit/a.css",
                    "security/a.css", "node_modules/x/a.css", "plugins/superdev/a.css", ".claude/a.css", ".agents/a.css"):
            p.write(rel, "a { color: red; }\n")
        self.assertEqual("PASS", self.gap_status(p)[0])
        p.write("tests/a.css", "a { color: red; }\n")
        self.assertEqual("FAIL", self.gap_status(p)[0], "tests/ is not among the folders left out")

    def test_building_blocks_in_comments_tests_and_the_base_are_not_new(self) -> None:
        p, _ = self.repo({"src/ui/old.rs": 'fn old() { el("p"); }\n'})
        p.write("src/ui/notes.rs", "// SafeHtml::trusted(x) is explained here\n/// el(\"div\") too\nfn page() {}\n")
        p.write("src/tests/page.rs", "let a = Node::Raw(x);\n")
        p.write("tests/page.rs", "let a = Node::Raw(x);\n")
        p.write("crates/extras/tests/page.rs", "let a = SafeHtml::trusted(x);\n")
        p.write("plugins/superdev/helper.rs", "let a = SafeHtml::trusted(x);\n")
        p.write(".claude/helper.rs", "let a = SafeHtml::trusted(x);\n")
        p.write("target/generated.rs", "let a = SafeHtml::trusted(x);\n")
        p.git("add", "-f", "target/generated.rs")  # target/ is ignored; a tracked file there must still be left out
        p.write("src/ui/old.rs", 'fn old() { el("p"); }\nfn other() {}\n')
        self.assertEqual("PASS", self.gap_status(p)[0])
        p.write("src/ui/old.rs", 'fn old() { el("p"); }\nfn more() { el("b"); }\n')
        status, out = self.gap_status(p)
        self.assertEqual("FAIL", status)
        self.assertIn("src/ui/old.rs:2:", out)

    def test_a_building_block_is_found_in_every_rust_file_of_the_app(self) -> None:
        # The reader's cases A to C: a mail folder, a constant tag or an alias, and another crate of the app.
        files = {
            "A: a mail folder": ("src/ui/mail/ring.rs", 'fn ring() { el("div").attr("class", "ring").child(SafeHtml::trusted("<svg></svg>")); }\n'),
            "A: src/mail": ("src/mail/welcome.rs", "fn mail() { SafeHtml::trusted(body); }\n"),
            "B: a constant tag": ("src/ui/ring.rs", 'const DIV: &str = "div";\nfn ring() { el(DIV); }\n'),
            "B: an alias": ("src/ui/alias.rs", "use navree::ui::SafeHtml as Html;\nfn x() { Html::trusted(y); }\n"),
            "B: an import only": ("src/ui/import.rs", "use navree_ui::SafeHtml;\n"),
            "B: Node::Static as a pattern": ("src/ui/node.rs", "fn f(n: Node) { if let Node::Static(s) = n { s; } }\n"),
            "B: a sheet type": ("src/ui/sheet.rs", "fn s(sheet: &AppSheet) {}\n"),
            "C: another crate": ("crates/extras/src/lib.rs", "pub fn x() { SafeHtml::trusted(y); }\n"),
            "C: a build script": ("build.rs", "fn main() { SafeHtml::trusted(y); }\n"),
            "C: a module outside src": ("modules/billing/src/page.rs", 'pub fn x() { el("p"); }\n'),
        }
        for name, (rel, text) in files.items():
            with self.subTest(case=name):
                p, _ = self.repo()
                p.write(rel, text)
                out = p.run(*SKIP).stdout
                self.assertEqual("FAIL", status_of(out, "Navree UI gap rows"), out)
                self.assertIn(f"{rel}:", out)
                p.write("EXECUTION_PLAN.md", plan_with_gap(f"`{rel}`"))
                self.assertEqual("PASS", self.gap_status(p)[0], "a table row that names the file settles it")

    def test_a_path_written_in_prose_or_a_list_does_not_name_a_file(self) -> None:
        # The reader's case D: the file's path is in the gap section, but not in a row of its table.
        p, _ = self.repo()
        p.write("src/ui/badge.rs", 'fn b() { SafeHtml::trusted("<b>due</b>"); }\n')
        sections = {
            "prose": "None. Files looked at: src/ui/badge.rs.\n",
            "a list item": "- N-1 composed from Badge, in `src/ui/badge.rs`\n",
            "a heading": "### N-1 `src/ui/badge.rs`\n",
            "a table without the id": "| Screen | Files |\n|---|---|\n| Customers | `src/ui/badge.rs` |\n",
            "a row of another section": "None.\n",
        }
        for name, section in sections.items():
            with self.subTest(section=name):
                plan = PLAN.replace("## Navree UI gaps\nNone.\n", "## Navree UI gaps\n" + section)
                if name == "a row of another section":
                    plan = plan.replace("## Open items\nNone.\n", "## Open items\n| N-1 | x | y | z | w | `src/ui/badge.rs` | A, 2026-11-20 |\n")
                p.write("EXECUTION_PLAN.md", plan)
                status, out = self.gap_status(p)
                self.assertEqual("FAIL", status, out)
        p.write("EXECUTION_PLAN.md", plan_with_gap("`src/ui/badge.rs`"))
        self.assertEqual("PASS", self.gap_status(p)[0])
        p.write("EXECUTION_PLAN.md", plan_with_gap("`src/ui/badge.rs`").replace("| N-1 |", "|N-12|"))
        self.assertEqual("PASS", self.gap_status(p)[0], "any N-n id, with or without spaces around it")

    def test_the_reader_s_case_d_fails_both_ui_checks(self) -> None:
        p, _ = self.repo()
        p.write("src/ui/badge.rs", 'fn b() { SafeHtml::trusted("<b style=color:red onclick=go()>due</b>"); }\n')
        p.write("EXECUTION_PLAN.md", PLAN.replace("## Navree UI gaps\nNone.\n", "## Navree UI gaps\nNone. Files looked at: src/ui/badge.rs.\n"))
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "Navree UI raw markup"), out)
        self.assertEqual("FAIL", status_of(out, "Navree UI gap rows"), out)
        self.assertEqual(1, p.run(*SKIP).returncode)

    def test_a_word_that_only_looks_like_a_building_block_is_fixed_or_named_and_the_message_says_how(self) -> None:
        # A correct app can match by chance: a variable called el, a Spanish string, an import it does not use.
        for text in ("fn f(items: &[Item]) { for el in items { show(el); } }\n", 'let label = "el total";\n',
                     "use navree_ui::SafeHtml;\n"):
            with self.subTest(text=text):
                p, _ = self.repo()
                p.write("src/ui/list.rs", text)
                status, out = self.gap_status(p)
                self.assertEqual("FAIL", status, out)
                detail = detail_of(out, "Navree UI gap rows")
                self.assertIn("src/ui/list.rs:1:", detail)
                self.assertIn(GAP_MESSAGE, detail)
                self.assertIn("## Navree UI gaps", detail)
                self.assertIn("hard rule 14", detail)
                self.assertIn("renaming or removing it", detail)
                self.assertIn("a variable called el", detail)
                p.write("src/ui/list.rs", "fn f(items: &[Item]) { for item in items { show(item); } }\n")
                self.assertEqual("PASS", self.gap_status(p)[0], "renamed, so no use is left")
                p.write("src/ui/list.rs", text)
                p.write("EXECUTION_PLAN.md", plan_with_gap("`src/ui/list.rs`"))
                self.assertEqual("PASS", self.gap_status(p)[0], "or named in a row")

    def test_the_path_must_be_named_in_the_gap_section_whole(self) -> None:
        p, _ = self.repo()
        p.write("src/ui/balance.rs", 'fn b() { el("div"); }\n')
        for files in ("`src/ui/balance.rs.bak`", "`src/ui/balance.rs2`", "`app/src/ui/balance.rs`", "`src/ui/balance_rs`", "none"):
            with self.subTest(files=files):
                p.write("EXECUTION_PLAN.md", plan_with_gap(files))
                self.assertEqual("FAIL", self.gap_status(p)[0])
        p.write("EXECUTION_PLAN.md", PLAN.replace("`GET /sign-in`.", "`GET /sign-in`; src/ui/balance.rs."))  # named under ## Access
        self.assertEqual("FAIL", self.gap_status(p)[0], "a path named outside ## Navree UI gaps does not count")
        for files in ("src/ui/balance.rs", "`src/ui/balance.rs`, `src/ui/other.rs`", "see src/ui/balance.rs."):
            with self.subTest(files=files):
                p.write("EXECUTION_PLAN.md", plan_with_gap(files))
                self.assertEqual("PASS", self.gap_status(p)[0])

    def test_gap_rows_need_a_base_and_say_so_when_the_plan_is_missing(self) -> None:
        p, _ = self.repo(base_commit="")
        p.write("src/ui/balance.rs", 'fn b() { el("div"); }\n')
        out = p.run(*SKIP).stdout
        self.assertEqual("NOT RUN", status_of(out, "Navree UI gap rows"))
        self.assertIn("needs a git repository and a base", out)
        p, _ = self.repo()
        p.write("src/ui/balance.rs", 'fn b() { el("div"); }\n')
        (p.root / "EXECUTION_PLAN.md").unlink()
        status, out = self.gap_status(p)
        self.assertEqual("FAIL", status)
        self.assertIn("EXECUTION_PLAN.md was not found.", out)
        p, _ = self.repo()
        (p.root / "EXECUTION_PLAN.md").unlink()
        self.assertEqual("PASS", self.gap_status(p)[0], "nothing needs a row, so a missing plan is not this check's failure")

    def test_placeholders_fail_in_product_code_and_pass_in_tests(self) -> None:
        p = Project(self)
        p.write("src/modules/notes.rs", "pub fn list() { todo!() }\n")
        self.assertEqual("FAIL", status_of(p.run().stdout, "no placeholder content"))
        for rel, text in {
            "src/modules/notes.rs": "pub fn list() { unimplemented!(\"x\") }\n",
            "web/components/card.tsx": "export const A = () => <p>Lorem ipsum dolor</p>;\n",
            "web/lib/data.ts": "export const mockData = [];\n",
            "clients/mobile/src/home.ts": "const t = 'Coming soon';\n",
        }.items():
            with self.subTest(file=rel):
                p = Project(self)
                p.write(rel, text)
                self.assertEqual("FAIL", status_of(p.run().stdout, "no placeholder content"))
        p = Project(self)
        p.write("src/modules/mod.rs", "pub fn list() {}\n")
        p.write("src/tests/notes.rs", "fn t() { todo!() }\n")
        p.write("web/components/__tests__/a.tsx", "const mockData = 1;\n")
        p.write("web/components/a.test.tsx", "const mockData = 1;\n")
        p.write("web/components/__tests__/mocks/handlers.ts", "export const handlers = [];\n")  # a test folder wins
        p.write("src/mocks/notes.rs", "pub fn fixture() {}\n")  # Rust test support is not a front-end mock path
        p.write("clients/mobile/src/a.stories.tsx", "const t = 'coming soon';\n")
        out = p.run().stdout
        self.assertEqual("PASS", status_of(out, "no placeholder content"), out)

    def test_a_file_in_a_mocks_or_fixtures_folder_of_the_front_end_is_a_hit(self) -> None:
        for rel in ("web/lib/mocks/handlers.ts", "web/lib/fixtures/users.json", "web/components/mock/card.tsx",
                    "web/app/fixtures/seed.ts", "web/modules/crm/fixtures/rows.ts", "clients/mobile/src/mocks/api.ts",
                    "clients/mobile/src/fixtures/accounts.json"):
            with self.subTest(file=rel):
                p = Project(self)
                p.write(rel, "export const handlers = [];\n")
                out = p.run().stdout
                self.assertEqual("FAIL", status_of(out, "no placeholder content"), out)
                self.assertIn(f"{rel}:1:", out)
                self.assertIn("no mock data path stays in the app", out)
        p = Project(self)
        p.write("web/lib/format.ts", "export const money = 1;\n")
        p.write("web/lib/mocks-are-not-a-folder.ts", "export {};\n")
        p.write("web/lib/mockery.ts", "export {};\n")
        self.assertEqual("PASS", status_of(p.run().stdout, "no placeholder content"))

    def test_placeholders_are_not_run_without_a_source_folder(self) -> None:
        p = Project(self)
        p.write("tests/notes.rs", "fn t() { todo!() }\n")
        out = p.run().stdout
        self.assertEqual("NOT RUN", status_of(out, "no placeholder content"))
        self.assertIn("no source folders found", out)


@needs_node
@needs_git
class PublicRoutesTests(unittest.TestCase):
    """Hard rule 6: the public routes of `navree routes --json` are the plan's list."""

    @staticmethod
    def routes(*routes: tuple[str, str, str]) -> dict:
        listed = [{"method": m, "path": p, "name": None, "access": a, "module": "app", "page": False} for m, p, a in routes]
        return {**GREEN, "navree routes --json": {"stdout": json.dumps(listed, indent=2) + "\n"}}

    def run_with(self, plan: str | None, *routes: tuple[str, str, str]) -> str:
        p = Project(self)
        p.write("STACK.md", stack_text())
        if plan is not None:
            p.write("EXECUTION_PLAN.md", plan)
        return p.run(*SKIP, tools=self.routes(*routes)).stdout

    def test_every_public_route_is_named_in_the_access_section(self) -> None:
        out = self.run_with(PLAN, ("GET", "/health/live", "public"), ("GET", "/health/ready", "public"), ("GET", "/sign-in", "public"),
                            ("GET", "/customers", "auth"), ("POST", "/api/v1/invoices/{id}/send", "can:send Invoice from id"))
        self.assertEqual("PASS", status_of(out, "public routes"), out)
        self.assertIn("3 public route(s)", out)

    def test_a_public_route_the_plan_does_not_name_fails_and_is_listed(self) -> None:
        out = self.run_with(PLAN, ("GET", "/sign-in", "public"), ("GET", "/secret/export", "public"), ("POST", "/hook", "public"))
        self.assertEqual("FAIL", status_of(out, "public routes"), out)
        detail = detail_of(out, "public routes")
        self.assertIn("GET /secret/export", detail)
        self.assertIn("POST /hook", detail)
        self.assertNotIn("GET /sign-in", detail)
        self.assertIn("(hard rule 6)", detail)

    def test_without_the_plan_the_check_is_not_run(self) -> None:
        out = self.run_with(None, ("GET", "/secret", "public"))
        self.assertEqual("NOT RUN", status_of(out, "public routes"))
        self.assertIn("no EXECUTION_PLAN.md", detail_of(out, "public routes"))

    def test_the_method_counts_as_well_as_the_path(self) -> None:
        # A POST route made public by mistake must not pass because the plan lists the GET route of the same path.
        plan = PLAN.replace("`GET /sign-in`.", "`GET /sign-in`, `GET /share/{token}`.")
        self.assertEqual("PASS", status_of(self.run_with(plan, ("GET", "/share/{token}", "public")), "public routes"))
        out = self.run_with(plan, ("GET", "/share/{token}", "public"), ("POST", "/share/{token}", "public"), ("DELETE", "/sign-in", "public"))
        self.assertEqual("FAIL", status_of(out, "public routes"), out)
        detail = detail_of(out, "public routes")
        self.assertIn("POST /share/{token}", detail)
        self.assertIn("DELETE /sign-in", detail)
        self.assertNotIn("GET /share/{token}", detail)
        self.assertIn("`METHOD path`", detail)

    def test_a_route_is_named_only_as_method_and_path_in_backticks(self) -> None:
        for access in ("- Public routes: GET /secret.\n", "- Public routes: `/secret` (GET).\n", "- Public routes: `GET`, `/secret`.\n",
                       "- Public routes: owner / admin and GET /secret.\n", "- Public routes: `GET /secret/x`.\n", "- Public routes: `get /secret`.\n"):
            with self.subTest(access=access):
                plan = PLAN.replace("- Public routes: `GET /health/live`, `GET /health/ready`, `GET /sign-in`.\n", access)
                self.assertEqual("FAIL", status_of(self.run_with(plan, ("GET", "/secret", "public")), "public routes"))
        plan = PLAN.replace("`GET /sign-in`.", "`GET /sign-in`, `GET   /secret`, `HEAD /secret`.")
        self.assertEqual("PASS", status_of(self.run_with(plan, ("GET", "/secret", "public"), ("HEAD", "/secret", "public")), "public routes"))

    def test_a_lone_slash_in_the_access_section_does_not_name_the_root_route(self) -> None:
        prose = PLAN.replace("`GET /sign-in`.", "`GET /sign-in`. Workspace roles: owner / admin / member.")
        self.assertEqual("FAIL", status_of(self.run_with(prose, ("GET", "/", "public")), "public routes"))
        named = PLAN.replace("`GET /sign-in`.", "`GET /sign-in`, `GET /`.")
        self.assertEqual("PASS", status_of(self.run_with(named, ("GET", "/", "public")), "public routes"))

    def test_only_public_access_counts_and_a_path_is_named_whole(self) -> None:
        plan = PLAN.replace("`GET /sign-in`.", "`GET /sign-in`, `GET /a/b`, `GET /` and `GET /docs/{id}`.")
        self.assertEqual("PASS", status_of(self.run_with(plan, ("GET", "/", "public"), ("GET", "/a/b", "public"), ("GET", "/docs/{id}", "public"),
                                                          ("GET", "/private", "auth"), ("GET", "/staff", "roles:admin"), ("GET", "/x", "permissions:a.b")), "public routes"))
        for path in ("/a", "/a/b/c", "/docs", "/sign-in/x", "/doc"):
            with self.subTest(path=path):
                self.assertEqual("FAIL", status_of(self.run_with(plan, ("GET", path, "public")), "public routes"))
        self.assertEqual("FAIL", status_of(self.run_with(PLAN.replace("`GET /health/live`, ", ""), ("GET", "/health/live", "public")), "public routes"))

    def test_only_the_access_section_is_read_and_a_public_word_inside_another_access_does_not_count(self) -> None:
        elsewhere = PLAN.replace("## Open items\nNone.\n", "## Open items\n- O-1 `GET /secret` is public for now.\n")
        self.assertEqual("FAIL", status_of(self.run_with(elsewhere, ("GET", "/secret", "public")), "public routes"))
        self.assertEqual("PASS", status_of(self.run_with(PLAN, ("GET", "/x", "can:read PublicPage from id"), ("GET", "/y", "none")), "public routes"))
        self.assertEqual("FAIL", status_of(self.run_with(PLAN, ("GET", "/z", "public auth")), "public routes"))

    def test_log_lines_before_the_list_are_skipped(self) -> None:
        listed = json.dumps([{"method": "GET", "path": "/secret", "access": "public"}], indent=2)
        for before in ("[INFO] app started\n", "starting\n", "[2026-11-15T10:00:00Z] boot\n[WARN] x\n"):
            with self.subTest(before=before):
                p = Project(self)
                p.write("STACK.md", stack_text())
                p.write("EXECUTION_PLAN.md", PLAN)
                out = p.run(*SKIP, tools={**GREEN, "navree routes --json": {"stdout": before + listed + "\n"}}).stdout
                self.assertEqual("FAIL", status_of(out, "public routes"), out)
                self.assertIn("GET /secret", detail_of(out, "public routes"))

    def test_log_lines_after_the_list_are_skipped(self) -> None:
        # Navree logs to standard output for commands that do not own it, so the list may be followed by a log line.
        items = [{"method": "GET", "path": "/secret", "access": "public"}, {"method": "GET", "path": "/sign-in", "access": "public"}]
        for after in ("[INFO] done\n", "2026-11-15T10:00:00Z INFO routes listed\n", "[2026-11-15] 2 routes\n[WARN] x\n", "\n\n"):
            for shape in (json.dumps(items, indent=2), json.dumps(items), "[]"):
                with self.subTest(after=after, shape=shape[:12]):
                    p = Project(self)
                    p.write("STACK.md", stack_text())
                    p.write("EXECUTION_PLAN.md", PLAN)
                    out = p.run(*SKIP, tools={**GREEN, "navree routes --json": {"stdout": shape + "\n" + after}}).stdout
                    if shape == "[]":
                        self.assertEqual("PASS", status_of(out, "public routes"), out)
                    else:
                        self.assertEqual("FAIL", status_of(out, "public routes"), out)
                        self.assertIn("GET /secret", detail_of(out, "public routes"))
                        self.assertNotIn("GET /sign-in", detail_of(out, "public routes"))

    def test_a_routes_command_that_fails_or_prints_no_list_fails_the_check(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text())
        p.write("EXECUTION_PLAN.md", PLAN)
        out = p.run(*SKIP, tools={**GREEN, "navree routes --json": {"exit": 1, "stderr": "database unreachable\n"}}).stdout
        self.assertEqual("FAIL", status_of(out, "public routes"))
        self.assertIn("navree routes --json failed", out)
        self.assertIn("database unreachable", out)
        out = p.run(*SKIP, tools={**GREEN, "navree routes --json": {"stdout": "no routes here\n"}}).stdout
        self.assertEqual("FAIL", status_of(out, "public routes"))
        self.assertIn("did not print a JSON list", out)


@needs_node
@needs_git
class WebAndContractTests(unittest.TestCase):
    NEXT = dict(front_end="next", kit="saas", web_dir="web", openapi="openapi.json", api_types="web/lib/api/schema.d.ts")
    DRIFT = {
        **GREEN,
        "navree openapi:export": {"write": {"openapi.json": '{"openapi": "3.1.0"}\n'}},
        "navree openapi:client --input openapi.json --out web/lib/api": {"write": {"web/lib/api/schema.d.ts": "export type Api = 1;\n"}},
    }

    @needs_npm
    def test_web_scripts_run_through_the_lockfile_package_manager(self) -> None:
        p = Project(self)
        ok = 'node -e "process.exit(0)"'
        scripts = {"typecheck": ok, "lint": ok, "test": 'node -e "process.exit(1)"', "build": ok}
        p.write("web/package.json", json.dumps({"name": "web", "private": True, "scripts": scripts}))
        p.write("web/package-lock.json", json.dumps({"name": "web", "lockfileVersion": 3, "packages": {}}))
        p.write("STACK.md", stack_text(**self.NEXT))
        out = p.run("--skip-boot", "--skip-build").stdout
        self.assertEqual("PASS", status_of(out, "web typecheck"), out)
        self.assertEqual("PASS", status_of(out, "web lint"))
        self.assertEqual("FAIL", status_of(out, "web test"))
        self.assertEqual("NOT RUN", status_of(out, "web build"))

    def test_a_missing_typecheck_script_fails_and_a_missing_lint_test_or_build_script_is_not_run(self) -> None:
        p = Project(self)
        p.write("web/package.json", json.dumps({"name": "web", "scripts": {}}))
        p.write("STACK.md", stack_text(**self.NEXT))
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "web typecheck"))
        self.assertIn('defines no "typecheck" script', out)
        for name in ("lint", "test", "build"):
            self.assertEqual("NOT RUN", status_of(out, f"web {name}"), name)
            self.assertIn(f'defines no "{name}" script', detail_of(out, f"web {name}"))
        self.assertEqual(1, p.run(*SKIP, "--strict").returncode)

    def test_without_a_package_json_the_scripts_are_not_found(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text(**self.NEXT))
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "web typecheck"))
        self.assertIn("web/package.json not found", out)
        self.assertEqual("NOT RUN", status_of(out, "web lint"))

    def drift_repo(self, committed_types: str = "export type Api = 1;\n") -> Project:
        p = Project(self)
        p.init_git()
        p.write("openapi.json", '{"openapi": "3.1.0"}\n')
        p.write("web/lib/api/schema.d.ts", committed_types)
        p.write("STACK.md", stack_text(**self.NEXT))
        p.commit("base")
        p.tools = self.DRIFT
        return p

    def test_contract_drift_passes_when_the_regenerated_files_equal_the_committed_ones(self) -> None:
        p = self.drift_repo()
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "API contract drift"))

    def test_contract_drift_fails_when_the_regenerated_files_differ_from_the_commit(self) -> None:
        p = self.drift_repo("export type Api = 0;\n")
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "API contract drift"), out)
        self.assertIn("web/lib/api/schema.d.ts", out)
        self.assertIn("review and commit them (hard rule 17)", out)

    def test_contract_drift_compares_with_the_last_commit_not_the_index(self) -> None:
        # The regenerated file is staged but not committed: the index agrees with it, the commit does not.
        p = self.drift_repo("export type Api = 0;\n")
        p.write("web/lib/api/schema.d.ts", "export type Api = 1;\n")
        p.git("add", "web/lib/api/schema.d.ts")
        self.assertEqual("FAIL", status_of(p.run(*SKIP).stdout, "API contract drift"))
        p.commit("commit the regenerated types")
        self.assertEqual("PASS", status_of(p.run(*SKIP).stdout, "API contract drift"))

    def test_contract_drift_fails_for_a_file_that_is_not_tracked(self) -> None:
        p = self.drift_repo()
        p.git("rm", "-q", "--cached", "openapi.json")
        out = p.run(*SKIP).stdout
        self.assertEqual("FAIL", status_of(out, "API contract drift"))
        self.assertIn("not tracked by git: openapi.json", out)

    def test_contract_drift_is_not_run_outside_git_or_before_a_first_commit_and_never_passes_without_navree(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text(**self.NEXT))
        self.assertEqual("NOT RUN", status_of(p.run(*SKIP).stdout, "API contract drift"))
        p.init_git()
        self.assertEqual("NOT RUN", status_of(p.run(*SKIP).stdout, "API contract drift"))
        self.assertIn("no commit yet", p.run(*SKIP).stdout)
        p.write("openapi.json", "{}\n")
        p.write("web/lib/api/schema.d.ts", "export {};\n")
        p.commit("base")
        self.assertEqual("FAIL", status_of(p.run(*SKIP).stdout, "API contract drift"))
        out = p.run(*SKIP, tools={**GREEN, "navree openapi:export": {"exit": 1, "stderr": "no app here\n"}}).stdout
        self.assertEqual("FAIL", status_of(out, "API contract drift"))
        self.assertIn("navree openapi:export failed", out)


@needs_node
class BootTests(unittest.TestCase):
    """The boot check, with a copy of node standing in for the release binary: `<binary> serve` runs serve.js."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server, cls.url = start_health_server()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def app(self, serve_js: str) -> Project:
        p = Project(self)
        p.write("STACK.md", stack_text())
        p.copy_node_as_binary(serve_js)
        return p

    def test_a_binary_that_answers_live_and_ready_passes(self) -> None:
        out = self.app(HEALTH_SERVER).run("--skip-build").stdout
        self.assertEqual("PASS", status_of(out, "boot (release binary + health)"), out)
        self.assertIn("/health/live says up", out)

    def test_a_binary_that_exits_fails_with_its_log_and_no_note_about_the_address(self) -> None:
        out = self.app('console.error("cannot connect to the database"); process.exit(3);\n').run("--skip-build").stdout
        self.assertEqual("FAIL", status_of(out, "boot (release binary + health)"), out)
        for text in ("exited (3)", "cannot connect to the database"):
            self.assertIn(text, out)
        self.assertNotIn("APP_HTTP__ADDR", out)
        self.assertNotIn("--health-url", detail_of(out, "boot (release binary + health)"))

    def test_health_url_never_stands_in_for_the_binary_it_started(self) -> None:
        # Another app already answers at --health-url; the boot check must still judge the binary it started.
        p = self.app('console.error("boom"); process.exit(3);\n')
        out = p.run("--skip-build", "--health-url", f"{self.url}/health/ready").stdout
        self.assertEqual("FAIL", status_of(out, "boot (release binary + health)"), out)
        p = self.app(HEALTH_SERVER)
        out = p.run("--skip-build", "--health-url", f"{free_url()}/nothing-listens-here").stdout
        self.assertEqual("PASS", status_of(out, "boot (release binary + health)"), "the URL is for --suites only")

    def test_a_missing_binary_is_not_run_with_skip_build_and_a_failure_otherwise(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text())
        self.assertEqual("NOT RUN", status_of(p.run("--skip-build").stdout, "boot (release binary + health)"))
        self.assertEqual("FAIL", status_of(p.run().stdout, "boot (release binary + health)"))


@needs_node
class SuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server, cls.url = start_health_server()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    SECURITY = "cargo test --test security"
    ACCESS = "cargo test --test access"

    def suites(self, lines: tuple[str, ...], tools: dict | None = None, **stack: str) -> str:
        p = Project(self)
        p.write("STACK.md", stack_text(suites=lines, **stack))
        return p.run(*SKIP, "--suites", "--api-url", self.url, tools=tools if tools is not None else GREEN).stdout

    def test_suites_fail_when_nothing_listens(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text(suites=(self.SECURITY,)))
        out = p.run(*SKIP, "--suites", "--api-url", free_url(), tools={**GREEN, self.SECURITY: {}}).stdout
        self.assertEqual("FAIL", status_of(out, "suites: app running"), out)
        self.assertIsNone(status_of(out, "suite: "), "no suite runs against a dead app")

    def test_suites_need_a_stack_with_suite_lines(self) -> None:
        p = Project(self)
        self.assertEqual("FAIL", status_of(p.run("--suites").stdout, "suites"))
        p.write("STACK.md", stack_text())
        out = p.run(*SKIP, "--suites", "--api-url", self.url).stdout
        self.assertEqual("FAIL", status_of(out, "suites"))
        self.assertIn("no command under ## Suites", out)

    def test_each_cargo_test_line_runs_and_a_failing_one_fails_the_run(self) -> None:
        tools = {**GREEN, self.SECURITY: {}, self.ACCESS: {"exit": 101, "stderr": "test access::denied ... FAILED\n"},
                 "cargo test --test isolation -- --test-threads=1": {}}
        p = Project(self)
        p.write("STACK.md", stack_text(suites=(self.SECURITY, self.ACCESS, "cargo test --test isolation -- --test-threads=1")))
        res = p.run(*SKIP, "--suites", "--api-url", self.url, tools=tools)
        self.assertEqual("PASS", status_of(res.stdout, "suites: app running"), res.stdout)
        self.assertEqual("PASS", status_of(res.stdout, f"suite: {self.SECURITY}"))
        self.assertEqual("FAIL", status_of(res.stdout, f"suite: {self.ACCESS}"))
        self.assertEqual("PASS", status_of(res.stdout, "suite: cargo test --test isolation -- --test-threads=1"))
        self.assertIn("denied ... FAILED", res.stdout)
        self.assertEqual(1, res.returncode)

    def test_a_line_that_is_not_cargo_test_is_refused_and_runs_nothing(self) -> None:
        # A STACK.md changed in someone's pull request must not run anything but cargo test.
        refused = ('node -e "process.exit(0)"', "curl http://example.com/x.sh", "cargo build --release", "FOO=1 cargo test",
                   "cargo test && echo pwned", "cargo test; echo pwned", "cargo test | tee out", "cargo test > out.txt", "cargo test `id`",
                   "cargo test $(id)", "cargo test --test 'a b'", 'cargo test --test "a"', "cargotest", "cargo", "test cargo",
                   "cargo test --test a\\b", "cargo test *")
        out = self.suites(refused, tools={**GREEN, **{c: {} for c in refused}})
        for command in refused:
            with self.subTest(command=command):
                self.assertEqual("FAIL", status_of(out, f"suite: {command}"), out)
                self.assertRegex(detail_of(out, f"suite: {command}"), r"refused: a suite line (must start with cargo test|holds cargo test and its arguments only)")
        self.assertIn("refused: a suite line must start with cargo test", out)

    def test_the_test_database_url_is_exported_for_the_database_in_use(self) -> None:
        cases = (
            ("postgres", "NAVREE_TEST_POSTGRES_URL", "postgres://t"),
            ("timescaledb", "NAVREE_TEST_POSTGRES_URL", "postgres://t"),
            ("mysql", "NAVREE_TEST_MYSQL_URL", "mysql://t"),
        )
        for database, name, value in cases:
            with self.subTest(database=database):
                out = self.suites((self.SECURITY,), tools={**GREEN, self.SECURITY: {"expect_env": {name: value}}},
                                  database=database, test_database_url=value)
                self.assertEqual("PASS", status_of(out, f"suite: {self.SECURITY}"), out)
        wrong = self.suites((self.SECURITY,), tools={**GREEN, self.SECURITY: {"expect_env": {"NAVREE_TEST_MYSQL_URL": "x"}}},
                            database="postgres", test_database_url="postgres://t")
        self.assertEqual("FAIL", status_of(wrong, f"suite: {self.SECURITY}"), "postgres sets the postgres variable only")

    def test_health_url_replaces_the_default_probe_for_the_suites(self) -> None:
        p = Project(self)
        p.write("STACK.md", stack_text(suites=(self.SECURITY,)))
        res = p.run(*SKIP, "--suites", "--api-url", free_url(), "--health-url", f"{self.url}/health/ready", tools={**GREEN, self.SECURITY: {}})
        self.assertEqual("PASS", status_of(res.stdout, "suites: app running"), res.stdout)

    def test_a_green_run_with_suites_says_so(self) -> None:
        p, _ = repo(self, {"serve.js": HEALTH_SERVER}, database="sqlite", test_database_url="")
        p.write("STACK.md", stack_text(base_commit=p.git("rev-parse", "--short", "HEAD"), suites=(self.SECURITY,), database="sqlite", test_database_url=""))
        p.copy_node_as_binary(HEALTH_SERVER)
        res = p.run("--suites", "--strict", "--api-url", self.url, tools={**GREEN, self.SECURITY: {}})
        self.assertEqual(0, res.returncode, res.stdout)
        self.assertIn("DONE — all live checks and committed suites green. Browser, role and device evidence", res.stdout)


@needs_node
class TauriTests(unittest.TestCase):
    """The shell checks fail an open Tauri config and pass a locked-down one (the tree is clients/mobile)."""

    LOCKED_CONF = {"app": {"security": {"csp": {"default-src": "'self'"}}}}
    STRIPPED_CARGO = '[dependencies]\ntauri = { version = "2", features = [] }\n\n[profile.release]\nstrip = true\n'

    def run_on(self, conf: dict, capability: dict, cargo: str, *extra: str) -> subprocess.CompletedProcess[str]:
        p = Project(self)
        tauri = "clients/mobile/src-tauri"
        p.write("STACK.md", stack_text(front_end="none"))
        for rel, text in SKILL_FILES.items():
            p.write(rel, text)
        p.write("clients/mobile/package.json", '{"name": "mobile", "scripts": {}}')
        p.write(f"{tauri}/tauri.conf.json", json.dumps(conf))
        p.write(f"{tauri}/capabilities/default.json", json.dumps(capability))
        p.write(f"{tauri}/Cargo.toml", cargo)
        return p.run(*SKIP, *extra, tools=GREEN)

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
        res = self.run_on(self.LOCKED_CONF, self.http("https://api.example.com/*"),
                          '[dependencies]\ntauri = { version = "2", features = [] }\n')
        self.assertEqual(0, res.returncode, res.stdout)
        self.assertIn("CSP set", res.stdout)
        self.assertIn("clients/mobile/src-tauri CSP set", res.stdout)

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

    def test_debug_origins_in_release_are_a_warning(self) -> None:
        cap = self.http("https://api.example.com/*", "http://10.0.2.2:4100/*")
        res = self.run_on(self.LOCKED_CONF, cap, self.STRIPPED_CARGO)
        self.assertEqual(0, res.returncode, res.stdout)
        self.assertIn("warning:", res.stdout)
        self.assertIn("[PASS] clients/mobile/src-tauri debug origins in release capabilities", res.stdout)
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

    def test_an_unstripped_release_profile_and_global_tauri_are_warnings_not_failures(self) -> None:
        conf = {"app": {"withGlobalTauri": True, "security": {"csp": {"default-src": "'self'"}}}}
        res = self.run_on(conf, self.http("https://api.example.com/*"), '[dependencies]\ntauri = { version = "2" }\n')
        self.assertEqual(0, res.returncode, res.stdout)
        for label in ("withGlobalTauri", "release profile"):
            self.assertIn(f"[PASS] clients/mobile/src-tauri {label}", res.stdout)
        self.assertEqual(2, res.stdout.count("warning:"))
        self.assertEqual(1, self.run_on(conf, self.http("https://api.example.com/*"), self.STRIPPED_CARGO, "--strict").returncode)


if __name__ == "__main__":
    unittest.main()
