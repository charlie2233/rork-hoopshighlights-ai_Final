# Phase Launch51: TestFlight Build 4 Readiness

## Goal

Record current internal TestFlight readiness evidence after the staging cloud deploy was repaired and build 4 was uploaded.

## Evidence

- Branch: `codex/phase-launch51-testflight-build4-readiness`
- Base commit: `fd7313e0ca9eb9a53fbd08f03354cb11a96ce42d`
- iOS upload workflow run: `26674584185`
- Upload log evidence: `xcodebuild -exportArchive` reported `Upload succeeded`, `Uploaded HoopsClips`, and `Internal TestFlight upload command completed`.
- App Store Connect app ID: `6763813635`
- App Store Connect build check, using Xcode `altool --generate-jwt` without printing token/key material:
  - build ID: `ef4ac814-216f-4843-b648-95edfaf4481a`
  - bundle build number: `4`
  - uploaded date: `2026-05-29T21:39:13-07:00`
  - processing state: `VALID`
  - expired: `false`
  - uses non-exempt encryption: `false`
- Connected iPhone check:
  - one paired iPhone is available through `xcrun devicectl`
  - installed HoopClips on the phone is still build `3`, so build `4` must be installed from TestFlight before the post-install smoke can start
- Staging version probe:
  - `python3 scripts/staging_version_probe.py --expected-git-sha fd7313e0ca9eb9a53fbd08f03354cb11a96ce42d --json`
  - result: passed for both direct editing service and staging Worker

## Readiness Meaning

Build 4 is uploaded and processed by App Store Connect, and the cloud staging backend/Worker version path is live on the same commit. This is enough to proceed to the trusted-phone internal TestFlight smoke once build 4 is installed on the device.

This does not prove App Store submission readiness yet. The launch gate still requires:

- build 4 installed from TestFlight on the real iPhone
- upload/import of a short basketball clip
- cloud team scan and selected-team analysis
- Review
- Export
- AI Edit render
- preview
- More Hype revision
- revised preview
- share/open-in
- launch-grade selected-team/highlight accuracy evidence meeting the 85% quality target

## Safety Notes

- No private key contents, JWT, base64 API key, R2 credentials, or full presigned URLs were printed.
- The iOS app remains a control surface only; cloud owns analysis, GPT editing, render planning, rendering, storage, and revision work.
- The readiness checker now accepts current-SHA CI upload proof when no local `.xcarchive` or `.ipa` exists, because the signed archive was created on the GitHub-hosted runner and uploaded directly to TestFlight.

## Validation

Commands:

```sh
git diff --check
python3 -m unittest scripts.test_submission_readiness_preflight -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/submission_readiness_preflight.py --skip-live
```

Results:

- `git diff --check`: passed.
- `scripts.test_submission_readiness_preflight`: 32 tests passed.
- Full script test discovery: 109 tests passed.
- `submission_readiness_preflight.py --skip-live`: improved from 7 launch failures to 3 current failures while preserving the real launch gates:
  - tracked/untracked files are dirty because this branch is in progress
  - launch-grade selected-team/highlight accuracy report is missing
  - installed TestFlight post-install smoke is still unproven

Follow-up refinement after fast-forwarding `main`: the readiness checker now also accepts prior upload/deploy proof when later commits changed only docs/scripts and no iOS upload-relevant or cloud deploy-relevant files.
