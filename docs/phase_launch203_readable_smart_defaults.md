# Phase Launch203: Readable Smart Defaults + Audio Reaction Recall

## Goal

Make HoopClips easier to trust during internal TestFlight by tightening the default AI Edit instructions and improving highlight recall for loud crowd/audio reactions.

## Changes

- iOS Export default prompt now respects selected-team confidence mode:
  - `includeUncertain = true`: unsure team clips stay reviewable.
  - `includeUncertain = false`: only confident team matches are eligible.
- Default AI Edit guidance is shorter so user side notes still have room while retaining the important guardrails:
  - selected team focus
  - made shots, blocks, steals, forced turnovers, defensive stops
  - crowd/audio pops as recall hints
  - visible-outcome verification
  - duplicate/filler rejection
- Cloud native analysis now treats sustained crowd swells after a loud peak as part of the audio reaction score.
- Cloud review trimming now reserves more audio-reaction candidates when the candidate pool is large.
- GPT reranker sampling now reserves more audio-reaction candidates for large candidate pools so loud crowd moments reach the vision model for verification.

## Architecture

- iOS remains a control surface only. It sends compact prompt/config context and does not analyze, render, compose, or export production edits locally.
- Cloud analysis still creates candidate windows.
- Audio reaction candidates are recall hints only. They are not proof of a highlight.
- GPT may use the sampled frames to judge whether the audio reaction corresponds to visible basketball action and a real outcome.
- Backend validators still enforce render safety, clip IDs, timestamps, and outcome-quality rules.

## Sound Recognition Behavior

- Sudden loud crowd pops can create `Crowd Reaction` recall windows.
- Sustained crowd swells after the peak now add salience, which helps catch moments where the reaction builds instead of appearing as one frame of audio.
- Review/GPT reserves are bounded:
  - analysis review reserve scales from 2 to 10 audio-reaction candidates depending on candidate pool size.
  - GPT sampling reserve scales from 2 to 10 audio-reaction candidates depending on GPT candidate budget.
- Weak audio-only filler is still filtered unless there is enough activity/context for review.

## Validation

- Focused iOS prompt-builder tests:
  - `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' -derivedDataPath /tmp/hoopclips-launch203-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation ...`
  - Result: passed for focused CloudEdit prompt/default-focus tests.
- Backend focused audio tests:
  - `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_pipeline_quality.py' -k audio_reaction`
  - Result: 7 tests passed.
  - `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_gpt_reranker.py' -k audio_reaction`
  - Result: 6 tests passed.
- Backend broader tests:
  - `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_pipeline_quality.py'`
  - Result: 65 tests passed.
  - `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_gpt_reranker.py'`
  - Result: 87 tests passed.
- iOS build-for-testing:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch203-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`
- iOS Debug build:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch203-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build`
  - Result: `** BUILD SUCCEEDED **`

## Notes

- Earlier broad iOS unit-test execution was interrupted during Xcode finalization after surfacing a pre-existing candidate-ranking failure outside this patch scope. The focused prompt-builder tests passed after the copy fixes.
- Root-level untracked Xcode project folders were left unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`
