# Phase Clip73: Outcome Reliability Ranking

## Goal

Improve deterministic and GPT-fallback clip quality by preferring shot clips with cloud-supported outcome evidence over higher-scored but uncertain or overclaimed provider shot labels. This helps avoid misleading made-shot highlights, pre-basket clips, and duplicate cleanup choices that keep the wrong version of the same play.

## Changes

- Added `clip_outcome_reliability_score` in the cloud edit-planning backend.
- Updated `rank_clips` so eligible clips still require good timing/context, then prefer supported shot outcomes before generic planning score.
- Updated duplicate cleanup so two versions of the same moment keep the one with stronger outcome support.
- Kept defensive events such as blocks, steals, forced turnovers, and defensive stops highly reliable so they are not pushed out by shot-only logic.
- Added regression tests for:
  - supported made-shot evidence outranking a higher-confidence but uncertain provider-overclaimed make.
  - duplicate cleanup keeping the supported shot version instead of the overclaimed duplicate.

## Architecture Notes

- Cloud backend still owns analysis, GPT selection, edit planning, validation, rendering, storage, and clipping-quality improvements.
- iOS remains the control surface for upload, review, export choices, status/timeline, preview, download, and share.
- This patch does not add iOS local video analysis, rendering, composition, export, Remotion, Canva, or FFmpeg behavior.
- GPT remains optional and validated; deterministic fallback now has a stronger outcome-evidence preference when GPT is disabled, invalid, or unavailable.
- No full videos are sent to GPT, and GPT still cannot generate FFmpeg commands or bypass EditPlan validation.

## Validation

Commands run from:

`/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_rank_clips_prefers_supported_outcome_over_higher_scored_uncertain_shot ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_duplicate_cleanup_prefers_supported_outcome_over_overclaimed_duplicate -v
```

Result: passed. 2 tests passed, 0 failed.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m py_compile ios/backend/app/editing.py
```

Result: passed with exit code 0.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover ios/backend/tests -v
```

Result: passed. 162 tests passed, 0 failed.

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

## Post-Push CI Observation

PR #32 commit `4b5fd70f99c023469f10a1b7a61e4ac09393631c` was checked after push.

- Cloud Edit Deploy Preflight run `26534405534` failed before exposing step logs.
- `Worker typecheck and dry run` job `78159296953`: failure, `steps: null`, `logs_url: null`.
- `Editing backend Python tests` job `78159297026`: failure, `steps: null`, `logs_url: null`.
- `Verify cloud edit deploy secrets` job `78159307818`: skipped.
- iOS Internal TestFlight Upload run `26534405536` failed before exposing step logs.
- `No-secret internal staging codecheck` job `78159297114`: failure, `steps: null`, `logs_url: null`.
- `Build internal staging TestFlight archive` job `78159297792`: skipped.

## Remaining Blockers

- Real labeled basketball footage is still required before claiming the 85% selected-team/highlight quality target.
- Wired-iPhone/TestFlight smoke is still required before Apple submission.
- PR CI remains blocked by GitHub jobs that fail before recording steps/logs, while equivalent local checks passed.
