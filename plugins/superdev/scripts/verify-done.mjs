#!/usr/bin/env node
// verify-done.mjs — live Definition-of-Done check for a SuperDev-built monorepo.
//
// Replaces the old bash done-gate + hand-marked completion ledger: nothing
// is read from a self-graded ledger; every check runs NOW, against the real
// tree and the real built artifact. Cross-platform (Windows/macOS/Linux), no
// dependencies. Run from the target monorepo root:
//
//   node <superdev-plugin>/scripts/verify-done.mjs [--root DIR] [--skip-build]
//        [--skip-boot] [--health-url URL] [--suites] [--api-url URL] [--strict]
//
// --suites runs every committed `smoke` and `test:*` package script against the
// RUNNING stack (start it and reset the demo data first); --api-url is the base
// it must answer on (default http://127.0.0.1:${PORT or 3001}).
// --strict turns every SKIP and WARN into a failure; release claims use it.
//
// Exit 0 = done (as far as machines can tell). Exit 1 = not done; the report
// names the exact failing checks. Fix at root cause — suppressions fail here.

import { spawn, spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:net";
import { join } from "node:path";

const args = process.argv.slice(2);
const opt = (name) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
};
const ROOT = opt("--root") ?? process.cwd();
const SKIP_BUILD = args.includes("--skip-build");
const SKIP_BOOT = args.includes("--skip-boot");
const HEALTH_URL = opt("--health-url");
const RUN_SUITES = args.includes("--suites");
const API_URL = opt("--api-url");
const STRICT = args.includes("--strict");

const results = []; // {status: 'PASS'|'FAIL'|'WARN'|'SKIP', label, detail?}
const record = (status, label, detail) => results.push({ status, label, detail });

function readJson(path) {
  try { return JSON.parse(readFileSync(path, "utf8")); } catch { return null; }
}

function detectPm(root) {
  if (existsSync(join(root, "pnpm-lock.yaml"))) return "pnpm";
  if (existsSync(join(root, "yarn.lock"))) return "yarn";
  if (existsSync(join(root, "bun.lockb")) || existsSync(join(root, "bun.lock"))) return "bun";
  return "npm";
}

function runScript(pm, dir, script, timeout = 600_000) {
  const cmd = pm === "npm" ? `npm run ${script}` : `${pm} run ${script}`;
  const res = spawnSync(cmd, { cwd: dir, shell: true, encoding: "utf8", timeout, maxBuffer: 64 * 1024 * 1024 });
  const out = `${res.stdout ?? ""}\n${res.stderr ?? ""}`.trim();
  return { ok: res.status === 0, tail: out.split("\n").slice(-8).join("\n") };
}

function* walk(dir, exts, skipDirs = new Set(["node_modules", ".next", "dist", ".turbo", ".git"])) {
  let entries;
  try { entries = readdirSync(dir); } catch { return; }
  for (const name of entries) {
    const p = join(dir, name);
    let st;
    try { st = statSync(p); } catch { continue; }
    if (st.isDirectory()) {
      if (!skipDirs.has(name)) yield* walk(p, exts, skipDirs);
    } else if (exts.some((e) => name.endsWith(e))) {
      yield p;
    }
  }
}

function grepFiles(files, regex, exclude = /(\.(test|spec)\.|__tests__|\/mocks?\/|\.stories\.)/) {
  const hits = [];
  for (const f of files) {
    if (exclude.test(f.replaceAll("\\", "/"))) continue;
    let text;
    try { text = readFileSync(f, "utf8"); } catch { continue; }
    text.split("\n").forEach((line, i) => {
      if (regex.test(line)) hits.push(`${f.slice(ROOT.length + 1)}:${i + 1}: ${line.trim().slice(0, 120)}`);
    });
  }
  return hits;
}

