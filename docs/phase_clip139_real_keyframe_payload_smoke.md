# Phase Clip139: Real Keyframe Payload Smoke

## Goal

Prove the GPT-led editor path can use real FFmpeg keyframe extraction without sending full videos, source object keys, local file paths, or presigned URLs to GPT. Earlier coverage already checked the compact payload builder with synthetic `SampledFrame` objects; this phase adds a real extraction smoke around a generated MP4.

## What Changed

- Added a backend test that creates a tiny synthetic MP4 with FFmpeg.
- The test runs `_extract_candidate_keyframes` against that real video.
- The resulting GPT payload is checked for:
  - required `start`, `eventCenter`, and `finish` sampled keyframe roles
  - JPEG data URLs in `input_image` items
  - compact `sampledKeyframes` metadata in the JSON text
  - no `sourceObjectKey`
  - no source video filename or local file URL
  - no full-video path in the serialized payload

This is still cloud/backend-only test coverage. It does not add iOS rendering, local analysis, or client-side composition.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_real_ffmpeg_keyframe_extraction_builds_compact_payload_without_source_video -v` -> 1 test passed.
- `python3 -m py_compile services/editing/tests/test_gpt_reranker.py` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` -> 60 tests passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 109 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Keep this test in the backend CI path. If it fails in CI, treat that as a clipping-quality blocker because GPT cannot be trusted as final semantic editor without real sampled frame evidence.
