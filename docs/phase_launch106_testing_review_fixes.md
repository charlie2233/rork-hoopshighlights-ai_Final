# Phase Launch106 Testing Review Fixes

## Goal

Resolve tester-reported launch blockers before internal launch. HoopClips stays cloud-first: iOS controls upload, review, AI edit requests, status, preview, save, and share; cloud services own analysis, GPT edit planning, rendering, and storage.

## Tester Blocking Feedback

- Export shows `Cloud editing version check failed: request timed out`.
- Export has too many choices for normal users.
- AI Edit should expose a simple side note box for user direction.
- Share should be a simple share button, not a list of every possible app.
- History formatting feels crowded.
- Some labels are hidden or cramped on phones.
- Too many small explanatory labels make the app feel noisy.
- Highlight accuracy needs more GPT help; cost is not the constraint for the current testing phase.
- Keep using real cloud job/render status only. Do not add fake thinking, fake ETA, or artificial waits.

## Current Evidence

- Branch: `codex/phase-launch70-editing-analysis-progress`
- Latest pushed commit before this pass: `eed1289 Fix HoopClips bundle display name [skip ci]`
- Existing uncommitted launch prep before this pass: iOS build number 7, TestFlight config checks, History title rename affordance.
- Editing staging config already uses quality-beta GPT knobs in `services/editing/cloudbuild.yaml`:
  - `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED=true`
  - `HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED=true`
  - `HOOPS_AI_CLIP_GPT_REVISION_ENABLED=true`
  - `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP=8`
  - `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE=60`
  - `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO=60`
  - `HOOPS_AI_CLIP_GPT_TIMEOUT_SECONDS=60`
  - `HOOPS_AI_CLIP_GPT_MAX_OUTPUT_TOKENS=12000`
  - `HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED=true`

## Work Log

### Pass 1 - Triage

- Confirmed `AIEditView` blocks the primary render action when `/v1/editing/version` times out.
- Confirmed Export still shows legacy local-render controls even when this build requires the cloud video pipeline.
- Confirmed the Export share area lists editor and social app shortcuts; tester wants one simple share action.
- Confirmed AI Edit already sends a bounded user prompt, but the UI label reads like a technical edit direction instead of a simple side note.
- Confirmed History title rename exists through tapping the title, but rows are still dense.

### Pass 2 - iOS UX Fixes In Progress

- Added a short post-sign-in transition in `ContentView` only after the sign-in screen was shown. It displays `You're in` / `Opening HoopClips`, then routes to the Player tab. Persisted sessions still open immediately.
- Changed cloud edit version timeout behavior so a slow `/v1/editing/version` check becomes a warning instead of blocking the real render request. Explicit config/backend flag failures still block.
- Simplified AI Edit copy, renamed `Edit Direction` to `Side Note`, and kept the prompt bounded/sanitized before it reaches the backend.
- In cloud-required builds, Export now hides legacy local-render controls and keeps AI Edit as the primary render path.
- Replaced the exported-app shortcut grids with one simple `Share` button plus `Save`.
- Started History layout cleanup by moving row actions below the project row so project titles and rename affordance have more room on small phones.

### Pass 3 - Validation

Local validation was kept off GitHub Actions to save minutes:

```bash
git diff --check
python3 -m unittest scripts.test_submission_readiness_preflight -v
bash ios/scripts/verify_internal_staging_config.sh
xcodebuild build-for-testing \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-launch106-bft \
  CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation
```

- `git diff --check`: passed.
- Submission readiness unit tests: 36 passed.
- Internal staging config verification: passed for app env, cloud launch mode, analysis URL, edit URL, bundle ID, marketing version, build number 7, and Info.plist path.
- iOS Debug build-for-testing: passed.
- Existing warnings remain in `CloudAnalysisService.swift` progress callbacks and `VideoExportService.swift` AVFoundation export APIs; this pass did not introduce new build failures.

### Pass 4 - Random Quit Triage

- Checked local `~/Library/Logs/DiagnosticReports/HoopsClips-*.ips` reports. They were simulator test-harness SIGTRAP reports from older `CloudEditServiceTests`, not foreground user-session crashes.
- Checked connected-device visibility with `xcrun devicectl list devices`; `charlie的iPhone` was registered but unavailable, so real iPhone crash/Jetsam logs could not be pulled in this pass.
- Confirmed the current Photos import code is file-backed only and supports `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`; the old `Data.self` fallback is not present in this branch.
- Added privacy-safe stability breadcrumbs for app lifecycle, memory warnings, import persistence, team scan, analysis, and tab changes. These log only safe phases/counts/durations/file sizes, not video URLs, R2 object keys, credentials, or presigned URLs.
- Added an import background task around file/Photos import and reused the analysis background task for the pre-analysis team scan upload so iOS is less likely to suspend/kill those operations mid-transfer.
- On the next launch after a foreground abnormal exit, `LaunchTelemetry` records the previous lifecycle state, screen, checkpoint, and memory-warning count to unified logging.

