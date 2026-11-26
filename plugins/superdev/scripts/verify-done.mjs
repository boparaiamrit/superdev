#!/usr/bin/env node
// verify-done.mjs 3.2.0 — the live done check of a superdev build of a Navree app.
//
// Every check runs now, against the real tree and the real release binary; nothing is read
// from a file that grades itself. Plain Node 18 or newer, no dependencies, the same on Windows,
// Linux and macOS. Run it from the app root (or pass --root); --help lists the flags and
// every check. Exit 0: no check failed, which is not done: only a --suites --strict run whose last
// line is DONE means the build is done. Exit 1: a check failed (--strict also fails a warning and a
// NOT RUN); the report names the failing checks. Exit 2: a usage error. Fix at the root cause:
// suppressions fail here.

import { spawn, spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:net";
import { join, posix, relative, resolve, sep } from "node:path";

const VERSION = "3.2.0";
const MINUTE = 60_000;
const TIMEOUT = { cargo: 30 * MINUTE, navree: 10 * MINUTE, web: 10 * MINUTE, suite: 15 * MINUTE };
const MAX_BUFFER = 64 * 1024 * 1024;
const BOOT_WAIT_MS = 60_000;

const FLAGS = [
  ["--root DIR", "app root (default: the current directory)"],
  ["--fast", "only the checks that build nothing (STACK.md, navree CLI, skills, cargo fmt, the flow's files, the sweeps over source); the others print NOT RUN, so a fast run never ends DONE; not with --suites"],
  ["--skip-build", "do not run cargo build --release or the web build script (those checks print NOT RUN)"],
  ["--skip-boot", "do not boot the release binary (NOT RUN)"],
  ["--suites", "run the committed suites listed in STACK.md under ## Suites (each line must start with cargo test and boots its own app, so no app needs to be running)"],
  ["--base REF", "base commit for the suppression and raw-markup sweeps (default: base_commit in STACK.md)"],
  ["--strict", "every warning and every NOT RUN fails, and SECURITY_REPORT.md, AUDIT_REPORT.md, QA_COVERAGE.md and ACCEPTANCES.md are read; only a --strict run that ends DONE means the build is done, and without --suites it cannot: the suites are then NOT RUN"],
  ["--help", "print this text and exit 0"],
];
const VALUE_FLAGS = new Set(["--root", "--base"]);
const BOOL_FLAGS = new Set(["--fast", "--skip-build", "--skip-boot", "--suites", "--strict"]);
// Flags of 3.0.0 that named the running app the suites were sent to.
const REMOVED_FLAGS = new Set(["--api-url", "--health-url"]);

// The one list of checks in the plugin, in run order: label (when it runs): what it runs.
const CHECKS = [
  "STACK.md (always): present, every key there (new_command may be empty: the app existed before the build), front_end, kit and database inside their sets, test_database_url set for any database but sqlite",
  "navree CLI (STACK.md valid): navree --version prints navree <navree_version>",
  "navree skills installed (STACK.md valid): .claude/skills/navree/SKILL.md and .agents/skills/navree/SKILL.md exist",
  "cargo fmt (STACK.md valid): cargo fmt --all -- --check",
  "cargo clippy (STACK.md valid; not with --fast): cargo clippy --workspace --all-targets -- -D warnings",
  "cargo test (STACK.md valid; not with --fast): cargo test --workspace",
  "navree check (STACK.md valid; not with --fast): navree check, which needs config and a migrated database",
  "navree config:check (STACK.md valid; not with --fast): navree config:check",
  "release build (STACK.md valid; not with --fast): cargo build --release; NOT RUN with --skip-build",
  "public routes (STACK.md valid; not with --fast): <target>/release/<binary> routes --json, the binary the boot check starts (CARGO_TARGET_DIR is honoured), compared both ways with the plan: every public route is named as `METHOD path` in backticks in EXECUTION_PLAN.md ## Access, and every route listed in the bullet that starts Public routes is a public route of the binary (NOT RUN without the plan or the binary)",
  "boot (release binary + health) (STACK.md valid; not with --fast): <target>/release/<binary> serve on a free port of its own; /health/live says up, /health/ready answers 200",
  "first address (GET /) (STACK.md valid; not with --fast): GET / on that binary answers anything but 404 or a 5xx (a redirect or a 200 passes)",
  "web typecheck, web lint, web test, web build (front_end: next; not with --fast): the package scripts of web_dir; a missing lint, test or build script and build with --skip-build are NOT RUN",
  "API contract drift (front_end: next; not with --fast): navree openapi:export and openapi:client REWRITE the document and the types in the working tree, then git diff --exit-code HEAD on both",
  "Navree UI raw markup (front_end: navree): no script or style element and no style, class or on* attribute in a tag (quoted or not) in the src/*.rs lines added since the base, mail and tests folders excluded (all of src/ without a base); no loose script file added since the base",
  "Navree UI gap rows (front_end: navree): every Rust file of the app (outside target/, plugins/, .claude/, .agents/ and tests/ folders, mail folders and other crates included) in which a line added since the base uses SafeHtml, Node::Raw, Node::Static, el or AppSheet, and every .css file added or changed since the base, is named in the Files of a table row of EXECUTION_PLAN.md ## Navree UI gaps; prose does not name a file (NOT RUN without a base)",
  "<dir> CSP, HTTP capability scope, devtools and the other Tauri labels (a Tauri config within 4 levels): the Tauri shell checks",
  "no new suppressions since <base> (a git repository and a base): lines added since the base, committed or not, with allow, expect, cfg_attr(allow), eslint-disable, oxlint-disable, ts-ignore or as any in .ts and .tsx code, and lints turned off in Cargo.toml [lints], .cargo/config.toml rustflags, a clippy.toml allow-* or *-threshold key, an ESLint or oxlint rule set to off or 0, \"strict\": false in tsconfig; plugins/, design/source/ and docs/brief/ are left out, and so is #![allow(dead_code)] as the first attribute of tests/support/mod.rs",
  "no placeholder content (always, over the folders that exist): placeholder text and todo!() in src/*.rs, web/ and clients/*/src, tests excluded; any file in a mocks or fixtures folder of the front end",
  "plan confirmed (STACK.md valid): EXECUTION_PLAN.md has the line `Status: CONFIRMED by <name> on <YYYY-MM-DD>` (NOT RUN without the plan or while it is a draft)",
  "module dependency graph (STACK.md valid): EXECUTION_PLAN.md ## Modules forms an acyclic dependency graph with no unknown dependencies, no lower-tier module depending on a higher-tier module, and ## Build order listing every dependency before its dependents (hard rule 26)",
  "contracts agreed (STACK.md valid): every module of the plan's ## Modules has contracts/<module>.md with `Status: AGREED by <name> on <YYYY-MM-DD>` (NOT RUN for a missing or draft contract)",
  "contract stories (STACK.md valid): every agreed contracts/<module>.md holds a ## Stories table with non-empty Must pass and Must reject cases (hard rule 30)",
  "Cargo.lock committed (STACK.md valid, a git repository): Cargo.lock is tracked by git and not ignored (NOT RUN before cargo has written it)",
  "SECURITY_REPORT.md, AUDIT_REPORT.md, QA_COVERAGE.md (STACK.md valid): read under --strict only (NOT RUN without it): each exists; its ## Findings section holds a table with the columns Severity and State, or None.; no finding of a table with those columns is an open Blocker or Major, and a state `accepted ACC-n` names an entry of ACCEPTANCES.md; no table cell is NOT RUN, or PASS (server), without an ACC-n of ACCEPTANCES.md, nor a row of a Not run section; QA_COVERAGE.md has no FAIL cell",
  "acceptances (STACK.md valid): read under --strict only (NOT RUN without it): every module row of EXECUTION_PLAN.md ## Build order is PASS, or PASS (6.5 NOT RUN, ACC-n) with an ACC-n of ACCEPTANCES.md; each entry of ACCEPTANCES.md has its own number; the file is committed, and no commit changes it together with another file (git log --name-only, also for an app in a sub-folder of its repository)",
  "suite: <command> (--suites): each command under ## Suites runs as written (each boots its own app, so no running app is needed); a line must start with cargo test and holds no shell syntax; without --suites the one line `suites` is NOT RUN, so a --strict run does not end DONE",
];

const helpText = () => [
  `superdev verify-done ${VERSION}`,
  "",
  "Usage: node verify-done.mjs [flags]",
  "Runs every check now against the real tree and the real release binary of a Navree app, prints [PASS],",
  "[FAIL] or [NOT RUN] for each, and exits 0 (no check failed), 1 (a check failed) or 2 (usage error).",
  "Exit 0 is not done: only a --suites --strict run whose last line is DONE means the build is done.",
  "",
  "Flags:",
  ...FLAGS.map(([flag, text]) => `  ${flag.padEnd(18)}${text}`),
  "",
  "Checks, in the order they run:",
  ...CHECKS.map((c, i) => `  ${String(i + 1).padStart(2)}. ${c}`),
  "",
  "A check that passes for development but would not pass a release claim prints PASS with a detail line",
  "starting warning:; --strict turns every warning and every NOT RUN into a failure. An unknown flag, a",
  "flag missing its value, or --fast with --suites prints the usage to stderr and exits 2.",
  "",
].join("\n");

const USAGE = `Usage: node verify-done.mjs ${FLAGS.map(([f]) => `[${f}]`).join(" ")}`;

function parseArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--help") return { help: true };
    if (BOOL_FLAGS.has(arg)) {
      opts[arg] = true;
    } else if (VALUE_FLAGS.has(arg)) {
      const value = argv[++i];
      if (value === undefined || value.startsWith("--")) return { error: `${arg} needs a value` };
      opts[arg] = value;
    } else if (REMOVED_FLAGS.has(arg)) {
      return { error: `${arg} is no longer a flag: each suite boots its own app, so --suites needs no address` };
    } else {
      return { error: `${arg.startsWith("-") ? "unknown flag" : "unexpected argument"}: ${arg}` };
    }
  }
  if (opts["--fast"] && opts["--suites"]) return { error: "--fast and --suites contradict: a suite builds the app, and --fast runs only what builds nothing" };
  return { opts };
}

