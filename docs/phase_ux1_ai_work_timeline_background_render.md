# Phase UX1 AI Work Timeline Background Render

Date: 2026-05-15

Branch:

```text
codex/phase-ux1-ai-work-timeline-background-render
```

Base commit:

```text
b48638b
```

Goal:

```text
Make the Export-page AI Edit Agent feel like visible cloud AI editing work by adding an AI Work Timeline, background render messaging, and completed AI Work Receipt.
```

This phase does not add templates, payments, local video rendering, local video composition, local analysis, Remotion runtime, Canva runtime, manual timeline editing, fake thinking, or intentional delays. The iOS app remains the control surface. Cloud analysis, edit planning, revision planning, template policy, durable render state, and FFmpeg rendering remain backend-owned.

## Product UX

Export now explains AI Edit as cloud editing work:

```text
HoopClips edits in the cloud: it finds your best plays, builds the edit plan, renders the MP4, and stores the result temporarily for preview and sharing.
```

Background render copy:

```text
You can leave the app - HoopClips will keep editing in the cloud. Come back anytime to preview your finished reel.
```

Engineering-style status labels were softened into product-facing states:

```text
HoopClips is starting your edit
Building your AI edit
Applying your style
Preparing cloud edit
Waiting for cloud editing
Rendering your highlight reel
Your reel is ready
```

## Backend Model

Added response models:

```text
AIWorkStep
AIWorkTimeline
AIWorkReceipt
```

Render status responses can now include:

```text
workTimeline
workReceipt
```

Timeline steps:

```text
video_uploaded
finding_highlights
selecting_best_clips
removing_duplicates
applying_template
adding_slow_motion
adding_watermark_outro
rendering_mp4
finalizing_download
```

The timeline is generated from real available state:

```text
candidate clip count
selected clip count
duplicate-group metadata when present
template display name
slow-motion effects in the edit plan
watermark/outro settings
render job status
download/final-output readiness
```

The completed receipt includes:

```text
selected clips from candidates
template name and ID
slow-motion moment count
output duration
output resolution policy
watermark/outro status
storage expiration
plan tier and priority queue flag
```

User-facing timeline text intentionally avoids full object keys, presigned URLs, secrets, and raw renderer implementation details.

## Renderer Logs

Successful render logs now include:

```text
workTimeline
workReceipt
```

Failed render logs include:

```text
workTimeline
failureReason
```

This keeps support/debug evidence aligned with the status payload without exposing full presigned URLs.

## iOS Integration

Added Swift response models:

```text
CloudEditWorkStepStatus
CloudEditWorkStep
CloudEditWorkTimeline
CloudEditWorkReceipt
```

Export AI Edit now shows:

```text
AI Work Timeline
AI Work Receipt after render completion
background cloud render message
priority label for non-free tiers
```

Accessibility identifiers:

```text
export.aiEdit.timeline
export.aiEdit.timeline.<stepId>
export.aiEdit.receipt
export.aiEdit.backgroundRender.message
```

If the backend omits timeline data, iOS builds a local display-only timeline from already-known app state. It does not analyze video, plan edits, compose video, or render locally.

## Tests And Validation

Backend:

```text
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service
```

Result:

```text
OK - 24 tests
```

iOS Debug simulator build:

```text
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux1-dd build CODE_SIGNING_ALLOWED=NO
```

Result:

```text
BUILD SUCCEEDED
```

iOS Debug build-for-testing:

```text
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux1-dd-bft build-for-testing CODE_SIGNING_ALLOWED=NO
```

Result:

```text
TEST BUILD SUCCEEDED
```

Additional validation should include the focused Export-page UI smoke when a stable simulator or TestFlight install is available.

## Remaining Notes

No live cloud render smoke was required for this UX-only phase unless backend contract issues appear. The next live check should verify that staging render status payloads include `workTimeline` and rendered jobs include `workReceipt` once the deployed backend includes this branch.
