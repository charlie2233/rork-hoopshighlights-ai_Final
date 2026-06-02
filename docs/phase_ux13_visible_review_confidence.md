# Phase UX13 Visible Review Confidence

## Goal

Make the iOS Review screen clearer on small phones by showing what the user has selected for the edit without implying that review is finished.

## Changes

- Renamed the Review progress strip from `Review Progress` to `Selected clips`.
- Changed the visible summary from `kept` language to short selected/check copy:
  - `8/12 selected`
  - `8/12 selected, 3 to check`
- Added `ReviewProgressCopy` so the compact text and accessibility value are covered by tests.
- Kept the change iOS-only and UI-only. No local analysis, rendering, composition, or export behavior was added.

## Validation

- Passed: focused iOS unit test for Review progress copy.
  - `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-ux13-dd CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testReviewProgressCopyShowsSelectedAndCheckCounts`
  - Result bundle: `/tmp/hoopclips-ux13-dd/Logs/Test/Test-HoopsClips-2026.06.01_20-31-52--0700.xcresult`
- Passed: iOS Debug simulator build.
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux13-dd CODE_SIGNING_ALLOWED=NO build`
- Passed: `git diff --check`.

## Related Audio Recall Verification

The current branch already includes the cloud-side crowd-pop/audio-reaction recall path from `main`. No iOS audio analysis was added. Local verification:

- Passed: backend analysis audio-reaction/crowd-pop tests.
  - `PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_pipeline_quality.py -k "audio_reaction or crowd_pop or audio_cue"`
  - Result: 19 passed, 56 deselected.
- Passed: GPT reranker audio-reaction/crowd-pop tests.
  - `uv run --with-requirements services/editing/requirements.txt --with pytest python -m pytest services/editing/tests/test_gpt_reranker.py -k "audio_reaction or crowd_pop or audio_cue"`
  - Result: 9 passed, 86 deselected.

## Launch Notes

- This should reduce confusion for players, parents, and coaches who see clips preselected before manually checking uncertain team, audio, timing, or outcome candidates.
- Real-device smoke should confirm the summary wraps cleanly on smaller phones and Dynamic Type.