// ------------------------------------------------------------------ run state and helpers
let ROOT = process.cwd();
let SKIP_BUILD = false;
let SKIP_BOOT = false;
let FAST = false;
let STRICT = false;

const results = []; // {status: "PASS" | "FAIL" | "NOT RUN", label, detail?}
const record = (status, label, detail) => results.push({ status, label, detail });
const pass = (label, detail) => record("PASS", label, detail);
const fail = (label, detail) => record("FAIL", label, detail);
const notRun = (label, detail) => record("NOT RUN", label, detail);
// A pass that would not survive a release claim: --strict counts it as a failure.
const passWithWarning = (label, warning, detail) =>
  record("PASS", label, [`warning: ${warning}`, detail].filter(Boolean).join("\n"));
const isWarning = (r) => r.status === "PASS" && /^warning:/.test(r.detail ?? "");

const progress = (what) => process.stderr.write(`  running: ${what}\n`);
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const tail = (text, n = 12) => text.trim().split(/\r?\n/).slice(-n).join("\n");
const toRel = (path) => relative(ROOT, path).split(sep).join("/") || ".";
const posixPath = (p) => p.split("\\").join("/");
const capped = (hits) => (hits.length > 10 ? [...hits.slice(0, 10), `... and ${hits.length - 10} more`] : hits).join("\n");

function readText(path) {
  try { return readFileSync(path, "utf8").replace(/^\uFEFF/, ""); } catch { return null; }
}

function readJson(path) {
  try { return JSON.parse(readText(path)); } catch { return null; }
}

function isDir(path) {
  try { return statSync(path).isDirectory(); } catch { return false; }
}

function* walk(dir, suffixes) {
  const skip = new Set(["node_modules", ".next", "dist", "target", ".git"]);
  let entries;
  try { entries = readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!skip.has(entry.name)) yield* walk(path, suffixes);
    } else if (suffixes.some((s) => entry.name.endsWith(s))) {
      yield path;
    }
  }
}

// Lines of the given files that match the pattern, as "path:line: text".
function scanFiles(files, regex, { skipComments = false } = {}) {
  const hits = [];
  for (const file of files) {
    (readText(file) ?? "").split(/\r?\n/).forEach((line, i) => {
      if (skipComments && line.trimStart().startsWith("//")) return;
      if (regex.test(line)) hits.push(`${toRel(file)}:${i + 1}: ${line.trim().slice(0, 120)}`);
    });
  }
  return hits;
}

// Runs a program without a shell (cargo, navree) or, with shell true, a command line through it (package-manager
// scripts and suite lines; Windows needs the shell for .cmd shims).
function run(cmd, args, { cwd = ROOT, timeout, env, shell = false } = {}) {
  progress([cmd, ...args].join(" "));
  const options = { cwd, env: env ?? process.env, encoding: "utf8", timeout, maxBuffer: MAX_BUFFER, windowsHide: true };
  const res = shell ? spawnSync(cmd, { ...options, shell: true }) : spawnSync(cmd, args, options);
  const missing = res.error?.code === "ENOENT";
  const timedOut = res.error?.code === "ETIMEDOUT";
  const note = missing ? "was not found on PATH" : timedOut ? `timed out after ${Math.round(timeout / MINUTE)} minutes` : res.error?.message;
  return { ok: res.status === 0 && !res.error, status: res.status, stdout: res.stdout ?? "", out: `${res.stdout ?? ""}\n${res.stderr ?? ""}`.trim(), missing, note };
}

// What a failed command left: the last 12 lines of its output, or why it could not run.
const failureDetail = (cmd, r) =>
  r.note ? `${cmd} ${r.note}${r.missing ? "" : `\n${tail(r.out)}`}`.trim() : r.out ? tail(r.out) : `${cmd} exited with status ${r.status} and printed nothing`;

function programCheck(label, cmd, args, timeout, { onPass, extraFailure } = {}) {
  const r = run(cmd, args, { timeout });
  if (r.ok) pass(label, onPass?.(r));
  else fail(label, [failureDetail(cmd, r), r.missing ? "" : extraFailure].filter(Boolean).join("\n"));
}

function git(args) {
  const res = spawnSync("git", ["-C", ROOT, "-c", "core.quotePath=false", "-c", "color.ui=never", ...args], {
    encoding: "utf8", maxBuffer: MAX_BUFFER, windowsHide: true,
  });
  return { ok: res.status === 0, out: res.stdout ?? "" };
}

const isGitRepo = () => git(["rev-parse", "--git-dir"]).ok;
const isCommit = (ref) => git(["rev-parse", "--verify", "--quiet", `${ref}^{commit}`]).ok;
const untrackedFiles = () => git(["ls-files", "--others", "--exclude-standard", "-z"]).out.split("\0").filter(Boolean).map(posixPath);
// Files added or changed since the base (committed or not; `filter` is a git --diff-filter) and every untracked file.
const changedFiles = (base, filter) => [...new Set([
  ...git(["diff", "--name-only", `--diff-filter=${filter}`, "--relative", "-z", base, "--"]).out.split("\0").filter(Boolean).map(posixPath),
  ...untrackedFiles(),
])];

