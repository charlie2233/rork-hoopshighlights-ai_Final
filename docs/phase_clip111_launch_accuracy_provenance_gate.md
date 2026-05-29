# Phase Clip111: Launch Accuracy Provenance Gate

## Goal

Tighten the selected-team/highlight accuracy launch gate so HoopClips cannot be marked ready from a thin or synthetic passing JSON report. The real 85% target still needs a labeled internal footage run, but the submission preflight now requires proof that the report came from real cloud analysis output joined with manual labels.

## What Changed

- `scripts/evaluate_team_highlight_accuracy.py` now emits a sanitized `evidence` summary with every JSON report:
  - `inputSchemaVersion`
  - `inputSource`
  - `caseCount`
  - `distinctVideoCount`
  - missing case/video/team/analysis-job counts
- `scripts/build_team_highlight_eval_payload.py` carries `analysisJobId` into each eval case when building from cloud analysis JSON.
- `scripts/submission_readiness_preflight.py` now requires launch accuracy reports to prove:
  - evaluator input schema is `team-highlight-eval-v1`
  - source is `real_cloud_analysis_with_manual_labels`
  - distinct video count meets the default launch case floor
  - no case is missing `caseId`, `videoId`, `selectedTeamId`, or `analysisJobId`
  - all existing 85% metric and coverage thresholds remain default-or-stricter

The evidence summary contains counts and provenance fields only. It does not print source object keys, presigned URLs, credentials, raw model payloads, or full video data.

## Why

The evaluator already checks selected-team precision, evidence quality, recall with uncertain review clips, highlight precision/recall, blocks, steals, timing quality, shot outcome evidence, opponent highlights, negative clips, and bad-window negatives. The remaining launch risk was that submission readiness could accept a fabricated report with plausible metric numbers. This phase makes the preflight demand launch-grade provenance before it accepts the report.

## Required Launch Flow

1. Run cloud analysis on internal footage.
2. Create manual labels with `caseId`, `videoId`, selected team, expected highlight/team/event/outcome rows, and hard negative rows.
3. Build the evaluator payload:

```bash
python3 scripts/build_team_highlight_eval_payload.py \
  --analysis-result artifacts/analysis_game_001.json \
  --labels artifacts/labels_game_001.json \
  --output artifacts/team_highlight_eval_game_001.json
```

4. Combine enough cases to satisfy launch defaults.
5. Generate the report:

```bash
python3 -m scripts.evaluate_team_highlight_accuracy artifacts/team_highlight_eval.json --json \
  > artifacts/team_highlight_accuracy_report.json
```

6. Run submission preflight:

```bash
python3 scripts/submission_readiness_preflight.py \
  --team-accuracy-report artifacts/team_highlight_accuracy_report.json
```

## Validation

- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/build_team_highlight_eval_payload.py scripts/submission_readiness_preflight.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py scripts/test_submission_readiness_preflight.py` passed.
- `python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_build_team_highlight_eval_payload scripts.test_submission_readiness_preflight -v` passed: 45 tests.
- `git diff --check` passed.

## Launch Recommendation

Do not submit or claim the 85% selected-team/highlight target until the stricter preflight passes with a real labeled-footage report. The report should include multiple distinct videos, makes, misses, blocks, steals, opponent highlights, bad-window negatives, and uncertain team cases that remain reviewable.
