# Tauri client security

A Tauri app runs web code with a bridge to native power. The bridge is the attack surface: whatever the capabilities grant, any script running in the WebView (including an injected one) can do. Lock it down before the first screen and re-check before every release. `verify-done.mjs` fails on the items marked ✱ and warns on those marked ⚠ (a warning fails `--strict`, which release claims use).

## 1. Content Security Policy ✱

`tauri.conf.json` → `app.security.csp` must be set, with a `default-src`, never `null` or `{}`. Start from:

```json
"csp": {
  "default-src": "'self'",
  "script-src": "'self'",
  "style-src": "'self' 'unsafe-inline'",
  "img-src": "'self' data: blob: http://10.0.2.2:<api-port> http://localhost:<api-port>",
  "connect-src": "'self' ipc: http://ipc.localhost",
  "font-src": "'self' data:"
}
```

- No `unsafe-eval`, no remote `script-src`, no `*`, `https:` or `http:` in `default-src`, `script-src` or `connect-src`. Bundle every script.
- Hot reload needs extra origins in development only (the Vite dev server and its `ws://` socket): put them in `app.security.devCsp`, which applies to `tauri dev` only, not in `csp`.
- Add the production API origin to `img-src` (and `connect-src` only if the WebView fetches directly) before a release build.
- Tauri injects nonces/hashes for its own scripts at build time; a CSP that breaks the app in production is a bug in the CSP, not a reason to null it.

## 2. Capabilities — least privilege ✱

`src-tauri/capabilities/*.json` lists what the frontend may call. Grant per plugin only the permissions a feature uses, for the windows that need them. List the release set explicitly so nothing else is picked up (without `app.security.capabilities`, every file in the folder is enabled):

```jsonc
// tauri.conf.json
"app": { "security": { "csp": { … }, "capabilities": ["default"] } }

// capabilities/default.json — what release builds get
{
  "identifier": "default",
  "windows": ["main"],
  "permissions": [
    "core:default",
    { "identifier": "http:default", "allow": [{ "url": "https://api.example.com/*" }] },
    { "identifier": "opener:allow-open-url", "allow": [{ "url": "https://*" }, { "url": "tel:*" }, { "url": "mailto:*" }] },
    "notification:default",
    "os:default"
  ]
}

// capabilities/dev.json — emulator and LAN origins, debug only
{ "identifier": "dev", "windows": ["main"],
  "permissions": [{ "identifier": "http:default", "allow": [{ "url": "http://10.0.2.2:<api-port>/*" }, { "url": "http://localhost:<api-port>/*" }] }] }

// tauri.dev.conf.json — merged in for dev and debug QA builds: `tauri android dev --config src-tauri/tauri.dev.conf.json`
{ "app": { "security": { "capabilities": ["default", "dev"] } } }
```

- **The HTTP scope lists exact origins.** No `*` anywhere in the scheme or host (`"*"`, `"https://*"`, `"https://*.example.com/*"`, `"http://*:4100/*"`) — any of those turns the app into an open proxy for injected script ✱. Path wildcards (`/*`) are fine. Remote hosts are `https` only ✱; emulator and LAN origins in a capability that release builds enable are a warning ⚠.
- **Opener** scopes may use `https://*` — opening a link in the system browser is not an API call — plus only the schemes used (`tel:`, `mailto:`, the WhatsApp/web origins). Never `file:` or arbitrary paths.
- No `remote` capability URLs (letting a remote site call native commands) unless a product requirement says so and it is reviewed ✱.
- Custom Rust commands validate every argument; they never take a path, URL or SQL from the frontend without checking it against an allowlist.

## 3. Secrets and tokens

- No secrets in the bundle: no API keys, signing keys, admin tokens in `VITE_*` or source. Anything in the app can be extracted from the APK/IPA.
- **Access token in memory only.**
- **Refresh token in OS-protected storage**, in debug and release alike (so the emulator exercises the real path). Options, in order of preference:
  1. a small Tauri mobile plugin over the platform store — Android Keystore (an AES key in the Keystore encrypting a value in app-private storage) and iOS Keychain (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`);
  2. a maintained community plugin that does the same, pinned after reading its changelog and source;
  3. Stronghold, only with a random passphrase that is itself held in the Keystore/Keychain — never a constant in code.
- `tauri-plugin-store` writes plain JSON into app data — preferences only.
- On sign-out and on `session.ended`/`401` after a failed refresh: wipe the stored refresh token and every cached query.
- Never log tokens, OTPs or contact details to the console (logcat ships them to anyone with `adb`).
- **Prove it on the device** (debug build): `adb shell run-as <identifier> find . -type f`, then read every store, JSON and preferences file — no refresh token appears in plain text.

## 4. Transport

- Release builds reach the API over HTTPS only; cleartext is debug-only (manifest/network security config).
- Requests go through the native HTTP plugin; the server still applies CORS to WebView-origin requests if any (`http://tauri.localhost`, `tauri://localhost` and the Vite dev origin must be on its allowlist only if the app uses the WebView's own `fetch`).
- Certificate pinning is optional; if used, plan rotation before release.

## 5. Build flags

- DevTools only in debug: no `devtools` feature on the `tauri` crate, in any form of the dependency (`tauri = { … }`, `[dependencies.tauri]`, target-specific tables) ✱.
- Release builds strip debug info (`[profile.release]`: `strip = true` ⚠, `lto = true`, `codegen-units = 1`, `panic = "abort"` when crash reporting does not need unwinding).
- `withGlobalTauri` off unless needed ⚠; import APIs from the npm packages.

## 6. Deep links and QR payloads

- Validate every deep link and scanned QR payload against an exact scheme + host + path allowlist before acting. A QR sign-in token is exchanged with the API only after the payload matches the expected prefix; never auto-open arbitrary URLs from a scan.
- Deep links never carry tokens in the URL for the app to trust without server verification.

## 7. WebView limits that are security-relevant

- **Passkeys/WebAuthn are unavailable** in the Android System WebView and WKWebView for an app-bundled origin. Offer password, one-time code, TOTP two-factor and QR sign-in from a signed-in web session.
- Biometric unlock (if added) gates access to the stored refresh token on the device; it is not a server authentication factor.

## Release checklist

- [ ] `verify-done.mjs --strict` clean for the app (no failures, no warnings).
- [ ] CSP set with `default-src`; production API origin added; no `unsafe-eval`; dev origins only in `devCsp`.
- [ ] Release capabilities listed explicitly; HTTP scope lists exact `https` production origins; debug origins only in the dev capability.
- [ ] No `devtools` feature, no cleartext, release profile strips debug info.
- [ ] Refresh token in Keystore/Keychain (proved with `run-as`); plain store holds no secrets.
- [ ] `grep` the built frontend for tokens, keys, `console.log` of auth data: none.
- [ ] Deep-link and QR handlers reject unknown schemes/hosts (tested).
