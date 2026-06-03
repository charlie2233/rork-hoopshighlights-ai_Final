# Release Device Smoke Report

## Active snapshot (2026-06-03)
- Branch: `codex/phase-launch-proof-next` (`832fd12` after label-review handoff cleanup)
- Focus: internal TestFlight/launch-readiness proof (staging + submission gates), not current public Release status.
- Latest authoritative checks:
  - `python3 scripts/launch_backend_config_preflight.py --json` -> `pass=85 warn=12 fail=0`.
  - Snapshot files:
    - `artifacts/launch_readiness/submission_readiness_skip_live_2026-06-03.json`
    - `artifacts/launch_readiness/submission_readiness_live_2026-06-03.json`
  - `python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_labeling_bundle/temp_mapped_draft/team_highlight_accuracy_report.json --json` -> `pass=26 warn=1 fail=7`.
    - Required cloud deploy and iOS upload input names are visible locally or in the GitHub staging environment without printing secret values.
    - Live Worker `/v1/editing/version` and direct editing `/version` both return non-secret feature-flag state.
    - Direct editing `/version` still reports a stale `gitSha`, so current source must be deployed before submission-readiness can be claimed.
    - Human-review status from `python3 scripts/build_launch_team_accuracy_report.py --manifest artifacts/team_highlight_accuracy_manifest.json --label-status --json`:
      - `caseCount=2`, `clipCount=54`, `completeClipCount=0`, `incompleteClipCount=54`
      - `launch_label_case_all_001`: `30/30` incomplete
      - `launch_label_case_team_001`: `24/24` incomplete
    - The `temp_mapped_draft` accuracy report is rejected as draft evidence and does not count toward launch readiness.
  - Latest branch-dispatched workflow evidence is positive but stale to the current tip:
    - `Cloud Edit Deploy Preflight` run `26860674510`: success on `bc37b0e`.
    - `iOS Internal TestFlight Upload` runs `26860672121`, `26860897604`, and `26861050768`: success on `bc37b0e`.
    - Current branch tip is `832fd12`, so rerun branch workflows after any launch-meaningful code/config change before treating them as current-tip proof.
  - Latest main workflow failures are stale relative to this branch but still real until main is updated and rerun:
    - `Cloud Edit Deploy Preflight` run `26766947519`: main expected quick-scan max candidate clips `160`; this branch expects the current default `320`.
    - `iOS Internal TestFlight Upload` run `26766947563`: main expected build `11`; this branch aligns internal staging build `14`.
- Untracked root folders remain preserved and intentionally unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Automated validation status at snapshot
- Backend configuration posture remains clean for staging intent (`pass=85`, no hard fails).
- Submission readiness is still blocked by label evidence, installed TestFlight smoke, stale direct editing deploy SHA, failed main workflow state, skipped secret-gated deploy proof, and current-tip workflow freshness.
- CI/main branch workflow logs show code-side failures that are fixed on this branch, but they must be proven on main after landing.
- Known known blockers from live evidence:
  - Secret-gated deploy workflow job remains `skipped`, so provider credential readiness is not launch-proven.
  - Connected iPhone unavailable in this environment for physical smoke tests.
  - Direct editing service deploy SHA is stale.
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
- Required deploy and iOS upload input-name checks pass without exposing values, but the secret-gated deploy job is still skipped and must be rerun as `credential-check`, then `preflight` or `deploy`.
- `team_highlight_labeling_bundle` is still incomplete (`0/54` clips reviewed), so launch-ready accuracy gate is unproven.
- iPhone import/review/export/share flow from installed TestFlight app is unproven in this environment.
- Live backend version probes return feature flags, but direct editing deploy SHA is stale; deploy current source before claiming readiness.
- This branch did not perform signed archive/upload steps; it documents snapshot state only.

## Historical notes
- Prior entries in this file include previous build 4/27 Release-device verification from older branches and are retained for historical context.
