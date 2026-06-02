# Phase UX14 Export Note Readability

## Goal

Make Export / AI Edit easier to understand on small phones and with larger text settings while preserving the cloud-first editing architecture.

## Changes

- Renamed the optional note label from `Side note (optional)` to `Tell HoopClips how to edit`.
- Replaced the note placeholder with a short example string: `Example: more hype, defense, NBA recap, 4:30 reel.`
- Renamed `Quick focus` to `Tap a focus` so the preset note buttons read more like an action.
- Tightened the visible setup copy so users know a blank note is OK.
- Updated the crowd-pop quick prompt to treat very loud crowd pops, bench reactions, and audio spikes as nearby highlight clues that still need visible outcome proof.
- Updated the visible default focus summary from generic `crowd/audio cues` to `loud crowd/audio cues`.
- Added `AIEditPromptCopy` so the most important visible strings are covered by unit tests.
- Added a native cloud-analysis recall lane for super-loud crowd pops with modest visual/action context, so those uncertain moments stay available for Review/GPT instead of being dropped behind higher-scoring made-shot clips.

## Architecture

- iOS still only sends a compact user note/intent to the cloud edit request.
- Cloud still owns clip selection, GPT editing, EditPlan validation, rendering, and storage.
- No local iOS analysis, rendering, composition, FFmpeg command generation, or fake job state was added.
- Loud crowd/audio cues remain recall hints only. GPT and validators still require sampled frame evidence of real basketball action and visible outcome before a rendered EditPlan can keep them as final highlights.

## Validation

- Passed: focused iOS unit tests for prompt copy and cloud edit focus summary.
  - `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-ux14-dd CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditPromptCopyStaysShortVisibleAndPlain -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptCarriesSelectedTeamFocus -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultFocusSummaryShowsAllTeamsTarget -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultFocusSummaryStaysCompactForLongTeamNames`
  - Result bundle: `/tmp/hoopclips-ux14-dd/Logs/Test/Test-HoopsClips-2026.06.01_20-48-30--0700.xcresult`
- Passed: focused native/GPT audio recall tests.
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_review_trim_reserves_super_loud_crowd_pop_with_modest_action_context ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_unlabeled_audio_only_filler_is_not_audio_reaction_candidate ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_review_trim_reserves_unlabeled_loud_crowd_pop_candidate -v`
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_detects_super_loud_audio_pop_with_some_action_context services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_sampling_reserves_super_loud_audio_review_candidate_below_plan_quality services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_audio_reaction_detection_ignores_weak_audio_only_filler -v`
- Passed: broader local backend suites.
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v` passed 76 tests.
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed 95 tests.
- Passed: backend compile sanity.
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py`
- Passed: iOS Debug simulator build.
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux14-dd CODE_SIGNING_ALLOWED=NO build`
- Passed: `git diff --check`.

## Launch Notes

- This is a low-risk readability pass for players, parents, and coaches who do not know what to type.
- Real-device smoke should confirm the title, placeholder, quick-focus buttons, and target summary remain readable on smaller iPhones and Dynamic Type.
