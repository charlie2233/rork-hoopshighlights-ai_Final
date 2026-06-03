# Release Device Smoke Report

## Active snapshot (2026-06-02)
- Branch: `codex/phase-launch-proof-next` (`bc37b0e`)
- Focus: internal TestFlight/launch-readiness proof (staging + submission gates), not current public Release status.
- Latest authoritative checks:
  - `python3 scripts/launch_backend_config_preflight.py --json` → `pass=85 warn=12 fail=0`.
  - `python3 scripts/submission_readiness_preflight.py --skip-live --json` → `pass=22 warn=6 fail=4`.
  - `python3 scripts/submission_readiness_preflight --json` → `pass=22 warn=4 fail=6`.
    - Failures include URLError live probes + missing required environment inputs.
  - `python3 scripts/staging_version_probe.py --json` → worker and editing version probes failed with `Probe failed: URLError` in this environment.
- Untracked root folders remain preserved and intentionally unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Automated validation status at snapshot
- Backend configuration posture remains clean for staging intent (`pass=85`, no hard fails).
- Submission readiness is still blocked by missing environment inputs and unverified live backend/device path.
- CI/main branch preflight status fetch currently does not return in this environment.
- Known known blockers from live evidence:
  - Missing cloud deploy inputs for `cloud-edit-deploy-preflight`.
  - Missing iOS upload inputs for `ios-testflight-upload`.
  - Connected iPhone unavailable in this environment for physical smoke tests.
  - Live version probes are unreachable from this environment (`URLError`).

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
- Missing deploy secrets and iOS upload secrets in environment are still unresolved.
- `team_highlight_labeling_bundle` is still incomplete (`0/54` clips reviewed), so launch-ready accuracy gate is unproven.
- iPhone import/review/export/share flow from installed TestFlight app is unproven in this environment.
- Live backend version probes currently fail with URLError from this environment; rerun from authorized, networked context.
- This branch did not perform signed archive/upload steps; it documents snapshot state only.

## Historical notes
- Prior entries in this file include previous build 4/27 Release-device verification from older branches and are retained for historical context.
