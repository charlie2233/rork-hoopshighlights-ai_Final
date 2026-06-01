# Phase Launch204: Export Readability and Audio Recall

## Goal

Keep Export simple for users while making the remaining option controls safer on small phones and large Dynamic Type.
Improve highlight recall for loud crowd/audio pops while keeping audio as a review hint, not proof of a made shot or defensive outcome.

## Change

- Replaced fixed horizontal `HStack` layouts in local Export quality and file-format controls with adaptive grids.
- Allowed option descriptions to wrap to more lines at accessibility text sizes.
- Added stable minimum heights so cards do not collapse or squeeze labels when text wraps.
- Recognized iOS/backend labels such as `Audio Pop Cue` and `Audio Pop Cue - Action` as GPT audio-reaction recall hints.
- Added a relaxed `super_loud_audio_pop` source for very loud audio peaks with some action context, so crowd pops are less likely to be missed.
- Increased GPT sampling reserve for audio-reaction candidates so strong crowd-pop moments reach sampled-keyframe review more often.
- Kept the existing safety rule: audio can nominate a clip for review, but GPT and backend validators still require sampled visual evidence before keeping or claiming an outcome.

## Architecture

- iOS still only displays export options/status/preview/share controls.
- No local video analysis, edit planning, cloud rendering, Remotion, Canva, or FFmpeg behavior was added.
- Audio-reaction recall stays in the cloud/GPT edit path and only uses existing candidate clip metadata plus sampled frames.
- GPT still cannot invent clip IDs, exact timestamps, outcomes, or FFmpeg commands.

## Validation

- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch204-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch204-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build`
  - Result: `** BUILD SUCCEEDED **`
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker`
  - Result: `Ran 90 tests ... OK`
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_create_edit_job_gpt_disabled_drops_weak_generic_fallback_candidate`
  - Result: `Ran 1 test ... OK`
- `git diff --check`
  - Result: passed

## Notes

- Root-level untracked Xcode project folders remain unrelated and must stay unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`
- No remote GitHub Actions run was triggered for this slice; commit should use `[skip ci]` to preserve Actions budget.
