#!/usr/bin/env node
// verify-done.mjs — live Definition-of-Done check for a SuperDev-built monorepo.
//
// Replaces the old bash done-gate + hand-marked completion ledger: nothing
// is read from a self-graded ledger; every check runs NOW, against the real
// tree and the real built artifact. Cross-platform (Windows/macOS/Linux), no
// dependencies. Run from the target monorepo root:
//
//   node <superdev-plugin>/scripts/verify-done.mjs [--root DIR] [--skip-build]
//        [--skip-boot] [--health-url URL]
//
// Exit 0 = done (as far as machines can tell). Exit 1 = not done; the report
// names the exact failing checks. Fix at root cause — suppressions fail here.

import { spawn, spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
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

const results = []; // {status: 'PASS'|'FAIL'|'SKIP', label, detail?}
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

function runScript(pm, dir, script) {
  const cmd = pm === "npm" ? `npm run ${script}` : `${pm} run ${script}`;
  const res = spawnSync(cmd, { cwd: dir, shell: true, encoding: "utf8", timeout: 600_000 });
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
  const child = spawn(process.execPath, [dist], { cwd: join(ROOT, "apps", "api"), env: process.env });
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
    const ports = [...new Set([portMatch?.[1], process.env.PORT, "3001", "3000", "4203", "8080"].filter(Boolean))];
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
  const dirs = ["apps/web/src", "apps/admin/src", "apps/api/resources/js", "resources/js"]
    .map((d) => join(ROOT, d)).filter((d) => existsSync(d));
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
suppressionSweep();
placeholderSweep();

// ------------------------------------------------------------------ report
console.log("");
let failed = 0;
for (const r of results) {
  if (r.status === "FAIL") failed++;
  const mark = { PASS: "✓", FAIL: "✗", SKIP: "–" }[r.status];
  console.log(` ${mark} [${r.status}] ${r.label}`);
  if (r.detail) console.log(r.detail.split("\n").map((l) => `      ${l}`).join("\n"));
}
console.log("");
if (failed) {
  console.log(`NOT DONE — ${failed} failing check(s). Fix at root cause (no suppressions), then re-run.`);
  process.exit(1);
}
console.log("DONE — all live checks green. (Audits and browser QA are separate skills; this script proves build, boot, and hygiene.)");