Validation:

```bash
git diff --check
python3 -m unittest scripts.test_submission_readiness_preflight -v
bash ios/scripts/verify_internal_staging_config.sh
xcodebuild build-for-testing \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-stability-bft \
  CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation
```

- `git diff --check`: passed.
- Submission readiness unit tests: 36 passed.
- Internal staging config verification: passed.
- First build attempt caught an optional-string `Logger` interpolation error in `LaunchTelemetry`; fixed it.
- Rerun iOS Debug build-for-testing: passed.
- Device crash pull remains blocked until the iPhone is visible to `devicectl`.

### Pass 5 - Auth Boundary Player Reset

- Tester found that signing out and signing into another account left the previous video loaded in the Player tab.
- Root cause: `ContentView` keeps the same `HighlightsViewModel` in `@State` while auth screens swap in/out, so the visible auth flow changed but the active project state remained alive.
- Added an auth-boundary reset in `ContentView`: when the user signs out or the authenticated user scope changes from one signed-in account to another, HoopClips persists the current project, clears the active Player/Review/Export state, returns to Player, and closes the paywall.
- Added a safe `auth.project_reset` stability checkpoint with only the reset reason.

Validation:

- `git diff --check`
- `python3 -m unittest scripts.test_submission_readiness_preflight -v`
- iOS Debug build-for-testing with code signing disabled:
  `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-auth-boundary-bft CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation`

Results:

- `git diff --check`: passed.
- Submission readiness unit tests: 36 passed.
- iOS Debug build-for-testing: passed.

### Pass 6 - Completion Truth Audit

Current branch audit:

- Branch: `codex/phase-launch70-editing-analysis-progress`
- Latest pushed commit: `043bb3c Reset active project on auth switch [skip ci]`
- Working tree: clean and in sync with origin before this doc update.
- Product icon/logo: current branch contains `71f3a61 Refresh HoopClips product app icon`; the installed asset is a 1024x1024 PNG at `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`.
- Free editing availability: Free daily AI edit chances remain capped at `3` across iOS policy, backend policy, and static launch preflight coverage.
- GPT-led editing quality knobs: staging defaults keep GPT editor, GPT plan edit, and GPT revision enabled with 60 candidate clips for Free and Pro/internal review and 8 Pro/internal keyframes per clip.
- Photos import hang fix: current `VideoPlayerView` is file-backed for `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`; the old `Data.self` fallback is absent.
- Team selection: the cloud-first pre-analysis team quick scan and selected-team/all-teams flow are implemented and tested, including blocks and steals ownership behavior.

Fresh readiness command:

```bash
python3 scripts/submission_readiness_preflight.py --skip-live
```

Result:

- `pass=24 warn=2 fail=7`

Hard failures still blocking submission:

- Launch-grade selected-team/highlight accuracy evidence is missing; the 85% quality target still needs a labeled footage report from `scripts/evaluate_team_highlight_accuracy.py`.
- The archived upload artifact metadata does not match the expected upload metadata.
- The wired iPhone is detected but unavailable to `devicectl`, so install/post-install smoke cannot run yet.
- The latest main-branch Cloud Edit Deploy Preflight workflow run is not for current commit `043bb3c`.
- The latest main-branch iOS Internal TestFlight Upload workflow run is not for current commit `043bb3c`.
- The latest manually dispatched secret-gated deploy preflight is not for current commit `043bb3c`.
- Installed TestFlight post-install smoke remains unproven.

Warnings:

- Live Worker `/v1/editing/version` probe was skipped by `--skip-live`.
- Live editing service `/version` probe was skipped by `--skip-live`.

Submission decision:

- Do not submit this build to Apple yet.
- Next required proof is real-device availability plus a full internal smoke: install -> import/upload -> cloud team scan -> selected team or all teams -> cloud analysis -> Review -> AI Edit -> render -> preview -> More Hype revision -> revised preview -> Share/Open In.
- Keep GitHub Actions usage limited until the device smoke and live staging probes are ready; then rerun only the necessary current-commit deploy/upload workflows.

## Fix Plan

- Make cloud editing version timeout a non-blocking warning; the real create-job/render request remains the source of truth. Explicit configuration and backend flag blocks still block.
- In cloud-required builds, hide legacy Export theme/music/quality/format/post-processing controls and route users to AI Edit.
- Rename and simplify the AI Edit side note field.
- Simplify share UI to one Share button plus Save.
- Reduce small low-contrast explanatory copy and improve line wrapping.
- Polish History row density and detail copy.

## Validation To Run

- `git diff --check`
- iOS Debug build-for-testing with code signing disabled.
- Existing submission preflight unit tests touched by build 7 changes.
- Backend tests only if backend code changes.
