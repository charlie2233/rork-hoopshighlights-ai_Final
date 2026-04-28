# Phase Edit3c UI Smoke Harness

## Purpose

Phase Edit3c makes the iOS AI Edit Agent flow testable without desktop mouse-click automation.

The smoke harness proves this client path:

```text
Review fixture
-> Make Highlight Reel
-> Personal Highlight
-> 30s target
-> cloud render request
-> rendered status
-> MP4 preview
-> downloaded local MP4 share sheet
```

The iOS app remains a client only. Video analysis, edit planning, and rendering stay cloud-backend owned.

## Stable Accessibility Identifiers

The AI edit smoke uses stable identifiers instead of visible copy:

```text
review.makeHighlightReelButton
edit.style.personalHighlightButton
edit.style.fullGameHighlightButton
edit.duration.30sButton
edit.render.startButton
edit.status.label
edit.preview.player
edit.share.button
edit.failure.reasonLabel
```

## DEBUG Smoke Fixtures

The app supports a DEBUG-only smoke mode through launch args and environment variables:

```text
--hoops-ai-edit-live-smoke
HOOPS_UI_SMOKE_MODE=1
HOOPS_AI_EDIT_TEST_FIXTURE=staging_render_ready
HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
HOOPS_CLOUD_EDIT_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
HOOPS_SMOKE_SOURCE_OBJECT_KEY=<optional staging R2 source object key override>
HOOPS_SMOKE_INSTALL_ID=<unique smoke install id>
```

`staging_render_ready` seeds a Review-like state with two kept cloud clips and a staging source object key.

`failing_render` seeds the same Review-like state, then the AI Edit view simulates a failed render before any backend call. This validates failure copy and `edit.failure.reasonLabel` without requiring a live backend failure.

For reliable live smoke, supply a fresh small staging source object key. If no source object key is supplied, the fixture falls back to the known staging smoke source:

```text
uploads/25a101ba8d234fd98094bd112276161f/source.mp4
```

## Clean Simulator Runbook

Pick a simulator dynamically, then reset and boot it:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final

SIM_UDID="$(xcrun simctl list devices available | awk -F '[()]' '/iPhone 17 / {print $2; exit}')"
test -n "$SIM_UDID"

xcrun simctl shutdown all || true
xcrun simctl erase "$SIM_UDID"
xcrun simctl boot "$SIM_UDID"
xcrun simctl bootstatus "$SIM_UDID" -b
```

## Live UI Smoke

Refresh the source fixture before a live UI smoke, or separately prove the backend render path, with:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend \
  ios/backend/.venv/bin/python services/editing/scripts/ios_ai_edit_client_smoke.py \
  --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --output-dir /tmp/hoopclips-phase-edit3c-worker-smoke \
  --timeout-seconds 300
```

Write a small config file with the source object key from that output:

```bash
export HOOPS_SMOKE_SOURCE_OBJECT_KEY="<sourceObjectKey from Worker smoke>"
export HOOPS_SMOKE_INSTALL_ID="phase-edit3c-live-ui-smoke-$(date +%Y%m%d%H%M%S)"

python3 - <<'PY'
import json
import os

with open("/tmp/hoopsclips-ai-edit-ui-smoke.json", "w", encoding="utf-8") as handle:
    json.dump(
        {
            "workerURL": "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev",
            "sourceObjectKey": os.environ["HOOPS_SMOKE_SOURCE_OBJECT_KEY"],
            "installID": os.environ["HOOPS_SMOKE_INSTALL_ID"],
        },
        handle,
    )
PY
```

Run the focused live UI smoke:

```bash
DERIVED_DATA="/tmp/hoopsclips-phase-edit3c-live-ui-derived"
RESULT_BUNDLE="/tmp/hoopsclips-phase-edit3c-live-ui-$(date +%Y%m%d-%H%M%S).xcresult"
rm -rf "$DERIVED_DATA" "$RESULT_BUNDLE"

xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination "platform=iOS Simulator,id=$SIM_UDID" \
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testLiveAIEditClientSmokeFlow \
  -parallel-testing-enabled NO \
  -derivedDataPath "$DERIVED_DATA" \
  -resultBundlePath "$RESULT_BUNDLE" \
  OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' \
  CODE_SIGNING_ALLOWED=NO
```

The test is skipped by default unless the `HOOPS_ENABLE_UI_SMOKE` Swift compilation flag is provided.

## Failure Fixture Smoke

Run the failure UI smoke locally without requiring a backend failure:

```bash
DERIVED_DATA="/tmp/hoopsclips-phase-edit3c-failure-ui-derived"
RESULT_BUNDLE="/tmp/hoopsclips-phase-edit3c-failure-ui-$(date +%Y%m%d-%H%M%S).xcresult"
rm -rf "$DERIVED_DATA" "$RESULT_BUNDLE"

xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination "platform=iOS Simulator,id=$SIM_UDID" \
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testAIEditFailureFixtureShowsFailureReason \
  -parallel-testing-enabled NO \
  -derivedDataPath "$DERIVED_DATA" \
  -resultBundlePath "$RESULT_BUNDLE" \
  OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' \
  CODE_SIGNING_ALLOWED=NO
```

The test is skipped by default unless the `HOOPS_ENABLE_UI_SMOKE` Swift compilation flag is provided.

## Evidence To Capture

Expected attachments in the `.xcresult` bundle:

```text
01 Review Make Highlight Reel
02 AI Edit Style Picker
03 AI Edit Rendered Preview
04 AI Edit Share Sheet
AI Edit Failure Fixture
```

If `test-without-building` or `xcodebuild test` fails with a simulator IPC error such as `NSMachErrorDomain Code=-308`, document that separately as a simulator runner failure when:

```text
iOS Debug build passes
iOS build-for-testing passes
Worker smoke passes
manual or rerun UI smoke evidence exists
```

Do not treat a simulator IPC failure as proof that the cloud edit product path failed.
