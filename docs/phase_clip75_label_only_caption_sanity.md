# Phase Clip75: Label-Only Caption Sanity

## Goal

Prevent deterministic fallback edits from overclaiming a made basket in captions when the only evidence is a provider label like `Made Shot`. HoopClips should behave more like a careful shooting tracker: label-only candidates can stay in recall, but the rendered caption should stay neutral unless native shot signals or validated GPT evidence support the result.

## Changes

- Deterministic edit-plan captions now return `GOOD LOOK` instead of `BUCKET` for label-only shot result claims.
- Native shot-signal supported makes can still caption as `BUCKET`.
- GPT reranker prompt now explicitly treats `outcomeEvidenceSource=label_only` as unverified until sampled frames visibly prove the result.
- GPT compact payload includes `shotTrackerRules.treatLabelOnlyOutcomeEvidenceAsUnverified`.
- Added regression tests for:
  - label-only `Made Shot` fallback captions not becoming `BUCKET`.
  - native-supported made shots still allowing `BUCKET`.
  - GPT payload and instructions exposing the label-only caution.

## Architecture Notes

- Cloud backend remains responsible for analysis, GPT clip selection, edit planning, validation, rendering, storage, and clipping-quality improvements.
- iOS remains the upload/review/export/status/preview/share control surface.
- No iOS local analysis, rendering, composition, export, Remotion runtime, Canva runtime, or FFmpeg command generation was added.
- GPT still receives only compact candidate metadata plus sampled keyframes, never full videos.
- This keeps uncertain or label-only candidates reviewable while reducing misleading user-facing captions.

## Validation

Commands run from:

`/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_does_not_caption_label_only_made_claim_as_bucket ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_can_caption_native_supported_make_as_bucket ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_does_not_caption_uncertain_shot_attempt_as_bucket ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_rank_clips_prefers_native_outcome_evidence_over_label_only_make_claim -v
```

Result: passed. 4 tests passed, 0 failed.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_is_strict_structured_output_and_not_stored -v
```

Result: passed. 1 test passed, 0 failed.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py
```

Result: passed with exit code 0.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover ios/backend/tests -v
```

Result: passed. 165 tests passed, 0 failed.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover services/editing/tests -v
```

Result: passed. 93 tests passed, 0 failed.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Result: passed. 53 tests passed, 0 failed.

```bash
npm --prefix services/control-plane run typecheck
```

Result: passed with exit code 0.

```bash
npm --prefix services/control-plane test
```

Result: passed. 28 tests passed, 0 failed.

```bash
git diff --check
```

Result: passed with exit code 0.

## Remaining Blockers

- Real labeled basketball footage is still required before claiming the 85% selected-team/highlight quality target.
- Wired-iPhone/TestFlight smoke is still required before Apple submission.
- GitHub Actions PR checks are still blocked by no-step/no-log runner failures in the current branch history, despite equivalent local checks passing.
