# Phase Build 51 TestFlight Prep And Upload Proof

Date: 2026-07-18

## Goal

Prepare the latest merged `main` state after PR #80 for a new internal TestFlight upload without reusing App Store Connect build `50`, then record the successful upload/status proof.

## What Changed

- Bumped the HoopsClips app target build number to `51`.
- Updated the internal staging config verifier to require `CURRENT_PROJECT_VERSION=51`.
- Updated the submission-readiness preflight expected iOS build number to `51`.
- Updated the `iOS Internal TestFlight Upload` workflow archive/status assertions and App Store Connect status query to target build `51`.
- Initially refreshed launch docs to keep build `50` as the available TestFlight build while build `51` waited for upload/status proof.
- After merge, upload/status proof was collected and launch docs were refreshed again to make build `51` the current internal TestFlight build.

## Boundary

The prep commit did not upload to TestFlight by itself. After it merged, the signed upload workflow and read-only status workflow passed on `main`.

## Upload Proof

- PR #81 merge SHA: `60eda29b7989e97a93ebdf973c0d80446caa07bf`.
- Main push/codecheck run `29644908038`: success; build settings, export options, and 12 focused unsigned simulator tests passed.
- Upload run `29644918870`: success; signed archive, metadata/privacy checks, App Store Connect upload, and runner-owned certificate cleanup passed.
- Status run `29645129050`: success; App Store Connect reports build `1.0.0 (51)` as `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, `readyForInternalTesting=true`, not expired, minimum iOS `17.0`, and `usesNonExemptEncryption=false`.

## Rerun Commands

To upload a later build after another build-number bump:

```bash
gh workflow run ios-testflight-upload.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=upload
```

After the upload run succeeds, verify App Store Connect processing and internal availability:

```bash
gh workflow run ios-testflight-upload.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=status
```

Then install the latest internal TestFlight build and run the real-basketball smoke checklist in `docs/phase_beta_launch_gates_after_pr43.md`.
