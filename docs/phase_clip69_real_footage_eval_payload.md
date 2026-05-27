# Phase Clip69: Real-Footage Eval Payload Builder

## Goal

Make the 85% selected-team highlight proof easier to produce from real internal footage. The repo already had the scoring harness, but testers still had to hand-build evaluator JSON. This phase adds a safe metadata-only builder that combines a real cloud analysis result with manual labels.

## Change

- Added `scripts/build_team_highlight_eval_payload.py`.
- The builder reads a cloud analysis job/result JSON plus a manual labels JSON and emits `team-highlight-eval-v1` payloads for `scripts/evaluate_team_highlight_accuracy.py`.
- Manual labels can match prediction clips by `predictionIndex`, `predictionClipId`, or time overlap.
- The builder fails by default when analysis returned prediction clips that were not manually labeled, so precision cannot be inflated by ignoring bad returned clips.
- The evaluator now treats review-included uncertain clips as recall evidence for selected-team highlights and defensive events, even when they are not auto-kept. This matches the product goal that lower-confidence clips should remain available for user review instead of being silently dropped.

## Manual Label Shape

```json
{
  "caseId": "internal_game_001",
  "selectedTeamId": "team_dark",
  "clips": [
    {
      "labelId": "q1_made_three_001",
      "start": 12.2,
      "end": 16.5,
      "expected": {
        "teamId": "team_dark",
        "isHighlight": true,
        "eventType": "made_three",
        "outcome": "made"
      }
    }
  ]
}
```

## Commands

```bash
python3 -m scripts.build_team_highlight_eval_payload \
  --analysis-result path/to/cloud_analysis_job.json \
  --labels path/to/manual_labels.json \
  --output path/to/team_highlight_eval.json

python3 -m scripts.evaluate_team_highlight_accuracy path/to/team_highlight_eval.json --json
```

## Validation

```bash
python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/build_team_highlight_eval_payload.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py
# Result: passed

python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_build_team_highlight_eval_payload -v
# Result: 14 tests passed

git diff --check
# Result: passed
```

## Launch Note

This creates the artifact path for the real-footage proof, but it is not itself the proof. Internal launch still needs actual labeled footage run through this builder/evaluator with selected-team makes, misses, blocks, steals, forced turnovers, uncertain review clips, opponent highlights, and bad-window negatives.
