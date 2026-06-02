# Phase: UX Accuracy Full-Play Prompt

Branch: `codex/phase-ux-accuracy-compatibility-next`

## Goal

Make the AI Edit prompt simpler for users while making the cloud GPT editor more accurate about complete basketball moments.

## Changes

- Renamed the quick prompt `Clear outcomes` to `Full plays`.
- Updated that quick prompt to request action-to-result clips with visible outcomes while keeping unsure clips reviewable.
- Added backend structured intent parsing for:
  - `clear outcome`
  - `visible outcome`
  - `full play`
  - `show the play`
  - `action-to-result`
  - `late fragments`
  - `dead balls`
  - `complete play`
- Added `clarityFocusRequested` to GPT selection-quality rules.
- Added a GPT instruction for clarity-focused prompts to prefer setup-to-result plays and reject late fragments, reaction-only aftermath, or basket/result-only clips.

## Architecture

- Cloud/backend still owns analysis, GPT selection, EditPlan validation, rendering, and storage.
- iOS only sends a compact user note/intent and shows status/preview/share controls.
- Raw user prompt text is not sent to GPT in the compact reranker payload.
- GPT still receives existing candidates and sampled keyframes only, never full videos.
- GPT still cannot output FFmpeg commands or bypass validators.

## Why This Helps

Players and parents understand `Full plays` faster than `Clear outcomes`. The backend now turns that phrase into structured `clarity` and `full_action_context` intent, so GPT can bias final selection toward clips with setup, action, result, and follow-through instead of late basket fragments or post-play reactions.

## Validation Results

Local checks run on this branch:

```bash
git diff --check
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_user_prompt_full_play_language_maps_to_clarity_focus -v
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v
ios/backend/.venv/bin/python -m pytest services/editing/tests/test_gpt_reranker.py
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-full-play-prompt-dd CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditQuickPromptsIncludeSimpleLongReelIntent test
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-full-play-prompt-dd CODE_SIGNING_ALLOWED=NO build-for-testing
```

Results:

- `git diff --check`: passed.
- Focused backend intent test: passed.
- Full `ios.backend.tests.test_edit_plan_agent`: 111 tests passed.
- `services/editing/tests/test_gpt_reranker.py`: 105 tests passed.
- Focused iOS prompt test on `iPhone 16e` simulator: `TEST SUCCEEDED`.
- Debug `build-for-testing` on `iPhone 16e` simulator: `TEST BUILD SUCCEEDED`.

## Background App Behavior

Existing cloud-analysis and AI Edit copy already tells users they can switch apps after upload/render handoff while HoopClips keeps the real backend job attached:

- `CloudAnalysisProgressCopy.backgroundReminder(...)` shows the import/analysis reminder from real cloud status.
- `HighlightsViewModel.recordCloudAnalysisHandoff(...)` persists: `Cloud analysis started. You can switch apps after upload and reopen HoopClips for real job status.`
- `AIEditBackgroundJobCopy.reminder(...)` shows the AI Edit/render reminder from real render phase.

No fake waiting, fake ETA, or fake backend progress was added.

## Launch Notes

This is not a full launch sign-off. Internal TestFlight still needs the installed iPhone smoke, current deploy preflight, current upload workflow evidence, and human-reviewed launch-grade accuracy report.
