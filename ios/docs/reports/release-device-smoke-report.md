# Release Device Smoke Report

## Active snapshot (2026-07-15)

- Device: trusted physical iPhone with internal TestFlight `1.0.0 (45)` installed.
- Source: real basketball video, 379.9 MB, split into forty-eight 8 MB upload parts.
- Result: failed at upload; progress remained at 14%, so team scan, analysis, Review, AI Edit, render, download, Photos, and share/open export were not reached.
- Evidence: two parts completed while one active part remained idle. The app was backgrounded, and the 15-minute signed upload plan expired before the 10-minute request-idle timeout and retry sequence could recover.
- Fix candidate: build `46` changes the background request-idle timeout to 90 seconds, preserving the existing retry/backoff policy while keeping its worst-case idle recovery inside the signed upload window.
- Automated regression: the background upload configuration asserts a 90-second request timeout, 24-hour resource timeout, connectivity waiting, and non-discretionary transfer behavior.
- Apple state: signing/provisioning is resolved and is not the blocker for this attempt.
- Next gate: upload/install build `46`, rerun this real-basketball flow, and record every downstream step separately.

## Active snapshot (2026-07-05)

- Branch evidence source: `main`
- Build `44` launch proof baseline: `4540381752db2eb5ac22442c8f49971e0d49f6cb`
- PR #43: merged, integration complete.
- PR #46 and PR #47: merged, launch proof/testing UI hidden and Settings Formspree support retained with auto-dismiss banners.
- PR #48: merged, next TestFlight build bumped to `1.0.0 (44)`.
- Staging deploy: passed in `Cloud Edit Deploy Preflight` run `28317412159`.
- Live Worker/direct editing version proof: passed for the merged SHA.
- Deterministic Worker render smoke: passed and produced a valid H.264/AAC MP4.
- iOS build `43` upload: succeeded in `iOS Internal TestFlight Upload` run `28470081179`.
- iOS build `44` archive: succeeded in `iOS Internal TestFlight Upload` run `28756536677`.
- iOS build `44` upload: blocked in `iOS Internal TestFlight Upload` runs `28756673502` and `28764285946`.
- Current blocker: Apple certificate limit/provisioning state for `atrak.charlie.hoopsclips`.
- Handoff: `TESTFLIGHT_BLOCKER.md`
- Real-basketball TestFlight checklist: `docs/phase_beta_launch_gates_after_pr43.md`

Installed build `44` TestFlight smoke remains unproven until the account holder repairs Apple certificate/provisioning state, CI uploads the internal build, and a trusted iPhone runs the real-basketball flow from upload through render, download, save to Photos, and share/open export.

## Active snapshot (2026-06-03)
- Branch: `codex/phase-launch-proof-next`
- Evidence head before this report refresh: `2976d4b`
- Focus: internal TestFlight/launch-readiness proof (staging + submission gates), not current public Release status.
- Latest authoritative checks:
  - `Cloud Edit Deploy Preflight` run `26885100097`: success on `2976d4b`.
    - Worker typecheck/dry run passed.
    - Editing backend Python tests passed.
    - Secret-gated deploy credential jobs were skipped; deploy credentials remain unproven until the workflow is run in the credential/deploy mode.
  - `iOS Internal TestFlight Upload` run `26885101901`: success on `2976d4b` with `operation=codecheck`.
    - No-secret internal staging codecheck passed.
    - Signed TestFlight archive job was skipped intentionally.
  - `Release Secrets Preflight` run `26884199422`: failed on `86fdc33`.
    - Non-secret missing GitHub `production` environment variables:
      - `HOOPS_CLOUD_ANALYSIS_BASE_URL`
      - `HOOPS_CLOUD_EDIT_BASE_URL`
    - Handoff: `docs/phase_launch_release_secrets_cloud_url_blocker_2026-06-03.md`
  - Secret-free live backend status snapshot:
    - `GET https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version` returned HTTP `200`.
    - Response reported cloud FFmpeg render support, AI Edit render/revision/template flags, GPT clip editor/planner/revision flags, and GPT highlight reranker configured.
    - Handoff: `docs/phase_launch_live_backend_status_2026-06-03.md`
  - Human-reviewed label gate remains open:
    - Latest inspected label bundle status: `caseCount=2`, `clipCount=54`, `completeClipCount=0`, `incompleteClipCount=54`.
    - `launch_label_case_all_001`: `30/30` incomplete.
    - `launch_label_case_team_001`: `24/24` incomplete.
    - GPT draft/mapped labels do not count as launch evidence until every clip has `needsLabel=false` and `reviewedByHuman=true`.
