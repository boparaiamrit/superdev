# Release builds

Only when the operator asks for a store or sideload build. Re-run `security.md`'s release checklist first.

## Android

- **Signing key:** create an upload keystore once (`keytool -genkeypair -v -keystore upload.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload`). Store it and its passwords in a secret manager, never in the repo. Reference it from a gitignored `keystore.properties` read by the Gradle config, or from CI secrets.
- **Versions:** `version` in `tauri.conf.json` (semver) and a monotonically increasing Android version code (`bundle.android.versionCode`, or derived). Never reuse a version code.
- **Build:** `pnpm tauri android build --aab` for Play (all ABIs); `--apk` for sideloading. Confirm the release manifest has no cleartext and the Rust library is stripped.
- **Play Console:** internal testing track first; data-safety form must match what the app actually collects; target the current required API level.

## iOS (macOS + Xcode)

- Team and bundle ID set in Xcode or `bundle.iOS.developmentTeam`.
- `pnpm tauri ios build --export-method app-store-connect` (or `release-testing` for ad hoc).
- Privacy manifest and every usage-description string present; App Store Connect privacy answers match the app.

## Desktop

- Windows: `tauri build` produces MSI/NSIS; sign with a code-signing certificate or SmartScreen will warn.
- macOS: sign with a Developer ID and notarize, or Gatekeeper blocks the app.
- Updater (optional): the Tauri updater plugin with a signing key pair; the public key is in the app, the private key never leaves the release pipeline.

## Proof before shipping

- The release artifact installs on a clean device/emulator, signs in against the production API (or staging), and passes the device QA smoke.
- `adb logcat` clean; no debug menus; demo hints off.
- Version code higher than the last published one.
