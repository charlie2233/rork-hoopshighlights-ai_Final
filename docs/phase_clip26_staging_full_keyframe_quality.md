# Phase Clip26 Staging Full Keyframe Quality

## Goal

Improve GPT-led clip selection quality in staging by making the quality-beta deploy default use the full 10-frame shot-tracker keyframe package.

The code default already supported 10 frames per clip. Staging Cloud Build still pinned `_AI_CLIP_GPT_KEYFRAMES_PER_CLIP=8`, which meant quality-beta deploys could miss the dedicated `rimApproach`, `rimEntry`, and `belowRim` evidence path unless an operator remembered an override.

## Change

- Updated `services/editing/cloudbuild.yaml`:
  - `_AI_CLIP_GPT_KEYFRAMES_PER_CLIP: "10"`
- Updated `scripts/launch_backend_config_preflight.py` so static preflight expects the 10-frame quality default.
- Added a launch-script test proving the expected GPT keyframe default is 10.
- Updated the older Clip22 note to mark the 8-frame staging default as superseded.

## Safety

- GPT/editor kill switches stay off by default in Cloud Build:
  - `_AI_CLIP_GPT_EDITOR_ENABLED: "false"`
  - `_AI_CLIP_GPT_PLAN_EDIT_ENABLED: "false"`
  - `_AI_CLIP_GPT_REVISION_ENABLED: "false"`
  - `_GPT_HIGHLIGHT_RERANKER_ENABLED: "false"`
- This does not enable public cloud cutover.
- This does not change iOS local behavior.
- No full videos are sent to GPT.
- GPT still receives sampled keyframes from existing candidates only.

## Red Evidence

```text
python3 -m unittest scripts.test_launch_backend_config_preflight.LaunchBackendConfigPreflightTests.test_quality_beta_uses_full_shot_tracker_keyframe_default -v

FAIL: '8' != '10'
```

## Validation

```text
python3 -m unittest scripts.test_launch_backend_config_preflight.LaunchBackendConfigPreflightTests.test_quality_beta_uses_full_shot_tracker_keyframe_default scripts.test_launch_backend_config_preflight.LaunchBackendConfigPreflightTests.test_current_repo_has_no_static_failures -v
Ran 2 tests in 0.014s
OK

python3 -m py_compile scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py
OK

python3 -m unittest discover -s scripts -p 'test_*.py' -v
Ran 35 tests in 0.160s
OK

python3 scripts/launch_backend_config_preflight.py --json
status=pass, summary: fail=0, pass=63, warn=12

git diff --check
OK
```

## Launch Recommendation

Use the 10-frame staging default for internal quality-beta GPT smoke runs. This better matches the product goal: GPT should judge shots from setup, release, shot arc, rim approach, rim entry, and follow-through evidence instead of generic before/after frames.
