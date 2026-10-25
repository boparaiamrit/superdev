# Device QA — driving the app on an emulator

The `mobile-qa-tester` agent runs this playbook; the main agent can run it directly. Evidence goes to `apps/mobile/qa/<area>/` (gitignored): screenshots, logcat, a short `RESULTS.md` with one line per step (pass/fail + evidence path), summarised into `QA_COVERAGE.md` §9 by the release gate.

Commands are bash — use Git Bash on Windows (set `MSYS_NO_PATHCONV=1` for device paths). The SDK tools live in `$ANDROID_HOME/emulator`, `platform-tools` and `cmdline-tools/latest/bin` (on Windows `%LOCALAPPDATA%\Android\Sdk\…`).

## Setup

```bash
# once: an emulator image matching the host CPU (x86_64 on Intel/AMD, arm64-v8a on Apple Silicon)
sdkmanager "system-images;android-35;google_apis;x86_64"
avdmanager create avd -n qa -k "system-images;android-35;google_apis;x86_64" -d pixel_7

emulator -list-avds
emulator -avd qa -accel on -gpu auto -no-boot-anim &
adb wait-for-device && adb shell getprop sys.boot_completed   # 1 when ready
pnpm --filter @<scope>/mobile tauri android build --debug --apk --target x86_64 --config src-tauri/tauri.dev.conf.json
adb install -r apps/mobile/src-tauri/gen/android/app/build/outputs/apk/universal/debug/app-universal-debug.apk
adb shell am start -n <identifier>/.MainActivity
```

- **Reaching the API.** The emulator's `10.0.2.2` is the host's loopback, so an API listening on `127.0.0.1` works. A physical phone over USB: `adb reverse tcp:<api-port> tcp:<api-port>` and use `http://localhost:<api-port>`. A phone over Wi-Fi needs the API bound to `0.0.0.0`, the LAN origin in the dev capability, and a firewall rule on the host.
- **Cleartext** to the local API works only because the debug manifest allows it (scaffolding.md); a debug build without it fails every request.
- **Fast loop while building a screen:** `tauri android dev` (hot reload against the Vite server; `TAURI_DEV_HOST` for a phone). Prove a finished module on an installed APK.
- **Several devices attached:** pass `-s <serial>` on every `adb` command; one agent per device.

## Driving

| Need | Command |
| --- | --- |
| Find buttons/fields | `adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml` — the WebView's accessibility tree (labels, `aria-label`s, bounds) |
| Tap / type / key | `adb shell input tap X Y`, `input text 'abc'` (escape spaces as `%s`), `input keyevent KEYCODE_BACK|KEYCODE_HOME|KEYCODE_ENTER` |
| Several fast taps | one `adb shell "input tap …; input tap …"` call (each adb spawn costs ~0.5 s) |
| Swipe / pull to refresh | `adb shell input swipe x1 y1 x2 y2 300` |
| Screenshot | `adb shell screencap -p /sdcard/qa.png && adb pull /sdcard/qa.png qa/<area>/<nn>-<step>.png` (redirecting `adb exec-out` output in PowerShell corrupts the PNG) |
| Logs | `adb logcat -c` before a run; `adb logcat -d > qa/<area>/logcat.txt`; web console lines appear under the Tauri console tag |
| Offline | `adb shell cmd connectivity airplane-mode enable|disable` |
| Notification shade | `adb shell cmd statusbar expand-notifications` then screenshot; `collapse` after |
| Files for pickers | `adb push photo.jpg /sdcard/Pictures/` then trigger a media scan (`content call --method scan_volume --uri content://media --arg external_primary`) |
| App state, contrast, tap targets | WebView DevTools (debug build): `adb shell cat /proc/net/unix | grep webview_devtools_remote` → `adb forward tcp:9333 localabstract:webview_devtools_remote_<pid>` → Chrome DevTools Protocol (`Runtime.evaluate` for route, form values, element rects; or Playwright `connectOverCDP` to run the release gate's axe and contrast scripts) |
| Stored secrets (debug build) | `adb shell run-as <identifier> find . -type f`, then read the store/JSON/preferences files: no refresh token in plain text |

Screen coordinates from CSS: `x_screen = x_css × devicePixelRatio`, `y_screen = y_css × devicePixelRatio + status-bar height` (read both from the device once).

## What every module run covers

1. Happy path of the module's main task, end to end.
2. Empty, loading and error states (stop the API for the error state).
3. Keyboard: fields scroll into view above the keyboard; sheets are not covered.
4. Insets: nothing under the status bar, cutout or gesture bar (portrait; landscape if supported).
5. Android back at every depth: sheet → screen → home tab → exit.
6. Rotation / process death if the module holds unsaved input (restore or warn).
7. Logcat: no app errors or unhandled rejections.

## What the final pass adds (release-qa-gate)

- Sign-in variants, token expiry and refresh, revoke and block live, live updates, phone alerts from the background, airplane mode recovery.
- Contrast and tap targets (≥ 48 dp) inside the WebView, and the stored-secrets check.
- One run on the smallest supported screen size.
- **Release-build smoke:** `tauri android build --apk` without the dev config, signed with a throwaway QA keystore (`keytool -genkeypair -keystore qa-release.jks -alias qa -keyalg RSA -validity 30`, kept outside git) — never the store key. It installs and launches, has no WebView DevTools socket, and refuses cleartext to the local API. If an HTTPS staging API exists, it signs in and passes the main flow against it; if not, record those steps `NOT RUN`. This is a QA build, not a release; a store release happens only when the operator asks (release.md).

## Limits to record, not fake

Each goes into `QA_COVERAGE.md` as `NOT RUN` with the reason, for the operator to accept:

- Emulators without internet cannot download on-demand scanner models; test the paste fallback.
- The virtual camera cannot show a real QR code; prove scanning on a phone.
- iOS needs a Mac.
- Closed-app push needs FCM/APNs credentials and a real phone.
