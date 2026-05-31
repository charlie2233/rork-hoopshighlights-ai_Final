# Phase Clip157 Large Candidate Pool And Long Edits

## Goal

Increase highlight quality by giving the cloud GPT editor far more candidate clips to judge, while also letting users request longer cloud-rendered highlight edits up to `4:30` (`270s`).

## Architecture

- Cloud analysis owns candidate generation and now returns up to `160` candidates.
- iOS sends up to `160` existing candidate clips to AI Edit; it still does not analyze, render, compose, or export video locally.
- GPT-led editing still receives only candidate metadata and sampled keyframes, never full videos, R2 credentials, full presigned URLs, or raw FFmpeg commands.
- Backend validators still own template bounds, policy limits, watermark/outro rules, EditPlan repair, and deterministic FFmpeg render safety.

## Candidate Pool Changes

- `GPT_CANDIDATE_REVIEW_LIMIT` is now `160`.
- `HOOPS_MAX_RETURNED_CLIPS` defaults and deploy preflight requirements move from `60` to `160`.
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE` defaults and staging deploy requirements move from `60` to `160`.
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO` defaults and staging deploy requirements move from `60` to `160`.
- Free keeps `3` sampled keyframes per clip.
- Pro/internal keeps `5...8` sampled keyframes per clip.
- GPT timeout and output budget move to `120s` and `24000` output tokens so the larger strict JSON response has room.

## Long Edit Changes

- Free, Pro, internal, and dev policy caps now allow `270s` render targets.
- Free still stays capped at `3` AI edits/day, 720p, watermark, outro, and standard queue.
- Base and Pro template packs expose longer duration choices, including `270s`.
- Agent Template Cookbook duration rules mirror the TemplatePack duration options so GPT plan-edit context can direct longer stories safely.
- iOS AI Edit length chips use a horizontal scroller and friendly labels such as `4:30`.
- The pre-analysis target highlight length slider now reaches `270s`.

## Brand Credit

- Settings/About now includes a subtle `Created by atrak.dev with` credit using a `heart.fill` icon for the love mark.
- This is app UI only; it does not change cloud-rendered watermark/outro policy or exported video assets.

## Launch Notes

- Deploy analysis and editing together so the 160-candidate analysis pool, AI Edit request schema, GPT reranker caps, and staging defaults stay aligned.
- Longer edits can expose weak candidate recall faster; keep using labeled selected-team/highlight accuracy runs before claiming the 85% target.
- Current blockers from the launch readiness audit still apply: real-device internal smoke, live staging probes, current-commit deploy/upload workflows, and launch-grade accuracy evidence.

## Validation

- `git pull --ff-only`: branch was already up to date before edits.
- Static stale-cap sweep for the old `60`/`180` launch knobs: no stale candidate/duration caps found in the touched paths.
- `git diff --check`: passed.
- `python3 -m py_compile ios/backend/app/editing.py ios/backend/app/config.py services/editing/editing_app/gpt_reranker.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py`: passed.
- `python3 -m unittest scripts.test_launch_backend_config_preflight -v`: 7 tests passed.
- GPT reranker focused tests:

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_env_overrides_are_launch_bounded \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_caps_are_applied_before_openai_call -v
```

Result: 4 tests passed.

- Editing service focused tests:

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest \
  services.editing.tests.test_editing_service.EditingServiceTests.test_plan_tier_policy_defaults_are_safe_without_statsig \
  services.editing.tests.test_editing_service.EditingServiceTests.test_policy_rejection_emits_safe_policy_failed_event \
  services.editing.tests.test_editing_service.EditingServiceTests.test_render_over_free_policy_duration_rejected_before_render -v
```

Result: 3 tests passed.

- Pipeline quality focused tests:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_one_sixty \
  ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_backend_candidate_pool_env_is_clamped_for_review_safety -v
```

Result: 2 tests passed.

- Agent/template backend tests:

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v
```

Result: 100 tests passed.

- Launch config preflight:

```bash
python3 scripts/launch_backend_config_preflight.py --json
```

Result: `pass=81 warn=12 fail=0`.

- Cloud Build/GitHub workflow YAML parse:

```bash
ruby -e 'require "yaml"; YAML.load_file("services/editing/cloudbuild.yaml"); YAML.load_file("ios/backend/cloudbuild.yaml"); YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "yaml parses"'
```

Result: `yaml parses`.

- iOS Debug build-for-testing:

```bash
xcodebuild build-for-testing \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-clip157-bft \
  CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation
```

Result after the final Settings/About credit edit: `** TEST BUILD SUCCEEDED **`.