// Added lines of a zero-context diff as {file, line, text}.
function parseAddedLines(diff) {
  const out = [];
  let file = null;
  let line = 0;
  let inHunk = false;
  for (const raw of diff.split("\n")) {
    if (raw.startsWith("diff --git ")) {
      inHunk = false;
      file = null;
    } else if (!inHunk && raw.startsWith("+++ ")) {
      file = raw.slice(4).trimEnd() === "/dev/null" ? null : raw.slice(4).trimEnd().replace(/^b\//, "");
    } else if (raw.startsWith("@@")) {
      const m = raw.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (m) { line = Number(m[1]); inHunk = true; }
    } else if (inHunk && file && raw.startsWith("+")) {
      out.push({ file, line: line++, text: raw.slice(1).replace(/\r$/, "") });
    } else if (inHunk && raw.startsWith(" ")) {
      line++;
    }
  }
  return out;
}

let addedCache = null;
// Every line the build added since the base, in the files `wants` accepts: the added lines of the diff (committed or
// not) and every line of an untracked file.
function addedSince(base, wants) {
  if (addedCache?.base !== base) {
    addedCache = { base, lines: parseAddedLines(git(["diff", "--no-ext-diff", "-U0", "--relative", "--src-prefix=a/", "--dst-prefix=b/", base, "--"]).out) };
  }
  return [...addedCache.lines.filter((e) => wants(e.file)), ...untrackedFiles().filter(wants).flatMap(linesOf)];
}

const linesOf = (rel) => (readText(join(ROOT, rel)) ?? "").split(/\r?\n/).map((text, i) => ({ file: rel, line: i + 1, text }));
const asHit = (e) => `${e.file}:${e.line}: ${e.text.trim().slice(0, 120)}`;
// Whether `text` names the file or path `s` (not as the start or end of a longer path).
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const names = (text, s) => new RegExp(`(?<![\\w./-])${escapeRe(s)}(?![\\w/-]|\\.\\w)`).test(text);
// The text of one `## ` section of a Markdown file.
const sectionOf = (text, heading) => (text.match(new RegExp(`^##\\s+${heading}\\s*$([\\s\\S]*?)(?=^##\\s|(?![\\s\\S]))`, "m")) ?? [])[1] ?? "";

// ------------------------------------------------------------------ STACK.md
const STACK_KEYS = [
  "navree_version", "new_command", "front_end", "kit", "database", "binary", "clients",
  "base_commit", "test_database_url", "web_dir", "openapi", "api_types",
];
const STACK_SETS = {
  front_end: ["navree", "next", "none"],
  kit: ["none", "saas", "api"],
  database: ["timescaledb", "postgres", "mysql", "sqlite"],
};
const STACK_CLIENTS = ["web", "admin", "tauri-android", "tauri-ios", "tauri-desktop"];

function readStack() {
  const text = readText(join(ROOT, "STACK.md"));
  if (text === null) return { present: false, keys: {}, suites: [], problems: [] };
  const keys = {};
  const suites = [];
  let section = "head";
  for (const line of text.split(/\r?\n/).map((l) => l.trimEnd())) {
    if (/^##\s+Suites\b/.test(line)) section = "suites";
    else if (/^##\s/.test(line)) section = "other";
    else if (section === "head" && /^[a-z_]+:/.test(line)) keys[line.slice(0, line.indexOf(":"))] = line.slice(line.indexOf(":") + 1).trim();
    else if (section === "suites" && line.startsWith("- ") && line.slice(2).trim()) suites.push(line.slice(2).trim());
  }
  const problems = [];
  const missing = STACK_KEYS.filter((k) => !(k in keys));
  if (missing.length) problems.push(`missing key(s): ${missing.join(", ")}`);
  const empty = ["navree_version", "front_end", "kit", "database", "binary"].filter((k) => k in keys && !keys[k]);
  if (empty.length) problems.push(`empty value(s): ${empty.join(", ")}`);
  for (const [key, allowed] of Object.entries(STACK_SETS)) {
    if (keys[key] && !allowed.includes(keys[key])) problems.push(`${key}: "${keys[key]}" is not one of ${allowed.join(", ")}`);
  }
  const badClients = (keys.clients ?? "").split(",").map((c) => c.trim()).filter((c) => c && !STACK_CLIENTS.includes(c));
  if (badClients.length) problems.push(`clients: "${badClients.join(", ")}" is not in ${STACK_CLIENTS.join(", ")}`);
  const unset = keys.front_end === "next" ? ["web_dir", "openapi", "api_types"].filter((k) => k in keys && !keys[k]) : [];
  if (unset.length) problems.push(`front_end: next needs a value for ${unset.join(", ")}`);
  if (["timescaledb", "postgres", "mysql"].includes(keys.database) && "test_database_url" in keys && !keys.test_database_url) {
    problems.push(`test_database_url is empty: it is required for database ${keys.database} (only sqlite may leave it empty), or the real-database tests would pass without running`);
  }
  return { present: true, keys, suites, problems };
}

// ------------------------------------------------------------------ navree and cargo
function skillsInstalled() {
  const absent = [".claude/skills/navree/SKILL.md", ".agents/skills/navree/SKILL.md"].filter((p) => !existsSync(join(ROOT, p)));
  if (absent.length) fail("navree skills installed", `missing: ${absent.join(", ")}\nRun navree skills:install in the app root (hard rule 1).`);
  else pass("navree skills installed");
}

function navreeCli(stack) {
  const expected = `navree ${stack.keys.navree_version}`;
  const r = run("navree", ["--version"], { timeout: TIMEOUT.navree });
  const found = r.out.split(/\r?\n/)[0].trim();
  if (r.ok && found === expected) pass("navree CLI", found);
  else if (r.missing) fail("navree CLI", "navree was not found on PATH; install it with: cargo install navree-cli");
  else fail("navree CLI", `expected: ${expected}\nfound:    ${r.ok ? found : failureDetail("navree", r)}`);
}

function cargoTest() {
  programCheck("cargo test", "cargo", ["test", "--workspace"], TIMEOUT.cargo, {
    onPass: (r) => {
      const lines = r.out.split(/\r?\n/).filter((l) => l.startsWith("test result:"));
      return [...lines.slice(0, 8), ...(lines.length > 8 ? [`... and ${lines.length - 8} more test result lines`] : [])].join("\n") || undefined;
    },
  });
}

// ------------------------------------------------------------------ boot
const freePort = () => new Promise((done) => {
  const srv = createServer().once("error", () => done(0));
  srv.listen(0, "127.0.0.1", () => { const { port } = srv.address(); srv.close(() => done(port)); });
});

async function probe(url, timeout = 2000, init = {}) {
  try {
    const res = await fetch(url, { ...init, signal: AbortSignal.timeout(timeout) });
    return { status: res.status, body: await res.text(), text: `HTTP ${res.status}` };
  } catch (error) {
    return { status: 0, body: "", text: `no answer (${error?.cause?.code ?? error?.name ?? error})` };
  }
}

// The release binary of the app: <target>/release/<binary>, where cargo's target folder is CARGO_TARGET_DIR when it is set.
const releaseExe = (stack) => join(resolve(ROOT, process.env.CARGO_TARGET_DIR || "target"), "release", stack.keys.binary + (process.platform === "win32" ? ".exe" : ""));
const SKIPPED_BY_FAST = "skipped by --fast: it builds or boots the app";
const notRunByFlag = () => (FAST && !SKIP_BOOT ? SKIPPED_BY_FAST : "skipped by flag");

// GET / on the booted binary: the product's first address is owned, so it answers anything but 404 or a 5xx.
async function firstAddress(port) {
  const answer = await probe(`http://127.0.0.1:${port}/`, 5000, { redirect: "manual" });
  if (answer.status === 0) return { ok: false, detail: `GET / got ${answer.text}` };
  if (answer.status === 404 || answer.status >= 500) {
    return { ok: false, detail: `GET / answered HTTP ${answer.status}: no route owns the product's first address. Add a GET !/ route that lands on the product's first screen, or redirects to it, and name it in EXECUTION_PLAN.md ## Access (step 4 of superdev-build)` };
  }
  return { ok: true, detail: `GET / answered HTTP ${answer.status}` };
}

async function bootCheck(stack) {
  const label = "boot (release binary + health)";
  const homeLabel = "first address (GET /)";
  if (SKIP_BOOT || FAST) {
    notRun(label, notRunByFlag());
    return notRun(homeLabel, FAST && !SKIP_BOOT ? SKIPPED_BY_FAST : "skipped with the boot check");
  }
  const exe = releaseExe(stack);
  if (!existsSync(exe)) {
    if (SKIP_BUILD) notRun(label, `skipped: --skip-build was given and ${toRel(exe)} does not exist`);
    else fail(label, `${toRel(exe)} not found after the release build; check the binary key in STACK.md`);
    return notRun(homeLabel, "the release binary was not started");
  }
  const port = await freePort();
  const liveUrl = `http://127.0.0.1:${port}/health/live`;
  const readyUrl = `http://127.0.0.1:${port}/health/ready`;
  progress(`${toRel(exe)} serve (127.0.0.1:${port})`);
  const child = spawn(exe, ["serve"], {
    cwd: ROOT, env: { ...process.env, APP_HTTP__ADDR: `127.0.0.1:${port}` }, stdio: ["ignore", "pipe", "pipe"], windowsHide: true,
  });
  let log = "";
  let ended = null; // why the process is gone, once it is
  child.stdout.on("data", (d) => { log += d; });
  child.stderr.on("data", (d) => { log += d; });
  const gone = new Promise((done) => {
    child.once("exit", (code, signal) => { ended = `exited (${code ?? signal}) before the app answered`; done(); });
    child.once("error", (error) => { ended = `could not be started: ${error.message}`; done(); });
  });
  const isUp = (p) => p.status === 200 && p.body.replace(/\s/g, "").includes('"status":"up"');
  let live = { text: "not asked" };
  let ready = { text: "not asked" };
  let verdict = null;
  const deadline = Date.now() + BOOT_WAIT_MS;
  while (!verdict) {
    if (ended) {
      verdict = { ok: false, detail: `${toRel(exe)} ${ended}:\n${tail(log)}` };
    } else {
      if (!isUp(live)) live = await probe(liveUrl);
      if (isUp(live)) ready = await probe(readyUrl);
      if (ready.status === 200) verdict = { ok: true, detail: `${liveUrl} says up; ${readyUrl} answered 200` };
      else if (Date.now() >= deadline) {
        verdict = { ok: false, detail: `no healthy answer within ${BOOT_WAIT_MS / 1000} s (${liveUrl}: ${live.text}; ${readyUrl}: ${ready.text}). Last log lines:\n${tail(log)}` };
      }
    }
    if (!verdict) await sleep(1000);
  }
  const home = verdict.ok && !ended ? await firstAddress(port) : null;
  if (!ended) {
    child.kill();
    await Promise.race([gone, sleep(3000)]);
  }
  child.stdout.destroy();
  child.stderr.destroy();
  record(verdict.ok ? "PASS" : "FAIL", label, verdict.detail);
  if (home) record(home.ok ? "PASS" : "FAIL", homeLabel, home.detail);
  else notRun(homeLabel, "the release binary did not boot, so GET / was not asked");
}

// ------------------------------------------------------------------ Next.js front end
function webChecks(stack) {
  if (FAST) return ["typecheck", "lint", "test", "build"].forEach((name) => notRun(`web ${name}`, SKIPPED_BY_FAST));
  const dir = join(ROOT, stack.keys.web_dir);
  const pkgPath = toRel(join(dir, "package.json"));
  const pkg = readJson(join(dir, "package.json"));
  const manager = [dir, ROOT].flatMap((d) => [
    ["pnpm-lock.yaml", "pnpm"], ["yarn.lock", "yarn"], ["bun.lock", "bun"], ["bun.lockb", "bun"], ["package-lock.json", "npm"],
  ].filter(([file]) => existsSync(join(d, file))).map(([, name]) => name))[0] ?? "pnpm";
  for (const name of ["typecheck", "lint", "test", "build"]) {
    const label = `web ${name}`;
    if (!pkg?.scripts?.[name]) {
      const why = pkg ? `${pkgPath} defines no "${name}" script` : `${pkgPath} not found; web_dir in STACK.md must be the folder of the Next.js app`;
      if (name === "typecheck") fail(label, `${why}; add one (for example "tsc --noEmit").`);
      else notRun(label, `${why}; add one, or a release claim cannot run it.`);
    } else if (name === "build" && SKIP_BUILD) {
      notRun(label, "skipped by flag");
    } else {
      const r = run(`${manager} run ${name}`, [], { cwd: dir, timeout: TIMEOUT.web, shell: true });
      if (r.ok) pass(label); else fail(label, failureDetail(manager, r));
    }
  }
}

function contractDrift(stack) {
  const label = "API contract drift";
  if (FAST) return notRun(label, SKIPPED_BY_FAST);
  if (!isGitRepo()) return notRun(label, "not a git repository");
  if (!git(["rev-parse", "--verify", "--quiet", "HEAD"]).ok) return notRun(label, "the repository has no commit yet");
  const openapi = posixPath(stack.keys.openapi);
  const apiTypes = posixPath(stack.keys.api_types);
  for (const args of [["openapi:export"], ["openapi:client", "--input", openapi, "--out", posix.dirname(apiTypes)]]) {
    const r = run("navree", args, { timeout: TIMEOUT.navree });
    if (!r.ok) return fail(label, `navree ${args[0]} failed:\n${failureDetail("navree", r)}`);
  }
  const absent = [openapi, apiTypes].filter((p) => !existsSync(join(ROOT, p)));
  if (absent.length) {
    return fail(label, `the commands did not write: ${absent.join(", ")}\nnavree openapi:export is documented to write openapi.json at the app root; check navree-openapi for where the document and the types go, and correct STACK.md.`);
  }
  const untracked = [openapi, apiTypes].filter((p) => !git(["ls-files", "--error-unmatch", "--", p]).ok);
  if (untracked.length) return fail(label, `not tracked by git: ${untracked.join(", ")}\nCommit the regenerated files (hard rule 17).`);
  if (git(["diff", "--exit-code", "HEAD", "--", openapi, apiTypes]).ok) return pass(label);
  fail(label, `${git(["diff", "--stat", "HEAD", "--", openapi, apiTypes]).out.trim()}\nregenerated files differ from the committed ones: review and commit them (hard rule 17).`);
}

// ------------------------------------------------------------------ Navree UI raw markup
// A script or style element, a style, class or on* attribute inside a tag (quoted or not), or one written as a string of its own.
const RAW_MARKUP = /<script\b|<\/script>|<style\b|<[a-z][a-z0-9-]*\b[^<>]*\s(?:style|class|on[a-z]+)\s*=|\s(?:style|class|on[a-z]+)=\\?["']/i;
// Navree UI's raw building blocks by name, so that a use alias, an import or a constant tag is read as well.
const GAP_BLOCK = /\bSafeHtml\b|Node::(?:Raw|Static)\b|\bel\b|\bAppSheet\b/;
const SCRIPT_FOLDERS = ["web", "clients", "design", "docs", "plugins", "qa", "audit", "security", "tests", "target", "node_modules", ".claude", ".agents"];
const SHEET_FOLDERS = SCRIPT_FOLDERS.filter((f) => f !== "tests");
const HTML_FOLDERS = ["design", "docs", "qa", "web", "clients", "target"];
const isUiSource = (rel) => rel.startsWith("src/") && rel.endsWith(".rs") && !/\/(tests|mail)\//.test(`/${rel}`);
// Every Rust file of the app, in any crate and in mail folders: a raw string reaches a page only through a building block.
const isAppRust = (rel) => rel.endsWith(".rs") && !/^(target|plugins|tests|\.claude|\.agents)\//.test(rel) && !/\/tests\//.test(`/${rel}`);
const isCode = (e) => !e.text.trimStart().startsWith("//");

// The lines of the Navree UI sources to judge: those added since the base, or all of src/ without a base.
const uiSourceLines = (base) => (base
  ? addedSince(base, isUiSource)
  : [...walk(join(ROOT, "src"), [".rs"])].map(toRel).filter(isUiSource).flatMap(linesOf)).filter(isCode);

function rawMarkupSweep(base) {
  const label = "Navree UI raw markup";
  const swept = Boolean(base) && isGitRepo() && isCommit(base);
  const hits = uiSourceLines(swept ? base : null).filter((e) => RAW_MARKUP.test(e.text)).map(asHit);
  if (swept) {
    for (const rel of changedFiles(base, "A")) {
      const folders = rel.split("/").slice(0, -1);
      if (/\.m?js$/.test(rel) && !SCRIPT_FOLDERS.includes(folders[0]) && !folders.includes("node_modules")) {
        hits.push(`${rel}:1: a script file outside web/, clients/, design/, docs/, plugins/, qa/, audit/, security/ and tests/`);
      } else if (rel.endsWith(".html") && !HTML_FOLDERS.includes(folders[0]) && !folders.includes("mail")) {
        hits.push(...scanFiles([join(ROOT, rel)], /<script/i).slice(0, 1));
      }
    }
  }
  if (hits.length) return fail(label, `${capped(hits)}\nA Navree UI screen is built from Navree UI components, never raw markup or a loose script (hard rule 14).`);
  if (swept) return pass(label);
  passWithWarning(label, "no base, so all of src/ was read and the added-file part of the sweep (loose scripts, HTML with a script) did not run: set base_commit in STACK.md or pass --base");
}

// The building blocks hard rule 14 accounts for, and the app stylesheets, each in a file that a gap row names.
function gapRowSweep(base) {
  const label = "Navree UI gap rows";
  if (!base || !isGitRepo() || !isCommit(base)) return notRun(label, "needs a git repository and a base: set base_commit in STACK.md or pass --base");
  const sheets = changedFiles(base, "AMR")
    .filter((rel) => rel.endsWith(".css") && !SHEET_FOLDERS.includes(rel.split("/")[0]) && !rel.split("/").includes("node_modules"))
    .map((file) => ({ file, line: 1, text: "an app stylesheet" }));
  const used = [...addedSince(base, isAppRust).filter(isCode).filter((e) => GAP_BLOCK.test(e.text)), ...sheets];
  const plan = readText(join(ROOT, "EXECUTION_PLAN.md"));
  // Only a table row of the gap section names a file: prose, a list item or a heading does not.
  const rows = sectionOf(plan ?? "", "Navree UI gaps").split("\n").filter((l) => /^\|\s*N-\d+\s*\|/.test(l)).join("\n");
  const unnamed = used.filter((e) => !names(rows, e.file));
  if (!unnamed.length) return pass(label);
  fail(label, [
    capped(unnamed.map(asHit)),
    ...(plan === null ? ["EXECUTION_PLAN.md was not found."] : []),
    "not named in the Files column of any row of the gap table (## Navree UI gaps in EXECUTION_PLAN.md, hard rule 14).",
    "SafeHtml, Node::Raw, Node::Static, el and AppSheet may be used for three things only: stored rich text Navree has cleaned, the app's own fixed image or icon (a logo or a mark, never a drawing that shows the app's data), or a stylesheet of token values or fonts. Add a table row for each file above, with that use as its resolution, the file in its Files column and the operator's name and date.",
    "A line that matches only by its name (a variable called el, an unused import of SafeHtml) is fixed by renaming or removing it. The script cannot tell the uses apart; ui-auditor checks them.",
  ].join("\n"));
}

// ------------------------------------------------------------------ Tauri shell (hard rule 25)
const TAURI_DOC = "design-to-tauri/references/security.md, hard rule 25";
// Emulator, loopback and private-LAN hosts: fine for debug, a warning in a capability release builds enable.
const LOCAL_HOST = /^(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.0\.2\.2|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$/i;

function tauriDirs() {
  const found = [];
  const skip = new Set(["node_modules", "target", "dist", "build", "gen", "vendor", ".git", ".next", ".turbo"]);
  const visit = (dir, depth) => {
    let entries;
    try { entries = readdirSync(dir, { withFileTypes: true }); } catch { return; }
    if (entries.some((e) => e.isFile() && /^(tauri\.conf\.json5?|Tauri\.toml)$/.test(e.name))) found.push(dir);
    if (depth >= 4) return;
    for (const e of entries) if (e.isDirectory() && !skip.has(e.name)) visit(join(dir, e.name), depth + 1);
  };
  visit(ROOT, 0);
  return found;
}

function cspDirectives(csp) {
  if (typeof csp === "string") {
    return Object.fromEntries(csp.split(";").map((d) => d.trim().split(/\s+/)).filter((p) => p[0]).map(([k, ...v]) => [k, v.join(" ")]));
  }
  if (csp && typeof csp === "object") {
    return Object.fromEntries(Object.entries(csp).map(([k, v]) => [k, Array.isArray(v) ? v.join(" ") : String(v)]));
  }
  return {};
}

function tauriChecks() {
  for (const dir of tauriDirs()) {
    const rel = toRel(dir);
    if (!existsSync(join(dir, "tauri.conf.json"))) {
      notRun(`${rel} Tauri shell`, `tauri.conf.json5 and Tauri.toml are not parsed: check the CSP, the capabilities and devtools by hand (${TAURI_DOC}).`);
      continue;
    }
    const conf = readJson(join(dir, "tauri.conf.json"));
    if (!conf) { fail(`${rel} tauri.conf.json`, "not valid JSON"); continue; }
    const security = conf.app?.security ?? conf.tauri?.security ?? {};

    const csp = cspDirectives(security.csp);
    const sources = (k) => (csp[k] ?? "").split(/\s+/).filter(Boolean);
    const anyOrigin = (s) => ["*", "http:", "https:", "ws:", "wss:"].includes(s) || /^([a-z]+:\/\/)?\*(:[\d*]+)?\/?$/i.test(s);
    if (!Object.keys(csp).length) {
      fail(`${rel} CSP`, `app.security.csp is null or empty: set a Content Security Policy (${TAURI_DOC}).`);
    } else if (!csp["default-src"]) {
      fail(`${rel} CSP`, "CSP has no default-src, so anything it does not list loads from anywhere.");
    } else if (Object.values(csp).some((v) => /unsafe-eval/.test(v))) {
      fail(`${rel} CSP`, "CSP allows 'unsafe-eval'.");
    } else if (["default-src", "script-src", "connect-src"].some((k) => sources(k).some(anyOrigin))) {
      fail(`${rel} CSP`, "CSP allows any origin (*, https:, http:) in default-src, script-src or connect-src.");
    } else {
      pass(`${rel} CSP set`);
    }
    if ((conf.app ?? conf.build ?? {}).withGlobalTauri === true) {
      passWithWarning(`${rel} withGlobalTauri`, "window.__TAURI__ is exposed to every script in the WebView; import the APIs from the npm packages instead.");
    }

    // Capabilities are parsed, not searched: an opener scope of https://* is fine, an HTTP-plugin scope is not.
    const listed = Array.isArray(security.capabilities) ? security.capabilities : null;
    const caps = [];
    const capDir = join(dir, "capabilities");
    if (existsSync(capDir)) {
      for (const f of readdirSync(capDir)) {
        if (f.endsWith(".json")) {
          const cap = readJson(join(capDir, f));
          if (cap) caps.push({ file: f, cap });
          else fail(`${rel} capabilities/${f}`, "not valid JSON");
        } else if (/\.(json5|toml)$/.test(f)) {
          notRun(`${rel} capabilities/${f}`, "format not parsed: review its scopes by hand.");
        }
      }
    }
    for (const cap of listed ?? []) if (cap && typeof cap === "object") caps.push({ file: "tauri.conf.json (inline)", cap });
    const inRelease = (cap) => !listed || listed.some((x) => x === cap.identifier || (x && typeof x === "object" && x.identifier === cap.identifier));

    const wide = [], cleartext = [], debugOrigins = [], remote = [];
    for (const { file, cap } of caps) {
      if (cap.remote) remote.push(file);
      for (const perm of cap.permissions ?? []) {
        if (!perm || typeof perm !== "object" || !String(perm.identifier ?? "").startsWith("http:")) continue;
        for (const entry of perm.allow ?? []) {
          const url = typeof entry === "string" ? entry : entry?.url;
          if (typeof url !== "string") continue;
          const m = url.match(/^([a-z*]+):\/\/([^/]*)/i);
          if (!m || /\*/.test(m[1]) || /\*/.test(m[2])) { wide.push(`${file}: ${url}`); continue; }
          if (LOCAL_HOST.test(m[2])) { if (inRelease(cap)) debugOrigins.push(`${file}: ${url}`); }
          else if (m[1].toLowerCase() === "http") cleartext.push(`${file}: ${url}`);
        }
      }
    }
    if (wide.length) fail(`${rel} HTTP capability scope`, `Wildcard hosts let any script in the WebView call anywhere: list exact API origins (${TAURI_DOC}):\n${wide.join("\n")}`);
    else pass(`${rel} HTTP capability scope`);
    if (cleartext.length) fail(`${rel} cleartext API origin`, `Remote hosts must be https:\n${cleartext.join("\n")}`);
    if (debugOrigins.length) {
      passWithWarning(`${rel} debug origins in release capabilities`,
        `emulator or LAN origins in a capability that release builds enable: move them to a debug-only capability (${TAURI_DOC}):\n${debugOrigins.join("\n")}`);
    }
    if (remote.length) fail(`${rel} remote capabilities`, `Remote URLs can call native commands (${remote.join(", ")}); remove or document a reviewed requirement.`);

    const cargoPath = join(dir, "Cargo.toml");
    if (existsSync(cargoPath)) {
      const cargo = readFileSync(cargoPath, "utf8").replaceAll("\r\n", "\n");
      // Every form of the dependency: `tauri = { ... }` (arrays may span lines), `[dependencies.tauri]`, target tables.
      const specs = [
        ...[...cargo.matchAll(/^\s*tauri\s*=\s*(\{[\s\S]*?\}|.*)$/gm)].map((m) => m[0]),
        ...[...cargo.matchAll(/^\[(?:target\.[^\n]*\.)?dependencies\.tauri\][\s\S]*?(?=^\[|(?![\s\S]))/gm)].map((m) => m[0]),
      ];
      if (specs.some((s) => /["']devtools["']/.test(s))) fail(`${rel} devtools`, "The tauri crate enables the devtools feature for every build, including release.");
      else pass(`${rel} no devtools in release`);
      const profile = cargo.match(/^\[profile\.release\]([\s\S]*?)(?=^\[|(?![\s\S]))/m)?.[1] ?? "";
      if (!/^\s*strip\s*=\s*(true|"symbols"|"debuginfo")/m.test(profile)) {
        passWithWarning(`${rel} release profile`, `[profile.release] does not strip debug info (strip = true; ${TAURI_DOC}).`);
      }
    }
  }
}

// ------------------------------------------------------------------ sweeps
const RUST_SUPPRESSION = /#!?\[(allow|expect)\(|#!?\[cfg_attr\(.*\b(allow|expect)\(/;
const SCRIPT_SUPPRESSION = /(?:es|ox)lint-disable|@ts-ignore|@ts-expect-error|@ts-nocheck/;
// The configuration of ESLint and of oxlint (the Next.js kit lints with it); oxlint also reads "allow" as off.
const ESLINT_CONFIG = /(^|\/)(eslint\.config\.[cm]?[jt]s|\.eslintrc(\.(json|[cm]?js|ya?ml))?|\.oxlintrc\.json)$/;
const ESLINT_RULE_OFF = /^\s*["']?[@\w/.-]+["']?\s*:\s*(?:["'](?:off|allow)["']|0(?![\w.])|\[\s*(?:["'](?:off|allow)["']|0(?![\w.])))/;
// A clippy.toml loosens a lint with an allow-* key or a *-threshold key; disallowed-* keys only tighten.
const CLIPPY_TOML = /(^|\/)\.?clippy\.toml$/;
const CLIPPY_LOOSENS = /^\s*(allow-[\w-]+|[\w-]*-threshold)\s*=/;
const CARGO_CONFIG = /(^|\/)\.cargo\/config(\.toml)?$/;
const ALLOW_FLAG = /(^|["'\s=\[,])(-A\s*[A-Za-z_:]*|--allow\b[ =]?[\w:]*)(?=["'\s,\]]|$)/;
const TSCONFIG = /(^|\/)tsconfig[^/]*\.json$/;
const SUPPRESSION_FILE = /\.(rs|tsx?|jsx?|mjs)$|(^|\/)Cargo\.toml$/;

// The line of `rel` that numbers `lineNo` sits inside a [lints] table (or a dotted lints key) of a Cargo.toml.
const lintLines = new Map();
function inLintsTable(rel, lineNo) {
  if (!lintLines.has(rel)) {
    const inside = new Set();
    let open = false;
    linesOf(rel).forEach(({ text, line }) => {
      const header = text.match(/^\s*\[([^\]]+)\]\s*$/);
      if (header) open = /^(workspace\.)?lints(\.|$)/.test(header[1].trim());
      else if (open) inside.add(line);
    });
    lintLines.set(rel, inside);
  }
  return lintLines.get(rel).has(lineNo);
}

// The only suppression allowed: `#![allow(dead_code)]` as the first attribute of tests/support/mod.rs (hard rule 15).
function isSupportException(rel, text, lineNo) {
  if (rel !== "tests/support/mod.rs" || text.trim() !== "#![allow(dead_code)]") return false;
  const first = linesOf(rel).find((l) => l.text.trim() && !l.text.trim().startsWith("//"));
  return first?.line === lineNo;
}

// The text of a TypeScript line without its strings and comments, so that English in them is not read as code.
function codeOf(text) {
  if (/^\s*\*/.test(text)) return "";
  let out = "";
  let quote = null;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) {
      if (c === "\\") i++;
      else if (c === quote) quote = null;
    } else if (c === '"' || c === "'" || c === "`") {
      quote = c;
    } else if (c === "/" && text[i + 1] === "/") {
      break;
    } else if (c === "/" && text[i + 1] === "*") {
      const end = text.indexOf("*/", i + 2);
      if (end < 0) break;
      i = end + 1;
    } else {
      out += c;
    }
  }
  return out;
}

function isSuppression({ file: rel, text, line }) {
  if (rel.endsWith(".rs")) return RUST_SUPPRESSION.test(text) && !isSupportException(rel, text, line);
  if (CLIPPY_TOML.test(rel)) return CLIPPY_LOOSENS.test(text);
  if (ESLINT_CONFIG.test(rel) && ESLINT_RULE_OFF.test(text)) return true;
  if (/\.(tsx?|jsx?|mjs)$/.test(rel)) return SCRIPT_SUPPRESSION.test(text) || (/\.tsx?$/.test(rel) && /\bas any\b/.test(codeOf(text)));
  if (TSCONFIG.test(rel)) return /"strict"\s*:\s*false/.test(text);
  if (CARGO_CONFIG.test(rel)) return ALLOW_FLAG.test(text);
  return /Cargo\.toml$/.test(rel) && /["']allow["']/.test(text) && (inLintsTable(rel, line) || /^\s*(workspace\.)?lints\./.test(text));
}
const PLACEHOLDER = /lorem ipsum|coming soon|not implemented|TODO: ?implement|mockData|fakeUsers|placeholder data|4242 ?4242|\btodo!\(|\bunimplemented!\(/i;
const TEST_CODE = /(^|\/)(tests?|__tests__|e2e)\/|\.(test|spec|stories)\./;
const MOCK_FOLDER = /(^|\/)(mocks?|fixtures)\//;

function suppressionSweep(base, apiTypes) {
  const label = `no new suppressions since ${base ?? "base"}`;
  if (!isGitRepo()) return notRun(label, "not a git repository");
  if (!base) return notRun(label, "no base: set base_commit in STACK.md or pass --base");
  if (!isCommit(base)) return notRun(label, `the base ${base} is not a commit of this repository: correct base_commit in STACK.md or --base`);
  const generated = apiTypes ? posixPath(apiTypes) : null;
  const considered = (rel) => rel !== generated && !/^(\.claude|\.agents|target|plugins|design\/source|docs\/brief)\//.test(rel) && !rel.split("/").includes("node_modules");
  const wants = (rel) => considered(rel) && [SUPPRESSION_FILE, ESLINT_CONFIG, TSCONFIG, CARGO_CONFIG, CLIPPY_TOML].some((re) => re.test(rel));
  const hits = addedSince(base, wants).filter(isSuppression).map(asHit);
  if (hits.length) return fail(label, `Fix the cause instead of silencing the check (hard rule 15):\n${capped(hits)}`);
  pass(label);
}

function placeholderSweep(webDir, apiTypes) {
  const label = "no placeholder content";
  const web = webDir || "web";
  const scripts = [".ts", ".tsx", ".js", ".jsx"];
  const folders = [{ dir: join(ROOT, "src"), suffixes: [".rs"], frontEnd: false }];
  for (const sub of ["app", "components", "lib", "modules"]) folders.push({ dir: join(ROOT, web, sub), suffixes: scripts, frontEnd: true });
  const clients = join(ROOT, "clients");
  for (const name of isDir(clients) ? readdirSync(clients) : []) folders.push({ dir: join(clients, name, "src"), suffixes: scripts, frontEnd: true });
  const present = folders.filter((f) => isDir(f.dir));
  if (!present.length) return notRun(label, "no source folders found");
  const generated = apiTypes ? posixPath(apiTypes) : null;
  const files = [];
  const hits = [];
  for (const f of present) {
    // In a front end any file of a mocks or fixtures folder is a hit; in Rust sources those folders are test support.
    for (const file of walk(f.dir, f.frontEnd ? [""] : f.suffixes)) {
      const rel = toRel(file);
      if (TEST_CODE.test(rel) || rel === generated) continue;
      if (MOCK_FOLDER.test(rel)) {
        if (f.frontEnd) hits.push(`${rel}:1: a file in a mocks or fixtures folder of the front end: no mock data path stays in the app`);
      } else if (f.suffixes.some((s) => rel.endsWith(s))) {
        files.push(file);
      }
    }
  }
  hits.push(...scanFiles(files, PLACEHOLDER));
  if (hits.length) fail(label, capped(hits));
  else pass(label);
}

// ------------------------------------------------------------------ committed suites (--suites)
// Each suite line is a cargo test command, which boots its own app: no running app is needed.
function suiteChecks(stack) {
  if (!stack.present || stack.problems.length) {
    return fail("suites", "--suites needs a valid STACK.md with a ## Suites section (superdev-build/references/artifacts.md).");
  }
  if (!stack.suites.length) {
    return fail("suites", "STACK.md lists no command under ## Suites; each committed suite is added there when it is created (security-foundation/references/security-suites.md).");
  }
  const env = { ...process.env };
  const { database, test_database_url: url } = stack.keys;
  if (url && ["timescaledb", "postgres"].includes(database)) env.NAVREE_TEST_POSTGRES_URL = url;
  if (url && database === "mysql") env.NAVREE_TEST_MYSQL_URL = url;
  for (const command of stack.suites) {
    // A changed STACK.md must not run anything but cargo test: no shell, and arguments of plain characters only.
    const words = command.split(/\s+/);
    if (words[0] !== "cargo" || words[1] !== "test") {
      fail(`suite: ${command}`, "refused: a suite line must start with cargo test (STACK.md ## Suites, superdev-build/references/artifacts.md)");
    } else if (!words.every((w) => /^[A-Za-z0-9_.:=+@%/,-]+$/.test(w))) {
      fail(`suite: ${command}`, "refused: a suite line holds cargo test and its arguments only, with no shell syntax and no quotes");
    } else {
      const r = run("cargo", words.slice(1), { timeout: TIMEOUT.suite, env });
      if (r.ok) pass(`suite: ${command}`); else fail(`suite: ${command}`, failureDetail("cargo", r));
    }
  }
}

// ------------------------------------------------------------------ public routes (hard rule 6)
const isPublicRoute = (x) => String(x.access ?? "").split(/\s+/).includes("public");

// The routes the plan lists as public: the `METHOD path` names in backticks of the bullet of ## Access that starts with
// "Public routes" (a wrapped line of that bullet belongs to it).
function listedPublicRoutes(access) {
  const listed = new Set();
  let inBullet = false;
  for (const line of access.split("\n")) {
    if (/^\s*[-*+]\s/.test(line)) inBullet = /^\s*[-*+]\s+public routes\b/i.test(line);
    if (inBullet) for (const m of line.matchAll(/`([A-Z]+)\s+(\/[^`\s]*)`/g)) listed.add(`${m[1]} ${m[2]}`);
  }
  return listed;
}

// The public routes of the release binary, which is what ships, compared both ways with the plan's list.
function publicRoutes(stack) {
  const label = "public routes";
  if (FAST) return notRun(label, SKIPPED_BY_FAST);
  const plan = readText(join(ROOT, "EXECUTION_PLAN.md"));
  if (plan === null) return notRun(label, "no EXECUTION_PLAN.md: the public routes of the release binary are compared with its ## Access section (hard rule 6)");
  const exe = releaseExe(stack);
  if (!existsSync(exe)) {
    if (SKIP_BUILD) return notRun(label, `skipped: --skip-build was given and ${toRel(exe)} does not exist`);
    return fail(label, `${toRel(exe)} not found after the release build: the public routes are read from the release binary, the one that ships (hard rule 6); check the binary key in STACK.md`);
  }
  const r = run(exe, ["routes", "--json"], { timeout: TIMEOUT.navree });
  if (!r.ok) return fail(label, `${toRel(exe)} routes --json failed:\n${failureDetail(toRel(exe), r)}`);
  const routes = routeList(r.stdout);
  if (!routes) return fail(label, `${toRel(exe)} routes --json did not print a JSON list:\n${tail(r.out)}`);
  const access = sectionOf(plan, "Access");
  const open = routes.filter(isPublicRoute);
  const unnamed = open.filter((x) => !new RegExp(`\`${escapeRe(String(x.method))}\\s+${escapeRe(String(x.path))}\``).test(access));
  const have = new Set(open.map((x) => `${x.method} ${x.path}`));
  const stale = [...listedPublicRoutes(access)].filter((name) => !have.has(name));
  const problems = [];
  if (unnamed.length) {
    problems.push(`${capped(unnamed.map((x) => `${x.method} ${x.path}`))}\nnot named in EXECUTION_PLAN.md ## Access as \`METHOD path\` in backticks: list each public route there that way, or remove #[public] (hard rule 6)`);
  }
  if (stale.length) {
    problems.push(`${capped(stale)}\nlisted as public routes in EXECUTION_PLAN.md ## Access, but the release binary does not have them as public routes: remove them from the plan, or make the route public on purpose (hard rule 6)`);
  }
  if (problems.length) return fail(label, problems.join("\n"));
  pass(label, `${open.length} public route(s) of ${toRel(exe)}, each named in EXECUTION_PLAN.md ## Access, and every public route the plan lists is there`);
}

// The route list of <binary> routes --json: it starts at a line beginning with [ and ends at the first line that is exactly ]
// (or is that one line); a log line before or after it is skipped.
function routeList(stdout) {
  const lines = stdout.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    if (!lines[i].startsWith("[")) continue;
    const end = lines.findIndex((l, k) => k > i && l.trimEnd() === "]");
    for (const text of [lines[i], end > i ? lines.slice(i, end + 1).join("\n") : "null"]) {
      try {
        const value = JSON.parse(text);
        if (Array.isArray(value)) return value;
      } catch { /* a log line, not the list */ }
    }
  }
  return null;
}

// ------------------------------------------------------------------ the flow's files (steps 3, 4 and 5)
const statusOf = (text) => text.match(/^Status:\s*(.*?)\s*$/m)?.[1] ?? null;
const signedStatus = (word, line) => new RegExp(`^${word} by\\s+\\S.*?\\s+on\\s+\\d{4}-\\d{2}-\\d{2}$`).test(line ?? "");
const isDraft = (line) => /^DRAFT\b/.test(line ?? "");

// Every Markdown table of a text: {heading, header (lower-cased cells), rows}, each cell trimmed.
function tables(text) {
  const found = [];
  const cellsOf = (line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  let heading = "";
  let current = null;
  for (const line of text.split(/\r?\n/)) {
    const h = line.match(/^#{1,6}\s+(.*?)\s*$/);
    if (h) {
      heading = h[1];
      current = null;
    } else if (!line.trim().startsWith("|")) {
      current = null;
    } else if (!current) {
      current = { heading, header: cellsOf(line).map((c) => c.toLowerCase()), rows: [], separated: false };
      found.push(current);
    } else if (!current.separated) {
      current.separated = true;
      if (!/^[\s|:-]+$/.test(line)) current.rows.push(cellsOf(line));
    } else {
      current.rows.push(cellsOf(line));
    }
  }
  return found;
}

// The modules of the plan: the Module column of the table under ## Modules.
function moduleNames(plan) {
  const table = tables(sectionOf(plan, "Modules"))[0];
  const col = table ? table.header.indexOf("module") : -1;
  return col < 0 ? [] : table.rows.map((cells) => (cells[col] ?? "").replace(/[`*]/g, "").trim()).filter(Boolean);
}

function planConfirmed(plan) {
  const label = "plan confirmed";
  if (plan === null) return notRun(label, "no EXECUTION_PLAN.md: step 3 writes it, and the operator confirms it (hard rule 2)");
  const line = statusOf(plan);
  if (signedStatus("CONFIRMED", line)) return pass(label, `Status: ${line}`);
  if (isDraft(line)) return notRun(label, "Status: DRAFT: the operator has not confirmed the plan yet (hard rule 2)");
  fail(label, `${line === null ? "EXECUTION_PLAN.md has no Status line" : `Status: ${line}`}; the line must read \`Status: CONFIRMED by <name> on <YYYY-MM-DD>\`, written after the operator said so (hard rule 2)`);
}

function contractsAgreed(plan) {
  const label = "contracts agreed";
  if (plan === null) return notRun(label, "no EXECUTION_PLAN.md, so no module is known (step 3 writes it)");
  const modules = moduleNames(plan);
  if (!modules.length) return notRun(label, "EXECUTION_PLAN.md ## Modules lists no module");
  const unwritten = [];
  const wrong = [];
  for (const module of modules) {
    const file = `contracts/${module}.md`;
    const text = readText(join(ROOT, file));
    const line = text === null ? null : statusOf(text);
    if (text === null) unwritten.push(`${file} does not exist (step 5 writes it before the module's code, hard rule 3)`);
    else if (signedStatus("AGREED", line)) continue;
    else if (isDraft(line)) unwritten.push(`${file}: Status: DRAFT, the operator has not agreed it`);
    else wrong.push(`${file}: ${line === null ? "no Status line" : `Status: ${line}`}; the line must read \`Status: AGREED by <name> on <YYYY-MM-DD>\``);
  }
  if (wrong.length) return fail(label, [...wrong, ...unwritten].join("\n"));
  if (unwritten.length) return notRun(label, unwritten.join("\n"));
  pass(label, `${modules.length} contract(s): ${modules.join(", ")}`);
}

function moduleDependencyGraph(plan) {
  const label = "module dependency graph";
  if (plan === null) return notRun(label, "no EXECUTION_PLAN.md: step 3 writes ## Modules and ## Build order (hard rule 26)");
  const table = tables(sectionOf(plan, "Modules"))[0];
  if (!table || !table.rows.length) return notRun(label, "EXECUTION_PLAN.md ## Modules lists no module");
  const colId = table.header.indexOf("id");
  const colMod = table.header.indexOf("module");
  const colTier = table.header.indexOf("tier");
  const colDeps = table.header.indexOf("depends on");
  if (colMod < 0) return fail(label, "EXECUTION_PLAN.md ## Modules has no Module column");

  const clean = (s) => (s ?? "").replace(/[`*]/g, "").trim();
  const nodes = [];
  const byKey = new Map();
  const problems = [];
  for (const cells of table.rows) {
    const id = colId >= 0 ? clean(cells[colId]) : "";
    const name = clean(cells[colMod]);
    if (!name) continue;
    const key = name.toLowerCase();
    const labelName = id ? `${id} ${name}` : name;
    let tier = null;
    if (colTier >= 0) {
      const rawTier = clean(cells[colTier]);
      if (/^[0-3]$/.test(rawTier)) tier = Number(rawTier);
      else problems.push(`${labelName}: invalid tier "${rawTier || "(empty)"}" (expected 0 to 3, hard rule 26)`);
    }
    const rawDeps = colDeps >= 0 ? clean(cells[colDeps]) : "";
    const depTokens = rawDeps && !/^(?:\(none\)|none|-)$/i.test(rawDeps)
      ? rawDeps.split(/[,;]/).map((t) => clean(t)).filter((t) => t && !/^(?:\(none\)|none|-)$/i.test(t))
      : [];
    const node = { key, id, name, label: labelName, tier, depTokens, deps: [] };
    nodes.push(node);
    byKey.set(key, node);
    if (id) byKey.set(id.toLowerCase(), node);
  }

  for (const node of nodes) {
    for (const tok of node.depTokens) {
      const firstWord = tok.split(/\s+/)[0].toLowerCase();
      const target = byKey.get(tok.toLowerCase()) ?? byKey.get(firstWord);
      if (!target) {
        problems.push(`${node.label}: depends on unknown module "${tok}" (hard rule 26)`);
      } else {
        node.deps.push(target);
        if (node.tier !== null && target.tier !== null && target.tier > node.tier) {
          problems.push(`tier inversion: ${node.label} (tier ${node.tier}) depends on ${target.label} (tier ${target.tier}); lower tiers never depend on higher tiers (hard rule 26)`);
        }
      }
    }
  }

  // DFS 3-color cycle detection over the module graph.
  const color = new Map();
  const stack = [];
  const visit = (node) => {
    color.set(node.key, 1);
    stack.push(node);
    for (const dep of node.deps) {
      const state = color.get(dep.key) ?? 0;
      if (state === 1) {
        const start = stack.findIndex((n) => n.key === dep.key);
        const cycle = [...stack.slice(start).map((n) => n.label), dep.label];
        problems.push(`cycle detected: ${cycle.join(" -> ")} (hard rule 26)`);
      } else if (state === 0) {
        visit(dep);
      }
    }
    stack.pop();
    color.set(node.key, 2);
  };
  for (const node of nodes) if ((color.get(node.key) ?? 0) === 0) visit(node);

  // Build order must place every dependency before any module that depends on it.
  const buildTable = tables(sectionOf(plan, "Build order"))[0];
  if (buildTable) {
    const colOrderMod = buildTable.header.indexOf("module");
    const orderPos = new Map();
    if (colOrderMod >= 0) {
      buildTable.rows.forEach((cells, idx) => {
        const raw = clean(cells[colOrderMod]);
        const parts = raw.split(/\s+/);
        const match = byKey.get(raw.toLowerCase()) ?? byKey.get((parts[1] ?? "").toLowerCase()) ?? byKey.get((parts[0] ?? "").toLowerCase());
        if (match && !orderPos.has(match.key)) orderPos.set(match.key, idx);
      });
      for (const node of nodes) {
        const pos = orderPos.get(node.key);
        if (pos === undefined) continue;
        for (const dep of node.deps) {
          const depPos = orderPos.get(dep.key);
          if (depPos !== undefined && depPos > pos) {
            problems.push(`build order inversion: ${node.label} appears before ${dep.label}, which it depends on (hard rule 26)`);
          }
        }
      }
    }
  }

  if (problems.length) return fail(label, capped([...new Set(problems)]));
  pass(label, `${nodes.length} module(s), acyclic${colTier >= 0 ? " with valid hierarchy tiers" : ""} and ordered build sequence`);
}

function contractStories(plan) {
  const label = "contract stories";
  if (plan === null) return notRun(label, "no EXECUTION_PLAN.md, so no module contract is known (hard rule 30)");
  const modules = moduleNames(plan);
  if (!modules.length) return notRun(label, "EXECUTION_PLAN.md ## Modules lists no module");
  const unwritten = [];
  const problems = [];
  const isEmptyCell = (s) => !s || /^(?:\(none\)|none|-)$/i.test(s.replace(/[`*]/g, "").trim());
  for (const module of modules) {
    const file = `contracts/${module}.md`;
    const text = readText(join(ROOT, file));
    if (text === null || isDraft(statusOf(text))) {
      unwritten.push(`${file}: missing or still DRAFT (hard rule 30)`);
      continue;
    }
    const section = sectionOf(text, "Stories");
    if (!section.trim()) {
      problems.push(`${file}: missing ## Stories section with Must pass and Must reject cases (hard rule 30)`);
      continue;
    }
    const table = tables(section)[0];
    if (!table || !table.rows.length) {
      problems.push(`${file}: ## Stories has no story rows (hard rule 30)`);
      continue;
    }
    const colPass = table.header.indexOf("must pass");
    const colReject = table.header.indexOf("must reject");
    if (colPass < 0 || colReject < 0) {
      problems.push(`${file}: ## Stories table must include Must pass and Must reject columns (hard rule 30)`);
      continue;
    }
    for (const cells of table.rows) {
      const storyId = (cells[0] ?? "story").replace(/[`*]/g, "").trim() || "story";
      if (isEmptyCell(cells[colPass] ?? "")) problems.push(`${file} (${storyId}): empty Must pass cell (hard rule 30)`);
      if (isEmptyCell(cells[colReject] ?? "")) problems.push(`${file} (${storyId}): empty Must reject cell (hard rule 30)`);
    }
  }
  if (problems.length) return fail(label, capped(problems));
  if (unwritten.length) return notRun(label, unwritten.join("\n"));
  pass(label, `${modules.length} contract(s) define Must pass and Must reject stories`);
}

function cargoLockCommitted() {
  const label = "Cargo.lock committed";
  if (!isGitRepo()) return notRun(label, "not a git repository");
  if (!existsSync(join(ROOT, "Cargo.lock"))) return notRun(label, "no Cargo.lock yet: cargo writes it at the first build, and step 4 commits it");
  if (git(["ls-files", "--error-unmatch", "--", "Cargo.lock"]).ok) return pass(label);
  const ignored = git(["check-ignore", "-q", "--", "Cargo.lock"]).ok;
  fail(label, `Cargo.lock is ${ignored ? "ignored by git" : "not tracked by git"}: an application commits its lock file, so that builds and the dependency audit read the same versions (git add Cargo.lock, step 4)`);
}

// ------------------------------------------------------------------ reports and acceptances (--strict)
const REPORT_FILES = { "SECURITY_REPORT.md": "step 7 (security-review-and-fix)", "AUDIT_REPORT.md": "step 7 (product-audit)", "QA_COVERAGE.md": "step 8 (product-qa)" };
const ACCEPTANCES = "ACCEPTANCES.md";
const cited = (text) => text.match(/\bACC-\d+\b/g) ?? [];
const headingOf = (line) => line.match(/^#{1,6}\s+(.*?)\s*$/)?.[1] ?? null;
const isNotRunCell = (cell) => /^NOT RUN\b/i.test(cell) || /^PASS\s*\([^)]*\bserver\b/i.test(cell);

// The entries of ACCEPTANCES.md: a heading `## ACC-n` and, under it, the date, the operator's name, what is accepted and the operator's words.
function acceptanceEntries() {
  const text = readText(join(ROOT, ACCEPTANCES));
  if (text === null) return { ids: new Set(), incomplete: [] };
  const blocks = text.split(/^(?=#{2,3}\s+ACC-\d+\b)/m).filter((b) => /^#{2,3}\s+ACC-\d+\b/.test(b));
  const ids = new Set();
  const incomplete = [];
  for (const block of blocks) {
    const id = block.match(/^#{2,3}\s+(ACC-\d+)\b/)[1];
    if (ids.has(id)) incomplete.push(`${id} is the heading of two entries: a number is never used twice`);
    ids.add(id);
    const missing = [["Date", /^[-*\s]*Date:\s*\d{4}-\d{2}-\d{2}/m], ["Operator", /^[-*\s]*Operator:\s*\S/m], ["Accepts", /^[-*\s]*Accepts:\s*\S/m], ["Words", /^[-*\s]*Words:\s*\S/m]]
      .filter(([, re]) => !re.test(block)).map(([name]) => name);
    if (missing.length) incomplete.push(`${id} lacks ${missing.join(", ")}`);
  }
  return { ids, incomplete };
}

// What a report holds that blocks a release claim: an open Blocker or Major, an accepted state with no entry behind it,
// a NOT RUN with no acceptance, and in the coverage matrix a FAIL cell.
function reportProblems(name, text, ids) {
  const problems = [];
  const unknown = (where, cellText) => cited(cellText).filter((id) => !ids.has(id)).forEach((id) => problems.push(`${where}: ${id} is not an entry of ${ACCEPTANCES}`));
  let findingsTables = 0;
  for (const table of tables(text)) {
    const col = (word) => table.header.indexOf(word);
    // Any table with both columns is read as findings, so one under a sub-heading is not skipped.
    const findings = col("severity") >= 0 && col("state") >= 0;
    const notRunSection = /not run/i.test(table.heading);
    if (/^findings$/i.test(table.heading)) {
      findingsTables += 1;
      if (!findings) problems.push(`${table.heading}: the table has no ${["severity", "state"].filter((c) => col(c) < 0).map((c) => c[0].toUpperCase() + c.slice(1)).join(" and no ")} column, so its findings cannot be read`);
    }
    for (const cells of table.rows) {
      const row = `${table.heading}, ${(findings ? cells[col("id")] : cells[0]) || cells.join(" | ").slice(0, 60)}`;
      if (findings) {
        const severity = (cells[col("severity")] ?? "").replace(/[`*]/g, "").trim();
        const state = cells[col("state")] ?? "";
        if (/^accepted\b/i.test(state)) {
          if (!cited(state).length) problems.push(`${row}: accepted with no ACC-n (the state reads \`accepted ACC-n\`, naming an entry of ${ACCEPTANCES})`);
          unknown(row, state);
        } else if (/^(blocker|major)\b/i.test(severity) && !/^fixed\b/i.test(state)) {
          problems.push(`${row}: ${severity} is ${state || "without a state"}: fix it, or the operator accepts it in ${ACCEPTANCES}`);
        }
      }
      for (const cell of cells) {
        if (isNotRunCell(cell)) {
          if (!cited(cell).length) problems.push(`${row}: ${cell.startsWith("PASS") ? "PASS (server) leaves the browser half NOT RUN" : "NOT RUN"} with no ACC-n`);
          unknown(row, cell);
        }
        if (name === "QA_COVERAGE.md" && /^FAIL\b/i.test(cell)) problems.push(`${row}: a FAIL cell: fix it at the root cause and run the cell again`);
      }
      if (notRunSection) {
        if (!cited(cells.join(" ")).length) problems.push(`${row}: a Not run row with no ACC-n`);
        unknown(row, cells.join(" "));
      }
    }
  }
  // A Not run section written as a list, and what the Findings section holds when it has no table.
  let heading = "";
  let hasFindings = false;
  let findingsSayNone = false;
  for (const line of text.split(/\r?\n/)) {
    heading = headingOf(line) ?? heading;
    if (/^findings$/i.test(heading)) {
      hasFindings = true;
      if (/^\s*(?:[-*+]\s+)?none\.?\s*$/i.test(line)) findingsSayNone = true;
    }
    if (headingOf(line) === null && /not run/i.test(heading) && /^\s*(?:[-*+]|\d+\.)\s+\S/.test(line) && !/^\s*[-*+]\s+none\.?\s*$/i.test(line)) {
      const row = `${heading}, ${line.trim().slice(0, 60)}`;
      if (!cited(line).length) problems.push(`${row}: a Not run entry with no ACC-n`);
      unknown(row, line);
    }
  }
  if (!hasFindings) problems.push("no ## Findings section: it holds the findings table, or None.");
  else if (!findingsTables && !findingsSayNone) problems.push("the ## Findings section holds neither the findings table nor None.");
  return [...new Set(problems)];
}

function reportCheck(name, ids) {
  if (!STRICT) return notRun(name, "checked under --strict only: this run does not read it");
  const text = readText(join(ROOT, name));
  if (text === null) return fail(name, `${name} does not exist: ${REPORT_FILES[name]} writes it`);
  const problems = reportProblems(name, text, ids);
  if (problems.length) return fail(name, `${capped(problems)}\nA release claim needs no open Blocker or Major finding, no NOT RUN without an acceptance, and every acceptance an entry of ${ACCEPTANCES}.`);
  pass(name, `no open Blocker or Major finding, and every NOT RUN accepted by an entry of ${ACCEPTANCES}`);
}

// The commits that change `file` of the app root, with every file each of them changes. git log names files from the
// top folder of the repository, so for an app in a sub-folder the file is looked up by its path from there.
function commitsChanging(file) {
  const name = `${git(["rev-parse", "--show-prefix"]).out.trim()}${file}`;
  const log = git(["log", "--name-only", "--no-renames", "--format=%x01%h"]);
  if (!log.ok) return [];
  return log.out.split("\x01").slice(1)
    .map((chunk) => { const [hash, ...files] = chunk.split("\n").map((l) => l.trim()).filter(Boolean); return { hash, files }; })
    .filter((c) => c.files.includes(name));
}

function acceptanceCheck(plan, entries) {
  const label = "acceptances";
  if (!STRICT) return notRun(label, "checked under --strict only: this run does not read the build order's proofs or ACCEPTANCES.md");
  const problems = [...entries.incomplete.map((p) => `${ACCEPTANCES}: ${p}`)];
  let rows = 0;
  if (plan !== null) {
    for (const table of tables(plan).filter((t) => /^build order$/i.test(t.heading))) {
      const status = table.header.indexOf("status");
      for (const cells of table.rows) {
        rows += 1;
        const cell = (cells[status] ?? "").replace(/[`*]/g, "").trim();
        const m = cell.match(/^PASS(?:\s*\((.*)\))?$/);
        if (!m) problems.push(`${cells[0]}: Status ${cell || "is empty"}: a built module reads PASS, or PASS (6.5 NOT RUN, ACC-n)`);
        else if (m[1] !== undefined && !cited(m[1]).length) problems.push(`${cells[0]}: Status ${cell} has no ACC-n`);
        else if (m[1] !== undefined) cited(m[1]).filter((id) => !entries.ids.has(id)).forEach((id) => problems.push(`${cells[0]}: ${id} is not an entry of ${ACCEPTANCES}`));
      }
    }
    if (!rows) problems.push("EXECUTION_PLAN.md ## Build order has no module row");
  }
  let unreadable = null;
  if (existsSync(join(ROOT, ACCEPTANCES))) {
    if (!isGitRepo()) {
      unreadable = `not a git repository: the history of ${ACCEPTANCES} cannot be read`;
    } else {
      const tracked = git(["ls-files", "--error-unmatch", "--", ACCEPTANCES]).ok;
      if (!tracked || git(["status", "--porcelain", "--", ACCEPTANCES]).out.trim()) {
        problems.push(`${ACCEPTANCES} ${tracked ? "has uncommitted changes" : "is not committed"}: the operator's entry is a commit of its own`);
      }
      for (const c of commitsChanging(ACCEPTANCES)) {
        if (c.files.length > 1) problems.push(`commit ${c.hash} changes ${ACCEPTANCES} together with ${c.files.length - 1} other file(s): an acceptance is a commit of its own`);
      }
    }
  }
  if (problems.length) return fail(label, capped(problems));
  if (unreadable) return notRun(label, unreadable);
  pass(label, `${rows} module row(s) PASS; ${entries.ids.size} acceptance(s) in ${ACCEPTANCES}${entries.ids.size ? ", each in a commit of its own" : ""}`);
}

// ------------------------------------------------------------------ report
function report(stack) {
  const lines = [
    `superdev verify-done ${VERSION} — root: ${ROOT}`,
    !stack.present ? "stack: not read"
      : stack.problems.length ? "stack: invalid (see the STACK.md check)"
        : `stack: front_end=${stack.keys.front_end} database=${stack.keys.database} binary=${stack.keys.binary} (STACK.md)`,
    "=".repeat(60),
  ];
  for (const r of results) {
    lines.push(` [${r.status}] ${r.label}`);
    if (r.detail) lines.push(...r.detail.split("\n").map((l) => `      ${l}`.trimEnd()));
  }
  const failed = results.filter((r) => r.status === "FAIL").length;
  const warned = results.filter(isWarning).length;
  const skipped = results.filter((r) => r.status === "NOT RUN").length;
  const passed = results.filter((r) => r.status === "PASS").map((r) => r.label);
  const notRunLabels = results.filter((r) => r.status === "NOT RUN").map((r) => r.label);
  lines.push("");
  let code = 0;
  if (failed) {
    code = 1;
    lines.push(`NOT DONE — ${failed} failing check(s). Fix at the root cause (no suppressions), then re-run.`);
  } else if (STRICT && (warned || skipped)) {
    code = 1;
    lines.push(`NOT DONE (--strict) — ${warned} warning(s) and ${skipped} check(s) not run. A release claim needs every check run and clean.`);
  } else if (STRICT) {
    lines.push(`DONE — all live checks and committed suites green under --strict; SECURITY_REPORT.md, AUDIT_REPORT.md and QA_COVERAGE.md hold no open Blocker or Major finding and no NOT RUN without an acceptance in ${ACCEPTANCES}. Browser, role and device evidence is the product-qa gate's QA_COVERAGE.md.`);
  } else {
    lines.push(`NOT DONE (no check failed, so the exit code is 0, and exit 0 is not done) — passed: ${passed.join(", ") || "none"}. Not run: ${notRunLabels.join(", ") || "none"}${warned ? `; ${warned} warning(s)` : ""}. Steps 7 and 8 were not checked: SECURITY_REPORT.md, AUDIT_REPORT.md and QA_COVERAGE.md are read under --strict. Only a --strict run that ends DONE means the build is done.`);
  }
  return { code, stdout: `${lines.join("\n")}\n`, stderr: "" };
}

async function main(argv) {
  const parsed = parseArgs(argv);
  if (parsed.help) return { code: 0, stdout: helpText(), stderr: "" };
  if (parsed.error) return { code: 2, stdout: "", stderr: `verify-done: ${parsed.error}\n${USAGE}\nRun with --help for the flags and the checks.\n` };
  const o = parsed.opts;
  ROOT = resolve(o["--root"] ?? process.cwd());
  if (!isDir(ROOT)) return { code: 2, stdout: "", stderr: `verify-done: --root is not a directory: ${ROOT}\n` };
  SKIP_BUILD = Boolean(o["--skip-build"]);
  SKIP_BOOT = Boolean(o["--skip-boot"]);
  FAST = Boolean(o["--fast"]);
  STRICT = Boolean(o["--strict"]);

  const stack = readStack();
  if (!stack.present) fail("STACK.md", "no STACK.md in the app root: run the check from the app root (or pass --root), where superdev-build writes it at step 1 (format in superdev-build/references/artifacts.md)");
  else if (stack.problems.length) fail("STACK.md", stack.problems.join("\n"));
  else pass("STACK.md");
  const keys = stack.keys;
  const base = o["--base"] ?? (keys.base_commit || undefined);
  const stackOk = stack.present && !stack.problems.length;

  if (stackOk) {
    navreeCli(stack);
    skillsInstalled();
    programCheck("cargo fmt", "cargo", ["fmt", "--all", "--", "--check"], TIMEOUT.cargo);
    if (FAST) {
      for (const label of ["cargo clippy", "cargo test", "navree check", "navree config:check", "release build"]) notRun(label, SKIPPED_BY_FAST);
    } else {
      programCheck("cargo clippy", "cargo", ["clippy", "--workspace", "--all-targets", "--", "-D", "warnings"], TIMEOUT.cargo);
      cargoTest();
      programCheck("navree check", "navree", ["check"], TIMEOUT.navree, {
        extraFailure: "navree check needs config and a migrated database: start the database (navree dock up for TimescaleDB and PostgreSQL; MySQL runs on a server you provide at database.url; SQLite needs nothing), then run navree migrate (hard rule 13).",
      });
      programCheck("navree config:check", "navree", ["config:check"], TIMEOUT.navree);
      if (SKIP_BUILD) notRun("release build", "skipped by flag");
      else programCheck("release build", "cargo", ["build", "--release"], TIMEOUT.cargo);
    }
    publicRoutes(stack);
    await bootCheck(stack);
    if (keys.front_end === "next") {
      webChecks(stack);
      contractDrift(stack);
    }
    if (keys.front_end === "navree") {
      rawMarkupSweep(base);
      gapRowSweep(base);
    }
  }
  tauriChecks();
  suppressionSweep(base, keys.api_types);
  placeholderSweep(keys.web_dir, keys.api_types);
  if (stackOk) {
    const plan = readText(join(ROOT, "EXECUTION_PLAN.md"));
    planConfirmed(plan);
    moduleDependencyGraph(plan);
    contractsAgreed(plan);
    contractStories(plan);
    cargoLockCommitted();
    const entries = acceptanceEntries();
    for (const name of Object.keys(REPORT_FILES)) reportCheck(name, entries.ids);
    acceptanceCheck(plan, entries);
  }
  if (o["--suites"]) suiteChecks(stack);
  else if (stackOk) notRun("suites", FAST ? SKIPPED_BY_FAST : "the committed suites of STACK.md ## Suites were not run: --suites runs them");
  return report(stack);
}

const result = await main(process.argv.slice(2));
const flush = (stream, text) => new Promise((done) => (text ? stream.write(text, done) : done()));
await flush(process.stderr, result.stderr);
await flush(process.stdout, result.stdout);
process.exit(result.code);
