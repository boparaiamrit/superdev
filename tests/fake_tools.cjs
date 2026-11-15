// Stand-ins for navree and cargo in the tests of verify-done.mjs, loaded with NODE_OPTIONS=--require.
//
// When FAKE_TOOLS names a JSON file, a spawnSync call for `navree` or `cargo` is answered from it instead
// of starting the program; every other call (git, package managers) is passed on. The file maps the command
// line ("navree routes --json") to {exit, stdout, stderr, expect_env: {NAME: value}, write: {path: text}}.
// A command line the file does not list exits 9. `write` creates files relative to the working directory,
// the way navree openapi:export does; `expect_env` makes the call fail unless the variable has that value.
const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

if (process.env.FAKE_TOOLS) {
  const tools = JSON.parse(fs.readFileSync(process.env.FAKE_TOOLS, "utf8"));
  const realSpawnSync = childProcess.spawnSync;
  childProcess.spawnSync = function spawnSync(command, args, options) {
    if (command !== "navree" && command !== "cargo") return realSpawnSync.apply(this, arguments);
    const line = `${command} ${(Array.isArray(args) ? args : []).join(" ")}`;
    const spec = tools[line];
    if (!spec) return { status: 9, signal: null, stdout: "", stderr: `no stand-in for: ${line}\n`, output: null, pid: 0 };
    const env = (options && options.env) || process.env;
    const cwd = (options && options.cwd) || process.cwd();
    let status = spec.exit === undefined ? 0 : spec.exit;
    let stderr = spec.stderr || "";
    for (const [name, value] of Object.entries(spec.expect_env || {})) {
      if (env[name] !== value) {
        status = 1;
        stderr = `${name} is not ${value}\n`;
      }
    }
    for (const [file, text] of Object.entries(spec.write || {})) {
      const target = path.resolve(cwd, file);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, text);
    }
    return { status, signal: null, stdout: spec.stdout || "", stderr, output: null, pid: 0 };
  };
}
