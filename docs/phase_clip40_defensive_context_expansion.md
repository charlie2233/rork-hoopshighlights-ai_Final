# Phase Clip40: Defensive Context Expansion

## Goal

Improve selected-team highlight quality for steals, blocks, forced turnovers, and defensive stops by preventing tight provider/native windows from reaching Review or GPT as event-only snippets.

## Change

- Cloud analysis now expands defensive clips around `eventCenter` before enforcing minimum duration.
- GPT rerank preparation now expands defensive candidate clips from the source duration before keyframe extraction.
- Defensive GPT context now includes a `defensiveEventLike` quality hint so GPT can distinguish non-scoring defensive highlights from generic filler.
- Generic non-defensive clips remain unchanged.

## Why

Steals and defensive stops can arrive as very short windows centered on the possession change. Those clips are bad user-facing highlights and often fail GPT timing gates before the model can judge them. Expanding around the event gives GPT and the renderer a full play: setup, challenge or possession change, recovery, and outcome.

## Safety

- This stays cloud-side only.
- GPT still receives sampled keyframes and compact clip metadata, not full videos.
- GPT still cannot output FFmpeg commands, storage keys, URLs, or raw renderer instructions.
- Renderer execution remains deterministic and validator-gated.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_normalization_expands_tiny_defensive_clip_with_event_center -v` -> 1 test passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_source_context_expansion_salvages_thin_defensive_windows_before_gpt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_source_context_expansion_salvages_thin_shot_windows_before_gpt -v` -> 2 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 124 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 85 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 40 tests passed.

## Launch Recommendation

Use this alongside team quick scan and GPT defensive frame roles. Keep measuring the 85% target with labeled footage; this phase improves the input quality for that measurement but does not claim the target by itself.
