# Phase Clip4 Visual Story Quality

Date: 2026-05-26
Branch: `codex/phase-clip4-visual-story-quality`

## Goal

Improve HoopClips highlight quality beyond simple shot tracking by preventing GPT and native analysis from promoting tiny, late, audio-only, duplicate, or visually unsupported basketball moments.

Cloud remains the owner of analysis, GPT clip selection, edit planning, rendering, storage, and receipts. iOS behavior is unchanged in this phase.

## Audit Findings

- `services/inference` is not present in this checkout; the active inference/analysis path is under `ios/backend/app`.
- Native classifier labels were too trusting of audio/motion windows. A no-boundary audio spike could become a shot-like label, then later pass shot-context checks because the label made it look like a basketball scoring event.
- GPT quality signals were required by the OpenAI schema, but the backend model defaulted missing signal booleans to `true` when constructed from non-schema callers.
- GPT-kept duplicate moments were deduped by explicit `duplicateGroup`, but overlapping clips without a duplicate group could both survive.
- AI Work Receipt exposed GPT sampled/kept/rejected counts, but not the rejection reason mix needed to understand why bad clips were filtered.

## Changes

- Made `GPTHighlightQualitySignals` fail closed: all visual quality booleans and the reason must be explicitly supplied.
- Added source/GPT consistency validation so a generic audio-heavy `Highlight` cannot be accepted as a made/missed/blocked scoring event just because GPT says all quality booleans are true.
- Added overlap/event-center duplicate suppression after GPT decisions, keeping the stronger window and recording dropped duplicate IDs.
- Added `rejectedReasonCounts` to `GPTHighlightRerankSummary` and surfaced it in `AIWorkReceipt`/summary rows.
- Updated native `classify_window` so shot-like labels require native shot context. Audio-only windows stay generic and do not auto-keep.

## Safety

- GPT still receives only existing candidate clips plus sampled JPEG keyframes.
- GPT cannot create raw FFmpeg commands, local render instructions, storage keys, source URLs, or exact timestamps.
- Deterministic backend validators still own `EditPlan` repair/validation and FFmpeg rendering.
- No secrets, R2 credentials, or full presigned URLs were added or logged.

## Validation

Focused validation:

```sh
python3 -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/editing_app/models.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_decision_rejects_partial_quality_signals ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_generic_audio_only_scoring_claim ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_dedupes_overlapping_kept_clips_without_duplicate_group services.editing.tests.test_editing_service.EditingServiceTests.test_gpt_highlight_rerank_summary_feeds_render_receipt -v
python3 -m py_compile ios/backend/app/classifier.py ios/backend/tests/test_pipeline_quality.py
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_classifier_does_not_call_audio_only_window_a_shot ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_ranking_prefers_complete_shot_context_over_later_audio_spike ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_shot_motion_over_audio_only_spike -v
```

Results:

- Python compile checks passed.
- GPT quality/source/overlap/receipt focused checks: 4 tests passed.
- Native classifier/pipeline focused checks: 3 tests passed.

Broad validation:

```sh
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker services.editing.tests.test_editing_service ios.backend.tests.test_pipeline_quality -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
git diff --check
```

Results:

- Combined edit-plan/GPT-reranker/editing-service/pipeline suite: 118 tests passed.
- iOS backend discovery suite: 73 tests passed.
- Services editing discovery suite: 65 tests passed.
- `git diff --check`: passed.

## Remaining Launch Gaps

- Live staging GPT smoke with a real basketball upload is still needed after provider deploy gates are cleared.
- Cloudflare `staging / CLOUDFLARE_API_TOKEN`, deploy-secret proof, signed TestFlight archive, and wired-device installed TestFlight smoke remain outside this code-only phase.
- Future work should make `hybrid` detection a true native-plus-external union and expand native recall to return more high-recall windows before GPT selection.
