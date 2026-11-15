# Tauri client security

The WebView runs web code with a bridge to native functions. Whatever the capabilities grant, any
script in the WebView can use, an injected one included. Lock the shell down before the first screen
and again before every release.

`verify-done.mjs` reads the shell's configuration; the last column names the label each check
prints. A check that fails makes the script exit 1. A check marked warning prints `PASS` with a
detail line starting `warning:`, and `--strict`, which a release claim uses, turns it into a
failure. A file the script cannot parse (`tauri.conf.json5`, `Tauri.toml`, or a capability file in
`.json5` or `.toml`) prints `NOT RUN` under `Tauri shell` or `capabilities/<file>`: review its
settings by hand against this table.

## Configuration

| Setting | What to do | Label in `verify-done.mjs` |
|---|---|---|
| `app.security.csp` in `tauri.conf.json` | Set it with a `default-src`. No `unsafe-eval`. No `*`, `https:` or `http:` in `default-src`, `script-src` or `connect-src`. Bundle every script. Origins for hot reload go in `app.security.devCsp`, which applies to `tauri dev` only. Add the production API origin to `img-src` before a release build. | `CSP` fails on a missing or empty CSP, a missing `default-src`, `unsafe-eval` or an any-origin source; `CSP set` is the pass |
| Capabilities | Least privilege: list the release set in `app.security.capabilities` (without it every file in `capabilities/` is enabled) and grant each plugin only what a screen uses. | the rows below |
| HTTP scope | Exact origins. No `*` in the scheme or the host (`https://*`, `https://*.example.in/*`); a path wildcard is fine. The `opener` scope may use `https://*`, `tel:` and `mailto:`, never `file:`. | `HTTP capability scope` fails on a wildcard in an `http:` permission |
| API origins | Remote hosts are `https`. | `cleartext API origin` fails on a remote `http` origin |
| Debug origins | Emulator, loopback and private-network origins live in `capabilities/dev.json`, switched on only for debug builds by `tauri.dev.conf.json`, never in a capability that a release enables. | `debug origins in release capabilities` (warning) |
| Remote capabilities | None, unless a reviewed requirement says so. | `remote capabilities` fails |
| `tauri` crate | No `devtools` feature, in any form of the dependency. | `devtools` fails; `no devtools in release` is the pass |
| `[profile.release]` | `strip = true`. | `release profile` (warning) |
| `withGlobalTauri` | Off; import the APIs from the npm packages. | `withGlobalTauri` (warning) |
| The files themselves | `tauri.conf.json` and each file in `capabilities/` are valid JSON. | `tauri.conf.json` and `capabilities/<file>` fail when they are not |

Custom Rust commands validate every argument; none takes a path, a URL or SQL from the web layer
without checking it against an allowlist. The script does not check this.

## Secrets and tokens

These are checked on a device, not by the script (rule TAU-7).

- No secret in the bundle: no API key, signing key or admin token in source or in `VITE_*`
  variables. Anything in the app can be extracted from the package.
- The access token lives in memory only. The refresh token goes in OS-protected storage, in debug
  and release builds alike so that the emulator runs the real path: a small plugin over the Android
  Keystore and the iOS Keychain, or a maintained community plugin that does the same, pinned after
  reading its changelog and source. `tauri-plugin-store` writes a plain JSON file: preferences only.
- On sign-out, and when a refresh is refused, wipe the stored refresh token and every cached query.
  Never log tokens, codes or contact details; logcat shows them to anyone with `adb`.
- Prove it on a debug build: `adb shell run-as <identifier> find . -type f`, then read every store,
  JSON and preference file. No refresh token appears in plain text.

## Transport and links

- Release builds reach the API over HTTPS only; cleartext is allowed in the debug manifest alone.
- Requests go through the native HTTP plugin, which is not subject to browser CORS. If any call uses
  the WebView's own `fetch`, the API's allowed CORS origins must include the WebView's origins,
  exactly (`navree-security-checklist`).
- Check every deep link and scanned payload against an exact scheme, host and path allowlist before
  acting. A link never carries a token that the app trusts without the API verifying it.

## WebView limits

- Treat passkeys (WebAuthn) as unavailable in the system WebView and WKWebView for a bundled origin
  until a device run proves otherwise; offer the other first factors the API has (`navree-auth`).
  Biometric unlock, if added, guards local access to the refresh token; it is not an authentication
  factor for the API.

## Release checklist

- [ ] `verify-done.mjs --strict` prints `PASS` for every label above with no `warning:` line.
- [ ] The CSP has the production API origin; the release capabilities are listed; the HTTP scope
      holds exact `https` production origins only.
- [ ] No `devtools`, no cleartext, and the release profile strips.
- [ ] The refresh token is in the keystore, proved with `run-as`; the plain store holds no secret.
- [ ] A search of the built web layer for tokens, keys and logging of auth data finds none.
- [ ] Deep-link and scan handlers reject unknown schemes and hosts, tested.
