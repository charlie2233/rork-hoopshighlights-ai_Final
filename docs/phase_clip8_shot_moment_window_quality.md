# Phase Clip8 Shot Moment Window Quality

## Goal

Improve HoopClips highlight selection quality by tightening cloud-owned shot semantics after the GPT-led editor work. This phase keeps iOS as the upload/review/status/preview/share control surface and keeps all candidate analysis, GPT selection, edit planning, validation, and rendering in the backend.

## What Changed

- Native candidate classification no longer labels a motion/context-only shot window as `Made Shot`.
- Native classifier now emits `Shot Attempt` and `Layup Attempt` for uncertain shot-like moments so GPT vision can decide made/missed/blocked from sampled keyframes.
- Native outcome hints now treat `Attempt` labels as `uncertain` instead of implying made baskets.
- GPT highlight decisions are rejected when a high-confidence native shot signal says the outcome was made/missed/blocked and GPT claims a conflicting outcome.
- The existing GPT patch forbidden-content scanner now also protects GPT highlight rerank decisions and plan-edit text from render commands, local-render instructions, URLs, storage keys, `.mp4` paths, and presigned URL markers.

## Architecture Notes

- No iOS rendering, composition, analysis, or export logic was added.
- GPT still receives only compact candidate metadata and extracted keyframes; full source videos and storage URLs stay out of the model payload.
- GPT may suggest captions, story role, slow motion, crop focus, and ordering, but backend validators now enforce both timing and outcome sanity before those suggestions reach an `EditPlan`.
- FFmpeg remains deterministic backend rendering only; GPT output containing raw render commands is rejected before it can become a caption, label, reason, or patch value.

## Quality Behavior

- Tiny and late/pre-basket clips remain excluded before GPT sampling.
- Complete shot windows remain eligible, but uncertain native labels do not overclaim made baskets.
- GPT cannot turn a native high-confidence miss into a made-shot caption.
- GPT cannot leak `ffmpeg -i source.mp4`, presigned URLs, storage keys, or local render directions into user-visible edit metadata.

## Validation Evidence

- Red test before implementation:
  - `test_gpt_highlight_rerank_rejects_outcome_conflicting_with_native_shot_signal` initially accepted a GPT made-shot claim over native `missed`.
  - `test_gpt_highlight_rerank_rejects_forbidden_render_command_content` initially accepted `ffmpeg -i source.mp4` as a caption.
  - `test_classifier_keeps_shot_candidate_without_claiming_made_outcome_from_motion_only_context` initially produced `Made Shot`.
- Focused green suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker -v`
  - Result: 92 tests passed.
- Full backend discovery:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 87 tests passed.
- Full editing service tests:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 65 tests passed.
- Control-plane guardrails:
  - `npm --prefix services/control-plane test`
  - Result: 20 tests passed.
  - `npm --prefix services/control-plane run typecheck`
  - Result: passed.
- Hygiene:
  - `python3 -m py_compile ios/backend/app/classifier.py ios/backend/app/editing.py ios/backend/app/pipeline.py services/editing/editing_app/gpt_reranker.py`
  - `git diff --check`
  - Result: passed.

## Launch Recommendation

Keep this behind the existing GPT/editor feature flags and deploy to staging with the rest of the GPT-led highlight pipeline. For internal beta, use real upload -> analysis -> GPT rerank -> render smoke clips to compare caption/outcome sanity against the previous `Made Shot` overclaim behavior.
