# Release Device Smoke Report

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
