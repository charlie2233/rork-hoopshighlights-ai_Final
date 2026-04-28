# Phase Edit3d Live UI Smoke Evidence

## Goal

Run the existing DEBUG UI smoke harness for the iOS AI Edit Agent and document whether the live path reaches:

```text
Review fixture
-> Make Highlight Reel
-> Personal Highlight
-> 30s target
-> cloud render
-> MP4 preview
-> share sheet
```

The iOS app remains client-only. No local AI analysis, edit planning, video composition, or production rendering was added in this phase.

## Branch

```text
codex/phase-edit3d-live-ui-smoke-evidence
base commit: 753066e Add AI edit UI smoke harness
```

## Simulator

```text
Device: iPhone 17
UDID: A46E2157-77ED-42CE-959D-65C068681A47
Runtime: iOS 26.0.1
```

Clean boot sequence was run:

```bash
xcrun simctl shutdown all
xcrun simctl erase all
xcrun simctl boot A46E2157-77ED-42CE-959D-65C068681A47
xcrun simctl bootstatus A46E2157-77ED-42CE-959D-65C068681A47 -b
```

## Build Validation

Passed:

```bash
git diff --check
```

Passed:

```bash
xcodebuild build \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO
```

Passed:

```bash
xcodebuild build-for-testing \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' \
  -derivedDataPath /tmp/hoopsclips-phase-edit3d-bft-derived \
  OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' \
  CODE_SIGNING_ALLOWED=NO
```

## Fresh Worker Render Proof

The existing Worker/backend smoke produced a playable cloud-rendered MP4 from a fresh staging source object.

Important note: the first shell pipeline returned nonzero because `tee` was pointed at a file inside an output directory before the script created that directory. The script itself printed a passing JSON result and produced the rendered MP4.

```text
status: pass
workerUrl: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
sourceObjectKey: uploads/9939c51d8993440fb6f5c7ea23f80885/source.mp4
editJobId: edit_5aca2a9fb5144e6ea6ae54e9696400e5
renderJobId: render_f33f182f85f8456d81067c70e31cecb3
outputObjectKey: edits/edit_5aca2a9fb5144e6ea6ae54e9696400e5/render_jobs/render_f33f182f85f8456d81067c70e31cecb3/final.mp4
renderLogObjectKey: edits/edit_5aca2a9fb5144e6ea6ae54e9696400e5/render_jobs/render_f33f182f85f8456d81067c70e31cecb3/render_log.json
downloadedPath: /private/tmp/hoopclips-phase-edit3d-worker-smoke/final.mp4
media: 720x1280 H.264/AAC MP4, duration 14.422005s
```

## UI-Shaped Backend Contract Proof

To separate backend behavior from the simulator runner, a UI-shaped backend request was run outside the app with:

- Personal Highlight
- 30 second target
- 9:16 aspect ratio
- free tier
- two UUID-style source clips
- the same staging source object used by the UI smoke

It reached `rendered`.

```text
sourceObjectKey: uploads/9939c51d8993440fb6f5c7ea23f80885/source.mp4
editJobId: edit_6229d152c86a4c49aa77a46890d60b87
renderJobId: render_d5c6f96ae6ce4bc4b552fa546fb671b3
status: rendered
durationSeconds: 14.422
outputObjectKey: edits/edit_6229d152c86a4c49aa77a46890d60b87/render_jobs/render_d5c6f96ae6ce4bc4b552fa546fb671b3/final.mp4
renderLogObjectKey: edits/edit_6229d152c86a4c49aa77a46890d60b87/render_jobs/render_d5c6f96ae6ce4bc4b552fa546fb671b3/render_log.json
failureReason: null
```

No presigned download URL was logged.

## Live UI Smoke Attempt 1

Command:

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' \
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testLiveAIEditClientSmokeFlow \
  -parallel-testing-enabled NO \
  -derivedDataPath /tmp/hoopsclips-phase-edit3d-live-ui-derived \
  -resultBundlePath /tmp/hoopsclips-phase-edit3d-live-ui.xcresult \
  OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' \
  CODE_SIGNING_ALLOWED=NO