// ---------------------------------------------------------------- packages
const pm = detectPm(ROOT);
const packageDirs = [];
for (const base of ["apps", "packages"]) {
  const baseDir = join(ROOT, base);
  if (!existsSync(baseDir)) continue;
  for (const name of readdirSync(baseDir)) {
    const dir = join(baseDir, name);
    if (existsSync(join(dir, "package.json"))) packageDirs.push(dir);
  }
}
if (packageDirs.length === 0 && existsSync(join(ROOT, "package.json"))) packageDirs.push(ROOT);

console.log(`superdev verify-done — root: ${ROOT} (${pm})`);
console.log("=".repeat(60));

for (const dir of packageDirs) {
  const rel = dir.slice(ROOT.length + 1) || ".";
  const pkg = readJson(join(dir, "package.json")) ?? {};
  const scripts = pkg.scripts ?? {};
  for (const step of ["typecheck", "lint", "build"]) {
    if (!scripts[step] || (step === "build" && SKIP_BUILD)) {
      if (scripts[step]) record("SKIP", `${rel} ${step}`, "skipped by flag");
      continue;
    }
    const r = runScript(pm, dir, step);
    record(r.ok ? "PASS" : "FAIL", `${rel} ${step}`, r.ok ? undefined : r.tail);
  }
}

// ------------------------------------------------------------ contracts CJS
const contractsPkg = readJson(join(ROOT, "packages", "contracts", "package.json"));
const apiPkg = readJson(join(ROOT, "apps", "api", "package.json"));
if (contractsPkg && apiPkg) {
  const contractsEsm = contractsPkg.type === "module";
  const apiEsm = apiPkg.type === "module";
  if (contractsEsm && !apiEsm) {
    record("FAIL", "contracts module format",
      'packages/contracts is ESM-only ("type":"module") but apps/api is CommonJS — boot will throw ERR_PACKAGE_PATH_NOT_EXPORTED. Build contracts as CommonJS (hard-rules #3).');
  } else {
    record("PASS", "contracts module format");
  }
}

