# Phase Clip74: Label-Only Outcome Evidence

## Goal

Improve fallback and GPT-assisted clip selection by separating real cloud-native shot outcome evidence from label-only claims such as `Made Shot`. A provider label can still help recall, but it should not outrank a lower-scored clip whose native shot signals support the visible result.

## Changes

- Added `clip_outcome_evidence_source` to classify candidate outcome support as `native_shot_signals`, `label_only`, `uncertain`, `not_shot`, `defensive_event`, or `non_shot`.
- Lowered shot outcome reliability for label-only made/missed claims while keeping them above explicit uncertain shots.
- Kept native shot-signal evidence as the strongest shot-result signal for deterministic ranking and duplicate cleanup.
- Added outcome evidence source and reliability score into Agent Template Cookbook candidate context.
- Added outcome evidence source and reliability score into the GPT highlight reranker compact payload and quality hints.
- Added regression tests proving:
  - native shot outcome evidence beats a higher-scored label-only made-shot claim.
  - supported outcome evidence still beats uncertain provider-overclaimed shots.
  - GPT payloads include outcome evidence source and reliability without storing video URLs or secrets.

## Architecture Notes

- Cloud backend remains responsible for analysis, GPT clip selection, edit planning, validation, rendering, storage, and clipping-quality improvements.
- iOS remains the upload/review/export/status/preview/share control surface.
- No iOS local video analysis, rendering, composition, export, Remotion runtime, Canva runtime, or FFmpeg command generation was added.
- GPT still receives only compact candidate metadata plus sampled keyframes, never full videos.
- Label-only candidates remain available for recall and user review; the change only prevents them from pretending to be stronger than native outcome evidence.

## Validation

Commands run from:

`/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_rank_clips_prefers_native_outcome_evidence_over_label_only_make_claim ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_rank_clips_prefers_supported_outcome_over_higher_scored_uncertain_shot ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_duplicate_cleanup_prefers_supported_outcome_over_overclaimed_duplicate ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_agent_editing_context_is_compact_and_template_specific -v
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

Result: passed. 163 tests passed, 0 failed.

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
