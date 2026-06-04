# Phase Launch Build 15 Signing Handoff - 2026-06-03

## Current branch

- Branch: `codex/phase-launch-proof-next`
- Current code head before this docs-only note: `46ac2ac3f09f7805f5ae4848806d05c45396f0e8`
- Internal TestFlight marketing/build target: `1.0.0` build `15`
- Build `15` was created because build `14` was already uploaded successfully from older branch head `bc37b0ec5613ecee87d90e057245abeb92865800`.

## Current-head proof that is green

These runs are on `46ac2ac3f09f7805f5ae4848806d05c45396f0e8`.

- Cloud Edit Deploy Preflight `operation=preflight`: GitHub Actions run `26877407142`
  - Worker typecheck and dry run: success
  - Editing backend Python tests plus launch script tests: success
  - Secret-gated cloud edit deploy preflight: success
  - No deploy or rollback was requested.
- iOS Internal TestFlight Upload `operation=codecheck`: GitHub Actions run `26877408870`
  - No-secret internal staging codecheck: success
  - Signed archive/upload path was skipped by design.

## Signed archive blocker

Signed iOS archive preflight is not green for build `15` yet. The latest repo state keeps automatic signing, which is the same signing mode that previously produced build `14`.

Observed failed runs:

- `ade3ec0` signed archive preflight retry: GitHub Actions run `26927591040`
- `af93d57` signed archive preflight retry: GitHub Actions run `26877074295`
- `af93d57` initial signed archive preflight: GitHub Actions run `26876817391`
- `b7b3a0a` distribution-signing experiment: GitHub Actions run `26877277110`

The distribution-signing experiment was reverted in `46ac2ac` because Xcode reported a signing-mode conflict. The actionable blocker from the automatic-signing attempts is Apple account/provisioning state, not a source compile failure:

- Apple account reached the maximum number of certificates.
- No matching provisioning profile was available for bundle ID `atrak.charlie.hoopsclips`.

## 2026-06-04 current-branch retry

The signed archive path was rerun on branch `codex/phase-launch-proof-next` at
head `ade3ec0` with `iOS Internal TestFlight Upload` operation `preflight`.
The run failed before upload, and no App Store Connect upload was attempted.

- Run: `26927591040`
- Job: `Build internal staging TestFlight archive`
- Result: `failure`
- Non-secret failure symptoms:
  - Apple account reached the maximum number of certificates.
  - No matching iOS App Development provisioning profile was available for
    bundle ID `atrak.charlie.hoopsclips`.

This confirms the signed archive blocker is still Apple account/provisioning
state, not an iOS source compile failure.

## Secret-safe Apple Developer handoff

Use this prompt for a browser/account-side helper. Do not paste secrets back into chat.

```text
Fix HoopClips Apple signing for internal TestFlight.

App bundle ID: atrak.charlie.hoopsclips
Marketing/build waiting for upload: 1.0.0 build 15
Branch head to rerun after signing repair: 46ac2ac3f09f7805f5ae4848806d05c45396f0e8

GitHub Actions evidence:
- Cloud preflight run 26877407142 passed.
- iOS no-secret codecheck run 26877408870 passed.
- Signed archive preflight failed because Apple signing/provisioning is unavailable.

Please do not return private keys, certificate files, passwords, tokens, base64 values, credentials, or full secret contents.

Needed outcome:
1. Revoke or clean up an unused Apple signing certificate if required.
2. Ensure automatic signing can create or use a valid profile for bundle ID atrak.charlie.hoopsclips.
3. Return only non-secret status: what was fixed, the visible certificate/profile names if helpful, and whether CI can rerun iOS operation=preflight.
```

## Next steps after Apple signing is repaired

1. Rerun `iOS Internal TestFlight Upload` with `operation=preflight` on branch `codex/phase-launch-proof-next`.
2. If the signed archive preflight passes, run `operation=upload` for build `15`.
3. After App Store Connect processing, run installed TestFlight smoke on a trusted iPhone.
4. Do not mark launch ready until the human-reviewed accuracy report and installed TestFlight smoke are both proven.