// ---------------------------------------------------------- swagger landmine
const apiSrc = join(ROOT, "apps", "api", "src");
if (existsSync(apiSrc)) {
  const hits = grepFiles([...walk(apiSrc, [".ts"])], /patchNestJsSwagger\s*\(/);
  if (hits.length) {
    record("FAIL", "patchNestJsSwagger (hard-rules #2)",
      `Crashes boot with @nestjs/swagger 11:\n${hits.slice(0, 5).join("\n")}`);
  } else {
    record("PASS", "no patchNestJsSwagger");
  }
}

// ------------------------------------------------------------------- boot
async function bootCheck() {
  if (SKIP_BOOT) { record("SKIP", "api boot", "skipped by flag"); return; }
  const dist = join(ROOT, "apps", "api", "dist", "main.js");
  if (!existsSync(dist)) { record("SKIP", "api boot", "apps/api/dist/main.js not found (no build output)"); return; }
  // A free port, so a dev stack already running on the usual port (needed for --suites) does not collide.
  const bootPort = await freePort();
  const child = spawn(process.execPath, [dist], { cwd: join(ROOT, "apps", "api"), env: { ...process.env, PORT: String(bootPort) } });
  let log = "";
  child.stdout.on("data", (d) => { log += d.toString(); });
  child.stderr.on("data", (d) => { log += d.toString(); });
  const exited = new Promise((r) => child.on("exit", (code) => r(code)));
  const deadline = Date.now() + 25_000;
  let verdict = null;
  while (Date.now() < deadline && !verdict) {
    const code = await Promise.race([exited, new Promise((r) => setTimeout(() => r("pending"), 1000))]);
    if (code !== "pending") {
      verdict = { ok: false, detail: `process exited (${code}) during boot:\n${log.split("\n").slice(-10).join("\n")}` };
      break;
    }
    const portMatch = log.match(/(?:localhost|127\.0\.0\.1|port)\D{0,12}?(\d{4,5})/i);
    const ports = [...new Set([String(bootPort), portMatch?.[1], process.env.PORT, "3001", "3000", "4203", "8080"].filter(Boolean))];
    const urls = HEALTH_URL ? [HEALTH_URL] : ports.flatMap((p) =>
      [`http://127.0.0.1:${p}/health/ready`, `http://127.0.0.1:${p}/health`, `http://127.0.0.1:${p}/v1/health`]);
    for (const u of urls) {
      try {
        const res = await fetch(u, { signal: AbortSignal.timeout(2000) });
        if (res.status < 500) { verdict = { ok: true, detail: `${u} → HTTP ${res.status}` }; break; }
      } catch { /* keep polling */ }
    }
    if (!verdict && /successfully started|listening/i.test(log)) {
      // Process reports up but health did not answer yet; give the loop more
      // time rather than passing on a log line alone.
      continue;
    }
  }
  if (!verdict) {
    verdict = { ok: false, detail: `no health response within 25s. Boot log tail:\n${log.split("\n").slice(-10).join("\n")}` };
  }
  try { child.kill(); } catch { /* already gone */ }
  record(verdict.ok ? "PASS" : "FAIL", "api boot (dist + health, hard-rules #1)", verdict.detail);
}

function freePort() {
  return new Promise((resolve) => {
    const srv = createServer();
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on("error", () => resolve(0));
  });
}

// ------------------------------------------------------- tauri shell (hard-rules #18)
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
    const rel = dir.slice(ROOT.length + 1) || ".";
    if (!existsSync(join(dir, "tauri.conf.json"))) {
      record("SKIP", `${rel} Tauri shell`, "tauri.conf.json5 / Tauri.toml are not parsed — check CSP, capabilities and devtools by hand (design-to-tauri/references/security.md).");
      continue;
    }
    const conf = readJson(join(dir, "tauri.conf.json"));
    if (!conf) { record("FAIL", `${rel} tauri.conf.json`, "not valid JSON"); continue; }
    const security = conf.app?.security ?? conf.tauri?.security ?? {};

    const csp = cspDirectives(security.csp);
    const sources = (k) => (csp[k] ?? "").split(/\s+/).filter(Boolean);
    const anyOrigin = (s) => ["*", "http:", "https:", "ws:", "wss:"].includes(s) || /^([a-z]+:\/\/)?\*(:[\d*]+)?\/?$/i.test(s);
    if (!Object.keys(csp).length) {
      record("FAIL", `${rel} CSP`, "app.security.csp is null or empty — set a Content Security Policy (design-to-tauri/references/security.md).");
    } else if (!csp["default-src"]) {
      record("FAIL", `${rel} CSP`, "CSP has no default-src, so anything it does not list loads from anywhere.");
    } else if (Object.values(csp).some((v) => /unsafe-eval/.test(v))) {
      record("FAIL", `${rel} CSP`, "CSP allows 'unsafe-eval'.");
    } else if (["default-src", "script-src", "connect-src"].some((k) => sources(k).some(anyOrigin))) {
      record("FAIL", `${rel} CSP`, "CSP allows any origin (*, https:, http:) in default-src, script-src or connect-src.");
    } else {
      record("PASS", `${rel} CSP set`);
    }
    if ((conf.app ?? conf.build ?? {}).withGlobalTauri === true) {
      record("WARN", `${rel} withGlobalTauri`, "window.__TAURI__ is exposed to every script in the WebView; import the APIs from the npm packages instead.");
    }

    // Capabilities: parsed, not grepped — an opener scope of https://* is fine, an HTTP-plugin scope is not.
    const listed = Array.isArray(security.capabilities) ? security.capabilities : null;
    const caps = [];
    const capDir = join(dir, "capabilities");
    if (existsSync(capDir)) {
      for (const f of readdirSync(capDir)) {
        if (f.endsWith(".json")) {
          const cap = readJson(join(capDir, f));
          if (cap) caps.push({ file: f, cap });
          else record("FAIL", `${rel} capabilities/${f}`, "not valid JSON");
        } else if (/\.(json5|toml)$/.test(f)) {
          record("SKIP", `${rel} capabilities/${f}`, "format not parsed — review its scopes by hand.");
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
    if (wide.length) record("FAIL", `${rel} HTTP capability scope`, `Wildcard hosts let any script in the WebView call anywhere — list exact API origins:\n${wide.join("\n")}`);
    else record("PASS", `${rel} HTTP capability scope`);
    if (cleartext.length) record("FAIL", `${rel} cleartext API origin`, `Remote hosts must be https:\n${cleartext.join("\n")}`);
    if (debugOrigins.length) {
      record("WARN", `${rel} debug origins in release capabilities`,
        `Emulator/LAN origins in a capability release builds enable — move them to a debug-only capability (security.md §2):\n${debugOrigins.join("\n")}`);
    }
    if (remote.length) record("FAIL", `${rel} remote capabilities`, `Remote URLs can call native commands (${remote.join(", ")}); remove or document a reviewed requirement.`);

    const cargoPath = join(dir, "Cargo.toml");
    if (existsSync(cargoPath)) {
      const cargo = readFileSync(cargoPath, "utf8").replaceAll("\r\n", "\n");
      // Every form of the dependency: `tauri = { … }` (arrays may span lines), `[dependencies.tauri]`, target tables.
      const specs = [
        ...[...cargo.matchAll(/^\s*tauri\s*=\s*(\{[\s\S]*?\}|.*)$/gm)].map((m) => m[0]),
        ...[...cargo.matchAll(/^\[(?:target\.[^\n]*\.)?dependencies\.tauri\][\s\S]*?(?=^\[|(?![\s\S]))/gm)].map((m) => m[0]),
      ];
      if (specs.some((s) => /["']devtools["']/.test(s))) record("FAIL", `${rel} devtools`, "The tauri crate enables the devtools feature for every build, including release.");
      else record("PASS", `${rel} no devtools in release`);
      const profile = cargo.match(/^\[profile\.release\]([\s\S]*?)(?=^\[|(?![\s\S]))/m)?.[1] ?? "";
      if (!/^\s*strip\s*=\s*(true|"symbols"|"debuginfo")/m.test(profile)) {
        record("WARN", `${rel} release profile`, "[profile.release] does not strip debug info (strip = true; design-to-tauri/references/security.md §5).");
      }
    }
  }
}

// --------------------------------------------- committed runtime suites (--suites)
async function suites() {
  if (!RUN_SUITES) return;
  const port = process.env.PORT ?? "3001";
  const base = (API_URL ?? `http://127.0.0.1:${port}`).replace(/\/$/, "");
  const candidates = HEALTH_URL ? [HEALTH_URL] : [`${base}/health/ready`, `${base}/health`, `${base}/api/v1/health`, `${base}/v1/health`];
  let up = false;
  for (const u of candidates) {
    try { const r = await fetch(u, { signal: AbortSignal.timeout(3000) }); if (r.status < 500) { up = true; break; } } catch { /* next */ }
  }
  if (!up) {
    record("FAIL", "suites: stack running", `No health answer at ${candidates.join(", ")}. Start the stack (and reset the demo data), or pass --api-url / --health-url.`);
    return;
  }
  const order = (name) => (name === "smoke" ? 0 : name === "test:contract" ? 1 : name === "test:security" ? 2 : 3);
  let ran = 0;
  for (const dir of packageDirs) {
    const rel = dir.slice(ROOT.length + 1) || ".";
    const scripts = (readJson(join(dir, "package.json")) ?? {}).scripts ?? {};
    const names = Object.keys(scripts)
      .filter((n) => n === "smoke" || (/^test:/.test(n) && !/^test:(watch|unit|cov|coverage|e2e:ui)(:|$)/.test(n)))
      .sort((a, b) => order(a) - order(b) || a.localeCompare(b));
    for (const name of names) {
      const r = runScript(pm, dir, name, 900_000);
      record(r.ok ? "PASS" : "FAIL", `${rel} ${name}`, r.ok ? undefined : r.tail);
      ran++;
    }
  }
  if (!ran) record("FAIL", "suites", "--suites given but no package defines smoke or test:* scripts (security-foundation/references/security-test-suites.md).");
}

// --------------------------------------------------------- suppression sweep
function suppressionSweep() {
  const re = /eslint-disable|@ts-ignore|@ts-expect-error|as any[^A-Za-z]|as unknown as/;
  const git = spawnSync("git", ["-C", ROOT, "rev-parse", "--git-dir"], { encoding: "utf8" });
  if (git.status !== 0) { record("SKIP", "suppression sweep", "not a git repo"); return; }
  const diff = spawnSync("git", ["-C", ROOT, "-c", "color.ui=never", "diff", "HEAD", "--", "apps", "packages"],
    { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const added = (diff.stdout ?? "").split("\n")
    .filter((l) => l.startsWith("+") && !l.startsWith("+++") && re.test(l));
  const untracked = spawnSync("git", ["-C", ROOT, "ls-files", "--others", "--exclude-standard", "--", "apps", "packages"],
    { encoding: "utf8" }).stdout?.split("\n").filter(Boolean) ?? [];
  const untrackedHits = grepFiles(
    untracked.map((f) => join(ROOT, f)).filter((f) => existsSync(f)), re, /$^/);
  const all = [...added.map((l) => l.trim().slice(0, 120)), ...untrackedHits];
  if (all.length) {
    record("FAIL", "no new suppressions vs HEAD", `Fix root causes instead:\n${all.slice(0, 10).join("\n")}`);
  } else {
    record("PASS", "no new suppressions vs HEAD");
  }
}

// --------------------------------------------------------- placeholder sweep
function placeholderSweep() {
  // Every client app's src (web, admin, mobile, desktop…); API servers are left to the audits.
  const dirs = packageDirs
    .filter((d) => d.startsWith(join(ROOT, "apps")))
    .filter((d) => { const p = readJson(join(d, "package.json")) ?? {}; return !{ ...p.dependencies, ...p.devDependencies }["@nestjs/core"]; })
    .map((d) => join(d, "src"))
    .concat(["apps/api/resources/js", "resources/js"].map((d) => join(ROOT, d)))
    .filter((d) => existsSync(d));
  if (!dirs.length) { record("SKIP", "placeholder sweep", "no frontend src dirs"); return; }
  const files = dirs.flatMap((d) => [...walk(d, [".ts", ".tsx", ".js", ".jsx"])]);
  const hits = grepFiles(files, /lorem ipsum|coming soon|not implemented|TODO: ?implement|mockData|fakeUsers|placeholder data|4242 ?4242/i);
  if (hits.length) {
    record("FAIL", "no demo/placeholder content", hits.slice(0, 10).join("\n"));
  } else {
    record("PASS", "no demo/placeholder content");
  }
}

await bootCheck();
tauriChecks();
suppressionSweep();
placeholderSweep();
await suites();

// ------------------------------------------------------------------ report
console.log("");
for (const r of results) {
  const mark = { PASS: "✓", FAIL: "✗", WARN: "!", SKIP: "–" }[r.status];
  console.log(` ${mark} [${r.status}] ${r.label}`);
  if (r.detail) console.log(r.detail.split("\n").map((l) => `      ${l}`).join("\n"));
}
console.log("");
const count = (status) => results.filter((r) => r.status === status).length;
const [failed, warned, skipped] = [count("FAIL"), count("WARN"), count("SKIP")];
if (failed) {
  console.log(`NOT DONE — ${failed} failing check(s). Fix at root cause (no suppressions), then re-run.`);
  process.exit(1);
}
if (STRICT && (warned || skipped)) {
  console.log(`NOT DONE (--strict) — ${warned} warning(s) and ${skipped} skipped check(s). A release claim needs every check run and clean.`);
  process.exit(1);
}
const caveat = warned || skipped
  ? ` — with ${warned} warning(s) and ${skipped} skipped check(s), so not a release claim (re-run with --strict)`
  : "";
console.log(RUN_SUITES
  ? `DONE — all live checks and committed suites green${caveat}. (Browser, device and accessibility evidence live in release-qa-gate's QA_COVERAGE.md.)`
  : `DONE — all live checks green${caveat}. (Run with --suites against the running stack for the committed runtime suites; browser and device QA are in release-qa-gate.)`);
