# Phase Clip61 Quality-Over-Cost GPT Candidate Window

## Goal

Increase the cloud-owned candidate window that reaches GPT-led highlight editing so HoopClips can favor accuracy and user review quality over marginal inference cost during internal beta.

## Architecture

- Cloud analysis still owns candidate generation, team quick scan, team attribution, clip filtering, GPT semantic editing, EditPlan generation, rendering, and storage.
- iOS remains a control surface: import/upload, selected-team choice, Review, Export configuration, status/timeline, preview, download, and share.
- GPT receives only existing candidate clip metadata plus sampled keyframes. Full videos, raw FFmpeg commands, secrets, R2 credentials, and full presigned URLs are not sent.
- Deterministic validators still enforce template, policy, timing, watermark/outro, caption, and render-safety bounds before the renderer runs.

## Behavior

- `HOOPS_MAX_RETURNED_CLIPS` now defaults to `40`, matching the analysis clamp and giving Review/AI Edit the full high-recall pool.
- GPT candidate review caps now default to `40` for Free and Pro/internal. Free availability stays broad for acquisition, while daily Free editing chances remain governed by the quota layer.
- GPT keyframes stay at the quality-beta ceiling of `10` frames per clip. This preserves richer release, arc, rim, outcome, block, steal, and follow-through evidence.
- GPT request timeout and structured-output budget are widened to `60` seconds and `8000` tokens so 40 decisions plus plan-edit JSON can fit without truncation.
- iOS now forwards the strongest 40 cloud-edit candidates, preserving complete shot context and defensive highlights before sorting back to timeline order.

## Config

- Analysis backend:
  - `_MAX_RETURNED_CLIPS: "40"`
  - `HOOPS_MAX_RETURNED_CLIPS` clamp remains `8...40`
- Editing service:
  - `_AI_CLIP_GPT_MAX_CANDIDATES_FREE: "40"`
  - `_AI_CLIP_GPT_MAX_CANDIDATES_PRO: "40"`
  - `_AI_CLIP_GPT_KEYFRAMES_PER_CLIP: "10"`
  - `_AI_CLIP_GPT_TIMEOUT_SECONDS: "60"`
  - `_AI_CLIP_GPT_MAX_OUTPUT_TOKENS: "8000"`

## Fallback

When GPT is disabled, fails, or returns no valid decisions, the backend still ranks eligible CV/runtime candidates deterministically. Fallback summaries are now also sized for a 40-candidate window, so AI Work Receipt evidence stays aligned with the widened pool.

## Validation

- `python3 -m py_compile ios/backend/app/config.py ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/editing_app/models.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py` -> passed.
- `python3 -m unittest scripts.test_launch_backend_config_preflight -v` -> 4 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_forty ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_backend_candidate_pool_env_is_clamped_for_review_safety -v` -> 2 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_candidate_cap_is_generous_but_bounded -v` -> 3 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 149 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 92 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 43 tests passed.
- XcodeBuildMCP `build_sim` with `-skipMacroValidation` -> succeeded for `HoopsClips` Debug on iPhone 17 Pro simulator. Existing warnings remain in `CloudAnalysisService.swift` and `VideoExportService.swift`.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip61-bft -skipMacroValidation build-for-testing` -> `** TEST BUILD SUCCEEDED **`.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip61-bft -skipMacroValidation -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsStrongestCandidatesBeforeFortyClipCap test-without-building` -> `** TEST EXECUTE SUCCEEDED **`.
- `python3 scripts/launch_backend_config_preflight.py` -> 74 pass, 12 warn, 0 fail. Warnings are existing production cutover, Statsig/Sentry/RevenueCat backend config, and staging ingress posture gates.
- `git diff --check` -> passed.

## Launch Recommendations

- Keep this enabled for internal TestFlight and staging quality review.
- Use labeled beta footage to measure selected-team and final-highlight accuracy against the 85% target.
- Keep uncertain but review-worthy clips in Review rather than silently discarding them.
- Revisit per-tier candidate caps only after real usage and OpenAI/R2 cost telemetry are available.
