# dg-mobile

Minimal Operaton testing demo: a native Java Android app displaying **Hello world**.
No external runtime libraries. Requires Android 6.0 (API 23) or newer.

## Build and release

Use Java 17, Gradle 8.9, and Android SDK 35 (including Build Tools 35.0.0):

```sh
gradle --no-daemon testDebugUnitTest lintDebug assembleDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`.
Operaton prepares `release/<version>` and release notes. RC tags build an APK
and upload the `release-payloads` Actions artifact. Operaton verifies the bytes
and publishes an RC prerelease with `SHA256SUMS`, never latest. Final tags copy
the approved RC bytes into a draft without rebuilding; Operaton verifies and
publishes the final release.

## Download and install

Download `dg-mobile-v0.1.0.apk` and `SHA256SUMS` from the
[v0.1.0 release](https://github.com/glothriel/dg-mobile/releases/tag/v0.1.0).
In the download directory:

```sh
sha256sum --check SHA256SUMS
adb install -r dg-mobile-v0.1.0.apk
```

Alternatively, open the APK on your Android device and allow installation from
that download source. Launch **dg-mobile** to see **Hello world**.

This is an installable **demo/debug-key-signed APK**, not a production release.
CI generates the standard Android debug key; no real signing credentials are used.
Keys may change between CI runs, so uninstall a previous demo first if Android
rejects an update due to a signature mismatch.
