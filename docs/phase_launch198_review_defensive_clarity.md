# Phase Launch198 - Review Defensive and Audio Evidence Clarity

## Goal

Make Review easier for testers to trust before AI Edit by explaining why defensive plays and loud crowd/audio reaction moments should stay available for human review.

## Changes

- Added `Defensive cue` evidence rows for defensive clips.
  - Explains that blocks, steals, pressure, loose balls, and forced turnovers can be highlights without a made shot.
  - Keeps the signal in Review; no iOS-side rendering or production analysis changes.
- Added `Crowd/audio cue` evidence rows for clips with strong audio peaks.
  - Shows the audio peak percentage.
  - Reminds the user to verify that the play outcome is visible.
- Added regression coverage for defensive and audio evidence rows.
- Verified the existing cloud-owned audio reaction pipeline:
  - backend analysis detects loud local crowd-pop/swell boundaries and keeps pre-pop action context;
  - GPT reranker reserves audio-reaction recall candidates, samples before/after frames, and treats audio as a recall hint only unless visuals prove the basketball outcome.

## Architecture

- iOS remains the review/control surface.
- Cloud remains responsible for semantic clip selection, GPT edit planning, rendering, validation, and storage.
- This phase only improves visible review explanations for existing clip signals.

## Validation

Commands run:

```bash
git diff --check
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_pipeline_quality.py -k audio_reaction
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services/editing/tests/test_gpt_reranker.py -k audio_reaction
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewEvidenceRowsShowConfidentTeamAndKeyMoments -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewEvidenceRowsTreatTurnoverPressureAsDefense -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewEvidenceRowsShowCrowdAudioCueForLoudReactions -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkMissingTeamAttributionStatusUncertain
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build-for-testing
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build
```

Results:

- `git diff --check`: passed.
- Backend audio-reaction pipeline tests: 5 passed.
- Editing GPT audio-reaction tests: 3 passed.
- Focused iOS tests: passed on `iPhone 16e` simulator.
  - Result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.01_13-56-51--0700.xcresult`
- iOS Debug `build-for-testing`: passed.
- iOS Debug `build`: passed.

## Launch Note

This helps internal testers understand why HoopClips keeps defensive moments and loud reactions in the review pool. Full launch readiness still needs the real-device TestFlight smoke through import, cloud analysis, Review, AI Edit render, preview, revision, and share/open-in.