```

Result:

```text
Failed: Test crashed with signal kill.
Result bundle: /tmp/hoopsclips-phase-edit3d-live-ui.xcresult
```

Evidence captured before the runner died:

```text
/tmp/phase_edit3d_live_ui_attachments/0C3907EF-8EA8-416D-A777-1D640E71E487.png
  suggested name: 01 Review Make Highlight Reel

/tmp/phase_edit3d_live_ui_attachments/66310A73-6EDB-4AEE-BFE4-05C949B480C1.png
  suggested name: 02 AI Edit Style Picker
```

Observed progress:

```text
Review fixture appeared: yes
Make Highlight Reel button visible and tapped: yes
Personal Highlight selected: yes
30s duration selected: yes
render requested: yes
render status reached rendered: no
preview appeared: no
share sheet appeared: no
```

## Live UI Smoke Attempt 2

The test was retried with Xcode test timeouts disabled:

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' \
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testLiveAIEditClientSmokeFlow \
  -parallel-testing-enabled NO \
  -derivedDataPath /tmp/hoopsclips-phase-edit3d-live-ui-derived \
  -resultBundlePath /tmp/hoopsclips-phase-edit3d-live-ui-retry.xcresult \
  -test-timeouts-enabled NO \
  OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' \
  CODE_SIGNING_ALLOWED=NO
```

Result:

```text
Failed: Test crashed with signal term.
Runner log included: [XPCErrors] [C:1] Error received: Connection interrupted.
Result bundle: /tmp/hoopsclips-phase-edit3d-live-ui-retry.xcresult
```

Evidence captured before the runner died:

```text
/tmp/phase_edit3d_live_ui_retry_attachments/C0915682-84FC-48EC-8359-5303ECF37D92.png
  suggested name: 01 Review Make Highlight Reel

/tmp/phase_edit3d_live_ui_retry_attachments/3498A91F-A579-4ACF-B31E-4F7D4003F4F2.png
  suggested name: 02 AI Edit Style Picker

/tmp/phase_edit3d_live_ui_retry_attachments/B1D8743A-AB4C-421F-B311-3FF96D2BDD83.png
  suggested name: 03 AI Edit Render Status
```

Additional simulator screenshots:

```text
/tmp/phase_edit3d_after_retry.png
/tmp/phase_edit3d_30s_after_retry.png
```

Observed progress:

```text
Review fixture appeared: yes
Make Highlight Reel button visible and tapped: yes
Personal Highlight selected: yes
30s duration selected: yes
render requested: yes
visible status before runner failure: Queued
render status reached rendered: no
preview appeared: no
share sheet appeared: no
```

## Current Interpretation

The backend and the UI-shaped payload are capable of rendering through the active Worker path. The remaining live UI proof is blocked by the simulator/XCTest connection dying before the app reaches preview/share.

This phase did not prove preview/share through the live UI. It did prove:

- app launch in smoke mode
- Review fixture seeding
- AI Edit sheet presentation
- Personal Highlight and 30s selection
- render request initiation
- render status UI entering `Queued`
- backend render correctness with the same source object and UI-shaped request

## Remaining Blocker

The full live UI path is still blocked at:

```text
XCTest runner / simulator connection dies while the AI Edit UI is polling render status.
```

Observed failure signatures:

```text
Test crashed with signal kill
Test crashed with signal term
[XPCErrors] [C:1] Error received: Connection interrupted.
```

The next debugging step should be narrow: add DEBUG-only diagnostics that expose the current `editJobId`, `renderJobId`, last poll status, and last poll error to the UI smoke evidence without logging presigned URLs. That will distinguish:

- app poll loop not issuing status requests
- status requests hanging
- status responses staying queued
- app task cancellation when the XCTest runner dies
- real backend delay

Do not start revision commands until this live UI proof reaches preview/share or this blocker is explicitly accepted.