- Untracked root folders remain preserved and intentionally unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Automated validation status at snapshot
- Current branch has green safe CI proof for cloud preflight and iOS no-secret codecheck at `2976d4b`.
- Submission readiness is still blocked by label evidence, installed TestFlight smoke, skipped secret-gated deploy proof, missing production cloud URL variables, and signed archive/TestFlight upload proof.
- Branch proof is not a substitute for main/default-branch proof after landing.
- Known known blockers from live evidence:
  - GitHub `production` variables `HOOPS_CLOUD_ANALYSIS_BASE_URL` and `HOOPS_CLOUD_EDIT_BASE_URL` are missing.
  - Secret-gated deploy workflow jobs remain `skipped`, so provider credential readiness is not launch-proven.
  - Connected iPhone unavailable in this environment for physical smoke tests.
  - Human-reviewed team/highlight label bundle is incomplete (`0/54`).


## Manual real-device validation required
- Install internal TestFlight build on trusted, trusted iPhone.
- Confirm on-device launch, version, and team/edit/intent flow.
- Import one short basketball clip from Photos and one from Files.
- Run cloud analysis and confirm Review clip load.
- Run AI Edit render, preview MP4, run one revision, and preview revised MP4.
- Save/download final and revised reels, and share/open in common editors.
- Verify About & Privacy, Support, and launch status screens.
- Run accessibility smoke pass (VoiceOver, largest text, Reduce Motion, normal mode) and collect screenshots/notes.

## Result template
| Check | Result | Notes |
| --- | --- | --- |
| Cold launch | blocked | iPhone connectivity unavailable in this environment (`devicectl`/`xcrun` device state could not be used for trusted-device smoke). |
| Google sign-in | blocked | Requires trusted device run with installed build. |
| Firebase email/password | blocked | Requires trusted device run with installed build. |
| RevenueCat purchase | blocked | Requires trusted device run with sandbox credentials. |
| RevenueCat restore | blocked | Requires trusted device run with sandbox credentials. |
| Photos import | blocked | Requires trusted device run with TestFlight installed app. |
| Files import | blocked | Requires trusted device run with TestFlight installed app. |
| On-device analysis | blocked | Requires trusted device run with TestFlight installed app. |
| Review flow | blocked | Requires trusted device run with TestFlight installed app. |
| Export render | blocked | Requires trusted device run with TestFlight installed app. |
| Save to Photos | blocked | Requires trusted device run with TestFlight installed app. |
| Open-in/share | blocked | Requires trusted device run with TestFlight installed app. |
| Legal links open | blocked | Requires trusted device run with TestFlight installed app. |
| Accessibility normal mode | blocked | Verify using `ios/docs/checklists/release-accessibility-smoke-checklist.md` once device is online. |
| Accessibility VoiceOver | blocked | Verify using `ios/docs/checklists/release-accessibility-smoke-checklist.md` once device is online. |
| Accessibility largest text | blocked | Verify using `ios/docs/checklists/release-accessibility-smoke-checklist.md` once device is online. |
| Accessibility Reduce Motion | blocked | Verify using `ios/docs/checklists/release-accessibility-smoke-checklist.md` once device is online. |

## Blockers
- GitHub `production` environment is missing `HOOPS_CLOUD_ANALYSIS_BASE_URL` and `HOOPS_CLOUD_EDIT_BASE_URL`; `Release Secrets Preflight` run `26884199422` failed until those non-secret variables are confirmed and set.
- Required deploy and iOS upload input-name checks pass without exposing values, but the secret-gated deploy job is still skipped and must be rerun as `credential-check`, then `preflight` or `deploy`.
- `team_highlight_labeling_bundle` is still incomplete (`0/54` clips reviewed), so launch-ready accuracy gate is unproven.
- iPhone import/review/export/share flow from installed TestFlight app is unproven in this environment.
- Internal staging Worker `/v1/editing/version` is live and reports cloud/GPT/render capability, but this does not close production cloud cutover or installed TestFlight smoke.
- This branch did not perform signed archive/upload steps; it documents snapshot state only.

## Historical notes
- Prior entries in this file include previous build 4/27 Release-device verification from older branches and are retained for historical context.

## 2026-06-03 current handoff update

Current launch branch evidence before installed-device smoke:

- Branch: `codex/phase-launch-proof-next`
- HEAD: `a780814 docs: link signing handoff in readiness snapshot`
- `Cloud Edit Deploy Preflight` run `26892016399`: `success`
- `iOS Internal TestFlight Upload` codecheck run `26892019111`: `success`

Installed TestFlight smoke remains unproven. Use the current handoff before
claiming this report green:

- `docs/phase_launch_installed_testflight_smoke_handoff_2026-06-03.md`

The smoke result should be added here only after a current TestFlight-installed
build runs on a trusted physical iPhone through import, team choice, cloud
analysis, Review, cloud render, preview, download/save, share/open-in, revision,
and History recovery. Keep production URL, human accuracy review, and Apple
signing/archive blockers separate unless each has current passing evidence.
