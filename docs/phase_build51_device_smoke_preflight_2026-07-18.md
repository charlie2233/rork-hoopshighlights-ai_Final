# Phase Build 51 Device Smoke Preflight

Date: 2026-07-18 Pacific

## Purpose

Make the first physical-device gate repeatable before the full real-basketball
smoke starts:

```text
installed HoopClips app == atrak.charlie.hoopsclips 1.0.0 (51)
```

This is not a replacement for the real-basketball smoke. It only proves that
the trusted iPhone is reachable and running the correct TestFlight build before
upload, team scan, analysis, Review, AI Edit, render, download, Photos save,
and share/open export are tested.

## Helper

```bash
python3 scripts/check_installed_testflight_build.py
```

With an explicit device:

```bash
python3 scripts/check_installed_testflight_build.py --device E5786BB6-0095-5509-8B85-110C0B5CE6D3
```

To also launch the already-installed app after metadata passes:

```bash
python3 scripts/check_installed_testflight_build.py --device E5786BB6-0095-5509-8B85-110C0B5CE6D3 --launch
```

The helper is read-only unless `--launch` is passed. It does not install an
app, upload to App Store Connect, archive, submit, or print secrets.

## Current Attempt

Current `devicectl` discovery reports the paired phone in the device table:

```text
charlie's iPhone / E5786BB6-0095-5509-8B85-110C0B5CE6D3 / available (paired) / iPhone 15 Pro
```

One helper run read installed-app metadata and confirmed the installed HoopClips
app is still build `49`:

```text
bundleId: atrak.charlie.hoopsclips
marketingVersion: 1.0.0
buildNumber: 49
```

Blocker:

```text
Build number mismatch: expected 51, got 49.
```

Later reruns intermittently lost the CoreDevice app metadata channel even while
the device table still showed `available (paired)`. Recovery: unlock the iPhone,
connect by USB or restore same-network device tunneling, reopen Xcode Devices if
needed, install/update HoopClips `1.0.0 (51)` from TestFlight, then rerun the
helper.

## Required Follow-Up

After the helper reports `installedTestFlightBuildReady: true`, run the full
real-basketball TestFlight smoke:

1. Install or confirm HoopClips `1.0.0 (51)` from TestFlight.
2. Upload real basketball video.
3. Wait for `proxy_ready`.
4. Run team scan.
5. Run analysis.
6. Open Review.
7. Run AI Edit.
8. Render.
9. Download.
10. Save to Photos.
11. Share/open export.

Only mark the installed TestFlight smoke complete after every step has current
evidence from the TestFlight-installed build.
