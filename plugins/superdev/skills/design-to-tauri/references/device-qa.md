# Device QA

`mobile-qa-tester` runs this list, or the main agent does (hard rule 25). Evidence goes under
`qa/mobile-qa-tester/<area>/`, which is git-ignored: screenshots, `logcat.txt` and a `RESULTS.md`
with one line per step (`PASS`, `FAIL` or `NOT RUN`, and the evidence path). The report is
`qa/mobile-qa-tester.md`.

## Setup

- Build a debug APK and install it:
  `tauri android build --debug --apk --target <abi> --config src-tauri/tauri.dev.conf.json`,
  `adb install -r <apk>`, `adb shell am start -n <identifier>/.MainActivity`. Use an emulator image
  that matches the host CPU, or a phone with USB debugging.
- The emulator reaches the host at `10.0.2.2`, so an API listening on `127.0.0.1` works
  (`navree dev` listens on `http://127.0.0.1:8080`). A phone on USB:
  `adb reverse tcp:<port> tcp:<port>` and use `http://localhost:<port>`. A phone on Wi-Fi needs the
  API bound to `0.0.0.0`, the LAN origin in `capabilities/dev.json` and a firewall rule on the host.
- Prove a finished module on an installed APK; `tauri android dev` is for the loop while a screen is
  being built.
- With several devices attached, pass `-s <serial>` to every `adb` command and give each agent one
  device.
- The commands that are not obvious: `adb shell uiautomator dump` (the WebView's accessibility tree,
  for labels and bounds), `adb shell screencap -p` then `adb pull`, `adb logcat -c` before a run and
  `adb logcat -d` after it. Do not redirect `adb exec-out` output in PowerShell; it corrupts the
  PNG.

## Every module run

1. The module's main task, end to end.
2. Empty, loading and error states (stop the API for the error state).
3. Keyboard: fields scroll into view above it and sheets are not covered.
4. Insets: nothing sits under the status bar, the cutout or the gesture bar.
5. Android back at every depth: sheet, then screen, then home tab, then exit.
6. Rotation and process death, when the module holds unsaved input: it restores or warns.
7. Logcat has no app error and no unhandled rejection.

## The final pass, at the `product-qa` gate

- The sign-in variants the product offers, token expiry and refresh (run the QA API with a short
  access-token lifetime, found through `navree-auth` and never set that way in production), revoking
  and blocking while signed in, live updates, notifications from the background, and recovery after
  airplane mode.
- Contrast and tap targets of at least 48 dp inside the WebView, measured through the debug build's
  WebView DevTools socket (`adb forward` to `webview_devtools_remote_<pid>`), and the stored-secrets
  check of [security](security.md).
- One run on the smallest screen the product supports.
- A release-build smoke: `tauri android build --apk` without the dev config, signed with a throwaway
  QA keystore kept outside git, never the store key. It installs and launches, exposes no DevTools
  socket and refuses cleartext to the local API. It is a QA build, not a release.

## Limits to record, not fake

Each is `NOT RUN` with its reason in `qa/mobile-qa-tester.md`, for the operator to accept in
writing: iOS needs a Mac; an emulator's virtual camera cannot scan a real code; closed-app push
needs Firebase or Apple push credentials and a real phone; a platform or screen size that was not
available.
