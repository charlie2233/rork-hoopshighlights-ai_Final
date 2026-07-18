# Phase Build 51 TestFlight Prep

Date: 2026-07-18

## Goal

Prepare the latest merged `main` state after PR #80 for a new internal TestFlight upload without reusing App Store Connect build `50`.

## What Changed

- Bumped the HoopsClips app target build number to `51`.
- Updated the internal staging config verifier to require `CURRENT_PROJECT_VERSION=51`.
- Updated the submission-readiness preflight expected iOS build number to `51`.
- Updated the `iOS Internal TestFlight Upload` workflow archive/status assertions and App Store Connect status query to target build `51`.
- Refreshed launch docs to keep build `50` as the currently available TestFlight build and classify build `51` as the next upload candidate until upload/status proof exists.

## Boundary

This prep does not upload to TestFlight by itself. Build `51` is not available to testers until the signed upload workflow and read-only status workflow both pass on `main`.

## Rerun Commands

After this prep lands on `main`, upload build `51`:

```bash
gh workflow run ios-testflight-upload.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=upload
```

After the upload run succeeds, verify App Store Connect processing and internal availability:

```bash
gh workflow run ios-testflight-upload.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=status
```

Then install the latest internal TestFlight build and run the real-basketball smoke checklist in `docs/phase_beta_launch_gates_after_pr43.md`.
