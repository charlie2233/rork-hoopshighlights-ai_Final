# Phase UX22: Audio Reaction Raw Fallback

## Goal

Keep loud crowd-pop moments in the cloud candidate pool even when the visual segmentation path does not form a clean segment.

## Change

The native cloud candidate builder already extracts an FFmpeg audio profile, detects spike/cluster/swell reaction cues, builds reaction windows around those moments, and treats them as recall hints for GPT review.

This phase applies the same audio-reaction reserve pass to the raw-window fallback path. Before this change, the reserve was guaranteed only when the visual hysteresis path produced segmented candidates. Now, if segmentation returns no candidates and the backend falls back to combined-score window ranking, loud crowd-pop windows are still reserved into the final candidate pool.

## Safety

- Audio reactions remain recall hints, not automatic scoring claims.
- Crowd-pop-only clips still stay review-first unless frames show clear basketball action and outcome.
- GPT still receives compact candidate metadata/keyframes only; full videos and FFmpeg commands are not sent to GPT.
- Rendering remains deterministic and cloud-owned.

## Validation

Passed:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_raw_candidate_fallback_reserves_loud_crowd_pop_for_review \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_boundaries_detect_loud_local_crowd_pops \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_candidate_windows_include_crowd_pop_recall_anchor_for_gpt_review \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_unlabeled_audio_only_filler_is_not_audio_reaction_candidate \
  -v
```

Result: 4 tests passed.

Also passed:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
```

Result: 82 tests passed.

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_marks_crowd_reaction_candidates_as_audio_recall_hints \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_sampling_reserves_audio_reaction_recall_candidate_when_scoring_fills_cap \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_sampling_reserves_three_audio_reactions_for_free_pool \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_audio_reaction_detection_ignores_weak_audio_only_filler \
  -v
```

Result: 4 tests passed.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py
```

Result: passed.

```bash
git diff --check
```

Result: passed.

## Launch Notes

This should improve recall for clips where a crowd/bench reaction points to a nearby block, steal, finish, or momentum play. It does not lower the visual-evidence gate for final GPT selection.
