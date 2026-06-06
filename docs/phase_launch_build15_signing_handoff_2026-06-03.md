# Phase Launch Build 15 Signing Handoff - updated 2026-06-06

## Current branch

- Branch: `codex/phase-clip1-gpt-led-highlight-editor`
- Current signing target: HoopClips `1.0.0` build `15`
- Bundle ID: `atrak.charlie.hoopsclips`
- Current signing evidence doc: `docs/phase_launch_build15_archive_signing_recheck_2026-06-06.md`

## Current-head proof that is green

Latest staging/cloud proof on the branch:

- Cloud Edit Deploy Preflight run `27055102528`: success
- Worker and editing service `/version`: `200`
- Deployed SHA: `dd860a62a4a012867b30099fc886c7530aaa16ff`

The iOS workflow input check also proves required TestFlight upload input names
are present without printing values.

## Current signed archive blocker

Signed archive/upload is still blocked by Apple account/provisioning state.
The latest current-branch archive attempts reached the signing step and failed
with non-secret markers:

- Apple account has reached the maximum number of certificates.
- No provisioning profile was found for bundle id `atrak.charlie.hoopsclips`.

Most relevant current-branch runs:

- `27054133236`: original archive attempt on current branch; failed at signed archive.
- `27054196968`: manual `Apple Distribution` identity experiment; failed because it conflicted with automatic signing.
- `27054245288`: corrected automatic-signing workflow with global `DEVELOPMENT_TEAM`; failed on Apple certificate/profile capacity.

The workflow now keeps automatic signing and passes `DEVELOPMENT_TEAM` globally
so Swift Package targets inherit the team. The remaining failure is account-side
certificate/profile capacity, not a source compile failure.

## Secret-safe Apple Developer handoff

Use this prompt for a browser/account-side helper. Do not paste secrets back into chat.

```text
Fix HoopClips Apple signing for internal TestFlight.

App bundle ID: atrak.charlie.hoopsclips
Marketing/build waiting for upload: 1.0.0 build 15
Branch to rerun after signing repair: codex/phase-clip1-gpt-led-highlight-editor

Current GitHub Actions evidence:
- Cloud deploy/preflight run 27055102528 passed.
- iOS archive run 27054245288 failed at Apple signing/provisioning.
- Failure markers: max Apple certificates; no profile for atrak.charlie.hoopsclips.

Please do not return private keys, certificate files, passwords, tokens, base64 values, credentials, or full secret contents.

Needed outcome:
1. Revoke or clean up an unused Apple signing certificate if required.
2. Ensure automatic signing can create or use a valid profile for bundle ID atrak.charlie.hoopsclips.
3. Return only non-secret status: what was fixed, the visible certificate/profile names if helpful, and whether CI can rerun iOS operation=archive.
```

## Next steps after Apple signing is repaired

1. Rerun `iOS Internal TestFlight Upload` with `operation=archive` on branch `codex/phase-clip1-gpt-led-highlight-editor`.
2. If the signed archive metadata passes, run `operation=upload` for build `15`.
3. After App Store Connect processing, run installed TestFlight smoke on a trusted iPhone.
4. Do not mark launch ready until the human-reviewed accuracy report and installed TestFlight smoke are both proven.
