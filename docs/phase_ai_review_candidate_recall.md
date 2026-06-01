# Phase: AI Review Candidate Recall

Date: 2026-06-01
Branch: `codex/phase-ai-review-candidate-recall`

## Goal

Improve highlight clipping accuracy by sending a deeper set of plausible clips to cloud GPT/review, especially selected-team uncertain clips, blocks, steals, forced turnovers, and defensive stops. This phase does not move rendering or analysis into iOS.

## Changes

- Backend review trimming now reserves up to half of the review list for uncertain selected-team clips when the user chooses a specific team and allows uncertain clips.
- Backend review trimming now reserves up to one-third of larger review lists for defensive families, so blocks/steals/forced turnovers/defensive stops are less likely to be crowded out by made-shot candidates.
- iOS cloud edit request building now reserves up to half of the 320-candidate request for review-only clips, with a 32-clip floor for larger uploads.
- iOS selected-team review thresholds are lower so weak-but-plausible clips go to GPT/user review as `unreviewed` instead of being dropped early.

## Safety

- Confident opponent clips remain filtered when the user selects one team.
- Extra uncertain clips are not auto-kept; they are sent as `userReviewDecision: "unreviewed"`.
- GPT/review receives compact clip metadata from existing candidate clips. No full videos are sent to GPT by this change.
- GPT still cannot generate FFmpeg commands or bypass EditPlan validation.
- No local iOS rendering, composition, or production analysis was added.

## Validation

- Passed: `git diff --check`
- Passed: `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v` (52 tests)
- Passed: `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v` (42 tests)
- Passed: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ai-review-recall-dd build-for-testing`
- Passed: targeted local `xcodebuild ... test-without-building` for the new cloud edit candidate-recall tests on iPhone 17 simulator
- Not run: GitHub Actions, to preserve the current budget.

## Launch Notes

This improves recall for internal TestFlight testing, but launch readiness still depends on real-device smoke through import, cloud analysis, review, export, AI edit render, preview, revision, and share/open-in.
