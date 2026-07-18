# Release Device Smoke Report

## Active snapshot (2026-07-18)

- Current uploaded build: internal TestFlight `1.0.0 (52)` from main SHA `f46705959eb1d792e93d03999eb43c828de114f0`.
- Staging deployment: run `29632345235` passed editing/Worker deployment and live version proof for the build `50` main SHA. Live capabilities and a fresh secret-safe presign probe confirmed a 3,600-second signed upload lease.
- TestFlight upload: run `29656420482` passed signed archive, metadata/privacy checks, upload, and runner-owned certificate cleanup for build `52`.
- App Store Connect processing: status run `29656700078` confirmed build `52` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing.
- Apple state: developer/app agreements, bundle ID, and certificates are active; signing is not the current blocker.
- Device proof: build `49` was installed and launched on the paired iPhone. A real 380 MB basketball source produced a 24-part plan and four background sessions, reached about 15%, then expired with `0/24` completed parts before team scan.
- Root-cause classification: the upload had enough throughput to cross initial progress, but the 15-minute lease and foreground/background reconciliation discarded recoverable multipart state. This is not evidence for changing basketball detection thresholds.
- Build `52` fix baseline: build `51` one-hour signed URLs, bounded multipart lease renewal, active-session-first foreground reconciliation, completed-part finalization without the original temporary source, concise resume notices, AI Edit selected-style polish, and PR #85 upload-status declutter.
- Automated proof: all 46 Worker tests passed, control-plane typecheck passed, launch config preflight passed with `85` passes and `0` failures, and the exact focused iOS CI selection passed all 12 tests across three suites. Merged-main CI, staging deployment, signed archive/upload, Apple processing, and internal TestFlight availability all passed.
- Installed-build preflight helper: run `python3 scripts/check_installed_testflight_build.py --device E5786BB6-0095-5509-8B85-110C0B5CE6D3` once the iPhone is available to confirm the installed TestFlight app is `atrak.charlie.hoopsclips` `1.0.0 (52)` before the real-basketball smoke.
- Production Release preflight: run `29639140468` passed required production-input checks, production-compatible RevenueCat validation, Release cloud-mode validation, an unsigned Release simulator build, and built `Info.plist` wiring checks. It does not prove a signed production archive/upload, App Store submission, installed-device behavior, or public cloud operational readiness.
- Quality gate: a staging real-video diagnostic produced 11 clips, conservatively matching two known highlights and nine known negatives; auto-keep selected one known highlight and eight negatives. The required human-reviewed 85% report remains open.
- Current gate: the paired iPhone currently appears as `unavailable` through CoreDevice. One earlier installed-app metadata read confirmed HoopClips `1.0.0 (49)` was installed, while later reads lost the CoreDevice app metadata channel and `devicectl list devices` reported `tunnelState=unavailable`. Restore stable device tunneling, install or update to internal TestFlight build `52`, cross the old 15-minute point with the same class of real source, and record every downstream step separately.

### Prior build 45 failure that builds 46 and 47 address

- Device/source: trusted physical iPhone with internal TestFlight `1.0.0 (45)` and a real 379.9 MB basketball video split into forty-eight 8 MB upload parts.
- Result: upload remained at 14%, so team scan, analysis, Review, AI Edit, render, download, Photos, and share/open export were not reached.
- Evidence: two parts completed while one active part remained idle. The app was backgrounded, and the 15-minute signed upload plan expired before the 10-minute request-idle timeout and retry sequence could recover.
- Fix: build `46` changes the background request-idle timeout to 90 seconds, preserving retry/backoff while keeping worst-case idle recovery inside the signed upload window. Build `47` also halves multipart operations for this source size and adds one normal-network upload lane.
- Measurement boundary: fewer parts and scheduling waves are deterministic, but no wall-clock speedup is claimed until build `47` completes the same real-device upload.
- Apple state: signing, provisioning, upload, and processing are resolved and are not blockers for this rerun.

## Historical snapshot (2026-07-05)

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
- Historical blocker at this snapshot: Apple certificate limit/provisioning state for `atrak.charlie.hoopsclips`.
- Handoff: `TESTFLIGHT_BLOCKER.md`
- Real-basketball TestFlight checklist: `docs/phase_beta_launch_gates_after_pr43.md`

At this snapshot, installed build `44` TestFlight smoke was unproven pending Apple certificate repair, upload, and a trusted-iPhone run. Those Apple gates were resolved later; the active snapshot above is authoritative.

## Historical snapshot (2026-06-03)
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

## Current Blockers
- Install internal TestFlight build `52` on the trusted iPhone and complete the real-basketball upload-through-export smoke, including crossing the old 15-minute upload failure point.
- Complete the human-reviewed team/highlight accuracy report and meet the required 85% gate without weakening detection thresholds.
- Run and verify a signed production Release archive/upload before claiming App Store submission proof. Release preflight run `29639140468` proves configuration and unsigned compilation only.
- Finish the App Store Connect listing, review, and compliance audit in an authenticated App Store Connect session.
- Keep public cloud launch gated until production identity/quota, observability, render reliability, and confirmed-label requirements are separately proven.

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
