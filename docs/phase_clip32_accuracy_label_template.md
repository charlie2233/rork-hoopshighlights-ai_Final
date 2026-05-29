# Phase Clip32: Accuracy Label Template

## Goal

Make the launch-grade selected-team/highlight accuracy gate easier to complete without weakening it. The submission preflight already requires a real `team-highlight-eval-v1` report from manually labeled cloud-analysis output; this phase adds a safe label-template generator so the team can export real staging analysis, label every predicted clip, and build the required evaluation payload without inventing evidence.

## What Changed

- Added `scripts/make_team_highlight_label_template.py`.
- The generator reads a real HoopClips cloud analysis result and emits a metadata-only manual-label template.
- Each predicted clip row includes:
  - `predictionIndex`
  - `predictionClipId`
  - `start` / `end`
  - `predicted` team/highlight summary
  - blank `expected.teamId`, `expected.isHighlight`, `expected.eventType`, and `expected.outcome`
  - `needsLabel: true`
- `scripts/build_team_highlight_eval_payload.py` now refuses template rows until `needsLabel` is set to `false` and the required expected labels are filled.

The template intentionally does not copy presigned URLs, storage keys, credentials, or video bytes. It is only for human review labels and launch evidence.

## How To Use

Export a real staging cloud analysis JSON, then create a human-label template:

```bash
python3 -m scripts.make_team_highlight_label_template \
  --analysis-result artifacts/staging_analysis_result.json \
  --output artifacts/team_highlight_manual_labels.json \
  --case-id internal_game_001 \
  --video-id internal_video_001
```

Fill every row in `artifacts/team_highlight_manual_labels.json`:

```json
{
  "needsLabel": false,
  "expected": {
    "teamId": "team_dark",
    "isHighlight": true,
    "eventType": "steal",
    "outcome": "forced_turnover"
  }
}
```

Then build and score the launch evidence:

```bash
python3 -m scripts.build_team_highlight_eval_payload \
  --analysis-result artifacts/staging_analysis_result.json \
  --labels artifacts/team_highlight_manual_labels.json \
  --output artifacts/team_highlight_eval.json

python3 -m scripts.evaluate_team_highlight_accuracy \
  artifacts/team_highlight_eval.json \
  --json > artifacts/team_highlight_accuracy_report.json

python3 scripts/submission_readiness_preflight.py \
  --team-accuracy-report artifacts/team_highlight_accuracy_report.json
```

## Guardrails

- Real cloud analysis is still required.
- Human labels are still required.
- Unfilled template rows fail before scoring.
- Blocks, steals, defensive stops, opponent clips, boring clips, bad-window negatives, and uncertain review clips should stay in the label file so the accuracy report cannot be inflated.
- This does not claim the 85% launch target by itself; it only makes the evidence path repeatable.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `python3 -m unittest scripts.test_build_team_highlight_eval_payload -v` -> 5 tests passed.
- `python3 -m py_compile scripts/build_team_highlight_eval_payload.py scripts/make_team_highlight_label_template.py scripts/test_build_team_highlight_eval_payload.py` -> passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 86 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use this template flow for the next real TestFlight smoke video. Once the cloud analysis result is exported and every row is manually labeled, the generated report can satisfy the submission preflight's selected-team/highlight accuracy evidence gate if the metrics pass the launch thresholds.
