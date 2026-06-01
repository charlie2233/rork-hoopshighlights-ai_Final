# Phase Launch150 GPT Full Keyframe Staging

## Goal

Improve GPT-led highlight accuracy for internal beta by making staging use the full 10-keyframe shot-tracker package. This gives GPT visible setup, release, shot arc, rim approach, rim entry, below-rim/follow-through, and defensive outcome context instead of stopping at the older 8-frame cap.

## Changes

- Raised `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP` default/clamp for Pro/internal GPT editing from `8` to `10`.
- Updated direct staging deploy paths to pass `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP=10`:
  - `services/editing/cloudbuild.yaml`
  - `.github/workflows/cloud-edit-deploy-preflight.yml`
- Updated launch preflight expected substitutions to require the 10-frame staging default.
- Updated GPT reranker tests and config docs for the `5...10` Pro/internal keyframe range.
- Reconciled launch preflight with the current quality-over-cost candidate pool:
  - GPT candidate caps stay at `220` for Free and Pro/internal.
  - Analysis returned/team-scan candidate caps stay at `220` where applicable.
- Updated iOS Free/Pro smoke copy to assert `3 AI edits/day` and `25 AI edits/day`.

## Architecture Notes

- Cloud remains the owner of keyframe extraction, GPT clip selection, EditPlan generation, rendering, and storage.
- iOS behavior is unchanged.
- GPT still receives sampled keyframes from existing candidate clips only.
- Full videos, FFmpeg commands, R2 credentials, and presigned URLs are still not sent to GPT.
- Free edit availability and daily Free edit quota are unchanged by this phase.
- Free daily AI edit quota remains `3`.

## Validation

- `git diff --check` passed.
- Python compile passed:

```sh
python3 -m py_compile services/editing/editing_app/gpt_reranker.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py
```

- Launch backend config preflight tests passed:

```sh
python3 -m unittest scripts.test_launch_backend_config_preflight -v
```

- Focused GPT reranker tests passed with the repo backend venv:

```sh
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_env_overrides_are_launch_bounded services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment -v
```

- iOS Debug `build-for-testing` passed:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO build-for-testing
```

- Note: the same GPT reranker unittest command failed under system `python3` because that interpreter does not have `pydantic`; rerunning under `ios/backend/.venv/bin/python` passed.

## Launch Notes

- This is an accuracy-over-cost beta setting. It is appropriate for internal TestFlight/staging quality review.
- Keep monitoring OpenAI payload failures and timing, but do not reduce the keyframe count before labeled user feedback unless request size becomes a real blocker.
