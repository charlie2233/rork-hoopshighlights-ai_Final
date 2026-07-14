# TestFlight Signing Incident

Status: resolved on July 13, 2026. Build `1.0.0 (44)` was uploaded successfully and App Store Connect reports it as `VALID` and `IN_BETA_TESTING`.

This file is retained as the non-secret incident record and rerun guide. Apple signing is no longer the blocker; the remaining beta path is build `45` upload, its compatible Worker deploy, and installed real-basketball TestFlight smoke.

Build `45` is the next upload candidate because it adds install-bound analysis polling and cancellation. The strict Worker must not be deployed before build `45` is available to internal testers; build `44` does not send `installId` on its legacy analysis poll request.

## Resolution Evidence

- PR #43 remains merged; the enhancement integration workstream was not redone.
- Current merged signing-lifecycle baseline: `45c383a91d6b8223a33032593a839e72e041b955`.
- Staging deploy, live Worker/direct editing version proof, and deterministic Worker render smoke remain passed.
- Build `44` signed archive run `28756536677`: passed.
- Upload diagnostic run `29297858325`: failed at signing with the certificate-capacity and missing-profile errors.
- Apple API inspection found ten stale `Apple Development: Created via API` certificates left by earlier ephemeral CI runners. Their private keys no longer existed after those runners ended.
- The ten stale CI development certificates were revoked while the existing distribution certificate was preserved.
- Upload run `29298033420`: passed the signed archive, archive metadata/privacy checks, and `Upload to internal TestFlight`.
- App Store Connect build `1.0.0 (44)`: `VALID`, `IN_BETA_TESTING`, not expired, minimum iOS `17.0`, and no non-exempt encryption declaration required.
- The one development certificate created by the successful ephemeral runner was revoked after upload.
- PR #59 merged at `45c383a91d6b8223a33032593a839e72e041b955`. Its archive-only run `29309860620` passed signed archive/metadata checks, intentionally skipped upload, and revoked the runner-owned development certificate through the new serial-bound cleanup.

No certificate contents, private keys, API key contents, provisioning profile contents, passwords, or tokens belong in this file.

## Root Cause

The automatic-signing workflow used a fresh GitHub-hosted runner for every archive. Xcode created a new development certificate through the App Store Connect API, but the certificate's private key disappeared with the runner. Repeated archive attempts accumulated ten unusable API-created development certificates and exhausted the account limit.

Revoking only the local Mac's development certificate did not remove those CI-created certificates. That is why the first July 13 retry still returned:

- `Choose a certificate to revoke. Your account has reached the maximum number of certificates.`
- `No profiles for 'atrak.charlie.hoopsclips' were found.`

## Recurrence Prevention

The signed workflow now serializes automatic-signing jobs and refuses to start Xcode while any preexisting API-created development certificate needs reconciliation. It records the runner's local certificate serials before signing, then its `always()` cleanup step revokes only a matching API certificate whose serial was newly installed on that runner or extracted from that runner's archive. It refuses to delete more than one.

If a runner disappears before cleanup, the leaked certificate causes the next signed run to stop before creating another certificate. The operator must then reconcile that single non-secret certificate record through Apple before retrying. This fail-closed path prevents another silent certificate buildup without deleting a same-named certificate created by another repository or manual Xcode session.

The workflow preserves the distribution certificate and never prints or commits private material.

## Future Rerun Command

Use this only when a later build needs to be uploaded:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
```

Expected passing evidence:

- `Build signed internal staging archive`: success.
- Bundle ID: `atrak.charlie.hoopsclips`.
- Version/build: the values expected by the workflow.
- Environment: `internal_staging`.
- Launch mode: `internal_only`.
- App-owned `PrivacyInfo.xcprivacy`: present and valid at the app-bundle root.
- `Upload to internal TestFlight`: success for `operation=upload`.
- `Revoke this runner's automatic signing certificate`: success with zero or one serial-matched certificate revoked.

## Remaining TestFlight Work

Upload build `45`, wait until App Store Connect reports it ready for internal testing, deploy the matching strict staging Worker, and complete the real-basketball checklist in `docs/phase_beta_launch_gates_after_pr43.md`. Record the result in `ios/docs/reports/release-device-smoke-report.md` without secrets, private video contents, presigned URLs, object keys, or local file paths.
