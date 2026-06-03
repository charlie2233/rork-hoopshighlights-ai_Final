# Release Device Smoke Report

## Active snapshot (2026-06-03)
- Branch: `codex/phase-launch-proof-next` (`72dbecc`)
- Focus: internal TestFlight/launch-readiness proof (staging + submission gates), not current public Release status.
- Latest authoritative checks:
  - `python3 scripts/launch_backend_config_preflight.py --json` → `pass=85 warn=12 fail=0`.
  - Snapshot files:
    - `artifacts/launch_readiness/submission_readiness_skip_live_2026-06-03.json`
    - `artifacts/launch_readiness/submission_readiness_live_2026-06-03.json`
  - `python3 scripts/submission_readiness_preflight.py --skip-live --json` → `pass=22 warn=6 fail=4`.
    - Fails: missing `CLOUDFLARE_API_TOKEN`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, `GCP_REGION`; missing iOS upload inputs; and unreviewed accuracy bundle.
    - Human-review status from `python3 scripts/build_launch_team_accuracy_report.py --manifest artifacts/team_highlight_accuracy_manifest.json --label-status --json`:
      - `caseCount=2`, `clipCount=54`, `completeClipCount=0`, `incompleteClipCount=54`
      - `launch_label_case_all_001`: `30/30` incomplete
      - `launch_label_case_team_001`: `24/24` incomplete
  - `python3 scripts/submission_readiness_preflight --json` → `pass=22 warn=4 fail=6`.
    - Failures include live DNS/route probe errors (`URLError`) and missing required environment inputs.
  - The live checks include `expectedGitSha` reported by probe tooling as `72dbecc0eb469cafab57ad09356a9014d8d4b603`; both route checks fail due DNS resolution in this environment.
  - `python3 scripts/staging_version_probe.py --json` → `pass: fail`.
    - Diagnosis: `staging_version_unready` with both `worker` and `editing` route `URLError` failures.
- Untracked root folders remain preserved and intentionally unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Automated validation status at snapshot
- Backend configuration posture remains clean for staging intent (`pass=85`, no hard fails).
- Submission readiness is still blocked by missing environment inputs and live backend probe errors in this environment.
- CI/main branch workflow/state fetch currently does not return in this environment (`gh run list` fails here), and deploy preflight run state is not visible here.
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
- Missing deploy secrets in environment are still unresolved:
  - `CLOUDFLARE_API_TOKEN`
  - `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - `GCP_DEPLOY_SERVICE_ACCOUNT`
  - `GCP_PROJECT_ID`
  - `GCP_REGION`
- Missing iOS upload inputs in environment are still unresolved:
  - `HOOPS_DEVELOPMENT_TEAM`
  - `HOOPS_REVENUECAT_API_KEY`
  - `HOOPS_GOOGLE_CLIENT_ID`
  - `HOOPS_GOOGLE_REVERSED_CLIENT_ID`
  - `HOOPS_FIREBASE_AUTH_API_KEY`
  - `HOOPS_SENTRY_DSN`
  - `APP_STORE_CONNECT_KEY_ID`
  - `APP_STORE_CONNECT_ISSUER_ID`
  - `APP_STORE_CONNECT_API_KEY_BASE64`
  - `HOOPS_PRIVACY_POLICY_URL`
  - `HOOPS_TERMS_OF_SERVICE_URL`
- `team_highlight_labeling_bundle` is still incomplete (`0/54` clips reviewed), so launch-ready accuracy gate is unproven.
- iPhone import/review/export/share flow from installed TestFlight app is unproven in this environment.
- Live backend version probes currently fail with URLError from this environment; rerun from authorized, networked context.
- This branch did not perform signed archive/upload steps; it documents snapshot state only.

## Historical notes
- Prior entries in this file include previous build 4/27 Release-device verification from older branches and are retained for historical context.
