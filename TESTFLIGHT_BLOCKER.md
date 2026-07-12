# TestFlight Blocker

Status: blocked on Apple account certificate/provisioning state during TestFlight upload, not on the PR #43 cloud integration or the launch UI cleanup.

## Confirmed State

- Build `44` launch proof baseline is merge commit `4540381752db2eb5ac22442c8f49971e0d49f6cb`.
- PR #43 is merged and the integration workstream is complete on `main`.
- PR #46 and PR #47 hid launch testing/proof UI, kept the Settings Formspree support box, and auto-dismiss the Settings support banners.
- PR #48 bumped the next iOS TestFlight build to `1.0.0 (44)` because build `43` was already uploaded.
- Staging deploy proof passed in GitHub Actions run `28317412159`.
- Live Worker/direct editing version proof passed for the merged SHA.
- Deterministic Worker render smoke passed and produced a valid MP4.
- Previous TestFlight upload for build `43` succeeded in GitHub Actions run `28470081179`.
- Build `44` signed archive passed in GitHub Actions run `28756536677`.
- Build `44` upload failed in GitHub Actions run `28756673502` while re-archiving on a fresh runner.
- Build `44` upload rerun `28764285946` failed at the same signed archive gate.
- Follow-up signing-scope experiments in runs `28765082606` and `28765646576` proved that forcing `Apple Distribution` manually conflicts with the current automatic-signing workflow and should not be used without a manual provisioning profile.
- Corrected automatic-signing upload rerun `28765926589` failed at the same Apple account certificate/provisioning gate.

The build `44` archive job reached signing, created the archive, and verified:

- bundle ID: `atrak.charlie.hoopsclips`
- version: `1.0.0`
- build: `44`
- environment: `internal_staging`
- launch mode: `internal_only`

The latest corrected automatic-signing build `44` upload rerun reached signing after secrets and App Store Connect API key materialization. It failed with:

- Apple account has reached the maximum number of certificates and requires choosing a certificate to revoke.
- No matching iOS App Development provisioning profile was available for bundle ID `atrak.charlie.hoopsclips`.

## Required Account Holder Actions

1. Sign in to the Apple Developer account at `https://developer.apple.com/account/`.
2. Revoke unused/expired Apple Development or iOS Development certificates until CI automatic signing can create or use a valid certificate again.
3. Sign in to App Store Connect at `https://appstoreconnect.apple.com/agreements/`.
4. Verify Agreements, Tax, and Banking are current enough for TestFlight/App Store Connect operations.
5. Verify the App ID / bundle ID `atrak.charlie.hoopsclips` exists for the team.
6. Verify the App ID capabilities match the Xcode project and provisioning expectations.
7. Ensure valid signing/provisioning can be created for `atrak.charlie.hoopsclips` from the GitHub Actions runner.
8. Ensure the App Store Connect API key and team membership used by CI can perform automatic signing and TestFlight upload.

Do not paste private keys, API key contents, provisioning profile contents, or token values into chat or docs. Only report non-secret status and error lines.

## Rerun Command After Repair

From the repository:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
```

Build `44` already has a passing archive-only run (`28756536677`). The upload operation re-archives on a fresh runner, so the next useful gate after Apple certificate/provisioning repair is `operation=upload`.

Then complete the real-basketball TestFlight smoke checklist in `docs/phase_beta_launch_gates_after_pr43.md`.

## Expected Passing Archive Evidence

- `Build internal staging TestFlight archive`: success.
- Archive bundle ID: `atrak.charlie.hoopsclips`.
- Archive version: `1.0.0`.
- Archive build: `44`.
- App environment: `internal_staging`.
- Cloud launch mode: `internal_only`.
- Cloud analysis/edit base URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`.
- App-owned `PrivacyInfo.xcprivacy`: present at the app-bundle root and valid.

## Expected Passing Upload Evidence

- `Build internal staging TestFlight archive`: success.
- `Upload to internal TestFlight`: success.
- Log includes `Upload succeeded` and `Internal TestFlight upload command completed`.
- App Store Connect shows build `1.0.0 (44)` processing or available for internal TestFlight.
