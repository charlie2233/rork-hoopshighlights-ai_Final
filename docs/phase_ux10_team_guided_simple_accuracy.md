# Phase UX10 Team Guided Simple Accuracy

## Goal

Make the pre-analysis flow clearer on small phones and reduce wrong-team analysis mistakes.

## Changes

- The analysis button now changes to the real next action:
  - `Scanning Teams` while the cloud jersey scan is running.
  - `Choose Team First` when the scan found teams and the user must choose a team or All teams.
  - `Go Pro` when the video exceeds the free duration gate.
- Team target cards now show visible strategy copy, not only an accessibility hint:
  - All teams keeps highlights from both teams.
  - Selected teams keep uncertain clips reviewable instead of silently dropping them.
- Team cards have taller responsive sizing so longer labels and Dynamic Type have room to wrap.
- Cloud analysis now treats recognized audio reaction cue metadata as a review-worthy recall signal even when raw normalized volume is below the previous loud-pop threshold.
- Audio-reaction review trimming now uses a salience score that includes cue confidence and pattern type, so richer crowd-pop clusters/swells are harder to lose when the review pool is full.

## Architecture Guardrails

- iOS remains a control surface for choosing target team, starting analysis, reviewing clips, previewing, and sharing.
- Team scan, team attribution, GPT clip selection, edit planning, rendering, and storage remain cloud/backend owned.
- No local rendering, local production analysis, or full-video GPT calls were added.
- Audio pops remain recall hints only: GPT and validators still require sampled visual evidence before keeping or claiming an outcome.

## Validation

- Passed: `git diff --check`.
- Passed: iOS Debug simulator build:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux10-dd CODE_SIGNING_ALLOWED=NO build`
- Passed: iOS Debug build-for-testing:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux10-dd CODE_SIGNING_ALLOWED=NO build-for-testing`
- Passed: focused audio backend tests:
  - `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -k audio`
- Passed: full backend pipeline quality tests:
  - `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality`
- Passed: GPT reranker audio-reaction tests:
  - `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -k audio`
- Inconclusive: focused iOS team-choice UI smoke with `HOOPS_ENABLE_UI_SMOKE`.
  - Command: `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-ux10-dd CODE_SIGNING_ALLOWED=NO OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' -only-testing:HoopsClipsUITests/HoopsClipsUITests/testPreanalysisTeamChoiceSmoke`
  - The app launched with `--hoops-team-choice-ui-smoke`, but the XCTest runner stayed silent for several minutes and the run was interrupted. This was not counted as a pass or app failure.

## Launch Notes

- This is a small usability and accuracy guardrail: it should reduce accidental wrong-team runs by making the required pre-analysis choice obvious.
- Sound recognition is now stronger for crowd-pop recall, especially repeated clusters/swells around a play.
- It does not replace the real TestFlight smoke or labeled clip accuracy evaluation.
