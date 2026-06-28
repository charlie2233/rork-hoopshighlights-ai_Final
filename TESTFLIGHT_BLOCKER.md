# TestFlight Blocker

Status: blocked on Apple account license/provisioning, not on the PR #43 cloud integration.

## Confirmed State

- `main` is at merge commit `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- PR #43 is merged and the integration workstream is complete on `main`.
- Staging deploy proof passed in GitHub Actions run `28317412159`.
- Live Worker/direct editing version proof passed for the merged SHA.
- Deterministic Worker render smoke passed and produced a valid MP4.
- Signed iOS archive failed in GitHub Actions run `28317649241`.

The archive job reached signing after secrets and App Store Connect API key materialization. It failed with:

- Apple Developer Program License Agreement update required.
- No provisioning profiles found for bundle ID `atrak.charlie.hoopsclips`.

## Required Account Holder Actions

1. Sign in to the Apple Developer account at `https://developer.apple.com/account/`.
2. Accept the latest Apple Developer Program License Agreement for the team.
3. Sign in to App Store Connect at `https://appstoreconnect.apple.com/agreements/`.
4. Verify Agreements, Tax, and Banking are current enough for TestFlight/App Store Connect operations.
5. Verify the App ID / bundle ID `atrak.charlie.hoopsclips` exists for the team.
6. Verify the App ID capabilities match the Xcode project and provisioning expectations.
7. Ensure valid Apple Distribution / App Store provisioning can be created for `atrak.charlie.hoopsclips`.
8. Ensure the App Store Connect API key and team membership used by CI can perform automatic signing and TestFlight upload.

Do not paste private keys, API key contents, provisioning profile contents, or token values into chat or docs. Only report non-secret status and error lines.

## Rerun Commands After Repair

From the repository:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=archive
```

After the archive succeeds:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
```

Then complete the real-basketball TestFlight smoke checklist in `docs/phase_beta_launch_gates_after_pr43.md`.

## Expected Passing Archive Evidence

- `Build internal staging TestFlight archive`: success.
- Archive bundle ID: `atrak.charlie.hoopsclips`.
- Archive version: `1.0.0`.
- Archive build: `43`.
- App environment: `internal_staging`.
- Cloud launch mode: `internal_only`.
- Cloud analysis/edit base URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`.

