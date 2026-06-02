# Phase UX6 Visible Simple Accuracy Pass

## Goal

Make HoopClips easier to use across phone sizes while improving highlight recall for loud crowd reaction moments.

## Architecture Guardrails

- Cloud backend owns analysis, highlight recall, GPT/edit planning inputs, rendering, and storage.
- iOS remains the control/status surface for import, team choice, target length, review, preview, download, and share/open-in.
- This pass does not add local iOS analysis, rendering, composition, FFmpeg command generation, or video export behavior.
- No secrets, R2 credentials, or presigned URLs were added to logs or docs.

## Changes

### Crowd-Pop Recall

- Broadened `_is_audio_reaction_candidate` so loud audio reactions can be preserved when the candidate label is basketball-contextual, such as `Possible Layup`, not only generic labels like `Highlight`.
- Kept the existing conservative gates:
  - very loud audio score
  - enough motion, visual activity, or confidence
  - minimum combined score
- Added a regression test proving a loud `Possible Layup` reaction candidate survives review trimming when scoring clips fill the cap.

### Visibility And Compatibility

- Added layout priority to `RorkMetricChip` text so duration, format, detected count, and kept count labels are less likely to be squeezed by icons/spacers.
- Hardened the analysis team section title/subtitle, uncertain-team helper, team-scan retry action, and cloud-analysis path copy with wrapping and minimum scaling.
- These changes are SwiftUI layout-only and should help small phones, large Dynamic Type, and localized strings without changing the workflow.

## Validation

- `git diff --check` passed.
- `PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_pipeline_quality.py -k "audio_reaction or review_trim"` passed: 18 selected tests.
- `PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_pipeline_quality.py` passed: 70 tests.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build` passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build-for-testing` passed.
- Xcode emitted the existing AppIntents metadata warning because no AppIntents framework dependency is present.

## Launch Notes

- This is not a full TestFlight readiness signoff.
- Real-device smoke is still required for import -> cloud analysis -> Review -> Export -> AI Edit -> render -> preview -> revision -> share/open-in.
- The unrelated root `HoopsClips.xcodeproj/` and `HoopsHighlightsAI.xcodeproj/` folders must remain untracked unless explicitly requested.
