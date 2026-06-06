# Installed TestFlight Smoke Handoff - updated 2026-06-06

This handoff is for the person with access to a trusted physical iPhone and the
current internal TestFlight build. It does not mark the smoke gate complete.

Do not paste secrets, tokens, private keys, passwords, session cookies, base64
values, or full presigned URLs into chat, screenshots, notes, or logs.

## Current status

- Branch: `codex/phase-clip1-gpt-led-highlight-editor`
- Latest staging deploy proof: Cloud Edit Deploy Preflight run `27055102528`
- Deployed/staging SHA: `dd860a62a4a012867b30099fc886c7530aaa16ff`
- Installed TestFlight smoke: not complete
- Current physical iPhone state: paired but unavailable to CoreDevice
- Current iPhone blocker detail: `tunnelState=unavailable`, `ddiServicesAvailable=false`
- Current archive/upload blocker: Apple signing/provisioning capacity for bundle id `atrak.charlie.hoopsclips`
- Current accuracy blocker: reduced bundle remains `0/18` complete

This smoke should run only after the tester has a processed current internal
TestFlight build installed on a trusted physical iPhone and the intended cloud
environment is confirmed.

## Prerequisites before running smoke

Confirm these non-secret facts first:

- Current internal TestFlight build is processed and installable.
- Tester iPhone is trusted, unlocked, reachable by USB or same-LAN CoreDevice tunnel, and can launch the installed TestFlight app.
- `xcrun devicectl list devices` reports an available physical iPhone.
- App build number and branch/SHA are known.
- Cloud analysis/edit base URLs for this build are confirmed by the release owner.
- The tester has at least one real basketball source video available in Photos or Files.

Do not run this as launch evidence against an old developer-installed build or a
historical TestFlight upload.

## Current device recovery before smoke

The current device recheck is documented in:

```text
docs/phase_launch_device_tunnel_recheck_2026-06-06.md
```

Recovery steps:

1. Unlock the iPhone.
2. Connect it by USB, or put the phone and Mac on the same local network with wireless debugging available.
3. Open Xcode Devices and Simulators if needed to refresh CoreDevice.
4. Rerun `xcrun devicectl list devices`.
5. Continue only when the physical iPhone is available.

## Smoke path to execute

Run the full path on the physical iPhone:

1. Install HoopClips from TestFlight.
2. Cold launch the app.
3. Confirm legal links open.
4. Sign in or continue using the intended internal-test auth path.
5. Import a real basketball video from Photos.
6. Import or open a real basketball video from Files if available.
7. Confirm the app shows readable import/progress/recovery copy.
8. Run team scan or pre-analysis team choice.
9. Choose either a detected team or `All teams`.
10. Start cloud analysis.
11. Confirm analysis status stays cloud-owned and does not mention local analysis fallback, fake thinking, or ETA copy.
12. Open Review.
13. Confirm clip cards and controls are readable on the phone.
14. Keep/remove at least one clip if needed.
15. Go to Export or AI Edit.
16. Choose an edit intent/style and target length.
17. Render through the cloud backend.
18. Confirm work receipt/timeline/status is readable.
19. Preview the finished MP4.
20. Download or save the saved reel.
21. Share/open the MP4 through the iOS share sheet.
22. If available, open/share to at least one editor target such as Files, Photos, CapCut, iMovie, or Adobe.
23. Request one revision such as `More Hype`, `Shorter`, or a similar allowed edit note.
24. Preview and share/open the revised MP4.
25. Close and reopen HoopClips.
26. Use History to resume the project, watch source video, watch saved reel, share saved reel, and delete only if cleanup is intended.

## Evidence to report back

Report only non-secret evidence:

- TestFlight build number.
- App version/build if visible.
- Commit SHA or branch if known.
- iPhone model and iOS version.
- Cloud environment label used for the build, such as internal staging or production.
- Whether each smoke path step passed or failed.
- Any failing step name and short non-secret description.
- Whether the rendered MP4 previewed.
- Whether save/download succeeded.
- Which share/open-in targets were verified.
- Whether History resume/source/saved-reel/share/delete controls worked.
- Screenshot names or local file paths for redacted screenshots, if collected.

Do not report login credentials, passwords, API keys, tokens, private keys,
base64 secret values, full presigned URLs, upload/source/render/object-key URLs,
or personal contact/payment identifiers.

## Completion criteria

The installed TestFlight smoke blocker can be marked resolved only after:

- A current internal TestFlight build is installed from TestFlight, not from a local developer install.
- The full import -> team choice -> cloud analysis -> Review -> cloud render -> preview -> download/save -> share/open-in -> revision -> History path passes.
- Failures are either fixed and rerun or explicitly documented as launch blockers.
- `ios/docs/reports/release-device-smoke-report.md` is updated with the passing build number, device, date, and non-secret evidence.
- The current readiness snapshot is updated with the passing smoke evidence.

Until then, internal TestFlight readiness remains incomplete.
