# Phase Launch191 - Review Confidence Clarity

## Goal

Improve highlight review trust and clipping accuracy by keeping defensive candidate labels precise across iOS Review, cloud analysis, team quick scan, EditPlan planning, and GPT reranking. Also make backend loud crowd/audio pops stronger recall hints for GPT review without treating crowd noise as proof of a made play.

## Change

- Stopped treating generic `contest` / `contested` labels as blocks.
- Kept contests as defensive review candidates, now classified as defensive stops instead of blocked shots.
- Centralized iOS Review defensive-family checks through `HighlightsViewModel` so badges, filters, quick actions, and cloud edit request logic agree.
- Updated team quick scan sampling so contested plays use defensive/possession review frames instead of block-specific ball-deflection frames.
- Updated backend EditPlan/GPT reranker defensive family classification so GPT sees the right candidate family and does not over-index contested jumpers as blocks.
- Reserved a small cloud Review lane for `Crowd Reaction` / audio-pop candidates when normal scoring clips fill the cap.
- Reserved the same audio-reaction lane in GPT sampling so loud crowd pops reach the vision model as recall hints.
- Added `audioReactionReviewSegments` diagnostics for backend evidence. GPT instructions still require sampled frames to prove the basketball event before keeping/captioning the clip.

## Architecture

- Cloud still owns analysis, team scan, GPT selection, edit planning, validation, rendering, and storage.
- iOS only displays Review metadata and forwards cloud-owned clip metadata/user choices.
- No local iOS video analysis, rendering, composition, or export logic was added.
- Audio recognition is backend FFmpeg/audio-profile based and used as a recall signal only. It does not replace CV/GPT visual verification, timestamp logic, or deterministic render validation.

## Validation

Run locally:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testContestReviewClipIsDefensiveStopNotBlock
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build
cd ios/backend
uv run --isolated --with-requirements requirements.txt --with pytest python -m pytest tests/test_pipeline_quality.py::PipelineQualityTests::test_defensive_label_family_treats_contest_as_stop_not_block tests/test_team_quick_scan.py::TeamQuickScanTests::test_contested_jumper_uses_defensive_stop_roles_not_block_roles tests/test_edit_plan_agent.py::EditPlanAgentTests::test_agent_context_treats_contest_as_defensive_stop_not_block -q
uv run --isolated --with-requirements requirements.txt --with pytest python -m pytest tests/test_pipeline_quality.py::PipelineQualityTests::test_review_trim_reserves_audio_reaction_recall_candidate_when_scoring_fills_cap tests/test_pipeline_quality.py::PipelineQualityTests::test_analysis_team_diagnostics_count_audio_reaction_review_clips tests/test_pipeline_quality.py::PipelineQualityTests::test_candidate_windows_include_crowd_pop_recall_anchor_for_gpt_review -q
uv run --isolated --with-requirements requirements.txt --with pytest python -m pytest tests/test_pipeline_quality.py tests/test_team_quick_scan.py tests/test_edit_plan_agent.py -q
cd ../../services/editing
uv run --isolated --with-requirements requirements.txt --with pytest python -m pytest tests/test_gpt_reranker.py::GPTHighlightRerankerTests::test_sampling_reserves_turnover_pressure_labels_for_gpt_review -q
uv run --isolated --with-requirements requirements.txt --with pytest python -m pytest tests/test_gpt_reranker.py::GPTHighlightRerankerTests::test_gpt_sampling_reserves_audio_reaction_recall_candidate_when_scoring_fills_cap tests/test_gpt_reranker.py::GPTHighlightRerankerTests::test_audio_reaction_sampling_adds_before_and_after_pop_context tests/test_gpt_reranker.py::GPTHighlightRerankerTests::test_payload_marks_crowd_reaction_candidates_as_audio_recall_hints -q
uv run --isolated --with-requirements requirements.txt --with pytest python -m pytest tests/test_gpt_reranker.py -q
```

Results:

- `git diff --check`: passed.
- iOS focused Review test: passed, `** TEST SUCCEEDED **`.
- iOS Debug simulator build: passed, `** BUILD SUCCEEDED **`.
- iOS Debug `build-for-testing`: passed, `** TEST BUILD SUCCEEDED **`.
- Backend focused contest/team/EditPlan tests: `3 passed`.
- Backend focused audio-pop tests: `3 passed`.
- Backend broad pipeline/team/EditPlan tests: `212 passed, 33 subtests passed`.
- Services focused GPT audio-pop tests: `3 passed`.
- Services broad GPT reranker tests: `83 passed`.

## Launch Note

This improves Review clarity and defensive candidate accuracy. Internal TestFlight readiness still requires installed-app smoke, live deploy/preflight proof, and real labeled highlight accuracy evidence.
